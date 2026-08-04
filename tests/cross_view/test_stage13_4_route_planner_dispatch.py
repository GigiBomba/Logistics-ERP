"""Tests for route planner → dispatch integration via EventBus.

Verifies that:
- QtRoutePlannerView subscribes to TRUCK_CREATED / TRUCK_UPDATED / TRUCK_DELETED
  events and refreshes its truck dropdown when those events fire.
- TRIP_CREATED events published on the shared EventBus cause the dispatch board
  to add a card to the appropriate column.
- Shutdown properly removes event subscriptions so that orphaned views do not
  respond to events.
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QWidget

# ── SP workaround ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_qt_app():
    """Ensure Qt app has no stale widgets from prior test modules."""
    from PySide6.QtWidgets import QApplication
    try:
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                try:
                    w.close()
                    w.deleteLater()
                except (RuntimeError, Exception):
                    pass
    except Exception:
        pass
    yield
    try:
        app = QApplication.instance()
        if app:
            try:
                app.processEvents()
            except Exception:
                pass
    except Exception:
        pass


SAMPLE_TRIP_CARD_DATA: dict = {
    "trip_id": "T99",
    "trip_id_num": 99,
    "status": "Planned",
    "truck_plate": "",
    "truck_id": None,
    "driver_name": "",
    "driver_id": None,
    "origin": "Berlin",
    "destination": "Paris",
    "departure_date": "2026-07-24",
    "eta": "2026-07-25",
    "alerts_count": 0,
}


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


class _FakeMapWidget(QWidget):
    """QWidget subclass that ducks the MapWidget interface used by _build_ui."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loadFinished = MagicMock()

    def set_click_callback(self, cb):
        self._test_cb = cb

    def setMinimumWidth(self, w):
        pass

    def _run_js(self, js):
        pass


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    ops.undo_stack = MagicMock()
    ops.get_active_alerts.return_value = []
    ops.get_alerts.return_value = []
    return ops


@pytest.fixture
def route_planner_view(qtbot, qt_widget, monkeypatch):
    """Create QtRoutePlannerView with all heavy dependencies mocked.

    Follows the pattern from ``tests/test_route_planner_view.py``'s
    ``route_planner`` fixture.
    """
    from ui.views.route_planner_view import QtRoutePlannerView

    monkeypatch.setattr(
        "ui.views.route_planner_view.MapWidget",
        lambda *a, **kw: _FakeMapWidget(),
    )
    monkeypatch.setattr(
        "ui.views.route_planner_view.QtRouteMapRenderer",
        lambda *a, **kw: MagicMock(),
    )
    monkeypatch.setattr(
        "ui.views.route_planner_view.RouteStateManager",
        lambda db: MagicMock(),
    )
    monkeypatch.setattr(
        "ui.views.route_planner_view.RoutePersistenceService",
        lambda *a, **kw: MagicMock(),
    )
    monkeypatch.setattr(
        "ui.views.route_planner_view.RouteHistoryService",
        lambda db: MagicMock(),
    )
    view = QtRoutePlannerView(
        qt_widget,
        db=MagicMock(),
        controller=MagicMock(),
        api_client=MagicMock(),
        route_controller=MagicMock(),
    )
    qtbot.addWidget(view)
    yield view
    try:
        with contextlib.suppress(Exception):
            view.shutdown()
    except Exception:
        pass
    finally:
        # Ensure view is properly cleaned up even if C++ object was deleted
        try:
            view.deleteLater()
        except Exception:
            pass


@pytest.fixture
def dispatch_board_view(qtbot, mock_db, mock_ops):
    """Create QtDispatchBoardView with all services mocked at module level.

    Follows the pattern from ``tests/test_dispatch_board_view.py``'s
    ``view_with_mocks`` fixture.
    """
    with (
        patch("ui.views.dispatch_board.dispatch_board.TripService") as mock_ts,
        patch("ui.views.dispatch_board.dispatch_board.FleetService") as mock_fs,
        patch("ui.views.dispatch_board.dispatch_board.ClientService"),
        patch("ui.views.dispatch_board.dispatch_board.DriverTruckService") as mock_dts,
        patch("ui.views.dispatch_board.dispatch_board.TripConflictService") as mock_tcs,
        patch("ui.views.dispatch_board.dispatch_board.DispatchService") as mock_ds,
        patch("ui.views.dispatch_board.dispatch_board.AlertManager"),
        patch("ui.views.dispatch_board.dispatch_board.QtDispatchDetailPanel"),
    ):
        # -- TripService mock -------------------------------------------------
        ts_instance = MagicMock()
        ts_instance.get_by_statuses.return_value = []
        ts_instance.get_by_id.return_value = None
        ts_instance.get_all.return_value = []
        ts_instance._route_repo = MagicMock()
        mock_ts.return_value = ts_instance

        # -- FleetService mock ------------------------------------------------
        fs_instance = MagicMock()
        fs_instance._fleet_repo = MagicMock()
        mock_fs.return_value = fs_instance

        # -- DriverTruckService mock ------------------------------------------
        dts_instance = MagicMock()
        dts_instance._driver_repo = MagicMock()
        mock_dts.return_value = dts_instance

        # -- ConflictService mock ---------------------------------------------
        tcs_instance = MagicMock()
        mock_tcs.return_value = tcs_instance

        # -- DispatchService mock ---------------------------------------------
        ds_instance = MagicMock()
        ds_instance.evaluate_trip_delay.return_value = (False, 0)
        ds_instance.resolve_delay_alert = MagicMock()
        ds_instance.create_delay_alert = MagicMock()
        mock_ds.return_value = ds_instance

        from ui.views.dispatch_board.dispatch_board import QtDispatchBoardView

        view = QtDispatchBoardView(db=mock_db, ops=mock_ops)
        view._dispatch = lambda fn: fn()

        # Wait for the background load thread spawned by __init__ → _start_load
        if view._load_thread is not None and view._load_thread.is_alive():
            view._load_thread.join(timeout=2)

        qtbot.addWidget(view)
        qtbot.wait(50)

        yield view

        view.shutdown()


# ═════════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestRoutePlannerToDispatch:
    """Integration tests between route planner and dispatch board via EventBus."""

    # ── Test 1: subscription verification ─────────────────────────────────

    def test_route_planner_subscribes_to_truck_events(self, route_planner_view):
        """QtRoutePlannerView registers ``_on_truck_event`` for
        TRUCK_CREATED, TRUCK_UPDATED, and TRUCK_DELETED."""
        view = route_planner_view
        from services.operations.event_bus import (
            TRUCK_CREATED,
            TRUCK_DELETED,
            TRUCK_UPDATED,
        )

        assert view._event_subscribed is True

        event_bus = view._event_bus
        subscribers_created = event_bus._subscribers.get(TRUCK_CREATED, [])
        subscribers_updated = event_bus._subscribers.get(TRUCK_UPDATED, [])
        subscribers_deleted = event_bus._subscribers.get(TRUCK_DELETED, [])

        assert view._on_truck_event in subscribers_created
        assert view._on_truck_event in subscribers_updated
        assert view._on_truck_event in subscribers_deleted

    # ── Test 2: truck event → dropdown refresh ────────────────────────────

    def test_truck_created_refreshes_dropdown(self, route_planner_view):
        """Publishing TRUCK_CREATED on EventBus triggers ``_load_trucks()``."""
        view = route_planner_view
        from services.operations.event_bus import TRUCK_CREATED

        with patch.object(view, "_load_trucks") as mock_load:
            view._event_bus.publish(
                TRUCK_CREATED, {"data": {"truck_id": 1, "plate_number": "AB-123-CD"}}
            )
            mock_load.assert_called_once()

    # ── Test 3: trip created → card on dispatch board ─────────────────────

    def test_trip_created_adds_card_to_dispatch_board(self, dispatch_board_view):
        """Publishing TRIP_CREATED on EventBus adds a card to the Planned column."""
        view = dispatch_board_view
        from services.operations.event_bus import TRIP_CREATED

        # Arrange: TripService returns a trip
        view._trip_service.get_by_id.return_value = {
            "id": 99,
            "status": "Planned",
            "truck_number": "",
            "driver_name": "",
            "start_date": "2026-07-24",
            "end_date": "2026-07-25",
            "origin": "Berlin",
            "destination": "Paris",
        }
        view._build_card_data = MagicMock(return_value=dict(SAMPLE_TRIP_CARD_DATA))

        planned_col = view._columns["Planned"]
        planned_col._cards = []

        # Act — publish passes `data` as ev["data"]; the handler does
        # ev.get("data", {}) so the inner dict must contain trip_id directly.
        view._event_bus.publish(TRIP_CREATED, {"trip_id": 99})

        # Assert
        assert len(planned_col._cards) >= 1
        card = planned_col._cards[0]
        assert card.trip_data["trip_id_num"] == 99
        assert card.trip_data["status"] == "Planned"

    # ── Test 4: trip created → service call → card details ────────────────

    def test_trip_created_via_service_then_board_has_card(
        self, dispatch_board_view
    ):
        """TripService.get_by_id is called with the correct trip_id and the
        resulting card reflects the trip details."""
        view = dispatch_board_view
        from services.operations.event_bus import TRIP_CREATED

        trip_data = {
            "id": 42,
            "status": "Planned",
            "truck_number": "AB123CD",
            "driver_name": "John Driver",
            "start_date": "2026-07-24",
            "end_date": "2026-07-26",
            "origin": "London",
            "destination": "Amsterdam",
        }
        view._trip_service.get_by_id.return_value = trip_data
        view._build_card_data = MagicMock(
            return_value={
                **SAMPLE_TRIP_CARD_DATA,
                "trip_id_num": 42,
                "status": "Planned",
                "truck_plate": "AB123CD",
                "driver_name": "John Driver",
                "origin": "London",
                "destination": "Amsterdam",
                "departure_date": "2026-07-24",
                "eta": "2026-07-26",
            }
        )

        planned_col = view._columns["Planned"]
        planned_col._cards = []

        # Act — publish passes `data` as ev["data"]; the handler does
        # ev.get("data", {}) so the inner dict must contain trip_id directly.
        view._event_bus.publish(TRIP_CREATED, {"trip_id": 42})

        # Assert: service was called with the correct trip id
        view._trip_service.get_by_id.assert_called_once_with(42)

        # Assert: card was added to the Planned column
        assert len(planned_col._cards) == 1
        card = planned_col._cards[0]
        assert card.trip_data["trip_id_num"] == 42
        assert card.trip_data["status"] == "Planned"
        assert card.trip_data["truck_plate"] == "AB123CD"
        assert card.trip_data["driver_name"] == "John Driver"

    # ── Test 5: shutdown prevents event responses ─────────────────────────

    def test_route_planner_shutdown_unsubscribes(self, route_planner_view):
        """After shutdown, publishing TRUCK_CREATED does NOT trigger
        ``_load_trucks``."""
        view = route_planner_view
        from services.operations.event_bus import TRUCK_CREATED

        # Act: shut down the view
        view.shutdown()

        # Verify the subscription flag is cleared
        assert view._event_subscribed is False

        # Verify the callback is no longer in the subscriber list
        subscribers = view._event_bus._subscribers.get(TRUCK_CREATED, [])
        assert view._on_truck_event not in subscribers

        # Finally, publishing the event should not call _load_trucks
        with patch.object(view, "_load_trucks") as mock_load:
            view._event_bus.publish(
                TRUCK_CREATED, {"data": {"truck_id": 1, "plate_number": "XY-999-ZZ"}}
            )
            mock_load.assert_not_called()
