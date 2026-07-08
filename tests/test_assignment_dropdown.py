"""Tests for the assignment dropdown widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestQtAssignmentDropdown:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        dropdown = QtAssignmentDropdown(qt_widget)
        qtbot.addWidget(dropdown)

    def test_set_items(self, qt_widget, qtbot):
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        dropdown = QtAssignmentDropdown(qt_widget)
        qtbot.addWidget(dropdown)
        items = [{"id": 1, "label": "Truck A"}, {"id": 2, "label": "Truck B"}]
        dropdown.set_items(items)

    def test_set_selected(self, qt_widget, qtbot):
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        dropdown = QtAssignmentDropdown(qt_widget)
        qtbot.addWidget(dropdown)
        items = [{"id": 1, "label": "Truck A"}]
        dropdown.set_items(items)
        dropdown.set_selected(1)

    def test_get_selected_id(self, qt_widget, qtbot):
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        dropdown = QtAssignmentDropdown(qt_widget)
        qtbot.addWidget(dropdown)
        assert dropdown.get_selected_id() is None or isinstance(dropdown.get_selected_id(), (int, type(None)))

    def test_clear(self, qt_widget, qtbot):
        from ui.widgets.assignment_dropdown import QtAssignmentDropdown
        dropdown = QtAssignmentDropdown(qt_widget)
        qtbot.addWidget(dropdown)
        items = [{"id": 1, "label": "Truck A"}]
        dropdown.set_items(items)
        dropdown.clear()
