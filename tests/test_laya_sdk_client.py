"""Tests du client SDK réel (RealLayaClient) — sans laya/torch installés.

Le stub imite ``laya.Agent`` : mêmes formes de réponse que le SDK (choix ->
probabilités par libellé ; score -> probabilités INDICÉES par position,
arrondies à 4 décimales — la somme dérive, écart d'exécution D1/A3).

Couverture :
- mapping figé QUESTIONS_V1 -> format SDK (instructions verbatim) ;
- traduction des indices score -> libellés de niveaux ;
- contrat de réponse brute (parse §8.6 + tolérance de somme adaptée) ;
- fabrique de clients de ``run_laya`` (client: sdk) bout en bout ;
- échantillonnage stratifié déterministe (pilot A3/D3).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import agents.laya as laya_module
from agents.laya import (
    RealLayaClient,
    _map_score_probabilities,
    _select_stratified_sample,
    _to_sdk_questions,
    run_laya,
)
from agents.orchestrator import run_pipeline
from src.core.errors import ErrorCode, ValidationError
from src.core.tasks import parse_raw_response, validate_distribution
from src.storage.database import Database
from tests.helpers import build_environment

SUM_TOLERANCE_SDK = 2e-3  # écart D1 (arrondi 4 décimales du SDK)


# --- Stub de l'Agent SDK -----------------------------------------------------


class _StubSdkAgent:
    """Imite ``laya.Agent.predict`` — réponses arrondies à 4 décimales."""

    calls = 0

    def predict(self, state, questions, max_len=None):  # signature SDK
        _StubSdkAgent.calls += 1
        answers = {}
        for qid, q in questions.items():
            if q["type"] == "choice":
                keys = list(q["criteria"].keys())
                n = len(keys)
                probs = {k: round(1.0 / n, 4) for k in keys}
                answers[qid] = {
                    "type": "choice",
                    "choice": keys[0],
                    "probabilities": probs,
                    "answer_confidence": 0.5,
                }
            else:  # score : probabilités indicées
                n = len(q["criteria"])
                probs = {str(i): round(1.0 / n, 4) for i in range(n)}
                answers[qid] = {
                    "type": "score",
                    "score": float(n) / 2.0,
                    "legend": {str(i): c for i, c in enumerate(q["criteria"])},
                    "probabilities": probs,
                    "answer_confidence": 0.5,
                }
        return {
            "answers": answers,
            "routing": {"model": "multilingual"},
            "usage": {"input_tokens": 42, "windows": 1},
        }


@pytest.fixture()
def real_client_stubbed(monkeypatch):
    """RealLayaClient dont l'Agent SDK est remplacé par le stub."""
    client = RealLayaClient(max_len=2048)
    monkeypatch.setattr(
        RealLayaClient, "_ensure_agent", lambda self: _StubSdkAgent()
    )
    return client


# --- Mapping figé ------------------------------------------------------------


class TestMappingQuestions:
    def test_structure_choice(self) -> None:
        sdk_q = _to_sdk_questions(laya_module.QUESTIONS_V1)
        sb = sdk_q["score_bucket"]
        assert sb["type"] == "choice"
        # instructions verbatim (wording figé §8.5)
        assert (
            sb["instructions"]
            == laya_module.QUESTIONS_V1["score_bucket"]["instructions"]
        )
        # critères : dict {libellé: None}, mêmes libellés dans l'ordre figé
        crit = sb["criteria"]
        assert list(crit.keys()) == laya_module.QUESTIONS_V1["score_bucket"]["criteria"]
        assert set(crit.values()) == {None}

    def test_structure_score(self) -> None:
        sdk_q = _to_sdk_questions(laya_module.QUESTIONS_V1)
        for task in ("total_corners", "total_yellow_cards"):
            q = sdk_q[task]
            assert q["type"] == "score"
            assert q["criteria"] == laya_module.QUESTIONS_V1[task]["criteria"]
            assert (
                q["instructions"]
                == laya_module.QUESTIONS_V1[task]["instructions"]
            )

    def test_mapping_deterministe(self) -> None:
        assert _to_sdk_questions(
            laya_module.QUESTIONS_V1
        ) == _to_sdk_questions(laya_module.QUESTIONS_V1)


class TestMapScoreProbabilities:
    def test_indices_vers_libelles(self) -> None:
        criteria = ["0", "1", "2", "21+"]
        probs = {"0": 0.1, "1": 0.2, "2": 0.3, "3": 0.4}
        out = _map_score_probabilities(probs, criteria)
        assert out == {"0": 0.1, "1": 0.2, "2": 0.3, "21+": 0.4}

    def test_indice_manquant_rejete(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _map_score_probabilities({"0": 0.5}, ["0", "1"])
        assert exc.value.code == ErrorCode.MISSING_CATEGORY


# --- Contrat de réponse ------------------------------------------------------


class TestContratReponse:
    def test_format_brut_et_validation(self, real_client_stubbed) -> None:
        raw, latency = real_client_stubbed.predict(
            '{"metadata":{"cutoff_seconds":0}}',
            laya_module.QUESTIONS_V1,
        )
        assert latency >= 0.0
        parsed = parse_raw_response(raw)
        for task, q in laya_module.QUESTIONS_V1.items():
            dist = validate_distribution(
                parsed[task], task, sum_tolerance=SUM_TOLERANCE_SDK
            )
            assert set(dist) == set(q["criteria"])

    def test_somme_derivee_rejetee_en_1e_6(self, real_client_stubbed) -> None:
        """L'arrondi 4 décimales (17 x 0.0588 = 0.9996) échoue à 1e-6 —
        la tolérance adaptée D1 est nécessaire, et documentée."""
        raw, _ = real_client_stubbed.predict(
            "{}", laya_module.QUESTIONS_V1
        )
        parsed = parse_raw_response(raw)
        with pytest.raises(ValidationError):
            validate_distribution(
                parsed["score_bucket"], "score_bucket", sum_tolerance=1e-6
            )

    def test_aucune_renormalisation(self, real_client_stubbed) -> None:
        """Les probabilités reçues (somme 0.9996) passent TELLES QUELLES."""
        raw, _ = real_client_stubbed.predict(
            "{}", laya_module.QUESTIONS_V1
        )
        parsed = parse_raw_response(raw)
        dist = validate_distribution(
            parsed["score_bucket"], "score_bucket",
            sum_tolerance=SUM_TOLERANCE_SDK,
        )
        # 17 catégories uniformes arrondies : chaque p = 0.0588 exactement
        assert set(dist.values()) == {round(1.0 / 17, 4)}
        assert abs(sum(dist.values()) - 0.9996) < 1e-12

    def test_reponse_pas_de_distribution(self, monkeypatch) -> None:
        class _BadAgent:
            def predict(self, state, questions, max_len=None):
                return {"answers": {"score_bucket": {"type": "choice"}}}

        monkeypatch.setattr(
            RealLayaClient, "_ensure_agent", lambda self: _BadAgent()
        )
        client = RealLayaClient()
        with pytest.raises(ValidationError):
            client.predict("{}", laya_module.QUESTIONS_V1)

    def test_echantillonnage_deterministe(self, tmp_path) -> None:
        """La sélection stratifiée est reproductible et couvre les strates."""
        env = build_environment(tmp_path)
        assert run_pipeline(env["config"], "run_prep_sample") == 0
        db = Database(env["db"])
        rule = {
            "stratified_by": ["cutoff_seconds", "information_tier"],
            "n_per_stratum": 2,
        }
        first = _select_stratified_sample(db, rule)
        second = _select_stratified_sample(db, rule)
        db.close()
        assert first, "échantillon vide"
        assert first == second, "sélection non déterministe"
        rows_total = None
        db = Database(env["db"])
        strata_db = db.query(
            "SELECT DISTINCT cutoff_seconds, information_tier "
            "FROM match_snapshots WHERE validation_status='validated'"
        )
        rows_total = db.query(
            "SELECT snapshot_id, cutoff_seconds, information_tier "
            "FROM match_snapshots WHERE validation_status='validated'"
        )
        db.close()
        strata_all = {
            (r["cutoff_seconds"], r["information_tier"]) for r in rows_total
        }
        selected_strata = set()
        for r in rows_total:
            if r["snapshot_id"] in first:
                selected_strata.add(
                    (r["cutoff_seconds"], r["information_tier"])
                )
        assert selected_strata == strata_all, "strates non couvertes"
        assert strata_db is not None


# --- Fabrique + run bout en bout (client: sdk, stub) ------------------------


@pytest.fixture(scope="module")
def sdk_env(tmp_path_factory):
    """Environnement complet (pipeline mock exécuté) + config client: sdk."""
    root = tmp_path_factory.mktemp("sdk_factory")
    env = build_environment(root)
    assert run_pipeline(env["config"], "run_factory_prep") == 0

    cfg = yaml.safe_load(Path(env["config"]).read_text(encoding="utf-8"))
    cfg["laya"]["client"] = "sdk"
    cfg["laya"]["sum_tolerance"] = SUM_TOLERANCE_SDK
    cfg["laya"]["model_version"] = "laya-0.3.21-multilingual-stub"
    cfg["laya"]["max_len"] = 2048
    sdk_config = root / "configs" / "experiment_sdk.yaml"
    sdk_config.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    env["sdk_config"] = sdk_config
    return env


class TestFabriqueSdk:
    def test_run_laya_sdk_stub(self, sdk_env, monkeypatch) -> None:
        monkeypatch.setattr(
            RealLayaClient, "_ensure_agent", lambda self: _StubSdkAgent()
        )
        code = run_laya(sdk_env["sdk_config"], "run_sdk_stub_001", "v1")
        assert code == 0, "run_laya doit réussir avec le client sdk stubbé"

        db = Database(sdk_env["db"])
        rows = db.query(
            "SELECT * FROM laya_predictions "
            "WHERE run_id='run_sdk_stub_001' AND status='valid'"
        )
        db.close()
        assert rows, "aucune prédiction SDK enregistrée"
        for row in rows:
            assert row["model_version"] == "laya-0.3.21-multilingual-stub"
            parsed = json.loads(row["parsed_response"])
            for task in laya_module.QUESTIONS_V1:
                # parsed_response = {tâche: {catégorie: p}} — le wrapper
                # « probabilities » n'existe que dans la réponse brute.
                validate_distribution(
                    {"probabilities": parsed[task]}, task,
                    sum_tolerance=SUM_TOLERANCE_SDK,
                )

        artifact = json.loads(
            (
                Path(sdk_env["root"])
                / "artifacts"
                / "run_sdk_stub_001"
                / "laya_run.json"
            ).read_text(encoding="utf-8")
        )
        assert artifact["producer"] == "laya_agent"
        assert artifact["status"] in ("validated", "warning")
        meta = artifact["payload"]["model_metadata"]
        assert meta["package"] == "laya"
        assert "convaiinnovations/laya-multilingual" in meta["checkpoint"]
        assert "e4e9ddf2" in meta["checkpoint"]
        assert "RealLayaClient" in artifact["payload"]["note"]
        assert artifact["payload"]["repetition_audit"]["k"] == 5

    def test_client_inconnu_bloque(self, sdk_env, monkeypatch) -> None:
        cfg = yaml.safe_load(
            Path(sdk_env["sdk_config"]).read_text(encoding="utf-8")
        )
        cfg["laya"]["client"] = "inconnu"
        bad_config = Path(sdk_env["root"]) / "configs" / "bad.yaml"
        bad_config.write_text(
            yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        assert run_laya(bad_config, "run_bad_client", "v1") == 2
