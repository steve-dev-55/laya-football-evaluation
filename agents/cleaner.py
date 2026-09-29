"""Agent Nettoyeur (protocole §14.3, §3.3–§3.5, §21 « Nettoyeur »).

Rôle : transformer les données brutes immuables en données canoniques :
- identifiants déterministes (team_id / match_id / event_id / stat_id, §4.3) ;
- déduplication sur une clé documentée (match : match_id ; événements :
  (match_id, source_event_id) ; statistiques : (match_id, elapsed, team)) ;
- contrôles score/événements/timestamps/conventions de comptage (§3.5) ;
- exclusions motivées consignées dans `cleaning_report.json` (§3.4) ;
- export canonique JSON par (compétition, saison) sous data/canonical/.

Règles d'inclusion (§3.3) et d'exclusion (§3.4) appliquées :
- statut « finished » requis (match joué et homologué, sans prolongation) ;
- score/événements cohérents (buts, cartons jaunes/rouges) ;
- totaux de corners cohérents avec les statistiques finales ;
- variables cibles présentes (score, corners, cartons) ;
- horodatages valides et compatibles avec la durée du match.

Aucune feature dérivée du résultat n'est injectée dans les données live (§3.5) :
les colonnes live restent strictement celles du protocole (§4.2).

Usage (§16) :
    python -m agents.cleaner --run-id RUN_ID [--config configs/experiment.yaml]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agents.common import (
    add_seconds,
    bulk_upsert,
    canonical_team_name,
    config_paths,
    load_config,
    log_error,
    log_event,
    setup_logging,
    sha256_file,
    write_artifact,
)
from src.core.ids import match_id as compute_match_id
from src.core.ids import sha256_text
from src.core.ids import team_id as compute_team_id
from src.storage.database import Database

AGENT_NAME = "cleaner"
PRODUCER = "cleaner_agent"

# Délais de publication (décision figée annexe B : « disponibilité réelle des
# statistiques ») utilisés si la source ne fournit pas son propre délai.
DEFAULT_EVENT_DELAY_SECONDS = 30
DEFAULT_STATS_DELAY_SECONDS = 45
# Durée de mise à disposition d'un match terminé (fin de match + marge).
MATCH_AVAILABLE_OFFSET_SECONDS = 5760
# Temps de jeu maximal admissible (90 min + arrêts de jeu bornés).
# Adaptation d'exécution (2026-09-29, corpus réel) : 5760 -> 6300 s
# (105 min) — les données StatsBomb modernes contiennent régulièrement des
# événements jusqu'à la minute 100-101 (VAR + arrêts de jeu longs) ; ces
# événements sont authentiques et comptent dans le score officiel (§3.5).
# Aucun impact anti-fuite : les cutoffs (<= 5100 s) restent largement en
# deçà ; les événements des arrêts de jeu ne sont visibles d'aucun snapshot.
MAX_ELAPSED_SECONDS = 6300

# Raisons d'exclusion motivées (§3.4) — codes figés pour l'audit.
EXCLUSION_STATUS_NOT_FINISHED = "status_not_finished"
EXCLUSION_INVALID_TIMESTAMPS = "invalid_timestamps"
EXCLUSION_MISSING_TARGET = "missing_target_variable"
EXCLUSION_SCORE_EVENTS_MISMATCH = "score_events_mismatch"
EXCLUSION_CARDS_EVENTS_MISMATCH = "cards_events_mismatch"
EXCLUSION_CORNERS_STATS_MISMATCH = "corners_stats_mismatch"
EXCLUSION_DUPLICATE = "unresolved_duplicate"

# Types d'événements canoniques (§6.2 + cartons jaunes pour les comptages).
KNOWN_EVENT_TYPES = frozenset(
    {"goal", "yellow_card", "red_card", "penalty", "substitution"}
)


def _check_match(record: dict[str, Any]) -> str | None:
    """Contrôles d'inclusion/exclusion d'un match brut (§3.3, §3.4).

    Returns:
        Le code de raison d'exclusion, ou None si le match est retenu.
    """
    if record.get("status") != "finished":
        return EXCLUSION_STATUS_NOT_FINISHED
    kickoff = record.get("kickoff_timestamp", "")
    try:
        add_seconds(kickoff, 0)
    except ValueError:
        return EXCLUSION_INVALID_TIMESTAMPS
    if record.get("date_utc") != kickoff[:10]:
        return EXCLUSION_INVALID_TIMESTAMPS
    events = record.get("events") or []
    if any(
        not isinstance(e.get("elapsed_seconds"), int)
        or not 0 <= e["elapsed_seconds"] <= MAX_ELAPSED_SECONDS
        for e in events
    ):
        return EXCLUSION_INVALID_TIMESTAMPS
    for key in ("home_goals", "away_goals", "total_corners", "total_yellow_cards"):
        if not isinstance(record.get(key), int):
            return EXCLUSION_MISSING_TARGET
    # Cohérence score / événements de but (§3.4, convention §3.5).
    goals_home = sum(
        1 for e in events if e.get("type") == "goal" and e.get("team") == "home"
    )
    goals_away = sum(
        1 for e in events if e.get("type") == "goal" and e.get("team") == "away"
    )
    if goals_home != record["home_goals"] or goals_away != record["away_goals"]:
        return EXCLUSION_SCORE_EVENTS_MISMATCH
    # Cohérence cartons : convention « 2e jaune = jaune » (annexe B) —
    # chaque carton jaune (y compris celui précédant une expulsion) compte.
    yellows = sum(1 for e in events if e.get("type") == "yellow_card")
    if yellows != record["total_yellow_cards"]:
        return EXCLUSION_CARDS_EVENTS_MISMATCH
    reds = sum(1 for e in events if e.get("type") == "red_card")
    if reds != (record.get("total_red_cards") or 0):
        return EXCLUSION_CARDS_EVENTS_MISMATCH
    # Cohérence corners : la dernière statistique cumulative par équipe doit
    # totaliser exactement le total officiel (§3.5).
    stats = record.get("statistics") or []
    last: dict[str, int] = {}
    for row in stats:
        last[row["team"]] = int(row.get("corners") or 0)
    if sum(last.values()) != record["total_corners"]:
        return EXCLUSION_CORNERS_STATS_MISMATCH
    return None


def _canonical_match_row(
    record: dict[str, Any], source_hash: str, status: str
) -> dict[str, Any]:
    """Construit la ligne canonique `matches` (§4.2) d'un match brut."""
    comp = record["competition_id"]
    home_id = compute_team_id(comp, canonical_team_name(record["home_team_name"]))
    away_id = compute_team_id(comp, canonical_team_name(record["away_team_name"]))
    kickoff = record["kickoff_timestamp"]
    return {
        "match_id": compute_match_id(
            comp, record["season"], kickoff, home_id, away_id
        ),
        "source_match_id": record["source_match_id"],
        "competition_id": comp,
        "season": record["season"],
        "date_utc": record["date_utc"],
        "kickoff_timestamp": kickoff,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "home_goals": record["home_goals"],
        "away_goals": record["away_goals"],
        "total_corners": record["total_corners"],
        "total_yellow_cards": record["total_yellow_cards"],
        "total_red_cards": record.get("total_red_cards") or 0,
        "status": status,
        "source_hash": source_hash,
        "available_timestamp": add_seconds(kickoff, MATCH_AVAILABLE_OFFSET_SECONDS),
        # Champs non-SQL conservés pour l'export canonique JSON.
        "home_team_name": record["home_team_name"],
        "away_team_name": record["away_team_name"],
    }


def _canonical_event_rows(
    match: dict[str, Any], record: dict[str, Any], source_hash: str
) -> list[dict[str, Any]]:
    """Construit les lignes `match_events` (§4.2), dédupliquées sur la clé
    documentée (match_id, source_event_id)."""
    delays = record.get("available_delay") or {}
    event_delay = delays.get("events", DEFAULT_EVENT_DELAY_SECONDS)
    kickoff = match["kickoff_timestamp"]
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    # Ordre source documenté : (elapsed_seconds, source_event_id).
    ordered = sorted(
        record.get("events") or [],
        key=lambda e: (e["elapsed_seconds"], str(e["source_event_id"])),
    )
    for event in ordered:
        if event["source_event_id"] in seen:
            continue  # déduplication sur clé documentée
        seen.add(event["source_event_id"])
        elapsed = event["elapsed_seconds"]
        team_name = event.get("team")
        rows.append(
            {
                "event_id": sha256_text(f"{match['match_id']}:{event['source_event_id']}"),
                "match_id": match["match_id"],
                "elapsed_seconds": elapsed,
                "period": 1 if elapsed <= 2700 else 2,
                "event_type": event["type"],
                "team_id": _side_team_id(match, team_name),
                "player_id": event.get("player_id"),
                "detail": event.get("detail"),
                "source_event_id": str(event["source_event_id"]),
                "source_hash": source_hash,
                "available_timestamp": add_seconds(kickoff, elapsed + event_delay),
            }
        )
    return rows


def _canonical_stat_rows(
    match: dict[str, Any], record: dict[str, Any], source_hash: str
) -> list[dict[str, Any]]:
    """Construit les lignes `match_statistics` (§4.2), dédupliquées sur la clé
    documentée (match_id, elapsed_seconds, équipe)."""
    delays = record.get("available_delay") or {}
    stats_delay = delays.get("statistics", DEFAULT_STATS_DELAY_SECONDS)
    kickoff = match["kickoff_timestamp"]
    seen: set[tuple[int, str]] = set()
    rows: list[dict[str, Any]] = []
    ordered = sorted(
        record.get("statistics") or [],
        key=lambda s: (s["elapsed_seconds"], s["team"]),
    )
    for stat in ordered:
        key = (stat["elapsed_seconds"], stat["team"])
        if key in seen:
            continue
        seen.add(key)
        elapsed = stat["elapsed_seconds"]
        rows.append(
            {
                "stat_id": sha256_text(
                    f"{match['match_id']}:{elapsed}:{_side_team_id(match, stat['team'])}"
                ),
                "match_id": match["match_id"],
                "available_timestamp": add_seconds(kickoff, elapsed + stats_delay),
                "elapsed_seconds": elapsed,
                "team_id": _side_team_id(match, stat["team"]),
                "shots": stat.get("shots"),
                "shots_on_target": stat.get("shots_on_target"),
                "corners": stat.get("corners"),
                "yellow_cards": stat.get("yellow_cards"),
                "red_cards": stat.get("red_cards"),
                "possession": stat.get("possession"),
                "xg": stat.get("xg"),
                "source_hash": source_hash,
            }
        )
    return rows


def _side_team_id(match: dict[str, Any], side: str | None) -> str | None:
    """Résout le camp (« home »/« away ») en team_id canonique."""
    if side == "home":
        return match["home_team_id"]
    if side == "away":
        return match["away_team_id"]
    return None


def clean(config_path: str | Path, run_id: str) -> int:
    """Exécute le nettoyage et écrit `cleaning_report.json`."""
    cfg = load_config(config_path)
    paths = config_paths(cfg)
    logger = setup_logging(AGENT_NAME, paths["logs_dir"])
    log_event(logger, "start", "ok", "nettoyage des données brutes", run_id=run_id)

    db = Database(paths["db"])
    db.init()

    input_hashes: list[str] = []
    exclusions: list[dict[str, Any]] = []
    deduplications: list[dict[str, Any]] = []
    per_stratum: dict[str, dict[str, int]] = {}
    match_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    stat_rows: list[dict[str, Any]] = []
    seen_match_ids: set[str] = set()
    canonical_export: dict[str, Any] = {}

    # Périmètre : produit cartésien (grille synthétique) OU paires explicites
    # `source.corpus_pairs` (corpus réel A1 — cf. docs/frozen_corpus.json).
    pairs = (cfg.get("source") or {}).get("corpus_pairs")
    if pairs:
        comp_season_pairs = [(p["competition"], p["season"]) for p in pairs]
    else:
        comp_season_pairs = [
            (comp, season)
            for comp in cfg["competitions"]
            for season in cfg["seasons"]
        ]

    for comp, season in comp_season_pairs:
        raw_path = paths["raw_dir"] / comp / season / "matches.json"
        source_hash = sha256_file(raw_path)
        input_hashes.append(f"raw:{comp}/{season}:{source_hash}")
        raw_doc = json.loads(raw_path.read_text(encoding="utf-8"))
        records = raw_doc.get("matches") or []
        stratum_key = f"{comp}/{season}"
        stratum = {"collected": len(records), "included": 0,
                   "excluded": 0, "duplicates": 0}
        stratum_export: dict[str, Any] = {"teams": {}, "matches": []}

        for record in records:
            reason = _check_match(record)
            row = _canonical_match_row(record, source_hash, "included")
            if row["match_id"] in seen_match_ids:
                # Doublon non résolu : même clé canonique depuis la source.
                deduplications.append(
                    {
                        "source_match_id": record["source_match_id"],
                        "match_id": row["match_id"],
                        "key": "match_id",
                        "resolution": "premier enregistrement conservé",
                    }
                )
                stratum["duplicates"] += 1
                continue
            seen_match_ids.add(row["match_id"])
            if reason is not None:
                row["status"] = f"excluded:{reason}"
                exclusions.append(
                    {
                        "source_match_id": record["source_match_id"],
                        "match_id": row["match_id"],
                        "competition": comp,
                        "season": season,
                        "reason": reason,
                    }
                )
                stratum["excluded"] += 1
                match_rows.append(row)
                continue
            stratum["included"] += 1
            match_rows.append(row)
            event_rows.extend(_canonical_event_rows(row, record, source_hash))
            stat_rows.extend(_canonical_stat_rows(row, record, source_hash))
            stratum_export["teams"][row["home_team_id"]] = row["home_team_name"]
            stratum_export["teams"][row["away_team_id"]] = row["away_team_name"]
            stratum_export["matches"].append(
                {
                    k: v for k, v in row.items()
                    if k not in ("home_team_name", "away_team_name")
                }
            )
        per_stratum[stratum_key] = stratum
        canonical_export[f"{comp}/{season}"] = stratum_export
        log_event(
            logger, "clean", "ok",
            f"{stratum_key} inclus={stratum['included']} "
            f"exclus={stratum['excluded']} doublons={stratum['duplicates']}",
            run_id=run_id, entity_id=stratum_key,
        )

    # Insertions idempotentes (les statuts exclus restent tracés dans la
    # table matches ; événements/statistiques uniquement pour les inclus).
    # Les colonnes non-SQL (noms d'équipes) servent uniquement à l'export.
    sql_match_rows = [
        {k: v for k, v in row.items()
         if k not in ("home_team_name", "away_team_name")}
        for row in match_rows
    ]
    bulk_upsert(db, "matches", sql_match_rows)
    bulk_upsert(db, "match_events", event_rows)
    bulk_upsert(db, "match_statistics", stat_rows)

    # Export canonique JSON (livrable §19.1, relu par l'agent snapshot).
    for stratum_key, export in canonical_export.items():
        comp, season = stratum_key.split("/")
        out = paths["canonical_dir"] / comp / season / "canonical.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(export, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        input_hashes.append(
            f"canonical:{stratum_key}:{sha256_file(out)}"
        )

    total_collected = sum(s["collected"] for s in per_stratum.values())
    total_included = sum(s["included"] for s in per_stratum.values())
    max_missing_rate = 0.0
    for stratum in per_stratum.values():
        rate = (stratum["collected"] - stratum["included"]) / max(stratum["collected"], 1)
        max_missing_rate = max(max_missing_rate, rate)
    threshold = float(cfg["thresholds"]["max_stratum_missing_rate"])

    warnings: list[str] = []
    status = "validated"
    if exclusions:
        warnings.append(
            f"{len(exclusions)} matchs exclus (raisons dans cleaning_report.json)"
        )
    if deduplications:
        warnings.append(f"{len(deduplications)} doublons dédupliqués")
    if max_missing_rate > threshold:
        # Seuil §11.4 : > 10 % de matchs manquants dans une strate obligatoire.
        warnings.append(
            f"taux de matchs manquants max = {max_missing_rate:.3f} > {threshold} "
            "(§11.4 : le test final est bloqué)"
        )
        status = "warning"

    payload = {
        "per_stratum": per_stratum,
        "exclusions": exclusions,
        "deduplications": deduplications,
        "counts": {
            "collected": total_collected,
            "included": total_included,
            "excluded": len(exclusions),
            "duplicates": len(deduplications),
            "events": len(event_rows),
            "statistics": len(stat_rows),
        },
        "max_stratum_missing_rate": max_missing_rate,
        "threshold_stratum_missing_rate": threshold,
        "deduplication_keys": {
            "matches": "match_id",
            "match_events": "(match_id, source_event_id)",
            "match_statistics": "(match_id, elapsed_seconds, team)",
        },
        "counting_conventions": {
            "goals": "buts, penalties et csc comptés pour l'équipe bénéficiaire (§3.5)",
            "second_yellow": "compté comme jaune si identifiable (annexe B)",
            "bench_cards": "exclus de la cible (§3.5)",
        },
    }
    artifact_path = paths["artifacts_dir"] / run_id / "cleaning_report.json"
    write_artifact(
        artifact_path,
        payload,
        experiment_id=cfg["experiment_id"],
        run_id=run_id,
        producer=PRODUCER,
        input_hashes=input_hashes,
        status=status,
        record_count=total_included,
        warnings=warnings,
    )
    log_event(
        logger, "artifact", status,
        f"cleaning_report.json inclus={total_included}/{total_collected}",
        run_id=run_id,
    )
    if total_included == 0:
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "clean",
                  "aucun match inclus après nettoyage")
        return 1
    log_event(logger, "end", "ok", "nettoyage terminé", run_id=run_id)
    db.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Parseur CLI de l'agent nettoyeur."""
    parser = argparse.ArgumentParser(description="Agent Nettoyeur (protocole §14.3)")
    parser.add_argument("--run-id", default="run_001")
    parser.add_argument("--config", default="configs/experiment.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI (§16)."""
    args = build_parser().parse_args(argv)
    return clean(args.config, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
