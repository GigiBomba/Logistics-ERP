"""Tests for the admin panel view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def admin_panel(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.admin_panel_view.QtAdminPanelView._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    prefs = MagicMock()
    ops = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.admin_panel_view", fromlist=["QtAdminPanelView"]).QtAdminPanelView(
        qt_widget, db=db, prefs=prefs, ops=ops, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtAdminPanelView:
    def test_creation(self, admin_panel):
        assert admin_panel.db is not None

    def test_user_table_created(self, admin_panel):
        assert hasattr(admin_panel, "_user_table")

    def test_add_user_button_exists(self, admin_panel):
        assert hasattr(admin_panel, "_btn_add_user")

    def test_tenant_info_section(self, admin_panel):
        assert hasattr(admin_panel, "_tenant_info")

    def test_shutdown_cleanup(self, admin_panel):
        admin_panel.shutdown()

    def test_wakeup_does_not_crash(self, admin_panel):
        admin_panel.wakeup()
