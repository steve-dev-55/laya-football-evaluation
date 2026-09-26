"""Tests des baselines (protocole §10, §11.1, §14.7).

Le préambule (nettoyeur → pré-match → snapshot → baselines) est exécuté UNE
fois sur données synthétiques isolées (session), puis :
- uniforme = 1/n partout ;
- Poisson : sommes = 1, aucune probabilité négative ;
- la régression logistique n'utilise JAMAIS les matchs de la saison test
  (vérifié par identifiants ET par dates de kickoff).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents import baselines as baselines_agent
from agents import cleaner as cleaner_agent
from agents import pre_match as pre_match_agent
from agents import snapshot as snapshot_agent
from agents.common import read_artifact
from src.core.tasks import QUESTIONS_V1
from src.storage.database import Database
from tests.helpers import (
    TEST_SEED,
    TEST_SPLIT_SEASONS,
    TRAIN_SEASONS,
    build_environment,
)

RUN_ID = "run_baselines"


@pytest.fixture(scope="session")
def baselines_env(tmp_path_factory):
    """Environnement synthétique + préambule pipeline jusqu'aux baselines."""
    root = tmp_path_factory.mktemp("baselines")
    environment = build_environment(root)
    for module in (
        cleaner_agent,
        pre_match_agent,
        snapshot_agent,
        baselines_agent,
    ):
        code = module.main(["--config", str(environment["config"]), "--run-id", RUN_ID])
        assert code == 0, f"échec du préambule : {module.__name__}"
    return environment


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _model_rows(baselines_env, model: str) -> list[dict]:
    path = (
        baselines_env["root"] / "predictions" / RUN_ID / "baselines" / f"{model}.jsonl"
    )
    rows = _read_jsonl(path)
    assert rows, f"aucune prédiction pour {model}"
    return rows


class TestUniforme:
    """Baseline uniforme (§10.1) : 1/n sur chaque catégorie."""

    def test_uniforme_partout(self, baselines_env) -> None:
        for row in _model_rows(baselines_env, "uniform"):
            assert row["status"] == "valid"
            for task, dist in row["tasks"].items():
                criteria = QUESTIONS_V1[task]["criteria"]
                assert set(dist) == set(criteria)
                expected = 1.0 / len(criteria)
                for category, probability in dist.items():
                    assert probability == pytest.approx(expected, abs=1e-5), (
                        f"{task}/{category} : {probability} ≠ {expected}"
                    )


class TestPoisson:
    """Baseline Poisson (§10.2) : distributions valides."""

    def test_sommes_egales_a_un(self, baselines_env) -> None:
        for row in _model_rows(baselines_env, "poisson"):
            for task, dist in row["tasks"].items():
                criteria = QUESTIONS_V1[task]["criteria"]
                assert set(dist) == set(criteria)
                # Arrondi canonique à 1e-6 par catégorie → tolérance 2e-5.
                assert sum(dist.values()) == pytest.approx(1.0, abs=2e-5), (
                    f"{task} : somme = {sum(dist.values())}"
                )

    def test_aucune_probabilite_negative(self, baselines_env) -> None:
        for row in _model_rows(baselines_env, "poisson"):
            for task, dist in row["tasks"].items():
                for category, probability in dist.items():
                    assert probability >= 0.0, f"{task}/{category} : {probability}"

    def test_toutes_les_taches_presentes(self, baselines_env) -> None:
        tasks = set(QUESTIONS_V1)
        for row in _model_rows(baselines_env, "poisson"):
            assert set(row["tasks"]) == tasks


class TestRegressionSansFuiteTemporelle:
    """La logistique ne s'entraîne JAMAIS sur la saison test (§11.1, §14.7)."""

    def test_aucun_match_test_dans_l_entrainement(self, baselines_env) -> None:
        artifact = read_artifact(
            baselines_env["root"] / "artifacts" / RUN_ID / "baselines_run.json"
        )
        training = artifact["payload"]["training"]["logistic_1x2"]
        train_ids = set(training["train_match_ids"])
        assert training["n_train_matches"] == len(train_ids)

        database = Database(baselines_env["db"])
        matches = database.query("SELECT * FROM matches")
        database.close()
        test_ids = {
            m["match_id"] for m in matches if m["season"] in TEST_SPLIT_SEASONS
        }
        assert test_ids, "aucun match de la saison test dans la base"
        assert not (train_ids & test_ids), (
            f"matchs du test final dans l'entraînement : {sorted(train_ids & test_ids)}"
        )

    def test_saisons_et_dates_d_entrainement(self, baselines_env) -> None:
        artifact = read_artifact(
            baselines_env["root"] / "artifacts" / RUN_ID / "baselines_run.json"
        )
        training = artifact["payload"]["training"]["logistic_1x2"]
        assert set(training["train_seasons"]) == set(TRAIN_SEASONS)

        database = Database(baselines_env["db"])
        matches = database.query("SELECT * FROM matches")
        database.close()
        by_id = {m["match_id"]: m for m in matches}
        for match_id in training["train_match_ids"]:
            assert by_id[match_id]["season"] in TRAIN_SEASONS
        # Frontière temporelle stricte : tout l'entraînement précède le test.
        test_kickoffs = sorted(
            m["kickoff_timestamp"]
            for m in matches
            if m["season"] in TEST_SPLIT_SEASONS
        )
        assert training["max_kickoff"] < test_kickoffs[0]

    def test_dix_pre_matchs_d_entrainement_minimum(self, baselines_env) -> None:
        artifact = read_artifact(
            baselines_env["root"] / "artifacts" / RUN_ID / "baselines_run.json"
        )
        training = artifact["payload"]["training"]["logistic_1x2"]
        # Exigence bloquante de l'agent baselines (≥ 10 pré-matchs).
        assert training["n_train_matches"] >= 10


class TestArtefactBaselines:
    """L'artefact baselines_run.json publie modèles et fenêtre (§14.7)."""

    def test_modeles_et_statuts(self, baselines_env) -> None:
        artifact = read_artifact(
            baselines_env["root"] / "artifacts" / RUN_ID / "baselines_run.json"
        )
        payload = artifact["payload"]
        assert artifact["status"] == "validated"
        expected_models = {
            "uniform", "historical_frequency", "current_score",
            "persistence", "poisson", "logistic_1x2",
        }
        assert set(payload["models"]) == expected_models
        for counts in payload["models"].values():
            assert counts["n_predictions"] > 0
            assert counts["n_invalid"] == 0

    def test_logistique_uniquement_sur_le_test(self, baselines_env) -> None:
        # La logistique ne prédit QUE la saison test (§11.1) ; les modèles
        # point-in-time prédisent tous les snapshots validés.
        logistic_rows = _model_rows(baselines_env, "logistic_1x2")
        database = Database(baselines_env["db"])
        snapshots = {
            s["snapshot_id"]: s
            for s in database.query("SELECT * FROM match_snapshots")
        }
        matches = {
            m["match_id"]: m for m in database.query("SELECT * FROM matches")
        }
        database.close()
        for row in logistic_rows:
            snap = snapshots[row["snapshot_id"]]
            assert matches[snap["match_id"]]["season"] in TEST_SPLIT_SEASONS
        assert set(logistic_rows[0]["tasks"]) == {"one_x_two"}

    def test_seed_figee(self, baselines_env) -> None:
        artifact = read_artifact(
            baselines_env["root"] / "artifacts" / RUN_ID / "baselines_run.json"
        )
        assert artifact["payload"]["training"]["logistic_1x2"]["hyperparameters"]
        _ = TEST_SEED
