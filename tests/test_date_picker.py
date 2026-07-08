"""Tests for the custom date picker widget (already partially covered)."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from PySide6.QtCore import QDate

class TestQtDatePickerExtended:
    def test_set_date_from_python_date(self, qt_widget, qtbot):
        from ui.widgets.date_picker import QtDatePicker
        import datetime
        picker = QtDatePicker(qt_widget, date_pattern="yyyy-MM-dd")
        qtbot.addWidget(picker)
        picker.set_date(datetime.date(2026, 7, 9))
        assert "2026-07-09" in picker.text()

    def test_get_date_py_returns_date(self, qt_widget, qtbot):
        from ui.widgets.date_picker import QtDatePicker
        picker = QtDatePicker(qt_widget, initial_date=QDate(2026, 1, 15), date_pattern="yyyy-MM-dd")
        qtbot.addWidget(picker)
        result = picker.date_py()
        assert result is not None

    def test_placeholder_text(self, qt_widget, qtbot):
        from ui.widgets.date_picker import QtDatePicker
        picker = QtDatePicker(qt_widget, placeholder="Select date")
        qtbot.addWidget(picker)
        assert picker.placeholderText() == "Select date"

    def test_custom_date_pattern(self, qt_widget, qtbot):
        from ui.widgets.date_picker import QtDatePicker
        picker = QtDatePicker(qt_widget, date_pattern="dd/MM/yyyy")
        qtbot.addWidget(picker)
        picker.set_date(QDate(2026, 6, 15))
        assert "15/06/2026" in picker.text()

class TestMakeDateEntry:
    def test_factory_creates_picker(self, qt_widget, qtbot):
        from ui.widgets.date_picker import make_date_entry
        picker = make_date_entry(qt_widget)
        qtbot.addWidget(picker)
