"""Tests for the alert panel widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtAlertPanel:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.alert_panel import QtAlertPanel
        panel = QtAlertPanel(qt_widget, alerts=[])
        qtbot.addWidget(panel)
        assert panel is not None

    def test_creation_with_alerts(self, qt_widget, qtbot):
        from unittest.mock import MagicMock
        from ui.widgets.alert_panel import QtAlertPanel
        from services.operations.alert_manager import Severity
        alert1 = MagicMock()
        alert1.severity = Severity.WARNING
        alert1.type.value = "maintenance"
        alert1.title = "Truck Maintenance Due"
        alert1.message = "Truck needs service"
        alert1.created_at = None
        alert1.truck_id = None
        alert1.trip_id = None
        alert2 = MagicMock()
        alert2.severity = Severity.CRITICAL
        alert2.type.value = "overdue_invoice"
        alert2.title = "Driver License Expiring"
        alert2.message = "License expiring soon"
        alert2.created_at = None
        alert2.truck_id = None
        alert2.trip_id = None
        panel = QtAlertPanel(qt_widget, alerts=[alert1, alert2])
        qtbot.addWidget(panel)
        assert panel is not None

    def test_show_anchored(self, qt_widget, qtbot):
        from ui.widgets.alert_panel import QtAlertPanel
        panel = QtAlertPanel(qt_widget, alerts=[])
        qtbot.addWidget(panel)
        panel.show_anchored(qt_widget)
        assert panel.isVisible()

    def test_close(self, qt_widget, qtbot):
        from ui.widgets.alert_panel import QtAlertPanel
        panel = QtAlertPanel(qt_widget, alerts=[])
        qtbot.addWidget(panel)
        panel._close()
        assert not panel.isVisible()
