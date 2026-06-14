"""Tests for the PySide6 navigation panel widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QFrame

from ui.qt_widgets.qt_nav_panel import NavPanel, W_COLLAPSED, W_EXPANDED


class TestNavPanel:
    def test_creation_default_width(self, qt_widget, qtbot):
        panel = NavPanel(qt_widget)
        qtbot.addWidget(panel)
        assert panel.width() == W_COLLAPSED

    def test_add_group(self, qt_widget, qtbot):
        panel = NavPanel(qt_widget)
        qtbot.addWidget(panel)
        panel.add_group("Group", "nav.group_overview")
        labels = panel.findChildren(QLabel)
        group_lbls = [l for l in labels if l.property("role") == "nav-group-label"]
        assert len(group_lbls) == 1

    def test_add_item(self, qt_widget, qtbot):
        panel = NavPanel(qt_widget)
        qtbot.addWidget(panel)
        panel.add_item("overview", "\U0001f3e0", "Overview", i18n_key="nav.overview")
        assert "overview" in panel._items

    def test_select_emits_callback(self, qt_widget, qtbot):
        panel = NavPanel(qt_widget)
        qtbot.addWidget(panel)
        selected = []
        panel = NavPanel(qt_widget, on_select=lambda k: selected.append(k))
        qtbot.addWidget(panel)
        panel.add_item("overview", "\U0001f3e0", "Overview", i18n_key="nav.overview")
        panel.select("overview")
        assert selected == ["overview"]

    def test_highlight_changes_state(self, qt_widget, qtbot):
        panel = NavPanel(qt_widget)
        qtbot.addWidget(panel)
        panel.add_item("overview", "\U0001f3e0", "Overview", i18n_key="nav.overview")
        panel.highlight("overview")
        frame = panel._items["overview"]
        assert frame.property("state") == "active"

    def test_expand_toggle(self, qt_widget, qtbot):
        panel = NavPanel(qt_widget)
        qtbot.addWidget(panel)
        panel._toggle_expand()
        qtbot.waitUntil(lambda: panel.width() == W_EXPANDED, timeout=1000)
        assert panel._expanded

    def test_collapse_toggle(self, qt_widget, qtbot):
        panel = NavPanel(qt_widget)
        qtbot.addWidget(panel)
        panel._set_width(W_EXPANDED)
        qtbot.waitUntil(lambda: panel.width() == W_EXPANDED, timeout=1000)
        panel._set_width(W_COLLAPSED)
        qtbot.waitUntil(lambda: panel.width() == W_COLLAPSED, timeout=1000)
        assert not panel._expanded

    def test_i18n_refresh(self, qt_widget, qtbot):
        panel = NavPanel(qt_widget)
        qtbot.addWidget(panel)
        panel.add_item("overview", "\U0001f3e0", "Overview", i18n_key="nav.overview")
        # Simulate a language change by calling the refresh directly.
        panel._refresh_labels()
        assert panel._labels["overview"].text() != ""

    def test_text_labels_hidden_when_collapsed(self, qt_widget, qtbot):
        panel = NavPanel(qt_widget)
        qtbot.addWidget(panel)
        panel.add_item("overview", "\U0001f3e0", "Overview", i18n_key="nav.overview")
        text_lbl = panel._text_label_for_item(panel._items["overview"])
        assert text_lbl is not None
        assert text_lbl.isHidden()
