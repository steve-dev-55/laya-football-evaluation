"""Tests anti-fuite obligatoires (protocole §5.4, §5.5).

Le snapshot propre ne produit AUCUNE violation. Tests NÉGATIFS exigés par
§5.5 : événement futur référencé dans l'état, champ final dans l'état, source
pré-match non disponible avant cutoff, événement live postérieur au cutoff.
"""

from __future__ import annotations

import pytest

from src.core.leakage import (
    audit_snapshot_set,
    check_no_final_fields,
    check_no_future_events,
    check_pre_match_sources_before_cutoff,
    check_snapshot,
    check_state_fields_against_cutoff,
    leakage_rate,
)

KICKOFF = "2026-01-01T15:00:00Z"
CUTOFF_TS = "2026-01-01T15:30:00Z"
PRE_MATCH_CUTOFF = KICKOFF


def _clean_state() -> dict:
    """État canonique propre : pré-match + un but live disponible."""
    return {
        "metadata": {
            "competition": "EPL",
            "season": "2025-2026",
            "cutoff_seconds": 1800,
            "cutoff_timestamp": CUTOFF_TS,
            "information_tier": "B",
            "snapshot_type": "fixed",
            "trigger_event_ids": [],
            "pre_match_cutoff_timestamp": PRE_MATCH_CUTOFF,
            "pre_match_source_match_ids": ["m0"],
        },
        "pre_match": {"home": {"form_last_5": "WDLWW"}, "away": {}},
        "live": {
            "score": {"home": 1, "away": 0},
            "events": [
                {
                    "event_id": "e_goal_900",
                    "type": "goal",
                    "team": "home",
                    "elapsed_seconds": 900,
                    "available_timestamp": "2026-01-01T15:15:30Z",
                    "detail": None,
                }
            ],
        },
    }


def _snapshot(state: dict | None = None, cutoff: int = 1800) -> dict:
    return {
        "snapshot_id": "m1:1800:B:main",
        "match_id": "m1",
        "cutoff_seconds": cutoff,
        "cutoff_timestamp": CUTOFF_TS,
        "snapshot_type": "fixed",
        "information_tier": "B",
        "state": state if state is not None else _clean_state(),
    }


def _events() -> list[dict]:
    """Événements canoniques du match (dont un futur et un visible)."""
    return [
        {
            "match_id": "m1",
            "event_id": "e_goal_900",
            "elapsed_seconds": 900,
            "event_type": "goal",
        },
        {
            "match_id": "m1",
            "event_id": "e_goal_2600",
            "elapsed_seconds": 2600,  # postérieur au cutoff 1800
            "event_type": "goal",
        },
    ]


def _contexts() -> list[dict]:
    """Contextes pré-match (replis utilisés par le test 3)."""
    return [
        {"match_id": "m1", "team_id": "t1", "source_match_ids": '["m0"]'},
    ]


def _matches_by_id(available: str = "2025-12-30T16:00:00Z") -> dict[str, dict]:
    return {
        "m0": {
            "match_id": "m0",
            "available_timestamp": available,
            "date_utc": "2025-12-30",
        },
    }


class TestSnapshotPropre:
    """Un snapshot conforme ne déclenche AUCUNE violation (§5.5)."""

    def test_check_snapshot_sans_violation(self) -> None:
        report = check_snapshot(
            _snapshot(), _events(),
            contexts=_contexts(), matches_by_id=_matches_by_id(),
        )
        assert report.violations == []
        assert report.has_leakage is False

    def test_audit_snapshot_set_taux_nul(self) -> None:
        reports = audit_snapshot_set(
            [_snapshot()], _events(),
            contexts=_contexts(), matches_by_id=_matches_by_id(),
        )
        assert leakage_rate(reports) == 0.0

    def test_tier_sans_bloc_pre_match(self) -> None:
        state = {"metadata": {"cutoff_seconds": 0}}
        report = check_snapshot(
            {"snapshot_id": "s", "match_id": "m", "cutoff_seconds": 0, "state": state},
            _events(),
        )
        assert report.has_leakage is False


class TestNegatifFutureEvents:
    """Test négatif §5.5 : événement futur référencé dans l'état."""

    def test_evenement_futur_reference(self) -> None:
        state = _clean_state()
        state["live"]["events"].append(
            {
                "event_id": "e_goal_2600",
                "type": "goal",
                "team": "away",
                "elapsed_seconds": 2600,
                "available_timestamp": "2026-01-01T15:43:30Z",
                "detail": None,
            }
        )
        snapshot = _snapshot(state)
        violations = check_no_future_events(snapshot, _events())
        assert violations
        assert any("e_goal_2600" in v for v in violations)

    def test_evenement_futur_bloque_le_snapshot(self) -> None:
        state = _clean_state()
        state["live"]["events"].append(
            {
                "event_id": "e_goal_2600",
                "type": "goal",
                "team": "away",
                "elapsed_seconds": 2600,
                "available_timestamp": "2026-01-01T15:43:30Z",
                "detail": None,
            }
        )
        report = check_snapshot(
            _snapshot(state), _events(),
            contexts=_contexts(), matches_by_id=_matches_by_id(),
        )
        assert report.has_leakage is True
        # La règle de l'agent snapshot (§14.5) : fuite → statut blocked.
        assert ("blocked" if report.has_leakage else "validated") == "blocked"


class TestNegatifChampsFinaux:
    """Test négatif §5.5 : champ final dans l'état sérialisé."""

    def test_champ_final_score(self) -> None:
        state = _clean_state()
        state["live"]["final_score"] = "2-1"
        assert check_no_final_fields(_snapshot(state))

    def test_champ_full_time(self) -> None:
        state = _clean_state()
        state["metadata"]["full_time"] = "H"
        violations = check_no_final_fields(_snapshot(state))
        assert any("full_time" in v for v in violations)

    def test_champ_actual_result(self) -> None:
        state = _clean_state()
        state["metadata"]["actual_result"] = "1"
        assert check_no_final_fields(_snapshot(state))


class TestNegatifPreMatchSources:
    """Test négatif §5.5 : source pré-match non disponible avant cutoff."""

    def test_source_disponible_apres_cutoff(self) -> None:
        # Disponible 1 h APRÈS le cutoff pré-match → violation.
        matches = _matches_by_id(available="2026-01-01T16:00:00Z")
        violations = check_pre_match_sources_before_cutoff(
            _snapshot(), _contexts(), matches
        )
        assert violations
        assert any("m0" in v for v in violations)

    def test_source_disponible_au_meme_instant(self) -> None:
        # Égalité stricte interdite : disponible == cutoff → violation.
        matches = _matches_by_id(available=PRE_MATCH_CUTOFF)
        assert check_pre_match_sources_before_cutoff(_snapshot(), _contexts(), matches)

    def test_source_disponible_avant_cutoff_acceptee(self) -> None:
        matches = _matches_by_id(available="2025-12-30T16:00:00Z")
        assert check_pre_match_sources_before_cutoff(
            _snapshot(), _contexts(), matches
        ) == []

    def test_source_introuvable(self) -> None:
        violations = check_pre_match_sources_before_cutoff(
            _snapshot(), _contexts(), {}
        )
        assert any("introuvable" in v for v in violations)

    def test_contexte_repli_sans_available(self) -> None:
        # Un contexte de repli sans available_timestamp est signalé :
        # provenance non auditable (§11.4).
        state = _clean_state()
        state["metadata"]["pre_match_source_match_ids"] = ["ctx_only"]
        violations = check_pre_match_sources_before_cutoff(
            _snapshot(state),
            [{"match_id": "ctx_only", "team_id": "t"}],
            {},
        )
        assert violations


class TestNegatifLiveApresCutoff:
    """Test négatif §5.5 : événement live postérieur au cutoff."""

    def test_evenement_live_apres_cutoff(self) -> None:
        state = _clean_state()
        state["live"]["events"].append(
            {
                "event_id": "e_goal_2000",
                "type": "goal",
                "team": "home",
                "elapsed_seconds": 2000,  # > cutoff 1800
                "available_timestamp": "2026-01-01T15:35:00Z",
                "detail": None,
            }
        )
        violations = check_state_fields_against_cutoff(_snapshot(state))
        assert any("2000" in v for v in violations)

    def test_evenement_disponible_apres_cutoff_timestamp(self) -> None:
        state = _clean_state()
        state["live"]["events"] = [
            {
                "event_id": "e_goal_900",
                "type": "goal",
                "team": "home",
                "elapsed_seconds": 900,
                "available_timestamp": "2026-01-01T15:40:00Z",  # > cutoff_ts
                "detail": None,
            }
        ]
        violations = check_state_fields_against_cutoff(_snapshot(state))
        assert any("15:40:00" in v for v in violations)

    def test_tier_inconnu(self) -> None:
        state = _clean_state()
        state["metadata"]["information_tier"] = "Z"
        violations = check_state_fields_against_cutoff(_snapshot(state))
        assert any("tier" in v for v in violations)


class TestTauxDeFuite:
    """leakage_rate > 0 dès qu'un snapshot fuit (§11.4 : > 5 % bloque)."""

    def test_taux_de_fuite_positif(self) -> None:
        leaking_state = _clean_state()
        leaking_state["metadata"]["full_time"] = "H"
        snapshots = []
        for index, state in enumerate(
            (_clean_state(), leaking_state, _clean_state())
        ):
            snap = _snapshot(state)
            snap["snapshot_id"] = f"m1:1800:B:variant{index}"
            snapshots.append(snap)
        reports = audit_snapshot_set(
            snapshots, _events(),
            contexts=_contexts(),
            matches_by_id=_matches_by_id(),
        )
        assert len(reports) == 3
        assert leakage_rate(reports) == pytest.approx(1 / 3)

    def test_taux_de_fuite_avec_fuite(self) -> None:
        leaking_state = _clean_state()
        leaking_state["metadata"]["full_time"] = "H"
        reports = audit_snapshot_set(
            [_snapshot(leaking_state)], _events(),
            contexts=_contexts(), matches_by_id=_matches_by_id(),
        )
        rate = leakage_rate(reports)
        assert rate > 0.0
