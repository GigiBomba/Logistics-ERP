"""Tests for the PySide6 sidebar navigation panel."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QFrame

from ui.widgets.sidebar import Sidebar
from ui.design_tokens import SIDEBAR_COLLAPSED, SIDEBAR_EXPANDED


class TestSidebar:
    def test_creation_default_width(self, qt_widget, qtbot):
        panel = Sidebar(qt_widget)
        qtbot.addWidget(panel)
        assert panel.width() == SIDEBAR_COLLAPSED

    def test_add_group(self, qt_widget, qtbot):
        panel = Sidebar(qt_widget)
        qtbot.addWidget(panel)
        panel.add_group("Group", "nav.group_overview")
        assert "Group" in panel._groups

    def test_add_item(self, qt_widget, qtbot):
        panel = Sidebar(qt_widget)
        qtbot.addWidget(panel)
        panel.add_item("overview", "Overview", i18n_key="nav.overview")
        assert "overview" in panel._items

    def test_select_emits_callback(self, qt_widget, qtbot):
        selected = []
        panel = Sidebar(qt_widget, on_select=lambda k, _: selected.append(k))
        qtbot.addWidget(panel)
        panel.add_item("overview", "Overview", i18n_key="nav.overview")
        panel.select("overview")
        assert selected == ["overview"]

    def test_highlight_changes_state(self, qt_widget, qtbot):
        panel = Sidebar(qt_widget)
        qtbot.addWidget(panel)
        panel.add_item("overview", "Overview", i18n_key="nav.overview")
        panel.highlight("overview")
        assert panel.get_active_key() == "overview"

    def test_expand_immediate(self, qt_widget, qtbot):
        panel = Sidebar(qt_widget)
        qtbot.addWidget(panel)
        panel._set_width_immediate(SIDEBAR_EXPANDED)
        assert panel.width() == SIDEBAR_EXPANDED
        assert panel._expanded

    def test_collapse_immediate(self, qt_widget, qtbot):
        panel = Sidebar(qt_widget)
        qtbot.addWidget(panel)
        panel._set_width_immediate(SIDEBAR_EXPANDED)
        panel._set_width_immediate(SIDEBAR_COLLAPSED)
        assert panel.width() == SIDEBAR_COLLAPSED
        assert not panel._expanded

    def test_i18n_refresh(self, qt_widget, qtbot):
        panel = Sidebar(qt_widget)
        qtbot.addWidget(panel)
        panel.add_item("overview", "Overview", i18n_key="nav.overview")
        # Simulate a language change by calling the refresh directly.
        panel._refresh_labels()
        assert panel._labels["overview"].text() != ""

    def test_text_labels_hidden_when_collapsed(self, qt_widget, qtbot):
        panel = Sidebar(qt_widget)
        qtbot.addWidget(panel)
        panel.add_item("overview", "Overview", i18n_key="nav.overview")
        text_lbl = panel._text_label_for_item(panel._items["overview"])
        assert text_lbl is not None
        assert text_lbl.isHidden()
