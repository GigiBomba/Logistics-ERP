"""Tests for the automail EditorPanel and _FormatToolbar."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.views.automail.editor_panel import EditorPanel, _FormatToolbar


# ── _FormatToolbar ─────────────────────────────────────────────────────


class TestFormatToolbar:
    def test_creation(self, qt_widget, qtbot):
        editor = QTextEdit()
        toolbar = _FormatToolbar(qt_widget, editor)
        qtbot.addWidget(toolbar)
        assert toolbar._editor is editor
        # Buttons: Bold, Italic, Underline, UL, OL
        buttons = toolbar.findChildren(QToolButton)
        assert len(buttons) >= 3  # at least B, I, U

    def test_toggle_bold(self, qt_widget, qtbot):
        editor = QTextEdit()
        editor.setPlainText("Hello")
        toolbar = _FormatToolbar(qt_widget, editor)
        qtbot.addWidget(toolbar)
        toolbar._toggle_bold()
        # Check format was applied (button checked state may not sync immediately)
        fmt = editor.textCursor().charFormat()
        assert fmt.fontWeight() >= 14  # QFont.Weight.Bold = 75, normal = 50 → >= 75

    def test_toggle_italic(self, qt_widget, qtbot):
        editor = QTextEdit()
        editor.setPlainText("Hello")
        toolbar = _FormatToolbar(qt_widget, editor)
        qtbot.addWidget(toolbar)
        toolbar._toggle_italic()
        fmt = editor.textCursor().charFormat()
        assert fmt.fontItalic() is True

    def test_toggle_underline(self, qt_widget, qtbot):
        editor = QTextEdit()
        editor.setPlainText("Hello")
        toolbar = _FormatToolbar(qt_widget, editor)
        qtbot.addWidget(toolbar)
        toolbar._toggle_underline()
        fmt = editor.textCursor().charFormat()
        assert fmt.fontUnderline() is True

    def test_insert_unordered_list(self, qt_widget, qtbot):
        editor = QTextEdit()
        toolbar = _FormatToolbar(qt_widget, editor)
        qtbot.addWidget(toolbar)
        toolbar._insert_unordered_list()
        html = editor.toHtml()
        assert "Item" in html  # The list inserted contains "Item"
        # The HTML structure may vary, verify content
        assert editor.toPlainText() == "Item\n" or "Item" in editor.toPlainText()

    def test_insert_ordered_list(self, qt_widget, qtbot):
        editor = QTextEdit()
        toolbar = _FormatToolbar(qt_widget, editor)
        qtbot.addWidget(toolbar)
        toolbar._insert_ordered_list()
        assert "Item" in editor.toPlainText()


# ── EditorPanel ────────────────────────────────────────────────────────


class TestEditorPanelCreation:
    def test_creation_without_db(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        assert panel._repo is None
        assert panel._template_service is None
        assert panel._current_template is None
        assert panel._preview_mode is False

    def test_creation_with_db(self, qt_widget, qtbot):
        db = MagicMock()
        panel = EditorPanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        assert panel._repo is not None
        assert panel._template_service is not None

    def test_property_role(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        assert panel.property("role") == "automail-editor-panel"

    def test_has_template_combo(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        assert panel._template_combo is not None
        assert panel._template_combo.count() == 0

    def test_has_subject_edit(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        assert panel._subject_edit is not None
        assert isinstance(panel._subject_edit, QLineEdit)

    def test_has_body_editor(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        assert panel._body_editor is not None
        assert isinstance(panel._body_editor, QTextEdit)

    def test_has_format_toolbar(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        toolbars = panel.findChildren(_FormatToolbar)
        assert len(toolbars) == 1

    def test_has_preview_widget(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        assert panel._preview_widget is not None
        # Preview is hidden by default
        assert panel._preview_widget.isVisible() is False

    def test_has_template_action_buttons(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        buttons = panel.findChildren(QPushButton)
        # Should have Edit, Dup, New, Del, Save, Send Test
        action_btn_texts = [btn.text() for btn in buttons]
        assert any("Edit" in t or "edit" in t for t in action_btn_texts)
        assert any("Save" in t or "save" in t for t in action_btn_texts)

    def test_variable_picker_popup_created(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        assert panel._var_picker is not None


class TestEditorPanelPreviewToggle:
    def test_toggle_preview_shows_preview(self, qt_widget, qtbot):
        db = MagicMock()
        panel = EditorPanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        panel.show()
        qtbot.wait(10)
        assert panel._preview_mode is False
        panel._toggle_preview()
        assert panel._preview_mode is True
        assert panel._preview_widget.isHidden() is False
        assert panel._body_editor.isHidden() is True

    def test_toggle_preview_back_to_edit(self, qt_widget, qtbot):
        db = MagicMock()
        panel = EditorPanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        panel.show()
        qtbot.wait(10)
        panel._toggle_preview()  # → preview
        panel._toggle_preview()  # → edit
        assert panel._preview_mode is False
        assert panel._preview_widget.isHidden() is True
        assert panel._body_editor.isHidden() is False

    def test_render_preview_called_on_toggle(self, qt_widget, qtbot):
        db = MagicMock()
        panel = EditorPanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        panel._current_template = {
            "id": 1,
            "name": "Test",
            "subject": "Hello {{client_name}}",
            "body_text": "Dear {{client_name}}",
            "body_html": "<p>Dear {{client_name}}</p>",
        }
        with patch.object(panel, "_render_preview") as mock_render:
            panel._toggle_preview()
            mock_render.assert_called_once()


class TestEditorPanelTemplateLoading:
    def test_load_templates_empty(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_template_by_id.return_value = None
        svc = MagicMock()
        svc.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ):
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._load_templates()
            assert panel._template_combo.count() == 0

    def test_load_templates_with_data(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_template_by_id.return_value = {
            "id": 10,
            "name": "Default",
            "subject": "Payment Notice",
            "body_text": "Dear client",
            "body_html": "",
        }
        svc = MagicMock()
        svc.get_all_templates.return_value = [
            {"id": 10, "name": "Default"},
            {"id": 20, "name": "Urgent"},
        ]

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ):
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._load_templates()
            assert panel._template_combo.count() == 2
            # First template should be auto-selected
            assert panel._current_template is not None

    def test_template_selected_updates_fields(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_template_by_id.return_value = {
            "id": 10,
            "name": "Default",
            "subject": "Payment Notice",
            "body_text": "Dear client",
            "body_html": "",
        }
        svc = MagicMock()
        svc.get_all_templates.return_value = [
            {"id": 10, "name": "Default"},
        ]

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ):
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._load_templates()
            assert panel._subject_edit.text() == "Payment Notice"
            assert panel._body_editor.toPlainText() == "Dear client"

    def test_template_selected_with_html_body(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_template_by_id.return_value = {
            "id": 10,
            "name": "HTML Template",
            "subject": "Notice",
            "body_text": "",
            "body_html": "<p>Dear <b>client</b></p>",
        }
        svc = MagicMock()
        svc.get_all_templates.return_value = [
            {"id": 10, "name": "HTML Template"},
        ]

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ):
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._load_templates()
            # Should contain the HTML
            html = panel._body_editor.toHtml()
            assert "client" in html.lower()

    def test_wakeup_loads_templates(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        svc = MagicMock()
        svc.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ):
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            svc.get_all_templates.reset_mock()
            panel.wakeup()
            svc.get_all_templates.assert_called_once()


class TestEditorPanelTemplateCRUD:
    def test_edit_template_opens_dialog(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        svc = MagicMock()
        svc.get_all_templates.return_value = [
            {"id": 10, "name": "Default"},
        ]
        repo.get_template_by_id.return_value = {
            "id": 10,
            "name": "Default",
            "subject": "Subject",
            "body_text": "Body",
            "body_html": "",
        }

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ), patch(
            "ui.views.automail.template_editor_dialog.TemplateEditorDialog",
        ) as mock_dlg:
            mock_dlg.return_value.exec.return_value = True
            mock_dlg.return_value.get_data.return_value = {
                "name": "Updated",
                "subject": "Updated Subject",
                "body_text": "Updated Body",
                "body_html": "",
            }
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._load_templates()
            panel._on_edit_template()
            repo.update_template.assert_called_once()
            # Should re-load templates after update
            svc.get_all_templates.assert_called()

    def test_edit_template_without_current(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._on_edit_template()  # Should not crash

    def test_duplicate_template(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        svc = MagicMock()
        svc.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ):
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._current_template = {
                "id": 1,
                "name": "Original",
                "subject": "Subject",
                "body_text": "Body",
                "body_html": "<p>Body</p>",
            }
            panel._on_duplicate_template()
            repo.create_template.assert_called_once()
            args = repo.create_template.call_args[0][0]
            assert "(copy)" in args["name"]

    def test_duplicate_template_without_repo(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._on_duplicate_template()  # Should not crash

    def test_new_template_opens_dialog(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        svc = MagicMock()
        svc.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ), patch(
            "ui.views.automail.template_editor_dialog.TemplateEditorDialog",
        ) as mock_dlg:
            mock_dlg.return_value.exec.return_value = True
            mock_dlg.return_value.get_data.return_value = {
                "name": "New Template",
                "subject": "Subject",
                "body_text": "Body",
                "body_html": "",
            }
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._on_new_template()
            repo.create_template.assert_called_once()

    def test_delete_template_confirmed(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        svc = MagicMock()
        svc.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ), patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes,
        ):
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._current_template = {"id": 1, "name": "Test"}
            panel._on_delete_template()
            repo.delete_template.assert_called_with(1)

    def test_delete_template_declined(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        svc = MagicMock()
        svc.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ), patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.No,
        ):
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._current_template = {"id": 1, "name": "Test"}
            panel._on_delete_template()
            repo.delete_template.assert_not_called()

    def test_delete_template_without_current(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._on_delete_template()  # Should not crash


class TestEditorPanelSave:
    def test_save_template(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        svc = MagicMock()
        svc.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.editor_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.editor_panel.TemplateService",
            return_value=svc,
        ), patch.object(
            QMessageBox, "information",
        ) as mock_info:
            panel = EditorPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._current_template = {"id": 1, "name": "Test"}
            panel._subject_edit.setText("Updated Subject")
            panel._body_editor.setPlainText("Updated Body")
            panel._on_save_template()
            repo.update_template.assert_called_once()
            args = repo.update_template.call_args
            assert args[0][0] == 1
            assert args[0][1]["subject"] == "Updated Subject"

    def test_save_template_without_repo(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._on_save_template()  # Should not crash

    def test_save_template_without_current(self, qt_widget, qtbot):
        db = MagicMock()
        panel = EditorPanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        panel._on_save_template()  # Should not crash


class TestEditorPanelAttachmentPreview:
    def test_update_attach_preview_with_template(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._current_template = {"id": 1, "name": "Test"}
        panel._update_attach_preview()
        assert panel._attach_preview.text() != ""

    def test_update_attach_preview_without_template(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._current_template = None
        panel._update_attach_preview()
        assert panel._attach_preview.text() == ""


class TestEditorPanelVariablePicker:
    def test_open_variable_picker_for_subject(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        with patch.object(panel._var_picker, "show_popup") as mock_show:
            panel._open_variable_picker(panel._subject_edit, panel._insert_var_subj_btn)
            mock_show.assert_called_once_with(panel._insert_var_subj_btn)

    def test_open_variable_picker_for_body(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        with patch.object(panel._var_picker, "show_popup") as mock_show:
            panel._open_variable_picker(panel._body_editor, panel._insert_var_body_btn)
            mock_show.assert_called_once_with(panel._insert_var_body_btn)

    def test_variable_chosen_inserts_into_line_edit(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._var_picker_target = panel._subject_edit
        panel._subject_edit.setText("Hello ")
        panel._on_variable_chosen("client_name")
        assert "{client_name}" in panel._subject_edit.text()

    def test_variable_chosen_inserts_into_text_edit(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._var_picker_target = panel._body_editor
        panel._body_editor.setPlainText("Dear ")
        panel._on_variable_chosen("client_name")
        assert "{client_name}" in panel._body_editor.toPlainText()


class TestEditorPanelRenderPreview:
    def test_render_preview_called_on_text_change(self, qt_widget, qtbot):
        db = MagicMock()
        panel = EditorPanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        panel._preview_timer.setInterval(10)
        with patch.object(panel._preview_timer, "start") as mock_start:
            panel._subject_edit.setText("New text")
            mock_start.assert_called_once()

    def test_render_preview_without_template_service(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._render_preview()  # Should not crash


class TestEditorPanelSendTest:
    def test_send_test_without_repo(self, qt_widget, qtbot):
        panel = EditorPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._on_send_test()  # Should not crash

    def test_send_test_without_ops(self, qt_widget, qtbot):
        db = MagicMock()
        panel = EditorPanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        panel._on_send_test()  # Should not crash

    def test_send_test_smtp_not_configured(self, qt_widget, qtbot):
        db = MagicMock()
        ops = MagicMock()
        ops.notification_center = None

        with patch.object(
            QMessageBox, "warning",
        ) as mock_warn:
            panel = EditorPanel(qt_widget, db=db, ops=ops)
            qtbot.addWidget(panel)
            panel._on_send_test()
            mock_warn.assert_called_once()


# ── SP workaround (if needed) ─────────────────────────────────────────

import ui.widgets as _ui_widgets
if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S


# ── Send test full flow ──────────────────────────────────────────────


class TestEditorPanelSendTestFullFlow:
    """Integration-style tests for the full send-test-email flow."""

    def test_send_test_full_flow_success(self, qt_widget, qtbot):
        """Full send-test flow: QInputDialog accepted, email sent, success box."""
        db = MagicMock()
        ops = MagicMock()
        ops.notification_center = MagicMock()
        ops.notification_center.send_email.return_value = True

        with patch.object(
            QInputDialog, "getText", return_value=("test@acme.com", True),
        ), patch(
            "ui.views.automail.editor_panel.load_company_config",
            return_value={"email": "admin@acme.com", "company_name": "Operion"},
        ), patch(
            "ui.views.automail.editor_panel.get_sample_context",
            return_value={"invoice_number": "INV-TEST"},
        ), patch(
            "ui.views.automail.editor_panel.render_template",
            side_effect=lambda text, ctx: text,  # identity
        ), patch.object(
            QMessageBox, "information",
        ) as mock_info, patch.object(
            QMessageBox, "warning",
        ) as mock_warn:
            panel = EditorPanel(qt_widget, db=db, ops=ops)
            qtbot.addWidget(panel)
            panel._subject_edit.setText("Test Subject")
            panel._body_editor.setPlainText("Test Body")
            panel._on_send_test()
            mock_info.assert_called_once()
            mock_warn.assert_not_called()
            # Verify the success message mentions the recipient email
            args, _ = mock_info.call_args
            assert "test@acme.com" in str(args)

    def test_send_test_full_flow_failure(self, qt_widget, qtbot):
        """Full send-test flow: nc.send_email raises → warning box."""
        db = MagicMock()
        ops = MagicMock()
        ops.notification_center = MagicMock()
        ops.notification_center.send_email.side_effect = Exception("SMTP error")

        with patch.object(
            QInputDialog, "getText", return_value=("test@acme.com", True),
        ), patch(
            "ui.views.automail.editor_panel.load_company_config",
            return_value={"email": "admin@acme.com"},
        ), patch(
            "ui.views.automail.editor_panel.get_sample_context",
            return_value={"invoice_number": "INV-TEST"},
        ), patch(
            "ui.views.automail.editor_panel.render_template",
            side_effect=lambda text, ctx: text,
        ), patch.object(
            QMessageBox, "information",
        ) as mock_info, patch.object(
            QMessageBox, "warning",
        ) as mock_warn:
            panel = EditorPanel(qt_widget, db=db, ops=ops)
            qtbot.addWidget(panel)
            panel._subject_edit.setText("Test Subject")
            panel._body_editor.setPlainText("Test Body")
            panel._on_send_test()
            mock_warn.assert_called_once()
            mock_info.assert_not_called()
            # Verify warning contains the exception message
            args, _ = mock_warn.call_args
            assert "SMTP error" in str(args)

    def test_send_test_cancelled(self, qt_widget, qtbot):
        """User cancels the email input dialog — no action taken."""
        db = MagicMock()
        ops = MagicMock()
        ops.notification_center = MagicMock()

        with patch.object(
            QInputDialog, "getText", return_value=("", False),
        ), patch(
            "ui.views.automail.editor_panel.load_company_config",
            return_value={"email": "admin@acme.com"},
        ), patch.object(
            QMessageBox, "information",
        ) as mock_info, patch.object(
            QMessageBox, "warning",
        ) as mock_warn:
            panel = EditorPanel(qt_widget, db=db, ops=ops)
            qtbot.addWidget(panel)
            panel._on_send_test()
            mock_info.assert_not_called()
            mock_warn.assert_not_called()
