"""Trip state machine: Planned → Loading → In Transit → Delivered → Invoiced → Paid (+ Cancelled).

Reads VALID_TRANSITIONS from services.operations.event_bus to derive
every legal transition pair and tests them all via parametrize.
"""

from __future__ import annotations

import pytest

from services.operations.event_bus import VALID_TRANSITIONS

pytestmark = pytest.mark.state_machine


def _all_valid_pairs() -> list[tuple[str, str]]:
    """Derive every (from, to) pair from the canonical VALID_TRANSITIONS dict."""
    pairs: list[tuple[str, str]] = []
    for from_status, to_list in VALID_TRANSITIONS.items():
        for to_status in to_list:
            pairs.append((from_status, to_status))
    return pairs


VALID_PAIRS = _all_valid_pairs()


class TestTripValidTransitions:
    """Every legal transition defined in VALID_TRANSITIONS must succeed."""

    @pytest.mark.parametrize("from_status,to_status", VALID_PAIRS)
    def test_valid_transition(
        self, from_status, to_status, workflow_env, event_monitor, db
    ):
        """A legal transition must succeed and emit trip.status_changed."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status=from_status,
        )

        event_monitor.track("trip.status_changed")
        result = workflow_env.transition_status(trip_id, to_status)

        assert (
            result is True or result is not None
        ), f"{from_status} -> {to_status} failed"
        event_monitor.assert_event_published("trip.status_changed")

        trip = workflow_env.get_trip(trip_id)
        assert (
            trip["status"] == to_status
        ), f"Expected {to_status}, got {trip['status']}"


class TestTripInvalidTransitions:
    """Illegal transitions must be rejected with status unchanged."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("Planned", "Delivered"),        # skip Loading + In Transit
            ("Planned", "In Transit"),       # skip Loading
            ("Planned", "Paid"),             # ridiculous jump
            ("Loading", "Delivered"),        # skip In Transit
            ("Delivered", "Planned"),        # not a valid backward transition
            ("Delivered", "Paid"),           # skip Invoiced
            ("Paid", "Delivered"),           # no backward from terminal
            ("Paid", "Planned"),             # way backward from terminal
            ("Paid", "Cancelled"),           # no Cancelled from terminal
            ("Cancelled", "In Transit"),     # only -> Planned from Cancelled
            ("Cancelled", "Loading"),        # only -> Planned from Cancelled
            ("Cancelled", "Delivered"),      # only -> Planned from Cancelled
            ("In Transit", "Planned"),       # not in VALID_TRANSITIONS
            ("In Transit", "Paid"),          # skip Delivered + Invoiced
            ("Invoiced", "Planned"),         # way backward
            ("Invoiced", "In Transit"),      # skip Delivered backward then forward
        ],
    )
    def test_invalid_transition_rejected(
        self, from_status, to_status, workflow_env, db
    ):
        """Illegal transition must return False and leave status unchanged."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status=from_status,
        )

        result = workflow_env.transition_status(trip_id, to_status)
        assert result is False, (
            f"{from_status} -> {to_status} should be rejected, "
            f"got {result}"
        )

        trip = workflow_env.get_trip(trip_id)
        assert trip["status"] == from_status, (
            f"Status changed illegally: "
            f"{from_status} -> {trip['status']}"
        )


class TestTripEdgeCaseTransitions:
    """Edge cases: same-status, archived trips, non-existent trips."""

    def test_same_status_is_no_op(self, workflow_env, db):
        """Transitioning to the same status should succeed silently."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        result = workflow_env.transition_status(trip_id, "Planned")
        assert result is True, "Same-status transition should succeed"

    def test_nonexistent_trip_returns_false(self, workflow_env):
        """Transitioning a non-existent trip returns False."""
        result = workflow_env.transition_status(999_999, "Loading")
        assert result is False, "Non-existent trip should return False"
