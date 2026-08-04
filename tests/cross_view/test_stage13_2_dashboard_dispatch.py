"""Tests for Dashboard → Dispatch Board integration (Stage 13.2).

Verifies that:
- ``MainWindow._switch_module("dispatch_board")`` creates a ``QtDispatchBoardView``
  and caches it with a non-None frame and object reference.
- The dispatch board subscribes to all expected event-bus event types.
- Publishing ``TRIP_CREATED`` on the shared EventBus results in a card being
  added to the correct kanban column.
- Publishing ``TRIP_STATUS_CHANGED`` moves a card between columns.
- Publishing ``ALERT_CREATED`` propagates to the view's alert tracking state.
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QStackedWidget

# ── SP workaround ──────────────────────────────────────────────────────────

# ── Sample data ───────────────────────────────────────────────────────────

SAMPLE_CARD_DATA: dict = {
    "trip_id": "T1",
    "trip_id_num": 1,
    "status": "Planned",
    "truck_plate": "AB12CDE",
    "truck_id": 101,
    "driver_name": "John Doe",
    "driver_id": 201,
    "origin": "Bucharest",
    "destination": "Cluj",
    "departure_date": "2026-07-23",
    "eta": "2026-07-25",
    "alerts_count": 0,
}


SAMPLE_TRIP: dict = {
    "id": 99,
    "status": "Planned",
    "truck_number": "",
    "truck_id": None,
    "driver_name": "",
    "driver_id": None,
    "start_date": "2026-07-24",
    "end_date": "2026-07-25",
    "route_history_v2_id": None,
}


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    """Minimal database mock."""
    return MagicMock()


@pytest.fixture
def mock_ops():
    """Minimal OperationsEngine mock."""
    ops = MagicMock()
    ops.event_bus = MagicMock()
    ops.undo_stack = MagicMock()
    ops.get_active_alerts.return_value = []
    ops.get_alerts.return_value = []
    return ops


@pytest.fixture
def view_with_mocks(qtbot, mock_db, mock_ops):
    """Create a ``QtDispatchBoardView`` with all services mocked at module level.

    Follows the exact pattern from ``tests/test_dispatch_board_view.py``'s
    ``view_with_mocks`` fixture.
    """
    from ui.views.dispatch_board.dispatch_board import QtDispatchBoardView

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

        view = QtDispatchBoardView(db=mock_db, ops=mock_ops)
        view._dispatch = lambda fn: fn()

        # Wait for the background load thread spawned by __init__ → _start_load
        if view._load_thread is not None and view._load_thread.is_alive():
            view._load_thread.join(timeout=2)

        qtbot.addWidget(view)
        qtbot.wait(50)  # Let QTimer.singleShot callbacks settle

        yield view

        view.shutdown()


@pytest.fixture
def main_window_with_dispatch(qtbot, mock_db, mock_ops):
    """Create a ``MainWindow`` that can actually create real ``QtDispatchBoardView``
    instances via ``_switch_module``.

    Uses heavy mocking for everything except the dispatch-board creation path.
    Follows the pattern from ``tests/test_main_window.py``'s ``main_window`` fixture.
    """
    from ui.main_window import MainWindow

    # ── Patch MainWindow internals ─────────────────────────────────────────
    with (
        patch.object(MainWindow, "_init_services", lambda self: None),
        patch.object(MainWindow, "_init_fuel_status", lambda self: None),
        patch("ui.main_window.AppShell"),
        patch("ui.main_window.EventBus"),
        patch("ui.main_window.Config"),
        patch("ui.main_window.QWidgetShortcut"),
    ):
        # Build a minimal _build_ui that provides a real QStackedWidget parent
        def _patched_build_ui(self):
            self.app_shell = MagicMock()
            self.app_shell.view_container = QStackedWidget()
            self.app_shell.top_bar = MagicMock()
            self.app_shell.nav = MagicMock()
            self.app_shell.set_breadcrumb = MagicMock()
            self.app_shell.set_alert_count = MagicMock()

        with patch.object(MainWindow, "_build_ui", _patched_build_ui):
            # ── Also patch the dispatch board's module-level services ─────
            # so that any QtDispatchBoardView created by _create_module uses
            # mocked service classes.
            with (
                patch(
                    "ui.views.dispatch_board.dispatch_board.TripService"
                ) as mock_ts,
                patch("ui.views.dispatch_board.dispatch_board.FleetService"),
                patch("ui.views.dispatch_board.dispatch_board.ClientService"),
                patch(
                    "ui.views.dispatch_board.dispatch_board.DriverTruckService"
                ),
                patch(
                    "ui.views.dispatch_board.dispatch_board.TripConflictService"
                ),
                patch(
                    "ui.views.dispatch_board.dispatch_board.DispatchService"
                ),
                patch(
                    "ui.views.dispatch_board.dispatch_board.AlertManager"
                ),
                patch(
                    "ui.views.dispatch_board.dispatch_board.QtDispatchDetailPanel"
                ),
            ):
                # Configure TripService mock
                ts_instance = MagicMock()
                ts_instance.get_by_statuses.return_value = []
                ts_instance.get_by_id.return_value = None
                ts_instance.get_all.return_value = []
                ts_instance._route_repo = MagicMock()
                mock_ts.return_value = ts_instance

                widget = MainWindow(
                    db=mock_db,
                    api=MagicMock(),
                    prefs=MagicMock(),
                    ops=mock_ops,
                    api_client=MagicMock(),
                )

                # Service attributes that _init_services would normally set
                widget.trip_service = MagicMock()
                widget.client_service = MagicMock()
                widget.fleet_service = MagicMock()
                widget._fuel_service = MagicMock()

                # Prevent page-animation crashes
                with patch.object(
                    MainWindow, "_animate_page_switch", lambda self, frame: None
                ):
                    qtbot.addWidget(widget)
                    yield widget

                    # Clean up any view created during the test
                    for key, cache in list(widget._module_cache.items()):
                        obj = cache.get("obj")
                        if obj is not None and hasattr(obj, "shutdown"):
                            with contextlib.suppress(Exception):
                                obj.shutdown()


# ═════════════════════════════════════════════════════════════════════════════
# TestDashboardToDispatch
# ═════════════════════════════════════════════════════════════════════════════


class TestDashboardToDispatch:
    """Integration from Dashboard (MainWindow) to Dispatch Board."""

    # ── Test 1: _switch_module creates the view ────────────────────────────

    def test_switch_to_dispatch_creates_view(
        self, main_window_with_dispatch, qtbot
    ):
        """Calling ``_switch_module("dispatch_board")`` creates a
        ``QtDispatchBoardView`` and caches it with ``frame`` and ``obj``
        both non-None."""
        mw = main_window_with_dispatch

        mw._switch_module("dispatch_board")

        cache = mw._module_cache.get("dispatch_board")
        assert cache is not None, "dispatch_board should be in _module_cache"
        assert cache.get("frame") is not None, "frame should be non-None"
        assert cache.get("obj") is not None, "obj should be non-None"

        # Clean-up: join background thread and shutdown
        view = cache["obj"]
        if hasattr(view, "_load_thread") and view._load_thread is not None:
            if view._load_thread.is_alive():
                view._load_thread.join(timeout=2)
        view._dispatch = lambda fn: fn()
        qtbot.wait(50)

    # ── Test 2: event subscriptions ────────────────────────────────────────

    def test_subscribe_events_registers_all_handlers(self, view_with_mocks):
        """After view creation, all 11 event types are registered in both
        ``_event_handlers`` and ``_subs``."""
        view = view_with_mocks
        assert len(view._event_handlers) == 11, (
            f"Expected 11 event handlers, got {len(view._event_handlers)}"
        )

        # The BaseView._subscribe method appends to _subs for each handler.
        # 11 event types → 11 entries in _subs.
        assert len(view._subs) == 11, (
            f"Expected 11 _subs entries, got {len(view._subs)}"
        )

    # ── Test 3: TRIP_CREATED → card added to column ───────────────────────

    def test_trip_created_event_adds_card(self, view_with_mocks):
        """Publishing ``TRIP_CREATED`` on the EventBus adds a card to the
        Planned column."""
        view = view_with_mocks
        from services.operations.event_bus import TRIP_CREATED

        # Arrange
        view._trip_service.get_by_id.return_value = dict(SAMPLE_TRIP)
        view._build_card_data = MagicMock(
            return_value={**SAMPLE_CARD_DATA, "trip_id_num": 99, "status": "Planned"}
        )

        planned_col = view._columns["Planned"]
        planned_col._cards = []

        # Act — publish TRIP_CREATED; _dispatch=λ fn:fn() ensures sync execution
        view._event_bus.publish(TRIP_CREATED, {"trip_id": 99})

        # Assert
        assert len(planned_col._cards) >= 1, (
            "Expected at least one card in Planned column"
        )
        card = planned_col._cards[0]
        assert card.trip_data["trip_id_num"] == 99
        assert card.trip_data["status"] == "Planned"

    # ── Test 4: TRIP_STATUS_CHANGED → card moves ──────────────────────────

    def test_trip_status_changed_moves_card(self, view_with_mocks):
        """Publishing ``TRIP_STATUS_CHANGED`` on the EventBus moves a card
        from the Planned column to the Loading column."""
        view = view_with_mocks
        from services.operations.event_bus import TRIP_STATUS_CHANGED
        from ui.widgets.trip_card import QtTripCard

        # Arrange: pre-populate a mock card in Planned column
        card = MagicMock(spec=QtTripCard)
        card.trip_data = dict(SAMPLE_CARD_DATA)
        card.trip_data["status"] = "Planned"
        view._columns["Planned"]._cards = [card]
        view._columns["Planned"].status_key = "Planned"
        view._columns["Loading"]._cards = []
        view._columns["Loading"].status_key = "Loading"

        # Act — publish TRIP_STATUS_CHANGED
        with patch.object(view._columns["Planned"], "remove_card") as mock_rm:
            view._event_bus.publish(
                TRIP_STATUS_CHANGED,
                {"trip_id": 1, "new_status": "Loading"},
            )

        # Assert: card was removed from Planned
        mock_rm.assert_called_once_with(card)

        # Assert: new card was added to Loading
        assert len(view._columns["Loading"]._cards) == 1, (
            "Expected 1 card in Loading column"
        )

    # ── Test 5: ALERT_CREATED → alert tracked ─────────────────────────────

    def test_alert_created_shows_on_alert_panel(self, view_with_mocks):
        """Publishing ``ALERT_CREATED`` on the EventBus increments the alert
        count for the relevant trip in ``_alert_counts``."""
        view = view_with_mocks
        from services.operations.event_bus import ALERT_CREATED

        view._alert_counts = {}

        # Act — publish ALERT_CREATED
        view._event_bus.publish(
            ALERT_CREATED,
            {"alert": {"trip_id": 42, "severity": "warning", "message": "Test alert"}},
        )

        # Assert: alert count was incremented
        assert view._alert_counts.get(42) == 1, (
            "Expected 1 alert for trip 42"
        )
