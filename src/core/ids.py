"""Identifiants déterministes et idempotence (protocole §4.3).

Formules imposées :
- team_id    = SHA256(competition_id + ':' + canonical_team_name)
- match_id   = SHA256(competition_id + ':' + season + ':' + kickoff_timestamp
                     + ':' + home_team_id + ':' + away_team_id)
- snapshot_id = match_id + ':' + cutoff_seconds + ':' + information_tier
                + ':' + variant_id
"""

from __future__ import annotations

import hashlib
from typing import Any

from src.core.canonical import canonical_json


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def team_id(competition_id: str, canonical_team_name: str) -> str:
    """Identifiant d'équipe déterministe (§4.3)."""
    return _sha256(f"{competition_id}:{canonical_team_name}")


def match_id(
    competition_id: str,
    season: str,
    kickoff_timestamp: str,
    home_team_id: str,
    away_team_id: str,
) -> str:
    """Identifiant de match déterministe (§4.3).

    `kickoff_timestamp` est le timestamp ISO-8601 UTC canonique du coup
    d'envoi (définition figée dans le manifeste, annexe B).
    """
    return _sha256(
        f"{competition_id}:{season}:{kickoff_timestamp}:{home_team_id}:{away_team_id}"
    )


def snapshot_id(
    match_id: str,
    cutoff_seconds: int,
    information_tier: str,
    variant_id: str,
) -> str:
    """Identifiant de snapshot déterministe (§4.3)."""
    return f"{match_id}:{cutoff_seconds}:{information_tier}:{variant_id}"


def prediction_id(run_id: str, snapshot_id: str, model_version: str) -> str:
    """Identifiant de prédiction déterministe pour un run donné."""
    return _sha256(f"{run_id}:{snapshot_id}:{model_version}")


def content_hash(obj: Any) -> str:
    """Hash SHA-256 du contenu d'un artefact via sa sérialisation canonique."""
    return _sha256(canonical_json(obj))


def sha256_bytes(data: bytes) -> str:
    """Hash SHA-256 de données brutes (réponses API, fichiers)."""
    return hashlib.sha256(data).hexdigest()
