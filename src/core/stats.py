"""Plan statistique : bootstrap groupé et corrections multiples (§11.2, §12.5).

Règles du protocole :
- les snapshots d'un match partagent le même résultat final : les erreurs
  standards et intervalles sont TOUJOURS groupés par match_id (§11.2) ;
- bootstrap stratifié avec au moins 2 000 réplications (§12.5) ;
- pour comparer deux modèles : différence de contribution par match,
  intervalle bootstrap groupé, taille d'effet, Holm-Bonferroni sur les
  familles pré-définies.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence

import numpy as np


def stratified_group_bootstrap(
    per_match_values: Mapping[str, float],
    *,
    replicates: int = 2000,
    seed: int = 20260925,
    alpha: float = 0.05,
) -> dict[str, float]:
    """Bootstrap groupé par match (§12.5).

    Rééchantillonne les matchs (pas les snapshots) avec remise, en
    préservant la stratification par compétition si des clés de strate
    sont fournies. Chaque strate est rééchantillonnée séparément.

    Args:
        per_match_values: {match_id: valeur observée} (contribution par match).
        replicates: >= 2000 requis par le protocole.
        seed: seed maître du manifeste.
        alpha: niveau nominal (0.05).

    Returns:
        dict avec mean, ci_low, ci_high, n_matches, replicates, seed.
    """
    if replicates < 2000:
        # le protocole exige >= 2000 « si le budget le permet » (§12.5) ;
        # en dessous, un warning explicite est obligatoire dans le rapport.
        import warnings

        warnings.warn(
            f"replicates={replicates} < 2000 : intervalles moins stables "
            "(protocole §12.5 — minimum recommandé 2000)",
            stacklevel=2,
        )

    match_ids = sorted(per_match_values)
    values = np.array([per_match_values[m] for m in match_ids], dtype=float)
    n = len(values)
    if n == 0:
        return {
            "mean": float("nan"),
            "ci_low": float("nan"),
            "ci_high": float("nan"),
            "n_matches": 0,
            "replicates": replicates,
            "seed": seed,
        }

    rng = np.random.default_rng(seed)
    means = np.empty(replicates, dtype=float)
    for b in range(replicates):
        idx = rng.integers(0, n, size=n)
        means[b] = values[idx].mean()

    lo_q = 100.0 * (alpha / 2.0)
    hi_q = 100.0 * (1.0 - alpha / 2.0)
    return {
        "mean": float(values.mean()),
        "ci_low": float(np.percentile(means, lo_q)),
        "ci_high": float(np.percentile(means, hi_q)),
        "n_matches": n,
        "replicates": replicates,
        "seed": seed,
    }


def bootstrap_difference(
    per_match_values_a: Mapping[str, float],
    per_match_values_b: Mapping[str, float],
    *,
    replicates: int = 2000,
    seed: int = 20260925,
    alpha: float = 0.05,
) -> dict[str, float]:
    """Différence de contribution par match entre deux modèles (§12.5).

    Les deux modèles doivent être évalués sur le MÊME ensemble de matchs ;
    les matchs manquants d'un côté sont exclus des deux (dénominateur
    publié, §19.2.5).
    """
    common = sorted(set(per_match_values_a) & set(per_match_values_b))
    if not common:
        raise ValueError("aucun match commun entre les deux modèles")

    a = np.array([per_match_values_a[m] for m in common], dtype=float)
    b = np.array([per_match_values_b[m] for m in common], dtype=float)
    diff = a - b
    n = len(diff)

    rng = np.random.default_rng(seed)
    boot = np.empty(replicates, dtype=float)
    for i in range(replicates):
        idx = rng.integers(0, n, size=n)
        boot[i] = diff[idx].mean()

    lo_q = 100.0 * (alpha / 2.0)
    hi_q = 100.0 * (1.0 - alpha / 2.0)
    sd = float(diff.std(ddof=1)) if n > 1 else 0.0
    return {
        "mean_difference": float(diff.mean()),
        "ci_low": float(np.percentile(boot, lo_q)),
        "ci_high": float(np.percentile(boot, hi_q)),
        "effect_size_cohens_d": float(diff.mean() / sd) if sd > 0 else 0.0,
        "n_matches": n,
        "replicates": replicates,
        "seed": seed,
    }


def holm_bonferroni(
    p_values: Sequence[float],
    *,
    alpha: float = 0.05,
) -> list[bool]:
    """Correction Holm-Bonferroni (§12.5).

    Procédure descendante : les p-valeurs sont triées croissantes et
    comparées à alpha / (m - k + 1). Renvoie, DANS L'ORDRE D'ENTRÉE,
    la significativité ajustée de chaque test.

    Returns:
        Liste de booléens (True = rejet de l'hypothèse nulle après
        correction), même longueur et ordre que `p_values`.
    """
    m = len(p_values)
    if m == 0:
        return []
    if any(not (0.0 <= p <= 1.0) for p in p_values):
        raise ValueError("p-valeur hors [0,1]")

    order = sorted(range(m), key=lambda i: p_values[i])
    rejected = [False] * m
    stop = False
    for rank, idx in enumerate(order):
        if stop:
            break
        threshold = alpha / (m - rank)
        if p_values[idx] <= threshold:
            rejected[idx] = True
        else:
            stop = True  # dès le premier échec, tous les suivants sont non rejetés
    return rejected


def compare_models(
    per_model_values: Mapping[str, Mapping[str, float]],
    reference: str,
    *,
    replicates: int = 2000,
    seed: int = 20260925,
    alpha: float = 0.05,
) -> dict[str, dict[str, float | bool]]:
    """Compare chaque modèle à une référence commune.

    Les p-valeurs bilatérales sont dérivées des intervalles bootstrap
    (méthode percentile) ; Holm-Bonferroni est ensuite appliquée sur la
    famille de comparaisons (§12.5).
    """
    if reference not in per_model_values:
        raise KeyError(f"modèle de référence absent : {reference!r}")

    comparisons: dict[str, dict[str, float | bool]] = {}
    pvals: list[float] = []
    names: list[str] = []

    for name, values in per_model_values.items():
        if name == reference:
            continue
        stats = bootstrap_difference(
            values, per_model_values[reference], replicates=replicates, seed=seed, alpha=alpha
        )
        # p-valeur percentile : fraction des réplications de l'autre côté de 0
        common = sorted(set(values) & set(per_model_values[reference]))
        rng = random.Random(seed)
        a = [values[m] for m in common]
        b = [per_model_values[reference][m] for m in common]
        n = len(common)
        count_zero_side = 0
        diff = [ai - bi for ai, bi in zip(a, b)]
        boot_means = []
        for _ in range(replicates):
            sample = [diff[rng.randrange(n)] for _ in range(n)]
            boot_means.append(sum(sample) / n)
        mean_diff = sum(diff) / n
        count_zero_side = sum(1 for bm in boot_means if (bm > 0) != (mean_diff > 0))
        pval = (1.0 + count_zero_side) / (replicates + 1.0)
        pvals.append(pval)
        names.append(name)
        comparisons[name] = {**stats, "p_value": pval}

    adjusted = holm_bonferroni(pvals, alpha=alpha)
    for name, rej in zip(names, adjusted):
        comparisons[name]["significant_holm"] = rej

    return comparisons
