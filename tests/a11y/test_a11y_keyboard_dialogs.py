"""Keyboard navigation tests for share_route, confirmation_modal, and paired_assignment dialogs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard, QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QPushButton, QScrollArea

from tests.a11y.conftest import collect_focusable_children


# ======================================================================
# ShareRouteDialog
# ======================================================================


class TestShareRouteDialogKeyboard:
    """ShareRouteDialog — keyboard interaction tests."""

    def test_escape_dismisses(self, qt_widget, qtbot):
        """Escape key dismisses the dialog."""
        from ui.dialogs.share_route_dialog import ShareRouteDialog

        dialog = ShareRouteDialog(
            parent=qt_widget,
            share_url="https://operion.app/route?stops=test",
        )
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        QTest.keyClick(dialog, Qt.Key_Escape)
        assert dialog.result() == QDialog.Rejected, (
            "Dialog should be rejected on Escape"
        )

    def test_copy_button_via_enter(self, qt_widget, qtbot):
        """Enter on Copy button copies share_url to clipboard."""
        from ui.dialogs.share_route_dialog import ShareRouteDialog

        url = "https://operion.app/route?stops=test"
        dialog = ShareRouteDialog(parent=qt_widget, share_url=url)
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        buttons = dialog.findChildren(QPushButton)
        copy_btn = next((b for b in buttons if "Copy" in b.text()), None)
        assert copy_btn is not None, "Copy button not found"

        QTest.keyClick(copy_btn, Qt.Key_Enter)

        clipboard = QGuiApplication.clipboard()
        if clipboard:
            assert clipboard.text(QClipboard.Mode.Clipboard) == url, (
                "Clipboard should contain the share URL after Enter on Copy"
            )

    def test_copy_button_via_space(self, qt_widget, qtbot):
        """Space on Copy button copies share_url to clipboard."""
        from ui.dialogs.share_route_dialog import ShareRouteDialog

        url = "https://operion.app/route?stops=space-test"
        dialog = ShareRouteDialog(parent=qt_widget, share_url=url)
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        buttons = dialog.findChildren(QPushButton)
        copy_btn = next((b for b in buttons if "Copy" in b.text()), None)
        assert copy_btn is not None, "Copy button not found"

        # Send Space directly to the button (focus not required for keyClick)
        QTest.keyClick(copy_btn, Qt.Key_Space)

        clipboard = QGuiApplication.clipboard()
        if clipboard:
            assert clipboard.text(QClipboard.Mode.Clipboard) == url, (
                "Clipboard should contain the share URL after Space on Copy"
            )


# ======================================================================
# CoPilotConfirmationModal
# ======================================================================


class TestConfirmationModalKeyboard:
    """CoPilotConfirmationModal — keyboard interaction tests."""

    # ── Level 2 ────────────────────────────────────────────────────────

    def test_enter_confirm_level2(self, qt_widget, qtbot):
        """Enter on confirm button at Level 2 accepts the modal."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(
            parent=qt_widget, confirmation_level=2
        )
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        assert modal._confirm_btn.isEnabled(), (
            "Level 2 confirm button should be enabled by default"
        )
        modal._confirm_btn.setFocus()
        QTest.keyClick(modal._confirm_btn, Qt.Key_Enter)

        assert modal.result() == QDialog.Accepted, (
            "Modal should be accepted after Enter on Confirm"
        )

    def test_enter_does_not_confirm_level3_until_phrase_typed(self, qt_widget, qtbot):
        """Enter on disabled confirm at Level 3 does nothing; typing phrase allows it."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            confirmation_level=3,
            confirmation_phrase="delete",
        )
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        assert not modal._confirm_btn.isEnabled(), (
            "Level 3 confirm button should start disabled"
        )

        # Enter on disabled button should not accept
        modal._confirm_btn.setFocus()
        QTest.keyClick(modal._confirm_btn, Qt.Key_Enter)
        assert modal.result() != QDialog.Accepted, (
            "Modal should not accept without phrase typed"
        )

        # Type the phrase and try again
        qtbot.keyClicks(modal._phrase_input, "delete")
        assert modal._confirm_btn.isEnabled(), (
            "Confirm button should be enabled after typing phrase"
        )
        modal._confirm_btn.setFocus()
        QTest.keyClick(modal._confirm_btn, Qt.Key_Enter)
        assert modal.result() == QDialog.Accepted, (
            "Modal should accept after phrase is typed and Enter pressed"
        )

    def test_escape_dismisses_level2(self, qt_widget, qtbot):
        """Escape dismisses Level 2 modal."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(
            parent=qt_widget, confirmation_level=2
        )
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        QTest.keyClick(modal, Qt.Key_Escape)
        assert modal.result() == QDialog.Rejected, (
            "Modal should be rejected on Escape"
        )

    def test_tab_order_level3(self, qt_widget, qtbot):
        """Tab order at Level 3: scroll area → phrase input → Cancel → Confirm."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            confirmation_level=3,
            confirmation_phrase="delete",
        )
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        cancel_btn = next(
            (btn for btn in modal.findChildren(QPushButton) if btn.text() == "Cancel"),
            None,
        )
        assert cancel_btn is not None, "Cancel button not found"

        focusable = collect_focusable_children(modal)

        # Find scroll area
        scroll_areas = [w for w in focusable if isinstance(w, QScrollArea)]
        assert len(scroll_areas) >= 1, "Expected at least one QScrollArea"

        scroll_idx = focusable.index(scroll_areas[0])
        phrase_idx = focusable.index(modal._phrase_input)
        cancel_idx = focusable.index(cancel_btn)
        confirm_idx = focusable.index(modal._confirm_btn)

        assert scroll_idx < phrase_idx < cancel_idx < confirm_idx, (
            f"Expected scroll ({scroll_idx}) < phrase ({phrase_idx}) "
            f"< Cancel ({cancel_idx}) < Confirm ({confirm_idx})"
        )

    def test_phrase_input_typing_enables_confirm(self, qt_widget, qtbot):
        """Partial phrase keeps confirm disabled; full phrase enables it."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            confirmation_level=3,
            confirmation_phrase="delete",
        )
        qtbot.addWidget(modal)

        assert not modal._confirm_btn.isEnabled(), (
            "Confirm should be disabled initially"
        )

        qtbot.keyClicks(modal._phrase_input, "del")
        assert not modal._confirm_btn.isEnabled(), (
            "Confirm should still be disabled with partial phrase"
        )

        qtbot.keyClicks(modal._phrase_input, "ete")
        assert modal._confirm_btn.isEnabled(), (
            "Confirm should be enabled after full phrase typed"
        )

    def test_escape_dismisses_level3(self, qt_widget, qtbot):
        """Escape dismisses Level 3 modal."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            confirmation_level=3,
            confirmation_phrase="delete",
        )
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        QTest.keyClick(modal, Qt.Key_Escape)
        assert modal.result() == QDialog.Rejected, (
            "Level 3 modal should be rejected on Escape"
        )


# ======================================================================
# QtPairedAssignmentDialog
# ======================================================================


def _make_item(label: str = "Item", sublabel: str = "Details") -> dict:
    return {
        "id": 1,
        "label": label,
        "sublabel": sublabel,
        "score": 85,
        "available": True,
        "status_text": "",
    }


class TestPairedAssignmentDialogKeyboard:
    """QtPairedAssignmentDialog — keyboard interaction tests."""

    def test_escape_dismisses(self, qt_widget, qtbot):
        """Escape key dismisses the dialog."""
        from ui.dialogs.paired_assignment_dialog import QtPairedAssignmentDialog

        dialog = QtPairedAssignmentDialog(
            parent=qt_widget,
            trip_data={"trip_id": "T-001"},
            truck_items=[_make_item("TRK-001")],
            driver_items=[_make_item("DRV-042")],
        )
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        QTest.keyClick(dialog, Qt.Key_Escape)
        assert dialog.result() == QDialog.Rejected, (
            "Dialog should be rejected on Escape"
        )

    def test_tab_order_buttons(self, qt_widget, qtbot):
        """Tab order: Cancel → Assign Both → Truck Only → Driver Only."""
        from ui.dialogs.paired_assignment_dialog import QtPairedAssignmentDialog
        from ui.widgets import ActionButton

        dialog = QtPairedAssignmentDialog(
            parent=qt_widget,
            trip_data={"trip_id": "T-001"},
            truck_items=[
                _make_item("TRK-001"),
                _make_item("TRK-002"),
            ],
            driver_items=[
                _make_item("DRV-042"),
                _make_item("DRV-099"),
            ],
        )
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        focusable = collect_focusable_children(dialog)

        # Find Cancel button from the button row: it's the first ActionButton
        # child of _both_btn's parent (the button row widget).
        btn_row = dialog._both_btn.parent() if dialog._both_btn else None
        assert btn_row is not None
        btn_row_children = btn_row.findChildren(ActionButton)
        cancel_btn = btn_row_children[0] if btn_row_children else None
        assert cancel_btn is not None, "Cancel button not found"
        assert dialog._both_btn is not None, "Assign Both button not found"
        assert dialog._truck_btn is not None, "Truck Only button not found"
        assert dialog._driver_btn is not None, "Driver Only button not found"

        cancel_idx = focusable.index(cancel_btn)
        both_idx = focusable.index(dialog._both_btn)
        truck_idx = focusable.index(dialog._truck_btn)
        driver_idx = focusable.index(dialog._driver_btn)

        assert cancel_idx < both_idx < truck_idx < driver_idx, (
            f"Expected Cancel ({cancel_idx}) < Assign Both ({both_idx}) "
            f"< Truck Only ({truck_idx}) < Driver Only ({driver_idx})"
        )

    def test_enter_assigns_both_when_available(self, qt_widget, qtbot):
        """Enter on Assign Both button accepts the dialog when truck+driver selected."""
        from ui.dialogs.paired_assignment_dialog import QtPairedAssignmentDialog

        dialog = QtPairedAssignmentDialog(
            parent=qt_widget,
            trip_data={"trip_id": "T-001"},
            truck_items=[_make_item("TRK-001")],
            driver_items=[_make_item("DRV-042")],
        )
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        # Auto-select should have picked the first available truck + driver
        assert dialog._selected_truck is not None, "Truck should be auto-selected"
        assert dialog._selected_driver is not None, "Driver should be auto-selected"
        assert dialog._both_btn is not None
        assert dialog._both_btn.isEnabled(), "Assign Both should be enabled"

        dialog._both_btn.setFocus()
        with patch.object(dialog, "_do_assign_both") as mock_assign:
            QTest.keyClick(dialog._both_btn, Qt.Key_Enter)
            mock_assign.assert_called_once()
