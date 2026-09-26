#!/usr/bin/env python3
"""Analyse de puissance — §11.3 du protocole v2.0.0 (pré-enregistrement).

Endpoint primaire : log loss 1X2 (décision manifeste `primary_metrics`).
Test figé : différence appariée par match (moyenne des snapshots du match),
bootstrap cluster percentile par match (≥ 2 000 réplications, §12.5),
Holm-Bonferroni intra-famille (4 familles = une par cible ; la famille 1X2
contient m = 6 comparaisons Laya vs chaque baseline, agents/evaluator.py).

Méthode :
  1. Puissance exacte sous hypothèses gaussiennes de planification via la loi
     t non centrale (le bootstrap percentile du test est asymptotiquement
     équivalent au test t sur moyennes par match).
  2. Validation Monte-Carlo du test RÉEL (bootstrap cluster percentile,
     vecteur de différences appariées simulées au niveau snapshot avec effet
     aléatoire par match), incluant un miroir de src/core/stats.py.
  3. MDE (effet minimal détectable) à puissance 80 % et 90 % par scénario.

Hypothèses de planification (grille de sensibilité) :
  - sigma_d : écart-type de la différence appariée de log loss par snapshot
    (0,15 en planification ; 0,10–0,20 en sensibilité) ;
  - rho : corrélation intra-match des différences entre snapshots
    (0,30 ; 0,20–0,50) ;
  - K : nombre moyen de snapshots par match (12 en planification — conservateur,
    7 cutoffs fixes + événements ; 8–16 en sensibilité) ;
  - n : nombre de matchs de test (corpus figé ≈ 2 403 matchs, split
    chronologique 50/50 par compétition → ≈ 1 200 ; 600 = scénario dégradé
    après exclusions, 1 800 = borne haute).

Sortie : JSON (docs/power_analysis.json) + tableau lisible stdout.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.core.stats import bootstrap_difference  # noqa: E402

try:
    from scipy import stats as sps
except ImportError as exc:  # pragma: no cover
    raise SystemExit("scipy requis : pip install scipy") from exc

ALPHA = 0.05
M_FAMILY = 6          # comparaisons Laya vs 6 baselines dans la famille 1X2
N_GRID = [600, 1200, 1800]
DELTA_GRID = [0.005, 0.01, 0.015, 0.02, 0.03]
PLANNING = {"sigma": 0.15, "rho": 0.30, "K": 12}
SENSITIVITY = [
    {"sigma": 0.10, "rho": 0.30, "K": 12},
    {"sigma": 0.20, "rho": 0.30, "K": 12},
    {"sigma": 0.15, "rho": 0.20, "K": 12},
    {"sigma": 0.15, "rho": 0.50, "K": 12},
    {"sigma": 0.15, "rho": 0.30, "K": 8},
    {"sigma": 0.15, "rho": 0.30, "K": 16},
]
SEED = 20260925


def sigma_eff(sigma: float, rho: float, K: int) -> float:
    """Écart-type de la moyenne par match d'une différence appariée."""
    return sigma * math.sqrt(rho + (1.0 - rho) / K)


def power_nct(n: int, delta: float, sigma: float, rho: float, K: int,
              alpha: float = ALPHA, m: int = M_FAMILY) -> float:
    """Puissance du test (bootstrap percentile ≈ t) au plancher Holm alpha/m."""
    a2 = alpha / (2.0 * m)
    tcrit = sps.t.ppf(1.0 - a2, df=n - 1)
    ncp = delta * math.sqrt(n) / sigma_eff(sigma, rho, K)
    return float(sps.nct.sf(tcrit, df=n - 1, nc=ncp)
                 + sps.nct.cdf(-tcrit, df=n - 1, nc=ncp))


def mde(n: int, target: float, sigma: float, rho: float, K: int) -> float:
    """Effet minimal détectable à la puissance cible (inversion par bissection)."""
    lo, hi = 0.0, 0.5
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if power_nct(n, mid, sigma, rho, K) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def simulate_snapshots(n: int, K: int, delta: float, sigma: float,
                       rho: float, rng) -> np.ndarray:
    """Différences appariées par snapshot avec effet aléatoire par match."""
    var_match = rho * sigma * sigma
    var_res = (1.0 - rho) * sigma * sigma
    mu = rng.normal(0.0, math.sqrt(var_match), size=n)
    eps = rng.normal(0.0, math.sqrt(var_res), size=(n, K))
    return delta + mu[:, None] + eps


def mc_power(n: int, K: int, delta: float, sigma: float, rho: float,
             sims: int = 300, replicates: int = 2000,
             seed: int = SEED) -> dict:
    """Monte-Carlo du test réel : bootstrap cluster percentile au plancher Holm."""
    rng = np.random.default_rng(seed)
    a2 = ALPHA / (2.0 * M_FAMILY)
    reject = 0
    for _ in range(sims):
        d = simulate_snapshots(n, K, delta, sigma, rho, rng)
        match_means = d.mean(axis=1)
        idx = rng.integers(0, n, size=(replicates, n))
        boot = match_means[idx].mean(axis=1)
        lo, hi = np.percentile(boot, [100.0 * a2, 100.0 * (1.0 - a2)])
        if lo > 0.0:            # rejet directionnel : intervalle entièrement > 0
            reject += 1
    se = math.sqrt(max(reject, 1) / sims * (1 - reject / sims) / sims)
    return {"power": reject / sims, "sims": sims, "mc_se": se,
            "replicates": replicates}


def mirror_validation() -> dict:
    """Miroir : mêmes données, CI bootstrap du dépôt vs implémentation vectorisée."""
    rng = np.random.default_rng(SEED)
    n, K = 200, 12
    d = simulate_snapshots(n, K, 0.02, 0.15, 0.30, rng)
    match_means = d.mean(axis=1)          # différence appariée par match (Δ inclus)
    per_match_a = {f"m{i}": float(v) for i, v in enumerate(match_means)}
    per_match_b = {f"m{i}": 0.0 for i in range(n)}
    repo = bootstrap_difference(per_match_a, per_match_b,
                                replicates=2000, seed=SEED,
                                alpha=ALPHA / M_FAMILY)
    idx = np.random.default_rng(SEED).integers(0, n, size=(2000, n))
    boot = match_means[idx].mean(axis=1)
    a2 = ALPHA / (2.0 * M_FAMILY)
    mine = (float(np.percentile(boot, 100.0 * a2)),
            float(np.percentile(boot, 100.0 * (1.0 - a2))))
    return {"repo_ci": [repo["ci_low"], repo["ci_high"]],
            "vectorized_ci": list(mine),
            "mean_diff_repo": repo["mean_difference"],
            "mean_diff_vec": float(match_means.mean())}


def main() -> None:
    out: dict = {"alpha": ALPHA, "m_family": M_FAMILY, "planning": PLANNING,
                 "n_grid": N_GRID, "delta_grid": DELTA_GRID}

    # 1. Puissance — scénario de planification
    out["power_planning"] = {
        f"n={n}": {f"delta={d}": round(power_nct(n, d, **PLANNING), 4)
                   for d in DELTA_GRID}
        for n in N_GRID
    }

    # 2. MDE 80 % / 90 % — planification + sensibilité (à n = 1200)
    out["mde_planning"] = {
        f"n={n}": {"power80": round(mde(n, 0.80, **PLANNING), 4),
                   "power90": round(mde(n, 0.90, **PLANNING), 4)}
        for n in N_GRID
    }
    out["mde_sensitivity_n1200"] = {
        f"sigma={s['sigma']},rho={s['rho']},K={s['K']}":
            {"power80": round(mde(1200, 0.80, **s), 4),
             "power90": round(mde(1200, 0.90, **s), 4)}
        for s in SENSITIVITY
    }

    # 3. Validation Monte-Carlo du test réel (n = 1200, planification)
    mc = {f"delta={d}": mc_power(1200, PLANNING["K"], d,
                                PLANNING["sigma"], PLANNING["rho"])
          for d in (0.005, 0.01, 0.02)}
    for d in mc:
        mc[d]["power_exact_nct"] = round(power_nct(1200, float(d.split("=")[1]),
                                                   **PLANNING), 4)
    out["mc_validation_n1200"] = mc

    # 4. Miroir dépôt
    out["mirror_validation"] = mirror_validation()

    # 5. Traduction en nombre de snapshots / matchs (documentation)
    out["corpus"] = {
        "matches_total": 2403, "test_matches_expected": 1201,
        "snapshots_per_match_planning": PLANNING["K"],
        "test_snapshots_expected": PLANNING["K"] * 1201,
    }

    dest = REPO / "docs" / "power_analysis.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")

    print("=== Analyse de puissance (log loss 1X2, Holm m=6, alpha=0.05) ===\n")
    print("Puissance — scénario de planification (sigma=0.15, rho=0.30, K=12)")
    hdr = "  n     " + "".join(f"Δ={d:<7}" for d in DELTA_GRID)
    print(hdr)
    for n in N_GRID:
        row = f"  {n:<6}"
        for d in DELTA_GRID:
            row += f"{power_nct(n, d, **PLANNING):<9.3f}"
        print(row)
    print("\nMDE (planification)")
    for n in N_GRID:
        print(f"  n={n:<5} 80% → {out['mde_planning'][f'n={n}']['power80']:.4f}"
              f"   90% → {out['mde_planning'][f'n={n}']['power90']:.4f}")
    print("\nMDE — sensibilité (n=1200)")
    for k, v in out["mde_sensitivity_n1200"].items():
        print(f"  {k:<28} 80% → {v['power80']:.4f}  90% → {v['power90']:.4f}")
    print("\nValidation Monte-Carlo (n=1200, 300 sims × 2000 réplications)")
    for k, v in mc.items():
        print(f"  {k:<10} MC={v['power']:.3f} (±{v['mc_se']:.3f})  "
              f"exact t non central={v['power_exact_nct']:.3f}")
    mv = out["mirror_validation"]
    print(f"\nMiroir dépôt vs vectorisé (Δ=0.02, n=200) : "
          f"repo CI [{mv['repo_ci'][0]:.4f}, {mv['repo_ci'][1]:.4f}] vs "
          f"vec CI [{mv['vectorized_ci'][0]:.4f}, {mv['vectorized_ci'][1]:.4f}]")
    print(f"\nRésultats écrits : {dest}")


if __name__ == "__main__":
    main()
