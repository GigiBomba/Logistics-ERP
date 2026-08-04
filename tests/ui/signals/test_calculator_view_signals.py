"""Tests for QtCalculatorView signal (trip_context_updated).

Verifies the signal is connected to the slot and that emission
calls _apply_trip_context.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

# SP workaround
import ui.widgets as _ui_widgets

if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S


def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestCalculatorViewSignals:
    """QtCalculatorView — trip_context_updated signal."""

    # -- 1. Signal connected to slot -------------------------------------

    def test_signal_connected_to_slot(self, qtbot, qt_widget):
        """Create view, verify trip_context_updated connected to
        _on_trip_context_updated."""
        _ensure_qapp()
        from ui.views.calculator_view import QtCalculatorView

        # We need to construct the view without actually loading
        # from the DB.  Mock all dependencies.
        view = QtCalculatorView(
            parent=qt_widget,
            db=MagicMock(),
            fleet_service=MagicMock(),
            trip_service=MagicMock(),
            client_service=MagicMock(),
            prefs=MagicMock(),
            ops=MagicMock(),
            fuel_service=MagicMock(),
            api=MagicMock(),
            api_client=MagicMock(),
        )
        qtbot.addWidget(view)

        # Verify the signal is connected: look at the signal's
        # receiver count.  There should be at least one connection.
        # trip_context_updated.connect(self._apply_trip_context) is in __init__
        sig = view.trip_context_updated
        # Check the signal has receivers (slot is connected)
        assert sig is not None

        # A more reliable check: emit and see if _apply_trip_context is called.
        view._apply_trip_context = MagicMock()
        sig.emit(MagicMock(), ["route"])
        QTest.qWait(50)

        view._apply_trip_context.assert_called_once()

    # -- 2. Emission calls _apply_trip_context ---------------------------

    def test_emission_calls_apply_trip_context(self, qtbot, qt_widget):
        """Emit signal with mock context, verify _apply_trip_context called."""
        _ensure_qapp()
        from ui.views.calculator_view import QtCalculatorView

        view = QtCalculatorView(
            parent=qt_widget,
            db=MagicMock(),
            fleet_service=MagicMock(),
            trip_service=MagicMock(),
            client_service=MagicMock(),
            prefs=MagicMock(),
            ops=MagicMock(),
            fuel_service=MagicMock(),
            api=MagicMock(),
            api_client=MagicMock(),
        )
        qtbot.addWidget(view)

        # Replace _apply_trip_context with a spy
        view._apply_trip_context = MagicMock()

        # Create a mock TripContext
        mock_tc = MagicMock()
        mock_tc.route.distance_km = 150.0
        mock_tc.route.route_history_v2_id = 42
        mock_tc.costs.fuel_liters = 80.0
        mock_tc.costs.toll_cost = 50.0
        mock_tc.truck.id = 5

        # Emit the signal directly
        view.trip_context_updated.emit(mock_tc, ["route"])
        QTest.qWait(50)

        view._apply_trip_context.assert_called_once_with(mock_tc, ["route"])
