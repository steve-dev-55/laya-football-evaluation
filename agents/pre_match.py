"""Agent Pré-match (protocole §14.4, §5.2, §21 « Pré-match »).

Rôle : construire le contexte pré-match point-in-time de chaque match inclus :
- forme (5 et 10 derniers matchs) ;
- moyennes de buts marqués/encaissés (10 derniers matchs) ;
- classement AVANT le cutoff uniquement (points de la saison en cours) ;
- confrontations directes ;
- moyennes xG pour/contre (10 derniers matchs).

Règles bloquantes (§5.2) :
- chaque feature n'utilise que des matchs dont `available_timestamp` est
  STRICTEMENT antérieur au cutoff pré-match (= kickoff, décision annexe B) ;
- le match courant ne peut jamais figurer dans ses propres sources ;
- tous les `source_match_ids` sont listés et revalidés à postériori
  (`pre_match_validation.json`).

Usage (§16) :
    python -m agents.pre_match --run-id RUN_ID [--config configs/experiment.yaml]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agents.common import (
    bulk_upsert,
    config_paths,
    load_config,
    log_error,
    log_event,
    setup_logging,
    sha256_text,
    write_artifact,
)
from src.storage.database import Database, pre_match_window

AGENT_NAME = "pre_match"
PRODUCER = "pre_match_agent"

FEATURE_VERSION = "v1"
"""Version des features pré-match (toute modification casse la reproductibilité)."""

FORM_WINDOW = 10
"""Fenêtre maximale (en matchs) pour les moyennes historiques (§10.1)."""


def _side_result(
    match: dict[str, Any], team_id: str
) -> str:
    """Résultat d'un match terminé du point de vue d'une équipe (« W/D/L »)."""
    home_goals, away_goals = match["home_goals"], match["away_goals"]
    if match["home_team_id"] == team_id:
        scored, conceded = home_goals, away_goals
    else:
        scored, conceded = away_goals, home_goals
    if scored > conceded:
        return "W"
    if scored < conceded:
        return "L"
    return "D"


def _team_matches(past: list[dict[str, Any]], team_id: str) -> list[dict[str, Any]]:
    """Matchs terminés d'une équipe dans la fenêtre temporelle, les plus
    récents d'abord (§5.2 : available_timestamp < cutoff, match courant exclu)."""
    rows = [
        m
        for m in past
        if m["home_team_id"] == team_id or m["away_team_id"] == team_id
    ]
    return sorted(rows, key=lambda m: (m["kickoff_timestamp"], m["match_id"]),
                  reverse=True)


def _form(team_rows: list[dict[str, Any]], team_id: str, n: int) -> str | None:
    """Séquence de forme chronologique (« la plus récente à droite »)."""
    if not team_rows:
        return None
    seq = [_side_result(m, team_id) for m in team_rows[:n]]
    return "".join(reversed(seq)) if seq else None


def _goals_averages(
    team_rows: list[dict[str, Any]], team_id: str
) -> tuple[float | None, float | None]:
    """Moyennes de buts marqués/encaissés sur la fenêtre (§5.2)."""
    window = team_rows[:FORM_WINDOW]
    if not window:
        return None, None
    scored = conceded = 0
    for match in window:
        if match["home_team_id"] == team_id:
            scored += match["home_goals"]
            conceded += match["away_goals"]
        else:
            scored += match["away_goals"]
            conceded += match["home_goals"]
    n = len(window)
    return round(scored / n, 4), round(conceded / n, 4)


def _ranking_before(
    season_rows: list[dict[str, Any]], team_id: str
) -> float | None:
    """Classement point-in-time : points des matchs de la saison en cours
    disponibles AVANT le cutoff (§5.2 — jamais le classement final)."""
    if not season_rows:
        return None
    points: dict[str, int] = {}
    for match in season_rows:
        for side in ("home_team_id", "away_team_id"):
            points.setdefault(match[side], 0)
        result = (
            "H" if match["home_goals"] > match["away_goals"]
            else "A" if match["home_goals"] < match["away_goals"]
            else "D"
        )
        if result == "H":
            points[match["home_team_id"]] += 3
        elif result == "A":
            points[match["away_team_id"]] += 3
        else:
            points[match["home_team_id"]] += 1
            points[match["away_team_id"]] += 1
    ordered = sorted(points, key=lambda t: (-points[t], t))
    if team_id not in ordered:
        return None
    return float(ordered.index(team_id) + 1)


def _head_to_head(
    past: list[dict[str, Any]], home_id: str, away_id: str, n: int = 5
) -> str | None:
    """Dernières confrontations directes du point de vue domicile (« W/D/L »)."""
    rows = [
        m
        for m in sorted(past, key=lambda m: (m["kickoff_timestamp"], m["match_id"]),
                        reverse=True)
        if {m["home_team_id"], m["away_team_id"]} == {home_id, away_id}
    ]
    if not rows:
        return None
    seq = []
    for match in rows[:n]:
        if match["home_goals"] == match["away_goals"]:
            seq.append("D")
        elif (
            match["home_goals"] > match["away_goals"]
        ) == (match["home_team_id"] == home_id):
            seq.append("W")
        else:
            seq.append("L")
    return ",".join(seq)


def _xg_averages(
    team_rows: list[dict[str, Any]],
    team_id: str,
    final_stats: dict[str, dict[str, float]],
) -> tuple[float | None, float | None]:
    """Moyennes xG pour/contre sur la fenêtre (données finales des matchs
    PASSÉS uniquement — disponibles avant le cutoff par construction)."""
    window = team_rows[:FORM_WINDOW]
    fors: list[float] = []
    against: list[float] = []
    for match in window:
        stats = final_stats.get(match["match_id"], {})
        xg_home = stats.get(match["home_team_id"])
        xg_away = stats.get(match["away_team_id"])
        if xg_home is None or xg_away is None:
            continue
        if match["home_team_id"] == team_id:
            fors.append(xg_home)
            against.append(xg_away)
        else:
            fors.append(xg_away)
            against.append(xg_home)
    if not fors:
        return None, None
    return round(sum(fors) / len(fors), 4), round(sum(against) / len(against), 4)


def _final_xg_by_match(db: Database, match_ids: list[str]) -> dict[str, dict[str, float]]:
    """xG final par équipe et par match (dernière ligne de statistiques)."""
    result: dict[str, dict[str, float]] = {}
    for mid in match_ids:
        rows = db.query(
            "SELECT team_id, xg, elapsed_seconds FROM match_statistics "
            "WHERE match_id = ? ORDER BY elapsed_seconds",
            (mid,),
        )
        for row in rows:
            if row["xg"] is None:
                continue
            result.setdefault(mid, {})[row["team_id"]] = float(row["xg"])
    return result


def build_pre_match(config_path: str | Path, run_id: str) -> int:
    """Construit `pre_match_context` et le rapport de validation."""
    cfg = load_config(config_path)
    paths = config_paths(cfg)
    logger = setup_logging(AGENT_NAME, paths["logs_dir"])
    log_event(logger, "start", "ok", "contexte pré-match point-in-time",
              run_id=run_id)

    db = Database(paths["db"])
    db.init()

    matches = db.query(
        "SELECT * FROM matches WHERE status = 'included' ORDER BY kickoff_timestamp"
    )
    matches_by_id = {m["match_id"]: m for m in matches}
    all_matches = db.query("SELECT * FROM matches")
    all_by_id = {m["match_id"]: m for m in all_matches}
    final_stats = _final_xg_by_match(db, list(matches_by_id))

    context_rows: list[dict[str, Any]] = []
    validation: dict[str, Any] = {}
    n_blocked = 0

    for match in matches:
        cutoff = match["kickoff_timestamp"]
        # Vue temporelle stricte (§5.2) : available < cutoff, match courant exclu.
        past = [
            m
            for m in pre_match_window(db, "matches", cutoff, match["match_id"])
            if m["status"] == "included"
        ]
        season_rows = [m for m in past if m["season"] == match["season"]]
        source_ids: set[str] = set()

        for _side, team_id in (
            ("home", match["home_team_id"]),
            ("away", match["away_team_id"]),
        ):
            team_rows = _team_matches(past, team_id)
            goals_avg, conceded_avg = _goals_averages(team_rows, team_id)
            xg_for, xg_against = _xg_averages(team_rows, team_id, final_stats)
            ranking = _ranking_before(season_rows, team_id)
            h2h = _head_to_head(past, match["home_team_id"], match["away_team_id"])
            used = {m["match_id"] for m in team_rows[:FORM_WINDOW]}
            used |= {m["match_id"] for m in season_rows}
            source_ids |= used
            context_rows.append(
                {
                    "pre_match_id": sha256_text(f"{match['match_id']}:{team_id}"),
                    "match_id": match["match_id"],
                    "team_id": team_id,
                    "cutoff_timestamp": cutoff,
                    "feature_version": FEATURE_VERSION,
                    "form_last_5": _form(team_rows, team_id, 5),
                    "form_last_10": _form(team_rows, team_id, 10),
                    "goals_scored_avg": goals_avg,
                    "goals_conceded_avg": conceded_avg,
                    "head_to_head": h2h,
                    "ranking_before": ranking,
                    "xg_for_avg": xg_for,
                    "xg_against_avg": xg_against,
                    "injuries": None,
                    "suspensions": None,
                    "lineup": None,
                    "pre_match_odds": None,
                    "source_match_ids": json.dumps(sorted(used)),
                }
            )

        # Validation §5.2 : chaque source doit être strictement antérieure au
        # cutoff ET différente du match courant (double contrôle).
        violations = []
        for used_id in sorted(source_ids):
            if used_id == match["match_id"]:
                violations.append(f"match courant utilisé : {used_id}")
                continue
            source = all_by_id.get(used_id)
            if source is None or not (source["available_timestamp"] < cutoff):
                violations.append(
                    f"match source {used_id} non disponible avant cutoff"
                )
        ok = not violations
        n_blocked += 0 if ok else 1
        validation[match["match_id"]] = {
            "cutoff": cutoff,
            "n_sources": len(source_ids),
            "all_sources_before_cutoff": ok,
            "violations": violations,
        }
        log_event(
            logger, "pre_match", "ok" if ok else "blocked",
            f"cutoff={cutoff} sources={len(source_ids)}"
            + ("" if ok else f" violations={len(violations)}"),
            run_id=run_id, entity_id=match["match_id"],
        )

    bulk_upsert(db, "pre_match_context", context_rows)

    # Chaîne d'audit : l'entrée est l'artefact du nettoyeur (§15).
    cleaner_artifact = paths["artifacts_dir"] / run_id / "cleaning_report.json"
    input_hashes: list[str] = []
    if cleaner_artifact.is_file():
        cleaner_digest = sha256_text(cleaner_artifact.read_text(encoding="utf-8"))
        input_hashes.append(f"cleaning_report:{cleaner_digest}")
    status = "blocked" if n_blocked else "validated"
    warnings = []
    n_no_history = sum(1 for v in validation.values() if v["n_sources"] == 0)
    if n_no_history:
        warnings.append(
            f"{n_no_history} matchs sans historique (features null, §7.2)"
        )
    payload = {
        "feature_version": FEATURE_VERSION,
        "form_window": FORM_WINDOW,
        "per_match": validation,
        "counts": {
            "matches": len(matches),
            "contexts": len(context_rows),
            "blocked_matches": n_blocked,
            "matches_without_history": n_no_history,
        },
        "missing_data_rule": "null sans imputation (décision annexe B, §7.2)",
    }
    artifact_path = paths["artifacts_dir"] / run_id / "pre_match_validation.json"
    write_artifact(
        artifact_path,
        payload,
        experiment_id=cfg["experiment_id"],
        run_id=run_id,
        producer=PRODUCER,
        input_hashes=input_hashes,
        status=status,
        record_count=len(context_rows),
        warnings=warnings,
        errors=[] if not n_blocked else ["features avec sources non conformes"],
    )
    log_event(logger, "artifact", status,
              f"pre_match_validation.json contexts={len(context_rows)}",
              run_id=run_id)
    if n_blocked:
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "pre_match",
                  f"{n_blocked} matchs avec feature non conforme (§5.2)")
        db.close()
        return 1
    db.close()
    log_event(logger, "end", "ok", "contexte pré-match terminé", run_id=run_id)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Parseur CLI de l'agent pré-match."""
    parser = argparse.ArgumentParser(description="Agent Pré-match (protocole §14.4)")
    parser.add_argument("--run-id", default="run_001")
    parser.add_argument("--config", default="configs/experiment.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI (§16)."""
    args = build_parser().parse_args(argv)
    return build_pre_match(args.config, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
