"""Tests for the automation view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def automation_view(qt_widget, qtbot):
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

    def test_drop_zone_exists(self, automation_view):
        assert hasattr(automation_view, "_drop_zone")

    def test_detail_panel_exists(self, automation_view):
        assert hasattr(automation_view, "_detail")

    def test_run_list_layout_exists(self, automation_view):
        assert hasattr(automation_view, "_run_list_layout")

    def test_shutdown_cleanup(self, automation_view):
        automation_view.shutdown()

    def test_wakeup_does_not_crash(self, automation_view):
        automation_view.wakeup()

    def test_mode_radios_exist(self, automation_view):
        assert hasattr(automation_view, "_radio_simple")
        assert hasattr(automation_view, "_radio_advanced")

    def test_refresh_does_not_crash(self, automation_view):
        automation_view._refresh_from_db()
