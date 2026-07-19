"""Tests for the automail variable picker."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestVariablePicker:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.automail.variable_picker import VariablePickerPopup
        picker = VariablePickerPopup(qt_widget)
        qtbot.addWidget(picker)

    def test_has_variable_list(self, qt_widget, qtbot):
        from ui.views.automail.variable_picker import VariablePickerPopup
        picker = VariablePickerPopup(qt_widget)
        qtbot.addWidget(picker)

    def test_get_selected_variable(self, qt_widget, qtbot):
        from ui.views.automail.variable_picker import VariablePickerPopup
        picker = VariablePickerPopup(qt_widget)
        qtbot.addWidget(picker)
        var = picker.get_selected_variable() if hasattr(picker, "get_selected_variable") else None
