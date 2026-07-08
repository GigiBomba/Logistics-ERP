"""Tests for the alert panel widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtAlertPanel:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.alert_panel import QtAlertPanel
        panel = QtAlertPanel(qt_widget)
        qtbot.addWidget(panel)

    def test_set_alerts(self, qt_widget, qtbot):
        from ui.widgets.alert_panel import QtAlertPanel
        panel = QtAlertPanel(qt_widget)
        qtbot.addWidget(panel)
        alerts = [
            {"id": 1, "title": "Truck Maintenance Due", "severity": "warning"},
            {"id": 2, "title": "Driver License Expiring", "severity": "critical"},
        ]
        panel.set_alerts(alerts)

    def test_set_count(self, qt_widget, qtbot):
        from ui.widgets.alert_panel import QtAlertPanel
        panel = QtAlertPanel(qt_widget)
        qtbot.addWidget(panel)
        panel.set_count(5)

    def test_clear(self, qt_widget, qtbot):
        from ui.widgets.alert_panel import QtAlertPanel
        panel = QtAlertPanel(qt_widget)
        qtbot.addWidget(panel)
        panel.clear()
