"""Utilitaires communs aux agents (protocole §15, §16, §17, annexe A/B).

Fonctions fournies :
- horodatage UTC ISO-8601 canonique et arithmétique temporelle ;
- chargement/validation de la configuration `configs/experiment.yaml` ;
- journalisation au format §15 (timestamp, agent, run_id, entity_id, action,
  status, message court) vers `logs/{agent}.log` et `logs/errors.log` ;
- écriture d'artefacts JSON versionnés avec en-tête §15 et hash de sortie ;
- insertion groupée idempotente (complément de `src.storage.Database`,
  jamais une modification de `src/`).

Aucune donnée réelle, aucune clé API : ce module ne fait aucune E/S réseau.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from src.core.canonical import canonical_json
from src.core.ids import content_hash

# --- Constantes du contrat d'artefact (§15) ---------------------------------

ARTIFACT_SCHEMA_VERSION = "1.0.0"
"""Version du schéma d'en-tête des artefacts (§15)."""

REQUIRED_ARTIFACT_KEYS: tuple[str, ...] = (
    "schema_version",
    "experiment_id",
    "run_id",
    "producer",
    "created_at",
    "input_hashes",
    "output_hash",
    "status",
    "record_count",
    "warnings",
    "errors",
)

VALID_STATUSES = ("validated", "warning", "blocked")

# Clés primaires canoniques (miroir du schéma §4.2 — utilisé par bulk_upsert).
_PRIMARY_KEYS: dict[str, str] = {
    "matches": "match_id",
    "match_events": "event_id",
    "match_statistics": "stat_id",
    "pre_match_context": "pre_match_id",
    "match_snapshots": "snapshot_id",
    "laya_predictions": "prediction_id",
    "evaluation": "evaluation_id",
}

# Format ISO-8601 UTC commun à toute l'étude (décision annexe B).
ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"

# Défauts des chemins (relatifs à la racine du dépôt, §4.1).
DEFAULT_PATHS: dict[str, str] = {
    "db": "data/laya_experiment.db",
    "raw_dir": "data/raw",
    "canonical_dir": "data/canonical",
    "artifacts_dir": "data/artifacts",
    "predictions_dir": "data/predictions",
    "evaluation_dir": "data/evaluation",
    "reports_dir": "reports",
    "logs_dir": "logs",
}

REQUIRED_CONFIG_KEYS: tuple[str, ...] = (
    "experiment_id",
    "competitions",
    "seasons",
    "cutoffs_seconds",
    "information_tiers",
    "seed",
    "split",
    "thresholds",
    "bootstrap",
)


class ConfigError(ValueError):
    """Erreur de configuration (fichier absent, clés manquantes)."""


# --- Temps (timezone UTC, décision figée annexe B) --------------------------


def now_utc() -> str:
    """Horodatage courant au format ISO-8601 UTC « ...Z »."""
    return datetime.now(timezone.utc).strftime(ISO_FMT)


def parse_iso(timestamp: str) -> datetime:
    """Parse un horodatage ISO-8601 UTC « ...Z » en datetime conscient UTC."""
    return datetime.strptime(timestamp, ISO_FMT).replace(tzinfo=timezone.utc)


def add_seconds(timestamp: str, seconds: int) -> str:
    """Ajoute un délai en secondes à un horodatage ISO UTC canonique."""
    return (parse_iso(timestamp) + timedelta(seconds=seconds)).strftime(ISO_FMT)


# --- Noms d'équipes canoniques (§4.3) ---------------------------------------


def canonical_team_name(name: str) -> str:
    """Normalise un nom d'équipe pour l'identifiant déterministe (§4.3).

    Règle : espaces extrêmes supprimés, espaces internes réduites à une,
    casse pliée. La règle est figée : tout changement casse les identifiants.
    """
    return " ".join(name.strip().casefold().split())


# --- Hashes -----------------------------------------------------------------


def sha256_text(text: str) -> str:
    """Hash SHA-256 d'une chaîne UTF-8 (identifiants dérivés)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash SHA-256 du contenu binaire d'un fichier (données brutes §3.2)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- JSON sûr (pas de NaN/Inf dans un artefact canonique) -------------------


def json_safe(obj: Any) -> Any:
    """Remplace récursivement les flottants non finis par `None` (§7.1)."""
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


# --- Configuration (configs/experiment.yaml) --------------------------------


def load_config(path: str | Path) -> dict[str, Any]:
    """Charge et valide la configuration de l'expérience.

    Raises:
        ConfigError: fichier absent, YAML invalide ou clés obligatoires
            manquantes (annexe B : aucune valeur par défaut implicite pour
            les décisions figées).
    """
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"configuration introuvable : {p}")
    try:
        cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML invalide dans {p} : {exc}") from exc
    if not isinstance(cfg, dict):
        raise ConfigError(f"la configuration {p} n'est pas un mapping")
    missing = [k for k in REQUIRED_CONFIG_KEYS if k not in cfg]
    if missing:
        raise ConfigError(f"clés de configuration manquantes : {missing}")
    paths = dict(DEFAULT_PATHS)
    paths.update(cfg.get("paths") or {})
    cfg["paths"] = paths
    for key, default in (
        ("laya", {"client": "mock", "task_version": "v1",
                  "model_version": "laya-mock-1.0.0"}),
        ("repetition_audit", {"k": 5, "min_share": 0.10}),
        ("source", {"adapter": "local_file", "license": "unknown"}),
    ):
        merged = dict(default)
        merged.update(cfg.get(key) or {})
        cfg[key] = merged
    return cfg


def config_paths(cfg: Mapping[str, Any]) -> dict[str, Path]:
    """Résout les chemins de la configuration en chemins absolus/Path."""
    return {k: Path(v) for k, v in cfg["paths"].items()}


def resolve_split(
    cfg: Mapping[str, Any], matches: list[dict[str, Any]]
) -> tuple[set[str], set[str]]:
    """Résout le découpage train/test en (train_match_ids, test_match_ids).

    Deux modes (clé `split.mode`) :

    - ``by_season`` (défaut, comportement historique) : matchs des saisons
      listées dans `split.train_seasons` / `split.test_seasons`.
    - ``chronological_per_competition`` (AMENDEMENT A2, figé avant
      enregistrement OSF — experiment_manifest.json) : chaque compétition est
      coupée chronologiquement en deux moitiés (entraînement = première
      moitié, test final = seconde) ; les matchs d'un même jour restent dans
      le même bloc. Règle de frontière : les jours sont parcourus dans
      l'ordre et inclus au bloc entraînement jusqu'au premier jour où le
      cumul atteint ``train_fraction`` (défaut 0,5) des matchs de la
      compétition, ce jour frontière entier inclus à l'entraînement.
    """
    split = cfg["split"]
    mode = split.get("mode", "by_season")
    if mode == "by_season":
        train_seasons = set(split["train_seasons"])
        test_seasons = set(split["test_seasons"])
        train = {m["match_id"] for m in matches if m["season"] in train_seasons}
        test = {m["match_id"] for m in matches if m["season"] in test_seasons}
        return train, test
    if mode == "chronological_per_competition":
        fraction = float(split.get("train_fraction", 0.5))
        by_comp: dict[str, list[dict[str, Any]]] = {}
        for m in matches:
            by_comp.setdefault(m["competition_id"], []).append(m)
        train: set[str] = set()
        test: set[str] = set()
        for comp_matches in by_comp.values():
            ordered = sorted(
                comp_matches,
                key=lambda m: (m["kickoff_timestamp"], m["match_id"]),
            )
            total = len(ordered)
            target = fraction * total
            train_days: set[str] = set()
            for idx, m in enumerate(ordered):
                if idx < target:
                    train_days.add(m["date_utc"])
            for m in ordered:
                if m["date_utc"] in train_days:
                    train.add(m["match_id"])
                else:
                    test.add(m["match_id"])
        return train, test
    raise ConfigError(f"mode de découpage inconnu : {mode!r}")


# --- Journalisation (§15) ---------------------------------------------------


def setup_logging(agent: str, logs_dir: str | Path) -> logging.Logger:
    """Configure le journal d'un agent : `logs/{agent}.log` en lignes JSON.

    Chaque ligne contient timestamp, agent, run_id, entity_id, action,
    status et un message court (§15). Le handler est réinitialisé à chaque
    appel pour rester idempotent lors des relances dans le même processus.
    """
    logs = Path(logs_dir)
    logs.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"agents.{agent}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()
    handler = logging.FileHandler(logs / f"{agent}.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%H:%M:%S"))
    logger.addHandler(console)
    return logger


def log_event(
    logger: logging.Logger,
    action: str,
    status: str,
    message: str,
    *,
    run_id: str = "",
    entity_id: str = "",
) -> None:
    """Émet une ligne de journal au format §15."""
    agent = logger.name.rsplit(".", maxsplit=1)[-1]
    record = {
        "timestamp": now_utc(),
        "agent": agent,
        "run_id": run_id,
        "entity_id": entity_id,
        "action": action,
        "status": status,
        "message": message,
    }
    logger.info(canonical_json(record))


def log_error(
    logs_dir: str | Path,
    agent: str,
    run_id: str,
    action: str,
    message: str,
    *,
    entity_id: str = "",
) -> None:
    """Ajoute une entrée au journal commun `logs/errors.log` (§15)."""
    path = Path(logs_dir) / "errors.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": now_utc(),
        "agent": agent,
        "run_id": run_id,
        "entity_id": entity_id,
        "action": action,
        "status": "error",
        "message": message,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(canonical_json(record) + "\n")


# --- Artefacts (§15) ---------------------------------------------------------


def write_artifact(
    path: str | Path,
    payload: Any,
    *,
    experiment_id: str,
    run_id: str,
    producer: str,
    input_hashes: Sequence[str],
    status: str,
    record_count: int = 0,
    warnings: Sequence[str] | None = None,
    errors: Sequence[str] | None = None,
) -> str:
    """Écrit un artefact JSON : en-tête §15 + charge utile, atomiquement.

    Args:
        path: chemin du fichier artefact.
        payload: charge utile (données de l'agent), sérialisable.
        experiment_id: identifiant de l'expérience (manifeste).
        run_id: identifiant du run.
        producer: nom du producteur (ex. « snapshot_agent »).
        input_hashes: hashes SHA-256 des artefacts/fichiers d'entrée.
        status: `validated`, `warning` ou `blocked` (§16).
        record_count: nombre d'enregistrements produits.
        warnings: avertissements non bloquants.
        errors: erreurs rencontrées.

    Returns:
        Le hash de sortie `sha256:...` (hash canonique de la charge utile).
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"statut d'artefact inconnu : {status!r}")
    normalized_hashes = [
        h if h.startswith("sha256:") else f"sha256:{h}" for h in input_hashes
    ]
    safe_payload = json_safe(payload)
    output_hash = f"sha256:{content_hash(safe_payload)}"
    artifact = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "producer": producer,
        "created_at": now_utc(),
        "input_hashes": normalized_hashes,
        "output_hash": output_hash,
        "status": status,
        "record_count": int(record_count),
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "payload": safe_payload,
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, target)
    return output_hash


def read_artifact(path: str | Path) -> dict[str, Any]:
    """Lit un artefact et valide la présence de l'en-tête §15.

    Raises:
        ValueError: fichier absent ou en-tête incomplet.
    """
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"artefact introuvable : {p}")
    artifact = json.loads(p.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_ARTIFACT_KEYS if k not in artifact]
    if missing:
        raise ValueError(f"en-tête §15 incomplet dans {p} : manquant {missing}")
    return artifact


def read_manifest(path: str | Path) -> dict[str, Any]:
    """Lit `experiment_manifest.json` (annexe A) et valide ses clés minimales."""
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"manifeste introuvable : {p}")
    manifest = json.loads(p.read_text(encoding="utf-8"))
    required = (
        "experiment_id",
        "protocol_version",
        "competitions",
        "seasons",
        "cutoffs_seconds",
        "information_tiers",
        "seed",
        "bootstrap_replicates",
        "alpha",
        "primary_metrics",
        "decisions",
    )
    missing = [k for k in required if k not in manifest]
    if missing:
        raise ValueError(f"manifeste incomplet : clés manquantes {missing}")
    n_decisions = len(manifest["decisions"])
    if n_decisions != 17:
        raise ValueError(
            f"l'annexe B exige 17 décisions figées, manifeste en contient {n_decisions}"
        )
    return manifest


# --- Insertions groupées idempotentes (complément de src.storage) ------------


def bulk_upsert(
    db: Any,
    table: str,
    records: Sequence[Mapping[str, Any]],
    *,
    on_conflict: str = "update",
) -> int:
    """Insère un lot d'enregistrements de façon idempotente (§0.4).

    Complément de `src.storage.Database.upsert` : un seul commit pour tout le
    lot, avec au choix « DO UPDATE » (les relances réécrivent les mêmes
    valeurs déterministes) ou « OR IGNORE » (les lignes validées ne sont
    jamais modifiées, p.ex. `evaluation`).

    Raises:
        ValueError: table inconnue, lot vide ou enregistrements hétérogènes.
    """
    if table not in _PRIMARY_KEYS:
        raise ValueError(f"table inconnue : {table}")
    if not records:
        return 0
    pk = _PRIMARY_KEYS[table]
    cols = sorted(records[0])
    if any(sorted(r) != cols for r in records):
        raise ValueError(f"enregistrements hétérogènes pour {table}")
    rows = [tuple(r[c] for c in cols) for r in records]
    placeholders = ", ".join("?" for _ in cols)
    if on_conflict == "update":
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != pk)
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT({pk}) DO UPDATE SET {updates}"
        )
    elif on_conflict == "ignore":
        sql = f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    else:
        raise ValueError(f"mode on_conflict inconnu : {on_conflict!r}")
    db.executemany(sql, rows)
    return len(rows)


def iter_jsonl(path: str | Path) -> Iterable[dict[str, Any]]:
    """Itère sur les lignes JSON d'un fichier `.jsonl`."""
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)
