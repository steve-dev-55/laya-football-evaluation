"""Tests du plan statistique (protocole §11.2, §12.5).

Vérifie : Holm-Bonferroni (cas du protocole, ordre d'entrée préservé),
bootstrap groupé par match (seed reproductible, IC contient la moyenne,
n_matches correct), bootstrap de différence (matchs manquants exclus des
deux côtés, dénominateur publié).
"""

from __future__ import annotations

import random

import pytest

from src.core.stats import (
    bootstrap_difference,
    compare_models,
    holm_bonferroni,
    stratified_group_bootstrap,
)


def _per_match_values(n: int, seed: int, mu: float = 1.2) -> dict[str, float]:
    """Valeurs par match reproductibles (seed fixe, gaussiennes modérées)."""
    rng = random.Random(seed)
    return {f"match_{i:03d}": rng.gauss(mu, 0.3) for i in range(n)}


class TestHolmBonferroni:
    """Correction Holm-Bonferroni (§12.5) — procédure descendante."""

    def test_cas_du_protocole(self) -> None:
        # p triées : 0.01 (rejet), 0.03 (> 0.025 → stop), 0.04 (non rejet)
        rejected = holm_bonferroni([0.01, 0.04, 0.03], alpha=0.05)
        assert rejected == [True, False, False]

    def test_ordre_entree_preserve(self) -> None:
        rejected = holm_bonferroni([0.04, 0.03, 0.01], alpha=0.05)
        assert rejected == [False, False, True]

    def test_toutes_rejetees(self) -> None:
        rejected = holm_bonferroni([0.001, 0.004, 0.009], alpha=0.05)
        assert rejected == [True, True, True]

    def test_aucune_rejetee(self) -> None:
        rejected = holm_bonferroni([0.9, 0.8, 0.7], alpha=0.05)
        assert rejected == [False, False, False]

    def test_arret_au_premier_echec(self) -> None:
        # 0.01 <= 0.05/3 est rejeté ; 0.03 > 0.05/2 stoppe tout le reste
        # (0.5 ne peut plus être rejeté bien que > alpha seul).
        rejected = holm_bonferroni([0.01, 0.03, 0.5], alpha=0.05)
        assert rejected == [True, False, False]

    def test_liste_vide(self) -> None:
        assert holm_bonferroni([]) == []

    def test_p_hors_bornes_rejetee(self) -> None:
        with pytest.raises(ValueError):
            holm_bonferroni([0.5, 1.4])


class TestBootstrapGroupe:
    """Bootstrap stratifié groupé par match (§11.2, §12.5)."""

    def test_seed_reproductible(self) -> None:
        values = _per_match_values(30, seed=42)
        first = stratified_group_bootstrap(values, replicates=2000, seed=7, alpha=0.05)
        second = stratified_group_bootstrap(values, replicates=2000, seed=7, alpha=0.05)
        assert first == second

    def test_ic_contient_la_moyenne(self) -> None:
        values = _per_match_values(40, seed=11)
        result = stratified_group_bootstrap(values, replicates=2000, seed=20260925)
        assert result["ci_low"] <= result["mean"] <= result["ci_high"]

    def test_n_matches_correct(self) -> None:
        values = _per_match_values(25, seed=3)
        result = stratified_group_bootstrap(values, replicates=2000, seed=1)
        assert result["n_matches"] == 25
        assert result["replicates"] == 2000

    def test_seeds_differents_peuvent_differer(self) -> None:
        values = _per_match_values(30, seed=5)
        first = stratified_group_bootstrap(values, replicates=500, seed=1)
        second = stratified_group_bootstrap(values, replicates=500, seed=2)
        assert (first["ci_low"], first["ci_high"]) != (second["ci_low"], second["ci_high"])

    def test_vide(self) -> None:
        result = stratified_group_bootstrap({}, replicates=2000, seed=1)
        assert result["n_matches"] == 0
        assert result["mean"] != result["mean"]  # NaN explicite

    def test_replicates_sous_2000_avertit(self) -> None:
        values = _per_match_values(10, seed=9)
        with pytest.warns(UserWarning, match="2000"):
            stratified_group_bootstrap(values, replicates=100, seed=1)


class TestBootstrapDifference:
    """Différence de contribution par match entre deux modèles (§12.5)."""

    def test_matchs_manquants_exclus_des_deux_cotes(self) -> None:
        model_a = {f"match_{i}": 1.0 + 0.1 * i for i in range(6)}       # 0..5
        model_b = {f"match_{i}": 1.0 + 0.1 * i for i in range(1, 7)}    # 1..6
        result = bootstrap_difference(
            model_a, model_b, replicates=2000, seed=20260925
        )
        # Les matchs communs sont 1..5 : le dénominateur publié est 5.
        assert result["n_matches"] == 5
        assert result["mean_difference"] == pytest.approx(0.0)

    def test_difference_exacte(self) -> None:
        model_a = {f"m{i}": 2.0 for i in range(10)}
        model_b = {f"m{i}": 1.5 for i in range(10)}
        result = bootstrap_difference(
            model_a, model_b, replicates=2000, seed=20260925
        )
        assert result["mean_difference"] == pytest.approx(0.5)
        assert result["ci_low"] <= 0.5 <= result["ci_high"]

    def test_aucun_match_commun_rejete(self) -> None:
        with pytest.raises(ValueError, match="aucun match commun"):
            bootstrap_difference({"a": 1.0}, {"b": 2.0}, replicates=100, seed=1)


class TestCompareModels:
    """Comparaison à une référence avec Holm-Bonferroni (§12.5)."""

    def test_reference_et_holm(self) -> None:
        values = {
            "laya": _per_match_values(20, seed=1, mu=1.0),
            "baseline_a": _per_match_values(20, seed=2, mu=1.5),
            "baseline_b": _per_match_values(20, seed=3, mu=1.05),
        }
        result = compare_models(
            values, "laya", replicates=500, seed=20260925, alpha=0.05
        )
        assert set(result) == {"baseline_a", "baseline_b"}
        for model, stats in result.items():
            assert stats["mean_difference"] == pytest.approx(
                sum(values[model].values()) / len(values[model])
                - sum(values["laya"].values()) / len(values["laya"]),
                abs=1e-12,
            )
            assert "significant_holm" in stats
        # baseline_a (nettement moins bonne) doit être rejetée après Holm.
        assert result["baseline_a"]["significant_holm"] is True

    def test_reference_absente_rejetee(self) -> None:
        with pytest.raises(KeyError):
            compare_models({"a": {"m": 1.0}}, "laya", replicates=100, seed=1)
