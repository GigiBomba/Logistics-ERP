"""Regression tests for Phase 1 — EventBus wiring for trucks/clients.

The original bug: adding a truck in the Fleet Manager didn't refresh
the truck dropdown in the Route Planner (and similar mismatches
for the calculator and dispatch board).  The fix publishes
``TRUCK_*`` and ``CLIENT_*`` events from the manager views and has
the consumer views subscribe.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from services.operations.event_bus import (
    CLIENT_CREATED, CLIENT_UPDATED, EventBus, TRUCK_CREATED, TRUCK_DELETED, TRUCK_UPDATED,
)


def _ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _new_db():
    from database.db_manager import DatabaseManager
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    db = DatabaseManager(tmp.name)
    return db, tmp.name


class TestEventBusConstants(unittest.TestCase):
    def test_client_event_constants_defined(self) -> None:
        self.assertEqual(CLIENT_CREATED, "client.created")
        self.assertEqual(CLIENT_UPDATED, "client.updated")

    def test_truck_event_constants_defined(self) -> None:
        self.assertEqual(TRUCK_CREATED, "truck.created")
        self.assertEqual(TRUCK_UPDATED, "truck.updated")
        self.assertEqual(TRUCK_DELETED, "truck.deleted")


class TestEventBusPublish(unittest.TestCase):
    """The EventBus must be able to publish and receive events."""

    def setUp(self) -> None:
        self.bus = EventBus()
        # Save the original subscriber dict and restore after test.
        self._original = dict(self.bus._subscribers)

    def tearDown(self) -> None:
        # Restore original subscribers so we don't pollute the singleton.
        self.bus._subscribers = self._original

    def test_publish_and_subscribe(self) -> None:
        received = []
        handler = lambda ev: received.append(ev)
        self.bus.subscribe("test.event", handler)
        try:
            self.bus.publish("test.event", {"foo": "bar"})
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["type"], "test.event")
            self.assertEqual(received[0]["data"], {"foo": "bar"})
        finally:
            self.bus.unsubscribe("test.event", handler)

    def test_unsubscribe_stops_delivery(self) -> None:
        received = []
        handler = lambda ev: received.append(ev)
        self.bus.subscribe("test.event", handler)
        self.bus.unsubscribe("test.event", handler)
        self.bus.publish("test.event", {})
        self.assertEqual(received, [])

    def test_subscriber_can_be_a_bound_method(self) -> None:
        """Real widgets subscribe their bound methods; this is the
        common pattern and must work."""
        class Listener(QObject):
            def __init__(self):
                super().__init__()
                self.received = []
            def handler(self, ev):
                self.received.append(ev)
        _ensure_qapp()
        listener = Listener()
        self.bus.subscribe("test.event", listener.handler)
        try:
            self.bus.publish("test.event", {"x": 1})
            self.assertEqual(len(listener.received), 1)
            self.assertEqual(listener.received[0]["data"], {"x": 1})
        finally:
            self.bus.unsubscribe("test.event", listener.handler)


class TestTruckEventSubscription(unittest.TestCase):
    """The view that subscribes to TRUCK_* events must receive them."""

    def setUp(self) -> None:
        _ensure_qapp()
        self.bus = EventBus()
        self._original = dict(self.bus._subscribers)

    def tearDown(self) -> None:
        self.bus._subscribers = self._original

    def test_truck_created_received(self) -> None:
        received = []
        handler = lambda ev: received.append(ev)
        self.bus.subscribe(TRUCK_CREATED, handler)
        try:
            self.bus.publish(TRUCK_CREATED, {"truck_id": 1, "plate": "ABC"})
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["data"]["plate"], "ABC")
        finally:
            self.bus.unsubscribe(TRUCK_CREATED, handler)

    def test_truck_updated_received(self) -> None:
        received = []
        handler = lambda ev: received.append(ev)
        self.bus.subscribe(TRUCK_UPDATED, handler)
        try:
            self.bus.publish(TRUCK_UPDATED, {"truck_id": 1, "plate": "XYZ"})
            self.assertEqual(len(received), 1)
        finally:
            self.bus.unsubscribe(TRUCK_UPDATED, handler)

    def test_truck_deleted_received(self) -> None:
        received = []
        handler = lambda ev: received.append(ev)
        self.bus.subscribe(TRUCK_DELETED, handler)
        try:
            self.bus.publish(TRUCK_DELETED, {"truck_id": 1})
            self.assertEqual(len(received), 1)
        finally:
            self.bus.unsubscribe(TRUCK_DELETED, handler)

    def test_truck_event_payload_includes_plate(self) -> None:
        """The plate is needed by the refresh logic to keep a stable
        identity even if the database id changes (which it doesn't,
        but defense in depth).  Verify the Fleet Manager publishes
        the plate."""
        import inspect
        from ui.views import fleet_tab
        src = inspect.getsource(fleet_tab)
        self.assertIn("TRUCK_CREATED", src)
        self.assertIn('"plate":', src)


class TestClientEventSubscription(unittest.TestCase):
    def setUp(self) -> None:
        _ensure_qapp()
        self.bus = EventBus()
        self._original = dict(self.bus._subscribers)

    def tearDown(self) -> None:
        self.bus._subscribers = self._original

    def test_client_created_received(self) -> None:
        received = []
        handler = lambda ev: received.append(ev)
        self.bus.subscribe(CLIENT_CREATED, handler)
        try:
            self.bus.publish(CLIENT_CREATED, {"client_id": 1, "name": "Acme"})
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["data"]["name"], "Acme")
        finally:
            self.bus.unsubscribe(CLIENT_CREATED, handler)

    def test_client_updated_received(self) -> None:
        received = []
        handler = lambda ev: received.append(ev)
        self.bus.subscribe(CLIENT_UPDATED, handler)
        try:
            self.bus.publish(CLIENT_UPDATED, {"client_id": 1, "is_active": 0})
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["data"]["is_active"], 0)
        finally:
            self.bus.unsubscribe(CLIENT_UPDATED, handler)


class TestRoutePlannerSubscribes(unittest.TestCase):
    """Static check: the route planner must subscribe to truck events."""

    def test_subscribes_to_truck_events(self) -> None:
        import inspect
        from ui.views.route_planner_view import QtRoutePlannerView
        src = inspect.getsource(QtRoutePlannerView)
        self.assertIn("TRUCK_CREATED", src)
        self.assertIn("TRUCK_UPDATED", src)
        self.assertIn("TRUCK_DELETED", src)

    def test_has_truck_refresh_button(self) -> None:
        import inspect
        from ui.views.route_planner_view import QtRoutePlannerView
        src = inspect.getsource(QtRoutePlannerView)
        # The plan added a small refresh button next to the truck
        # combo.  Look for the button attribute name and the
        # construction call.
        self.assertIn("_truck_refresh_btn", src)
        self.assertTrue(
            'clicked.connect(self._load_trucks)' in src
            or 'command=self._load_trucks' in src,
            "Expected _truck_refresh_btn wired to _load_trucks",
        )

    def test_unsubscribes_in_shutdown(self) -> None:
        import inspect
        from ui.views.route_planner_view import QtRoutePlannerView
        src = inspect.getsource(QtRoutePlannerView.shutdown)
        # Each subscription should have a matching unsubscribe.
        for evt in ("TRUCK_CREATED", "TRUCK_UPDATED", "TRUCK_DELETED"):
            self.assertIn(
                f"bus.unsubscribe({evt}",
                src,
                f"shutdown() must unsubscribe from {evt}",
            )


class TestCalculatorSubscribes(unittest.TestCase):
    """Static check: the calculator must subscribe to truck + client events."""

    def test_subscribes_to_truck_events(self) -> None:
        import inspect
        from ui.views.calculator_view import QtCalculatorView
        src = inspect.getsource(QtCalculatorView)
        for evt in ("TRUCK_CREATED", "TRUCK_UPDATED", "TRUCK_DELETED"):
            self.assertIn(evt, src)

    def test_subscribes_to_client_events(self) -> None:
        import inspect
        from ui.views.calculator_view import QtCalculatorView
        src = inspect.getsource(QtCalculatorView)
        for evt in ("CLIENT_CREATED", "CLIENT_UPDATED"):
            self.assertIn(evt, src)

    def test_has_refresh_buttons(self) -> None:
        import inspect
        from ui.views.calculator_view import QtCalculatorView
        src = inspect.getsource(QtCalculatorView)
        self.assertIn("_truck_refresh_btn", src)
        self.assertIn("_client_refresh_btn", src)

    def test_unsubscribes_in_shutdown(self) -> None:
        import inspect
        from ui.views.calculator_view import QtCalculatorView
        src = inspect.getsource(QtCalculatorView.shutdown)
        for evt in (
            "TRUCK_CREATED", "TRUCK_UPDATED", "TRUCK_DELETED",
            "CLIENT_CREATED", "CLIENT_UPDATED",
        ):
            self.assertIn(
                f"bus.unsubscribe({evt}",
                src,
                f"shutdown() must unsubscribe from {evt}",
            )


class TestDispatchBoardSubscribes(unittest.TestCase):
    def test_subscribes_to_truck_created_and_deleted(self) -> None:
        import inspect
        from ui.views.dispatch_board_view import QtDispatchBoardView
        src = inspect.getsource(QtDispatchBoardView)
        for evt in ("TRUCK_CREATED", "TRUCK_DELETED"):
            self.assertIn(
                evt, src,
                f"dispatch board must subscribe to {evt}",
            )


if __name__ == "__main__":
    unittest.main()
