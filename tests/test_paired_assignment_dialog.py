"""Tests for the paired assignment dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def paired_assignment(qt_widget, qtbot):
    trip_data = {"trip_id": 1, "origin": "Berlin", "destination": "Paris"}
    truck_items = [{"id": 1, "label": "TRUCK-01", "sublabel": "Volvo", "score": 0.9, "available": True, "status_text": "Active"}]
    driver_items = [{"id": 1, "label": "John", "sublabel": "Driver", "score": 0.8, "available": True, "status_text": "Free"}]
    dlg = __import__("ui.dialogs.paired_assignment_dialog", fromlist=["QtPairedAssignmentDialog"]).QtPairedAssignmentDialog(
        parent=qt_widget, trip_data=trip_data,
        truck_items=truck_items, driver_items=driver_items,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()

class TestQtPairedAssignmentDialog:
    def test_creation(self, paired_assignment):
        assert paired_assignment is not None

    def test_truck_list_created(self, paired_assignment):
        assert hasattr(paired_assignment, "_truck_widgets")

    def test_driver_list_created(self, paired_assignment):
        assert hasattr(paired_assignment, "_driver_widgets")

    def test_assign_button_exists(self, paired_assignment):
        assert hasattr(paired_assignment, "_both_btn")

    def test_suggestion_area_exists(self, paired_assignment):
        assert hasattr(paired_assignment, "_paired_hint")

    def test_dialog_is_modal(self, paired_assignment):
        assert paired_assignment.isModal()
