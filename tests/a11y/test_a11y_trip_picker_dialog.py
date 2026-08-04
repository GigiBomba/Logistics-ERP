"""Accessibility tests for QtTripPickerDialog.

QtTripPickerDialog already has accessibleName set on the dialog ("Select trip"),
search edit ("Search trips"), and trip list ("Trip list"). It uses setTabOrder.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QListWidgetItem

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name,
    assert_accessible_name_not_empty,
    assert_widget_has_focus,
    collect_focusable_children,
)


class TestQtTripPickerDialogA11y:
    """QtTripPickerDialog — modal dialog for picking a trip from a list."""

    def test_dialog_accessible_name(self, qt_widget, qtbot):
        """QtTripPickerDialog should expose accessibleName 'Select trip'."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_name(dialog, "Select trip")

    def test_dialog_accessible_description(self, qt_widget, qtbot):
        """QtTripPickerDialog should expose an accessibleDescription (gap)."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_description_not_empty(dialog)

    def test_search_input_accessible_name(self, qt_widget, qtbot):
        """Search edit should have accessibleName 'Search trips'."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_name(dialog._search_edit, "Search trips")

    def test_trip_list_accessible_name(self, qt_widget, qtbot):
        """Trip list should have accessibleName 'Trip list'."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_name(dialog._list, "Trip list")

    def test_cancel_button_accessible_name(self, qt_widget, qtbot):
        """Cancel button should have an accessibleName (gap)."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog._cancel_btn)

    def test_link_button_accessible_name(self, qt_widget, qtbot):
        """Link button should have an accessibleName (gap)."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog._link_btn)

    def test_tab_order_search_to_list(self, qt_widget, qtbot):
        """Tab order should go from search edit to trip list."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()  # must be visible so children report isVisible()=True
        # Ensure list is visible for focus order check
        dialog._list.setVisible(True)
        focusable = collect_focusable_children(dialog)
        assert len(focusable) >= 3, (
            f"Expected at least 3 focusable children, found {len(focusable)}. "
            f"Check that dialog and children are visible."
        )
        search_idx = focusable.index(dialog._search_edit)
        list_idx = focusable.index(dialog._list)
        assert search_idx < list_idx, (
            f"Expected search_edit (index {search_idx}) before list (index {list_idx})"
        )

    def test_tab_order_list_to_cancel(self, qt_widget, qtbot):
        """Tab order should go from trip list to Cancel button."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()
        dialog._list.setVisible(True)
        focusable = collect_focusable_children(dialog)
        assert len(focusable) >= 3, (
            f"Expected at least 3 focusable children, found {len(focusable)}"
        )
        list_idx = focusable.index(dialog._list)
        cancel_idx = focusable.index(dialog._cancel_btn)
        assert list_idx < cancel_idx, (
            f"Expected list (index {list_idx}) before Cancel (index {cancel_idx})"
        )

    def test_tab_order_cancel_to_link(self, qt_widget, qtbot):
        """Tab order should go from Cancel button to Link button."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()
        dialog._list.setVisible(True)
        focusable = collect_focusable_children(dialog)
        assert len(focusable) >= 3, (
            f"Expected at least 3 focusable children, found {len(focusable)}"
        )
        cancel_idx = focusable.index(dialog._cancel_btn)
        link_idx = focusable.index(dialog._link_btn)
        assert cancel_idx < link_idx, (
            f"Expected Cancel (index {cancel_idx}) before Link (index {link_idx})"
        )

    # ── Keyboard navigation ────────────────────────────────────────────

    def test_tab_order_regression_full_cycle(self, qt_widget, qtbot):
        """Full tab order cycle: search → list → Cancel → Link (regression)."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()
        dialog._list.setVisible(True)
        focusable = collect_focusable_children(dialog)
        assert len(focusable) >= 4, (
            f"Expected at least 4 focusable children, found {len(focusable)}"
        )
        idx = {
            w: i for i, w in enumerate(focusable)
        }
        assert idx[dialog._search_edit] < idx[dialog._list] < idx[dialog._cancel_btn] < idx[dialog._link_btn], (
            "Tab order must be search → list → Cancel → Link"
        )

    def test_enter_on_list_selects(self, qt_widget, qtbot):
        """Enter on a selected list item accepts the dialog."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()

        item = QListWidgetItem("Test Trip #42")
        item.setData(Qt.UserRole, 42)
        dialog._list.addItem(item)
        dialog._list.setCurrentItem(item)
        dialog._list.setFocus()

        QTest.keyClick(dialog._list, Qt.Key_Return)
        assert dialog.result() == QDialog.Accepted, (
            "Enter on list item should accept"
        )

    def test_escape_dismisses(self, qt_widget, qtbot):
        """Escape key dismisses the dialog with Rejected."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        QTest.keyClick(dialog, Qt.Key_Escape)
        assert dialog.result() == QDialog.Rejected, (
            "Dialog should be rejected on Escape"
        )

    def test_search_filter_via_keyboard(self, qt_widget, qtbot):
        """Typing in search triggers _on_search_changed."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)

        with patch.object(dialog, "_on_search_changed") as mock_search:
            qtbot.keyClicks(dialog._search_edit, "Paris")
            mock_search.assert_called()

    def test_arrow_keys_navigate_list(self, qt_widget, qtbot):
        """Arrow keys move selection up and down in the list."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()

        item_a = QListWidgetItem("Trip A")
        item_a.setData(Qt.UserRole, 1)
        item_b = QListWidgetItem("Trip B")
        item_b.setData(Qt.UserRole, 2)
        dialog._list.addItem(item_a)
        dialog._list.addItem(item_b)
        dialog._list.setFocus()

        # Select first item, then move down
        dialog._list.setCurrentItem(item_a)
        QTest.keyClick(dialog._list, Qt.Key_Down)
        assert dialog._list.currentRow() == 1, "Down should move to second item"

        QTest.keyClick(dialog._list, Qt.Key_Up)
        assert dialog._list.currentRow() == 0, "Up should move back to first item"

    def test_double_click_selects(self, qt_widget, qtbot):
        """Double-click on a list item accepts the dialog."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog

        db = MagicMock()
        dialog = QtTripPickerDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        # The list is hidden because _load_trips found no results.
        # Make it visible and hide the empty-state placeholder.
        dialog._list.setVisible(True)
        dialog._trip_picker_empty.setVisible(False)

        item = QListWidgetItem("Trip DoubleClick")
        item.setData(Qt.UserRole, 99)
        dialog._list.addItem(item)
        dialog._list.setCurrentItem(item)

        # Process events so the list lays out the new item
        QTest.qWait(50)

        # Emit itemDoubleClicked directly (this is what a mouse double-click
        # would trigger in a live environment). QTest.mouseDClick is unreliable
        # in headless test runners.
        dialog._list.itemDoubleClicked.emit(item)
        assert dialog.result() == QDialog.Accepted, (
            "Double-click (itemDoubleClicked signal) should accept the dialog"
        )
