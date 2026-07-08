"""Tests for the maintenance control panel."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def maintenance_control(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.maintenance_control_panel.QtMaintenanceControlPanel._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.maintenance_control_panel", fromlist=["QtMaintenanceControlPanel"]).QtMaintenanceControlPanel(
        qt_widget, db=db, prefs=prefs, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()


class TestQtMaintenanceControlPanel:
    def test_creation(self, maintenance_control):
        assert maintenance_control.db is not None

    def test_truck_list_created(self, maintenance_control):
        assert hasattr(maintenance_control, "_truck_list")

    def test_schedule_form_created(self, maintenance_control):
        assert hasattr(maintenance_control, "_schedule_form")

    def test_add_schedule_button_exists(self, maintenance_control):
        assert hasattr(maintenance_control, "_btn_add_schedule")

    def test_shutdown_cleanup(self, maintenance_control):
        maintenance_control.shutdown()

    def test_wakeup_does_not_crash(self, maintenance_control):
        maintenance_control.wakeup()
