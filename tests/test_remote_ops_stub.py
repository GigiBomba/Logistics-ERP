"""Tests for client.remote_ops_stub — EventBus and RemoteOpsStub."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from client.remote_ops_stub import RemoteOpsStub
from services.operations.event_bus import EventBus


# The conftest.py reset_singletons fixture resets EventBus._instance = None
# before every test, so each test gets a fresh EventBus.


class TestEventBusPublish:
    """publish() stores events in history."""

    def test_publish_stores_one_event(self):
        bus = EventBus()
        assert len(bus.get_history()) == 0
        bus.publish("trip.created", {"id": 1})
        history = bus.get_history()
        assert len(history) == 1
        assert history[0]["type"] == "trip.created"
        assert history[0]["data"] == {"id": 1}

    def test_publish_default_data_is_empty_dict(self):
        bus = EventBus()
        bus.publish("system.startup")
        assert bus.get_history()[0]["data"] == {}

    def test_publish_sets_event_id_and_timestamp(self):
        bus = EventBus()
        bus.publish("trip.created", {"id": 1})
        ev = bus.get_history()[0]
        assert "id" in ev
        assert len(ev["id"]) == 12  # uuid4 hex[:12]
        assert "timestamp" in ev
        assert isinstance(ev["timestamp"], str)

    def test_publish_stores_multiple_events(self):
        bus = EventBus()
        bus.publish("trip.created", {"id": 1})
        bus.publish("trip.updated", {"id": 1})
        bus.publish("trip.created", {"id": 2})
        assert len(bus.get_history()) == 3

    def test_publish_filter_by_event_type(self):
        bus = EventBus()
        bus.publish("trip.created", {"id": 1})
        bus.publish("trip.updated", {"id": 2})
        bus.publish("trip.created", {"id": 3})
        created_events = bus.get_history(event_type="trip.created")
        assert len(created_events) == 2
        assert all(e["type"] == "trip.created" for e in created_events)

    def test_publish_with_no_subscribers_does_not_raise(self):
        bus = EventBus()
        # No subscribers registered for this event type — should not raise
        bus.publish("trip.created", {"id": 1})
        assert len(bus.get_history()) == 1


class TestEventBusSubscribe:
    """subscribe() registers callbacks that receive published events."""

    def test_subscribed_callback_receives_event(self):
        bus = EventBus()
        received = []

        def callback(ev):
            received.append(ev)

        bus.subscribe("trip.created", callback)
        bus.publish("trip.created", {"id": 42})
        assert len(received) == 1
        assert received[0]["data"]["id"] == 42

    def test_subscribed_callback_receives_correct_event_type_only(self):
        bus = EventBus()
        received = []

        def callback(ev):
            received.append(ev)

        bus.subscribe("trip.created", callback)
        bus.publish("trip.updated", {"id": 99})
        assert len(received) == 0

    def test_multiple_subscribers_all_receive_event(self):
        bus = EventBus()
        received_1 = []
        received_2 = []

        def cb1(ev):
            received_1.append(ev)

        def cb2(ev):
            received_2.append(ev)

        bus.subscribe("trip.created", cb1)
        bus.subscribe("trip.created", cb2)
        bus.publish("trip.created", {})
        assert len(received_1) == 1
        assert len(received_2) == 1

    def test_same_callback_registered_once_only(self):
        """Duplicate subscription does not register the callback twice."""
        bus = EventBus()
        received = []

        def callback(ev):
            received.append(ev)

        bus.subscribe("trip.created", callback)
        bus.subscribe("trip.created", callback)  # duplicate
        bus.publish("trip.created", {})
        assert len(received) == 1  # called once only

    def test_subscribe_to_custom_event_type(self):
        bus = EventBus()
        received = []

        def callback(ev):
            received.append(ev)

        bus.subscribe("my.custom.event", callback)
        bus.publish("my.custom.event", {"key": "val"})
        assert len(received) == 1
        assert received[0]["data"]["key"] == "val"

    def test_subscribe_to_multiple_event_types(self):
        bus = EventBus()
        received = []

        def callback(ev):
            received.append(ev)

        bus.subscribe("trip.created", callback)
        bus.subscribe("trip.updated", callback)
        bus.publish("trip.created", {})
        bus.publish("trip.updated", {})
        assert len(received) == 2


class TestEventBusUnsubscribe:
    """unsubscribe() removes a previously registered callback."""

    def test_unsubscribe_removes_callback(self):
        bus = EventBus()
        received = []

        def callback(ev):
            received.append(ev)

        bus.subscribe("trip.created", callback)
        bus.unsubscribe("trip.created", callback)
        bus.publish("trip.created", {})
        assert len(received) == 0

    def test_unsubscribe_does_not_affect_other_callbacks(self):
        bus = EventBus()
        received_1 = []
        received_2 = []

        def cb1(ev):
            received_1.append(ev)

        def cb2(ev):
            received_2.append(ev)

        bus.subscribe("trip.created", cb1)
        bus.subscribe("trip.created", cb2)
        bus.unsubscribe("trip.created", cb1)
        bus.publish("trip.created", {})
        assert len(received_1) == 0
        assert len(received_2) == 1

    def test_unsubscribe_non_existent_callback_does_not_raise(self):
        bus = EventBus()

        def callback(ev):
            pass

        bus.unsubscribe("trip.created", callback)  # should not raise

    def test_unsubscribe_non_existent_event_type_does_not_raise(self):
        bus = EventBus()

        def callback(ev):
            pass

        bus.unsubscribe("nonexistent.event", callback)  # should not raise

    def test_unsubscribe_from_wrong_event_type_keeps_subscription(self):
        bus = EventBus()
        received = []

        def callback(ev):
            received.append(ev)

        bus.subscribe("trip.created", callback)
        bus.unsubscribe("trip.updated", callback)  # different type
        bus.publish("trip.created", {})
        assert len(received) == 1


class TestEventBusReset:
    """reset() clears all subscribers and history."""

    def test_reset_clears_history(self):
        bus = EventBus()
        bus.publish("trip.created", {})
        bus.publish("trip.updated", {})
        bus.reset()
        assert len(bus.get_history()) == 0

    def test_reset_clears_subscribers(self):
        bus = EventBus()
        received = []

        def callback(ev):
            received.append(ev)

        bus.subscribe("trip.created", callback)
        bus.reset()
        bus.publish("trip.created", {})
        assert len(received) == 0

    def test_reset_allows_new_subscribers(self):
        bus = EventBus()
        bus.reset()
        received = []

        def callback(ev):
            received.append(ev)

        bus.subscribe("trip.created", callback)
        bus.publish("trip.created", {})
        assert len(received) == 1

    def test_reset_empty_bus_does_not_raise(self):
        bus = EventBus()
        bus.reset()
        bus.reset()  # second reset on clean slate


class TestEventBusHistoryLimit:
    """History is bounded by maxlen (default 100)."""

    def test_history_respects_limit_parameter(self):
        bus = EventBus()
        for i in range(10):
            bus.publish("trip.created", {"idx": i})
        filtered = bus.get_history(limit=3)
        assert len(filtered) == 3
        assert filtered[-1]["data"]["idx"] == 9
        assert filtered[0]["data"]["idx"] == 7


class TestRemoteOpsStub:
    """RemoteOpsStub provides EventBus and no-op lifecycle."""

    def test_initializes_with_event_bus(self):
        ops = RemoteOpsStub()
        assert isinstance(ops.event_bus, EventBus)

    def test_initializes_with_undo_stack(self):
        ops = RemoteOpsStub()
        assert ops.undo_stack is not None
        assert ops.undo_stack.can_undo() is False
        assert ops.undo_stack.can_redo() is False
        assert ops.undo_stack.commands == []

    def test_start_is_noop(self):
        ops = RemoteOpsStub()
        ops.start()  # should not raise

    def test_stop_is_noop(self):
        ops = RemoteOpsStub()
        ops.stop()  # should not raise

    def test_configure_smtp_from_db_is_noop(self):
        ops = RemoteOpsStub()
        ops._configure_smtp_from_db()  # should not raise

    def test_get_active_alerts_returns_empty_list_without_api_client(self):
        # NOTE: RemoteOpsStub is now API-BACKED — get_active_alerts() reads
        # GET /api/v1/alerts via the ApiClient.  Without an api_client it
        # degrades to [] so the UI never crashes offline.
        ops = RemoteOpsStub()
        assert ops.get_active_alerts() == []
        assert ops.get_active_alerts(limit=10) == []

    def test_get_active_alerts_is_api_backed(self):
        """get_active_alerts() surfaces server-side alerts via the API.

        The backend runs the OperationsEngine workers; the stub proxies
        get_active_alerts() to GET /api/v1/alerts (list) instead of
        returning a hollow empty list.
        """
        api = MagicMock()
        api.list_alerts.return_value = {
            "items": [
                {"id": "a1", "type": "maintenance", "message": "Oil change due",
                 "status": "active"},
                {"id": "a2", "type": "insurance", "message": "Insurance expires soon",
                 "status": "active"},
            ],
            "total": 2,
        }
        ops = RemoteOpsStub(api_client=api)
        alerts = ops.get_active_alerts(limit=10)
        assert len(alerts) == 2
        assert alerts[0].id == "a1"
        assert alerts[0].message == "Oil change due"
        assert alerts[0].type == "maintenance"
        assert alerts[1].status == "active"
        api.list_alerts.assert_called_once_with(limit=10)

    def test_get_active_alerts_returns_empty_on_api_error(self):
        """API failure degrades to [] instead of raising."""
        api = MagicMock()
        api.list_alerts.side_effect = RuntimeError("API unreachable")
        ops = RemoteOpsStub(api_client=api)
        assert ops.get_active_alerts() == []

    def test_get_active_alert_count_returns_zero_without_api_client(self):
        # NOTE: RemoteOpsStub is now API-BACKED — get_active_alert_count()
        # reads GET /api/v1/alerts/count via the ApiClient.  Without an
        # api_client it degrades to 0 so the UI never crashes offline.
        ops = RemoteOpsStub()
        assert ops.get_active_alert_count() == 0

    def test_get_active_alert_count_is_api_backed(self):
        """get_active_alert_count() reads the count from the alerts API."""
        api = MagicMock()
        api.get_alert_count.return_value = {"count": 7}
        ops = RemoteOpsStub(api_client=api)
        assert ops.get_active_alert_count() == 7
        api.get_alert_count.assert_called_once_with()

    def test_get_active_alert_count_returns_zero_on_api_error(self):
        """API failure degrades to 0 instead of raising."""
        api = MagicMock()
        api.get_alert_count.side_effect = RuntimeError("API unreachable")
        ops = RemoteOpsStub(api_client=api)
        assert ops.get_active_alert_count() == 0

    def test_resolve_alert_is_api_backed(self):
        """resolve_alert() proxies to POST /api/v1/alerts/{id}/resolve."""
        api = MagicMock()
        api.resolve_alert.return_value = {"status": "resolved"}
        ops = RemoteOpsStub(api_client=api)
        assert ops.resolve_alert("a1") is True
        api.resolve_alert.assert_called_once_with("a1")

    def test_resolve_alert_returns_false_without_api_client(self):
        ops = RemoteOpsStub()
        assert ops.resolve_alert("a1") is False

    def test_resolve_alert_returns_false_on_api_error(self):
        api = MagicMock()
        api.resolve_alert.side_effect = RuntimeError("API unreachable")
        ops = RemoteOpsStub(api_client=api)
        assert ops.resolve_alert("a1") is False

    def test_event_bus_is_persistent(self):
        ops = RemoteOpsStub()
        assert ops.event_bus is ops.event_bus

    def test_publish_subscribe_through_stub(self):
        """RemoteOpsStub delegates publish/subscribe to its EventBus."""
        ops = RemoteOpsStub()
        received = []

        def callback(ev):
            received.append(ev)

        ops.event_bus.subscribe("trip.created", callback)
        ops.event_bus.publish("trip.created", {"id": 1})
        assert len(received) == 1
        assert received[0]["data"]["id"] == 1

    def test_accepts_api_client(self):
        api_client = MagicMock()
        ops = RemoteOpsStub(api_client=api_client)
        assert ops._api_client is api_client

    def test_api_client_defaults_to_none(self):
        ops = RemoteOpsStub()
        assert ops._api_client is None

    def test_undo_stack_clear_push_pop(self):
        ops = RemoteOpsStub()
        ops.undo_stack.clear()        # no-op
        ops.undo_stack.push("cmd")     # no-op
        assert ops.undo_stack.pop() is None
        assert ops.undo_stack.last_undo_command() is None
        assert ops.undo_stack.last_redo_command() is None
