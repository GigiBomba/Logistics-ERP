"""Unit tests for EventBus — inject_db, abort_if_trip_is_archived, get_history, etc."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.operations.event_bus import EventBus
from tests.test_helpers import make_db


@pytest.fixture
def fresh_bus():
    """Return a brand-new EventBus with clean state (no history, no subscribers beyond defaults)."""
    bus = EventBus()
    bus._history.clear()
    return bus


# ── inject_db ──────────────────────────────────────────────────────────


def test_inject_db_sets_db_attribute():
    """inject_db stores the db reference on the bus instance."""
    db = make_db()
    bus = EventBus()
    bus.inject_db(db)
    assert bus._db is db


# ── abort_if_trip_is_archived ──────────────────────────────────────────


class TestAbortIfTripIsArchived:
    """Tests for EventBus.abort_if_trip_is_archived()."""

    def test_returns_true_when_archived(self):
        """Trip with archived==1 → return True."""
        db = make_db()
        bus = EventBus()
        bus.inject_db(db)
        with patch("services.trip_service.TripService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc
            mock_svc.get_by_id.return_value = {"id": 42, "archived": 1}
            result = bus.abort_if_trip_is_archived(42)
            assert result is True
            mock_svc.get_by_id.assert_called_once_with(42)

    def test_returns_false_when_not_archived(self):
        """Trip with archived==0 → return False."""
        db = make_db()
        bus = EventBus()
        bus.inject_db(db)
        with patch("services.trip_service.TripService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc
            mock_svc.get_by_id.return_value = {"id": 42, "archived": 0}
            result = bus.abort_if_trip_is_archived(42)
            assert result is False

    def test_returns_false_when_trip_not_found(self):
        """get_by_id returns None → return False."""
        db = make_db()
        bus = EventBus()
        bus.inject_db(db)
        with patch("services.trip_service.TripService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc
            mock_svc.get_by_id.return_value = None
            result = bus.abort_if_trip_is_archived(42)
            assert result is False

    def test_returns_false_when_no_db_injected(self):
        """No _db attribute → return False (safe fallback)."""
        bus = EventBus()
        result = bus.abort_if_trip_is_archived(1)
        assert result is False


# ── get_history ─────────────────────────────────────────────────────────


class TestGetHistory:
    """Tests for EventBus.get_history()."""

    def test_no_filter_returns_all(self, fresh_bus):
        """get_history() without event_type returns all events (up to limit)."""
        fresh_bus.publish("test.one", {"n": 1})
        fresh_bus.publish("test.two", {"n": 2})
        fresh_bus.publish("test.one", {"n": 3})
        history = fresh_bus.get_history()
        assert len(history) == 3

    def test_filter_by_event_type(self, fresh_bus):
        """get_history(event_type="test.one") returns only matching events."""
        fresh_bus.publish("test.one", {"n": 1})
        fresh_bus.publish("test.two", {"n": 2})
        fresh_bus.publish("test.one", {"n": 3})
        history = fresh_bus.get_history(event_type="test.one")
        assert len(history) == 2
        for ev in history:
            assert ev["type"] == "test.one"

    def test_filter_returns_empty_when_no_match(self, fresh_bus):
        """Filtering for an event type that was never published returns []."""
        fresh_bus.publish("test.one", {"n": 1})
        history = fresh_bus.get_history(event_type="test.nonexistent")
        assert history == []

    def test_respects_limit(self, fresh_bus):
        """get_history honors the limit parameter."""
        for i in range(10):
            fresh_bus.publish("test.evt", {"i": i})
        history = fresh_bus.get_history(limit=3)
        assert len(history) == 3

    def test_filter_respects_limit(self, fresh_bus):
        """get_history with event_type returns filtered results from the last N items."""
        fresh_bus.publish("test.b", {"n": 1})
        fresh_bus.publish("test.a", {"n": 2})
        fresh_bus.publish("test.b", {"n": 3})
        fresh_bus.publish("test.a", {"n": 4})
        fresh_bus.publish("test.b", {"n": 5})
        fresh_bus.publish("test.a", {"n": 6})
        # Last 2 items are {"n":5} (test.b) and {"n":6} (test.a) → filter gives 1 test.a
        history = fresh_bus.get_history(event_type="test.a", limit=2)
        assert len(history) == 1
        assert history[0]["data"]["n"] == 6


# ── publish variations ──────────────────────────────────────────────────


def test_publish_data_none_works(fresh_bus):
    """Publishing with data=None produces an event with data={} (not None)."""
    received = []
    handler = lambda ev: received.append(ev)
    fresh_bus.subscribe("test.none_data", handler)
    fresh_bus.publish("test.none_data", None)
    assert len(received) == 1
    assert received[0]["data"] == {}


def test_publish_unknown_event_type_works():
    """Publishing an event_type not in ALL_EVENTS creates a dynamic subscriber slot."""
    bus = EventBus()
    bus._history.clear()
    received = []
    handler = lambda ev: received.append(ev)
    bus.subscribe("completely.unknown.event", handler)
    bus.publish("completely.unknown.event", {"x": 1})
    assert len(received) == 1
    assert received[0]["data"] == {"x": 1}
    bus.unsubscribe("completely.unknown.event", handler)


# ── subscribe idempotency ───────────────────────────────────────────────


def test_subscribe_duplicate_callback_not_added_twice(fresh_bus):
    """Subscribing the same callable twice should not add it twice."""
    handler = lambda ev: None
    fresh_bus.subscribe("test.dup", handler)
    fresh_bus.subscribe("test.dup", handler)
    assert len(fresh_bus._subscribers["test.dup"]) == 1
