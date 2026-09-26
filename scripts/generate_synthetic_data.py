#!/usr/bin/env python3
"""Générateur de données synthétiques déterministes (protocole §0.2, §3).

Produit des documents bruts `data/raw/{competition}/{season}/matches.json`
100 % SYNTHÉTIQUES (aucune donnée réelle, aucune clé API) :
- pour la CI et les tests (tests/helpers.py réutilise ce module) ;
- pour l'exécution de démonstration `scripts/run_pipeline.sh`.

Déterminisme (§0.4) : RNG unique seedé (20260925 par défaut) et bloc
`source.retrieved_at` constant — deux exécutions produisent des octets
identiques, donc des hashes SHA-256 stables.

Cohérence garantie avec les contrôles de l'agent nettoyeur (§3.3–§3.5) :
- statut « finished », horodatages valides, date_utc = jour du kickoff ;
- nombre de buts = nombre d'événements « goal » par camp ;
- jaunes/rouges = nombre d'événements correspondants ;
- la dernière statistique cumulative de corners totalise le total officiel.

Usage :
    python3 scripts/generate_synthetic_data.py [--config configs/experiment.yaml]
        [--seed 20260925] [--matches-per-season 8] [--out-dir data/raw]
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

SEED = 20260925
"""Seed maître du manifeste (annexe A) — détermine tout le jeu synthétique."""

FIXED_RETRIEVED_AT = "2026-09-25T00:00:00Z"
"""Date de récupération CONSTANTTE : garantit des fichiers byte-identiques."""

TEAM_POOL: tuple[str, ...] = (
    "Alpha FC", "Beta United", "Gamma City", "Delta Rovers",
    "Epsilon SC", "Zeta Athletic", "Eta Wanderers", "Theta Albion",
)

SEASON_KICKOFF: dict[str, tuple[int, int, int]] = {
    "2021-2022": (2021, 8, 14),
    "2022-2023": (2022, 8, 13),
    "2023-2024": (2023, 8, 12),
}

COMPETITION_HOUR: dict[str, int] = {
    # Créneaux horaires distincts (≥ 2 h d'écart) : les matchs simultanés de
    # compétitions différentes ne partagent jamais la même disponibilité.
    "EPL": 13,
    "Bundesliga": 15,
    "LaLiga": 17,
    "SerieA": 19,
    "Ligue1": 21,
}

STAT_GRID: tuple[int, ...] = (900, 1800, 2700, 3600, 4500, 5400)
"""Tranches de statistiques cumulées (tous les quarts d'heure + fin)."""

MATCH_DURATION = 5400


def _result_score(pattern: int, rng: random.Random) -> tuple[int, int]:
    """Score garanti couvrant victoires/nuls/défaites (entraînement §11.1)."""
    if pattern == 0:  # match nul
        goals = rng.choice([0, 1, 2])
        return goals, goals
    if pattern == 1:  # victoire domicile
        return rng.choice([1, 2, 2, 3]), rng.choice([0, 0, 1])
    if pattern == 2:  # victoire extérieur
        return rng.choice([0, 0, 1]), rng.choice([1, 2, 2, 3])
    return rng.choice([0, 1, 1, 2]), rng.choice([0, 1, 1, 2])


def _cumulative(target: int, elapsed: int) -> int:
    """Compteur cumulé au instant `elapsed` (croissant, final = target)."""
    return min(target, int(target * elapsed / MATCH_DURATION))


def generate_match_record(
    rng: random.Random,
    competition: str,
    season: str,
    index: int,
) -> dict[str, Any]:
    """Génère un match brut cohérent (contrôles §3.3–§3.5 garantis)."""
    year, month, day = SEASON_KICKOFF[season]
    kickoff_dt = datetime(year, month, day, COMPETITION_HOUR[competition])
    kickoff_dt += timedelta(days=2 * index)
    kickoff = kickoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    home_name = TEAM_POOL[index % len(TEAM_POOL)]
    away_name = TEAM_POOL[(index + 1) % len(TEAM_POOL)]
    if index % 8 == 7:
        # Occasionnellement un score hors grille → catégorie « other » (§8.2).
        home_goals, away_goals = 4, rng.choice([0, 1])
    else:
        home_goals, away_goals = _result_score(index % 4, rng)

    events: list[dict[str, Any]] = []
    counter = 0

    def add_event(event_type: str, team: str, elapsed: int, detail: str) -> None:
        nonlocal counter
        events.append(
            {
                "source_event_id": f"ev-{counter:03d}",
                "type": event_type,
                "team": team,
                "elapsed_seconds": int(elapsed),
                "player_id": f"player-{rng.randrange(1, 15):02d}",
                "detail": detail,
            }
        )
        counter += 1

    for _ in range(home_goals):
        add_event("goal", "home", rng.randrange(150, 5300), "open_play")
    for _ in range(away_goals):
        add_event("goal", "away", rng.randrange(150, 5300), "open_play")

    n_yellows = rng.randrange(2, 7)
    for _ in range(n_yellows):
        add_event(
            "yellow_card", rng.choice(["home", "away"]),
            rng.randrange(300, 5300), "tactical_foul",
        )
    n_reds = 1 if rng.random() < 0.12 else 0
    red_elapsed: int | None = None
    red_team: str | None = None
    for _ in range(n_reds):
        red_elapsed = rng.randrange(1800, 5200)
        red_team = rng.choice(["home", "away"])
        add_event("red_card", red_team, red_elapsed, "professional_foul")
    if rng.random() < 0.35:
        add_event(
            "penalty", rng.choice(["home", "away"]),
            rng.randrange(200, 5000), "awarded",
        )
    for _ in range(2):
        add_event(
            "substitution", rng.choice(["home", "away"]),
            rng.randrange(2400, 5100), "tactical",
        )
    if index % 5 == 2:
        # Décision annexe B « événements de même timestamp » : deux
        # remplacements simultanés → snapshot agrégé de contrôle (§6.2).
        add_event("substitution", "home", 3000, "tactical")
        add_event("substitution", "away", 3000, "tactical")

    # Corners : total officiel, réparti entre les camps (parfois queue 21+).
    total_corners = rng.randrange(6, 23)
    home_corners = round(total_corners * rng.random())
    away_corners = total_corners - home_corners
    yellows = {"home": 0, "away": 0}
    for event in events:
        if event["type"] == "yellow_card":
            yellows[event["team"]] += 1

    statistics: list[dict[str, Any]] = []
    home_shots = rng.randrange(8, 20)
    away_shots = rng.randrange(8, 20)
    home_possession = round(0.35 + 0.30 * rng.random(), 3)
    home_xg = round(0.4 + 1.8 * rng.random(), 3)
    away_xg = round(0.4 + 1.8 * rng.random(), 3)
    for side in ("home", "away"):
        team_corners = home_corners if side == "home" else away_corners
        team_yellows = yellows[side]
        team_shots = home_shots if side == "home" else away_shots
        team_sot = max(2, team_shots // 2 - rng.randrange(0, 2))
        team_xg = home_xg if side == "home" else away_xg
        side_red = 1 if (side == red_team and red_elapsed is not None) else 0
        for elapsed in STAT_GRID:
            statistics.append(
                {
                    "elapsed_seconds": elapsed,
                    "team": side,
                    "shots": _cumulative(team_shots, elapsed),
                    "shots_on_target": _cumulative(team_sot, elapsed),
                    "corners": _cumulative(team_corners, elapsed),
                    "yellow_cards": _cumulative(team_yellows, elapsed),
                    "red_cards": (
                        1 if red_elapsed is not None and elapsed >= red_elapsed
                        and side == red_team else 0
                    ),
                    "possession": (
                        home_possession if side == "home"
                        else round(1.0 - home_possession, 3)
                    ),
                    "xg": round(_cumulative(round(team_xg * 1000), elapsed) / 1000, 3),
                }
            )

    return {
        "source_match_id": f"{competition}-{season}-{index:02d}",
        "competition_id": competition,
        "season": season,
        "date_utc": kickoff[:10],
        "kickoff_timestamp": kickoff,
        "status": "finished",
        "home_team_name": home_name,
        "away_team_name": away_name,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "total_corners": total_corners,
        "total_yellow_cards": n_yellows,
        "total_red_cards": n_reds,
        "events": events,
        "statistics": statistics,
        "available_delay": {"events": 30, "statistics": 45},
    }


def generate_dataset(
    raw_dir: str | Path,
    *,
    competitions: list[str],
    seasons: list[str],
    matches_per_season: int = 8,
    seed: int = SEED,
) -> list[Path]:
    """Écrit les documents bruts {comp}/{season}/matches.json (déterministe).

    Returns:
        Liste des chemins écrits.
    """
    rng = random.Random(seed)
    written: list[Path] = []
    for competition in competitions:
        for season in seasons:
            records = [
                generate_match_record(rng, competition, season, index)
                for index in range(matches_per_season)
            ]
            document = {
                "source": {
                    "provider": "synthetic-generator",
                    "license": "CC0-1.0 (données synthétiques)",
                    "retrieved_at": FIXED_RETRIEVED_AT,
                    "note": (
                        f"généré déterministement (seed={seed}) — aucune "
                        "donnée réelle"
                    ),
                },
                "matches": records,
            }
            path = Path(raw_dir) / competition / season / "matches.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            written.append(path)
    return written


def _scope_from_config(config_path: str | Path) -> tuple[list[str], list[str]]:
    """Lit compétitions/saisons depuis la configuration YAML."""
    import yaml

    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    return list(cfg["competitions"]), list(cfg["seasons"])


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI : génère data/raw pour le périmètre de la config."""
    parser = argparse.ArgumentParser(
        description="Générateur de données synthétiques déterministes (§0.2)"
    )
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--matches-per-season", type=int, default=8)
    parser.add_argument("--out-dir", default=None,
                        help="répertoire de sortie (défaut : paths.raw_dir de la config)")
    args = parser.parse_args(argv)

    competitions, seasons = _scope_from_config(args.config)
    if args.out_dir:
        raw_dir = Path(args.out_dir)
    else:
        raw_dir = Path("data") / "raw"
    written = generate_dataset(
        raw_dir,
        competitions=competitions,
        seasons=seasons,
        matches_per_season=args.matches_per_season,
        seed=args.seed,
    )
    print(
        f"[synthetic] {len(written)} documents écrits dans {raw_dir} "
        f"(compétitions={competitions}, saisons={seasons}, "
        f"seed={args.seed}, matchs/saison={args.matches_per_season})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
