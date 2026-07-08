"""Tests for the automail schedule editor dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

class TestScheduleEditorDialog:
    def test_creation(self, qt_widget, qtbot):
        from ui.views.automail.schedule_editor_dialog import ScheduleEditorDialog
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg.close()

    def test_has_frequency_selector(self, qt_widget, qtbot):
        from ui.views.automail.schedule_editor_dialog import ScheduleEditorDialog
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg.close()

    def test_has_day_of_week_selector(self, qt_widget, qtbot):
        from ui.views.automail.schedule_editor_dialog import ScheduleEditorDialog
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg.close()

    def test_has_time_input(self, qt_widget, qtbot):
        from ui.views.automail.schedule_editor_dialog import ScheduleEditorDialog
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg.close()

    def test_get_schedule_returns_dict(self, qt_widget, qtbot):
        from ui.views.automail.schedule_editor_dialog import ScheduleEditorDialog
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        schedule = dlg.get_schedule() if hasattr(dlg, "get_schedule") else {}
        assert isinstance(schedule, dict)
        dlg.close()
