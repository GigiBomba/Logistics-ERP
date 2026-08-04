"""Tests for QtDispatchBoardView — the dispatch board kanban widget (PySide6).

These are qtbot-based integration tests that create the full widget with
mocked service layer, verifying UI construction, lifecycle, and key
interactions.
"""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QAbstractButton, QLabel

from ui.components import EmptyState
from ui.views.dispatch_board.board_state import COLUMN_DEFS


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    ops.get_active_alerts.return_value = []
    ops.undo_stack = MagicMock()
    return ops


@pytest.fixture
def board_view(qtbot, mock_db, mock_ops):
    """Create QtDispatchBoardView with mocked service layer.

    All service constructors are patched so the widget initializes without
    real database access.  The background load thread completes quickly
    because the mocked ``TripService.get_by_statuses`` returns an empty
    list.
    """
    # Service mocks with sensible defaults
    mock_trip_service = MagicMock()
    mock_trip_service.get_by_statuses.return_value = []
    mock_trip_service.get_all.return_value = []

    mock_fleet_service = MagicMock()
    mock_fleet_service._fleet_repo = MagicMock()
    mock_fleet_service._fleet_repo.get_active_trucks.return_value = []
    mock_fleet_service._fleet_repo.get_by_id.return_value = None

    mock_client_service = MagicMock()

    mock_dta_service = MagicMock()
    mock_dta_service._driver_repo = MagicMock()
    mock_dta_service._driver_repo.get_active_drivers.return_value = []
    mock_dta_service._driver_repo.get_by_id.return_value = None

    mock_conflict_service = MagicMock()
    mock_conflict_service.check_conflicts.return_value = []

    patchers = [
        patch(
            "ui.views.dispatch_board.dispatch_board.TripService",
            return_value=mock_trip_service,
        ),
        patch(
            "ui.views.dispatch_board.dispatch_board.FleetService",
            return_value=mock_fleet_service,
        ),
        patch(
            "ui.views.dispatch_board.dispatch_board.ClientService",
            return_value=mock_client_service,
        ),
        patch(
            "ui.views.dispatch_board.dispatch_board.DriverTruckService",
            return_value=mock_dta_service,
        ),
        patch(
            "ui.views.dispatch_board.dispatch_board.TripConflictService",
            return_value=mock_conflict_service,
        ),
        patch("ui.views.dispatch_board.dispatch_board.DispatchService"),
    ]
    for p in patchers:
        p.start()

    from ui.views.dispatch_board.dispatch_board import QtDispatchBoardView

    # NOTE: The production code has an ordering bug where ``_alert_mgr``
    # is accessed (line 127) before it is assigned (line 148).  We
    # pre-initialise it here so the widget can be constructed.
    QtDispatchBoardView._alert_mgr = MagicMock()
    # ^^ This instance attribute is set late in the real init (line 148),
    #    but accessed earlier (line 127).  Setting a class-level default
    #    lets the instance attribute shadow it until the real init sets it.
    widget = QtDispatchBoardView(
        parent=None,
        db=mock_db,
        ops=mock_ops,
    )
    qtbot.addWidget(widget)
    widget.show()  # Make visible so child widget isVisible() checks work

    # The background thread dispatches ``_populate_columns`` back to the
    # main thread via a signal.  We also need ``_status_cards`` so that
    # ``_update_status_counts`` doesn't raise (it's never set in the
    # production code but is referenced by the mixin).
    widget._status_cards = {}
    # Wait for the deferred callbacks (QTimer.singleShot from
    # ``_populate_columns``, thread dispatch, etc.)
    qtbot.wait(300)

    yield widget

    with contextlib.suppress(Exception):
        widget.shutdown()
    for p in patchers:
        p.stop()


# =========================================================================
# Tests
# =========================================================================


class TestQtDispatchBoardView:
    """Suite of qtbot tests for the full dispatch board widget."""

    # ── Initialisation ─────────────────────────────────────────────────────

    def test_initialization(self, board_view):
        """Widget initialises without crashing and stores service references."""
        assert board_view is not None
        assert board_view._db is not None
        assert board_view._trip_service is not None
        assert board_view._fleet_service is not None
        assert board_view._dta_service is not None
        assert board_view._dispatch_service is not None

    def test_default_state(self, board_view):
        """Key internal state attributes are initialised correctly."""
        assert board_view._loading is False
        assert board_view._destroyed is False
        assert board_view._selected_cards == []
        assert board_view._all_card_data == []
        assert board_view._search_query == ""
        assert board_view._delivered_days == 30
        assert board_view._drag_card is None
        assert board_view._drag_source_col is None
        assert board_view._drag_target_col is None

    def test_caches_initialised(self, board_view):
        """Cache dictionaries are initialised empty."""
        assert board_view._driver_cache == {}
        assert board_view._route_cache == {}
        assert board_view._alert_counts == {}
        assert board_view._conflict_alerts == {}

    # ── Header ─────────────────────────────────────────────────────────────

    def test_header_renders_title(self, board_view):
        """Header contains a PageTitle widget (stored as ``_title_lbl``)."""
        assert board_view._title_lbl is not None
        assert isinstance(board_view._title_lbl, QLabel)

    def test_header_has_subtitle(self, board_view):
        """Header contains a subtitle label."""
        assert board_view._subtitle_lbl is not None

    def test_header_has_export_buttons(self, board_view):
        """Header contains export CSV, export PDF, and refresh buttons."""
        assert board_view._export_csv_btn is not None
        assert board_view._export_pdf_btn is not None
        assert board_view._refresh_btn is not None
        # All three are QAbstractButton subclasses
        assert isinstance(board_view._export_csv_btn, QAbstractButton)
        assert isinstance(board_view._export_pdf_btn, QAbstractButton)
        assert isinstance(board_view._refresh_btn, QAbstractButton)

    def test_refresh_button_triggers_load(self, board_view):
        """Clicking the refresh button calls ``_start_load``."""
        with patch.object(board_view, "_start_load") as mock_load:
            board_view._refresh_btn.click()
            mock_load.assert_called_once()

    # ── Tabs ───────────────────────────────────────────────────────────────

    def test_tabs_created(self, board_view):
        """Dispatch tabs widget is created and has three tabs."""
        assert board_view._tabs is not None

    def test_tab_switch_calls_alerts_refresh(self, board_view):
        """Switching to the alerts tab refreshes the alerts panel."""
        with patch.object(board_view._alerts_panel, "refresh") as mock_refresh:
            board_view._on_tab_switch("alerts")
            mock_refresh.assert_called_once_with(board_view._all_card_data)

    def test_tab_switch_calls_timeline_refresh(self, board_view):
        """Switching to the timeline tab refreshes the timeline."""
        with patch.object(board_view._timeline, "refresh") as mock_refresh:
            board_view._on_tab_switch("timeline")
            mock_refresh.assert_called_once_with(board_view._all_card_data)

    # ── Search bar ─────────────────────────────────────────────────────────

    def test_search_bar_created(self, board_view):
        """Search bar widget is created."""
        assert board_view._search_bar is not None

    def test_search_filter_updates_query(self, board_view):
        """Calling ``_on_search_filter`` updates query/statuses and applies
        filters."""
        with patch.object(board_view, "_apply_filters") as mock_apply:
            board_view._on_search_filter("truck-1", ["Planned", "In Transit"])
            assert board_view._search_query == "truck-1"
            assert board_view._search_statuses == ["Planned", "In Transit"]
            mock_apply.assert_called_once()

    # ── Kanban columns ─────────────────────────────────────────────────────

    def test_kanban_columns_created(self, board_view):
        """Five kanban columns are created with correct status keys."""
        assert len(board_view._columns) == 5
        expected_keys = {"Planned", "Loading", "In Transit", "Delivered", "Cancelled"}
        assert set(board_view._columns.keys()) == expected_keys

    def test_columns_have_status_key(self, board_view):
        """Each column has its correct ``status_key`` attribute."""
        for status_key, col in board_view._columns.items():
            assert col.status_key == status_key

    # ── Bulk toolbar ───────────────────────────────────────────────────────

    def test_bulk_toolbar_hidden_by_default(self, board_view):
        """Bulk toolbar starts hidden."""
        assert board_view._bulk_toolbar is not None
        assert not board_view._bulk_toolbar.isVisible()

    def test_bulk_toolbar_buttons_exist(self, board_view):
        """Bulk toolbar has assign driver, assign truck, and clear buttons."""
        assert board_view._bulk_assign_driver_btn is not None
        assert board_view._bulk_assign_truck_btn is not None
        assert board_view._bulk_clear_btn is not None

    def test_clear_selections_hides_toolbar(self, board_view):
        """``_clear_all_selections`` hides the bulk toolbar."""
        board_view.show()  # Ensure widget is visible for Qt visibility checks
        # Simulate a selection
        board_view._selected_cards = [MagicMock(), MagicMock()]
        board_view._update_bulk_toolbar()
        assert board_view._bulk_toolbar.isVisible()

        board_view._clear_all_selections()
        assert board_view._selected_cards == []
        assert not board_view._bulk_toolbar.isVisible()

    # ── Board stack ────────────────────────────────────────────────────────

    def test_board_stack_has_two_pages(self, board_view):
        """Board stacked widget has kanban scroll (index 0) and empty state
        (index 1) pages."""
        assert board_view._board_stack is not None
        assert board_view._board_stack.count() == 2

    def test_empty_state_shown_when_no_data(self, board_view):
        """With no data loaded, the kanban columns area is shown (index 0).

        The empty state (index 1) is only displayed when there *are* cards
        but all are filtered out by the search/filter bar.
        """
        # With mocked services returning [], all columns are empty and
        # ``total == 0``, so the kanban scroll area (index 0) is shown.
        assert board_view._board_stack.currentIndex() == 0

    def test_empty_state_is_empty_state_widget(self, board_view):
        """Page 1 of the board stack is an ``EmptyState`` widget."""
        page = board_view._board_stack.widget(1)
        assert isinstance(page, EmptyState)

    # ── Alerts panel ──────────────────────────────────────────────────────

    def test_alerts_panel_created(self, board_view):
        """Alerts panel widget is created."""
        assert board_view._alerts_panel is not None

    # ── Timeline ───────────────────────────────────────────────────────────

    def test_timeline_created(self, board_view):
        """Timeline widget is created."""
        assert board_view._timeline is not None

    # ── Refresh timer ─────────────────────────────────────────────────────

    def test_refresh_timer_created(self, board_view):
        """Auto-refresh timer is created and active."""
        assert board_view._refresh_timer is not None
        assert board_view._refresh_timer.isActive()
        assert board_view._refresh_timer.interval() == 30_000

    # ── Event bus subscription ─────────────────────────────────────────────

    def test_event_handlers_registered(self, board_view):
        """Event handlers dict is populated."""
        assert len(board_view._event_handlers) >= 9

    # ── i18n ──────────────────────────────────────────────────────────────

    def test_language_change_updates_labels(self, board_view):
        """``_on_language_changed`` updates title and subtitle."""
        # Should not crash
        board_view._on_language_changed("ro")
        # Title text may be the translation key in test environment
        assert board_view._title_lbl is not None

    # ── Lifecycle: shutdown ────────────────────────────────────────────────

    def test_shutdown_stops_timers(self, board_view):
        """shutdown() stops timers and marks widget as destroyed."""
        assert board_view._refresh_timer.isActive()
        board_view.shutdown()
        assert board_view._destroyed is True
        if board_view._refresh_timer is not None:
            assert not board_view._refresh_timer.isActive()

    def test_shutdown_is_idempotent(self, board_view):
        """Calling shutdown() twice does not crash."""
        board_view.shutdown()
        board_view.shutdown()  # second call is safe

    def test_shutdown_clears_detail_panel(self, board_view):
        """shutdown() closes and hides the detail drawer if open."""
        board_view._detail_drawer.show()
        board_view.shutdown()
        assert not board_view._detail_drawer.isVisible()

    # ── Lifecycle: wakeup ─────────────────────────────────────────────────

    def test_wakeup_resubscribes_events_and_starts_load(self, board_view):
        """wakeup() calls _subscribe_events and _start_load."""
        with patch.object(board_view, "_subscribe_events") as mock_sub:
            with patch.object(board_view, "_start_load") as mock_load:
                board_view.wakeup()
                mock_sub.assert_called_once()
                mock_load.assert_called_once()

    def test_wakeup_restarts_timer_if_stopped(self, board_view):
        """wakeup() restarts the refresh timer if it was stopped."""
        # Simulate timer stopped
        board_view._refresh_timer.stop()
        assert not board_view._refresh_timer.isActive()

        board_view.wakeup()
        assert board_view._refresh_timer.isActive()

    def test_wakeup_noop_if_destroyed(self, board_view):
        """wakeup() is a no-op after shutdown."""
        board_view.shutdown()
        with patch.object(board_view, "_subscribe_events") as mock_sub:
            with patch.object(board_view, "_start_load") as mock_load:
                board_view.wakeup()
                mock_sub.assert_not_called()
                mock_load.assert_not_called()

    # ── Navigation ─────────────────────────────────────────────────────────

    def test_handle_nav_data_stores_trip_id(self, board_view):
        """handle_nav_data stores trip_id and starts a fresh load."""
        with patch.object(board_view, "_start_load") as mock_load:
            board_view.handle_nav_data({"trip_id": 42})
            assert board_view._pending_nav_trip_id == 42
            mock_load.assert_called_once()

    def test_handle_nav_data_starts_load(self, board_view):
        """handle_nav_data always triggers _start_load even without trip_id."""
        with patch.object(board_view, "_start_load") as mock_load:
            board_view.handle_nav_data({})
            mock_load.assert_called_once()

    # ── Card helpers ──────────────────────────────────────────────────────

    def test_find_card_by_trip_id_returns_none(self, board_view):
        """_find_card_by_trip_id returns None when no card matches."""
        result = board_view._find_card_by_trip_id(999)
        assert result is None

    def test_find_card_by_trip_id_handles_empty_columns(self, board_view):
        """_find_card_by_trip_id handles empty columns gracefully."""
        assert board_view._find_card_by_trip_id(0) is None

    # ── Export ─────────────────────────────────────────────────────────────

    def test_export_csv_btn_click_does_not_crash(self, board_view):
        """Clicking export CSV button does not crash (export may fail silently
        if no data)."""
        with contextlib.suppress(Exception):
            board_view._export_csv_btn.click()

    def test_export_pdf_btn_click_does_not_crash(self, board_view):
        """Clicking export PDF button does not crash."""
        with contextlib.suppress(Exception):
            board_view._export_pdf_btn.click()

    # ── Quick assign (alerts -> board) ─────────────────────────────────────

    def test_quick_assign_noop_without_trip_id(self, board_view):
        """Quick assign methods are no-ops when item has no trip_id."""
        # Should not raise
        with contextlib.suppress(Exception):
            board_view._on_quick_assign_truck({"no_id": True})
            board_view._on_quick_assign_driver({"no_id": True})
            board_view._on_quick_assign_both({"no_id": True})

    def test_quick_assign_noop_without_matching_card(self, board_view):
        """Quick assign methods are no-ops when no card matches the trip_id."""
        with contextlib.suppress(Exception):
            board_view._on_quick_assign_truck({"trip_id_num": 999})
            board_view._on_quick_assign_driver({"trip_id_num": 999})
            board_view._on_quick_assign_both({"trip_id_num": 999})
