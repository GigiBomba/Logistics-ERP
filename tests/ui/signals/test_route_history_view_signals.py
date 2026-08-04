"""Tests for QtRouteHistoryView signal (preview_loaded).

Verifies the signal exists and is connected to the preview slot.
(Signal existence is already checked in test_cross_thread_signals.py.)
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


class TestRouteHistoryViewSignals:
    """QtRouteHistoryView — preview_loaded signal."""

    # -- 1. preview_loaded connected -------------------------------------

    def test_preview_loaded_connected(self, qtbot, qt_widget):
        """Verify preview_loaded signal exists and is connected to
        _apply_preview."""
        _ensure_qapp()
        from ui.views.route_history_view import QtRouteHistoryView

        # Signal exists as class attribute
        from ui.views.route_history_view import QtRouteHistoryView as RHV
        assert hasattr(RHV, "preview_loaded")

        # Create an instance with mocks
        view = QtRouteHistoryView(
            parent=qt_widget,
            db=MagicMock(),
            controller=MagicMock(),
            api_client=None,
        )
        qtbot.addWidget(view)

        # Replace _apply_preview with a spy
        view._apply_preview = MagicMock()

        # Emit the signal directly
        mock_record = MagicMock()
        mock_record.id = 42
        mock_record.distance_km = 150.0
        mock_record.duration_min = 120.0
        mock_record.origin = "Paris"
        mock_record.destination = "Berlin"

        view.preview_loaded.emit(mock_record, 1)
        QTest.qWait(50)

        # _apply_preview should have been called with the same args
        view._apply_preview.assert_called_once_with(mock_record, 1)
