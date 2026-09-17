"""Tests for the sidebar navigation widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QMainWindow

from ui.design_tokens import SIDEBAR_EXPANDED

@pytest.fixture
def sidebar(qt_main_window, qtbot):
    sidebar = __import__("ui.widgets.sidebar", fromlist=["Sidebar"]).Sidebar(
        parent=qt_main_window,
        on_select=MagicMock(),
        prefs=None,
    )
    qtbot.addWidget(sidebar)
    yield sidebar
    sidebar._destroy()

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
        sidebar._destroy()
        assert len(sidebar._items) == 0


class TestSidebarRecent:
    def test_recent_section_hidden_by_default(self, sidebar):
        assert sidebar._recent_section is not None
        assert sidebar._recent_section.isHidden()

    def test_recent_shows_last_three_items(self, sidebar):
        sidebar.set_recent_items([
            ("overview", "Overview"),
            ("analytics", "Analytics"),
            ("fleet", "Fleet"),
            ("clients", "Clients"),
        ])
        assert sidebar._recent_items == [
            ("analytics", "Analytics"),
            ("fleet", "Fleet"),
            ("clients", "Clients"),
        ]
        assert len(sidebar._recent_frames) == 3
        assert not sidebar._recent_section.isHidden()

    def test_recent_hidden_when_empty_after_populated(self, sidebar):
        sidebar.set_recent_items([("overview", "Overview")])
        assert not sidebar._recent_section.isHidden()
        sidebar.set_recent_items([])
        assert sidebar._recent_section.isHidden()
        assert len(sidebar._recent_frames) == 0

    def test_recent_item_click_navigates_without_active_state(self, sidebar):
        sidebar.set_recent_items([("overview", "Overview"), ("analytics", "Analytics")])
        sidebar._on_select.reset_mock()
        frame = sidebar._recent_frames[0]
        event = MagicMock()
        event.type.return_value = QEvent.MouseButtonPress
        sidebar.eventFilter(frame, event)
        sidebar._on_select.assert_called_with("overview", None)
        # Recent items never activate/highlight.
        assert sidebar.get_active_key() is None

    def test_recent_items_use_subdued_style(self, sidebar):
        sidebar.set_recent_items([("overview", "Overview")])
        frame = sidebar._recent_frames[0]
        assert frame.property("is-recent") is True
        # Tertiary text color applied to the recent label
        from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect
        text_lbl = None
        for child in frame.findChildren(QLabel):
            if child.width() != 32 and child.text():
                text_lbl = child
                break
        assert text_lbl is not None
        assert "5A5A6E" in text_lbl.styleSheet()  # COLOR_TEXT_TERTIARY
        # Icon dimmed to 60% opacity
        icon_lbl = next(
            child for child in frame.findChildren(QLabel) if child.width() == 32
        )
        effect = icon_lbl.graphicsEffect()
        assert isinstance(effect, QGraphicsOpacityEffect)
        assert abs(effect.opacity() - 0.6) < 1e-6


class TestSidebarBadge:
    def test_add_item_accepts_badge_key(self, sidebar):
        sidebar.add_item("invoices", "Invoices", badge_key="invoices.pending")
        assert sidebar._badge_keys["invoices"] == "invoices.pending"
        assert "invoices" in sidebar._badges
        assert sidebar._badges["invoices"].isHidden()

    def test_set_badge_shows_count_when_expanded(self, sidebar):
        sidebar._set_width_immediate(SIDEBAR_EXPANDED)
        sidebar.add_item("invoices", "Invoices", badge_key="invoices.pending")
        sidebar.set_badge("invoices", 3)
        badge = sidebar._badges["invoices"]
        assert badge.text() == "3"
        assert not badge.isHidden()

    def test_set_badge_hides_at_zero(self, sidebar):
        sidebar._set_width_immediate(SIDEBAR_EXPANDED)
        sidebar.add_item("invoices", "Invoices", badge_key="invoices.pending")
        sidebar.set_badge("invoices", 3)
        sidebar.set_badge("invoices", 0)
        badge = sidebar._badges["invoices"]
        assert badge.text() == ""
        assert badge.isHidden()

    def test_set_badge_caps_at_99(self, sidebar):
        sidebar._set_width_immediate(SIDEBAR_EXPANDED)
        sidebar.add_item("invoices", "Invoices", badge_key="invoices.pending")
        sidebar.set_badge("invoices", 150)
        badge = sidebar._badges["invoices"]
        assert badge.text() == "+99"
        assert not badge.isHidden()

    def test_set_badge_hidden_when_collapsed(self, sidebar):
        sidebar.add_item("invoices", "Invoices", badge_key="invoices.pending")
        sidebar.set_badge("invoices", 5)
        assert sidebar._badges["invoices"].isHidden()
        # Expanding restores the badge from the stored count.
        sidebar._set_width_immediate(SIDEBAR_EXPANDED)
        assert sidebar._badges["invoices"].text() == "5"
        assert not sidebar._badges["invoices"].isHidden()
