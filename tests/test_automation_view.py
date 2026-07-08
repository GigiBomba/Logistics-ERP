"""Tests for the automation view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def automation_view(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.automation_view.QtAutomationView._load_pipelines",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.automation_view", fromlist=["QtAutomationView"]).QtAutomationView(
        qt_widget, db=db, prefs=prefs, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtAutomationView:
    def test_creation(self, automation_view):
        assert automation_view.db is not None

    def test_pipeline_list_created(self, automation_view):
        assert hasattr(automation_view, "_pipeline_list")

    def test_control_buttons_exist(self, automation_view):
        assert hasattr(automation_view, "_btn_run")

    def test_queue_widget_exists(self, automation_view):
        assert hasattr(automation_view, "_queue_widget")

    def test_shutdown_cleanup(self, automation_view):
        automation_view.shutdown()

    def test_wakeup_does_not_crash(self, automation_view):
        automation_view.wakeup()

    def test_stop_button_exists(self, automation_view):
        assert hasattr(automation_view, "_btn_stop")

    def test_refresh_button_exists(self, automation_view):
        assert hasattr(automation_view, "_btn_refresh")
