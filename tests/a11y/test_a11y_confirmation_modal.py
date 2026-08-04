"""Accessibility tests for CoPilotConfirmationModal.

CoPilotConfirmationModal is a QDialog that shows before/after diffs, level
warnings, and confirm/cancel buttons.  Currently the modal and its child
controls do not set explicit accessibleName — these tests document the gap.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from tests.a11y.conftest import (
    assert_accessible_name_not_empty,
    assert_accessible_description_not_empty,
    assert_widget_has_focus,
)

# ── SP workaround ──────────────────────────────────────────────────────


class TestCoPilotConfirmationModalA11y:
    """CoPilotConfirmationModal — confirmation dialog with diff view.

    Supports three modes: step review (Level 2), typed confirmation (Level 3),
    and OCR multi-candidate pick-list.
    """

    # ── Level 2 (simple warning) ─────────────────────────────────────────

    def test_modal_has_accessible_name(self, qt_widget, qtbot):
        """Modal dialog should have an accessibleName."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(parent=qt_widget)
        qtbot.addWidget(modal)
        assert_accessible_name_not_empty(modal)

    def test_confirm_button_has_accessible_name(self, qt_widget, qtbot):
        """Confirm button should be accessible."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(parent=qt_widget)
        qtbot.addWidget(modal)
        assert_accessible_name_not_empty(modal._confirm_btn)

    def test_cancel_button_has_accessible_name(self, qt_widget, qtbot):
        """Cancel button should be accessible."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(parent=qt_widget)
        qtbot.addWidget(modal)
        cancel_btn = next(
            (btn for btn in modal.findChildren(QPushButton) if btn.text() == "Cancel"),
            None,
        )
        assert cancel_btn is not None, "Modal should have a Cancel button"
        assert_accessible_name_not_empty(cancel_btn)

    def test_modal_accessible_description(self, qt_widget, qtbot):
        """Modal dialog should have an accessibleDescription."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(parent=qt_widget)
        qtbot.addWidget(modal)
        assert_accessible_description_not_empty(modal)

    # ── Level 3 (typed confirmation) ─────────────────────────────────────

    def test_level3_phrase_input_has_accessible_name(self, qt_widget, qtbot):
        """Level 3 phrase input should have accessibleName."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            confirmation_level=3,
            confirmation_phrase="delete",
        )
        qtbot.addWidget(modal)
        assert modal._phrase_input is not None, (
            "Level 3 modal should have a phrase input"
        )
        assert_accessible_name_not_empty(modal._phrase_input)

    def test_level3_confirm_disabled_by_default(self, qt_widget, qtbot):
        """Level 3 confirm button starts disabled until phrase is typed."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            confirmation_level=3,
            confirmation_phrase="delete",
        )
        qtbot.addWidget(modal)
        assert not modal._confirm_btn.isEnabled(), (
            "Level 3 Confirm button should be disabled until phrase is typed"
        )

    # ── Tab order ────────────────────────────────────────────────────────

    def test_tab_order_cancel_before_confirm(self, qt_widget, qtbot):
        """Tab order should move from Cancel to Confirm button.

        Currently the buttons are added Cancel first, then Confirm, so tab
        order is Cancel → Confirm (not Confirm → Cancel as preferred for a11y).
        """
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(parent=qt_widget, confirmation_level=2)
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        cancel_btn = next(
            (btn for btn in modal.findChildren(QPushButton) if btn.text() == "Cancel"),
            None,
        )
        confirm_btn = modal._confirm_btn
        assert cancel_btn is not None
        assert confirm_btn is not None

        # Focus the Cancel button
        cancel_btn.setFocus()
        assert_widget_has_focus(cancel_btn)

        # Tab should move to Confirm
        QTest.keyClick(cancel_btn, Qt.Key_Tab)
        assert_widget_has_focus(confirm_btn)

    # ── Dismissal behaviour ──────────────────────────────────────────────

    def test_escape_key_dismisses(self, qt_widget, qtbot):
        """Escape key should dismiss the modal."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(parent=qt_widget)
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)
        assert modal.isVisible(), "Modal should be visible before Escape"

        QTest.keyClick(modal, Qt.Key_Escape)
        # QDialog::reject() hides the dialog
        assert not modal.isVisible(), "Modal should be dismissed on Escape"

    def test_cancel_button_dismisses(self, qt_widget, qtbot):
        """Cancel button should dismiss the modal via reject()."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(parent=qt_widget)
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        cancel_btn = next(
            (btn for btn in modal.findChildren(QPushButton) if btn.text() == "Cancel"),
            None,
        )
        assert cancel_btn is not None
        QTest.mouseClick(cancel_btn, Qt.LeftButton)
        assert not modal.isVisible(), "Modal should be dismissed after Cancel click"

    # ── Keyboard navigation tests ─────────────────────────────────────

    def test_level2_full_keyboard_flow(self, qt_widget, qtbot):
        """Level 2: Tab to Confirm → Enter → accepted."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(parent=qt_widget, confirmation_level=2)
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        confirm_btn = modal._confirm_btn
        assert confirm_btn is not None
        assert confirm_btn.isEnabled(), (
            "Level 2 Confirm button should be enabled by default"
        )

        # Send Enter directly to the Confirm button.
        # QPushButton inside a QDialog has autoDefault=true so Enter triggers
        # animateClick → clicked → _on_confirm → accept().
        QTest.keyClick(confirm_btn, Qt.Key_Enter)

        assert modal.is_confirmed, "Modal should be confirmed"
        assert modal.result() == QDialog.Accepted, "Modal should be accepted"

    def test_level3_full_keyboard_flow(self, qt_widget, qtbot):
        """Level 3: type phrase, then Enter on Confirm → accepted."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        phrase = "delete"
        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            confirmation_level=3,
            confirmation_phrase=phrase,
        )
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        # Type the confirmation phrase
        modal._phrase_input.setFocus()
        qtbot.keyClicks(modal._phrase_input, phrase)

        confirm_btn = modal._confirm_btn
        assert confirm_btn.isEnabled(), (
            "Confirm button should be enabled after typing the correct phrase"
        )

        # Send Enter directly to the Confirm button.
        # QPushButton inside QDialog: autoDefault=true → Enter triggers animateClick.
        QTest.keyClick(confirm_btn, Qt.Key_Enter)

        assert modal.is_confirmed, "Modal should be confirmed"
        assert modal.result() == QDialog.Accepted, "Modal should be accepted"

    def test_level3_escape_dismisses_before_typing(self, qt_widget, qtbot):
        """Pressing Escape before typing the phrase should reject."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            confirmation_level=3,
            confirmation_phrase="delete",
        )
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)
        assert modal.isVisible(), "Modal should be visible before Escape"

        # Press Escape (phrase not typed yet)
        QTest.keyClick(modal, Qt.Key_Escape)

        assert not modal.isVisible(), "Modal should be dismissed on Escape"
        assert not modal.is_confirmed, "Modal should not be confirmed"
        assert modal.result() == QDialog.Rejected, "Modal should be rejected"

    def test_level3_enter_does_not_confirm_without_phrase(self, qt_widget, qtbot):
        """Pressing Enter while Confirm is disabled should not confirm."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            confirmation_level=3,
            confirmation_phrase="delete",
        )
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        confirm_btn = modal._confirm_btn
        assert not confirm_btn.isEnabled(), (
            "Confirm button should be disabled before phrase is typed"
        )

        # Signal spy to detect if confirmed fires
        confirmed_signaled = []
        modal.confirmed.connect(lambda: confirmed_signaled.append(True))

        # Send Enter to the disabled Confirm button.
        # Since it's disabled, keyPressEvent won't call animateClick,
        # so _on_confirm is NOT invoked.
        QTest.keyClick(confirm_btn, Qt.Key_Enter)

        assert len(confirmed_signaled) == 0, (
            "confirmed signal should NOT be emitted"
        )
        assert not modal.is_confirmed, "Modal should not be confirmed"

    def test_ocr_full_keyboard_flow(self, qt_widget, qtbot):
        """OCR: Space to select candidate, Enter on Confirm → accepted."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        candidates = ["INVOICE-123", "INVOICE-456", "INVOICE-789"]
        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            ocr_candidates=candidates,
        )
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        confirm_btn = modal._confirm_btn
        # Confirm starts disabled
        assert not confirm_btn.isEnabled(), (
            "Confirm should be disabled before candidate selection"
        )

        # Get radio buttons (3 candidates + 1 "none of these")
        radio_buttons = modal._ocr_group.buttons()
        assert len(radio_buttons) == 4

        # Select the first candidate via Space key.
        # QRadioButton::keyPressEvent handles Space by calling animateClick(),
        # which emits clicked() and calls nextCheckState() → setChecked(true).
        first_candidate = radio_buttons[0]
        QTest.keyClick(first_candidate, Qt.Key_Space)

        assert confirm_btn.isEnabled(), (
            "Confirm should be enabled after candidate selection"
        )

        # Enter on Confirm — autoDefault=true in QDialog, so Enter triggers click
        QTest.keyClick(confirm_btn, Qt.Key_Enter)

        assert modal.is_confirmed, "Modal should be confirmed"
        assert modal.result() == QDialog.Accepted, "Modal should be accepted"
        assert modal.selected_candidate == 0, "First candidate should be selected"

    def test_ocr_none_of_these_keyboard(self, qt_widget, qtbot):
        """Select 'None of these' radio → Enter on Confirm → accepted."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        candidates = ["INVOICE-123", "INVOICE-456"]
        modal = CoPilotConfirmationModal(
            parent=qt_widget,
            ocr_candidates=candidates,
        )
        qtbot.addWidget(modal)
        modal.show()
        QTest.qWaitForWindowExposed(modal)

        confirm_btn = modal._confirm_btn
        # Confirm starts disabled
        assert not confirm_btn.isEnabled(), (
            "Confirm should be disabled before candidate selection"
        )

        # Get the "None of these" radio (last button added to the group)
        radio_buttons = modal._ocr_group.buttons()
        none_radio = radio_buttons[-1]
        none_of_these_id = modal._ocr_group.id(none_radio)
        assert none_of_these_id < 0, "None of these should have a negative id"

        # Select via keyboard simulation (setChecked + _on_candidate_changed)
        none_radio.setChecked(True)
        modal._on_candidate_changed()
        assert modal._ocr_group.checkedId() == none_of_these_id, (
            "'None of these' should be checked"
        )

        assert confirm_btn.isEnabled(), (
            "Confirm should be enabled after 'none of these' selection"
        )

        # Enter on Confirm
        QTest.keyClick(confirm_btn, Qt.Key_Enter)

        assert modal.is_confirmed, "Modal should be confirmed"
        assert modal.result() == QDialog.Accepted, "Modal should be accepted"
        assert modal.selected_candidate == none_of_these_id, (
            "Should select 'none of these'"
        )
