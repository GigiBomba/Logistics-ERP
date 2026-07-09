from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from services.operations.event_bus import TRIP_STATUS_CHANGED, EventBus
from services.operations.trip_status_engine import TripStatusEngine
from tests.test_helpers import make_db

pytestmark = pytest.mark.mutation


def _insert_trip(db, trip_id=1, status="Planned", created_at=None,
                 truck_number="TRUCK-001", truck_id=None):
    if created_at is None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.conn.execute(
        "INSERT INTO trips (id, status, created_at, truck_number, truck_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (trip_id, status, created_at, truck_number, truck_id),
    )
    db.conn.commit()


def _get_trip(db, trip_id=1):
    row = db.conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    return dict(row) if row else None


def _get_status_history(db, trip_id=1):
    rows = db.conn.execute(
        "SELECT * FROM trip_status_history WHERE trip_id = ? ORDER BY id",
        (trip_id,),
    ).fetchall()
    return [dict(r) for r in rows]


@pytest.fixture
def engine():
    db = make_db()
    eng = TripStatusEngine(db)
    yield eng
    eng.shutdown()


class TestKillMutationTransition:
    """Mutation-killing tests for TripStatusEngine.transition()."""

    def test_nonexistent_trip_raises_value_error(self):
        """Kill: not trip guard deletion (nonexistent trip -> ValueError)."""
        db = make_db()
        eng = TripStatusEngine(db)
        # If 'not trip' guard is removed, trip.get("status") on None -> crash
        with pytest.raises(ValueError, match="not found"):
            eng.transition(999, "Loading")
        eng.shutdown()

    def test_invalid_transition_raises_value_error(self):
        """Kill: 'new_status not in valid' -> 'in' mutation.

        If negation is removed, invalid transitions pass, valid ones raise.
        """
        db = make_db()
        eng = TripStatusEngine(db)
        _insert_trip(db, status="Planned")
        # Delivered is not a valid transition from Planned
        with pytest.raises(ValueError, match="Cannot transition"):
            eng.transition(1, "Delivered")
        eng.shutdown()

    def test_successful_transition_returns_true(self):
        """Kill: return True -> False mutation (successful transition returns True)."""
        db = make_db()
        eng = TripStatusEngine(db)
        _insert_trip(db)
        result = eng.transition(1, "Loading")
        assert result is True
        eng.shutdown()

    def test_transition_succeeds_even_when_history_fails(self):
        """Kill: exception swallowing in history recording removed.

        The history INSERT is wrapped in try/except, so even if it fails,
        the transition should still succeed.
        """
        db = make_db()
        eng = TripStatusEngine(db)
        _insert_trip(db)

        # Break the history table by dropping it momentarily
        db.conn.execute("DROP TABLE trip_status_history")
        db.conn.commit()

        # Should NOT raise — history failure is swallowed
        result = eng.transition(1, "Loading")
        assert result is True

        # Verify trip status WAS updated despite history failure
        trip = _get_trip(db)
        assert trip["status"] == "Loading"
        eng.shutdown()

    def test_event_payload_contains_correct_new_status(self):
        """Kill: event payload missing or wrong new_status field."""
        # Reset EventBus singleton for clean state
        EventBus._instance = None
        EventBus._lock = __import__('threading').Lock()
        bus = EventBus()

        db = make_db()
        eng = TripStatusEngine(db)
        _insert_trip(db, status="Planned")

        eng.transition(1, "Loading")

        events = bus.get_history(TRIP_STATUS_CHANGED)
        assert len(events) >= 1
        data = events[-1]["data"]
        assert data["trip_id"] == 1
        assert data["new_status"] == "Loading"
        assert data["old_status"] == "Planned"
        eng.shutdown()

    def test_valid_planned_to_loading_transition_succeeds(self):
        """Kill: valid transition (Planned -> Loading) succeeds."""
        db = make_db()
        eng = TripStatusEngine(db)
        _insert_trip(db, status="Planned")
        result = eng.transition(1, "Loading")
        assert result is True
        trip = _get_trip(db)
        assert trip["status"] == "Loading"
        eng.shutdown()

    def test_transition_records_history_in_db(self):
        """Kill: history insert statement deletion (transition should create history row)."""
        db = make_db()
        eng = TripStatusEngine(db)
        _insert_trip(db)
        eng.transition(1, "Loading")

        history = _get_status_history(db)
        assert len(history) == 1
        assert history[0]["trip_id"] == 1
        assert history[0]["old_status"] == "Planned"
        assert history[0]["new_status"] == "Loading"
        eng.shutdown()

    def test_transition_publishes_event_on_event_bus(self):
        """Kill: event publish statement deletion (transition should publish event)."""
        EventBus._instance = None
        EventBus._lock = __import__('threading').Lock()

        db = make_db()
        eng = TripStatusEngine(db)
        _insert_trip(db)
        eng.transition(1, "Loading")

        bus = EventBus()
        events = bus.get_history(TRIP_STATUS_CHANGED)
        assert len(events) >= 1
        eng.shutdown()
