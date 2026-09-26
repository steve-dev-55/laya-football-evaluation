"""Tests des identifiants déterministes (protocole §4.3, §0.4).

Vérifie : déterminisme (mêmes entrées → mêmes ID), unicité, longueur 64 hex,
format du snapshot_id.
"""

from __future__ import annotations

import re

from src.core.ids import (
    content_hash,
    match_id,
    prediction_id,
    sha256_bytes,
    snapshot_id,
    team_id,
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _match(competition: str, season: str, kickoff: str, home: str, away: str) -> str:
    return match_id(
        competition,
        season,
        kickoff,
        team_id(competition, home),
        team_id(competition, away),
    )


class TestTeamId:
    """team_id = SHA256(competition_id + ':' + canonical_team_name) (§4.3)."""

    def test_deterministe(self) -> None:
        assert team_id("EPL", "alpha fc") == team_id("EPL", "alpha fc")

    def test_depend_de_la_competition(self) -> None:
        assert team_id("EPL", "alpha fc") != team_id("LaLiga", "alpha fc")

    def test_longueur_64_hex(self) -> None:
        assert HEX64.match(team_id("EPL", "alpha fc"))


class TestMatchId:
    """match_id = SHA256(comp : saison : kickoff : home : away) (§4.3)."""

    def test_deterministe(self) -> None:
        first = _match("EPL", "2021-2022", "2021-08-14T13:00:00Z", "a", "b")
        second = _match("EPL", "2021-2022", "2021-08-14T13:00:00Z", "a", "b")
        assert first == second

    def test_unicite_par_kickoff(self) -> None:
        base = _match("EPL", "2021-2022", "2021-08-14T13:00:00Z", "a", "b")
        shifted = _match("EPL", "2021-2022", "2021-08-21T13:00:00Z", "a", "b")
        reversed_fixture = _match("EPL", "2021-2022", "2021-08-14T13:00:00Z", "b", "a")
        assert len({base, shifted, reversed_fixture}) == 3

    def test_unicite_par_saison_et_competition(self) -> None:
        base = _match("EPL", "2021-2022", "2021-08-14T13:00:00Z", "a", "b")
        other_season = _match("EPL", "2022-2023", "2021-08-14T13:00:00Z", "a", "b")
        other_comp = _match("LaLiga", "2021-2022", "2021-08-14T13:00:00Z", "a", "b")
        assert len({base, other_season, other_comp}) == 3

    def test_longueur_64_hex(self) -> None:
        assert HEX64.match(_match("EPL", "2021-2022", "2021-08-14T13:00:00Z", "a", "b"))


class TestSnapshotId:
    """snapshot_id = match_id + ':' + cutoff + ':' + tier + ':' + variant."""

    def test_format_exact(self) -> None:
        mid = "m" * 64
        sid = snapshot_id(mid, 1800, "B", "main")
        assert sid == f"{mid}:1800:B:main"

    def test_variante_evenementielle_distincte(self) -> None:
        mid = "m" * 64
        assert snapshot_id(mid, 1800, "B", "main") != snapshot_id(
            mid, 1800, "B", "event:abc"
        )

    def test_tiers_et_cutoff_distincts(self) -> None:
        mid = "m" * 64
        ids = {
            snapshot_id(mid, 0, "A", "main"),
            snapshot_id(mid, 0, "B", "main"),
            snapshot_id(mid, 1800, "B", "main"),
            snapshot_id(mid, 1800, "C", "main"),
        }
        assert len(ids) == 4


class TestPredictionIdEtHashes:
    """prediction_id et hashes de contenu (§4.3, §15)."""

    def test_prediction_id_deterministe_et_unique(self) -> None:
        first = prediction_id("run_001", "s1", "laya-mock-1.0.0")
        second = prediction_id("run_001", "s1", "poisson-v1")
        third = prediction_id("run_002", "s1", "laya-mock-1.0.0")
        assert first == prediction_id("run_001", "s1", "laya-mock-1.0.0")
        assert len({first, second, third}) == 3
        assert HEX64.match(first)

    def test_content_hash_deterministe(self) -> None:
        assert content_hash({"b": 1, "a": 2}) == content_hash({"a": 2, "b": 1})
        assert content_hash({"a": 1}) != content_hash({"a": 2})

    def test_sha256_bytes_longueur(self) -> None:
        assert HEX64.match(sha256_bytes(b"donnees brutes"))
        assert sha256_bytes(b"a") != sha256_bytes(b"b")
