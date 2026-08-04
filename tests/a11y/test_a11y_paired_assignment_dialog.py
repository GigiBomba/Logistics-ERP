"""Accessibility tests for QtPairedAssignmentDialog.

Gap: QtPairedAssignmentDialog does not set accessibleName or accessibleDescription.
Child ActionButton widgets also lack accessibleName — tests will FAIL documenting
the gap.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name_not_empty,
)


def _make_item(label: str = "Item", sublabel: str = "Details") -> dict:
    return {
        "id": 1,
        "label": label,
        "sublabel": sublabel,
        "score": 85,
        "available": True,
        "status_text": "",
    }


class TestQtPairedAssignmentDialogA11y:
    """QtPairedAssignmentDialog — side-by-side truck and driver picker."""

    def test_dialog_accessible_name(self, qt_widget, qtbot):
        """QtPairedAssignmentDialog should expose an accessibleName (gap)."""
        from ui.dialogs.paired_assignment_dialog import QtPairedAssignmentDialog

        trip_data = {"trip_id": "T-001", "origin": "Paris", "destination": "Lyon"}
        truck_items = [_make_item("TRK-001", "Mercedes")]
        driver_items = [_make_item("DRV-042", "Jean Dupont")]
        dialog = QtPairedAssignmentDialog(
            parent=qt_widget,
            trip_data=trip_data,
            truck_items=truck_items,
            driver_items=driver_items,
        )
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog)

    def test_dialog_accessible_description(self, qt_widget, qtbot):
        """QtPairedAssignmentDialog should expose an accessibleDescription (gap)."""
        from ui.dialogs.paired_assignment_dialog import QtPairedAssignmentDialog

        trip_data = {"trip_id": "T-001", "origin": "Paris", "destination": "Lyon"}
        dialog = QtPairedAssignmentDialog(
            parent=qt_widget,
            trip_data=trip_data,
            truck_items=[_make_item()],
            driver_items=[_make_item()],
        )
        qtbot.addWidget(dialog)
        assert_accessible_description_not_empty(dialog)

    def test_action_buttons_have_accessible_names(self, qt_widget, qtbot):
        """Assign Both / Truck Only / Driver Only buttons should have names (gap)."""
        from ui.dialogs.paired_assignment_dialog import QtPairedAssignmentDialog
        from ui.widgets import ActionButton

        dialog = QtPairedAssignmentDialog(
            parent=qt_widget,
            trip_data={"trip_id": "T-001"},
            truck_items=[
                _make_item("TRK-001", "Mercedes"),
                _make_item("TRK-002", "Volvo"),
            ],
            driver_items=[
                _make_item("DRV-042", "Jean"),
                _make_item("DRV-099", "Marie"),
            ],
        )
        qtbot.addWidget(dialog)
        action_buttons = dialog.findChildren(ActionButton)
        assert len(action_buttons) >= 3, (
            f"Expected at least 3 ActionButton children, found {len(action_buttons)}"
        )
        for btn in action_buttons:
            assert_accessible_name_not_empty(btn)

    def test_truck_labels_have_accessible_names(self, qt_widget, qtbot):
        """Truck column title labels should have an accessibleName (gap)."""
        from ui.dialogs.paired_assignment_dialog import QtPairedAssignmentDialog
        from PySide6.QtWidgets import QLabel

        dialog = QtPairedAssignmentDialog(
            parent=qt_widget,
            trip_data={"trip_id": "T-001"},
            truck_items=[_make_item("TRK-001")],
            driver_items=[_make_item("DRV-042")],
        )
        qtbot.addWidget(dialog)
        labels = dialog.findChildren(QLabel)
        truck_labels = [lbl for lbl in labels if "truck" in lbl.text().lower()]
        for lbl in truck_labels:
            assert_accessible_name_not_empty(lbl)
