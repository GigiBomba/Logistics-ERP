"""Accessibility tests for TemplateEditorDialog.

Gap: TemplateEditorDialog does not set accessibleName or accessibleDescription.
Child controls (name edit, subject edit, body editor, button box buttons)
also lack accessibleName.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from tests.a11y.conftest import (
    assert_accessible_description_not_empty,
    assert_accessible_name_not_empty,
    assert_widget_has_focus,
    collect_focusable_children,
)


class TestTemplateEditorDialogA11y:
    """TemplateEditorDialog — modal dialog for editing an email template."""

    def test_dialog_accessible_name(self, qt_widget, qtbot):
        """TemplateEditorDialog should expose an accessibleName (gap)."""
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog

        dialog = TemplateEditorDialog(parent=qt_widget, template=None)
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog)

    def test_dialog_accessible_description(self, qt_widget, qtbot):
        """TemplateEditorDialog should expose an accessibleDescription (gap)."""
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog

        dialog = TemplateEditorDialog(parent=qt_widget, template=None)
        qtbot.addWidget(dialog)
        assert_accessible_description_not_empty(dialog)

    def test_name_edit_accessible_name(self, qt_widget, qtbot):
        """Name input should have an accessibleName (gap)."""
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog

        dialog = TemplateEditorDialog(parent=qt_widget, template=None)
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog._name_edit)

    def test_subject_edit_accessible_name(self, qt_widget, qtbot):
        """Subject input should have an accessibleName (gap)."""
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog

        dialog = TemplateEditorDialog(parent=qt_widget, template=None)
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog._subject_edit)

    def test_body_editor_accessible_name(self, qt_widget, qtbot):
        """Body text editor should have an accessibleName (gap)."""
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog

        dialog = TemplateEditorDialog(parent=qt_widget, template=None)
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog._body_editor)

    def test_dialog_button_box_accessible_names(self, qt_widget, qtbot):
        """OK and Cancel buttons should have accessibleNames (gap)."""
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog

        dialog = TemplateEditorDialog(parent=qt_widget, template=None)
        qtbot.addWidget(dialog)
        button_box = dialog.findChild(QDialogButtonBox)
        assert button_box is not None, "QDialogButtonBox not found"
        for btn in button_box.buttons():
            assert_accessible_name_not_empty(btn)

    def test_populated_dialog_retains_accessible_name(self, qt_widget, qtbot):
        """TemplateEditorDialog should have accessibleName when populated (gap)."""
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog

        template = {
            "name": "Test Template",
            "subject": "Payment Notice: {invoice_number}",
            "body_text": "Body text here",
            "body_html": "<p>Body HTML here</p>",
        }
        dialog = TemplateEditorDialog(parent=qt_widget, template=template)
        qtbot.addWidget(dialog)
        assert_accessible_name_not_empty(dialog)

    # ── Keyboard navigation ────────────────────────────────────────────

    def test_tab_order_editors(self, qt_widget, qtbot):
        """Tab order: name → subject → body → save → cancel."""
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog

        dialog = TemplateEditorDialog(parent=qt_widget, template=None)
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        button_box = dialog.findChild(QDialogButtonBox)
        assert button_box is not None, "QDialogButtonBox not found"

        save_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        assert save_btn is not None, "Save (OK) button not found"
        assert cancel_btn is not None, "Cancel button not found"

        focusable = collect_focusable_children(dialog)

        name_idx = focusable.index(dialog._name_edit)
        subject_idx = focusable.index(dialog._subject_edit)
        body_idx = focusable.index(dialog._body_editor)
        save_idx = focusable.index(save_btn)
        cancel_idx = focusable.index(cancel_btn)

        assert name_idx < subject_idx < body_idx < save_idx < cancel_idx, (
            f"Expected name ({name_idx}) < subject ({subject_idx}) < body ({body_idx}) "
            f"< save ({save_idx}) < cancel ({cancel_idx})"
        )

    def test_escape_dismisses(self, qt_widget, qtbot):
        """Escape key dismisses the dialog."""
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog

        dialog = TemplateEditorDialog(parent=qt_widget, template=None)
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        QTest.keyClick(dialog, Qt.Key_Escape)
        assert dialog.result() == QDialog.Rejected, (
            "Dialog should be rejected on Escape"
        )

    def test_enter_on_save_button(self, qt_widget, qtbot):
        """Enter on Save (OK) button accepts the dialog."""
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog

        dialog = TemplateEditorDialog(parent=qt_widget, template=None)
        qtbot.addWidget(dialog)
        dialog.show()
        QTest.qWaitForWindowExposed(dialog)

        button_box = dialog.findChild(QDialogButtonBox)
        assert button_box is not None, "QDialogButtonBox not found"

        save_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert save_btn is not None, "Save (OK) button not found"

        save_btn.setFocus()
        assert_widget_has_focus(save_btn)

        QTest.keyClick(save_btn, Qt.Key_Enter)
        assert dialog.result() == QDialog.Accepted, (
            "Dialog should be accepted after Enter on Save"
        )
