"""Vérificateur anti-fuite (protocole §5).

Règle centrale (§0.2) : à un cutoff t, aucun artefact transmis à Laya ne
doit dépendre d'une information postérieure à t pour les données live, ou
postérieure à l'heure de coupure pré-match pour les données historiques.

Les tests doivent être exécutés sur 100 % des snapshots (§5.5).
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from src.core.canonical import canonical_json

# Champs interdits dans state_json (§5.4) — inspection clés, valeurs,
# métadonnées, texte sérialisé.
FORBIDDEN_KEY_FRAGMENTS: tuple[str, ...] = (
    "final_score",
    "final_goals",
    "final_corners",
    "final_yellow_cards",
    "actual_result",
    "full_time",
    "fulltime",
    "final_result",
    "total_match",
    "match_result",
    "actual_outcome",
)

# Nom des fichiers jamais référencés depuis un état (§5.4)
FORBIDDEN_PATH_FRAGMENTS: tuple[str, ...] = (
    "evaluation/",
    "result/",
    "prediction/",
)

# Types d'événements admissibles pour les snapshots événementiels (§6.2)
EVENT_SNAPSHOT_TYPES = frozenset({"goal", "red_card", "penalty", "substitution"})

INFORMATION_TIERS = ("A", "B", "C")


class LeakageReport:
    """Rapport des violations détectées sur un snapshot.

    Un snapshot est valide si et seulement si `violations` est vide.
    """

    def __init__(self, snapshot_id: str, violations: list[str]) -> None:
        self.snapshot_id = snapshot_id
        self.violations = violations

    @property
    def has_leakage(self) -> bool:
        return bool(self.violations)

    def __repr__(self) -> str:  # pragma: no cover — debug
        return f"LeakageReport({self.snapshot_id!r}, {len(self.violations)} violations)"


def check_no_future_events(
    snapshot: dict[str, Any], events: Iterable[dict[str, Any]]
) -> list[str]:
    """Test 1 (§5.5) : aucun événement postérieur au cutoff dans l'état.

    L'état sérialisé ne doit référencer aucun événement dont
    `elapsed_seconds` dépasse `cutoff_seconds` pour le même match.
    """
    cutoff = snapshot["cutoff_seconds"]
    match = snapshot["match_id"]
    future = [
        e
        for e in events
        if e.get("match_id") == match and e.get("elapsed_seconds", 0) > cutoff
    ]
    if future:
        serialized = canonical_json(snapshot.get("state", {}))
        leaks: list[str] = []
        for e in future:
            # l'événement fuit s'il (ou son id) apparaît dans l'état
            ev_id = str(e.get("event_id", ""))
            if ev_id and ev_id in serialized:
                leaks.append(f"événement futur {ev_id} référencé dans state_json")
        return leaks
    return []


def check_no_final_fields(snapshot: dict[str, Any]) -> list[str]:
    """Test 2 (§5.5) : aucun champ final dans l'état sérialisé.

    Le test inspecte les clés, les valeurs, les métadonnées et le texte
    sérialisé complet (§5.4), en minuscules.
    """
    serialized = json.dumps(snapshot.get("state", {}), sort_keys=True).lower()
    return [
        f"champ interdit détecté : {frag}"
        for frag in FORBIDDEN_KEY_FRAGMENTS
        if frag in serialized
    ]


def check_pre_match_sources_before_cutoff(
    snapshot: dict[str, Any],
    contexts: Iterable[dict[str, Any]],
    matches_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    """Test 3 (§5.5) : sources pré-match strictement antérieures au cutoff.

    Chaque match source utilisé par une feature doit vérifier
    `available_timestamp` < `T_pre_match_cutoff` (§5.2).
    """
    try:
        cutoff = snapshot["state"]["metadata"]["pre_match_cutoff_timestamp"]
        used_ids = set(snapshot["state"]["metadata"]["pre_match_source_match_ids"])
    except (KeyError, TypeError):
        return []  # pas de bloc pré-match dans ce snapshot (Tier sans pré-match)

    violations: list[str] = []
    ctx_by_match: dict[str, dict[str, Any]] = {}
    for c in contexts:
        ctx_by_match.setdefault(c.get("match_id", ""), c)
        # un contexte peut référencer plusieurs matchs sources via source_match_ids
    for m in matches_by_id.values():
        ctx_by_match.setdefault(m["match_id"], m)

    for used in used_ids:
        record = ctx_by_match.get(used) or matches_by_id.get(used)
        if record is None:
            violations.append(f"match source {used} introuvable (provenance non auditable)")
            continue
        available = record.get("available_timestamp") or record.get("date_utc")
        if available is None or not (available < cutoff):
            violations.append(
                f"match source {used} disponible à {available!r}, >= cutoff {cutoff!r}"
            )
    return violations


def check_state_fields_against_cutoff(snapshot: dict[str, Any]) -> list[str]:
    """Contrôle structurel : cohérence cutoff_seconds / événements embarqués.

    Un snapshot live embarque parfois des événements (Tier B) : chacun doit
    avoir elapsed_seconds <= cutoff_seconds et available_timestamp <=
    cutoff_timestamp (§5.3).
    """
    state = snapshot.get("state", {})
    cutoff_s = snapshot["cutoff_seconds"]
    cutoff_ts = snapshot.get("cutoff_timestamp", "")
    violations: list[str] = []

    live_events = state.get("live", {}).get("events", []) if isinstance(state.get("live"), dict) else []
    for e in live_events:
        if e.get("elapsed_seconds", 0) > cutoff_s:
            violations.append(
                f"événement live à {e.get('elapsed_seconds')}s > cutoff {cutoff_s}s"
            )
        avail = e.get("available_timestamp", "")
        if cutoff_ts and avail and avail > cutoff_ts:
            violations.append(
                f"événement live disponible à {avail} > cutoff_timestamp {cutoff_ts}"
            )

    # Cohérence du score live avec les événements goal inclus (complétude)
    meta_tier = state.get("metadata", {}).get("information_tier", "")
    if meta_tier and meta_tier not in INFORMATION_TIERS:
        violations.append(f"tier d'information inconnu : {meta_tier!r}")

    return violations


def check_snapshot(
    snapshot: dict[str, Any],
    events: Iterable[dict[str, Any]],
    *,
    contexts: Iterable[dict[str, Any]] = (),
    matches_by_id: dict[str, dict[str, Any]] | None = None,
) -> LeakageReport:
    """Exécute tous les tests anti-fuite sur un snapshot (§5.5).

    Args:
        snapshot: enregistrement de snapshot (match_id, cutoff_seconds,
            cutoff_timestamp, state, ...).
        events: événements canoniques du match (et des autres matchs).
        contexts: enregistrements de contexte pré-match.
        matches_by_id: matchs canoniques indexés par match_id.

    Returns:
        LeakageReport avec la liste des violations (vide = valide).
    """
    events = list(events)
    violations: list[str] = []
    violations += check_no_future_events(snapshot, events)
    violations += check_no_final_fields(snapshot)
    violations += check_state_fields_against_cutoff(snapshot)
    violations += check_pre_match_sources_before_cutoff(
        snapshot, contexts, matches_by_id or {}
    )
    sid = snapshot.get("snapshot_id", "<sans-id>")
    return LeakageReport(sid, violations)


def audit_snapshot_set(
    snapshots: Iterable[dict[str, Any]],
    events: Iterable[dict[str, Any]],
    *,
    contexts: Iterable[dict[str, Any]] = (),
    matches_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, LeakageReport]:
    """Applique les tests sur 100 % d'un ensemble de snapshots (§5.5).

    Returns:
        Mapping snapshot_id -> rapport.
    """
    reports: dict[str, LeakageReport] = {}
    for snap in snapshots:
        rep = check_snapshot(snap, events, contexts=contexts, matches_by_id=matches_by_id)
        reports[snap.get("snapshot_id", "<sans-id>")] = rep
    return reports


def leakage_rate(reports: dict[str, LeakageReport]) -> float:
    """Taux de snapshots fuyants ; > 5 % bloque le test final (§11.4)."""
    if not reports:
        return 0.0
    return sum(1 for r in reports.values() if r.has_leakage) / len(reports)
