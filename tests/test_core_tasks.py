"""Tests des tâches typées et du validateur de réponse (protocole §8).

Vérifie : 17 buckets / 22 corners / 14 jaunes ; validate_distribution
(acceptation + tous les codes de rejet, SANS renormalisation) ; frontières
de score_to_bucket ; dérivation 1X2.
"""

from __future__ import annotations

import math

import pytest

from src.core.errors import ErrorCode, ValidationError
from src.core.tasks import (
    CORNER_LEVELS,
    QUESTIONS_V1,
    SCORE_BUCKETS,
    YELLOW_LEVELS,
    corners_to_level,
    expected_value,
    parse_raw_response,
    score_bucket_to_1x2,
    score_to_bucket,
    validate_distribution,
    yellows_to_level,
)


def _uniform(criteria: list[str]) -> dict[str, float]:
    """Distribution uniforme valide sur les critères."""
    return {cat: 1.0 / len(criteria) for cat in criteria}


def _task_payload(task: str, dist: dict[str, float]) -> dict[str, dict]:
    return {"probabilities": dist}


class TestGrilleDesCibles:
    """Tailles exactes des grilles (§8.1–§8.4)."""

    def test_17_buckets_de_score(self) -> None:
        assert len(SCORE_BUCKETS) == 17
        assert SCORE_BUCKETS[-1] == "other"
        assert "3-3" in SCORE_BUCKETS

    def test_22_niveaux_de_corners(self) -> None:
        assert len(CORNER_LEVELS) == 22
        assert CORNER_LEVELS[-1] == "21+"
        assert CORNER_LEVELS[0] == "0"

    def test_14_niveaux_de_cartons(self) -> None:
        assert len(YELLOW_LEVELS) == 14
        assert YELLOW_LEVELS[-1] == "13+"

    def test_questions_v1_coherentes(self) -> None:
        assert QUESTIONS_V1["score_bucket"]["criteria"] == SCORE_BUCKETS
        assert QUESTIONS_V1["total_corners"]["criteria"] == CORNER_LEVELS
        assert QUESTIONS_V1["total_yellow_cards"]["criteria"] == YELLOW_LEVELS


class TestValidateDistribution:
    """Validateur §8.6 : étapes 1–5, codes exacts, aucune renormalisation."""

    def test_accepte_une_distribution_valide(self) -> None:
        for task, question in QUESTIONS_V1.items():
            dist = validate_distribution(
                _task_payload(task, _uniform(question["criteria"])), task
            )
            assert set(dist) == set(question["criteria"])
            assert abs(sum(dist.values()) - 1.0) <= 1e-6

    def test_accepte_somme_dans_la_tolerance(self) -> None:
        criteria = QUESTIONS_V1["total_yellow_cards"]["criteria"]
        dist = _uniform(criteria)
        dist["0"] += 4e-7  # |somme - 1| <= 1e-6 : accepté tel quel
        result = validate_distribution(_task_payload("total_yellow_cards", dist),
                                        "total_yellow_cards")
        assert math.isclose(sum(result.values()), 1.0, abs_tol=1e-6)

    def test_rejette_json_invalide(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            parse_raw_response("{ceci n'est pas du json")
        assert excinfo.value.code == ErrorCode.INVALID_JSON

    def test_rejette_racine_non_objet(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            parse_raw_response("[1, 2, 3]")
        assert excinfo.value.code == ErrorCode.INVALID_SCHEMA

    def test_rejette_cles_inattendues(self) -> None:
        criteria = QUESTIONS_V1["score_bucket"]["criteria"]
        payload = _task_payload("score_bucket", _uniform(criteria))
        payload["confidence"] = 0.9  # clé non documentée
        with pytest.raises(ValidationError) as excinfo:
            validate_distribution(payload, "score_bucket")
        assert excinfo.value.code == ErrorCode.INVALID_SCHEMA

    def test_rejette_cle_probabilities_absente(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            validate_distribution({"other": {}}, "score_bucket")
        assert excinfo.value.code == ErrorCode.INVALID_SCHEMA

    def test_rejette_proba_negative(self) -> None:
        criteria = QUESTIONS_V1["total_corners"]["criteria"]
        dist = _uniform(criteria)
        dist["3"] = -0.05
        dist["4"] += 0.05
        with pytest.raises(ValidationError) as excinfo:
            validate_distribution(_task_payload("total_corners", dist), "total_corners")
        assert excinfo.value.code == ErrorCode.INVALID_PROBABILITY

    def test_rejette_proba_nan(self) -> None:
        criteria = QUESTIONS_V1["total_corners"]["criteria"]
        dist = _uniform(criteria)
        dist["3"] = float("nan")
        with pytest.raises(ValidationError) as excinfo:
            validate_distribution(_task_payload("total_corners", dist), "total_corners")
        assert excinfo.value.code == ErrorCode.INVALID_PROBABILITY

    def test_rejette_proba_superieure_a_1(self) -> None:
        criteria = QUESTIONS_V1["total_corners"]["criteria"]
        dist = _uniform(criteria)
        dist["3"] = 1.2
        dist["4"] = 0.0
        with pytest.raises(ValidationError) as excinfo:
            validate_distribution(_task_payload("total_corners", dist), "total_corners")
        assert excinfo.value.code == ErrorCode.INVALID_PROBABILITY

    def test_rejette_somme_hors_tolerance_sans_renormalisation(self) -> None:
        criteria = QUESTIONS_V1["score_bucket"]["criteria"]
        dist = _uniform(criteria)
        dist["0-0"] += 0.01  # somme = 1.01 > 1e-6 : rejet, pas de réparation
        with pytest.raises(ValidationError) as excinfo:
            validate_distribution(_task_payload("score_bucket", dist), "score_bucket")
        assert excinfo.value.code == ErrorCode.INVALID_PROBABILITY_SUM
        # AUCUNE renormalisation ne doit avoir lieu : l'erreur est propagée.

    def test_rejette_categorie_manquante(self) -> None:
        criteria = QUESTIONS_V1["total_corners"]["criteria"]
        dist = _uniform(criteria)
        removed = dist.pop("5")
        dist["6"] += removed
        with pytest.raises(ValidationError) as excinfo:
            validate_distribution(_task_payload("total_corners", dist), "total_corners")
        assert excinfo.value.code == ErrorCode.MISSING_CATEGORY

    def test_rejette_categorie_inconnue(self) -> None:
        criteria = QUESTIONS_V1["total_corners"]["criteria"]
        dist = _uniform(criteria)
        dist["99"] = dist.pop("5")
        with pytest.raises(ValidationError) as excinfo:
            validate_distribution(_task_payload("total_corners", dist), "total_corners")
        assert excinfo.value.code == ErrorCode.MISSING_CATEGORY

    def test_rejette_cle_dupliquee_dans_le_texte_json(self) -> None:
        # Un texte JSON avec une clé dupliquée est réduit par json.loads au
        # dernier valeur : la somme dérive hors tolérance → rejet explicite,
        # jamais d'acceptation silencieuse d'une réponse malformée.
        import json

        criteria = QUESTIONS_V1["total_yellow_cards"]["criteria"]
        text = (
            '{"probabilities": {'
            + ", ".join(f'"{cat}": {1.0 / len(criteria)}' for cat in criteria)
            + ', "0": 0.07}}'
        )
        parsed = json.loads(text)
        assert len(parsed["probabilities"]) == len(criteria)
        with pytest.raises(ValidationError) as excinfo:
            validate_distribution(parsed, "total_yellow_cards")
        assert excinfo.value.code == ErrorCode.INVALID_PROBABILITY_SUM


class TestBornesEtConversions:
    """score_to_bucket, niveaux de comptage, 1X2 (§8.1, §8.2)."""

    def test_score_to_bucket_frontieres(self) -> None:
        assert score_to_bucket(0, 0) == "0-0"
        assert score_to_bucket(3, 3) == "3-3"  # dernier bucket dans la grille
        assert score_to_bucket(3, 0) == "3-0"
        assert score_to_bucket(0, 3) == "0-3"
        assert score_to_bucket(4, 0) == "other"  # hors grille
        assert score_to_bucket(0, 4) == "other"
        assert score_to_bucket(5, 7) == "other"

    def test_niveaux_de_comptage(self) -> None:
        assert corners_to_level(20) == "20"
        assert corners_to_level(21) == "21+"
        assert corners_to_level(28) == "21+"
        assert yellows_to_level(12) == "12"
        assert yellows_to_level(13) == "13+"

    def test_score_bucket_to_1x2(self) -> None:
        dist = {
            "1-0": 0.2,
            "2-1": 0.1,
            "0-1": 0.3,
            "1-1": 0.1,
            "other": 0.3,
        }
        one_x_two = score_bucket_to_1x2(dist)
        assert one_x_two == {"1": pytest.approx(0.3),
                             "X": pytest.approx(0.1),
                             "2": pytest.approx(0.3)}

    def test_expected_value_avec_queue_censuree(self) -> None:
        dist = {"0": 0.5, "1": 0.25, "21+": 0.25}
        # « 21+ » contribue au seuil (censure) : 0 + 0.25 + 21*0.25
        assert expected_value(dist) == pytest.approx(5.5)

    def test_expected_value_score_bucket_ignore_other(self) -> None:
        dist = {"1-0": 0.5, "2-2": 0.25, "other": 0.25}
        assert expected_value(dist, censored_tail=False) == pytest.approx(0.5 + 4 * 0.25)
