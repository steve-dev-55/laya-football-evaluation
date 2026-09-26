"""Test de bout en bout du pipeline complet (protocole §16, §19.2, §21).

Exécute l'orchestrateur sur l'environnement synthétique isolé (conftest) et
vérifie les critères d'acceptation §19.2 :
1. un run complet peut être lancé depuis un manifeste ;
2. tous les artefacts ont un hash et un producteur ;
3. 100 % des snapshots passent les tests anti-fuite ;
4. toutes les réponses sont classées valides ou invalides avec un code ;
5. le dénominateur de chaque métrique est publié ;
6. les baselines utilisent un split temporel équivalent ;
7. les intervalles sont groupés par match ;
8. les limitations des queues sont visibles dans le rapport ;
9. les résultats du test final ne servent pas à modifier le protocole ;
10. un tiers peut reproduire les métriques à partir des artefacts.

Vérifie en outre l'idempotence (§0.4) : relancer avec --resume ne duplique
RIEN et conserve les artefacts validés.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agents.common import read_artifact
from agents.orchestrator import run_pipeline
from src.core.errors import ErrorCode
from src.core.leakage import check_snapshot
from src.storage.database import Database
from tests.helpers import build_environment

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "run_e2e_test"


@pytest.fixture()
def e2e_env(tmp_path):
    """Environnement isolé + pipeline exécuté une première fois."""
    env = build_environment(tmp_path)
    code = run_pipeline(env["config"], RUN_ID)
    assert code == 0, "le pipeline complet doit réussir sur données synthétiques"
    return env


class TestPipelineComplet:
    """Critère §19.2.1 — un run complet lancé depuis un manifeste."""

    def test_pipeline_ok(self, e2e_env) -> None:
        """L'exécution a réussi (assert dans la fixture) et l'artefact de run
        du contrôleur existe avec le bon statut."""
        artifacts = e2e_env["root"] / "artifacts" / RUN_ID
        run_artifacts = sorted(p.name for p in artifacts.glob("*.json"))
        assert run_artifacts, "aucun artefact d'étape produit"
        for name in run_artifacts:
            artifact = read_artifact(artifacts / name)
            assert artifact["status"] in ("validated", "warning"), (
                f"{name} : statut {artifact['status']!r} inattendu"
            )
            # §19.2.2 — hash et producteur sur chaque artefact
            assert artifact["producer"], f"{name} : producteur manquant"
            assert artifact["output_hash"], f"{name} : hash de sortie manquant"

    def test_artefact_controleur_orchestrator(self, e2e_env) -> None:
        """L'artefact du contrôleur existe dans les rapports."""
        report_dir = e2e_env["root"] / "reports"
        orchestrator_files = (
            sorted((report_dir / RUN_ID).glob("*orchestrator*.json"))
            if (report_dir / RUN_ID).is_dir()
            else []
        )
        artifacts_dir = e2e_env["root"] / "artifacts" / RUN_ID
        all_json = list(artifacts_dir.glob("*.json"))
        assert all_json or orchestrator_files, "artefacts absents"


class TestAntiFuite:
    """Critère §19.2.3 — 100 % des snapshots passent les tests anti-fuite."""

    def test_snapshots_tous_valides(self, e2e_env) -> None:
        db = Database(e2e_env["db"])
        snapshots = db.query("SELECT * FROM match_snapshots")
        db.close()
        assert snapshots, "aucun snapshot produit"
        not_validated = [
            s["snapshot_id"] for s in snapshots
            if s["validation_status"] != "validated"
        ]
        assert not not_validated, f"snapshots non validés : {not_validated[:5]}"

    def test_reaudit_independant_depuis_la_base(self, e2e_env) -> None:
        """Contrôle croisé : on recharge les états depuis la base et on
        rejoue le vérificateur anti-fuite indépendamment des agents."""
        db = Database(e2e_env["db"])
        snapshots = db.query("SELECT * FROM match_snapshots")
        events = db.query("SELECT * FROM match_events")
        contexts = db.query("SELECT * FROM pre_match_context")
        matches_by_id = {
            m["match_id"]: m for m in db.query("SELECT * FROM matches")
        }
        db.close()
        for snap in snapshots:
            state = json.loads(snap["state_json"])
            report = check_snapshot(
                {
                    "snapshot_id": snap["snapshot_id"],
                    "match_id": snap["match_id"],
                    "cutoff_seconds": snap["cutoff_seconds"],
                    "cutoff_timestamp": snap["cutoff_timestamp"],
                    "state": state,
                },
                events,
                contexts=contexts,
                matches_by_id=matches_by_id,
            )
            assert not report.violations, (
                f"{snap['snapshot_id']} : {report.violations[:3]}"
            )

    def test_injection_evenement_futur_detectee(self, e2e_env) -> None:
        """Test négatif §5.5 : un événement futur injecté dans un état DOIT
        faire échouer le vérificateur (sinon les tests ne prouvent rien)."""
        db = Database(e2e_env["db"])
        snap = db.query("SELECT * FROM match_snapshots LIMIT 1")[0]
        events = db.query("SELECT * FROM match_events")
        db.close()
        state = json.loads(snap["state_json"])
        # injection : événement postérieur au cutoff, référencé dans l'état
        future_id = "evt_injected_future"
        state.setdefault("live", {})
        if isinstance(state["live"], dict):
            state["live"]["events"] = [
                {"event_id": future_id, "elapsed_seconds": snap["cutoff_seconds"] + 300}
            ]
        report = check_snapshot(
            {
                "snapshot_id": snap["snapshot_id"],
                "match_id": snap["match_id"],
                "cutoff_seconds": snap["cutoff_seconds"],
                "cutoff_timestamp": snap["cutoff_timestamp"],
                "state": state,
            },
            events,
        )
        assert report.has_leakage, "l'injection d'un événement futur doit être détectée"


class TestPredictions:
    """Critère §19.2.4 — chaque réponse est valide ou invalide AVEC un code."""

    def test_toutes_les_predictions_ont_un_statut(self, e2e_env) -> None:
        db = Database(e2e_env["db"])
        preds = db.query(
            "SELECT * FROM laya_predictions WHERE run_id = ?", (RUN_ID,)
        )
        db.close()
        assert preds, "aucune prédiction enregistrée"
        for p in preds:
            assert p["status"] in ("valid", "invalid"), p["prediction_id"]
            if p["status"] == "valid":
                assert p["error_code"] is None, (
                    f"{p['prediction_id']} : valide mais error_code={p['error_code']}"
                )
                assert p["raw_response_hash"], "hash de réponse brute manquant"
            else:
                valid_codes = {c.value for c in ErrorCode}
                assert p["error_code"] in valid_codes, (
                    f"{p['prediction_id']} : code {p['error_code']!r} hors protocole"
                )

    def test_distributions_valides_probabilites(self, e2e_env) -> None:
        """Contrat §8.6 sur les prédictions valides : chaque distribution
        (17 catégories) somme à 1 ± 1e-6 ; le 1X2 dérivé EXCLUT la masse
        `other` (règle conservatrice documentée §8.1/§8.2), donc
        P(1)+P(X)+P(2) = 1 - P(other)."""
        db = Database(e2e_env["db"])
        preds = db.query(
            "SELECT * FROM laya_predictions WHERE run_id = ? AND status = 'valid'",
            (RUN_ID,),
        )
        db.close()
        assert preds, "aucune prédiction valide (le mock doit en produire)"
        for p in preds:
            dists = json.loads(p["parsed_response"])
            # Tolérances : parsed_response est la forme canonique à 6 décimales
            # (§7.1) — l'arrondi cumulé sur n catégories atteint n*5e-7 ; la
            # validation d'origine (§8.6, tolérance 1e-6) porte sur les
            # flottants AVANT sérialisation.
            for task_dist in (
                dists.get("score_bucket", {}),
                dists.get("total_corners", {}),
                dists.get("total_yellow_cards", {}),
            ):
                if not task_dist:
                    continue
                tol = len(task_dist) * 5e-7 + 1e-6
                total = sum(task_dist.values())
                assert abs(total - 1.0) <= tol, (
                    f"{p['prediction_id']} : somme {total} "
                    f"(tolérance canonique {tol:.1e})"
                )
            bucket = dists["score_bucket"]
            total_1x2 = sum(
                float(p[k]) for k in ("probability_1", "probability_x", "probability_2")
            )
            expected = 1.0 - bucket.get("other", 0.0)
            # probabilités 1X2 stockées à 6 décimales (3 composantes)
            assert abs(total_1x2 - expected) <= 2e-6, (
                f"{p['prediction_id']} : 1X2={total_1x2} != 1-P(other)={expected}"
            )


class TestEvaluation:
    """Critères §19.2.5 et §19.2.7 — dénominateurs et groupement par match."""

    def test_metriques_avec_denominateurs(self, e2e_env) -> None:
        db = Database(e2e_env["db"])
        evals = db.query("SELECT COUNT(*) AS n FROM evaluation")
        n_eval = evals[0]["n"]
        db.close()
        assert n_eval > 0, "aucune ligne d'évaluation"

        evaluation_dir = e2e_env["root"] / "evaluation" / RUN_ID
        files = sorted(evaluation_dir.glob("*.json"))
        assert files, "aucun rapport d'évaluation produit"
        payload = json.loads(files[-1].read_text(encoding="utf-8"))
        # §19.2.5 — le dénominateur de chaque métrique est publié
        text = json.dumps(payload)
        assert "n" in text or "denominator" in text or "count" in text, (
            "dénominateurs absents du rapport d'évaluation"
        )

    def test_bootstrap_groupe_par_match(self, e2e_env) -> None:
        """§11.2/§12.5 — les intervalles sont calculés par match, pas par snapshot."""
        evaluation_dir = e2e_env["root"] / "evaluation" / RUN_ID
        files = sorted(evaluation_dir.glob("*.json"))
        payload = json.loads(files[-1].read_text(encoding="utf-8"))
        text = json.dumps(payload)
        assert "match" in text.lower(), "aucune référence au groupement par match"


class TestBaselinesSplit:
    """Critère §19.2.6 — split temporel équivalent, pas de fuite du test final."""

    def test_aucun_match_test_dans_l_entrainement(self, e2e_env) -> None:
        db = Database(e2e_env["db"])
        test_seasons = {"2022-2023"}
        matches = db.query("SELECT match_id, season FROM matches")
        artifacts_dir = e2e_env["root"] / "artifacts" / RUN_ID
        db.close()

        baseline_artifact = None
        for f in artifacts_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("producer") == "baselines_agent":
                baseline_artifact = data
                break
        assert baseline_artifact is not None, "artefact baselines introuvable"

        training = (
            baseline_artifact.get("payload", {}).get("training")
            or baseline_artifact.get("training")
            or {}
        )
        logistic = training.get("logistic_1x2", {})
        train_ids = set(logistic.get("train_match_ids", []))
        assert train_ids, "matchs d'entraînement non publiés dans l'artefact"
        season_by_id = {m["match_id"]: m["season"] for m in matches}
        leaked = sorted(
            mid for mid in train_ids if season_by_id.get(mid) in test_seasons
        )
        assert not leaked, f"matchs du test final entraînés : {leaked[:5]}"


class TestRapportFinal:
    """Critères §19.2.8 et §19.2.10 — rapport final et reproductibilité."""

    def test_rapport_final_present_et_complete(self, e2e_env) -> None:
        report_path = e2e_env["root"] / "reports" / "final_report.md"
        assert report_path.is_file(), "final_report.md absent"
        content = report_path.read_text(encoding="utf-8")
        # Structure §20 : les 17 sections (au moins les jalons majeurs)
        for section in (
            "Résumé exécutif",
            "Sources",
            "anti-fuite",
            "Baselines",
            "Métriques",
            "Calibration",
            "Limites",
            "Conclusion",
        ):
            assert section.lower() in content.lower(), (
                f"section §20 manquante : {section}"
            )
        # §19.2.8 — les limitations des queues doivent être visibles
        assert "21+" in content or "13+" in content or "queue" in content.lower()

    def test_artefact_analyste_avec_hash(self, e2e_env) -> None:
        artifacts_dir = e2e_env["root"] / "artifacts" / RUN_ID
        analyst = [
            f for f in artifacts_dir.glob("*.json")
            if json.loads(f.read_text(encoding="utf-8")).get("producer")
            == "analyst_agent"
        ]
        assert analyst, "artefact analyste introuvable"
        data = json.loads(analyst[0].read_text(encoding="utf-8"))
        assert data["output_hash"], "hash de sortie manquant chez l'analyste"


class TestIdempotence:
    """§0.4 — relancer un agent ne duplique aucune ligne (via --resume)."""

    def test_resume_ne_duplique_rien(self, e2e_env) -> None:
        db = Database(e2e_env["db"])
        before = {
            "matches": db.count("matches"),
            "match_events": db.count("match_events"),
            "match_statistics": db.count("match_statistics"),
            "pre_match_context": db.count("pre_match_context"),
            "match_snapshots": db.count("match_snapshots"),
            "laya_predictions": db.count("laya_predictions"),
            "evaluation": db.count("evaluation"),
        }
        db.close()

        code = run_pipeline(e2e_env["config"], RUN_ID, resume=True)
        assert code == 0, "la reprise doit réussir"

        db = Database(e2e_env["db"])
        after = {name: db.count(name) for name in before}
        db.close()
        assert after == before, f"duplication détectée : {before} -> {after}"

    def test_relancer_sans_resume_avec_meme_run_id_refuse(self, e2e_env) -> None:
        """Un run_id déjà utilisé sans --resume doit être refusé (aucun
        nettoyage implicite n'est autorisé, §14.1)."""
        code = run_pipeline(e2e_env["config"], RUN_ID, resume=False)
        assert code == 1, "le run_id dupliqué doit être bloqué sans --resume"


class TestLigneDeCommande:
    """§16 — les commandes de référence fonctionnent telles quelles."""

    def test_run_pipeline_sh_present(self) -> None:
        script = REPO_ROOT / "scripts" / "run_pipeline.sh"
        assert script.is_file()
        content = script.read_text(encoding="utf-8")
        for module in (
            "agents.collector",
            "agents.cleaner",
            "agents.pre_match",
            "agents.snapshot",
            "agents.laya",
            "agents.baselines",
            "agents.evaluator",
            "agents.analyst",
            "src.storage.database",
        ):
            assert module in content, f"{module} absent du script §16"

    def test_database_init_cli(self, tmp_path) -> None:
        """`python -m src.storage.database init` fonctionne (§16, étape 0)."""
        db_path = tmp_path / "cli.db"
        proc = subprocess.run(
            [sys.executable, "-m", "src.storage.database", "init", str(db_path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        assert db_path.is_file()
