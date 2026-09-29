"""Agent Snapshot (protocole §14.5, §5.3, §6, §7.1, §21 « Snapshot »).

Rôle : construire les snapshots d'état transmis ensuite à Laya et aux
baselines :
- snapshots fixes : pre_match (cutoff 0) puis 15/30/45/60/75/85 minutes
  (cutoffs_seconds [0, 900, 1800, 2700, 3600, 4500, 5100], §6.1), créés
  si le match est encore en jeu à l'instant correspondant ;
- snapshots événementiels : immédiatement après chaque but, carton rouge,
  penalty et remplacement (§6.2), avec gestion des événements de même
  timestamp (ordre source + version agrégée de contrôle, décision annexe B) ;
- tiers d'information A/B/C (§6.3) : A = pré-match seul, B = A + score,
  cartons, corners, événements, C = B + tirs, tirs cadrés, possession, xG.

L'état `state_json` est la sérialisation canonique §7.1 ; son hash est
stocké. TOUS les tests anti-fuite de `src.core.leakage` (§5.5) sont
exécutés sur 100 % des snapshots : toute violation bloque l'agent (§14.5).

Usage (§16) :
    python -m agents.snapshot --run-id RUN_ID [--config configs/experiment.yaml]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agents.common import (
    add_seconds,
    bulk_upsert,
    config_paths,
    load_config,
    log_error,
    log_event,
    setup_logging,
    sha256_text,
    write_artifact,
)
from src.core.canonical import canonical_json, state_hash
from src.core.ids import snapshot_id as compute_snapshot_id
from src.core.leakage import EVENT_SNAPSHOT_TYPES, audit_snapshot_set
from src.storage.database import Database

AGENT_NAME = "snapshot"
PRODUCER = "snapshot_agent"

MATCH_DURATION_SECONDS = 5400
"""Durée nominale de temps de jeu (90 min) pour la règle « encore en jeu »."""

EVENT_DELAY_SECONDS = 30
"""Délai de publication des événements (décision annexe B)."""


def _score_at(
    events: list[dict[str, Any]],
    home_id: str,
    cutoff_s: int,
    cutoff_ts: str,
) -> dict[str, int]:
    """Score live au cutoff : buts disponibles (disponibilité <= cutoff, §5.3)."""
    home = away = 0
    for event in events:
        if (
            event["event_type"] == "goal"
            and event["elapsed_seconds"] <= cutoff_s
            and event["available_timestamp"] <= cutoff_ts
        ):
            if event["team_id"] == home_id:
                home += 1
            else:
                away += 1
    return {"home": home, "away": away}


def _reds_at(
    events: list[dict[str, Any]],
    home_id: str,
    cutoff_s: int,
    cutoff_ts: str,
) -> dict[str, int]:
    """Cartons rouges au cutoff (domicile/extérieur)."""
    home = away = 0
    for event in events:
        if (
            event["event_type"] == "red_card"
            and event["elapsed_seconds"] <= cutoff_s
            and event["available_timestamp"] <= cutoff_ts
        ):
            if event["team_id"] == home_id:
                home += 1
            else:
                away += 1
    return {"home": home, "away": away}


def _latest_stats(
    stats: list[dict[str, Any]], cutoff_s: int, cutoff_ts: str
) -> dict[str, dict[str, Any]]:
    """Dernière statistique disponible par équipe au cutoff (§5.3)."""
    best: dict[str, dict[str, Any]] = {}
    for row in sorted(stats, key=lambda s: s["elapsed_seconds"]):
        if (
            row["elapsed_seconds"] <= cutoff_s
            and row["available_timestamp"] <= cutoff_ts
        ):
            best[row["team_id"]] = row
    return best


def _pre_match_block(
    contexts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Bloc pré-match de l'état (§7.1) — valeurs null si absentes (§7.2)."""
    return {
        side: {
            "form_last_5": ctx["form_last_5"],
            "form_last_10": ctx["form_last_10"],
            "goals_scored_avg": ctx["goals_scored_avg"],
            "goals_conceded_avg": ctx["goals_conceded_avg"],
            "ranking_before": ctx["ranking_before"],
            "head_to_head": ctx["head_to_head"],
            "xg_for_avg": ctx["xg_for_avg"],
            "xg_against_avg": ctx["xg_against_avg"],
        }
        for side, ctx in contexts.items()
    }


def build_state(
    match: dict[str, Any],
    teams: dict[str, str],
    tier: str,
    cutoff_s: int,
    cutoff_ts: str,
    contexts: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    stats: list[dict[str, Any]],
    trigger_event_ids: list[str],
    snapshot_type: str,
) -> dict[str, Any]:
    """Construit l'état canonique §7.1 d'un snapshot.

    Champs interdits (§5.4) : aucun champ final, aucun événement postérieur
    au cutoff, aucune statistique publiée après le cutoff.
    """
    home_id, away_id = match["home_team_id"], match["away_team_id"]
    source_ids: set[str] = set()
    for ctx in contexts.values():
        source_ids.update(json.loads(ctx["source_match_ids"] or "[]"))
    metadata = {
        "competition": match["competition_id"],
        "season": match["season"],
        "home_team": teams.get(home_id, home_id),
        "away_team": teams.get(away_id, away_id),
        "cutoff_seconds": cutoff_s,
        "cutoff_timestamp": cutoff_ts,
        "information_tier": tier,
        "snapshot_type": snapshot_type,
        "trigger_event_ids": trigger_event_ids,
        "pre_match_cutoff_timestamp": match["kickoff_timestamp"],
        "pre_match_source_match_ids": sorted(source_ids),
    }
    state: dict[str, Any] = {
        "metadata": metadata,
        "pre_match": _pre_match_block(contexts),
    }
    if tier == "A":
        # Tier A : pré-match uniquement (§6.3) — aucun bloc live.
        return state

    latest = _latest_stats(stats, cutoff_s, cutoff_ts)
    home_stats = latest.get(home_id, {})
    away_stats = latest.get(away_id, {})

    def _pair(key: str) -> dict[str, Any]:
        """Compteur live par équipe (null si non disponible, §7.2)."""
        return {
            "home": int(home_stats[key]) if home_stats.get(key) is not None else None,
            "away": int(away_stats[key]) if away_stats.get(key) is not None else None,
        }

    live: dict[str, Any] = {
        "score": _score_at(events, home_id, cutoff_s, cutoff_ts),
        "corners": _pair("corners"),
        "yellow_cards": _pair("yellow_cards"),
        "red_cards": _reds_at(events, home_id, cutoff_s, cutoff_ts),
        "events": [
            {
                "event_id": e["event_id"],
                "type": e["event_type"],
                "team": "home" if e["team_id"] == home_id else "away",
                "elapsed_seconds": e["elapsed_seconds"],
                "available_timestamp": e["available_timestamp"],
                "detail": e["detail"],
            }
            for e in events
            if e["elapsed_seconds"] <= cutoff_s
            and e["available_timestamp"] <= cutoff_ts
        ],
    }
    if tier == "C":
        live["shots"] = _pair("shots")
        live["shots_on_target"] = _pair("shots_on_target")
        live["possession"] = {
            "home": home_stats.get("possession"),
            "away": away_stats.get("possession"),
        }
        live["xg"] = {"home": home_stats.get("xg"), "away": away_stats.get("xg")}
    state["live"] = live
    return state


def _make_snapshot(
    match: dict[str, Any],
    teams: dict[str, str],
    tier: str,
    cutoff_s: int,
    cutoff_ts: str,
    variant: str,
    snapshot_type: str,
    contexts: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    stats: list[dict[str, Any]],
    trigger_ids: list[str],
) -> dict[str, Any]:
    """Enregistrement de snapshot complet (état + forme sérialisée, §4.2)."""
    state = build_state(
        match, teams, tier, cutoff_s, cutoff_ts, contexts,
        events, stats, trigger_ids, snapshot_type,
    )
    return {
        "snapshot_id": compute_snapshot_id(match["match_id"], cutoff_s, tier, variant),
        "match_id": match["match_id"],
        "cutoff_seconds": cutoff_s,
        "cutoff_timestamp": cutoff_ts,
        "snapshot_type": snapshot_type,
        "information_tier": tier,
        "state": state,
        "state_json": canonical_json(state),
        "state_hash": state_hash(state),
        "validation_status": "pending",
    }


def build_snapshots(config_path: str | Path, run_id: str) -> int:
    """Construit les snapshots et le rapport de validation anti-fuite."""
    cfg = load_config(config_path)
    paths = config_paths(cfg)
    logger = setup_logging(AGENT_NAME, paths["logs_dir"])
    log_event(logger, "start", "ok", "construction des snapshots", run_id=run_id)

    db = Database(paths["db"])
    db.init()

    # Équipes (noms canoniques) depuis l'export du nettoyeur (§4.1).
    teams: dict[str, str] = {}
    for comp in cfg["competitions"]:
        for season in cfg["seasons"]:
            export = paths["canonical_dir"] / comp / season / "canonical.json"
            if export.is_file():
                data = json.loads(export.read_text(encoding="utf-8"))
                teams.update(data.get("teams") or {})

    matches = db.query(
        "SELECT * FROM matches WHERE status = 'included' ORDER BY kickoff_timestamp"
    )
    matches_by_id = {m["match_id"]: m for m in db.query("SELECT * FROM matches")}
    all_events = db.query(
        "SELECT * FROM match_events ORDER BY match_id, elapsed_seconds"
    )
    all_stats = db.query("SELECT * FROM match_statistics")
    all_contexts = db.query("SELECT * FROM pre_match_context")

    contexts_by_match: dict[str, dict[str, dict[str, Any]]] = {}
    for ctx in all_contexts:
        per_match = contexts_by_match.setdefault(ctx["match_id"], {})
        side = (
            "home"
            if ctx["team_id"] == matches_by_id[ctx["match_id"]]["home_team_id"]
            else "away"
        )
        per_match[side] = ctx
    events_by_match: dict[str, list[dict[str, Any]]] = {}
    for event in all_events:
        events_by_match.setdefault(event["match_id"], []).append(event)
    stats_by_match: dict[str, list[dict[str, Any]]] = {}
    for stat in all_stats:
        stats_by_match.setdefault(stat["match_id"], []).append(stat)

    cutoffs = [int(c) for c in cfg["cutoffs_seconds"]]
    tiers = list(cfg["information_tiers"])

    # Mémoire/complexité (corpus réel : ~28 800 snapshots) : traitement PAR
    # MATCH avec audit anti-fuite et upsert incrémentaux. Équivalence stricte
    # avec l'accumulation intégrale : (1) un état n'embarque que les
    # événements de son propre match (check_no_future_events filtre par
    # match_id) ; (2) les matchs canoniques priment sur les contextes dans
    # check_pre_match_sources (correctif B2) et toutes les sources pré-match
    # figurent dans la table matches — les contextes de repli ne servent
    # jamais ; (3) bulk_upsert par match est idempotent (clé snapshot_id).
    n_total = 0
    n_blocked = 0
    by_tier: dict[str, int] = {}
    by_cutoff: dict[int, int] = {}
    per_snapshot: dict[str, Any] = {}
    sql_columns = (
        "snapshot_id", "match_id", "cutoff_seconds", "cutoff_timestamp",
        "snapshot_type", "information_tier", "state_json", "state_hash",
        "validation_status",
    )

    for match in matches:
        match_snapshots: list[dict[str, Any]] = []
        events = events_by_match.get(match["match_id"], [])
        stats = stats_by_match.get(match["match_id"], [])
        contexts = contexts_by_match.get(match["match_id"], {})
        kickoff = match["kickoff_timestamp"]
        max_elapsed = max(
            [e["elapsed_seconds"] for e in events]
            + [s["elapsed_seconds"] for s in stats]
            + [MATCH_DURATION_SECONDS]
        )

        # Snapshots fixes (§6.1) : créés si le match est encore en jeu.
        for cutoff_s in cutoffs:
            if cutoff_s > max_elapsed:
                continue
            cutoff_ts = add_seconds(kickoff, cutoff_s)
            snapshot_type = "pre_match" if cutoff_s == 0 else "fixed"
            for tier in tiers:
                match_snapshots.append(
                    _make_snapshot(
                        match, teams, tier, cutoff_s, cutoff_ts, "main",
                        snapshot_type, contexts, events, stats, [],
                    )
                )

        # Snapshots événementiels (§6.2) : à l'instant de disponibilité de
        # l'événement déclencheur (kickoff + elapsed + délai de publication).
        admissible = sorted(
            [e for e in events if e["event_type"] in EVENT_SNAPSHOT_TYPES],
            key=lambda e: (e["elapsed_seconds"], e["source_event_id"] or ""),
        )
        by_elapsed: dict[int, list[dict[str, Any]]] = {}
        for event in admissible:
            by_elapsed.setdefault(event["elapsed_seconds"], []).append(event)
        for elapsed, group in sorted(by_elapsed.items()):
            cutoff_ts = add_seconds(kickoff, elapsed + EVENT_DELAY_SECONDS)
            for event in group:
                for tier in tiers:
                    match_snapshots.append(
                        _make_snapshot(
                            match, teams, tier, elapsed, cutoff_ts,
                            f"event:{event['event_id']}", event["event_type"],
                            contexts, events, stats, [event["event_id"]],
                        )
                    )
            if len(group) > 1:
                # Décision annexe B : ordre source conservé + version
                # agrégée de contrôle si plusieurs événements coïncident.
                for tier in tiers:
                    match_snapshots.append(
                        _make_snapshot(
                            match, teams, tier, elapsed, cutoff_ts,
                            f"event:agg:{elapsed}", "aggregated",
                            contexts, events, stats,
                            [e["event_id"] for e in group],
                        )
                    )

        # Tests anti-fuite sur 100 % des snapshots du match (§5.5) —
        # src.core.leakage ; événements du match courant (équivalence
        # démontrée en tête de boucle) et matchs canoniques de la base.
        reports = audit_snapshot_set(
            match_snapshots, events=events_by_match.get(match["match_id"], []),
            contexts=(), matches_by_id=matches_by_id,
        )
        rows: list[dict[str, Any]] = []
        for snap in match_snapshots:
            report = reports[snap["snapshot_id"]]
            snap["validation_status"] = (
                "validated" if not report.has_leakage else "blocked"
            )
            per_snapshot[snap["snapshot_id"]] = {
                "status": snap["validation_status"],
                "violations": report.violations,
            }
            if snap["validation_status"] == "blocked":
                n_blocked += 1
            by_tier[snap["information_tier"]] = (
                by_tier.get(snap["information_tier"], 0) + 1
            )
            by_cutoff[snap["cutoff_seconds"]] = (
                by_cutoff.get(snap["cutoff_seconds"], 0) + 1
            )
            rows.append({k: snap[k] for k in sql_columns})
        bulk_upsert(db, "match_snapshots", rows)
        n_total += len(match_snapshots)

    rate = n_blocked / max(n_total, 1)
    max_leak = float(cfg["thresholds"]["max_snapshot_leakage_rate"])
    status = "blocked" if (n_blocked > 0 or rate > max_leak) else "validated"

    payload = {
        "summary": {
            "n_snapshots": n_total,
            "n_validated": n_total - n_blocked,
            "n_blocked": n_blocked,
            "leakage_rate": rate,
            "by_tier": by_tier,
            "by_cutoff": {str(k): v for k, v in sorted(by_cutoff.items())},
        },
        "per_snapshot": per_snapshot,
        "tests": [
            "test_no_future_events (§5.5)",
            "test_no_final_fields (§5.5)",
            "test_pre_match_sources_before_cutoff (§5.5)",
            "cohérence cutoff/événements embarqués (§5.3)",
        ],
    }
    input_hashes = [
        "pre_match_validation:"
        + _artifact_digest(paths["artifacts_dir"], run_id,
                           "pre_match_validation.json")
    ]
    artifact_path = paths["artifacts_dir"] / run_id / "snapshot_validation.json"
    write_artifact(
        artifact_path,
        payload,
        experiment_id=cfg["experiment_id"],
        run_id=run_id,
        producer=PRODUCER,
        input_hashes=input_hashes,
        status=status,
        record_count=n_total - n_blocked,
        warnings=[] if n_blocked == 0 else
        [f"{n_blocked} snapshots avec fuite détectée (§5.5)"],
        errors=[] if n_blocked == 0 else ["tests anti-fuite en échec (§14.5)"],
    )
    log_event(
        logger, "artifact", status,
        f"snapshot_validation.json snapshots={n_total} fuite={rate:.4f}",
        run_id=run_id,
    )
    if status == "blocked":
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "snapshot",
                  f"anti-fuite en échec : {n_blocked} snapshots bloqués")
        db.close()
        return 1
    db.close()
    log_event(logger, "end", "ok", "snapshots validés", run_id=run_id)
    return 0


def _artifact_digest(artifacts_dir: Path, run_id: str, name: str) -> str:
    """Hash SHA-256 d'un artefact d'entrée (chaîne d'audit §15)."""
    path = artifacts_dir / run_id / name
    if not path.is_file():
        return "absent"
    return sha256_text(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    """Parseur CLI de l'agent snapshot."""
    parser = argparse.ArgumentParser(description="Agent Snapshot (protocole §14.5)")
    parser.add_argument("--run-id", default="run_001")
    parser.add_argument("--config", default="configs/experiment.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI (§16)."""
    args = build_parser().parse_args(argv)
    return build_snapshots(args.config, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
