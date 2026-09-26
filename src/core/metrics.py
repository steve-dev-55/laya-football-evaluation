"""Métriques d'évaluation (protocole §12).

Conventions :
- log loss multiclass avec plancher epsilon = 1e-15 (§12.1) ;
- Brier multiclass, RPS (1X2 ordonné), ECE avec bins annoncés ;
- CRPS discret, log score discret, PIT randomisé pour les comptages (§12.3) ;
- couverture d'intervalles prédictifs à 50 %, 80 %, 95 %.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

EPS = 1e-15
"""Plancher de probabilité imposé par le protocole §12.1."""


def _check_dist(dist: Sequence[float]) -> None:
    if not dist:
        raise ValueError("distribution vide")
    for p in dist:
        if not math.isfinite(p) or p < 0 or p > 1:
            raise ValueError(f"probabilité invalide : {p}")


def log_loss(dist: Sequence[float], outcome_index: int, *, eps: float = EPS) -> float:
    """Log loss multiclass pour une observation (§12.1).

    Args:
        dist: probabilités dans l'ordre canonique des catégories.
        outcome_index: indice de la catégorie réalisée.
        eps: plancher de probabilité (1e-15).
    """
    _check_dist(dist)
    if not (0 <= outcome_index < len(dist)):
        raise ValueError(f"indice de réalisation hors bornes : {outcome_index}")
    p = max(dist[outcome_index], eps)
    return -math.log(p)


def brier_multiclass(dist: Sequence[float], outcome_index: int) -> float:
    """Score de Brier multiclass (somme des carrés, §12.1)."""
    _check_dist(dist)
    return sum(
        (p - (1.0 if i == outcome_index else 0.0)) ** 2 for i, p in enumerate(dist)
    )


def rps(dist: Sequence[float], outcome_index: int) -> float:
    """Ranked Probability Score pour cible ordonnée (§12.1).

    RPS = somme des erreurs quadratiques des probabilités cumulées.
    """
    _check_dist(dist)
    n = len(dist)
    if not (0 <= outcome_index < n):
        raise ValueError("indice hors bornes")
    cum_p = 0.0
    cum_o = 0.0
    score = 0.0
    for i in range(n - 1):  # dernier terme toujours nul
        cum_p += dist[i]
        cum_o += 1.0 if i == outcome_index else 0.0
        score += (cum_p - cum_o) ** 2
    return score / (n - 1)


def accuracy_top(dist: Sequence[float], outcome_index: int) -> float:
    """1.0 si la catégorie la plus probable est la catégorie réalisée (§12.1)."""
    _check_dist(dist)
    best = max(range(len(dist)), key=lambda i: dist[i])
    return 1.0 if best == outcome_index else 0.0


def ece(
    observations: Sequence[tuple[float, int]],
    *,
    n_bins: int = 15,
    binning: str = "equal-width",
) -> float:
    """Expected Calibration Error (§12.4).

    Args:
        observations: paires (probabilité prédite de la classe réalisée,
            réalisation 0/1 de la correction).
        n_bins: nombre de bins — figé dans le manifeste (annexe B).
        binning: `equal-width` (figé) ou `quantile` (sensibilité).
    """
    if not observations:
        return float("nan")
    if binning == "quantile":
        # sensibilité par quantiles — méthode documentée (§12.4)
        import numpy as np

        probs = np.array([p for p, _ in observations], dtype=float)
        qs = np.quantile(probs, np.linspace(0, 1, n_bins + 1))
        edges = np.unique(qs)
        n_bins = max(len(edges) - 1, 1)
        bin_index = np.clip(np.searchsorted(edges[1:-1], probs), 0, n_bins - 1)
        bin_ids = bin_index.tolist()
        edges_final = edges.tolist()
    else:
        edges_final = [i / n_bins for i in range(n_bins + 1)]
        bin_ids = [
            min(int(p * n_bins), n_bins - 1) for p, _ in observations
        ]

    total = len(observations)
    acc = 0.0
    for b in range(n_bins):
        members = [obs for obs, bid in zip(observations, bin_ids, strict=False) if bid == b]
        if not members:
            continue
        conf = sum(p for p, _ in members) / len(members)
        freq = sum(o for _, o in members) / len(members)
        acc += len(members) / total * abs(freq - conf)
    _ = edges_final
    return acc


def mae(expected: float, actual: float) -> float:
    """Erreur absolue moyenne — cas unitaire (§12.3)."""
    return abs(expected - actual)


def rmse(errors: Sequence[float]) -> float:
    """Racine de l'erreur quadratique moyenne (§12.3)."""
    if not errors:
        return float("nan")
    return math.sqrt(sum(e * e for e in errors) / len(errors))


def crps_discrete(dist: dict[str, float], actual_level: int) -> float:
    """CRPS pour une distribution discrète ordonnée avec queue censurée (§12.3).

    dist: {niveau: probabilité} avec une clé de queue `N+` éventuelle,
    traitée au seuil N (convention censurée).
    actual_level: valeur observée censurée de la même façon.
    """
    if not dist:
        raise ValueError("distribution vide")
    xs: list[float] = []
    ps: list[float] = []
    for cat in sorted(dist, key=lambda c: int(c.rstrip("+"))):
        p = dist[cat]
        x = float(cat.rstrip("+"))
        if xs and xs[-1] == x:  # sécurité anti-dupliqué
            ps[-1] += p
        else:
            xs.append(x)
            ps.append(p)
    n = len(xs)
    score = 0.0
    for i in range(n - 1):
        # masse cumulative au-delà du support observé
        cdf_hi = sum(p for x, p in zip(xs, ps, strict=False) if x <= xs[i])
        cdf_obs = 1.0 if xs[i] >= actual_level else 0.0
        score += (xs[i + 1] - xs[i]) * (cdf_hi - cdf_obs) ** 2
    return score


def log_score_discrete(dist: dict[str, float], actual_category: str) -> float:
    """Log score discret sur les niveaux (§12.3), plancher EPS."""
    if actual_category not in dist:
        raise ValueError(f"catégorie réalisée absente : {actual_category!r}")
    return -math.log(max(dist[actual_category], EPS))


def pit_randomized(dist: dict[str, float], actual_level: int, *, u: float) -> float:
    """PIT randomisé pour variable discrète (§12.3).

    Args:
        u: tirage uniforme U(0,1) fourni par l'appelant (seed maître du run).
    """
    if not (0.0 <= u <= 1.0):
        raise ValueError("u doit être dans [0,1]")
    levels = sorted((float(c.rstrip("+")), c) for c in dist)
    p_le = 0.0
    for x, cat in levels:
        if x < actual_level:
            p_le += dist[cat]
        elif x == actual_level:
            p_le += dist[cat] * u
            break
        else:
            break
    return p_le


def predictive_interval_coverage(
    dist: dict[str, float],
    actual_level: int,
    levels: Sequence[int] = (50, 80, 95),
) -> dict[int, float]:
    """Couverture empirique des intervalles prédictifs (§12.3).

    L'intervalle central à L % est l'ensemble des niveaux dont la masse
    cumulée autour de la médine couvre L % ; renvoie {L: 0/1}.
    """
    if not dist:
        raise ValueError("distribution vide")
    ordered = sorted(dist.items(), key=lambda kv: float(kv[0].rstrip("+")))
    xs = [float(c.rstrip("+")) for c, _ in ordered]
    ps = [p for _, p in ordered]
    total = sum(ps)
    if total <= 0:
        raise ValueError("distribution de masse nulle")

    # médiane
    cum = 0.0
    median = xs[-1]
    for x, p in zip(xs, ps, strict=False):
        cum += p
        if cum >= 0.5 * total:
            median = x
            break

    result: dict[int, float] = {}
    for lvl in levels:
        target = lvl / 100.0
        # extension symétrique autour de la médiane jusqu'à couvrir target
        acc = 0.0
        covered = False
        lo_i = hi_i = xs.index(median)
        acc += ps[lo_i]
        if actual_level == xs[lo_i] and acc >= target - 1e-12:
            covered = True
        while acc < target and (lo_i > 0 or hi_i < len(xs) - 1):
            # étendre du côté le plus proche de la médiane
            if lo_i > 0 and (hi_i >= len(xs) - 1 or
                             abs(xs[lo_i - 1] - median) <= abs(xs[hi_i + 1] - median)):
                lo_i -= 1
                acc += ps[lo_i]
            else:
                hi_i += 1
                acc += ps[hi_i]
            if xs[lo_i] <= actual_level <= xs[hi_i]:
                covered = True
                break
        result[lvl] = 1.0 if covered else 0.0
    return result


def tail_mass(dist: dict[str, float]) -> float:
    """Taux de masse dans la queue `21+` ou `13+` (§12.3)."""
    return sum(p for cat, p in dist.items() if cat.endswith("+"))


def jensen_shannon_distance(p: Sequence[float], q: Sequence[float]) -> float:
    """Distance de Jensen-Shannon (robustesse, §13.1)."""
    if len(p) != len(q):
        raise ValueError("distributions de longueurs différentes")
    import numpy as np

    a = np.clip(np.asarray(p, dtype=float), 0, 1)
    b = np.clip(np.asarray(q, dtype=float), 0, 1)
    m = 0.5 * (a + b)
    from scipy.stats import entropy

    return float(0.5 * entropy(a, m) + 0.5 * entropy(b, m))


def total_variation_distance(p: Sequence[float], q: Sequence[float]) -> float:
    """Distance en variation totale (robustesse, §13.1)."""
    if len(p) != len(q):
        raise ValueError("distributions de longueurs différentes")
    return 0.5 * sum(abs(pi - qi) for pi, qi in zip(p, q, strict=False))
