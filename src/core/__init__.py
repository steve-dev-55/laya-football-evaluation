"""Noyau du protocole : identifiants, sérialisation, tâches, anti-fuite, métriques, stats."""

from src.core.canonical import canonical_json, state_hash
from src.core.errors import ErrorCode, ValidationError
from src.core.ids import content_hash, match_id, prediction_id, snapshot_id, team_id
from src.core.leakage import (
    LeakageReport,
    audit_snapshot_set,
    check_snapshot,
    leakage_rate,
)

__all__ = [
    "canonical_json",
    "state_hash",
    "ErrorCode",
    "ValidationError",
    "content_hash",
    "match_id",
    "prediction_id",
    "snapshot_id",
    "team_id",
    "LeakageReport",
    "audit_snapshot_set",
    "check_snapshot",
    "leakage_rate",
]
