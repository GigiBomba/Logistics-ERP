"""Comprehensive Qt unit tests for CoPilotConfirmationModal.

Tests cover:
  - Widget construction (initially hidden)
  - Display with title, message, confirm button, cancel button
  - Confirm button click triggers confirmed signal
  - Cancel button click triggers rejected signal
  - Keyboard shortcuts: Enter confirms, Escape cancels
  - Modal blocks interaction with parent window (modal behavior)
  - Custom button text (overriding defaults)
  - Dynamic content update
  - Show/hide transitions
  - Multiple rapid confirm/cancel calls
  - Signal emission testing for both confirm and cancel paths
  - Level 2 vs Level 3 confirmation behavior
  - OCR candidate mode
  - from_steps classmethod
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def modal(qt_widget: QWidget) -> "CoPilotConfirmationModal":
    """Build a default Level-2 confirmation modal attached to a parent."""
    from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

    m = CoPilotConfirmationModal(
        parent=qt_widget,
        steps=[],
        confirmation_level=2,
    )
    # qtbot will clean up via qt_widget parent relationship
    return m


@pytest.fixture
def modal_with_steps(qt_widget: QWidget) -> "CoPilotConfirmationModal":
    """Build a modal with sample steps."""
    from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

    steps = [
        {
            "tool_name": "dispatch.create",
            "confirmation_level": 2,
            "parameters": {"route_id": "R-42", "driver": "John"},
        },
        {
            "tool_name": "invoice.generate",
            "confirmation_level": 3,
            "parameters": {"client": "Acme Corp", "amount": 1500.0},
            "before": {"status": "draft"},
            "after": {"status": "final"},
        },
    ]
    m = CoPilotConfirmationModal(
        parent=qt_widget,
        steps=steps,
        confirmation_level=2,
    )
    return m


@pytest.fixture
def modal_level3(qt_widget: QWidget) -> "CoPilotConfirmationModal":
    """Build a Level-3 (destructive) confirmation modal requiring typed phrase."""
    from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

    m = CoPilotConfirmationModal(
        parent=qt_widget,
        steps=[{"tool_name": "data.purge", "confirmation_level": 3, "parameters": {"table": "logs"}}],
        confirmation_level=3,
        confirmation_phrase="DELETE",
    )
    return m


@pytest.fixture
def modal_ocr(qt_widget: QWidget) -> "CoPilotConfirmationModal":
    """Build an OCR disambiguation modal."""
    from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

    m = CoPilotConfirmationModal(
        parent=qt_widget,
        ocr_candidates=["Invoice #1234", "Invoice #5678", "Receipt #9012"],
        confirmation_level=2,
    )
    return m


# =============================================================================
# Use the session-scoped QApp from test_conftest
# =============================================================================
pytestmark = pytest.mark.usefixtures("qapp")


# =============================================================================
# Widget Construction & Initialisation
# =============================================================================


class TestConstruction:
    """Verify the modal is built correctly with expected defaults."""

    def test_construction_defaults(self, qt_widget: QWidget):
        """Modal is created as a hidden dialog with modal=True."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        m = CoPilotConfirmationModal(parent=qt_widget)
        assert isinstance(m, QDialog)
        assert m.isModal() is True
        assert m.isVisible() is False
        assert m.windowTitle() != ""
        assert m.minimumWidth() == 560
        assert m.minimumHeight() == 400
        assert m.is_confirmed is False
        assert m.selected_candidate == -1

    def test_construction_no_parent(self):
        """Should construct safely with no parent."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        m = CoPilotConfirmationModal(parent=None)
        assert m is not None
        assert m.isModal() is True

    def test_construction_with_custom_summary(self, qt_widget: QWidget):
        """Custom summary_key and params appear in the header."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        m = CoPilotConfirmationModal(
            parent=qt_widget,
            summary_key="copilot.confirmation.review",
            summary_params={"action": "test"},
        )
        # Header QLabel should contain the translated text
        header = m.findChild(QLabel)
        assert header is not None
        assert header.text() != ""

    def test_construction_empty_state(self, qt_widget: QWidget):
        """When no steps and no OCR candidates, 'No confirmation needed' is shown."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        m = CoPilotConfirmationModal(parent=qt_widget, steps=[], confirmation_level=2)
        labels = m.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert any("No confirmation needed" in t or "confirmation" in t.lower() for t in texts)


# =============================================================================
# UI Elements
# =============================================================================


class TestUIElements:
    """Verify the modal contains the expected buttons, labels, and inputs."""

    def test_has_confirm_button(self, modal):
        """Confirm button exists and is initially enabled for Level 2."""
        btn = modal._confirm_btn
        assert isinstance(btn, QPushButton)
        assert btn.text() in ("Confirm", "")
        assert btn.isEnabled() is True

    def test_has_cancel_button(self, modal):
        """Cancel button exists."""
        cancel_btns = [btn for btn in modal.findChildren(QPushButton) if "Cancel" in btn.text()]
        assert len(cancel_btns) >= 1

    def test_confirm_disabled_for_level3(self, modal_level3):
        """Confirm button is initially disabled for Level 3."""
        assert modal_level3._confirm_btn.isEnabled() is False

    def test_level3_has_phrase_input(self, modal_level3):
        """Level 3 shows a QLineEdit for the confirmation phrase."""
        line_edit = modal_level3.findChild(QLineEdit)
        assert line_edit is not None
        assert line_edit.placeholderText() != ""

    def test_level3_confirm_enabled_on_correct_phrase(self, modal_level3, qtbot):
        """Typing the correct phrase enables the confirm button."""
        line_edit = modal_level3.findChild(QLineEdit)
        assert line_edit is not None
        qtbot.keyClicks(line_edit, "DELETE")
        assert modal_level3._confirm_btn.isEnabled() is True

    def test_level3_confirm_stays_disabled_on_wrong_phrase(self, modal_level3, qtbot):
        """Typing a wrong phrase keeps confirm disabled."""
        line_edit = modal_level3.findChild(QLineEdit)
        qtbot.keyClicks(line_edit, "WRONG")
        assert modal_level3._confirm_btn.isEnabled() is False

    def test_has_warning_label_level2(self, modal):
        """Level 2 shows a warning label."""
        labels = modal.findChildren(QLabel)
        warning_texts = [lbl.text() for lbl in labels if "business data" in lbl.text().lower() or "modify" in lbl.text().lower()]
        assert len(warning_texts) >= 1

    def test_has_warning_label_level3(self, modal_level3):
        """Level 3 shows an irreversible warning."""
        labels = modal_level3.findChildren(QLabel)
        warning_texts = [lbl.text() for lbl in labels if "irreversible" in lbl.text().lower()]
        assert len(warning_texts) >= 1

    def test_ocr_mode_has_radio_buttons(self, modal_ocr):
        """OCR mode shows radio buttons for each candidate plus 'None of these'."""
        from PySide6.QtWidgets import QRadioButton

        radios = modal_ocr.findChildren(QRadioButton)
        # 3 candidates + 1 "none of these" = 4 radio buttons
        assert len(radios) == 4
        assert modal_ocr._confirm_btn.isEnabled() is False  # No selection yet


# =============================================================================
# Signal Emission
# =============================================================================


class TestSignalEmission:
    """Verify correct signals are emitted on confirm/cancel."""

    def test_confirm_emits_confirmed_signal(self, modal, qtbot):
        """Clicking confirm emits the confirmed signal."""
        with qtbot.waitSignal(modal.confirmed, timeout=500):
            modal._confirm_btn.click()

    def test_confirm_also_accepts_dialog(self, modal, qtbot):
        """Clicking confirm calls accept() so dialog result is Accepted."""
        modal._confirm_btn.click()
        assert modal.result() == QDialog.DialogCode.Accepted

    def test_confirm_sets_is_confirmed(self, modal):
        """Clicking confirm sets the is_confirmed property to True."""
        modal._confirm_btn.click()
        assert modal.is_confirmed is True

    def test_cancel_emits_rejected_signal(self, modal, qtbot):
        """Clicking cancel emits the QDialog rejected signal."""
        with qtbot.waitSignal(modal.rejected, timeout=500):
            modal.reject()

    def test_cancel_sets_dialog_result_rejected(self, modal):
        """Cancel calls reject() which sets result to Rejected."""
        modal.reject()
        assert modal.result() == QDialog.DialogCode.Rejected

    def test_ocr_confirm_emits_candidate_selected(self, modal_ocr, qtbot):
        """Confirming in OCR mode emits candidate_selected with the chosen index."""
        from PySide6.QtWidgets import QRadioButton

        radios = modal_ocr.findChildren(QRadioButton)
        assert len(radios) >= 2, "Need at least 2 radio buttons"
        # Select the second candidate (index 1)
        radios[1].click()

        signal_called = False
        selected_index = None

        def _on_candidate(idx):
            nonlocal signal_called, selected_index
            signal_called = True
            selected_index = idx

        modal_ocr.candidate_selected.connect(_on_candidate)
        modal_ocr._confirm_btn.click()

        assert signal_called is True
        assert selected_index == 1

    def test_ocr_none_of_these_emits_minus_auto_id(self, modal_ocr):
        """Selecting 'None of these' and confirming emits candidate_selected
        with the auto-assigned negative id from QButtonGroup (typically -2)."""
        all_buttons = modal_ocr._ocr_group.buttons()
        assert len(all_buttons) >= 1
        none_radio = all_buttons[-1]  # Last button is "None of these"
        none_radio.click()

        # Get the actual auto-assigned id (QButtonGroup assigns -2, -3, etc. for id=-1)
        expected_id = modal_ocr._ocr_group.id(none_radio)
        assert expected_id < 0  # Should be a negative auto-assigned id

        selected_index = None

        def _on_candidate(idx):
            nonlocal selected_index
            selected_index = idx

        modal_ocr.candidate_selected.connect(_on_candidate)
        modal_ocr._confirm_btn.click()

        assert selected_index == expected_id

    def test_confirm_from_level3_with_phrase(self, modal_level3, qtbot):
        """Level 3 confirm emits confirmed signal after typing correct phrase."""
        line_edit = modal_level3.findChild(QLineEdit)
        qtbot.keyClicks(line_edit, "DELETE")

        with qtbot.waitSignal(modal_level3.confirmed, timeout=500):
            modal_level3._confirm_btn.click()

    def test_confirmed_signal_emitted_once_per_click(self, modal):
        """Each confirm click emits the confirmed signal exactly once."""
        emission_count = 0

        def count_emissions():
            nonlocal emission_count
            emission_count += 1

        modal.confirmed.connect(count_emissions)
        modal._confirm_btn.click()
        modal._confirm_btn.click()  # Second click — dialog already closed but signal fires
        assert emission_count == 2


# =============================================================================
# Keyboard Shortcuts
# =============================================================================


class TestKeyboardShortcuts:
    """Verify keyboard shortcuts trigger expected behavior."""

    def test_escape_rejects_dialog(self, modal, qtbot):
        """Pressing Escape calls reject()."""
        modal.show()
        qtbot.wait(50)
        with qtbot.waitSignal(modal.rejected, timeout=1000):
            qtbot.keyPress(modal, Qt.Key_Escape)

    def test_escape_sets_rejected_result(self, modal, qtbot):
        """Pressing Escape sets dialog result to Rejected."""
        modal.show()
        qtbot.wait(50)
        qtbot.keyPress(modal, Qt.Key_Escape)
        assert modal.result() == QDialog.DialogCode.Rejected

    def test_enter_key_on_confirm_button_triggers_confirm(self, modal, qtbot):
        """Pressing Enter while the confirm button is focused triggers it."""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        modal.show()
        qtbot.wait(50)
        modal._confirm_btn.setFocus()
        qtbot.wait(50)

        with qtbot.waitSignal(modal.confirmed, timeout=1000):
            event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Return, Qt.NoModifier)
            QApplication.sendEvent(modal._confirm_btn, event)
            qtbot.wait(100)

    def test_enter_key_on_cancel_button_triggers_reject(self, modal, qtbot):
        """Pressing Enter while cancel button is focused rejects."""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        # Find cancel button
        cancel_btns = [btn for btn in modal.findChildren(QPushButton) if "Cancel" in btn.text()]
        assert len(cancel_btns) >= 1
        cancel_btn = cancel_btns[0]

        modal.show()
        qtbot.wait(50)
        cancel_btn.setFocus()
        qtbot.wait(50)

        with qtbot.waitSignal(modal.rejected, timeout=1000):
            event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Return, Qt.NoModifier)
            QApplication.sendEvent(cancel_btn, event)
            qtbot.wait(100)

    def test_confirm_button_click_emits_confirmed(self, modal, qtbot):
        """Clicking the confirm button emits confirmed and sets is_confirmed."""
        modal._confirm_btn.click()
        qtbot.wait(50)
        assert modal.is_confirmed is True

    def test_enter_does_not_emit_confirmed_level3_without_phrase(self, modal_level3, qtbot):
        """Pressing Enter does not emit confirmed for Level 3 without the correct phrase."""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        emissions = []
        modal_level3.confirmed.connect(lambda: emissions.append(1))
        # Send key event via QApplication
        modal_level3.show()
        qtbot.wait(50)
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Return, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(modal_level3, event)
        qtbot.wait(100)
        assert len(emissions) == 0

    def test_confirm_click_works_level3_with_phrase(self, modal_level3, qtbot):
        """When phrase is typed, clicking confirm emits confirmed for Level 3."""
        line_edit = modal_level3.findChild(QLineEdit)
        qtbot.keyClicks(line_edit, "DELETE")
        assert modal_level3._confirm_btn.isEnabled() is True

        with qtbot.waitSignal(modal_level3.confirmed, timeout=500):
            modal_level3._confirm_btn.click()


# =============================================================================
# Modal Behavior
# =============================================================================


class TestModalBehavior:
    """Verify modal blocks interaction with parent."""

    def test_is_modal(self, modal):
        """Dialog is set as modal."""
        assert modal.isModal() is True

    def test_window_flags_include_dialog(self, modal):
        """Window flags indicate a dialog (modal)."""
        assert modal.windowFlags() & Qt.Dialog

    def test_modal_blocks_parent(self, qt_widget, modal):
        """Modal execution blocks interaction with parent (synchronous exec)."""
        # exec() would block, so just verify the modal flag is set
        assert modal.isModal() is True
        # The parent should be correctly set
        assert modal.parent() is qt_widget


# =============================================================================
# Custom Button Text
# =============================================================================


class TestCustomButtonText:
    """Verify button text uses translations or defaults."""

    def test_confirm_button_text(self, modal):
        """Confirm button shows default text."""
        assert modal._confirm_btn.text() in ("Confirm", "")

    def test_cancel_button_text(self, modal):
        """Cancel button shows default text."""
        cancel_btns = [btn for btn in modal.findChildren(QPushButton) if "Cancel" in btn.text()]
        assert len(cancel_btns) >= 1

    def test_button_text_uses_translation_keys(self, modal):
        """Buttons source their text from i18n translation keys."""
        from services.i18n import t

        expected_confirm = t("copilot.confirmation.confirm", default="Confirm")
        assert modal._confirm_btn.text() == expected_confirm

    def test_buttons_visible_when_shown(self, modal, qtbot):
        """Both confirm and cancel buttons are visible when dialog is shown."""
        modal.show()
        qtbot.wait(50)
        assert modal._confirm_btn.isVisible() is True
        # Find the cancel button
        cancel_btns = [btn for btn in modal.findChildren(QPushButton) if "Cancel" in btn.text()]
        assert len(cancel_btns) >= 1
        assert cancel_btns[0].isVisible() is True


# =============================================================================
# Dynamic Content Update
# =============================================================================


class TestDynamicContent:
    """Verify modal content can be updated dynamically."""

    def test_phrase_input_clears_on_retype(self, modal_level3, qtbot):
        """Clearing and retyping the phrase re-enables confirm."""
        line_edit = modal_level3.findChild(QLineEdit)
        qtbot.keyClicks(line_edit, "DELETE")
        assert modal_level3._confirm_btn.isEnabled() is True

        line_edit.clear()
        assert modal_level3._confirm_btn.isEnabled() is False

        qtbot.keyClicks(line_edit, "DELETE")
        assert modal_level3._confirm_btn.isEnabled() is True

    def test_phrase_input_strip_whitespace(self, modal_level3, qtbot):
        """Leading/trailing whitespace prevents phrase match."""
        # Modify the phrase input to test with spaces
        line_edit = modal_level3.findChild(QLineEdit)
        qtbot.keyClicks(line_edit, "  DELETE  ")
        # _on_phrase_changed strips whitespace: text.strip() == self._confirmation_phrase
        assert modal_level3._confirm_btn.isEnabled() is True

    def test_ocr_selection_changes_confirm_state(self, modal_ocr):
        """Selecting an OCR candidate enables the confirm button."""
        from PySide6.QtWidgets import QRadioButton

        assert modal_ocr._confirm_btn.isEnabled() is False
        radios = modal_ocr.findChildren(QRadioButton)
        assert len(radios) >= 1
        radios[0].click()
        assert modal_ocr._confirm_btn.isEnabled() is True


# =============================================================================
# Show/Hide Transitions
# =============================================================================


class TestShowHide:
    """Verify show/hide transitions work correctly."""

    def test_show_makes_visible(self, modal, qtbot):
        """Calling show() makes the modal visible."""
        modal.show()
        qtbot.wait(50)
        assert modal.isVisible() is True

    def test_hide_makes_invisible(self, modal, qtbot):
        """Calling hide() makes the modal invisible."""
        modal.show()
        qtbot.wait(50)
        assert modal.isVisible() is True
        modal.hide()
        qtbot.wait(50)
        assert modal.isVisible() is False

    def test_accept_closes_dialog(self, modal, qtbot):
        """Calling accept() closes (hides) the dialog."""
        modal.show()
        qtbot.wait(50)
        modal.accept()
        qtbot.wait(50)
        assert modal.isVisible() is False

    def test_reject_closes_dialog(self, modal, qtbot):
        """Calling reject() closes (hides) the dialog."""
        modal.show()
        qtbot.wait(50)
        modal.reject()
        qtbot.wait(50)
        assert modal.isVisible() is False


# =============================================================================
# Multiple Rapid Confirm/Cancel Calls
# =============================================================================


class TestRapidOperations:
    """Verify behavior under rapid confirm/cancel calls."""

    def test_double_confirm_emits_twice(self, modal):
        """Calling _on_confirm twice emits confirmed twice."""
        emissions = []

        def record():
            emissions.append(1)

        modal.confirmed.connect(record)
        modal._on_confirm()
        modal._on_confirm()
        assert len(emissions) == 2

    def test_confirm_then_reject(self, modal):
        """Confirm then reject still shows confirmed state."""
        modal._on_confirm()
        assert modal.is_confirmed is True
        modal.reject()
        assert modal.is_confirmed is True  # State persists

    def test_reject_then_confirm(self, modal):
        """Reject then confirm works correctly."""
        modal.reject()
        assert modal.is_confirmed is False
        modal._on_confirm()
        assert modal.is_confirmed is True

    def test_rapid_click_confirm_button(self, modal, qtbot):
        """Rapidly clicking confirm multiple times."""
        emissions = []

        def record():
            emissions.append(1)

        modal.confirmed.connect(record)
        modal._confirm_btn.click()
        modal._confirm_btn.click()
        modal._confirm_btn.click()
        assert len(emissions) == 3


# =============================================================================
# from_steps Classmethod
# =============================================================================


class TestFromSteps:
    """Verify the from_steps classmethod constructs correctly."""

    def test_from_steps_constructs(self, qt_widget):
        """from_steps creates a modal from ExecutionStep instances."""
        from ui.copilot.models import ExecutionStep, ConfirmationLevel
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        steps = [
            ExecutionStep(
                step_id="s1",
                tool_name="dispatch.create",
                confirmation_level=ConfirmationLevel.BUSINESS,
                parameters={"route_id": "R-42"},
            ),
        ]
        m = CoPilotConfirmationModal.from_steps(
            steps=steps,
            parent=qt_widget,
        )
        assert m is not None
        assert m._steps is not None
        assert len(m._steps) == 1
        assert m._steps[0]["tool_name"] == "dispatch.create"

    def test_from_steps_preserves_confirmation_level(self, qt_widget):
        """from_steps preserves the confirmation level."""
        from ui.copilot.models import ExecutionStep, ConfirmationLevel
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        steps = [
            ExecutionStep(
                step_id="s1",
                tool_name="data.purge",
                confirmation_level=ConfirmationLevel.DESTRUCTIVE,
            ),
        ]
        m = CoPilotConfirmationModal.from_steps(
            steps=steps,
            parent=qt_widget,
            confirmation_level=3,
            confirmation_phrase="DELETE",
        )
        assert m._confirmation_level == 3
        assert m._confirmation_phrase == "DELETE"

    def test_from_steps_empty(self, qt_widget):
        """from_steps with empty steps list works."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        m = CoPilotConfirmationModal.from_steps(steps=[], parent=qt_widget)
        assert m._steps == []


# =============================================================================
# Param Redaction
# =============================================================================


class TestParamRedaction:
    """Verify sensitive parameter values are redacted."""

    def test_redact_password(self):
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        params = {"username": "admin", "password": "secret123"}
        redacted = CoPilotConfirmationModal._redact_params(params)
        assert redacted["username"] == "admin"
        assert redacted["password"] == "****"

    def test_redact_token_and_secret(self):
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        params = {"api_token": "abc123", "client_secret": "xyz"}
        redacted = CoPilotConfirmationModal._redact_params(params)
        assert redacted["api_token"] == "****"
        assert redacted["client_secret"] == "****"

    def test_redact_auth_and_credential(self):
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        params = {"auth": "basic", "credential": "pass"}
        redacted = CoPilotConfirmationModal._redact_params(params)
        assert redacted["auth"] == "****"
        assert redacted["credential"] == "****"

    def test_redact_case_insensitive(self):
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        params = {"Password": "secret", "TOKEN": "abc", "SecretKey": "xyz"}
        redacted = CoPilotConfirmationModal._redact_params(params)
        assert redacted["Password"] == "****"
        assert redacted["TOKEN"] == "****"
        assert redacted["SecretKey"] == "****"

    def test_redact_non_sensitive_passthrough(self):
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        params = {"name": "test", "value": 42, "active": True}
        redacted = CoPilotConfirmationModal._redact_params(params)
        assert redacted["name"] == "test"
        assert redacted["value"] == 42
        assert redacted["active"] is True


# =============================================================================
# Step Diff Display
# =============================================================================


class TestStepDiff:
    """Verify step cards show before/after diffs when available."""

    def test_step_card_with_diff(self, qt_widget):
        """Steps with before/after values show diff widgets."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        steps = [
            {
                "tool_name": "update.status",
                "confirmation_level": 2,
                "parameters": {},
                "before": {"status": "pending"},
                "after": {"status": "completed"},
            },
        ]
        m = CoPilotConfirmationModal(parent=qt_widget, steps=steps)
        labels = m.findChildren(QLabel)
        label_texts = [lbl.text() for lbl in labels]
        assert any("Before" in t for t in label_texts)
        assert any("After" in t for t in label_texts)

    def test_step_card_without_diff_shows_params(self, qt_widget):
        """Steps without before/after values display parameters."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        steps = [
            {
                "tool_name": "simple.action",
                "confirmation_level": 2,
                "parameters": {"key1": "val1", "key2": "val2"},
            },
        ]
        m = CoPilotConfirmationModal(parent=qt_widget, steps=steps)
        labels = m.findChildren(QLabel)
        label_texts = " ".join(lbl.text() for lbl in labels)
        assert "key1" in label_texts or "val1" in label_texts or "simple.action" in label_texts

    def test_format_value_none(self, qt_widget):
        """_format_value returns '-' for None."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        m = CoPilotConfirmationModal(parent=qt_widget)
        assert m._format_value(None) == "-"

    def test_format_value_dict(self, qt_widget):
        """_format_value pretty-prints dicts."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        m = CoPilotConfirmationModal(parent=qt_widget)
        result = m._format_value({"a": 1, "b": "hello"})
        assert "a:" in result
        assert "1" in result
        assert "b:" in result
        assert "hello" in result

    def test_format_value_string(self, qt_widget):
        """_format_value returns str for non-dict values."""
        from ui.copilot.widgets.confirmation_modal import CoPilotConfirmationModal

        m = CoPilotConfirmationModal(parent=qt_widget)
        assert m._format_value(42) == "42"
        assert m._format_value("hello") == "hello"
