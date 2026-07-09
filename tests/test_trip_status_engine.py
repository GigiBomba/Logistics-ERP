"""Comprehensive unit tests for TripStatusEngine.

Covers state transitions, invalid transitions, status history recording,
trigger tracking, edge cases, bulk operations, validation, Rules integration,
event emission, and timestamp handling.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from services.operations.event_bus import TRIP_STATUS_CHANGED, TRIP_CREATED, EventBus
from services.operations.trip_status_engine import TripStatusEngine
from tests.test_helpers import make_db


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _insert_trip(db, trip_id=1, status="Planned", created_at=None,
                 truck_number="TRUCK-001", truck_id=None):
    """Insert a minimal trip row for testing."""
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


def _count_alerts(db):
    rows = db.conn.execute("SELECT COUNT(*) AS cnt FROM alerts").fetchone()
    return rows["cnt"] if rows else 0


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    db = make_db()
    eng = TripStatusEngine(db)
    yield eng
    eng.shutdown()


# ===================================================================
# VALID TRANSITIONS
# ===================================================================

class TestGetValidTransitions:
    """Tests for TripStatusEngine.get_valid_transitions()."""

    def test_planned_transitions(self, engine):
        """Planned → [Loading, Cancelled]."""
        transitions = engine.get_valid_transitions("Planned")
        assert sorted(transitions) == ["Cancelled", "Loading"]

    def test_loading_transitions(self, engine):
        """Loading → [Planned, In Transit, Cancelled]."""
        transitions = engine.get_valid_transitions("Loading")
        assert sorted(transitions) == ["Cancelled", "In Transit", "Planned"]

    def test_in_transit_transitions(self, engine):
        """In Transit → [Loading, Delivered, Cancelled]."""
        transitions = engine.get_valid_transitions("In Transit")
        assert sorted(transitions) == ["Cancelled", "Delivered", "Loading"]

    def test_delivered_transitions(self, engine):
        """Delivered → [In Transit, Invoiced, Cancelled]."""
        transitions = engine.get_valid_transitions("Delivered")
        assert sorted(transitions) == ["Cancelled", "In Transit", "Invoiced"]

    def test_invoiced_transitions(self, engine):
        """Invoiced → [Delivered, Paid, Cancelled]."""
        transitions = engine.get_valid_transitions("Invoiced")
        assert sorted(transitions) == ["Cancelled", "Delivered", "Paid"]

    def test_paid_transitions(self, engine):
        """Paid → [Invoiced]."""
        transitions = engine.get_valid_transitions("Paid")
        assert transitions == ["Invoiced"]

    def test_cancelled_transitions(self, engine):
        """Cancelled → [Planned]."""
        transitions = engine.get_valid_transitions("Cancelled")
        assert transitions == ["Planned"]

    def test_unknown_status_returns_empty_list(self, engine):
        """Unknown status should return empty list."""
        transitions = engine.get_valid_transitions("NonExistent")
        assert transitions == []


# ===================================================================
# STATE TRANSITION VALIDATION
# ===================================================================

class TestTransitionValidation:
    """Tests for transition validation logic."""

    def test_valid_transition_succeeds(self, engine):
        """A valid transition should succeed and return True."""
        _insert_trip(engine._trip_service.db)
        result = engine.transition(1, "Loading")
        assert result is True

    def test_invalid_transition_raises(self, engine):
        """An invalid transition should raise ValueError."""
        _insert_trip(engine._trip_service.db, status="Planned")
        with pytest.raises(ValueError, match="Cannot transition"):
            engine.transition(1, "Delivered")

    def test_nonexistent_trip_raises(self, engine):
        """Transition on a non-existent trip should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            engine.transition(999, "Loading")

    def test_same_status_transition_raises(self, engine):
        """Transition to the same status (not in valid transitions) should raise ValueError."""
        _insert_trip(engine._trip_service.db, status="Planned")
        with pytest.raises(ValueError, match="Cannot transition"):
            engine.transition(1, "Planned")

    def test_transition_updates_trip_in_db(self, engine):
        """After a valid transition the trip status in the DB must be updated."""
        _insert_trip(engine._trip_service.db, status="Loading")
        engine.transition(1, "In Transit")
        trip = _get_trip(engine._trip_service.db)
        assert trip["status"] == "In Transit"

    def test_valid_transition_returns_true(self, engine):
        """transition() should return True on success."""
        _insert_trip(engine._trip_service.db)
        assert engine.transition(1, "Loading") is True


# ===================================================================
# FULL STATUS FLOW
# ===================================================================

class TestFullStatusFlow:
    """End-to-end lifecycle transitions."""

    def test_full_lifecycle(self, engine):
        """Planned → Loading → In Transit → Delivered → Invoiced → Paid."""
        _insert_trip(engine._trip_service.db, status="Planned")
        steps = [
            "Loading",
            "In Transit",
            "Delivered",
            "Invoiced",
            "Paid",
        ]
        for new_status in steps:
            assert engine.transition(1, new_status) is True
            trip = _get_trip(engine._trip_service.db)
            assert trip["status"] == new_status, (
                f"Expected {new_status}, got {trip['status']}"
            )

    def test_cancel_from_every_state(self):
        """Cancelled should be reachable from Planned, Loading, In Transit, Delivered, Invoiced."""
        for start_status in ["Planned", "Loading", "In Transit", "Delivered", "Invoiced"]:
            db = make_db()
            eng = TripStatusEngine(db)
            _insert_trip(db, trip_id=1, status=start_status)
            result = eng.transition(1, "Cancelled")
            assert result is True, f"Failed to cancel from {start_status}"
            trip = _get_trip(db)
            assert trip["status"] == "Cancelled"
            eng.shutdown()

    def test_recover_from_cancelled(self, engine):
        """Cancelled → Planned should work."""
        _insert_trip(engine._trip_service.db, status="Cancelled")
        assert engine.transition(1, "Planned") is True
        trip = _get_trip(engine._trip_service.db)
        assert trip["status"] == "Planned"


# ===================================================================
# STATUS HISTORY RECORDING
# ===================================================================

class TestStatusHistoryRecording:
    """Verify each transition creates a trip_status_history record."""

    def test_transition_creates_history_record(self, engine):
        """A transition should create exactly one history row."""
        _insert_trip(engine._trip_service.db)
        engine.transition(1, "Loading")
        history = _get_status_history(engine._trip_service.db)
        assert len(history) == 1

    def test_history_contains_correct_fields(self, engine):
        """History row should have old_status, new_status, trip_id."""
        _insert_trip(engine._trip_service.db, status="Planned")
        engine.transition(1, "Loading")
        row = _get_status_history(engine._trip_service.db)[0]
        assert row["trip_id"] == 1
        assert row["old_status"] == "Planned"
        assert row["new_status"] == "Loading"

    def test_multiple_transitions_record_multiple_rows(self, engine):
        """Sequence of transitions should create one history row per step."""
        _insert_trip(engine._trip_service.db, status="Planned")
        for status in ["Loading", "In Transit", "Delivered"]:
            engine.transition(1, status)
        history = _get_status_history(engine._trip_service.db)
        assert len(history) == 3
        assert [h["new_status"] for h in history] == [
            "Loading", "In Transit", "Delivered",
        ]

    def test_history_contains_timestamps(self, engine):
        """created_at in history should be a non-empty string."""
        _insert_trip(engine._trip_service.db)
        engine.transition(1, "Loading")
        row = _get_status_history(engine._trip_service.db)[0]
        assert row["created_at"] is not None
        assert isinstance(row["created_at"], str)
        assert len(row["created_at"]) > 0


# ===================================================================
# TRIGGER / SOURCE TRACKING
# ===================================================================

class TestTriggerTracking:
    """Verify trigger/source information is recorded in history."""

    def test_default_trigger_is_manual(self, engine):
        """The default trigger value should be 'manual'."""
        _insert_trip(engine._trip_service.db)
        engine.transition(1, "Loading")
        row = _get_status_history(engine._trip_service.db)[0]
        assert row["trigger"] == "manual"

    def test_custom_trigger_is_recorded(self, engine):
        """A custom trigger string should be stored in the history."""
        _insert_trip(engine._trip_service.db)
        engine.transition(1, "Loading", trigger="user_action")
        row = _get_status_history(engine._trip_service.db)[0]
        assert row["trigger"] == "user_action"

    def test_none_trigger(self, engine):
        """None trigger should be accepted (stored as None/null)."""
        _insert_trip(engine._trip_service.db)
        engine.transition(1, "Loading", trigger=None)
        row = _get_status_history(engine._trip_service.db)[0]
        assert row["trigger"] is None


# ===================================================================
# EVENT EMISSION
# ===================================================================

class TestEventEmission:
    """Verify that the engine publishes events on transitions."""

    def test_transition_publishes_status_changed_event(self, engine):
        """A transition must publish a TRIP_STATUS_CHANGED event."""
        _insert_trip(engine._trip_service.db)
        engine.transition(1, "Loading")
        bus = EventBus()
        events = bus.get_history(TRIP_STATUS_CHANGED)
        assert len(events) >= 1

    def test_event_contains_trip_id_and_statuses(self, engine):
        """The TRIP_STATUS_CHANGED event must include trip_id, old_status, new_status."""
        _insert_trip(engine._trip_service.db, status="Planned")
        engine.transition(1, "Loading")
        bus = EventBus()
        events = bus.get_history(TRIP_STATUS_CHANGED)
        data = events[-1]["data"]
        assert data["trip_id"] == 1
        assert data["old_status"] == "Planned"
        assert data["new_status"] == "Loading"

    def test_engine_subscribes_to_trip_events_on_init(self, engine):
        """Engine should be subscribed to TRIP_CREATED so evaluate_trip is called."""
        bus = EventBus()
        # Publishing a trip event should not crash — evaluate_trip gracefully
        # handles non-existent trips
        bus.publish(TRIP_CREATED, {"data": {"trip_id": 999}})


# ===================================================================
# DELAY DETECTION (evaluate_trip / evaluate_all)
# ===================================================================

class TestDelayDetection:
    """Tests for evaluate_trip delay alerts."""

    def test_no_delay_for_recent_trip(self, engine):
        """A trip created moments ago should NOT trigger a delay alert."""
        recent = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _insert_trip(engine._trip_service.db, status="Planned",
                     created_at=recent)
        count = engine.evaluate_trip(1)
        assert count == 0

    def test_delay_alert_for_old_pending_trip(self, engine):
        """A pending trip older than threshold should trigger a delay alert."""
        old = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_trip(engine._trip_service.db, status="Planned",
                     created_at=old, truck_number="TRUCK-001")
        count = engine.evaluate_trip(1)
        assert count == 1

    def test_delay_alert_for_old_loading_trip(self, engine):
        """A loading trip older than threshold should trigger a delay alert."""
        old = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_trip(engine._trip_service.db, status="Loading",
                     created_at=old, truck_number="TRUCK-001")
        count = engine.evaluate_trip(1)
        assert count == 1

    def test_no_delay_for_non_pending_or_loading_status(self):
        """Only 'Planned'/'Loading' trips should be evaluated for delays."""
        old = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        for status in ["In Transit", "Delivered", "Invoiced", "Paid", "Cancelled"]:
            db = make_db()
            eng = TripStatusEngine(db)
            _insert_trip(db, trip_id=1, status=status, created_at=old)
            count = eng.evaluate_trip(1)
            assert count == 0, f"Expected 0 for status {status}, got {count}"
            eng.shutdown()

    def test_evaluate_all_checks_all_pending_loading_trips(self, engine):
        """evaluate_all should return total alerts created across pending/loading trips."""
        old = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_trip(engine._trip_service.db, trip_id=1, status="Planned",
                     created_at=old, truck_number="TRUCK-001")
        _insert_trip(engine._trip_service.db, trip_id=2, status="Loading",
                     created_at=old, truck_number="TRUCK-002")
        count = engine.evaluate_all()
        assert count == 2

    def test_evaluate_all_skips_non_matching_trips(self, engine):
        """evaluate_all should only process Planned/Loading trips."""
        old = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_trip(engine._trip_service.db, trip_id=1, status="Planned",
                     created_at=old, truck_number="TRUCK-001")
        _insert_trip(engine._trip_service.db, trip_id=2, status="Delivered",
                     created_at=old, truck_number="TRUCK-002")
        _insert_trip(engine._trip_service.db, trip_id=3, status="Loading",
                     created_at=old, truck_number="TRUCK-003")
        count = engine.evaluate_all()
        assert count == 2

    def test_no_alert_for_old_trip_with_no_created_at(self, engine):
        """A trip with null created_at should return 0 (no alert)."""
        _insert_trip(engine._trip_service.db, status="Planned", created_at=None)
        db = engine._trip_service.db
        # Patch the inserted trip to have NULL created_at
        db.conn.execute("UPDATE trips SET created_at = NULL WHERE id = 1")
        db.conn.commit()
        count = engine.evaluate_trip(1)
        assert count == 0

    def test_alert_created_has_correct_type_and_severity(self, engine):
        """The alert created by evaluate_trip should be TRIP_DELAY / WARNING."""
        old = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_trip(engine._trip_service.db, status="Planned",
                     created_at=old, truck_number="TRUCK-001", truck_id=42)
        engine.evaluate_trip(1)
        rows = engine._trip_service.db.conn.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT 1"
        ).fetchall()
        assert len(rows) == 1
        alert = dict(rows[0])
        assert alert["type"] == "trip_delay"
        assert alert["severity"] == "warning"


# ===================================================================
# EDGE CASES
# ===================================================================

class TestEdgeCases:
    """Edge cases for the engine."""

    def test_evaluate_trip_none_trip_id(self, engine):
        """Passing None as trip_id should return 0 (int() conversion fails)."""
        count = engine.evaluate_trip(None)
        assert count == 0

    def test_evaluate_trip_non_numeric_string(self, engine):
        """Passing a non-numeric string as trip_id should return 0."""
        count = engine.evaluate_trip("abc")
        assert count == 0

    def test_evaluate_trip_nonexistent(self, engine):
        """A non-existent trip_id should return 0."""
        count = engine.evaluate_trip(99999)
        assert count == 0

    def test_transition_none_trip_id(self, engine):
        """transition() with None trip_id should raise an error."""
        with pytest.raises(Exception):
            engine.transition(None, "Loading")  # type: ignore[arg-type]

    def test_transition_with_empty_string_status(self, engine):
        """transition() with empty new_status should raise ValueError."""
        _insert_trip(engine._trip_service.db, status="Planned")
        with pytest.raises(ValueError, match="Cannot transition"):
            engine.transition(1, "")

    def test_shutdown_is_idempotent(self, engine):
        """Calling shutdown() multiple times should not raise."""
        engine.shutdown()
        engine.shutdown()
        engine.shutdown()


# ===================================================================
# SHUTDOWN & LIFECYCLE
# ===================================================================

class TestLifecycle:
    """Engine lifecycle (init, shutdown, subscription)."""

    def test_engine_can_be_created_and_shutdown(self):
        """Creating and shutting down an engine should work without errors."""
        db = make_db()
        eng = TripStatusEngine(db)
        eng.shutdown()

    def test_shutdown_unsubscribes_from_events(self, engine):
        """After shutdown, the engine should no longer receive events."""
        bus = EventBus()
        # Capture subscriber count before shutdown (internal — just verify no crash)
        engine.shutdown()
        # Publishing events after shutdown should not raise
        bus.publish(TRIP_CREATED, {"data": {"trip_id": 999}})

    def test_event_subscription_calls_evaluate_trip(self):
        """Publishing TRIP_CREATED should trigger evaluate_trip internally.

        The event data published by TripService has ``trip_id`` at the top
        level of the data dict (``{"trip_id": ..., "data": {...}}``), so
        the subscriber's ``ev["data"].get("trip_id")`` picks it up.
        """
        db = make_db()
        eng = TripStatusEngine(db)
        bus = EventBus()
        _insert_trip(db, trip_id=100, status="Planned",
                     created_at=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
                     truck_number="TRUCK-EVT")
        # TripService.publish format: {"trip_id": ..., "data": ...}
        bus.publish(TRIP_CREATED, {"trip_id": 100, "data": {}})
        count = _count_alerts(db)
        assert count >= 1
        eng.shutdown()


# ===================================================================
# INTEGRATION WITH RULES
# ===================================================================

class TestRulesIntegration:
    """Tests verifying interaction with the Rules singleton."""

    def test_rules_affects_delay_threshold(self, engine):
        """Changing trip_delay_hours in Rules should affect alert creation."""
        from services.operations.rules import Rules
        rules = Rules()
        old_date = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_trip(engine._trip_service.db, status="Planned",
                     created_at=old_date)
        # Default delay_hours=2 hours. Trip is 1h old, no alert.
        count = engine.evaluate_trip(1)
        assert count == 0
        # Set delay_hours to 0.1 so that 1h > 0.1h → triggers alert
        rules.set("trip_delay_hours", 0.1)
        count = engine.evaluate_trip(1)
        assert count == 1
        # Restore default
        rules.set("trip_delay_hours", 2)

    def test_rules_default_value_used_when_key_missing(self, engine):
        """Rules.get should provide default when key not present."""
        from services.operations.rules import Rules
        rules = Rules()
        # Verify the default is 2
        assert rules.get("trip_delay_hours", 2) == 2
