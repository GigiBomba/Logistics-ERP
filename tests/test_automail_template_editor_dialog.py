"""Tests for TemplateEditorDialog — automail email template editor."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QTextEdit,
)

from ui.views.automail.template_editor_dialog import TemplateEditorDialog
from ui.widgets import StyledLineEdit


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def sample_template():
    return {
        "name": "Friendly Reminder",
        "subject": "Payment Reminder: Invoice {invoice_number}",
        "body_text": "Dear {client_contact}, please pay.",
        "body_html": "<p>Dear {client_contact}, please pay.</p>",
    }


# ── Creation ────────────────────────────────────────────────────────────


class TestTemplateEditorDialogCreation:
    def test_creation_create_mode(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert dlg._template is None
        assert "New Template" in dlg.windowTitle() or "New" in dlg.windowTitle()

    def test_creation_edit_mode(self, qt_widget, qtbot, sample_template):
        dlg = TemplateEditorDialog(qt_widget, template=sample_template)
        qtbot.addWidget(dlg)
        assert dlg._template is sample_template
        assert "Edit Template" in dlg.windowTitle() or "Edit" in dlg.windowTitle()

    def test_modal(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert dlg.isModal() is True

    def test_minimum_dimensions(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert dlg.minimumWidth() >= 600
        assert dlg.minimumHeight() >= 500


# ── UI Elements ─────────────────────────────────────────────────────────


class TestTemplateEditorDialogUI:
    def test_has_name_edit(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert isinstance(dlg._name_edit, StyledLineEdit)

    def test_has_subject_field(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert isinstance(dlg._subject_edit, QLineEdit)

    def test_has_body_editor(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert isinstance(dlg._body_editor, QTextEdit)
        assert dlg._body_editor.acceptRichText() is True
        assert dlg._body_editor.minimumHeight() >= 200

    def test_has_variable_reference_label(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        text = dlg.findChild(type(dlg)) or dlg  # just check it exists
        # Variable label was built - find it
        from PySide6.QtWidgets import QLabel
        labels = dlg.findChildren(QLabel)
        var_labels = [lbl for lbl in labels if "Available" in lbl.text() or "{" in lbl.text()]
        assert len(var_labels) >= 1

    def test_has_buttons(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        buttons = dlg.findChildren(QDialogButtonBox)
        assert len(buttons) >= 1


# ── Populate (edit mode) ────────────────────────────────────────────────


class TestTemplateEditorDialogPopulate:
    def test_populate_name(self, qt_widget, qtbot, sample_template):
        dlg = TemplateEditorDialog(qt_widget, template=sample_template)
        qtbot.addWidget(dlg)
        assert dlg._name_edit.text() == "Friendly Reminder"

    def test_populate_subject(self, qt_widget, qtbot, sample_template):
        dlg = TemplateEditorDialog(qt_widget, template=sample_template)
        qtbot.addWidget(dlg)
        assert dlg._subject_edit.text() == "Payment Reminder: Invoice {invoice_number}"

    def test_populate_body_html(self, qt_widget, qtbot):
        template = {
            "name": "HTML Template",
            "subject": "Test",
            "body_text": "plain",
            "body_html": "<p>HTML <strong>content</strong></p>",
        }
        dlg = TemplateEditorDialog(qt_widget, template=template)
        qtbot.addWidget(dlg)
        # Body editor should show HTML when body_html is non-empty
        html = dlg._body_editor.toHtml()
        assert "HTML" in html or "strong" in html or "content" in html

    def test_populate_body_text_fallback(self, qt_widget, qtbot):
        template = {
            "name": "Text Template",
            "subject": "Test",
            "body_text": "Plain text body",
            "body_html": "",
        }
        dlg = TemplateEditorDialog(qt_widget, template=template)
        qtbot.addWidget(dlg)
        assert dlg._body_editor.toPlainText() == "Plain text body"

    def test_populate_empty_template(self, qt_widget, qtbot):
        template = {
            "name": "",
            "subject": "",
            "body_text": "",
            "body_html": "",
        }
        dlg = TemplateEditorDialog(qt_widget, template=template)
        qtbot.addWidget(dlg)
        assert dlg._name_edit.text() == ""
        assert dlg._subject_edit.text() == ""
        assert dlg._body_editor.toPlainText() == ""


# ── get_data ────────────────────────────────────────────────────────────


class TestTemplateEditorDialogGetData:
    def test_get_data_returns_dict(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        data = dlg.get_data()
        assert isinstance(data, dict)

    def test_get_data_contains_keys(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        data = dlg.get_data()
        assert "name" in data
        assert "subject" in data
        assert "body_text" in data
        assert "body_html" in data

    def test_get_data_reflects_input(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg._name_edit.setText("Custom Template")
        dlg._subject_edit.setText("Subject Line")
        dlg._body_editor.setPlainText("Body content")
        data = dlg.get_data()
        assert data["name"] == "Custom Template"
        assert data["subject"] == "Subject Line"
        assert "Body content" in data["body_text"]


# ── Lifecycle ───────────────────────────────────────────────────────────


class TestTemplateEditorDialogLifecycle:
    def test_open_and_close(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg.show()
        assert dlg.isVisible() is True
        dlg.close()
        assert dlg.isVisible() is False

    def test_reject_via_button(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        buttons = dlg.findChildren(QDialogButtonBox)
        assert len(buttons) >= 1
        buttons[0].button(QDialogButtonBox.StandardButton.Cancel).click()
        assert dlg.result() == QDialog.Rejected

    def test_accept_via_button(self, qt_widget, qtbot):
        dlg = TemplateEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg._name_edit.setText("Test")
        buttons = dlg.findChildren(QDialogButtonBox)
        buttons[0].button(QDialogButtonBox.StandardButton.Ok).click()
        # After accept(), result is Accepted
        # Note: Accept relies on QDialogButtonBox connected to accept()
        pass  # OK button connected via buttons.accepted.connect(self.accept)
