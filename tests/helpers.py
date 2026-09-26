"""Aides de test : environnement synthétique isolé (protocole §0.2, §21).

AUCUNE donnée réelle : les documents bruts sont produits par
`scripts/generate_synthetic_data.py` (module importé par chemin), avec un
seed fixe — deux exécutions donnent des octets identiques.

`build_environment(root)` construit dans `root` (tmp_path) :
- `raw/` : documents `data/raw` synthétiques (2 compétitions × 2 saisons) ;
- `configs/experiment.yaml` : configuration de test avec TOUS les chemins
  redirigés vers `root` (aucune pollution du dépôt) ;
- `experiment_manifest.json` : manifeste complet (17 décisions, annexe B),
  construit puis validé via le code de production ;
- `db/experiment.db` : base SQLite initialisée.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import yaml

from agents.common import load_config, read_manifest
from agents.orchestrator import build_manifest_from_config
from src.storage.database import Database

REPO_ROOT = Path(__file__).resolve().parents[1]

TEST_COMPETITIONS = ["EPL", "LaLiga"]
TEST_SEASONS = ["2021-2022", "2022-2023"]
TRAIN_SEASONS = ["2021-2022"]
TEST_SPLIT_SEASONS = ["2022-2023"]
TEST_SEED = 20260925
MATCHES_PER_SEASON = 8


def _load_generator() -> Any:
    """Charge scripts/generate_synthetic_data.py comme module (sans package)."""
    spec = importlib.util.spec_from_file_location(
        "laya_synth", REPO_ROOT / "scripts" / "generate_synthetic_data.py"
    )
    if spec is None or spec.loader is None:  # pragma: no cover — garde-fou
        raise RuntimeError("impossible de charger le générateur synthétique")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SYNTH = _load_generator()


def generate_test_raw(raw_dir: Path) -> list[Path]:
    """Écrit les documents bruts synthétiques (2 compétitions × 2 saisons)."""
    return SYNTH.generate_dataset(
        raw_dir,
        competitions=TEST_COMPETITIONS,
        seasons=TEST_SEASONS,
        matches_per_season=MATCHES_PER_SEASON,
        seed=TEST_SEED,
    )


def write_test_config(root: Path, raw_dir: Path) -> Path:
    """Écrit la configuration YAML de test (chemins absolus vers `root`)."""
    config: dict[str, Any] = {
        "experiment_id": "laya-football-test",
        "competitions": TEST_COMPETITIONS,
        "seasons": TEST_SEASONS,
        "cutoffs_seconds": [0, 900, 1800, 2700, 3600, 4500, 5100],
        "information_tiers": ["A", "B", "C"],
        "seed": TEST_SEED,
        "split": {
            "train_seasons": TRAIN_SEASONS,
            "test_seasons": TEST_SPLIT_SEASONS,
        },
        "thresholds": {
            "max_snapshot_leakage_rate": 0.05,
            "max_stratum_missing_rate": 0.10,
            "max_invalid_response_rate": 0.05,
        },
        "bootstrap": {"replicates": 2000, "alpha": 0.05, "ece_bins": 15},
        "primary_metrics": {
            "1x2": "log_loss",
            "score_bucket": "log_loss",
            "corners": "crps",
            "yellow_cards": "crps",
        },
        "laya": {
            "client": "mock",
            "task_version": "v1",
            "model_version": "laya-mock-1.0.0",
        },
        "repetition_audit": {"k": 5, "min_share": 0.10},
        "source": {
            "adapter": "local_file",
            "license": "CC0-1.0 (données synthétiques de test)",
        },
        "paths": {
            "db": str(root / "db" / "experiment.db"),
            "raw_dir": str(raw_dir),
            "canonical_dir": str(root / "canonical"),
            "artifacts_dir": str(root / "artifacts"),
            "predictions_dir": str(root / "predictions"),
            "evaluation_dir": str(root / "evaluation"),
            "reports_dir": str(root / "reports"),
            "logs_dir": str(root / "logs"),
            "manifest": str(root / "experiment_manifest.json"),
        },
    }
    config_path = root / "configs" / "experiment.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return config_path


def write_test_manifest(config_path: Path) -> Path:
    """Construit + valide le manifeste de test (17 décisions, annexe B)."""
    cfg = load_config(config_path)
    manifest_path = Path(cfg["paths"]["manifest"])
    manifest = build_manifest_from_config(cfg)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    read_manifest(manifest_path)  # validation stricte (17 décisions exigées)
    return manifest_path


def build_environment(root: Path) -> dict[str, Path]:
    """Environnement complet et isolé : raw + config + manifeste + base."""
    root.mkdir(parents=True, exist_ok=True)
    raw_dir = root / "raw"
    generate_test_raw(raw_dir)
    config_path = write_test_config(root, raw_dir)
    manifest_path = write_test_manifest(config_path)
    db_path = root / "db" / "experiment.db"
    database = Database(db_path)
    database.init()
    database.close()
    return {
        "root": root,
        "raw_dir": raw_dir,
        "config": config_path,
        "manifest": manifest_path,
        "db": db_path,
    }
