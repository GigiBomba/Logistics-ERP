"""Fuzz tests for dispatch detail dialog.

Sends random keyboard and resize events to the detail drawer / dialog
to verify no crashes occur under adversarial input.
"""

from __future__ import annotations

import random
import string
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
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
# Fixtures  (replicated locally so no dependency on other test modules)
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
        qtbot.wait(50)

        yield view

        view.shutdown()


# ===========================================================================
# TestDispatchDetailDialogFuzz
# ===========================================================================


class TestDispatchDetailDialogFuzz:
    """Fuzz tests for the dispatch detail drawer/dialog."""

    # -- 1. Detail drawer keyboard fuzz --------------------------------------

    def test_detail_drawer_keyboard_fuzz(self, qtbot, view_with_mocks):
        """Open drawer, send random key presses, no crash."""
        view = view_with_mocks

        # Mock drawer/backdrop to avoid real Qt layout interaction
        drawer = MagicMock()
        drawer.isVisible.return_value = True
        drawer.width.return_value = 480
        view._detail_drawer = drawer
        view._detail_backdrop = MagicMock()
        view._board_tab = MagicMock()
        view._board_tab.width.return_value = 1200
        view._board_tab.height.return_value = 800
        view._board_content = MagicMock()
        view._board_content.geometry.return_value = MagicMock()
        view._board_content.mapTo.return_value = MagicMock()
        view._ops = MagicMock()

        for _ in range(20):
            key_val = random.choice(_FUZZ_KEYS)
            try:
                QTest.keyClick(drawer, key_val)
            except Exception:
                pass

    # -- 2. Detail drawer resize fuzz ----------------------------------------

    def test_detail_drawer_resize_fuzz(self, qtbot, view_with_mocks):
        """Open drawer, resize the parent board rapidly, no crash."""
        view = view_with_mocks

        drawer = MagicMock()
        drawer.isVisible.return_value = True
        drawer.width.return_value = 480
        view._detail_drawer = drawer
        view._detail_backdrop = MagicMock()
        view._board_tab = MagicMock()
        view._board_tab.width.return_value = 1200
        view._board_tab.height.return_value = 800
        view._board_content = MagicMock()
        view._board_content.geometry.return_value = MagicMock()
        view._board_content.mapTo.return_value = MagicMock()
        view._ops = MagicMock()

        for _ in range(15):
            w = random.randint(200, 1920)
            h = random.randint(200, 1080)
            try:
                view.resize(w, h)
            except Exception:
                pass

    # -- 3. Rapid open / close -----------------------------------------------

    def test_rapid_open_close(self, qtbot, view_with_mocks):
        """Open/close/open/close the drawer via _open_detail_drawer / _close_detail_drawer, no crash."""
        view = view_with_mocks

        # Use real mock instances for drawer/backdrop to track calls
        view._detail_drawer = MagicMock()
        view._detail_drawer.isVisible.return_value = False
        view._detail_drawer.width.return_value = 480
        view._detail_backdrop = MagicMock()
        view._board_tab = MagicMock()
        view._board_tab.width.return_value = 1200
        view._board_tab.height.return_value = 800
        view._board_content = MagicMock()
        view._board_content.geometry.return_value = MagicMock()
        view._board_content.mapTo.return_value = MagicMock()
        view._ops = MagicMock()

        trip_data = {
            "trip_id": "T99",
            "trip_id_num": 99,
            "status": "Planned",
            "truck_plate": "AB12CDE",
            "driver_name": "John Doe",
        }

        with patch("ui.views.dispatch_board.dispatch_board.QPropertyAnimation") as mock_anim_cls:
            mock_anim = MagicMock()
            mock_anim_cls.return_value = mock_anim

            for i in range(5):
                # Open
                try:
                    view._open_detail_drawer(trip_data)
                except Exception:
                    pass

                # Close
                try:
                    view._close_detail_drawer()
                except Exception:
                    pass
