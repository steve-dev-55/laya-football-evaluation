"""Agent Orchestrateur (protocole §14.1, §15, §16, §0.4).

Responsabilités (§14.1) :
- créer/valider `experiment_manifest.json` (via `read_manifest`, annexe A/B) ;
- vérifier la cohérence manifeste ↔ configuration (experiment_id,
  compétitions, saisons, cutoffs, tiers, seed, bootstrap) ;
- initialiser la base SQLite (équivalent de
  `python -m src.storage.database init`, §16) ;
- exécuter les agents DANS L'ORDRE §16 : collector → cleaner → pre_match →
  snapshot → laya → baselines → evaluator → analyst, chacun via
  `subprocess.run([sys.executable, "-m", agents.xxx, ...])` avec les mêmes
  --run-id/--config ;
- vérifier avant chaque étape la présence de l'artefact prérequis (produit
  par l'étape précédente), puis lire l'artefact produit et vérifier son
  statut §15 : `validated`/`warning` = poursuite, `blocked` = arrêt ;
- arrêter le pipeline au premier code de retour non nul (erreur bloquante)
  et journaliser ;
- écrire `logs/orchestrator.log` et un artefact de run
  `data/artifacts/{run_id}/orchestrator_run.json` (étapes, statuts,
  durées, hashes des artefacts d'entrée/sortie).

Idempotence (§0.4) — CHOIX DOCUMENTÉ :
- avec `--resume` : une étape dont l'artefact existe déjà avec le statut
  `validated` n'est PAS réexécutée (les agents sont déterministes et
  réécrivent les mêmes lignes, donc la reprise est sûre) ;
- sans `--resume` : si la base contient déjà des prédictions pour ce
  run_id, l'orchestrateur REFUSE de démarrer (aucun nettoyage destructif
  implicite) — il faut un nouveau run_id ou passer `--resume`.

Usage (§16) :
    python -m agents.orchestrator --config configs/experiment.yaml \
        [--run-id RUN_ID] [--resume]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
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
from src.storage.database import Database

AGENT_NAME = "orchestrator"
PRODUCER = "orchestrator_agent"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = "experiment_manifest.json"
PROTOCOL_VERSION = "2.0.0"

# Hypothèses pré-enregistrées (§1.3) — texte figé repris dans le manifeste
# et dans le rapport final (section 2).
PREREGISTERED_HYPOTHESES: dict[str, str] = {
    "H1_progression_temporelle": (
        "la log loss 1X2 diminue lorsque le cutoff passe de pré-match à 85 minutes"
    ),
    "H2_calibration": (
        "la calibration de Laya, mesurée par ECE et log loss, est meilleure "
        "que celle de la baseline historique à information identique"
    ),
    "H3_reaction_apres_but": (
        "après un but, la probabilité du vainqueur correspondant augmente "
        "en moyenne, toutes choses égales par ailleurs"
    ),
    "H4_robustesse": (
        "les paraphrases sémantiquement équivalentes ne modifient pas "
        "fortement la distribution prédictive"
    ),
    "H5_comptages": (
        "pour corners et cartons, la performance de Laya est comparée "
        "séparément à une baseline moyenne historique et à un modèle de "
        "comptage adapté"
    ),
}

DEFAULT_PRIMARY_METRICS: dict[str, str] = {
    "1x2": "log_loss",
    "score_bucket": "log_loss",
    "corners": "crps",
    "yellow_cards": "crps",
}


@dataclass(frozen=True)
class StepSpec:
    """Une étape du pipeline §16 : module CLI et artefact produit."""

    name: str
    module: str
    artifact: str
    location: str  # "artifacts" (data/artifacts/RUN_ID) | "evaluation"
    extra_args: tuple[str, ...] = ()


PIPELINE_STEPS: tuple[StepSpec, ...] = (
    StepSpec("collector", "agents.collector", "collector_coverage.json", "artifacts"),
    StepSpec("cleaner", "agents.cleaner", "cleaning_report.json", "artifacts"),
    StepSpec("pre_match", "agents.pre_match", "pre_match_validation.json", "artifacts"),
    StepSpec("snapshot", "agents.snapshot", "snapshot_validation.json", "artifacts"),
    StepSpec(
        "laya", "agents.laya", "laya_run.json", "artifacts",
        ("--task-version", "v1"),
    ),
    StepSpec("baselines", "agents.baselines", "baselines_run.json", "artifacts"),
    StepSpec("evaluator", "agents.evaluator", "evaluation_report.json", "evaluation"),
    StepSpec("analyst", "agents.analyst", "analyst_report.json", "artifacts"),
)


# --- Manifeste (annexe A/B) ------------------------------------------------


def resolve_manifest_path(cfg: dict[str, Any]) -> Path:
    """Chemin du manifeste : `paths.manifest` ou racine du dépôt."""
    explicit = cfg["paths"].get("manifest")
    if explicit:
        return Path(explicit)
    return REPO_ROOT / DEFAULT_MANIFEST


def build_manifest_from_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Construit un manifeste complet (annexe A) depuis la configuration.

    Chacune des 17 décisions de l'annexe B reçoit une valeur EXPLICITE
    dérivée de la configuration ou des constantes figées du protocole
    (aucune valeur implicite) ; la justification cite la provenance.
    Utilisé uniquement si `experiment_manifest.json` n'existe pas encore :
    un manifeste déjà présent fait toujours foi (pré-enregistrement).
    """
    laya = cfg["laya"]
    bootstrap = cfg["bootstrap"]
    _thresholds = cfg["thresholds"]  # figés, consultés par les agents amont
    _repetition = cfg["repetition_audit"]
    primary_metrics = cfg.get("primary_metrics") or dict(DEFAULT_PRIMARY_METRICS)
    return {
        "experiment_id": cfg["experiment_id"],
        "protocol_version": PROTOCOL_VERSION,
        "competitions": list(cfg["competitions"]),
        "seasons": list(cfg["seasons"]),
        "primary_source": (
            "LOCAL_FILE (à remplacer : StatsBomb/API-Football/FBref à figer "
            "avant collecte)"
        ),
        "secondary_source": "à figer avant la collecte",
        "cutoffs_seconds": [int(c) for c in cfg["cutoffs_seconds"]],
        "information_tiers": list(cfg["information_tiers"]),
        "score_bucket_cap": 3,
        "corners_tail": "21+",
        "yellow_cards_tail": "13+",
        "model": {
            "package": "laya-mock" if laya["client"] == "mock" else "laya",
            "version": laya["model_version"],
            "checkpoint": "PINNED_CHECKPOINT",
            "router_mode": "multilingual",
        },
        "bootstrap_replicates": int(bootstrap["replicates"]),
        "alpha": float(bootstrap["alpha"]),
        "seed": int(cfg["seed"]),
        "primary_metrics": primary_metrics,
        "hypotheses": dict(PREREGISTERED_HYPOTHESES),
        "decisions": _decisions_from_config(cfg),
    }


def _decisions_from_config(cfg: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Les 17 décisions de l'annexe B, valeurs explicites + justification."""
    thresholds = cfg["thresholds"]
    bootstrap = cfg["bootstrap"]
    repetition = cfg["repetition_audit"]
    split = cfg["split"]
    value = "value"
    why = "justification"
    return {
        "primary_and_secondary_source": {
            value: (
                "principale = LOCAL_FILE (à remplacer : StatsBomb/API-Football/"
                "FBref à figer avant collecte) ; secondaire = à figer"
            ),
            why: "source de démonstration locale ; à figer avant tout test final",
        },
        "seasons_and_competitions": {
            value: (
                f"saisons {', '.join(map(str, cfg['seasons']))} ; compétitions "
                f"{', '.join(map(str, cfg['competitions']))}"
            ),
            why: "périmètre §3.1 repris de configs/experiment.yaml",
        },
        "timezone_and_kickoff": {
            value: (
                "tous les horodatages en UTC ISO-8601 « ...Z » ; kickoff = "
                "timestamp officiel du coup d'envoi fourni par la source"
            ),
            why: "référence temporelle unique (§5.1)",
        },
        "statistics_availability": {
            value: (
                "événements publiés 30 s après l'instant de jeu, statistiques "
                "45 s après, match terminé disponible 96 min après le coup "
                "d'envoi"
            ),
            why: "délais de publication figés (agents/cleaner.py, §3.2)",
        },
        "second_yellow_card_convention": {
            value: (
                "le deuxième carton jaune est compté comme jaune si "
                "identifiable, sinon analyse de sensibilité"
            ),
            why: "convention §3.5/annexe B",
        },
        "same_timestamp_events": {
            value: (
                "ordre source (elapsed_seconds, source_event_id) conservé + "
                "snapshot agrégé de contrôle si plusieurs événements partagent "
                "le même instant"
            ),
            why: "agents/cleaner.py + agents/snapshot.py (§6.2)",
        },
        "tail_thresholds": {
            value: "corners 21+ ; cartons jaunes 13+",
            why: "queues censurées figées (src/core/tasks.py, §8.3, §8.4)",
        },
        "tiers_definition": {
            value: (
                "A = bloc pré-match seul ; B = A + score, cartons, corners, "
                "événements ; C = B + tirs, tirs cadrés, possession, xG (§6.3)"
            ),
            why: "niveaux d'information §6.3",
        },
        "question_wording_and_order": {
            value: (
                "QUESTIONS_V1 figé en version v1 ; ordre des critères = "
                "listes canoniques SCORE_BUCKETS / CORNER_LEVELS / "
                "YELLOW_LEVELS"
            ),
            why: "wording versionné §8.5 (src/core/tasks.py)",
        },
        "laya_checkpoint": {
            value: "PINNED_CHECKPOINT (à remplacer à l'exécution réelle)",
            why: "checkpoint du client mock ; le SDK réel sera figé (§2.1)",
        },
        "repetition_count": {
            value: (
                f"audit de répétition k = {int(repetition['k'])} sur au moins "
                f"{float(repetition['min_share']):.0%} des snapshots, échantillon "
                "déterministe stratifié par tier (§9.2)"
            ),
            why: "config repetition_audit (§9.2)",
        },
        "temporal_split": {
            value: (
                f"entraînement = {', '.join(map(str, split['train_seasons']))} ; "
                f"test final = {', '.join(map(str, split['test_seasons']))} ; "
                "matchs d'un même jour dans le même bloc"
            ),
            why: "découpage temporel §11.1, jamais de split aléatoire",
        },
        "primary_metrics": {
            value: (
                "1x2 = log_loss ; score_bucket = log_loss ; corners = crps ; "
                "yellow_cards = crps"
            ),
            why: "métrique principale par cible (§12, §11.3)",
        },
        "bootstrap_replicates": {
            value: (
                f"{int(bootstrap['replicates'])} réplications bootstrap "
                f"groupées par match, alpha = {float(bootstrap['alpha'])}"
            ),
            why: "plan statistique §12.5 / config bootstrap",
        },
        "holm_bonferroni_families": {
            value: (
                "une famille par cible (4 familles : 1x2, score_bucket, "
                "corners, yellow_cards), référence = laya"
            ),
            why: "agents/evaluator.py COMPARISON_FAMILIES (§12.5)",
        },
        "blocking_and_resume_criteria": {
            value: (
                "blocage si > "
                f"{float(thresholds['max_snapshot_leakage_rate']):.0%} de "
                "snapshots fuyants, > "
                f"{float(thresholds['max_stratum_missing_rate']):.0%} de "
                "matchs manquants dans une strate, > "
                f"{float(thresholds['max_invalid_response_rate']):.0%} de "
                "réponses invalides ; reprise = relance idempotente de "
                "l'étape (--resume, §0.4)"
            ),
            why: "seuils §11.4 / config thresholds",
        },
        "missing_data_rule": {
            value: "null, aucune imputation (§7.2)",
            why: "les données manquantes sont rapportées, jamais imputées",
        },
    }


def ensure_manifest(
    cfg: dict[str, Any], manifest_path: Path
) -> dict[str, Any]:
    """Valide le manifeste ; le crée depuis la config s'il est absent.

    Returns:
        Le manifeste validé (17 décisions, annexe A/B).

    Raises:
        ValueError: manifeste présent mais invalide (read_manifest).
        OSError: problème d'écriture.
    """
    if manifest_path.is_file():
        return read_manifest(manifest_path)
    manifest = build_manifest_from_config(cfg)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, manifest_path)
    return read_manifest(manifest_path)


def check_coherence(manifest: dict[str, Any], cfg: dict[str, Any]) -> list[str]:
    """Vérifie la cohérence manifeste ↔ configuration (§14.1).

    Contrôles : experiment_id, compétitions, saisons, cutoffs, tiers,
    seed, réplications bootstrap, alpha.
    """
    problems: list[str] = []
    if str(manifest.get("experiment_id")) != str(cfg["experiment_id"]):
        problems.append(
            f"experiment_id : manifeste={manifest.get('experiment_id')!r} "
            f"config={cfg['experiment_id']!r}"
        )
    for key in ("competitions", "seasons", "information_tiers"):
        manifest_values = [str(v) for v in manifest.get(key) or []]
        config_values = [str(v) for v in cfg.get(key) or []]
        if manifest_values != config_values:
            problems.append(
                f"{key} : manifeste={manifest_values} config={config_values}"
            )
    manifest_cutoffs = sorted(int(c) for c in manifest.get("cutoffs_seconds") or [])
    config_cutoffs = sorted(int(c) for c in cfg["cutoffs_seconds"])
    if manifest_cutoffs != config_cutoffs:
        problems.append(
            f"cutoffs_seconds : manifeste={manifest_cutoffs} config={config_cutoffs}"
        )
    if int(manifest.get("seed", -1)) != int(cfg["seed"]):
        problems.append(
            f"seed : manifeste={manifest.get('seed')!r} config={cfg['seed']!r}"
        )
    if int(manifest.get("bootstrap_replicates", -1)) != int(cfg["bootstrap"]["replicates"]):
        problems.append(
            f"bootstrap_replicates : manifeste={manifest.get('bootstrap_replicates')!r} "
            f"config={cfg['bootstrap']['replicates']!r}"
        )
    if abs(float(manifest.get("alpha", -1)) - float(cfg["bootstrap"]["alpha"])) > 1e-12:
        problems.append(
            f"alpha : manifeste={manifest.get('alpha')!r} "
            f"config={cfg['bootstrap']['alpha']!r}"
        )
    return problems


# --- Exécution du pipeline (§16) --------------------------------------------


def _artifact_path(
    paths: dict[str, Path], run_id: str, step: StepSpec
) -> Path:
    """Chemin de l'artefact produit par une étape."""
    base = paths["evaluation_dir"] if step.location == "evaluation" else paths["artifacts_dir"]
    return base / run_id / step.artifact


def _subprocess_env() -> dict[str, str]:
    """Environnement des sous-processus : PYTHONPATH incluant la racine."""
    env = dict(os.environ)
    parts = [str(REPO_ROOT)]
    parts += [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def _step_summary(
    step: StepSpec,
    command: list[str],
    status: str,
    duration_seconds: float,
    artifact: Path,
    artifact_data: dict[str, Any] | None,
    detail: str = "",
) -> dict[str, Any]:
    """Entrée de résumé pour une étape exécutée."""
    return {
        "name": step.name,
        "module": step.module,
        "command": " ".join(command),
        "status": status,
        "detail": detail,
        "duration_seconds": round(duration_seconds, 3),
        "artifact": str(artifact),
        "artifact_exists": artifact.is_file(),
        "artifact_status": (artifact_data or {}).get("status"),
        "artifact_output_hash": (artifact_data or {}).get("output_hash"),
        "artifact_sha256": (
            sha256_file(artifact) if artifact.is_file() else None
        ),
    }


def _write_run_artifact(
    cfg: dict[str, Any],
    paths: dict[str, Path],
    run_id: str,
    steps: list[dict[str, Any]],
    status: str,
    errors: list[str],
    config_path: Path,
    manifest_path: Path,
    started_at: str,
) -> Path:
    """Écrit l'artefact de run (résumé : étapes, statuts, durées, hashes)."""
    payload = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": now_utc(),
        "config": str(config_path),
        "manifest": str(manifest_path),
        "steps": steps,
        "totals": {
            "n_steps": len(PIPELINE_STEPS),
            "n_executed": sum(1 for s in steps if s["status"] != "skipped"),
            "n_skipped": sum(1 for s in steps if s["status"] == "skipped"),
            "duration_seconds": round(
                sum(float(s["duration_seconds"]) for s in steps), 3
            ),
        },
        "pipeline_order": [s.name for s in PIPELINE_STEPS],
    }
    artifact_path = paths["artifacts_dir"] / run_id / "orchestrator_run.json"
    write_artifact(
        artifact_path,
        payload,
        experiment_id=cfg["experiment_id"],
        run_id=run_id,
        producer=PRODUCER,
        input_hashes=[
            "config:" + sha256_file(config_path),
            "manifest:" + sha256_file(manifest_path),
        ],
        status=status,
        record_count=len(steps),
        errors=errors,
    )
    return artifact_path


def run_pipeline(
    config_path: str | Path, run_id: str, *, resume: bool = False
) -> int:
    """Exécute le pipeline complet §16 ; renvoie 0 si tout est validé."""
    config_file = Path(config_path)
    cfg = load_config(config_file)
    paths = config_paths(cfg)
    logger = setup_logging(AGENT_NAME, paths["logs_dir"])
    started_at = now_utc()
    log_event(
        logger, "start", "ok",
        f"run_id={run_id} resume={resume} config={config_file}",
        run_id=run_id,
    )

    # 1. Manifeste : création éventuelle puis validation stricte (annexe A/B).
    manifest_path = resolve_manifest_path(cfg)
    try:
        manifest = ensure_manifest(cfg, manifest_path)
    except (ValueError, OSError) as exc:
        message = f"manifeste invalide ou non créable : {exc}"
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "manifest", message)
        log_event(logger, "manifest", "error", message, run_id=run_id)
        _write_run_artifact(
            cfg, paths, run_id, [], "blocked", [message],
            config_file, manifest_path, started_at,
        )
        return 1
    log_event(
        logger, "manifest", "ok",
        f"manifeste validé : {manifest['experiment_id']} "
        f"({len(manifest['decisions'])} décisions)",
        run_id=run_id,
    )

    # 2. Cohérence manifeste ↔ configuration.
    problems = check_coherence(manifest, cfg)
    if problems:
        message = "incohérence manifeste/configuration : " + " ; ".join(problems)
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "coherence", message)
        log_event(logger, "coherence", "error", message, run_id=run_id)
        _write_run_artifact(
            cfg, paths, run_id, [], "blocked", problems,
            config_file, manifest_path, started_at,
        )
        return 1
    log_event(logger, "coherence", "ok", "manifeste et configuration cohérents",
              run_id=run_id)

    # 3. Base de données (§16 : python -m src.storage.database init).
    db = Database(paths["db"])
    db.init()
    n_existing = db.query(
        "SELECT COUNT(*) AS n FROM laya_predictions WHERE run_id = ?", (run_id,)
    )[0]["n"]
    db.close()
    if n_existing and not resume:
        message = (
            f"le run_id {run_id!r} contient déjà {n_existing} prédictions ; "
            "utilisez un nouveau run_id ou --resume (aucun nettoyage implicite)"
        )
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "run_id", message)
        log_event(logger, "run_id", "error", message, run_id=run_id)
        _write_run_artifact(
            cfg, paths, run_id, [], "blocked", [message],
            config_file, manifest_path, started_at,
        )
        return 1

    # 4. Étapes §16, dans l'ordre, sous-processus par sous-processus.
    steps: list[dict[str, Any]] = []
    previous: StepSpec | None = None
    for step in PIPELINE_STEPS:
        artifact_file = _artifact_path(paths, run_id, step)

        # --resume : passer l'étape si son artefact est déjà validé (§0.4).
        if resume and artifact_file.is_file():
            try:
                existing = read_artifact(artifact_file)
            except (ValueError, json.JSONDecodeError):
                existing = None
            if existing and existing.get("status") == "validated":
                log_event(
                    logger, step.name, "skipped",
                    f"artefact déjà validé : {artifact_file.name}",
                    run_id=run_id,
                )
                steps.append(
                    _step_summary(
                        step, [], "skipped", 0.0, artifact_file, existing,
                        "reprise : artefact validé conservé",
                    )
                )
                previous = step
                continue

        # Précondition : artefact de l'étape précédente (manifeste pour la 1re).
        prerequisite = (
            manifest_path if previous is None
            else _artifact_path(paths, run_id, previous)
        )
        if not prerequisite.is_file():
            message = f"prérequis manquant pour {step.name} : {prerequisite}"
            log_error(paths["logs_dir"], AGENT_NAME, run_id, step.name, message)
            log_event(logger, step.name, "blocked", message, run_id=run_id)
            steps.append(_step_summary(step, [], "blocked", 0.0, artifact_file, None,
                                       message))
            _write_run_artifact(
                cfg, paths, run_id, steps, "blocked", [message],
                config_file, manifest_path, started_at,
            )
            return 1

        command = [
            sys.executable, "-m", step.module,
            "--run-id", run_id,
            "--config", str(config_file.resolve()),
        ]
        command.extend(step.extra_args)
        log_event(logger, step.name, "start", " ".join(command), run_id=run_id)
        t0 = time.monotonic()
        process = subprocess.run(command, cwd=REPO_ROOT, env=_subprocess_env())
        duration = time.monotonic() - t0

        if process.returncode != 0:
            message = (
                f"{step.name} a échoué (code de retour {process.returncode})"
            )
            log_error(paths["logs_dir"], AGENT_NAME, run_id, step.name, message)
            log_event(logger, step.name, "blocked", message, run_id=run_id)
            steps.append(_step_summary(step, command, "blocked", duration,
                                       artifact_file, None, message))
            _write_run_artifact(
                cfg, paths, run_id, steps, "blocked", [message],
                config_file, manifest_path, started_at,
            )
            return 1

        # Postcondition : artefact présent, lisible, statut §15.
        if not artifact_file.is_file():
            message = f"artefact absent après {step.name} : {artifact_file}"
            log_error(paths["logs_dir"], AGENT_NAME, run_id, step.name, message)
            log_event(logger, step.name, "blocked", message, run_id=run_id)
            steps.append(_step_summary(step, command, "blocked", duration,
                                       artifact_file, None, message))
            _write_run_artifact(
                cfg, paths, run_id, steps, "blocked", [message],
                config_file, manifest_path, started_at,
            )
            return 1
        try:
            artifact = read_artifact(artifact_file)
        except (ValueError, json.JSONDecodeError) as exc:
            message = f"artefact illisible après {step.name} : {exc}"
            log_error(paths["logs_dir"], AGENT_NAME, run_id, step.name, message)
            log_event(logger, step.name, "blocked", message, run_id=run_id)
            steps.append(_step_summary(step, command, "blocked", duration,
                                       artifact_file, None, message))
            _write_run_artifact(
                cfg, paths, run_id, steps, "blocked", [message],
                config_file, manifest_path, started_at,
            )
            return 1

        status = artifact.get("status")
        steps.append(_step_summary(step, command, str(status), duration,
                                   artifact_file, artifact))
        log_event(
            logger, step.name, str(status),
            f"durée={duration:.1f}s artefact={artifact_file.name}",
            run_id=run_id,
        )
        if status == "blocked":
            message = f"{step.name} bloqué (statut §15 blocked)"
            log_error(paths["logs_dir"], AGENT_NAME, run_id, step.name, message)
            _write_run_artifact(
                cfg, paths, run_id, steps, "blocked", [message],
                config_file, manifest_path, started_at,
            )
            return 1
        previous = step

    # 5. Résumé final : artefact de run (statuts, durées, hashes).
    statuses = [str(s["status"]) for s in steps]
    run_status = (
        "blocked" if "blocked" in statuses
        else "warning" if "warning" in statuses
        else "validated"
    )
    run_artifact = _write_run_artifact(
        cfg, paths, run_id, steps, run_status, [],
        config_file, manifest_path, started_at,
    )
    log_event(
        logger, "end", "ok" if run_status != "blocked" else "blocked",
        f"pipeline terminé statut={run_status} artefact={run_artifact.name}",
        run_id=run_id,
    )
    return 0 if run_status != "blocked" else 1


def build_parser() -> argparse.ArgumentParser:
    """Parseur CLI de l'orchestrateur."""
    parser = argparse.ArgumentParser(description="Agent Orchestrateur (protocole §14.1)")
    parser.add_argument(
        "--config", default="configs/experiment.yaml",
        help="chemin du fichier de configuration YAML",
    )
    parser.add_argument(
        "--run-id", default=None,
        help="identifiant du run (défaut : run_<UTC>)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="passer les étapes dont l'artefact existe déjà avec statut validated",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI (§16)."""
    args = build_parser().parse_args(argv)
    run_id = args.run_id or (
        "run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    return run_pipeline(args.config, run_id, resume=args.resume)


if __name__ == "__main__":
    raise SystemExit(main())
