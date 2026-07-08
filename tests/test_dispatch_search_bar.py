"""Tests for the dispatch search bar widget."""
from __future__ import annotations
import pytest

class TestQtDispatchSearchBar:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.dispatch_search_bar import QtDispatchSearchBar
        bar = QtDispatchSearchBar(qt_widget)
        qtbot.addWidget(bar)

    def test_get_search_text(self, qt_widget, qtbot):
        from ui.widgets.dispatch_search_bar import QtDispatchSearchBar
        bar = QtDispatchSearchBar(qt_widget)
        qtbot.addWidget(bar)
        assert isinstance(bar.get_search_text(), str)

    def test_get_selected_status(self, qt_widget, qtbot):
        from ui.widgets.dispatch_search_bar import QtDispatchSearchBar
        bar = QtDispatchSearchBar(qt_widget)
        qtbot.addWidget(bar)
        status = bar.get_selected_status()
        assert isinstance(status, str) or status is None

    def test_clear(self, qt_widget, qtbot):
        from ui.widgets.dispatch_search_bar import QtDispatchSearchBar
        bar = QtDispatchSearchBar(qt_widget)
        qtbot.addWidget(bar)
        bar.clear()
        assert bar.get_search_text() == ""
