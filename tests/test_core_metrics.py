"""Tests des métriques d'évaluation (protocole §12).

Cas de référence : log loss au plancher 1e-15, Brier/RPS/CRPS/log score nuls
pour une distribution certaine, ECE nul pour une calibration parfaite, PIT
randomisé, couverture, distances JS et variation totale.
"""

from __future__ import annotations

import math

import pytest

from src.core.metrics import (
    accuracy_top,
    brier_multiclass,
    crps_discrete,
    ece,
    jensen_shannon_distance,
    log_loss,
    log_score_discrete,
    mae,
    pit_randomized,
    predictive_interval_coverage,
    rps,
    tail_mass,
    total_variation_distance,
)


class TestLogLoss:
    """Log loss multiclass, plancher epsilon = 1e-15 (§12.1)."""

    def test_plancher_epsilon_pour_proba_nulle(self) -> None:
        assert log_loss([0.0, 1.0], 0) == pytest.approx(-math.log(1e-15))

    def test_plancher_epsilon_pour_proba_tres_faible(self) -> None:
        assert log_loss([1e-20, 1.0], 0) == pytest.approx(-math.log(1e-15))

    def test_distribution_certaine(self) -> None:
        assert log_loss([0.0, 1.0], 1) == pytest.approx(0.0)

    def test_uniforme_3_classes(self) -> None:
        assert log_loss([1 / 3, 1 / 3, 1 / 3], 0) == pytest.approx(math.log(3))

    def test_proba_hors_bornes_rejetee(self) -> None:
        with pytest.raises(ValueError):
            log_loss([1.2, -0.2], 0)


class TestBrierEtRps:
    """Brier multiclass et RPS (cible ordonnée, §12.1)."""

    def test_brier_distribution_certaine_nulle(self) -> None:
        assert brier_multiclass([0.0, 1.0, 0.0], 1) == pytest.approx(0.0)

    def test_brier_uniforme_3_classes(self) -> None:
        assert brier_multiclass([1 / 3] * 3, 0) == pytest.approx(2 / 3)

    def test_rps_distribution_certaine_nul(self) -> None:
        assert rps([0.0, 0.0, 1.0], 2) == pytest.approx(0.0)

    def test_rps_penalise_les_erreurs_lointaines(self) -> None:
        near = rps([0.0, 1.0, 0.0], 1)
        far = rps([0.0, 1.0, 0.0], 2)
        assert far > near

    def test_rps_uniforme_extremes_symetriques(self) -> None:
        uniform = [1 / 3, 1 / 3, 1 / 3]
        # Les deux issues extrêmes ont le même RPS (0 → 5/18) ; l'issue
        # centrale est plus proche (1/9).
        assert rps(uniform, 0) == pytest.approx(rps(uniform, 2))
        assert rps(uniform, 0) == pytest.approx(5 / 18)
        assert rps(uniform, 1) == pytest.approx(1 / 9)


class TestEce:
    """Expected Calibration Error (§12.4)."""

    def test_calibration_parfaite_nulle(self) -> None:
        observations = [(0.5, 1)] * 50 + [(0.5, 0)] * 50
        assert ece(observations, n_bins=10) == pytest.approx(0.0)

    def test_mauvaise_calibration(self) -> None:
        observations = [(0.9, 0)] * 100  # très confiant, toujours faux
        assert ece(observations, n_bins=10) == pytest.approx(0.9)

    def test_sans_observation_nan(self) -> None:
        assert math.isnan(ece([]))


class TestCrpsEtLogScoreDiscrets:
    """CRPS discret et log score discret (§12.3)."""

    def test_crps_distribution_certaine_nul(self) -> None:
        dist = {str(level): 0.0 for level in range(22)}
        dist["5"] = 1.0
        assert crps_discrete(dist, 5) == pytest.approx(0.0)

    def test_crps_penalise_la_distance(self) -> None:
        dist = {str(level): 0.0 for level in range(22)}
        dist["5"] = 1.0
        assert crps_discrete(dist, 9) > crps_discrete(dist, 6)

    def test_crps_uniforme_positif(self) -> None:
        dist = {str(level): 1.0 / 22 for level in range(22)}
        assert crps_discrete(dist, 10) > 0.0

    def test_log_score_discrete_plancher(self) -> None:
        dist = {str(level): 0.0 for level in range(22)}
        dist["3"] = 1.0
        assert log_score_discrete(dist, "3") == pytest.approx(0.0)
        assert log_score_discrete(dist, "4") == pytest.approx(-math.log(1e-15))

    def test_log_score_discrete_categorie_absente(self) -> None:
        with pytest.raises(ValueError):
            log_score_discrete({"0": 1.0}, "1")


class TestPitRandomiseEtCouverture:
    """PIT randomisé et couverture des intervalles prédictifs (§12.3)."""

    def test_pit_distribution_certaine(self) -> None:
        dist = {str(level): 0.0 for level in range(14)}
        dist["4"] = 1.0
        # tout le tirage u tombe dans la masse de « 4 » : PIT = u
        assert pit_randomized(dist, 4, u=0.7) == pytest.approx(0.7)
        assert pit_randomized(dist, 4, u=0.0) == pytest.approx(0.0)
        assert pit_randomized(dist, 4, u=1.0) == pytest.approx(1.0)

    def test_pit_realisation_haute(self) -> None:
        dist = {"0": 0.5, "1": 0.5}
        assert pit_randomized(dist, 1, u=0.25) == pytest.approx(0.5 + 0.125)

    def test_pit_u_hors_bornes_rejete(self) -> None:
        with pytest.raises(ValueError):
            pit_randomized({"0": 1.0}, 0, u=1.5)

    def test_couverture_distribution_certaine(self) -> None:
        dist = {str(level): 0.0 for level in range(22)}
        dist["5"] = 1.0
        coverage = predictive_interval_coverage(dist, 5)
        assert coverage == {50: 1.0, 80: 1.0, 95: 1.0}

    def test_couverture_realisation_hors_support(self) -> None:
        dist = {str(level): 0.0 for level in range(22)}
        dist["5"] = 1.0
        coverage = predictive_interval_coverage(dist, 12)
        assert coverage == {50: 0.0, 80: 0.0, 95: 0.0}

    def test_couverture_large(self) -> None:
        dist = {str(level): 1.0 / 22 for level in range(22)}
        coverage = predictive_interval_coverage(dist, 10)
        assert coverage[95] == 1.0  # l'intervalle à 95 % couvre le support


class TestMaeEtDistances:
    """MAE, masse de queue, Jensen-Shannon, variation totale (§12.3, §13.1)."""

    def test_mae(self) -> None:
        assert mae(10.5, 8.0) == pytest.approx(2.5)

    def test_tail_mass(self) -> None:
        assert tail_mass({"3": 0.4, "21+": 0.6}) == pytest.approx(0.6)
        assert tail_mass({"0": 0.4, "13": 0.6}) == pytest.approx(0.0)

    def test_jensen_shannon_identiques_nulle(self) -> None:
        p = [0.2, 0.3, 0.5]
        assert jensen_shannon_distance(p, list(p)) == pytest.approx(0.0)

    def test_jensen_shannon_disjointes_maximale(self) -> None:
        p = [1.0, 0.0, 0.0]
        q = [0.0, 1.0, 0.0]
        assert jensen_shannon_distance(p, q) == pytest.approx(math.log(2))

    def test_jensen_shannon_symetrique(self) -> None:
        p = [0.1, 0.9]
        q = [0.8, 0.2]
        assert jensen_shannon_distance(p, q) == pytest.approx(
            jensen_shannon_distance(q, p)
        )

    def test_variation_totale_identiques_nulle(self) -> None:
        assert total_variation_distance([0.3, 0.7], [0.3, 0.7]) == pytest.approx(0.0)

    def test_variation_totale_disjointes_un(self) -> None:
        assert total_variation_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)

    def test_variation_totale_demi(self) -> None:
        assert total_variation_distance([0.6, 0.4], [0.4, 0.6]) == pytest.approx(0.2)


class TestAccuracyTop:
    """Exactitude de la classe la plus probable (§12.1)."""

    def test_top_classe(self) -> None:
        assert accuracy_top([0.1, 0.7, 0.2], 1) == 1.0
        assert accuracy_top([0.1, 0.7, 0.2], 0) == 0.0
