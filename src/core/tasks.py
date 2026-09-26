"""Tâches typées et support des cibles (protocole §8).

Les noms, l'ordre des catégories et la formulation exacte des questions sont
versionnés : toute modification crée une nouvelle version de tâche (§8.5).
"""

from __future__ import annotations

import json
import math
from typing import Any

from src.core.errors import ErrorCode, ValidationError

# --- Cibles (définitions figées, annexe B) -------------------------------

SCORE_BUCKET_CAP = 3
"""Tout score dont au moins une composante dépasse 3 est mappé vers `other`."""

SCORE_BUCKETS: list[str] = [
    f"{h}-{a}"
    for h in range(SCORE_BUCKET_CAP + 1)
    for a in range(SCORE_BUCKET_CAP + 1)
] + ["other"]

CORNER_LEVELS: list[str] = [str(i) for i in range(21)] + ["21+"]
YELLOW_LEVELS: list[str] = [str(i) for i in range(13)] + ["13+"]

# Marginales de buts pour l'analyse à plus haute résolution (§8.2)
GOAL_MARGINALS: dict[str, list[str]] = {
    "home_goals": [str(i) for i in range(8)] + ["8+"],
    "away_goals": [str(i) for i in range(8)] + ["8+"],
}

# Tâches cibles pour les métriques ordonnées (RPS)
OUTCOME_1X2 = ["1", "X", "2"]


def score_to_bucket(home_goals: int, away_goals: int) -> str:
    """Mappe un score exact vers son bucket (17 catégories, §8.2)."""
    if home_goals > SCORE_BUCKET_CAP or away_goals > SCORE_BUCKET_CAP:
        return "other"
    return f"{home_goals}-{away_goals}"


def corners_to_level(total_corners: int) -> str:
    """Mappe un total de corners vers son niveau (0..20, 21+, §8.3)."""
    return "21+" if total_corners >= 21 else str(total_corners)


def yellows_to_level(total_yellow_cards: int) -> str:
    """Mappe un total de cartons jaunes vers son niveau (0..12, 13+, §8.4)."""
    return "13+" if total_yellow_cards >= 13 else str(total_yellow_cards)


# --- Questions canoniques v1 (§8.5) ----------------------------------------

SCORE_BUCKET_CRITERIA = SCORE_BUCKETS  # ordre figé

QUESTIONS_V1: dict[str, dict[str, Any]] = {
    "score_bucket": {
        "type": "choice",
        "instructions": "What is the final score category of this football match?",
        "criteria": SCORE_BUCKET_CRITERIA,
    },
    "total_corners": {
        "type": "score",
        "instructions": "What will be the total number of corners in the match?",
        "criteria": CORNER_LEVELS,
    },
    "total_yellow_cards": {
        "type": "score",
        "instructions": "What will be the total number of yellow cards in the match?",
        "criteria": YELLOW_LEVELS,
    },
}

TASK_TARGETS = {
    "score_bucket": "score_bucket",
    "total_corners": "corners",
    "total_yellow_cards": "yellow_cards",
}


# --- Validateur de réponse (§8.6) ------------------------------------------

# Tolérance de somme imposée par le protocole
PROB_SUM_TOLERANCE = 1e-6


def parse_raw_response(raw_text: str) -> dict[str, Any]:
    """Étape 1 : vérifier que la réponse est du JSON valide."""
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValidationError(ErrorCode.INVALID_JSON, str(exc)) from exc
    if not isinstance(parsed, dict):
        raise ValidationError(ErrorCode.INVALID_SCHEMA, "la racine n'est pas un objet")
    return parsed


def validate_distribution(
    parsed: dict[str, Any],
    task: str,
    *,
    allow_keys: tuple[str, ...] = ("probabilities",),
) -> dict[str, float]:
    """Valide la distribution d'une tâche typée selon §8.6.

    Étapes : 2 (clés), 3 (probabilités finies dans [0,1]),
    4 (somme = 1 à 1e-6 près), 5 (ni catégorie manquante ni dupliquée),
    6 (cohérence de l'espérance avec la convention de queue).

    Returns:
        Distribution normalisée {categorie: probabilité} — sans jamais
        renormaliser les probabilités (interdit, §8.6).

    Raises:
        ValidationError: avec le code exact du protocole.
    """
    questions = QUESTIONS_V1[task]
    criteria = questions["criteria"]

    # 2 — clés attendues et uniquement les clés documentées
    unexpected = set(parsed) - set(allow_keys)
    missing = set(allow_keys) - set(parsed)
    if unexpected or missing:
        raise ValidationError(
            ErrorCode.INVALID_SCHEMA,
            f"clés inattendues={sorted(unexpected)} manquantes={sorted(missing)}",
        )

    raw_dist = parsed["probabilities"]
    if not isinstance(raw_dist, dict):
        raise ValidationError(ErrorCode.INVALID_SCHEMA, "probabilities n'est pas un objet")

    # 5 — catégories : présentes, uniques, exactement celles attendues
    keys = list(raw_dist.keys())
    if len(keys) != len(set(keys)):
        raise ValidationError(ErrorCode.MISSING_CATEGORY, "catégories dupliquées")
    if set(keys) != set(criteria):
        missing_cat = sorted(set(criteria) - set(keys))
        extra_cat = sorted(set(keys) - set(criteria))
        raise ValidationError(
            ErrorCode.MISSING_CATEGORY,
            f"manquantes={missing_cat} inconnues={extra_cat}",
        )

    # 3 — chaque probabilité finie, dans [0, 1]
    dist: dict[str, float] = {}
    for cat in criteria:  # ordre canonique figé
        value = raw_dist[cat]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(
                ErrorCode.INVALID_PROBABILITY, f"{cat}: valeur non numérique {value!r}"
            )
        v = float(value)
        if not math.isfinite(v) or not (0.0 <= v <= 1.0):
            raise ValidationError(
                ErrorCode.INVALID_PROBABILITY, f"{cat}: hors [0,1] ({v})"
            )
        dist[cat] = v

    # 4 — somme à 1 à 1e-6 près ; renormalisation interdite
    total = sum(dist.values())
    if abs(total - 1.0) > PROB_SUM_TOLERANCE:
        raise ValidationError(
            ErrorCode.INVALID_PROBABILITY_SUM, f"somme={total!r} (tolérance 1e-6)"
        )

    # 6 — cohérence de l'espérance avec la convention de queue
    expected = parsed.get("expected_value")
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        exp_from_dist = expected_value(dist, censored_tail=(task != "score_bucket"))
        if math.isfinite(float(expected)) and abs(float(expected) - exp_from_dist) > 0.51:
            raise ValidationError(
                ErrorCode.INVALID_SCHEMA,
                f"expected_value={expected} incohérent avec la distribution ({exp_from_dist:.3f})",
            )

    return dist


def expected_value(dist: dict[str, float], *, censored_tail: bool = True) -> float:
    """Espérance d'une distribution sur des niveaux ordonnés avec queue.

    Convention de queue (§8.3, §8.4) : `21+`/`13+` sont censurés — la masse
    de queue est comptée au seuil (valeur inférieure de l'intervalle). Une
    espérance dérivée ainsi est dite censurée et ne doit jamais être
    présentée comme une espérance non censurée.
    """
    acc = 0.0
    for cat, p in dist.items():
        if cat.endswith("+"):
            threshold = int(cat[:-1])
            acc += threshold * p  # valeur censurée = seuil
        elif cat == "other":
            # Pas d'ordre naturel : aucune contribution à l'espérance
            continue
        else:
            if "-" in cat:  # bucket de score "h-a"
                h, a = cat.split("-")
                acc += (int(h) + int(a)) * p
            else:
                acc += int(cat) * p
    return acc + 0.0


def score_bucket_to_1x2(dist: dict[str, float]) -> dict[str, float]:
    """Dérive le 1X2 de la distribution de score (§8.1).

    P(1) = somme P(h, a) pour h > a ; P(X) = somme pour h = a ; P(2) = h < a.
    `other` ne contribue à aucune catégorie (règle conservatrice documentée).
    """
    p1 = px = p2 = 0.0
    for cat, p in dist.items():
        if cat == "other":
            continue
        h, a = (int(x) for x in cat.split("-"))
        if h > a:
            p1 += p
        elif h == a:
            px += p
        elif h < a:
            p2 += p
    return {"1": p1, "X": px, "2": p2}


def bucket_order_1x2() -> list[str]:
    """Ordre canonique des catégories 1X2 (pour RPS)."""
    return list(OUTCOME_1X2)


def order_for_task(task: str) -> list[str]:
    """Ordre des catégories d'une tâche (pour RPS si un ordre cohérent existe)."""
    if task == "score_bucket":
        return list(SCORE_BUCKETS)
    if task == "total_corners":
        return list(CORNER_LEVELS)
    if task == "total_yellow_cards":
        return list(YELLOW_LEVELS)
    raise KeyError(f"tâche inconnue : {task}")
