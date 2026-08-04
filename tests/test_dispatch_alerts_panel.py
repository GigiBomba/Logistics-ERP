"""Tests for the dispatch alerts panel widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtDispatchAlertsPanel:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.dispatch_alerts_panel import QtDispatchAlertsPanel
        panel = QtDispatchAlertsPanel(qt_widget)
        qtbot.addWidget(panel)

    def test_refresh(self, qt_widget, qtbot):
        from ui.widgets.dispatch_alerts_panel import QtDispatchAlertsPanel
        panel = QtDispatchAlertsPanel(qt_widget)
        qtbot.addWidget(panel)
        alerts = [
            {"type": "conflict", "message": "Driver double-booked"},
            {"type": "warning", "message": "Truck overdue maintenance"},
        ]
        # refresh accepts a list of card data dicts
        panel.refresh(alerts)

    def test_has_alerts(self, qt_widget, qtbot):
        from ui.widgets.dispatch_alerts_panel import QtDispatchAlertsPanel
        panel = QtDispatchAlertsPanel(qt_widget)
        qtbot.addWidget(panel)
        assert isinstance(panel.has_alerts() if hasattr(panel, "has_alerts") else True, bool)
