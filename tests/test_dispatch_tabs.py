"""Tests for QtDispatchTabs — tab switching container."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from ui.widgets.dispatch_tabs import QtDispatchTabs


class TestQtDispatchTabs:
    def test_initial_state(self, qt_widget, qtbot):
        tabs = QtDispatchTabs(qt_widget)
        qtbot.addWidget(tabs)
        assert tabs.get_active_tab() is None

    def test_add_tab_creates_button(self, qt_widget, qtbot):
        tabs = QtDispatchTabs(qt_widget)
        qtbot.addWidget(tabs)
        panel = QWidget()
        tabs.add_tab("board", "Board", panel)
        # Find the button
        buttons = tabs.findChildren(QPushButton)
        assert len(buttons) == 1
        assert buttons[0].text() == "Board"

    def test_first_tab_auto_activated(self, qt_widget, qtbot):
        tabs = QtDispatchTabs(qt_widget)
        qtbot.addWidget(tabs)
        panel = QWidget()
        tabs.add_tab("main", "Main", panel)
        assert tabs.get_active_tab() == "main"

    def test_switch_to(self, qt_widget, qtbot):
        tabs = QtDispatchTabs(qt_widget)
        qtbot.addWidget(tabs)
        tabs.add_tab("a", "Tab A", QWidget())
        tabs.add_tab("b", "Tab B", QWidget())
        assert tabs.get_active_tab() == "a"
        tabs.switch_to("b")
        assert tabs.get_active_tab() == "b"

    def test_switch_same_tab_noop(self, qt_widget, qtbot):
        tabs = QtDispatchTabs(qt_widget)
        qtbot.addWidget(tabs)
        tabs.add_tab("x", "X", QWidget())
        tabs.switch_to("x")
        assert tabs.get_active_tab() == "x"

    def test_tab_active_property_updates(self, qt_widget, qtbot):
        tabs = QtDispatchTabs(qt_widget)
        qtbot.addWidget(tabs)
        tabs.add_tab("a", "Tab A", QWidget())
        tabs.add_tab("b", "Tab B", QWidget())
        btn_a = [b for b in tabs.findChildren(QPushButton) if b.property("tabId") == "a"][0]
        btn_b = [b for b in tabs.findChildren(QPushButton) if b.property("tabId") == "b"][0]
        assert btn_a.property("tabActive") is True
        assert btn_b.property("tabActive") is not True
        tabs.switch_to("b")
        assert btn_a.property("tabActive") is not True
        assert btn_b.property("tabActive") is True

    def test_on_switch_callback_fires(self, qt_widget, qtbot):
        tabs = QtDispatchTabs(qt_widget)
        qtbot.addWidget(tabs)
        fired = []
        tabs.add_tab("a", "A", QWidget())
        tabs.on_switch(lambda tid: fired.append(tid))
        tabs.add_tab("b", "B", QWidget())
        tabs.switch_to("b")
        # "b" fires because on_switch was registered before add_tab("b")
        # Auto-activation of "a" did NOT fire because callback wasn't set yet
        assert fired == ["b"]

    def test_refresh_translations(self, qt_widget, qtbot):
        tabs = QtDispatchTabs(qt_widget)
        qtbot.addWidget(tabs)
        tabs.add_tab("x", "Old", QWidget())
        tabs.refresh_translations({"x": "New"})
        btn = [b for b in tabs.findChildren(QPushButton) if b.property("tabId") == "x"][0]
        assert btn.text() == "New"

    def test_stacked_widget_switches(self, qt_widget, qtbot):
        tabs = QtDispatchTabs(qt_widget)
        qtbot.addWidget(tabs)
        panel_a = QWidget()
        panel_b = QWidget()
        panel_a.setObjectName("panelA")
        panel_b.setObjectName("panelB")
        tabs.add_tab("a", "A", panel_a)
        tabs.add_tab("b", "B", panel_b)
        tabs.switch_to("a")
        from PySide6.QtWidgets import QStackedWidget
        stack = tabs.findChild(QStackedWidget)
        assert stack.currentWidget() is panel_a
        tabs.switch_to("b")
        assert stack.currentWidget() is panel_b

    def test_get_active_tab_after_switch(self, qt_widget, qtbot):
        tabs = QtDispatchTabs(qt_widget)
        qtbot.addWidget(tabs)
        tabs.add_tab("first", "First", QWidget())
        tabs.add_tab("second", "Second", QWidget())
        assert tabs.get_active_tab() == "first"
        tabs.switch_to("second")
        assert tabs.get_active_tab() == "second"
