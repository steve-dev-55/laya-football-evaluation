"""Fixtures synthétiques déterministes (protocole §0.2, §5.5, §21).

AUCUNE donnée réelle : 2 compétitions × 2 saisons × 8 matchs avec événements
(buts, corners, cartons, penalties, remplacements — avec elapsed_seconds et
available_timestamp calculé par le nettoyeur) et statistiques live par trames
de 15 minutes. Tout est écrit dans tmp_path : le dépôt n'est jamais pollué.
"""

from __future__ import annotations

import pytest

from tests.helpers import build_environment


@pytest.fixture()
def synth_env(tmp_path):
    """Environnement isolé complet (raw + config + manifeste + base)."""
    return build_environment(tmp_path)
