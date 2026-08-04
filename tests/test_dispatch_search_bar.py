"""Tests for the dispatch search bar widget (modern PySide6 API).

The widget was rewritten during the PySide6 migration: ``get_search_text()`` /
``get_selected_status()`` / ``clear()`` became the ``_entry`` / ``_checkboxes``
state plus the public ``set_result_count()`` API. See
``test_dispatch_search_bar_widget.py`` for the comprehensive widget-level suite.
"""
from __future__ import annotations
import pytest

from ui.widgets.dispatch_search_bar import QtDispatchSearchBar, STATUS_OPTIONS


class TestQtDispatchSearchBar:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.dispatch_search_bar import QtDispatchSearchBar
        bar = QtDispatchSearchBar(qt_widget)
        qtbot.addWidget(bar)

    def test_get_search_text(self, qt_widget, qtbot):
        from ui.widgets.dispatch_search_bar import QtDispatchSearchBar
        bar = QtDispatchSearchBar(qt_widget)
        qtbot.addWidget(bar)
        assert isinstance(bar._entry.text(), str)

    def test_get_selected_status(self, qt_widget, qtbot):
        from ui.widgets.dispatch_search_bar import QtDispatchSearchBar
        bar = QtDispatchSearchBar(qt_widget)
        qtbot.addWidget(bar)
        statuses = [s for s, cb in bar._checkboxes.items() if cb.isChecked()]
        assert all(isinstance(s, str) for s in statuses)
        assert set(statuses) == set(STATUS_OPTIONS)  # all checked by default

    def test_clear(self, qt_widget, qtbot):
        from ui.widgets.dispatch_search_bar import QtDispatchSearchBar
        bar = QtDispatchSearchBar(qt_widget)
        qtbot.addWidget(bar)
        bar._entry.setText("query")
        bar._clear()
        assert bar._entry.text() == ""
