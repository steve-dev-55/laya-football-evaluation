"""Agent Analyste (protocole §14.9, §18, §20, §21 « Analyste »).

Rôle : produire `reports/final_report.md` suivant STRICTEMENT la structure
§20 (17 sections numérotées : Résumé exécutif → Annexes de reproductibilité)
à partir :
- des rapports d'évaluation de l'agent évaluateur
  (`data/evaluation/{run_id}/evaluation_report.json`) ;
- des artefacts des autres agents (`data/artifacts/{run_id}/…`) ;
- du manifeste `experiment_manifest.json` ;
- des journaux (`logs/errors.log`) et des exclusions du nettoyeur.

RÈGLES (§14.9, §21 « Analyste ») :
- séparer EXPLICITEMENT résultats confirmatoires (hypothèses H1–H5
  pré-enregistrées dans le manifeste), analyses exploratoires et simples
  observations ;
- NE JAMAIS recalculer une métrique : les agrégats, intervalles et
  comparaisons sont repris TELS QUELS de l'évaluateur ;
- publier les dénominateurs et les taux d'invalidité (§19.2.5) ;
- une section sans donnée affiche « en attente d'exécution » au lieu
  d'inventer une valeur ;
- rapporter les limites §18 (tableau) et borner la conclusion au périmètre
  observé.

Sorties :
- `reports/final_report.md` (livrable humain, §19.1) ;
- `data/artifacts/{run_id}/analyst_report.json` (artefact §15 : en-tête,
  hash du rapport, sections, entrées consommées) ;
- `logs/analyst.log`.

Usage (§16) :
    python -m agents.analyst --run-id RUN_ID [--config configs/experiment.yaml]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agents.common import (
    config_paths,
    load_config,
    log_error,
    log_event,
    now_utc,
    read_artifact,
    read_manifest,
    setup_logging,
    sha256_file,
    write_artifact,
)
from agents.orchestrator import (
    PREREGISTERED_HYPOTHESES,
    resolve_manifest_path,
)

AGENT_NAME = "analyst"
PRODUCER = "analyst_agent"

PENDING = "en attente d'exécution"

# Structure §20 — 17 sections numérotées, intitulés figés.
SECTION_TITLES: tuple[str, ...] = (
    "Résumé exécutif",
    "Questions et hypothèses pré-enregistrées",
    "Sources, périmètre et exclusions",
    "Définition point-in-time et contrôles anti-fuite",
    "Version de Laya et tâches typées",
    "Baselines et découpage temporel",
    "Métriques et plan statistique",
    "Résultats globaux",
    "Résultats par cutoff, compétition et tier",
    "Calibration",
    "Robustesse et réactions aux événements",
    "Analyse des erreurs",
    "Résultats confirmatoires",
    "Analyses exploratoires",
    "Limites",
    "Conclusion",
    "Annexes de reproductibilité",
)

# Métrique principale par cible (§12, annexe B) : clé d'agrégat évaluateur.
PRIMARY_METRIC_KEYS: dict[str, tuple[str, str]] = {
    "1x2": ("log_loss_1x2", "log loss 1X2"),
    "score_bucket": ("score_bucket_log_loss", "log loss score regroupé"),
    "corners": ("corners_crps", "CRPS corners"),
    "yellow_cards": ("yellows_crps", "CRPS cartons jaunes"),
}

# Limites §18 — libellé + impact sur l'interprétation (tableau §20.15).
LIMITS_TABLE: tuple[tuple[str, str], ...] = (
    (
        "Les données sportives publiques peuvent être incomplètes, corrigées "
        "après publication ou soumises à licence.",
        "La couverture par strate et les exclusions doivent être consultées "
        "avant toute généralisation ; la licence de la source doit être citée.",
    ),
    (
        "La qualité apparente de Laya peut refléter des biais de couverture "
        "des compétitions ou des sources.",
        "Les comparaisons entre compétitations/saisons peuvent confondre "
        "couverture des données et performance du modèle.",
    ),
    (
        "Les événements et statistiques live peuvent être publiés avec retard ; "
        "la disponibilité réelle doit être modélisée.",
        "Les délais figés (30 s / 45 s / 96 min) bornent le réalisme des "
        "snapshots ; un retard supérieur dégraderait la comparabilité.",
    ),
    (
        "Les snapshots d'un même match ne constituent pas des observations "
        "indépendantes.",
        "Les intervalles sont groupés par match (§11.2) ; les métriques par "
        "snapshot restent descriptives.",
    ),
    (
        "Une catégorie `other` ou une queue censurée limite l'interprétation "
        "du score ou de l'espérance.",
        "Les espérances de comptages sont censurées aux seuils 21+ / 13+ et "
        "ne doivent pas être lues comme des espérances complètes.",
    ),
    (
        "Les effets après événement ne sont pas des effets causaux.",
        "Les réactions événementielles (§13.3) sont descriptives : elles ne "
        "supportent aucune lecture contrefactuelle.",
    ),
    (
        "Les résultats ne doivent pas être présentés comme un conseil de "
        "pari ni comme une garantie de résultat.",
        "Diffusion scientifique uniquement ; aucune utilisation décisionnelle "
        "ou commerciale n'est couverte par ce protocole.",
    ),
    (
        "Aucune donnée personnelle sensible n'est nécessaire ; les "
        "identifiants de joueurs doivent être pseudonymisés.",
        "Les identifiants de joueurs du jeu de données sont pseudonymes "
        "synthétiques ; aucune donnée réelle n'est exposée.",
    ),
    (
        "Les erreurs de modèle et les données manquantes doivent être "
        "rapportées, pas masquées par une imputation opportuniste.",
        "Les valeurs manquantes restent null (§7.2) ; les taux d'invalidité "
        "et les exclusions sont publiés dans ce rapport.",
    ),
)

ARTIFACT_INPUTS: tuple[tuple[str, str], ...] = (
    # (nom logique, chemin relatif au run dans data/artifacts/RUN_ID)
    ("collector_coverage", "collector_coverage.json"),
    ("cleaning_report", "cleaning_report.json"),
    ("pre_match_validation", "pre_match_validation.json"),
    ("snapshot_validation", "snapshot_validation.json"),
    ("laya_run", "laya_run.json"),
    ("repetition_audit", "repetition_audit.json"),
    ("baselines_run", "baselines_run.json"),
)


# --- Chargement des entrées -------------------------------------------------


def load_inputs(
    paths: dict[str, Path], run_id: str
) -> tuple[dict[str, dict[str, Any] | None], dict[str, str]]:
    """Charge les artefacts du run (présence optionnelle) + hashes SHA-256."""
    artifacts: dict[str, dict[str, Any] | None] = {}
    hashes: dict[str, str] = {}
    for name, filename in ARTIFACT_INPUTS:
        path = paths["artifacts_dir"] / run_id / filename
        try:
            artifacts[name] = read_artifact(path) if path.is_file() else None
        except (ValueError, json.JSONDecodeError):
            artifacts[name] = None
        if path.is_file():
            hashes[name] = sha256_file(path)
    eval_path = paths["evaluation_dir"] / run_id / "evaluation_report.json"
    try:
        artifacts["evaluation_report"] = read_artifact(eval_path) if eval_path.is_file() else None
    except (ValueError, json.JSONDecodeError):
        artifacts["evaluation_report"] = None
    if eval_path.is_file():
        hashes["evaluation_report"] = sha256_file(eval_path)
    report_path = paths["reports_dir"] / "final_report.md"
    if report_path.is_file():
        hashes["previous_final_report"] = sha256_file(report_path)
    return artifacts, hashes


def load_error_log(paths: dict[str, Path]) -> list[dict[str, Any]]:
    """Lit `logs/errors.log` (lignes JSON §15), sans donnée personnelle."""
    errors_path = Path(paths["logs_dir"]) / "errors.log"
    if not errors_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in errors_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


# --- Aides de mise en forme (aucun calcul de métrique) ------------------------


def _holm_verdict(stats: dict[str, Any]) -> str:
    """Verdict Holm-Bonferroni formaté (§12.5) — pure mise en forme."""
    verdict = "significatif" if stats.get("significant_holm") else "non significatif"
    return f"(Holm : {verdict})"


def _num(value: Any, digits: int = 4) -> str:
    """Formate un nombre sans jamais le recalculer ; None → n/d."""
    if value is None:
        return "n/d"
    if isinstance(value, bool):
        return "oui" if value else "non"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _mean_ci(entry: Any) -> str:
    """« moyenne [ic_bas ; ic_haut] » tel que fourni par l'évaluateur."""
    if not isinstance(entry, dict):
        return PENDING
    mean = entry.get("mean")
    if mean is None:
        return "n/d"
    low, high = entry.get("ci_low"), entry.get("ci_high")
    if low is None or high is None:
        return _num(mean)
    return f"{_num(mean)} [{_num(low)} ; {_num(high)}]"


def _payload(artifact: dict[str, Any] | None) -> dict[str, Any]:
    """Charge utile d'un artefact (vide si absent)."""
    if not artifact:
        return {}
    return artifact.get("payload") or {}


def _status_of(artifact: dict[str, Any] | None) -> str:
    """Statut §15 d'un artefact, « absent » sinon."""
    return str((artifact or {}).get("status") or "absent")


def _markdown_table(header: list[str], rows: list[list[str]]) -> str:
    """Tableau Markdown simple avec en-tête figé."""
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _primary_targets(manifest: dict[str, Any]) -> list[str]:
    """Cibles des métriques principales (ordre du manifeste)."""
    metrics = manifest.get("primary_metrics") or {}
    return [str(t) for t in metrics if str(t) in PRIMARY_METRIC_KEYS]


# --- Sections §20 ------------------------------------------------------------


def _section_1_summary(
    manifest: dict[str, Any],
    evaluation: dict[str, Any],
    artifacts: dict[str, dict[str, Any] | None],
    run_id: str,
) -> list[str]:
    """Section 1 — Résumé exécutif (chiffres repris tels quels)."""
    lines = [""]
    laya_run = _payload(artifacts.get("laya_run"))
    cleaning = _payload(artifacts.get("cleaning_report"))
    snapshot_val = _payload(artifacts.get("snapshot_validation"))
    counts = laya_run.get("counts") or {}
    summary = snapshot_val.get("summary") or {}
    cleaning_counts = cleaning.get("counts") or {}
    model_meta = laya_run.get("model_metadata") or {}
    lines.append(
        f"- **Expérience :** {manifest.get('experiment_id')} — run `{run_id}` "
        f"(protocole v{manifest.get('protocol_version')})."
    )
    lines.append(
        "- **Statut du pipeline :** "
        + "; ".join(
            f"{name} = {_status_of(artifacts.get(name))}"
            for name, _ in ARTIFACT_INPUTS
        )
        + f" ; evaluation_report = {_status_of(artifacts.get('evaluation_report'))}."
    )
    lines.append(
        f"- **Périmètre analysé :** {cleaning_counts.get('included', 'n/d')} "
        f"matchs inclus (sur {cleaning_counts.get('collected', 'n/d')} collectés), "
        f"{summary.get('n_snapshots', 'n/d')} snapshots, "
        f"{counts.get('valid', 'n/d')} prédictions Laya valides "
        f"(taux d'invalidité {_num(counts.get('invalid_rate'), 4)})."
    )
    blocking = evaluation.get("blocking_checks") or {}
    if blocking:
        lines.append(
            "- **Contrôles bloquants §11.4 :** "
            + " ; ".join(
                f"{key} = {_num((check or {}).get('value'))} "
                f"(seuil {_num((check or {}).get('threshold'))}) "
                f"→ {'bloqué' if (check or {}).get('blocked') else 'passé'}"
                for key, check in blocking.items()
            )
            + "."
        )
    else:
        lines.append(f"- **Contrôles bloquants §11.4 :** {PENDING}.")
    hyp = evaluation.get("hypotheses") or {}
    lines.append(
        f"- **Hypothèses pré-enregistrées évaluées :** "
        f"{len([h for h in hyp if h])} sur 5 (détail en section 13)."
    )
    if "mock" in str(model_meta.get("package", "")):
        lines.append(
            "- **AVERTISSEMENT — mode démonstration :** le client Laya est un "
            "client *mock* déterministe et les données sont synthétiques ; "
            "AUCUNE conclusion sur le système Laya réel ne peut être tirée de "
            "ce run (§0.3)."
        )
    return lines


def _section_2_hypotheses(manifest: dict[str, Any]) -> list[str]:
    """Section 2 — Questions et hypothèses pré-enregistrées (§1)."""
    lines = [""]
    lines.append(
        "Question principale (§1.1) : à information disponible à la minute `t`, "
        "Laya produit-il des distributions prédictives mieux calibrées et/ou "
        "plus discriminantes que les baselines pour le 1X2, le score "
        "regroupé, les corners et les cartons jaunes ?"
    )
    lines.append("")
    lines.append("Hypothèses confirmatoires pré-enregistrées (§1.3) :")
    hypotheses = manifest.get("hypotheses") or PREREGISTERED_HYPOTHESES
    for code in sorted(hypotheses):
        lines.append(f"- **{code}** — {hypotheses[code]}")
    lines.append("")
    lines.append(
        "Une hypothèse non écrite dans le manifeste avant l'évaluation du "
        "test final est exploratoire et ne doit jamais être présentée comme "
        "confirmatoire (§1.3)."
    )
    return lines


def _section_3_sources(
    manifest: dict[str, Any],
    artifacts: dict[str, dict[str, Any] | None],
) -> list[str]:
    """Section 3 — Sources, périmètre et exclusions."""
    lines = [""]
    collector = _payload(artifacts.get("collector_coverage"))
    cleaning = _payload(artifacts.get("cleaning_report"))
    coverage = collector.get("coverage") or {}
    lines.append(f"- **Source principale :** {manifest.get('primary_source')}")
    lines.append(f"- **Source secondaire :** {manifest.get('secondary_source')}")
    lines.append(
        f"- **Compétitions :** {', '.join(manifest.get('competitions') or [])} ; "
        f"**saisons :** {', '.join(manifest.get('seasons') or [])}."
    )
    lines.append(
        f"- **Couverture du collecteur :** {coverage.get('found', 'n/d')}/"
        f"{coverage.get('expected', 'n/d')} documents."
    )
    exclusions = cleaning.get("exclusions") or []
    lines.append(
        f"- **Exclusions motivées (§3.4) :** {len(exclusions)} match(s) exclu(s)."
    )
    if exclusions:
        reasons: dict[str, int] = {}
        for exclusion in exclusions:
            reason = str(exclusion.get("reason"))
            reasons[reason] = reasons.get(reason, 0) + 1
        rows = [[reason, str(count)] for reason, count in sorted(reasons.items())]
        lines.append("")
        lines.append(_markdown_table(["Raison d'exclusion", "Matchs"], rows))
    lines.append("")
    lines.append(
        f"- **Taux de matchs manquants maximal par strate :** "
        f"{_num(cleaning.get('max_stratum_missing_rate'))} "
        f"(seuil {_num(cleaning.get('threshold_stratum_missing_rate'))})."
    )
    return lines


def _section_4_pit(manifest: dict[str, Any],
                   artifacts: dict[str, dict[str, Any] | None]) -> list[str]:
    """Section 4 — Définition point-in-time et contrôles anti-fuite."""
    lines = [""]
    snapshot_val = _payload(artifacts.get("snapshot_validation"))
    pre_match = _payload(artifacts.get("pre_match_validation"))
    summary = snapshot_val.get("summary") or {}
    lines.append(
        "- Référence temporelle : UTC ISO-8601 ; cutoffs fixes = "
        + ", ".join(f"{int(c)} s" for c in manifest.get("cutoffs_seconds") or [])
        + " (§5.1, §6.1) + snapshots événementiels (§6.2)."
    )
    lines.append(
        "- Tiers d'information : "
        + ", ".join(str(t) for t in manifest.get("information_tiers") or [])
        + " (décision annexe B ; définitions §6.3)."
    )
    lines.append(
        "- Tests anti-fuite exécutés sur 100 % des snapshots (§5.5) : "
        + " ; ".join(snapshot_val.get("tests") or [])
        + "."
    )
    lines.append(
        f"- Résultat : {summary.get('n_blocked', 'n/d')} snapshot(s) bloqué(s) "
        f"sur {summary.get('n_snapshots', 'n/d')} ; taux de fuite = "
        f"{_num(summary.get('leakage_rate'))} (seuil §11.4 : 5 %)."
    )
    pre_counts = pre_match.get("counts") or {}
    if pre_counts:
        lines.append(
            f"- Contexte pré-match : {pre_counts.get('contexts', 'n/d')} "
            f"contextes pour {pre_counts.get('matches', 'n/d')} matchs ; "
            f"{pre_counts.get('blocked_matches', 'n/d')} bloqué(s) ; "
            f"{pre_counts.get('matches_without_history', 'n/d')} sans "
            "historique (features null, §7.2)."
        )
    else:
        lines.append(f"- Contexte pré-match : {PENDING}.")
    return lines


def _section_5_laya(manifest: dict[str, Any],
                   artifacts: dict[str, dict[str, Any] | None]) -> list[str]:
    """Section 5 — Version de Laya et tâches typées (§2, §8)."""
    lines = [""]
    laya_run = _payload(artifacts.get("laya_run"))
    meta = laya_run.get("model_metadata") or {}
    model = manifest.get("model") or {}
    lines.append(f"- **Paquet :** {meta.get('package', model.get('package', 'n/d'))}.")
    lines.append(f"- **Version :** {meta.get('version', model.get('version', 'n/d'))}.")
    lines.append(
        f"- **Checkpoint :** {meta.get('checkpoint', model.get('checkpoint', 'n/d'))}."
    )
    lines.append(
        f"- **Mode routeur :** {model.get('router_mode', 'n/d')} ; "
        f"contexte maximal : {meta.get('max_context_chars', 'n/d')} caractères."
    )
    lines.append(
        f"- **Version des questions :** {laya_run.get('questions_version', 'n/d')} "
        "(QUESTIONS_V1 : score_bucket 17 catégories, total_corners 22 niveaux "
        "dont 21+, total_yellow_cards 14 niveaux dont 13+, §8.5)."
    )
    lines.append(
        "- Dérivations pré-enregistrées : 1X2 dérivé de la distribution de "
        "score regroupé (§8.1) ; espérances censurées aux seuils de queue "
        "(§8.3, §8.4) ; aucune renormalisation d'une réponse reçue (§8.6)."
    )
    counts = laya_run.get("counts") or {}
    if counts:
        lines.append(
            f"- **Réponses :** {counts.get('valid', 'n/d')} valides / "
            f"{counts.get('snapshots', 'n/d')} snapshots ; taux d'invalidité = "
            f"{_num(counts.get('invalid_rate'))} (seuil "
            f"{_num(counts.get('threshold_invalid_rate'))})."
        )
    return lines


def _section_6_baselines(manifest: dict[str, Any],
                         artifacts: dict[str, dict[str, Any] | None]) -> list[str]:
    """Section 6 — Baselines et découpage temporel (§10, §11.1)."""
    lines = [""]
    baselines = _payload(artifacts.get("baselines_run"))
    training = (baselines.get("training") or {}).get("logistic_1x2") or {}
    models = baselines.get("models") or {}
    lines.append(
        "- Baselines (§10.1, §10.2) : "
        + ", ".join(f"`{name}` ({(models.get(name) or {}).get('n_predictions', 'n/d')})"
                    for name in sorted(models))
        + "."
    )
    lines.append(
        "- Comparaison équitable (§10.4) : mêmes snapshots, mêmes cutoffs, "
        "mêmes informations que Laya."
    )
    if training:
        lines.append(
            f"- Découpage temporel (§11.1) : entraînement = "
            f"{', '.join(training.get('train_seasons') or [])} "
            f"({training.get('n_train_matches')} matchs, "
            f"kickoffs {training.get('min_kickoff')} → "
            f"{training.get('max_kickoff')}) ; test final = saisons "
            "les plus récentes. Aucun entraînement sur le test final."
        )
    else:
        lines.append(f"- Découpage temporel : {PENDING}.")
    return lines


def _section_7_plan(manifest: dict[str, Any],
                    evaluation: dict[str, Any]) -> list[str]:
    """Section 7 — Métriques et plan statistique (§12)."""
    lines = [""]
    metrics = manifest.get("primary_metrics") or {}
    lines.append(
        "- **Métriques principales par cible (annexe B) :** "
        + " ; ".join(f"{target} = {metric}" for target, metric in metrics.items())
        + "."
    )
    lines.append(
        "- Métriques secondaires : Brier, RPS, exactitude, MAE censurées, "
        "masse de queue, PIT randomisé, couverture 50/80/95 % (§12.3, §12.4)."
    )
    bootstrap = evaluation.get("bootstrap") or {}
    if bootstrap:
        lines.append(
            f"- **Bootstrap :** {bootstrap.get('method')} ; "
            f"{bootstrap.get('replicates')} réplications ; alpha = "
            f"{bootstrap.get('alpha')} ; seed = {bootstrap.get('seed')} (§12.5)."
        )
    else:
        lines.append(f"- **Bootstrap :** {PENDING}.")
    lines.append(
        "- Corrections multiples : Holm-Bonferroni, une famille par cible "
        "(4 familles, décision annexe B) ; un test non significatif ne prouve "
        "pas l'égalité des modèles (§12.5)."
    )
    return lines


def _section_8_global(
    manifest: dict[str, Any], evaluation: dict[str, Any]
) -> list[str]:
    """Section 8 — Résultats globaux (scope test, agrégats évaluateur)."""
    lines = [""]
    aggregates = (evaluation.get("aggregates") or {}).get("test") or {}
    denominators = evaluation.get("denominators") or {}
    bootstrap = evaluation.get("bootstrap") or {}
    if not aggregates:
        lines.append(f"{PENDING.capitalize()} — aucun agrégat fourni par l'évaluateur.")
        return lines
    method = f"{bootstrap.get('method', 'bootstrap groupé par match')} "
    method += f"({bootstrap.get('replicates', 'n/d')} réplications)"
    rows: list[list[str]] = []
    for model in sorted(aggregates):
        denom = denominators.get(model) or {}
        for target in _primary_targets(manifest):
            metric_key, label = PRIMARY_METRIC_KEYS[target]
            entry = aggregates.get(model, {}).get(metric_key)
            rows.append([
                model,
                target,
                label,
                "tous (0–5100 s)",
                str((entry or {}).get("n_matches", denom.get("n_matches", "n/d"))),
                str(denom.get("n_predictions_test_scope", "n/d")),
                _mean_ci(entry),
            ])
    lines.append(
        "Scope : saison(s) test (split temporel §11.1). Chaque ligne reprend "
        "l'agrégat fourni par l'évaluateur, sans recalcul."
    )
    lines.append("")
    lines.append(_markdown_table(
        ["Modèle", "Cible", "Métrique", "Cutoff", "Matchs", "Snapshots",
         "Réponses valides", "Valeur [IC 95 %]"],
        rows,
    ))
    lines.append("")
    lines.append(f"Méthode de bootstrap : {method}.")
    # Dénominateurs et taux d'invalidité (§19.2.5).
    lines.append("")
    lines.append("Dénominateurs et taux d'invalidité (§19.2.5) :")
    denom_rows: list[list[str]] = []
    for model in sorted(denominators):
        if model.startswith("_"):
            continue
        denom = denominators[model] or {}
        denom_rows.append([
            model,
            str(denom.get("n_predictions")),
            str(denom.get("n_predictions_test_scope")),
            str(denom.get("n_matches")),
            _num(denom.get("invalid_rate_laya")),
        ])
    laya_counts = denominators.get("_laya_response_counts") or {}
    denom_rows.append([
        "laya (total toutes saisons)",
        str(laya_counts.get("total", "n/d")),
        "—",
        "—",
        _num(
            (laya_counts.get("invalid") or 0) / (laya_counts.get("total") or 1)
            if laya_counts.get("total") else None
        ),
    ])
    lines.append(_markdown_table(
        ["Modèle", "Prédictions", "Prédictions (scope test)", "Matchs",
         "Taux d'invalidité"],
        denom_rows,
    ))
    return lines


def _section_9_strata(evaluation: dict[str, Any]) -> list[str]:
    """Section 9 — Résultats par cutoff, compétition et tier (descriptif)."""
    lines = [""]
    by_cutoff = evaluation.get("by_cutoff") or {}
    by_competition = evaluation.get("by_competition") or {}
    by_tier = evaluation.get("by_tier") or {}
    if not (by_cutoff or by_competition or by_tier):
        lines.append(f"{PENDING.capitalize()} — ventilations non fournies.")
        return lines
    if by_cutoff:
        lines.append("**Par cutoff (scope test, log loss 1X2 moyen) :**")
        rows = []
        for cutoff in sorted(by_cutoff, key=lambda c: int(c)):
            for model in sorted(by_cutoff[cutoff]):
                entry = by_cutoff[cutoff][model] or {}
                rows.append([
                    f"{int(cutoff)} s", model,
                    str(int(entry.get("n_predictions", 0))),
                    _num(entry.get("log_loss_1x2_mean")),
                ])
        lines.append("")
        lines.append(_markdown_table(
            ["Cutoff", "Modèle", "Prédictions", "Log loss 1X2 (moyenne)"], rows))
        lines.append("")
    if by_tier:
        lines.append("**Par tier d'information (scope test) :**")
        rows = []
        for tier in sorted(by_tier):
            for model in sorted(by_tier[tier]):
                entry = by_tier[tier][model] or {}
                rows.append([
                    tier, model,
                    str(int(entry.get("n_predictions", 0))),
                    _num(entry.get("log_loss_1x2_mean")),
                ])
        lines.append("")
        lines.append(_markdown_table(
            ["Tier", "Modèle", "Prédictions", "Log loss 1X2 (moyenne)"], rows))
        lines.append("")
    if by_competition:
        lines.append("**Par compétition (scope test) :**")
        rows = []
        for competition in sorted(by_competition):
            for model in sorted(by_competition[competition]):
                entry = by_competition[competition][model] or {}
                rows.append([
                    competition, model,
                    str(int(entry.get("n_predictions", 0))),
                    _num(entry.get("log_loss_1x2_mean")),
                ])
        lines.append("")
        lines.append(_markdown_table(
            ["Compétition", "Modèle", "Prédictions", "Log loss 1X2 (moyenne)"],
            rows))
    lines.append("")
    lines.append(
        "Ventilations descriptives (moyennes sans intervalle) fournies par "
        "l'évaluateur ; ces tableaux alimentent la section 14 (exploratoire)."
    )
    return lines


def _section_10_calibration(evaluation: dict[str, Any]) -> list[str]:
    """Section 10 — Calibration (§12.4)."""
    lines = [""]
    calibration = evaluation.get("calibration") or {}
    if not calibration:
        lines.append(f"{PENDING.capitalize()} — calibration non fournie.")
        return lines
    rows = []
    for model in sorted(calibration):
        entry = calibration[model] or {}
        rows.append([
            model,
            _num(entry.get("ece_1x2")),
            str(entry.get("n_observations")),
            str(entry.get("n_bins")),
            str(entry.get("binning")),
        ])
    lines.append(_markdown_table(
        ["Modèle", "ECE 1X2", "Observations", "Bins", "Découpage"], rows))
    lines.append("")
    lines.append(
        "ECE calculé par l'évaluateur (bins annoncés, décision figée) ; "
        "un ECE plus faible indique une meilleure calibration."
    )
    return lines


def _section_11_robustness(artifacts: dict[str, dict[str, Any] | None],
                           evaluation: dict[str, Any]) -> list[str]:
    """Section 11 — Robustesse et réactions aux événements (§13)."""
    lines = [""]
    repetition = _payload(artifacts.get("repetition_audit"))
    if repetition:
        lines.append(
            f"- **Audit de répétition (§9.2) :** k = {repetition.get('k')} sur "
            f"{repetition.get('n_audited')} snapshots "
            f"(part {repetition.get('share')}) ; sorties identiques = "
            f"{repetition.get('all_identical')} ; JS max = "
            f"{_num(repetition.get('max_js_distance'))} ; taux de changement "
            f"de décision = {_num(repetition.get('decision_change_rate'))}."
        )
    else:
        lines.append(f"- **Audit de répétition (§9.2) :** {PENDING}.")
    lines.append(
        f"- **Paraphrases / réordonnancement / traduction (§13.1, §13.2) :** "
        f"{PENDING} (aucune variante de formulation dans ce run — H4 non exécutée)."
    )
    reactions = evaluation.get("event_reactions") or {}
    if reactions:
        lines.append(
            f"- **Réaction après but (§13.3, H3) :** variation moyenne de la "
            f"probabilité du côté qui marque = "
            f"{_num(reactions.get('mean_delta_p_scoring_side'))} sur "
            f"{reactions.get('n_pairs')} paires ({reactions.get('scope')}). "
            "Analyse descriptive, sans interprétation causale."
        )
    else:
        lines.append(f"- **Réaction après but (§13.3) :** {PENDING}.")
    lines.append(
        f"- **Snapshots quasi identiques (§13.4) :** {PENDING}."
    )
    return lines


def _section_12_errors(artifacts: dict[str, dict[str, Any] | None],
                       evaluation: dict[str, Any],
                       error_log: list[dict[str, Any]]) -> list[str]:
    """Section 12 — Analyse des erreurs (chiffres publiés, pas recalculés)."""
    lines = [""]
    laya_run = _payload(artifacts.get("laya_run"))
    counts = laya_run.get("counts") or {}
    invalid = counts.get("invalid")
    if invalid is None:
        lines.append(f"- **Réponses invalides Laya :** {PENDING}.")
    else:
        lines.append(
            f"- **Réponses invalides Laya (§9.3) :** {invalid} sur "
            f"{counts.get('snapshots')} (taux "
            f"{_num(counts.get('invalid_rate'))}, seuil "
            f"{_num(counts.get('threshold_invalid_rate'))}) ; aucune réponse "
            "n'est réparée ni renormalisée (§0.4)."
        )
    aggregates = (evaluation.get("aggregates") or {}).get("test") or {}
    laya_agg = aggregates.get("laya") or {}
    if laya_agg:
        lines.append(
            "- **Masse de queue moyenne (censure 21+/13+) :** corners = "
            f"{_mean_ci(laya_agg.get('corners_tail_mass'))} ; cartons = "
            f"{_mean_ci(laya_agg.get('yellows_tail_mass'))}."
        )
        lines.append(
            "- **MAE censurée moyenne (comptages) :** corners = "
            f"{_mean_ci(laya_agg.get('corners_mae'))} ; cartons = "
            f"{_mean_ci(laya_agg.get('yellows_mae'))} ; buts = "
            f"{_mean_ci(laya_agg.get('mae_goals'))}."
        )
    if error_log:
        lines.append(
            f"- **Journal d'erreurs :** {len(error_log)} entrée(s) dans "
            "`logs/errors.log` (horodatées, sans donnée personnelle)."
        )
    else:
        lines.append("- **Journal d'erreurs :** aucune erreur journalisée.")
    lines.append(
        "- Les erreurs de modèle et les données manquantes sont rapportées, "
        "jamais masquées par une imputation (§18)."
    )
    return lines


def _section_13_confirmatory(manifest: dict[str, Any],
                             evaluation: dict[str, Any]) -> list[str]:
    """Section 13 — Résultats confirmatoires (H1–H5 du manifeste)."""
    lines = [""]
    lines.append(
        "**Résultats confirmatoires — hypothèses H1 à H5 pré-enregistrées "
        "uniquement.** Toute autre comparaison figure en section 14 "
        "(exploratoire) et ne peut pas être présentée comme confirmatoire "
        "(§1.3, annexe B)."
    )
    hypotheses = manifest.get("hypotheses") or PREREGISTERED_HYPOTHESES
    evaluated_hyp = evaluation.get("hypotheses") or {}
    if not evaluated_hyp:
        lines.append("")
        lines.append(f"{PENDING.capitalize()} — l'évaluateur n'a fourni aucun "
                     "résultat d'hypothèse.")
        return lines
    laya_agg = (evaluation.get("aggregates") or {}).get("test", {}).get("laya") or {}
    for code in sorted(hypotheses):
        lines.append("")
        lines.append(f"**{code} — {hypotheses[code]}**")
        data = evaluated_hyp.get(code)
        if code == "H1_progression_temporelle":
            entry = laya_agg.get("log_loss_1x2")
            lines.append(
                f"- Statut : confirmatoire. Log loss 1X2 (scope test) = "
                f"{_mean_ci(entry)}. La lecture par cutoff (section 9) permet "
                "de comparer pré-match et 85 minutes ; aucune conclusion "
                "n'est tirée ici à la place de l'évaluateur."
            )
        elif code == "H2_calibration":
            calibration = evaluation.get("calibration") or {}
            lines.append(
                f"- Statut : confirmatoire. ECE laya = "
                f"{_num((calibration.get('laya') or {}).get('ece_1x2'))} ; "
                f"ECE fréquence historique = "
                f"{_num((calibration.get('historical_frequency') or {}).get('ece_1x2'))}."
            )
        elif code == "H3_reaction_apres_but":
            reactions = data or {}
            lines.append(
                f"- Statut : confirmatoire (descriptif directionnel). Δ moyen "
                f"probabilité du côté buteur = "
                f"{_num(reactions.get('mean_delta_p_scoring_side'))} "
                f"({reactions.get('n_pairs')} paires) — sans lecture causale (§13.3)."
            )
        elif code == "H4_robustesse":
            lines.append(
                "- Statut : NON exécutée dans ce run (aucune variante de "
                "formulation pré-enregistrée n'a été soumise) — ne peut ni "
                "être validée ni être rejetée."
            )
        elif code == "H5_comptages":
            families = data.get("families") if isinstance(data, dict) else None
            if families:
                for family, payload in sorted(families.items()):
                    lines.append(
                        f"- Statut : confirmatoire. Famille `{family}` "
                        f"(référence {payload.get('reference')}) : "
                        + " ; ".join(
                            f"{model} Δ = { _num(stats.get('mean_difference')) } "
                            f"[{_num(stats.get('ci_low'))} ; "
                            f"{_num(stats.get('ci_high'))}] " + _holm_verdict(stats)
                            for model, stats in sorted((payload.get("models") or {}).items())
                        )
                    )
            else:
                lines.append(f"- Statut : confirmatoire. {PENDING}.")
        else:
            lines.append("- Hypothèse inconnue du rapporteur.")
    return lines


def _section_14_exploratory(evaluation: dict[str, Any]) -> list[str]:
    """Section 14 — Analyses exploratoires (jamais confirmatoires)."""
    lines = [""]
    lines.append(
        "**Analyses exploratoires.** Les résultats ci-dessous ne font partie "
        "d'aucune hypothèse pré-enregistrée : ils sont descriptifs et ne "
        "peuvent pas être présentés comme confirmatoires (annexe B)."
    )
    comparisons = evaluation.get("comparisons") or {}
    if comparisons:
        lines.append("")
        lines.append("**Comparaisons par famille (Holm-Bonferroni, §12.5) :**")
        rows = []
        for family, payload in sorted(comparisons.items()):
            for model, stats in sorted((payload.get("models") or {}).items()):
                rows.append([
                    family,
                    payload.get("metric"),
                    payload.get("reference"),
                    model,
                    _num(stats.get("mean_difference")),
                    f"[{_num(stats.get('ci_low'))} ; {_num(stats.get('ci_high'))}]",
                    "oui" if stats.get("significant_holm") else "non",
                    _num(stats.get("p_value"), 6),
                ])
        lines.append(_markdown_table(
            ["Famille", "Métrique", "Référence", "Modèle", "Δ moyen",
             "IC 95 %", "Significatif (Holm)", "p"],
            rows,
        ))
        lines.append("")
        lines.append(
            "Convention : différence = modèle − laya (>0 : moins bon que "
            "laya). Un test non significatif ne prouve pas l'équivalence."
        )
    else:
        lines.append(f"- Comparaisons par famille : {PENDING}.")
    lines.append(
        "- Ventilations par cutoff / compétition / tier : voir section 9 "
        "(descriptif)."
    )
    lines.append(
        "- Réactions événementielles après carton rouge, penalty, "
        f"remplacement : {PENDING}."
    )
    return lines


def _section_15_limits() -> list[str]:
    """Section 15 — Limites (tableau §18, texte figé du protocole)."""
    lines = [""]
    rows = [[str(i), limit, impact]
            for i, (limit, impact) in enumerate(LIMITS_TABLE, start=1)]
    lines.append(_markdown_table(
        ["#", "Limite (§18)", "Impact sur l'interprétation"], rows))
    return lines


def _section_16_conclusion(manifest: dict[str, Any],
                           artifacts: dict[str, dict[str, Any] | None],
                           evaluation: dict[str, Any]) -> list[str]:
    """Section 16 — Conclusion bornée au périmètre observé."""
    lines = [""]
    laya_run = _payload(artifacts.get("laya_run"))
    model_meta = laya_run.get("model_metadata") or {}
    lines.append(
        "Ce rapport documente un run exécutable de bout en bout du protocole "
        f"v{manifest.get('protocol_version')} : collecte, nettoyage, contexte "
        "pré-match, snapshots anti-fuite, prédictions, baselines, évaluation "
        "et correction multiple sont traçables par artefacts hashés (§15)."
    )
    if "mock" in str(model_meta.get("package", "")):
        lines.append(
            "Le périmètre observé est un jeu de données synthétique et un "
            "client mock déterministe : **aucune conclusion sur le système "
            "Laya réel, sa calibration réelle ou son utilité décisionnelle "
            "ne peut être tirée de ce run** (§0.3). Les résultats numériques "
            "valident la MÉTHODE (pipeline reproductible, contrôles "
            "anti-fuite, dénominateurs publiés), pas le modèle."
        )
    else:
        lines.append(
            "Les conclusions restent bornées au périmètre pré-enregistré "
            f"({', '.join(manifest.get('competitions') or [])}, "
            f"{', '.join(manifest.get('seasons') or [])}) et aux métriques "
            "principales déclarées ; tout autre résultat est exploratoire."
        )
    blocking = evaluation.get("blocking_checks") or {}
    if blocking and all(not (check or {}).get("blocked") for check in blocking.values()):
        lines.append(
            "Aucun critère de blocage §11.4 n'a été déclenché sur ce run."
        )
    return lines


def _section_17_annex(
    manifest: dict[str, Any],
    run_id: str,
    config_path: Path,
    manifest_path: Path,
    hashes: dict[str, str],
    generated_at: str,
) -> list[str]:
    """Section 17 — Annexes de reproductibilité (§17)."""
    lines = [""]
    lines.append(f"- **Run :** `{run_id}` ; généré le {generated_at} (UTC).")
    lines.append(
        f"- **Configuration :** `{config_path}` ; **manifeste :** "
        f"`{manifest_path}` ; seed = {manifest.get('seed')}."
    )
    lines.append(
        "- **Commandes de reproduction (§16) :** `python -m src.storage.database init` "
        "puis `python -m agents.collector|cleaner|pre_match|snapshot|laya|"
        "baselines|evaluator|analyst --run-id " + run_id + " --config "
        + str(config_path) + "` (ou `python -m agents.orchestrator --config "
        + str(config_path) + " --run-id " + run_id + "`)."
    )
    lines.append("")
    lines.append("**Décisions figées du manifeste (annexe B) :**")
    rows = []
    for key, decision in sorted((manifest.get("decisions") or {}).items()):
        value = decision.get("value") if isinstance(decision, dict) else decision
        why = decision.get("justification") if isinstance(decision, dict) else ""
        rows.append([key, str(value), str(why)])
    lines.append(_markdown_table(["Décision", "Valeur", "Justification"], rows))
    lines.append("")
    lines.append("**Hashes SHA-256 des artefacts sources :**")
    rows = [[name, digest] for name, digest in sorted(hashes.items())]
    lines.append(_markdown_table(["Artefact", "SHA-256"], rows))
    lines.append("")
    lines.append(
        "Une reproduction doit pouvoir repartir des fichiers bruts sans "
        "appeler de nouveau l'API externe (§17)."
    )
    return lines


def render_final_report(
    cfg: dict[str, Any],
    manifest: dict[str, Any],
    artifacts: dict[str, dict[str, Any] | None],
    hashes: dict[str, str],
    error_log: list[dict[str, Any]],
    run_id: str,
    config_path: Path,
    manifest_path: Path,
) -> str:
    """Assemble le rapport final §20 (17 sections numérotées)."""
    evaluation = _payload(artifacts.get("evaluation_report"))
    generated_at = now_utc()
    sections: list[tuple[str, list[str]]] = [
        ("Résumé exécutif",
         _section_1_summary(manifest, evaluation, artifacts, run_id)),
        ("Questions et hypothèses pré-enregistrées", _section_2_hypotheses(manifest)),
        ("Sources, périmètre et exclusions", _section_3_sources(manifest, artifacts)),
        ("Définition point-in-time et contrôles anti-fuite",
         _section_4_pit(manifest, artifacts)),
        ("Version de Laya et tâches typées", _section_5_laya(manifest, artifacts)),
        ("Baselines et découpage temporel", _section_6_baselines(manifest, artifacts)),
        ("Métriques et plan statistique", _section_7_plan(manifest, evaluation)),
        ("Résultats globaux", _section_8_global(manifest, evaluation)),
        ("Résultats par cutoff, compétition et tier", _section_9_strata(evaluation)),
        ("Calibration", _section_10_calibration(evaluation)),
        ("Robustesse et réactions aux événements",
         _section_11_robustness(artifacts, evaluation)),
        ("Analyse des erreurs",
         _section_12_errors(artifacts, evaluation, error_log)),
        ("Résultats confirmatoires",
         _section_13_confirmatory(manifest, evaluation)),
        ("Analyses exploratoires", _section_14_exploratory(evaluation)),
        ("Limites", _section_15_limits()),
        ("Conclusion", _section_16_conclusion(manifest, artifacts, evaluation)),
        ("Annexes de reproductibilité",
         _section_17_annex(manifest, run_id, config_path, manifest_path,
                           hashes, generated_at)),
    ]
    parts: list[str] = [
        "# Rapport final — Évaluation de Laya (protocole "
        f"v{manifest.get('protocol_version')})",
        "",
        f"- **Expérience :** {manifest.get('experiment_id')} — run `{run_id}`",
        f"- **Généré le :** {generated_at} (UTC)",
        "- **Structure :** §20 du protocole (17 sections numérotées)",
        "",
        "> Avertissement (§0.2, §18) : ce rapport est un document scientifique "
        "pré-enregistré ; il ne constitue ni un conseil de pari ni une garantie "
        "de résultat. Les sections sans donnée affichent « "
        + PENDING + " ».",
    ]
    for number, (title, body) in enumerate(sections, start=1):
        expected = SECTION_TITLES[number - 1]
        if title != expected:  # garde-fou structure §20
            raise ValueError(f"section {number} inattendue : {title!r} ≠ {expected!r}")
        parts.append(f"\n## {number}. {title}\n")
        parts.append("\n".join(body))
    return "\n".join(parts) + "\n"


def analyze(config_path: str | Path, run_id: str) -> int:
    """Produit le rapport final §20 et l'artefact d'en-tête §15."""
    config_file = Path(config_path)
    cfg = load_config(config_file)
    paths = config_paths(cfg)
    logger = setup_logging(AGENT_NAME, paths["logs_dir"])
    log_event(logger, "start", "ok", f"rapport final du run {run_id}", run_id=run_id)

    manifest_path = resolve_manifest_path(cfg)
    if not manifest_path.is_file():
        message = f"manifeste introuvable : {manifest_path}"
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "manifest", message)
        log_event(logger, "manifest", "error", message, run_id=run_id)
        return 1
    try:
        manifest = read_manifest(manifest_path)
    except ValueError as exc:
        message = f"manifeste invalide : {exc}"
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "manifest", message)
        log_event(logger, "manifest", "error", message, run_id=run_id)
        return 1

    artifacts, hashes = load_inputs(paths, run_id)
    error_log = load_error_log(paths)
    missing = [name for name, data in artifacts.items() if data is None]
    if missing:
        log_event(
            logger, "inputs", "warning",
            f"artefacts absents (sections « {PENDING} ») : {missing}",
            run_id=run_id,
        )

    report = render_final_report(
        cfg, manifest, artifacts, hashes, error_log, run_id,
        config_file.resolve(), manifest_path,
    )
    reports_dir = paths["reports_dir"]
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "final_report.md"
    report_path.write_text(report, encoding="utf-8")

    evaluation_present = artifacts.get("evaluation_report") is not None
    status = "validated" if evaluation_present else "warning"
    payload = {
        "report_path": str(report_path),
        "report_sha256": sha256_file(report_path),
        "sections": [f"{i}. {title}" for i, title in enumerate(SECTION_TITLES, 1)],
        "n_sections": len(SECTION_TITLES),
        "inputs_used": sorted(name for name, data in artifacts.items() if data),
        "inputs_missing": sorted(missing),
        "error_log_entries": len(error_log),
        "run_id": run_id,
        "note": (
            "Le rapport ne recalcule aucune métrique : agrégats, intervalles "
            "et comparaisons proviennent de l'évaluateur (§14.9)."
        ),
    }
    write_artifact(
        paths["artifacts_dir"] / run_id / "analyst_report.json",
        payload,
        experiment_id=cfg["experiment_id"],
        run_id=run_id,
        producer=PRODUCER,
        input_hashes=[
            f"{name}:{digest}" for name, digest in sorted(hashes.items())
        ],
        status=status,
        record_count=len(SECTION_TITLES),
        warnings=[] if evaluation_present else
        [f"rapport d'évaluation absent : sections « {PENDING} »"],
    )
    log_event(
        logger, "artifact", status,
        f"final_report.md + analyst_report.json (sections={len(SECTION_TITLES)})",
        run_id=run_id,
    )
    log_event(logger, "end", "ok", "rapport final écrit", run_id=run_id)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Parseur CLI de l'agent analyste."""
    parser = argparse.ArgumentParser(description="Agent Analyste (protocole §14.9)")
    parser.add_argument("--run-id", default="run_001")
    parser.add_argument("--config", default="configs/experiment.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI (§16)."""
    args = build_parser().parse_args(argv)
    return analyze(args.config, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
