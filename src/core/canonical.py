"""Sérialisation canonique déterministe (protocole §7.1).

Le JSON doit être déterministe : clés triées, nombres avec précision fixée,
valeurs manquantes représentées par null, pas de texte libre non contrôlé,
encodage UTF-8.
"""

from __future__ import annotations

import json
from typing import Any

# Précision fixe des nombres flottants (décision figée, annexe B)
FLOAT_PRECISION = 6


def _normalize(obj: Any) -> Any:
    """Normalise récursivement les nombres pour une sérialisation stable."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        # Précision fixée ; les -0.0 sont normalisés vers 0.0
        rounded = round(obj, FLOAT_PRECISION)
        return rounded + 0.0 if rounded != 0 else 0.0
    if obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    raise TypeError(f"type non sérialisable en canonique : {type(obj)!r}")


def canonical_json(obj: Any) -> str:
    """JSON canonique : clés triées, précision fixe, UTF-8, séparateurs compacts."""
    return json.dumps(
        _normalize(obj),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def state_hash(obj: Any) -> str:
    """Hash d'état d'un snapshot (via la forme canonique)."""
    import hashlib

    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
