"""Tests for the paired assignment dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def paired_assignment(qt_widget, qtbot):
    db = MagicMock()
    trip_id = 1
    dlg = __import__("ui.dialogs.paired_assignment_dialog", fromlist=["QtPairedAssignmentDialog"]).QtPairedAssignmentDialog(
        parent=qt_widget, db=db, trip_id=trip_id,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()

class TestQtPairedAssignmentDialog:
    def test_creation(self, paired_assignment):
        assert paired_assignment._trip_id == 1

    def test_truck_list_created(self, paired_assignment):
        assert hasattr(paired_assignment, "_truck_list")

    def test_driver_list_created(self, paired_assignment):
        assert hasattr(paired_assignment, "_driver_list")

    def test_assign_button_exists(self, paired_assignment):
        assert hasattr(paired_assignment, "_btn_assign")

    def test_suggestion_area_exists(self, paired_assignment):
        assert hasattr(paired_assignment, "_suggestion_label")

    def test_dialog_is_modal(self, paired_assignment):
        assert paired_assignment.isModal()
