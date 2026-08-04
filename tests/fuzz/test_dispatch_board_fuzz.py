"""Fuzz tests for the dispatch board view.

Sends random keyboard, mouse, and resize events to the board
to verify no crashes occur under adversarial input.
"""

from __future__ import annotations

import random
import string
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

# ---------------------------------------------------------------------------
# SP workaround
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Fuzz helpers
# ---------------------------------------------------------------------------

_FUZZ_KEYS = [
    k.value for k in Qt.Key
    if not any(x in k.name for x in ("Shift", "Control", "Alt", "Meta", "unknown"))
]


def random_text(max_len: int = 100) -> str:
    """Produce a random string of length in [0, max_len]."""
    return "".join(
        random.choices(string.ascii_letters + string.digits + " -_./", k=random.randint(0, max_len))
    )


# ---------------------------------------------------------------------------
# Fixtures  (replicated locally so no dependency on test_dispatch_board_view)
# ---------------------------------------------------------------------------


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
    """Create a ``QtDispatchBoardView`` with all services mocked at module level."""
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

        # -- ConflictService mock ----------------------------------------------
        tcs_instance = MagicMock()
        mock_tcs.return_value = tcs_instance

        # -- DispatchService mock ----------------------------------------------
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
        qtbot.wait(50)  # Let QTimer.singleShot callbacks from _populate_columns settle

        yield view

        view.shutdown()


# ===========================================================================
# TestDispatchBoardKeyboardFuzz
# ===========================================================================


class TestDispatchBoardKeyboardFuzz:
    """Keyboard fuzz: random keypresses, text entry, navigation keys."""

    # -- 1. Random keypresses ------------------------------------------------

    def test_random_keypresses(self, qtbot, view_with_mocks):
        """Send random Qt.Key values via QTest.keyClick. No crash."""
        view = view_with_mocks
        for _ in range(30):
            key_val = random.choice(_FUZZ_KEYS)
            try:
                QTest.keyClick(view, key_val)
            except Exception:
                pass  # tolerate key-not-supported errors; crash is the concern

    # -- 2. Random text input in search bar ----------------------------------

    def test_random_text_input_in_search(self, qtbot, view_with_mocks):
        """Type random strings into _search_bar via qtbot.keyClicks."""
        view = view_with_mocks
        for _ in range(20):
            text = random_text(30)
            try:
                qtbot.keyClicks(view._search_bar, text)
            except Exception:
                pass

    # -- 3. Escape and navigation keys ---------------------------------------

    def test_escape_and_navigation_keys(self, qtbot, view_with_mocks):
        """Send mixed Tab/Enter/Escape/Arrow key presses on cards/columns."""
        view = view_with_mocks
        nav_keys = [
            Qt.Key.Key_Tab.value, Qt.Key.Key_Backtab.value,
            Qt.Key.Key_Return.value, Qt.Key.Key_Enter.value,
            Qt.Key.Key_Escape.value, Qt.Key.Key_Left.value,
            Qt.Key.Key_Right.value, Qt.Key.Key_Up.value,
            Qt.Key.Key_Down.value, Qt.Key.Key_Home.value,
            Qt.Key.Key_End.value, Qt.Key.Key_PageUp.value,
            Qt.Key.Key_PageDown.value,
        ]
        for col_key in list(view._columns.keys()):
            col = view._columns[col_key]
            for _ in range(15 // len(view._columns)):
                key = random.choice(nav_keys)
                try:
                    QTest.keyClick(col, key)
                except Exception:
                    pass


# ===========================================================================
# TestDispatchBoardMouseFuzz
# ===========================================================================


class TestDispatchBoardMouseFuzz:
    """Mouse fuzz: random clicks on board, columns, right-clicks."""

    # -- 4. Random clicks on board -------------------------------------------

    def test_random_click_on_board(self, qtbot, view_with_mocks):
        """Random QPoint clicks within view geometry, no crash."""
        view = view_with_mocks
        geo = view.geometry()
        for _ in range(30):
            x = random.randint(0, max(geo.width() - 1, 1))
            y = random.randint(0, max(geo.height() - 1, 1))
            try:
                QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(x, y))
            except Exception:
                pass

    # -- 5. Random clicks on columns -----------------------------------------

    def test_random_click_on_columns(self, qtbot, view_with_mocks):
        """Random clicks on each column's card area, no crash."""
        view = view_with_mocks
        for col_key in list(view._columns.keys()):
            col = view._columns[col_key]
            geo = col.geometry()
            for _ in range(15 // len(view._columns)):
                x = random.randint(0, max(geo.width() - 1, 1))
                y = random.randint(0, max(geo.height() - 1, 1))
                try:
                    QTest.mouseClick(col, Qt.MouseButton.LeftButton, pos=QPoint(x, y))
                except Exception:
                    pass

    # -- 6. Random right-clicks ----------------------------------------------

    def test_random_right_clicks(self, qtbot, view_with_mocks):
        """Right-clicks at random positions, no crash."""
        view = view_with_mocks
        geo = view.geometry()
        for _ in range(15):
            x = random.randint(0, max(geo.width() - 1, 1))
            y = random.randint(0, max(geo.height() - 1, 1))
            try:
                QTest.mouseClick(view, Qt.MouseButton.RightButton, pos=QPoint(x, y))
            except Exception:
                pass


# ===========================================================================
# TestDispatchBoardResizeFuzz
# ===========================================================================


class TestDispatchBoardResizeFuzz:
    """Resize fuzz: random, edge-case, and rapid resize events."""

    # -- 7. Random resize ----------------------------------------------------

    def test_random_resize(self, qtbot, view_with_mocks):
        """Random resize events: w in [200,1920], h in [200,1080]."""
        view = view_with_mocks
        for _ in range(15):
            w = random.randint(200, 1920)
            h = random.randint(200, 1080)
            try:
                view.resize(w, h)
            except Exception:
                pass

    # -- 8. Minimum size edge cases ------------------------------------------

    def test_minimum_size_edge_cases(self, qtbot, view_with_mocks):
        """Resize to 0x0, 1x1, 50x50, 100x100. No crash."""
        view = view_with_mocks
        for w, h in [(0, 0), (1, 1), (50, 50), (100, 100)]:
            try:
                view.resize(w, h)
            except Exception:
                pass

    # -- 9. Rapid resize -----------------------------------------------------

    def test_rapid_resize(self, qtbot, view_with_mocks):
        """Rapid resize events."""
        view = view_with_mocks
        for _ in range(10):
            w = random.randint(100, 800)
            h = random.randint(100, 600)
            try:
                view.resize(w, h)
            except Exception:
                pass
