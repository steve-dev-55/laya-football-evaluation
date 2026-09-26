"""Codes d'erreur du protocole (§9.3).

Règle : une réponse invalide est enregistrée comme invalide avec son code ;
elle n'est JAMAIS réparée ou renormalisée silencieusement.
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """Codes minimaux imposés par le protocole §9.3."""

    OK = "OK"
    NETWORK_RETRY_EXHAUSTED = "NETWORK_RETRY_EXHAUSTED"
    INVALID_JSON = "INVALID_JSON"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    INVALID_PROBABILITY = "INVALID_PROBABILITY"
    INVALID_PROBABILITY_SUM = "INVALID_PROBABILITY_SUM"
    MISSING_CATEGORY = "MISSING_CATEGORY"
    LEAKAGE_DETECTED = "LEAKAGE_DETECTED"
    CONTEXT_TOO_LONG = "CONTEXT_TOO_LONG"
    SDK_ERROR = "SDK_ERROR"


# Erreurs de validité (pas de reprise automatique sans diagnostic, §9.3)
VALIDITY_ERRORS = frozenset({
    ErrorCode.INVALID_JSON,
    ErrorCode.INVALID_SCHEMA,
    ErrorCode.INVALID_PROBABILITY,
    ErrorCode.INVALID_PROBABILITY_SUM,
    ErrorCode.MISSING_CATEGORY,
    ErrorCode.LEAKAGE_DETECTED,
})


class ValidationError(Exception):
    """Exception de validation d'une réponse ou d'un artefact.

    Attributes:
        code: code d'erreur du protocole.
        detail: message court sans donnée personnelle.
    """

    def __init__(self, code: ErrorCode, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code.value}: {detail}")
