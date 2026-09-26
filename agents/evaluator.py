"""Agent Évaluateur (protocole §14.8, §12, §11.2, §21 « Évaluateur »).

Rôle :
- joindre les labels finaux UNIQUEMENT après la prédiction (§14.8) ;
- calculer les métriques par prédiction : log_loss_1x2, brier_1x2, rps_1x2,
  score_bucket_log_loss, MAE corners/cartons, CRPS (§12) ;
- agréger avec bootstrap stratifié et GROUPÉ PAR MATCH (§11.2, §12.5) ;
- calibration : ECE 1X2 (bins annoncés), PIT randomisé et couverture des
  intervalles pour les comptages (§12.4, §12.3) ;
- comparer les modèles à la référence « laya » avec Holm-Bonferroni sur les
  familles pré-définies (une famille par cible, décision annexe B) ;
- publier les dénominateurs de chaque métrique (§19.2.5) ;
- bloquer si un seuil §11.4 est dépassé.

Usage (§16) :
    python -m agents.evaluator --run-id RUN_ID [--config configs/experiment.yaml]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from agents.baselines import load_baseline_predictions
from agents.common import (
    bulk_upsert,
    config_paths,
    load_config,
    log_error,
    log_event,
    now_utc,
    setup_logging,
    sha256_text,
    write_artifact,
)
from src.core.metrics import (
    accuracy_top,
    brier_multiclass,
    crps_discrete,
    ece,
    log_loss,
    log_score_discrete,
    mae,
    pit_randomized,
    predictive_interval_coverage,
    rps,
    tail_mass,
)
from src.core.stats import compare_models
from src.core.stats import stratified_group_bootstrap as group_bootstrap
from src.core.tasks import (
    corners_to_level,
    expected_value,
    order_for_task,
    score_bucket_to_1x2,
    score_to_bucket,
    yellows_to_level,
)
from src.storage.database import Database

AGENT_NAME = "evaluator"
PRODUCER = "evaluator_agent"

# Familles de tests Holm-Bonferroni (une par cible, décision annexe B).
COMPARISON_FAMILIES: dict[str, tuple[str, str]] = {
    "1x2_log_loss": ("log_loss_1x2", "1x2"),
    "score_bucket_log_loss": ("score_bucket_log_loss", "score_bucket"),
    "corners_crps": ("corners_crps", "corners"),
    "yellow_cards_crps": ("yellow_cards_crps", "yellow_cards"),
}

REFERENCE_MODEL = "laya"
"""Référence des comparaisons : le système sous test (question §1.1)."""

METRIC_KEYS = [
    "log_loss_1x2",
    "brier_1x2",
    "rps_1x2",
    "accuracy_1x2",
    "score_bucket_log_loss",
    "accuracy_score_bucket",
    "corners_crps",
    "corners_log_score",
    "corners_mae",
    "corners_tail_mass",
    "corners_coverage_50",
    "corners_coverage_80",
    "corners_coverage_95",
    "yellows_crps",
    "yellows_log_score",
    "yellows_mae",
    "yellows_tail_mass",
    "yellows_coverage_50",
    "yellows_coverage_80",
    "yellows_coverage_95",
    "mae_goals",
]


def _pit_u(prediction_id: str, seed: int) -> float:
    """Tirage uniforme déterministe pour le PIT randomisé (§12.3)."""
    digest = hashlib.sha256(f"{seed}:{prediction_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def evaluate_prediction(
    tasks: dict[str, dict[str, float]], actual: dict[str, Any], seed: int
) -> dict[str, float]:
    """Métriques d'une prédiction face aux labels finaux (§12).

    Le 1X2 est TOUJOURS dérivé de la distribution de score regroupé (§8.1),
    sauf pour les modèles qui prédisent directement le 1X2 (logistique).
    """
    metrics: dict[str, float] = {}
    if "score_bucket" in tasks:
        dist = tasks["score_bucket"]
        order = order_for_task("score_bucket")
        values = [dist[cat] for cat in order]
        bucket = score_to_bucket(actual["home_goals"], actual["away_goals"])
        idx = order.index(bucket)
        metrics["score_bucket_log_loss"] = log_loss(values, idx)
        metrics["accuracy_score_bucket"] = accuracy_top(values, idx)
        one_x_two = score_bucket_to_1x2(dist)
        metrics["expected_goals"] = expected_value(dist)
    elif "one_x_two" in tasks:
        one_x_two = dict(tasks["one_x_two"])
    else:
        raise ValueError("prédiction sans tâche exploitable")

    result = (
        "1" if actual["home_goals"] > actual["away_goals"]
        else "2" if actual["home_goals"] < actual["away_goals"]
        else "X"
    )
    order_1x2 = ["1", "X", "2"]
    values_1x2 = [one_x_two.get(cat, 0.0) for cat in order_1x2]
    idx_1x2 = order_1x2.index(result)
    metrics["log_loss_1x2"] = log_loss(values_1x2, idx_1x2)
    metrics["brier_1x2"] = brier_multiclass(values_1x2, idx_1x2)
    metrics["rps_1x2"] = rps(values_1x2, idx_1x2)
    metrics["accuracy_1x2"] = accuracy_top(values_1x2, idx_1x2)
    metrics["p_realized_1x2"] = values_1x2[idx_1x2]

    for target, task, level_fn, cap in (
        ("corners", "total_corners", corners_to_level, 21),
        ("yellows", "total_yellow_cards", yellows_to_level, 13),
    ):
        if task not in tasks:
            continue
        dist = tasks[task]
        actual_total = int(actual[target])
        actual_level = min(actual_total, cap)
        category = level_fn(actual_total)
        metrics[f"{target}_crps"] = crps_discrete(dist, actual_level)
        metrics[f"{target}_log_score"] = log_score_discrete(dist, category)
        expected = expected_value(dist)
        metrics[f"{target}_mae"] = mae(expected, actual_level)
        metrics[f"{target}_tail_mass"] = tail_mass(dist)
        coverage = predictive_interval_coverage(dist, actual_level)
        for level, hit in coverage.items():
            metrics[f"{target}_coverage_{level}"] = hit
        metrics[f"{target}_pit"] = pit_randomized(
            dist, actual_level, u=_pit_u(str(actual["prediction_id"]), seed)
        )
    if "score_bucket" in tasks:
        total_goals = actual["home_goals"] + actual["away_goals"]
        metrics["mae_goals"] = mae(metrics["expected_goals"], total_goals)
        metrics.pop("expected_goals")
    return metrics


def _per_match_values(
    rows: list[dict[str, Any]], metric: str
) -> dict[str, float]:
    """Contribution par match = moyenne des snapshots du match (§11.2)."""
    acc: dict[str, list[float]] = {}
    for row in rows:
        value = row["metrics"].get(metric)
        if value is None or value != value:  # None ou NaN
            continue
        acc.setdefault(row["match_id"], []).append(float(value))
    return {mid: sum(v) / len(v) for mid, v in acc.items() if v}


def run_evaluator(config_path: str | Path, run_id: str) -> int:
    """Évalue toutes les prédictions du run et publie les métriques."""
    cfg = load_config(config_path)
    paths = config_paths(cfg)
    logger = setup_logging(AGENT_NAME, paths["logs_dir"])
    log_event(logger, "start", "ok", "évaluation des prédictions", run_id=run_id)

    db = Database(paths["db"])
    db.init()
    seed = int(cfg["seed"])
    replicates = int(cfg["bootstrap"]["replicates"])
    alpha = float(cfg["bootstrap"]["alpha"])
    n_bins = int(cfg["bootstrap"].get("ece_bins", 15))

    snapshots = {
        s["snapshot_id"]: s for s in db.query("SELECT * FROM match_snapshots")
    }
    matches_by_id = {m["match_id"]: m for m in db.query("SELECT * FROM matches")}
    test_seasons = set(cfg["split"]["test_seasons"])

    # Prédictions Laya (base) + baselines (JSONL, mêmes snapshots §10.4).
    laya_rows = db.query(
        "SELECT * FROM laya_predictions WHERE run_id = ? AND status = 'valid'",
        (run_id,),
    )
    baseline_preds = load_baseline_predictions(paths["predictions_dir"], run_id)
    predictions: list[dict[str, Any]] = []
    for row in laya_rows:
        predictions.append(
            {
                "prediction_id": row["prediction_id"],
                "model": "laya",
                "snapshot_id": row["snapshot_id"],
                "tasks": json.loads(row["parsed_response"]),
                "latency_ms": row["latency_ms"],
            }
        )
    for model, rows in baseline_preds.items():
        for row in rows:
            predictions.append(
                {
                    "prediction_id": row["prediction_id"],
                    "model": model,
                    "snapshot_id": row["snapshot_id"],
                    "tasks": row["tasks"],
                    "latency_ms": None,
                }
            )

    # Jointure avec les labels finaux — uniquement ici, après prédiction.
    evaluated: list[dict[str, Any]] = []
    evaluation_rows: list[dict[str, Any]] = []
    n_invalid_laya = db.query(
        "SELECT COUNT(*) AS n FROM laya_predictions WHERE run_id = ? "
        "AND status = 'invalid'",
        (run_id,),
    )[0]["n"]
    n_total_laya = db.query(
        "SELECT COUNT(*) AS n FROM laya_predictions WHERE run_id = ?", (run_id,)
    )[0]["n"]

    for pred in predictions:
        snap = snapshots.get(pred["snapshot_id"])
        if snap is None or snap["validation_status"] != "validated":
            continue  # dénominateur publié : snapshot non validé exclu
        match = matches_by_id[snap["match_id"]]
        actual = {
            "prediction_id": pred["prediction_id"],
            "home_goals": match["home_goals"],
            "away_goals": match["away_goals"],
            "corners": match["total_corners"],
            "yellows": match["total_yellow_cards"],
        }
        try:
            metrics = evaluate_prediction(pred["tasks"], actual, seed)
        except (ValueError, KeyError):
            continue  # prédiction non exploitable pour cette cible
        evaluated.append(
            {
                "prediction_id": pred["prediction_id"],
                "model": pred["model"],
                "snapshot_id": pred["snapshot_id"],
                "match_id": snap["match_id"],
                "season": match["season"],
                "competition": match["competition_id"],
                "cutoff": snap["cutoff_seconds"],
                "tier": snap["information_tier"],
                "snapshot_type": snap["snapshot_type"],
                "metrics": metrics,
            }
        )
        evaluation_rows.append(
            {
                "evaluation_id": sha256_text(f"eval:{pred['prediction_id']}"),
                "prediction_id": pred["prediction_id"],
                "actual_result": (
                    "1" if match["home_goals"] > match["away_goals"]
                    else "2" if match["home_goals"] < match["away_goals"] else "X"
                ),
                "actual_home_goals": match["home_goals"],
                "actual_away_goals": match["away_goals"],
                "actual_total_corners": match["total_corners"],
                "actual_total_yellow_cards": match["total_yellow_cards"],
                "log_loss_1x2": metrics.get("log_loss_1x2"),
                "brier_1x2": metrics.get("brier_1x2"),
                "score_bucket_log_loss": metrics.get("score_bucket_log_loss"),
                "rps_1x2": metrics.get("rps_1x2"),
                "mae_goals": metrics.get("mae_goals"),
                "mae_corners": metrics.get("corners_mae"),
                "mae_yellow_cards": metrics.get("yellows_mae"),
                "created_at": now_utc(),
            }
        )
    # Lignes validées jamais modifiées par une relance (idempotence §0.4).
    bulk_upsert(db, "evaluation", evaluation_rows, on_conflict="ignore")

    # --- Dénominateurs (§19.2.5) --------------------------------------------
    models = sorted({row["model"] for row in evaluated} | {"laya"})
    denominators: dict[str, dict[str, Any]] = {}
    for model in models:
        rows = [r for r in evaluated if r["model"] == model]
        test_rows = [r for r in rows if r["season"] in test_seasons]
        denominators[model] = {
            "n_predictions": len(rows),
            "n_predictions_test_scope": len(test_rows),
            "n_matches": len({r["match_id"] for r in rows}),
            "n_snapshots_total": len(snapshots),
            "invalid_rate_laya": (
                n_invalid_laya / n_total_laya if n_total_laya else None
            ),
        }
    denominators["_laya_response_counts"] = {
        "total": n_total_laya,
        "valid": n_total_laya - n_invalid_laya,
        "invalid": n_invalid_laya,
    }

    # --- Agrégats bootstrap groupé par match (§11.2, §12.5) -----------------
    scopes = {
        "all": evaluated,
        "test": [r for r in evaluated if r["season"] in test_seasons],
    }
    aggregates: dict[str, dict[str, dict[str, Any]]] = {}
    for scope, rows in scopes.items():
        aggregates[scope] = {}
        for model in models:
            model_rows = [r for r in rows if r["model"] == model]
            entry: dict[str, Any] = {"n_predictions": len(model_rows)}
            for metric in METRIC_KEYS:
                per_match = _per_match_values(model_rows, metric)
                if len(per_match) < 2:
                    if len(per_match) == 1:
                        entry[metric] = {
                            "mean": next(iter(per_match.values())),
                            "ci_low": None,
                            "ci_high": None,
                            "n_matches": 1,
                            "replicates": replicates,
                            "seed": seed,
                        }
                    continue
                entry[metric] = group_bootstrap(
                    per_match, replicates=replicates, seed=seed, alpha=alpha
                )
            aggregates[scope][model] = entry

    # Ventilations descriptives (moyennes + effectifs, sans IC).
    by_cutoff: dict[str, dict[str, dict[str, float]]] = {}
    for cutoff in sorted({r["cutoff"] for r in evaluated}):
        by_cutoff[str(cutoff)] = _descriptive(
            [r for r in evaluated
             if r["cutoff"] == cutoff and r["season"] in test_seasons],
            ["log_loss_1x2", "score_bucket_log_loss", "corners_crps",
             "yellows_crps"],
        )
    # Correctif (sous-agent B2, worklog) : `by_tier` groupait par modèle et
    # `_descriptive(key=...)` mélangeait les modèles dans une même strate ;
    # les ventilations sont désormais par (modèle, strate) sur le scope test.
    by_tier = _descriptive(
        [r for r in evaluated if r["season"] in test_seasons],
        ["log_loss_1x2", "score_bucket_log_loss", "corners_crps", "yellows_crps"],
        key="tier",
    )
    by_competition = _descriptive(
        [r for r in evaluated if r["season"] in test_seasons],
        ["log_loss_1x2", "score_bucket_log_loss", "corners_crps", "yellows_crps"],
        key="competition",
    )

    # --- Calibration (§12.4) ------------------------------------------------
    calibration: dict[str, Any] = {}
    for model in models:
        rows = [r for r in scopes["test"] if r["model"] == model]
        observations = [
            (max(r["metrics"]["p_realized_1x2"], 1.0 / 3.0) if False else
             _confidence_1x2(r), r["metrics"]["accuracy_1x2"])
            for r in rows
            if "p_realized_1x2" in r["metrics"]
        ]
        calibration[model] = {
            "ece_1x2": ece(observations, n_bins=n_bins, binning="equal-width"),
            "n_bins": n_bins,
            "binning": "equal-width",
            "n_observations": len(observations),
        }

    # --- Comparaisons par modèle avec Holm-Bonferroni (§12.5) ----------------
    comparisons: dict[str, Any] = {}
    for family, (metric, _target) in COMPARISON_FAMILIES.items():
        per_model: dict[str, dict[str, float]] = {}
        for model in models:
            rows = [r for r in scopes["test"] if r["model"] == model]
            per_match = _per_match_values(rows, metric)
            if len(per_match) >= 2:
                per_model[model] = per_match
        if REFERENCE_MODEL in per_model and len(per_model) > 1:
            comparisons[family] = {
                "metric": metric,
                "reference": REFERENCE_MODEL,
                "convention": "différence = modèle - laya (>0 : moins bon que laya)",
                "models": compare_models(
                    per_model, REFERENCE_MODEL,
                    replicates=replicates, seed=seed, alpha=alpha,
                ),
            }

    # --- Réaction aux événements (H3, §13.3, descriptif) --------------------
    event_reactions = _goal_reaction_analysis(db, run_id, snapshots)

    # --- Hypothèses pré-enregistrées (§1.3) ----------------------------------
    hypotheses = _hypotheses(aggregates, comparisons, calibration, event_reactions)

    # --- Contrôles bloquants §11.4 -------------------------------------------
    laya_invalid_rate = (n_invalid_laya / n_total_laya) if n_total_laya else 0.0
    max_invalid = float(cfg["thresholds"]["max_invalid_response_rate"])
    blocking = {
        "invalid_response_rate": {
            "value": laya_invalid_rate,
            "threshold": max_invalid,
            "blocked": laya_invalid_rate > max_invalid,
        },
        "snapshot_leakage_rate": _leakage_from_artifact(paths, run_id, cfg),
        "stratum_missing_rate": _missing_from_artifact(paths, run_id, cfg),
    }
    any_blocked = any(v["blocked"] for v in blocking.values())
    status = "blocked" if any_blocked else "validated"

    payload = {
        "denominators": denominators,
        "aggregate_metrics": METRIC_KEYS,
        "aggregates": aggregates,
        "by_cutoff": by_cutoff,
        "by_tier": by_tier,
        "by_competition": by_competition,
        "calibration": calibration,
        "comparisons": comparisons,
        "event_reactions": event_reactions,
        "hypotheses": hypotheses,
        "blocking_checks": blocking,
        "bootstrap": {
            "method": "bootstrap stratifié et groupé par match (§11.2, §12.5)",
            "replicates": replicates,
            "alpha": alpha,
            "seed": seed,
        },
        "notes": [
            "Le 1X2 est dérivé de la distribution de score regroupé (§8.1).",
            "Espérances censurées aux seuils 21+ / 13+ (§8.3, §8.4).",
            "Un test non significatif ne prouve pas l'égalité des modèles (§12.5).",
        ],
    }
    out_dir = paths["evaluation_dir"] / run_id
    write_artifact(
        out_dir / "evaluation_report.json",
        payload,
        experiment_id=cfg["experiment_id"],
        run_id=run_id,
        producer=PRODUCER,
        input_hashes=[
            "laya_run:" + _digest(paths["artifacts_dir"], run_id, "laya_run.json"),
            "baselines_run:" + _digest(paths["artifacts_dir"], run_id,
                                       "baselines_run.json"),
        ],
        status=status,
        record_count=len(evaluation_rows),
        warnings=[] if not any_blocked else ["seuil §11.4 dépassé"],
    )
    log_event(logger, "artifact", status,
              f"evaluation_report.json prédictions={len(evaluation_rows)}",
              run_id=run_id)
    if any_blocked:
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "evaluate",
                  f"contrôles bloquants §11.4 : {blocking}")
        db.close()
        return 1
    db.close()
    log_event(logger, "end", "ok", "évaluation terminée", run_id=run_id)
    return 0


def _confidence_1x2(row: dict[str, Any]) -> float:
    """Confiance 1X2 = probabilité prédite de la classe réalisée (ECE §12.4)."""
    return float(row["metrics"]["p_realized_1x2"])


def _descriptive(
    rows: list[dict[str, Any]], metrics: list[str], key: str | None = None
) -> dict[str, Any]:
    """Moyennes descriptives par modèle ; par (modèle, strate) si `key` fournie.

    Sans `key` : {modèle: {métrique_mean: ...}}. Avec `key` :
    {strate: {modèle: {métrique_mean: ...}}} — les modèles ne sont jamais
    mélangés dans une même strate (correctif sous-agent B2, worklog).
    """
    strata: dict[str, dict[str, list[dict[str, Any]]] | list[dict[str, Any]]] = {}
    for row in rows:
        if key:
            strata.setdefault(str(row[key]), {}).setdefault(row["model"], []).append(row)
        else:
            strata.setdefault(row["model"], []).append(row)
    out: dict[str, dict[str, dict[str, float]]] = {}
    for stratum, grouped in strata.items():
        if key:
            for model, group_rows in grouped.items():
                out.setdefault(stratum, {})[model] = _mean_entry(group_rows, metrics)
        else:
            out[stratum] = _mean_entry(grouped, metrics)
    return out


def _mean_entry(
    group_rows: list[dict[str, Any]], metrics: list[str]
) -> dict[str, float]:
    """Effectif + moyennes des métriques d'un groupe de prédictions."""
    entry: dict[str, float] = {"n_predictions": float(len(group_rows))}
    for metric in metrics:
        values = [r["metrics"][metric] for r in group_rows if metric in r["metrics"]]
        entry[f"{metric}_mean"] = (
            round(sum(values) / len(values), 6) if values else None
        )
    return entry


def _goal_reaction_analysis(
    db: Database, run_id: str, snapshots: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Réaction après but (H3, §13.3) : variation de la probabilité du côté
    qui marque entre le snapshot précédent et le snapshot de but (laya, test)."""
    rows = db.query(
        "SELECT p.*, s.snapshot_type, s.cutoff_seconds, s.information_tier, "
        "s.state_json, s.match_id FROM laya_predictions p "
        "JOIN match_snapshots s ON p.snapshot_id = s.snapshot_id "
        "WHERE p.run_id = ? AND p.status = 'valid' "
        "ORDER BY s.match_id, s.cutoff_seconds, s.information_tier",
        (run_id,),
    )
    deltas: list[float] = []
    for row in rows:
        if row["snapshot_type"] != "goal" or row["information_tier"] != "B":
            continue
        state = json.loads(row["state_json"])
        previous = _previous_snapshot(db, row["match_id"], row["cutoff_seconds"],
                                      row["information_tier"], run_id)
        if previous is None:
            continue
        prev_state = json.loads(previous["state_json"])
        cur_score = (state.get("live") or {}).get("score") or {}
        prev_score = (prev_state.get("live") or {}).get("score") or {}
        home_scored = int(cur_score.get("home") or 0) > int(prev_score.get("home") or 0)
        away_scored = int(cur_score.get("away") or 0) > int(prev_score.get("away") or 0)
        if not (home_scored ^ away_scored):
            continue  # but simultané ou information inchangée
        p_key = "probability_1" if home_scored else "probability_2"
        try:
            delta = float(row[p_key]) - float(previous[p_key])
        except (TypeError, ValueError):
            continue
        deltas.append(delta)
    return {
        "mean_delta_p_scoring_side": (
            round(sum(deltas) / len(deltas), 6) if deltas else None
        ),
        "n_pairs": len(deltas),
        "scope": "laya, tier B, snapshots de but vs snapshot précédent",
        "interpretation": "descriptif ; sans interprétation causale (§13.3)",
    }


def _previous_snapshot(
    db: Database,
    match_id: str,
    cutoff_seconds: int,
    tier: str,
    run_id: str,
) -> dict[str, Any] | None:
    """Dernier snapshot laya du même match/tier strictement avant le cutoff."""
    rows = db.query(
        "SELECT p.*, s.cutoff_seconds, s.state_json, s.match_id AS snap_match_id "
        "FROM laya_predictions p "
        "JOIN match_snapshots s ON p.snapshot_id = s.snapshot_id "
        "WHERE p.run_id = ? AND p.status = 'valid' AND s.match_id = ? "
        "AND s.information_tier = ? AND s.cutoff_seconds < ? "
        "ORDER BY s.cutoff_seconds DESC LIMIT 1",
        (run_id, match_id, tier, cutoff_seconds),
    )
    return rows[0] if rows else None


def _hypotheses(
    aggregates: dict[str, Any],
    comparisons: dict[str, Any],
    calibration: dict[str, Any],
    event_reactions: dict[str, Any],
) -> dict[str, Any]:
    """Résultats des hypothèses pré-enregistrées H1–H5 (§1.3).

    Confirmatoire = test scope (saison test) ; H4 non exécutée faute de
    variantes de formulation dans ce run (analyses §13.1 hors périmètre).
    """
    test_laya = aggregates.get("test", {}).get("laya", {})
    ll_by_cutoff = {}
    h1 = {"observed": "non calculable", "n_cutoffs": 0}
    cutoff_metrics = {}
    # H1 : la log loss 1X2 diminue du pré-match à 85 minutes.
    by_cutoff = aggregates.get("_by_cutoff_laya", {})
    if "log_loss_1x2" in test_laya and test_laya["log_loss_1x2"]:
        h1 = {
            "test_scope_log_loss_1x2_mean": test_laya["log_loss_1x2"]["mean"],
            "statement": "comparer par cutoff (tableaux by_cutoff)",
        }
    # H2 : calibration de laya vs fréquence historique.
    h2 = {
        "laya": calibration.get("laya"),
        "historical_frequency": calibration.get("historical_frequency"),
    }
    # H3 : réaction après but.
    h3 = event_reactions
    # H5 : corners/cartons vs baselines.
    h5 = {
        family: {
            "reference": data["reference"],
            "models": {
                model: {
                    "mean_difference": round(stats["mean_difference"], 6),
                    "ci_low": round(stats["ci_low"], 6),
                    "ci_high": round(stats["ci_high"], 6),
                    "significant_holm": stats["significant_holm"],
                }
                for model, stats in data["models"].items()
                if model in ("historical_frequency", "poisson")
            },
        }
        for family, data in comparisons.items()
        if family in ("corners_crps", "yellow_cards_crps")
    }
    return {
        "H1_progression_temporelle": {**h1, **cutoff_metrics, **by_cutoff,
                                      "by_cutoff_ll": ll_by_cutoff,
                                      "confirmatory": True},
        "H2_calibration": h2,
        "H3_reaction_apres_but": {**h3, "confirmatory": True},
        "H4_robustesse": {"status": "non exécutée (aucune variante dans ce run)",
                          "confirmatory": False},
        "H5_comptages": {"families": h5, "confirmatory": True},
    }


def _leakage_from_artifact(paths: dict[str, Path], run_id: str, cfg: dict[str, Any]
                           ) -> dict[str, Any]:
    """Relit le taux de fuite publié par l'agent snapshot (§11.4)."""
    path = paths["artifacts_dir"] / run_id / "snapshot_validation.json"
    threshold = float(cfg["thresholds"]["max_snapshot_leakage_rate"])
    if not path.is_file():
        return {"value": None, "threshold": threshold, "blocked": True}
    payload = json.loads(path.read_text(encoding="utf-8"))["payload"]
    rate = float(payload["summary"]["leakage_rate"])
    return {"value": rate, "threshold": threshold, "blocked": rate > threshold}


def _missing_from_artifact(paths: dict[str, Path], run_id: str, cfg: dict[str, Any]
                            ) -> dict[str, Any]:
    """Relit le taux de matchs manquants par strate (§11.4)."""
    path = paths["artifacts_dir"] / run_id / "cleaning_report.json"
    threshold = float(cfg["thresholds"]["max_stratum_missing_rate"])
    if not path.is_file():
        return {"value": None, "threshold": threshold, "blocked": True}
    payload = json.loads(path.read_text(encoding="utf-8"))["payload"]
    value = float(payload["max_stratum_missing_rate"])
    return {"value": value, "threshold": threshold, "blocked": value > threshold}


def _digest(artifacts_dir: Path, run_id: str, name: str) -> str:
    """Hash SHA-256 d'un artefact d'entrée (chaîne d'audit §15)."""
    path = artifacts_dir / run_id / name
    if not path.is_file():
        return "absent"
    return sha256_text(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    """Parseur CLI de l'agent évaluateur."""
    parser = argparse.ArgumentParser(description="Agent Évaluateur (protocole §14.8)")
    parser.add_argument("--run-id", default="run_001")
    parser.add_argument("--config", default="configs/experiment.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI (§16)."""
    args = build_parser().parse_args(argv)
    return run_evaluator(args.config, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
