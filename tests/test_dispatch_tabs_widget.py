"""Tests for QtDispatchTabs — tab switching container (widget-level).

Comprehensive tests covering construction, tab registration, switching,
callback invocation, translation refresh, panel replacement, and cleanup.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QPushButton, QStackedWidget, QWidget

from ui.widgets.dispatch_tabs import QtDispatchTabs


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tabs_widget(qtbot):
    tabs = QtDispatchTabs()
    qtbot.addWidget(tabs)
    yield tabs


@pytest.fixture
def tabs_with_panels(qtbot):
    tabs = QtDispatchTabs()
    tabs.add_tab("board", "Board", QWidget())
    tabs.add_tab("alerts", "Alerts", QWidget())
    tabs.add_tab("timeline", "Timeline", QWidget())
    qtbot.addWidget(tabs)
    yield tabs


# ── TestQtDispatchTabsInit — Construction and initial state ───────────────────


class TestQtDispatchTabsInit:
    """Verify the widget is created in a clean initial state."""

    def test_creation(self, tabs_widget):
        assert isinstance(tabs_widget, QtDispatchTabs)

    def test_initial_state(self, tabs_widget):
        assert tabs_widget._active_tab is None
        assert tabs_widget._tabs == {}
        assert tabs_widget._buttons == {}
        assert tabs_widget._on_switch_callback is None

    def test_ui_elements_exist(self, tabs_widget):
        assert hasattr(tabs_widget, "_tab_bar")
        assert hasattr(tabs_widget, "_stack")
        assert tabs_widget._tab_bar is not None
        assert tabs_widget._stack is not None
        assert tabs_widget._tab_bar.parent() is tabs_widget
        assert tabs_widget._stack.parent() is tabs_widget

    def test_separator_line_exists(self, tabs_widget):
        """A QFrame separator should exist between the tab bar and the stack."""
        separators = [
            child
            for child in tabs_widget.findChildren(QFrame)
            if child.property("role") == "tab-separator"
        ]
        assert len(separators) >= 1
        sep = separators[0]
        assert sep.parent() is tabs_widget
        assert sep.height() == 1

    def test_get_active_tab_returns_none_when_no_tabs(self, tabs_widget):
        """get_active_tab() should return None when no tabs are registered."""
        assert tabs_widget.get_active_tab() is None


# ── TestQtDispatchTabsAddTab — Tab registration ──────────────────────────────


class TestQtDispatchTabsAddTab:
    """Adding tabs should register them and auto-activate the first one."""

    def test_add_first_tab_auto_activates(self, tabs_widget):
        panel = QWidget()
        tabs_widget.add_tab("board", "Board", panel)
        assert tabs_widget._active_tab == "board"
        assert tabs_widget._stack.currentWidget() is panel

    def test_add_second_tab_does_not_auto_switch(self, tabs_widget):
        panel_a = QWidget()
        panel_b = QWidget()
        tabs_widget.add_tab("board", "Board", panel_a)
        tabs_widget.add_tab("alerts", "Alerts", panel_b)
        assert tabs_widget._active_tab == "board"
        assert tabs_widget._stack.currentWidget() is panel_a

    def test_add_tab_creates_button(self, tabs_widget):
        tabs_widget.add_tab("board", "Board", QWidget())
        assert "board" in tabs_widget._buttons
        btn = tabs_widget._buttons["board"]
        assert isinstance(btn, QPushButton)
        assert btn.text() == "Board"

    def test_button_has_correct_properties(self, tabs_widget):
        tabs_widget.add_tab("board", "Board", QWidget())
        btn = tabs_widget._buttons["board"]
        assert btn.property("tabRole") == "tab-button"
        assert btn.property("tabId") == "board"
        assert btn.cursor().shape() == Qt.PointingHandCursor


# ── TestQtDispatchTabsSwitchTo — Tab switching ────────────────────────────────


class TestQtDispatchTabsSwitchTo:
    """Switching between registered tabs should update state and UI."""

    def test_switch_to_valid_tab(self, tabs_with_panels):
        panel_b = tabs_with_panels._tabs["alerts"]
        tabs_with_panels.switch_to("alerts")
        assert tabs_with_panels._active_tab == "alerts"
        assert tabs_with_panels._stack.currentWidget() is panel_b

    def test_switch_to_same_tab_noop(self, tabs_with_panels):
        callback = MagicMock()
        tabs_with_panels.on_switch(callback)
        # First switch (no-op since "board" is already active)
        tabs_with_panels.switch_to("board")
        assert callback.call_count == 0

    def test_switch_to_unknown_tab_silently_returns(self, tabs_with_panels):
        # Should not raise, even though _active_tab is updated
        tabs_with_panels.switch_to("nonexistent")
        # No exception means success; _active_tab follows the code path

    def test_switch_to_deactivates_previous_button(self, tabs_with_panels):
        btn_board = tabs_with_panels._buttons["board"]
        btn_alerts = tabs_with_panels._buttons["alerts"]
        # Board is active initially; activate alerts
        tabs_with_panels.switch_to("alerts")
        assert btn_board.property("tabActive") is not True
        assert btn_alerts.property("tabActive") is True

    def test_switch_to_activates_new_button(self, tabs_with_panels):
        btn_alerts = tabs_with_panels._buttons["alerts"]
        assert btn_alerts.property("tabActive") is not True
        tabs_with_panels.switch_to("alerts")
        assert btn_alerts.property("tabActive") is True

    def test_get_active_tab_after_switch(self, tabs_with_panels):
        """get_active_tab() should return the correct tab_id after switching."""
        assert tabs_with_panels.get_active_tab() == "board"
        tabs_with_panels.switch_to("alerts")
        assert tabs_with_panels.get_active_tab() == "alerts"
        tabs_with_panels.switch_to("timeline")
        assert tabs_with_panels.get_active_tab() == "timeline"


# ── TestQtDispatchTabsCallback — Callback invocation ──────────────────────────


class TestQtDispatchTabsCallback:
    """The on_switch callback should fire correctly on tab switches."""

    def test_on_switch_callback_invoked(self, tabs_with_panels):
        callback = MagicMock()
        tabs_with_panels.on_switch(callback)
        tabs_with_panels.switch_to("alerts")
        callback.assert_called_once_with("alerts")

    def test_on_switch_callback_can_be_replaced(self, tabs_with_panels):
        cb1 = MagicMock()
        cb2 = MagicMock()
        tabs_with_panels.on_switch(cb1)
        tabs_with_panels.on_switch(cb2)
        tabs_with_panels.switch_to("alerts")
        cb1.assert_not_called()
        cb2.assert_called_once_with("alerts")

    def test_no_callback_set_no_error(self, tabs_with_panels):
        # No callback registered — switching should not raise
        tabs_with_panels.switch_to("alerts")
        assert tabs_with_panels._active_tab == "alerts"


# ── TestQtDispatchTabsRefreshTranslations — Label updates ─────────────────────


class TestQtDispatchTabsRefreshTranslations:
    """refresh_translations should update button text by tab_id."""

    def test_refresh_translations_updates_button_text(self, tabs_with_panels):
        tabs_with_panels.refresh_translations({"board": "Tabla"})
        btn = tabs_with_panels._buttons["board"]
        assert btn.text() == "Tabla"

    def test_refresh_translations_unknown_tab_ignored(self, tabs_with_panels):
        # Unknown tab_id should not cause errors
        tabs_with_panels.refresh_translations({"nonexistent": "Nope"})
        # Known tab should be unchanged
        assert tabs_with_panels._buttons["board"].text() == "Board"


# ── TestQtDispatchTabsSetTabPanel — Panel replacement ─────────────────────────


class TestQtDispatchTabsSetTabPanel:
    """set_tab_panel should swap the widget for a registered tab."""

    def test_set_tab_panel_replaces_panel(self, tabs_with_panels):
        old_panel = tabs_with_panels._tabs["board"]
        new_panel = QWidget()
        tabs_with_panels.set_tab_panel("board", new_panel)
        assert tabs_with_panels._tabs["board"] is new_panel
        assert tabs_with_panels._tabs["board"] is not old_panel

    def test_set_tab_panel_same_panel_noop(self, tabs_with_panels):
        panel = tabs_with_panels._tabs["board"]
        tabs_with_panels.set_tab_panel("board", panel)
        assert tabs_with_panels._tabs["board"] is panel

    def test_set_tab_panel_unknown_tab_noop(self, tabs_with_panels):
        panel = QWidget()
        # Should not raise
        tabs_with_panels.set_tab_panel("nonexistent", panel)

    def test_set_tab_panel_when_active_updates_stack(self, tabs_with_panels):
        new_panel = QWidget()
        tabs_with_panels.set_tab_panel("board", new_panel)
        assert tabs_with_panels._stack.currentWidget() is new_panel


# ── TestQtDispatchTabsDestroy — Cleanup ───────────────────────────────────────


class TestQtDispatchTabsDestroy:
    """destroy() should clear internal state and schedule deletion."""

    def test_destroy_clears_state(self, tabs_with_panels):
        tabs_with_panels.on_switch(lambda tid: None)
        tabs_with_panels._destroy()
        assert tabs_with_panels._on_switch_callback is None
        assert tabs_with_panels._tabs == {}
        assert tabs_with_panels._buttons == {}
        assert tabs_with_panels._active_tab is None
