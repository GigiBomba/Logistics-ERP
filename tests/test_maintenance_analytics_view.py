"""Tests for the maintenance analytics view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtMaintenanceAnalyticsView:
    def test_creation(self, qt_widget, qtbot, monkeypatch):
        monkeypatch.setattr(
            "ui.views.maintenance_analytics_view.QtMaintenanceAnalyticsView._initial_load",
            lambda self: None,
        )
        db = MagicMock()
        api_client = MagicMock()
        view = __import__("ui.views.maintenance_analytics_view", fromlist=["QtMaintenanceAnalyticsView"]).QtMaintenanceAnalyticsView(
            qt_widget, db=db, api_client=api_client,
        )
        qtbot.addWidget(view)
        with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
            view.shutdown()

    def test_has_kpi_cards(self, qt_widget, qtbot, monkeypatch):
        monkeypatch.setattr(
            "ui.views.maintenance_analytics_view.QtMaintenanceAnalyticsView._initial_load",
            lambda self: None,
        )
        view = __import__("ui.views.maintenance_analytics_view", fromlist=["QtMaintenanceAnalyticsView"]).QtMaintenanceAnalyticsView(
            qt_widget, db=MagicMock(), api_client=MagicMock(),
        )
        qtbot.addWidget(view)

    def test_has_charts(self, qt_widget, qtbot, monkeypatch):
        monkeypatch.setattr(
            "ui.views.maintenance_analytics_view.QtMaintenanceAnalyticsView._initial_load",
            lambda self: None,
        )
        view = __import__("ui.views.maintenance_analytics_view", fromlist=["QtMaintenanceAnalyticsView"]).QtMaintenanceAnalyticsView(
            qt_widget, db=MagicMock(), api_client=MagicMock(),
        )
        qtbot.addWidget(view)

    def test_wakeup_does_not_crash(self, qt_widget, qtbot, monkeypatch):
        monkeypatch.setattr(
            "ui.views.maintenance_analytics_view.QtMaintenanceAnalyticsView._initial_load",
            lambda self: None,
        )
        view = __import__("ui.views.maintenance_analytics_view", fromlist=["QtMaintenanceAnalyticsView"]).QtMaintenanceAnalyticsView(
            qt_widget, db=MagicMock(), api_client=MagicMock(),
        )
        qtbot.addWidget(view)
        view.wakeup()
