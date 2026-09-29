"""Agent Baselines (protocole §14.7, §10, §11.1, §21 « Baselines »).

Baselines implémentées (§10.1, §10.2), toutes avec exactement la même
information au même cutoff que Laya (§10.4) :
- `uniform` : distribution uniforme (contrôle de référence) ;
- `historical_frequency` : fréquences observées dans la fenêtre passée,
  recalculées de façon point-in-time pour chaque match ;
- `current_score` : le score/comptage courant devient la prédiction finale,
  converti en distribution par la règle pré-enregistrée (masse 1 sur la
  catégorie courante, dégénérée) ;
- `persistence` : comptage courant + moyenne historique du reste de match ;
- `poisson` : Poisson indépendant avec forces d'attaque/défense par équipe
  estimées sur la fenêtre passée (rétrécies vers la moyenne de ligue) ;
- `logistic_1x2` : régression logistique multinomiale (sklearn), entraînée
  sur les pré-matchs des SAISONS D'ENTRAÎNEMENT UNIQUEMENT (§11.1) et
  évaluée uniquement sur les snapshots de la saison test.

Blocage (§14.7) : aucun entraînement sur le test final — l'artefact publie
la fenêtre d'entraînement et la liste des matchs utilisés (assertions de
dates dans tests/test_baselines.py).

Usage (§16) :
    python -m agents.baselines --run-id RUN_ID [--config configs/experiment.yaml]
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from agents.common import (
    config_paths,
    iter_jsonl,
    load_config,
    log_error,
    log_event,
    resolve_split,
    setup_logging,
    sha256_text,
    write_artifact,
)
from src.core.canonical import canonical_json
from src.core.ids import prediction_id as compute_prediction_id
from src.core.tasks import (
    CORNER_LEVELS,
    QUESTIONS_V1,
    SCORE_BUCKETS,
    YELLOW_LEVELS,
)
from src.storage.database import Database

AGENT_NAME = "baselines"
PRODUCER = "baselines_agent"

NOMINAL_MATCH_SECONDS = 5400
"""Durée de temps de jeu nominale pour la fraction restante (annexe B)."""

# Défauts pré-enregistrés (utilisés si aucune historique n'est disponible).
DEFAULT_LAMBDA_HOME = 1.35
DEFAULT_LAMBDA_AWAY = 1.15
DEFAULT_CORNERS_MEAN = 10.6
DEFAULT_YELLOWS_MEAN = 3.5
SHRINKAGE_PRIOR_MATCHES = 5
"""Poids du rétrécissement vers la moyenne de ligue (poisson)."""

MODEL_VERSIONS = {
    "uniform": "uniform-v1",
    "historical_frequency": "hist-freq-v1",
    "current_score": "current-score-v1",
    "persistence": "persistence-v1",
    "poisson": "poisson-v1",
    "logistic_1x2": "logistic-1x2-v1",
}


def _poisson_pmf(lam: float, k_max: int) -> list[float]:
    """PMF de Poisson sur 0..k_max (lam modéré, Knuth)."""
    if lam <= 0.0:
        return [1.0] + [0.0] * k_max
    log_p = -lam
    probs: list[float] = []
    for k in range(k_max + 1):
        if k == 0:
            probs.append(math.exp(log_p))
        else:
            log_p += math.log(lam) - math.log(k)
            probs.append(math.exp(min(log_p, 0.0)))
    return probs


def _exact_sum(values: dict[str, float]) -> dict[str, float]:
    """Arrondit et reporte le résidu sur le mode (somme exactement 1)."""
    rounded = {k: round(v, 12) for k, v in values.items()}
    mode = max(rounded, key=lambda k: rounded[k])
    rounded[mode] = round(rounded[mode] + (1.0 - sum(rounded.values())), 12)
    return rounded


def _count_dist(current: int, lam: float, levels: list[str]) -> dict[str, float]:
    """Distribution de comptage : courant + Poisson(reste), queue censurée."""
    tail = levels[-1]
    threshold = int(tail.rstrip("+"))
    k_max = max(threshold - current, 0) + 4
    pmf = _poisson_pmf(lam, k_max)
    dist: dict[str, float] = {}
    for cat in levels:
        if cat == tail:
            continue
        offset = int(cat) - current
        dist[cat] = pmf[offset] if 0 <= offset <= k_max else 0.0
    dist[tail] = max(0.0, 1.0 - sum(dist.values()))
    return _exact_sum(dist)


def _bucket_dist(
    cur_h: int, cur_a: int, lam_h: float, lam_a: float
) -> dict[str, float]:
    """Distribution de score regroupé : Poisson indépendants du reste (§8.2)."""
    pmf_h = _poisson_pmf(lam_h, 9)
    pmf_a = _poisson_pmf(lam_a, 9)
    buckets: dict[str, float] = {}
    for i, ph in enumerate(pmf_h):
        for j, pa in enumerate(pmf_a):
            h, a = cur_h + i, cur_a + j
            cat = f"{h}-{a}" if h <= 3 and a <= 3 else "other"
            buckets[cat] = buckets.get(cat, 0.0) + ph * pa
    return _exact_sum({cat: buckets.get(cat, 0.0) for cat in SCORE_BUCKETS})


def _league_aggregates(
    past: list[dict[str, Any]],
) -> dict[str, Any]:
    """Agrégats de ligue sur la fenêtre passée (fréquences, moyennes,
    forces d'attaque/défense par équipe avec rétrécissement)."""
    n = len(past)
    agg: dict[str, Any] = {
        "n_matches": n,
        "bucket_freq": dict.fromkeys(SCORE_BUCKETS, 0),
        "corner_freq": dict.fromkeys(CORNER_LEVELS, 0),
        "yellow_freq": dict.fromkeys(YELLOW_LEVELS, 0),
        "mean_home_goals": DEFAULT_LAMBDA_HOME,
        "mean_away_goals": DEFAULT_LAMBDA_AWAY,
        "corners_mean": DEFAULT_CORNERS_MEAN,
        "yellows_mean": DEFAULT_YELLOWS_MEAN,
        "attack": {},
        "defense": {},
    }
    if n == 0:
        return agg
    goals_h = goals_a = corners = yellows = 0.0
    scored: dict[str, list[float]] = {}
    conceded: dict[str, list[float]] = {}
    for match in past:
        h, a = match["home_goals"], match["away_goals"]
        bucket = f"{h}-{a}" if h <= 3 and a <= 3 else "other"
        agg["bucket_freq"][bucket] += 1
        c_level = "21+" if (match["total_corners"] or 0) >= 21 else str(match["total_corners"])
        y_level = (
            "13+" if (match["total_yellow_cards"] or 0) >= 13
            else str(match["total_yellow_cards"])
        )
        agg["corner_freq"][c_level] = agg["corner_freq"].get(c_level, 0) + 1
        agg["yellow_freq"][y_level] = agg["yellow_freq"].get(y_level, 0) + 1
        goals_h += h
        goals_a += a
        corners += match["total_corners"] or 0
        yellows += match["total_yellow_cards"] or 0
        scored.setdefault(match["home_team_id"], []).append(h)
        conceded.setdefault(match["home_team_id"], []).append(a)
        scored.setdefault(match["away_team_id"], []).append(a)
        conceded.setdefault(match["away_team_id"], []).append(h)
    agg["mean_home_goals"] = goals_h / n
    agg["mean_away_goals"] = goals_a / n
    agg["corners_mean"] = corners / n
    agg["yellows_mean"] = yellows / n
    mean_total = (goals_h + goals_a) / (2 * n) or 1.0
    for team in set(scored) | set(conceded):
        att = sum(scored.get(team, [])) / max(len(scored.get(team, [])), 1)
        dfn = sum(conceded.get(team, [])) / max(len(conceded.get(team, [])), 1)
        n_team = len(scored.get(team, []))
        # Rétrécissement vers la moyenne de ligue (hyperparamètre figé).
        agg["attack"][team] = (n_team * att + SHRINKAGE_PRIOR_MATCHES * mean_total) / (
            n_team + SHRINKAGE_PRIOR_MATCHES
        )
        agg["defense"][team] = (n_team * dfn + SHRINKAGE_PRIOR_MATCHES * mean_total) / (
            n_team + SHRINKAGE_PRIOR_MATCHES
        )
    return agg


def _past_window(
    db: Database, match: dict[str, Any], cache: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Fenêtre point-in-time du match : inclus, même compétition,
    disponibles strictement avant le kickoff (§5.2, §10.4)."""
    key = match["match_id"]
    if key not in cache:
        rows = db.query(
            "SELECT * FROM matches WHERE status = 'included' "
            "AND competition_id = ? AND available_timestamp < ? "
            "AND match_id <> ? ORDER BY kickoff_timestamp",
            (match["competition_id"], match["kickoff_timestamp"], match["match_id"]),
        )
        cache[key] = rows
    return cache[key]


def _live_numbers(state: dict[str, Any]) -> dict[str, Any]:
    """Extrait les comptages courants et le cutoff de l'état (§7.1)."""
    meta = state.get("metadata") or {}
    live = state.get("live") or {}

    def _total(key: str) -> int:
        pair = live.get(key) or {}
        return int(pair.get("home") or 0) + int(pair.get("away") or 0)

    score = live.get("score") or {}
    reds = live.get("red_cards") or {}
    return {
        "cutoff_seconds": int(meta.get("cutoff_seconds") or 0),
        "score_h": int(score.get("home") or 0),
        "score_a": int(score.get("away") or 0),
        "corners": _total("corners"),
        "yellows": _total("yellow_cards"),
        "reds_home": int(reds.get("home") or 0),
        "reds_away": int(reds.get("away") or 0),
        "tier": meta.get("information_tier"),
    }


def _uniform() -> dict[str, dict[str, float]]:
    """Baseline uniforme (§10.1)."""
    return {
        task: _exact_sum({cat: 1.0 / len(question["criteria"])
                          for cat in question["criteria"]})
        for task, question in QUESTIONS_V1.items()
    }


def _historical_frequency(
    agg: dict[str, Any],
) -> dict[str, dict[str, float]]:
    """Baseline fréquence historique (§10.1) — point-in-time par match."""
    n = agg["n_matches"]
    if n == 0:
        return _uniform()
    out: dict[str, dict[str, float]] = {}
    for task, freqs, criteria in (
        ("score_bucket", agg["bucket_freq"], SCORE_BUCKETS),
        ("total_corners", agg["corner_freq"], CORNER_LEVELS),
        ("total_yellow_cards", agg["yellow_freq"], YELLOW_LEVELS),
    ):
        out[task] = _exact_sum({cat: freqs.get(cat, 0) / n for cat in criteria})
    return out


def _current_score(nums: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Baseline score courant : règle pré-enregistrée de conversion —
    toute la masse sur la catégorie courante (dégénérée, §10.1)."""
    h, a = nums["score_h"], nums["score_a"]
    bucket = f"{h}-{a}" if h <= 3 and a <= 3 else "other"
    corners = "21+" if nums["corners"] >= 21 else str(nums["corners"])
    yellows = "13+" if nums["yellows"] >= 13 else str(nums["yellows"])
    return {
        "score_bucket": _exact_sum({cat: 1.0 if cat == bucket else 0.0
                                    for cat in SCORE_BUCKETS}),
        "total_corners": _exact_sum({cat: 1.0 if cat == corners else 0.0
                                     for cat in CORNER_LEVELS}),
        "total_yellow_cards": _exact_sum({cat: 1.0 if cat == yellows else 0.0
                                          for cat in YELLOW_LEVELS}),
    }


def _persistence(nums: dict[str, Any], agg: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Baseline persistance : comptage courant + moyenne historique du reste
    (définition précise du « reste » : moyenne de ligue × fraction restante)."""
    remaining = max(0.0, (NOMINAL_MATCH_SECONDS - nums["cutoff_seconds"])
                    / NOMINAL_MATCH_SECONDS)
    lam_home = agg["mean_home_goals"] * remaining
    lam_away = agg["mean_away_goals"] * remaining
    return {
        "score_bucket": _bucket_dist(nums["score_h"], nums["score_a"], lam_home, lam_away),
        "total_corners": _count_dist(
            nums["corners"], agg["corners_mean"] * remaining, CORNER_LEVELS),
        "total_yellow_cards": _count_dist(
            nums["yellows"], agg["yellows_mean"] * remaining, YELLOW_LEVELS),
    }


def _poisson(
    nums: dict[str, Any],
    match: dict[str, Any],
    agg: dict[str, Any],
) -> dict[str, dict[str, float]]:
    """Baseline Poisson indépendant : attaque × défense rétrécies (§10.2)."""
    remaining = max(0.0, (NOMINAL_MATCH_SECONDS - nums["cutoff_seconds"])
                    / NOMINAL_MATCH_SECONDS)
    mean = (agg["mean_home_goals"] + agg["mean_away_goals"]) / 2.0 or 1.0
    att_h = agg["attack"].get(match["home_team_id"], mean)
    def_a = agg["defense"].get(match["away_team_id"], mean)
    att_a = agg["attack"].get(match["away_team_id"], mean)
    def_h = agg["defense"].get(match["home_team_id"], mean)
    lam_h = min(3.5, max(0.2, att_h * def_a / mean)) * remaining
    lam_a = min(3.5, max(0.2, att_a * def_h / mean)) * remaining
    return {
        "score_bucket": _bucket_dist(nums["score_h"], nums["score_a"], lam_h, lam_a),
        "total_corners": _count_dist(
            nums["corners"], agg["corners_mean"] * remaining, CORNER_LEVELS),
        "total_yellow_cards": _count_dist(
            nums["yellows"], agg["yellows_mean"] * remaining, YELLOW_LEVELS),
    }


def _extract_features(state: dict[str, Any]) -> list[float]:
    """Features de la régression logistique (pré-enregistrées) : différence
    de classement, de forme, de moyennes de buts, cutoff, score, cartons
    rouges et corners courants."""
    meta = state.get("metadata") or {}
    pre = state.get("pre_match") or {}
    home = pre.get("home") or {}
    away = pre.get("away") or {}
    live = state.get("live") or {}

    def _form_points(seq: str | None) -> float:
        """Points de forme : accepte « WDLWW » et « W,D,L » (h2h)."""
        if not seq:
            return 0.0
        return sum({"W": 3.0, "D": 1.0, "L": 0.0}.get(ch, 0.0)
                   for ch in seq.replace(",", ""))

    ranking_diff = (home.get("ranking_before") or 0.0) - (away.get("ranking_before") or 0.0)
    form_diff = _form_points(home.get("form_last_5")) - _form_points(away.get("form_last_5"))
    scored_diff = (home.get("goals_scored_avg") or 0.0) - (away.get("goals_scored_avg") or 0.0)
    conceded_diff = (
        (away.get("goals_conceded_avg") or 0.0) - (home.get("goals_conceded_avg") or 0.0)
    )
    score = live.get("score") or {}
    reds = live.get("red_cards") or {}

    def _total(key: str) -> float:
        pair = live.get(key) or {}
        return float((pair.get("home") or 0) - (pair.get("away") or 0))

    return [
        float(ranking_diff),
        float(form_diff),
        float(scored_diff),
        float(conceded_diff),
        int(meta.get("cutoff_seconds") or 0) / NOMINAL_MATCH_SECONDS,
        float((score.get("home") or 0) - (score.get("away") or 0)),
        float((reds.get("home") or 0) - (reds.get("away") or 0)),
        _total("corners"),
    ]


def run_baselines(config_path: str | Path, run_id: str) -> int:
    """Calcule les prédictions de toutes les baselines."""
    cfg = load_config(config_path)
    paths = config_paths(cfg)
    logger = setup_logging(AGENT_NAME, paths["logs_dir"])
    log_event(logger, "start", "ok", "calcul des baselines", run_id=run_id)

    db = Database(paths["db"])
    db.init()
    # Mémoire (corpus réel : ~125 000 snapshots avec state_json volumineux) :
    # pagination + écriture au fil de l'eau — sémantique identique (l'ordre
    # snapshot_id est préservé, les fichiers JSONL sont réécrits intégralement
    # à chaque exécution comme auparavant).
    matches_by_id = {m["match_id"]: m for m in db.query("SELECT * FROM matches")}
    # Découpage §11.1 : par saison OU chronologique 50/50 par compétition
    # (amendement A2 — cf. agents/common.py::resolve_split).
    train_match_ids, test_match_ids = resolve_split(cfg, list(matches_by_id.values()))

    # --- Entraînement de la régression logistique (§11.1) -------------------
    # Pré-matchs d'entraînement : requête ciblée (cutoff 0, tier B) — les
    # snapshots autres que pré-match ne sont pas chargés inutilement.
    train_rows = [
        s for s in db.query(
            "SELECT * FROM match_snapshots WHERE validation_status = 'validated' "
            "AND cutoff_seconds = 0 AND information_tier = 'B' ORDER BY snapshot_id"
        )
        if s["match_id"] in train_match_ids
    ]
    train_match_ids = train_match_ids & {s["match_id"] for s in train_rows}
    if len(train_rows) < 10:
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "train",
                  f"trop peu de pré-matchs d'entraînement : {len(train_rows)}")
        db.close()
        return 1
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    logistic = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(C=1.0, max_iter=1000, random_state=int(cfg["seed"])),
            ),
        ]
    )
    x_train = [_extract_features(json.loads(s["state_json"])) for s in train_rows]
    y_train = []
    for snap in train_rows:
        match = matches_by_id[snap["match_id"]]
        if match["home_goals"] > match["away_goals"]:
            y_train.append("1")
        elif match["home_goals"] < match["away_goals"]:
            y_train.append("2")
        else:
            y_train.append("X")
    logistic.fit(x_train, y_train)
    classes = list(logistic.named_steps["clf"].classes_)

    # Vérification bloquante §14.7 : aucun match du test final à l'entraînement.
    leak = sorted(train_match_ids & test_match_ids)
    if leak:
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "train",
                  f"matchs du test final dans l'entraînement : {leak}")
        db.close()
        return 1
    train_kickoffs = sorted(
        matches_by_id[mid]["kickoff_timestamp"] for mid in train_match_ids
    )

    # --- Prédictions par modèle --------------------------------------------
    out_dir = paths["predictions_dir"] / run_id / "baselines"
    out_dir.mkdir(parents=True, exist_ok=True)
    windows: dict[str, list[dict[str, Any]]] = {}
    aggs: dict[str, dict[str, Any]] = {}
    counts: dict[str, dict[str, int]] = {}
    handles = {m: (out_dir / f"{m}.jsonl").open("w", encoding="utf-8")
               for m in MODEL_VERSIONS}
    page_size = 10_000
    page_start = 0
    n_done = 0
    total_snaps = db.query(
        "SELECT COUNT(*) AS n FROM match_snapshots "
        "WHERE validation_status = 'validated'"
    )[0]["n"]

    while True:
        snapshots = db.query(
            "SELECT * FROM match_snapshots WHERE validation_status = 'validated' "
            "ORDER BY snapshot_id LIMIT ? OFFSET ?",
            (page_size, page_start),
        )
        if not snapshots:
            break
        page_start += len(snapshots)
        # Pagination (corpus réel) : lignes écrites au fil de l'eau dans les
        # mêmes fichiers JSONL (réécriture intégrale à chaque exécution).
        for snap in snapshots:
            match = matches_by_id[snap["match_id"]]
            state = json.loads(snap["state_json"])
            nums = _live_numbers(state)
            window_key = match["match_id"]
            if window_key not in aggs:
                aggs[window_key] = _league_aggregates(_past_window(db, match, windows))
            agg = aggs[window_key]
            models_for_snapshot: dict[str, dict[str, dict[str, float]] | None] = {
                "uniform": _uniform(),
                "historical_frequency": _historical_frequency(agg),
                "current_score": _current_score(nums),
                "persistence": _persistence(nums, agg),
                "poisson": _poisson(nums, match, agg),
            }
            # La logistique ne prédit que les snapshots du test final (§11.1) :
            # l'entraînement n'utilise que les périodes anciennes.
            logistic_tasks: dict[str, dict[str, float]] | None = None
            if match["match_id"] in test_match_ids:
                proba = logistic.predict_proba([_extract_features(state)])[0]
                one_x_two = _exact_sum(
                    {cls: float(p) for cls, p in zip(classes, proba, strict=False)}
                )
                logistic_tasks = {"one_x_two": one_x_two}
            models_for_snapshot["logistic_1x2"] = logistic_tasks

            for model, tasks in models_for_snapshot.items():
                if tasks is None:
                    continue
                row = {
                    "prediction_id": compute_prediction_id(
                        run_id, snap["snapshot_id"], MODEL_VERSIONS[model]
                    ),
                    "snapshot_id": snap["snapshot_id"],
                    "match_id": match["match_id"],
                    "model": model,
                    "model_version": MODEL_VERSIONS[model],
                    "status": "valid",
                    "tasks": tasks,
                }
                handles[model].write(canonical_json(row) + "\n")
        n_done += len(snapshots)
        log_event(logger, "progress", "ok",
                  f"{n_done}/{total_snaps} snapshots", run_id=run_id)
        if len(snapshots) < page_size:
            break

    for model, fh in handles.items():
        fh.close()
        n = sum(1 for _ in (out_dir / f"{model}.jsonl").open("rb"))
        counts[model] = {
            "n_predictions": n,
            "n_valid": n,
            "n_invalid": 0,
        }
        log_event(logger, "model", "ok",
                  f"{model} predictions={n}", run_id=run_id)

    payload = {
        "models": counts,
        "model_versions": MODEL_VERSIONS,
        "training": {
            "logistic_1x2": {
                "split_mode": cfg["split"].get("mode", "by_season"),
                "train_seasons": sorted(
                    {matches_by_id[mid]["season"] for mid in train_match_ids}
                ),
                "train_match_ids": sorted(train_match_ids),
                "n_train_matches": len(train_match_ids),
                "min_kickoff": train_kickoffs[0] if train_kickoffs else None,
                "max_kickoff": train_kickoffs[-1] if train_kickoffs else None,
                "hyperparameters": {"C": 1.0, "max_iter": 1000,
                                    "standardize": True},
                "training_rows": len(train_rows),
                "snapshot_filter": "cutoff_seconds == 0 and tier == 'B'",
            },
            "point_in_time_models": [
                "uniform",
                "historical_frequency",
                "current_score",
                "persistence",
                "poisson",
            ],
            "note": (
                "Les modèles point-in-time recalculent leur fenêtre pour "
                "chaque match (available_timestamp < kickoff, §10.4) ; la "
                "régression logistique est ajustée uniquement sur les "
                "saisons d'entraînement et prédit uniquement la saison test."
            ),
        },
        "registered_conversion_rules": {
            "current_score": "masse 1 sur la catégorie courante (dégénérée)",
            "persistence": "Poisson centré sur courant + moyenne ligue × reste",
        },
        "defaults_if_no_history": {
            "lambda_home": DEFAULT_LAMBDA_HOME,
            "lambda_away": DEFAULT_LAMBDA_AWAY,
            "corners_mean": DEFAULT_CORNERS_MEAN,
            "yellows_mean": DEFAULT_YELLOWS_MEAN,
            "shrinkage_prior_matches": SHRINKAGE_PRIOR_MATCHES,
        },
    }
    input_hashes = [
        "snapshot_validation:" + _digest(paths["artifacts_dir"], run_id,
                                          "snapshot_validation.json")
    ]
    artifact_path = paths["artifacts_dir"] / run_id / "baselines_run.json"
    write_artifact(
        artifact_path,
        payload,
        experiment_id=cfg["experiment_id"],
        run_id=run_id,
        producer=PRODUCER,
        input_hashes=input_hashes,
        status="validated",
        record_count=sum(c["n_predictions"] for c in counts.values()),
    )
    log_event(logger, "artifact", "validated",
              f"baselines_run.json modèles={len(counts)}", run_id=run_id)
    db.close()
    log_event(logger, "end", "ok", "baselines terminées", run_id=run_id)
    return 0


def load_baseline_predictions(
    predictions_dir: Path, run_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Charge les prédictions JSONL des baselines (utilisé par l'évaluateur)."""
    out_dir = predictions_dir / run_id / "baselines"
    result: dict[str, list[dict[str, Any]]] = {}
    if not out_dir.is_dir():
        return result
    for path in sorted(out_dir.glob("*.jsonl")):
        result[path.stem] = list(iter_jsonl(path))
    return result


def _digest(artifacts_dir: Path, run_id: str, name: str) -> str:
    """Hash SHA-256 d'un artefact d'entrée (chaîne d'audit §15)."""
    path = artifacts_dir / run_id / name
    if not path.is_file():
        return "absent"
    return sha256_text(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    """Parseur CLI de l'agent baselines."""
    parser = argparse.ArgumentParser(description="Agent Baselines (protocole §14.7)")
    parser.add_argument("--run-id", default="run_001")
    parser.add_argument("--config", default="configs/experiment.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI (§16)."""
    args = build_parser().parse_args(argv)
    return run_baselines(args.config, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
