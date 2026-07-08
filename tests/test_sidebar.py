"""Tests for the sidebar navigation widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QMainWindow

@pytest.fixture
def sidebar(qt_main_window, qtbot):
    sidebar = __import__("ui.widgets.sidebar", fromlist=["Sidebar"]).Sidebar(
        parent=qt_main_window,
        on_select=MagicMock(),
        prefs=None,
    )
    qtbot.addWidget(sidebar)
    yield sidebar
    sidebar.destroy()

class TestSidebar:
    def test_creation(self, sidebar):
        assert sidebar._expanded is False

    def test_initial_collapsed_width(self, sidebar):
        assert sidebar.width() <= 200

    def test_add_group_creates_label(self, sidebar):
        sidebar.add_group("Operations", "nav.group_operations")
        assert "Operations" in sidebar._group_labels

    def test_add_item_creates_frame(self, sidebar):
        sidebar.add_item("calc", "Calculator", i18n_key="nav.calculator")
        assert "calc" in sidebar._items

    def test_add_settings_item_creates_frame(self, sidebar):
        sidebar.add_settings_item("settings", "Settings")
        assert sidebar._settings_item == "settings"

    def test_select_calls_callback(self, sidebar):
        sidebar.add_item("overview", "Overview")
        sidebar.select("overview")
        sidebar._on_select.assert_called_with("overview", None)

    def test_get_active_key_returns_selected(self, sidebar):
        sidebar.add_item("analytics", "Analytics")
        sidebar.select("analytics")
        assert sidebar.get_active_key() == "analytics"

    def test_highlight_skips_same(self, sidebar):
        sidebar.add_item("fleet", "Fleet")
        sidebar.select("fleet")
        sidebar.highlight("fleet")
        assert sidebar.get_active_key() == "fleet"

    def test_collapsed_width(self, sidebar):
        assert sidebar.width() in (48, 200)

    def test_destroy_cleans_up(self, sidebar):
        sidebar.add_item("test", "Test")
        sidebar.destroy()
        assert len(sidebar._items) == 0
