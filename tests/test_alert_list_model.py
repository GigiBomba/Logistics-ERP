"""Tests for the alert list model."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestAlertListModel:
    def test_creation(self, qt_widget, qtbot):
        from ui.models.alert_list_model import AlertListModel
        model = AlertListModel(qt_widget)
        assert model is not None

    def test_set_alerts(self, qt_widget, qtbot):
        from ui.models.alert_list_model import AlertListModel
        model = AlertListModel(qt_widget)
        alerts = [
            {"id": 1, "title": "Alert 1", "severity": "high"},
            {"id": 2, "title": "Alert 2", "severity": "low"},
        ]
        model.set_alerts(alerts)

    def test_clear(self, qt_widget, qtbot):
        from ui.models.alert_list_model import AlertListModel
        model = AlertListModel(qt_widget)
        model.set_alerts([{"id": 1, "title": "A", "severity": "high"}])
        model.clear()

    def test_get_alerts(self, qt_widget, qtbot):
        from ui.models.alert_list_model import AlertListModel
        model = AlertListModel(qt_widget)
        assert isinstance(model.get_alerts(), list)
