"""Right panel — HTML email editor with live preview and variable insertion.

Features:
    - Template selector (combo + CRUD buttons)
    - Subject editor with variable insertion
    - Rich HTML editor with formatting toolbar
    - Edit/Preview toggle with live sample rendering
    - Attachment preview from current schedule
    - Save Template and Send Test Email
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
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

from repositories.automail_repository import AutoMailRepository
from services.automail.template_service import TemplateService, get_sample_context, render_template
from services.i18n import t
from services.invoicing.config_manager import load_company_config
from services.operations.notification_center import NotificationCenter
from ui.components import Btn
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_NEUTRAL_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_REGULAR,
    RADIUS_LG,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
)

logger = logging.getLogger(__name__)


class _FormatToolbar(QFrame):
    """Rich text formatting toolbar (Bold, Italic, Underline, lists)."""

    def __init__(self, parent: QWidget, editor: QTextEdit) -> None:
        super().__init__(parent)
        self._editor = editor
        self.setStyleSheet(
            f"background: {COLOR_BG_OVERLAY}; border-bottom: 1px solid {COLOR_BORDER_SUBTLE};"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_2, SPACE_2, SPACE_2, SPACE_2)
        layout.setSpacing(SPACE_2)

        def _make_btn(text: str, tooltip: str, command) -> QToolButton:
            btn = QToolButton(self)
            btn.setText(text)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.clicked.connect(command)
            btn.setStyleSheet(
                f"QToolButton {{ background: transparent; color: {COLOR_TEXT_SECONDARY}; "
                f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 12px; }}"
                f"QToolButton:hover {{ background: {COLOR_BG_HOVER}; color: {COLOR_TEXT_PRIMARY}; }}"
                f"QToolButton:checked {{ background: {COLOR_ACCENT_SUBTLE}; color: {COLOR_ACCENT_PRIMARY}; }}"
            )
            return btn

        self._bold_btn = _make_btn("B", "Bold (Ctrl+B)", self._toggle_bold)
        self._bold_btn.setStyleSheet(self._bold_btn.styleSheet() + "font-weight: bold;")
        layout.addWidget(self._bold_btn)

        self._italic_btn = _make_btn("I", "Italic (Ctrl+I)", self._toggle_italic)
        self._italic_btn.setStyleSheet(self._italic_btn.styleSheet() + "font-style: italic;")
        layout.addWidget(self._italic_btn)

        self._underline_btn = _make_btn("U", "Underline (Ctrl+U)", self._toggle_underline)
        self._underline_btn.setStyleSheet(self._underline_btn.styleSheet() + "text-decoration: underline;")
        layout.addWidget(self._underline_btn)

        layout.addWidget(QLabel("|", self))

        self._ul_btn = _make_btn("• List", "Unordered List", self._insert_unordered_list)
        layout.addWidget(self._ul_btn)

        self._ol_btn = _make_btn("1. List", "Ordered List", self._insert_ordered_list)
        layout.addWidget(self._ol_btn)

        layout.addStretch()

        # Sync button states with cursor position
        editor.cursorPositionChanged.connect(self._sync_buttons)

    def _sync_buttons(self) -> None:
        """Update toolbar button checked states from current char format."""
        fmt = self._editor.textCursor().charFormat()
        self._bold_btn.setChecked(fmt.fontWeight() >= QFont.Weight.Bold)
        self._italic_btn.setChecked(fmt.fontItalic())
        self._underline_btn.setChecked(fmt.fontUnderline())

    def _toggle_bold(self) -> None:
        cursor = self._editor.textCursor()
        fmt = cursor.charFormat()
        is_bold = fmt.fontWeight() >= QFont.Weight.Bold
        fmt.setFontWeight(QFont.Weight.Normal if is_bold else QFont.Weight.Bold)
        cursor.mergeCharFormat(fmt)
        self._editor.setTextCursor(cursor)
        self._editor.setFocus()

    def _toggle_italic(self) -> None:
        cursor = self._editor.textCursor()
        fmt = cursor.charFormat()
        italic = not fmt.fontItalic()
        fmt.setFontItalic(italic)
        cursor.mergeCharFormat(fmt)
        self._editor.setTextCursor(cursor)
        self._editor.setFocus()

    def _toggle_underline(self) -> None:
        cursor = self._editor.textCursor()
        fmt = cursor.charFormat()
        uline = not fmt.fontUnderline()
        fmt.setFontUnderline(uline)
        cursor.mergeCharFormat(fmt)
        self._editor.setTextCursor(cursor)
        self._editor.setFocus()

    def _insert_unordered_list(self) -> None:
        cursor = self._editor.textCursor()
        cursor.insertHtml("<ul><li>Item</li></ul>")
        self._editor.setFocus()

    def _insert_ordered_list(self) -> None:
        cursor = self._editor.textCursor()
        cursor.insertHtml("<ol><li>Item</li></ol>")
        self._editor.setFocus()


class EditorPanel(QFrame):
    """Right panel: email template editor with HTML toolbar and live preview."""

    templates_changed = Signal()

    def __init__(
        self,
        parent: QWidget,
        db=None,
        prefs=None,
        ops=None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._prefs = prefs
        self._ops = ops
        self._repo = AutoMailRepository(db) if db else None
        self._template_service = TemplateService(db) if db else None

        self._current_template: Optional[dict[str, Any]] = None
        self._preview_mode = False

        self.setProperty("role", "automail-editor-panel")
        self.setStyleSheet(f"background: {COLOR_BG_ELEVATED}; border-radius: {RADIUS_LG}px;")

        self._build_ui()

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget(scroll)
        content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(SPACE_4, SPACE_4, SPACE_4, SPACE_4)
        self._content_layout.setSpacing(SPACE_3)
        scroll.setWidget(content)

        layout.addWidget(scroll, 1)

        # ── Template selector ───────────────────────────────────────
        selector_row = QHBoxLayout()
        selector_row.setSpacing(SPACE_2)
        self._template_combo = QComboBox(content)
        self._template_combo.setMinimumWidth(160)
        self._template_combo.currentIndexChanged.connect(self._on_template_selected)
        selector_row.addWidget(self._template_combo, 1)

        self._edit_tpl_btn = Btn(content, text=t("common.edit", "Edit"),
                                 variant="ghost", size="sm",
                                 command=self._on_edit_template)
        selector_row.addWidget(self._edit_tpl_btn)

        self._dup_tpl_btn = Btn(content, text=t("common.duplicate", "Dup"),
                                variant="ghost", size="sm",
                                command=self._on_duplicate_template)
        selector_row.addWidget(self._dup_tpl_btn)

        self._new_tpl_btn = Btn(content, text=t("common.new", "New"),
                                variant="primary", size="sm",
                                command=self._on_new_template)
        selector_row.addWidget(self._new_tpl_btn)

        self._del_tpl_btn = Btn(content, text=t("common.delete", "Del"),
                                variant="ghost", size="sm",
                                command=self._on_delete_template)
        selector_row.addWidget(self._del_tpl_btn)

        self._content_layout.addLayout(selector_row)

        # ── Subject editor ──────────────────────────────────────────
        subject_header = QHBoxLayout()
        subject_header.setSpacing(SPACE_2)
        subj_label = QLabel(t("automail.subject", "Subject") + ":", content)
        subj_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: {FONT_WEIGHT_MEDIUM};")
        subject_header.addWidget(subj_label)

        self._insert_var_subj_btn = Btn(
            content, text=t("automail.insert_variable", "{{ Var }}"),
            variant="ghost", size="sm",
            command=lambda: self._open_variable_picker(self._subject_edit, self._insert_var_subj_btn),
        )
        subject_header.addWidget(self._insert_var_subj_btn)
        subject_header.addStretch()
        self._content_layout.addLayout(subject_header)

        self._subject_edit = QLineEdit(content)
        self._subject_edit.setStyleSheet(
            f"background: {COLOR_BG_OVERLAY}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: 6px; "
            f"padding: 8px 10px; font-size: 12px;"
        )
        self._subject_edit.textChanged.connect(self._schedule_preview_update)
        self._content_layout.addWidget(self._subject_edit)

        # ── Body editor ─────────────────────────────────────────────
        body_header = QHBoxLayout()
        body_header.setSpacing(SPACE_2)
        body_label = QLabel(t("automail.body", "Body"), content)
        body_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: {FONT_WEIGHT_MEDIUM};")
        body_header.addWidget(body_label)

        self._insert_var_body_btn = Btn(
            content, text=t("automail.insert_variable", "{{ Var }}"),
            variant="ghost", size="sm",
            command=lambda: self._open_variable_picker(self._body_editor, self._insert_var_body_btn),
        )
        body_header.addWidget(self._insert_var_body_btn)

        body_header.addStretch()

        self._preview_toggle_btn = Btn(
            content, text=t("automail.preview", "Preview"),
            variant="secondary", size="sm",
            command=self._toggle_preview,
        )
        body_header.addWidget(self._preview_toggle_btn)

        self._content_layout.addLayout(body_header)

        # Format toolbar
        self._body_editor = QTextEdit(content)
        self._body_editor.setAcceptRichText(True)
        self._body_editor.setStyleSheet(
            f"background: {COLOR_BG_OVERLAY}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: 6px; "
            f"padding: 8px; font-size: 12px;"
        )
        self._body_editor.setMinimumHeight(200)
        self._body_editor.textChanged.connect(self._schedule_preview_update)
        self._content_layout.addWidget(self._body_editor)

        self._format_toolbar = _FormatToolbar(content, self._body_editor)
        self._content_layout.addWidget(self._format_toolbar)

        # ── Preview (hidden until toggled) ──────────────────────────
        self._preview_widget = QTextEdit(content)
        self._preview_widget.setReadOnly(True)
        self._preview_widget.setStyleSheet(
            f"background: {COLOR_BG_OVERLAY}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: 6px; "
            f"padding: 8px; font-size: 12px;"
        )
        self._preview_widget.setMinimumHeight(200)
        self._preview_widget.hide()
        self._content_layout.addWidget(self._preview_widget)

        # Debounce timer for preview
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(500)
        self._preview_timer.timeout.connect(self._render_preview)

        # ── Attachment preview ──────────────────────────────────────
        self._attach_preview = QLabel(content)
        self._attach_preview.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;")
        self._content_layout.addWidget(self._attach_preview)

        # ── Actions ─────────────────────────────────────────────────
        actions = QHBoxLayout()
        actions.setSpacing(SPACE_2)

        self._save_btn = Btn(content, text=t("common.save", "Save Template"),
                             variant="primary", command=self._on_save_template)
        actions.addWidget(self._save_btn)

        self._test_btn = Btn(content, text=t("automail.send_test", "Send Test"),
                             variant="secondary", command=self._on_send_test)
        actions.addWidget(self._test_btn)

        actions.addStretch()
        self._content_layout.addLayout(actions)

        self._content_layout.addStretch()

        # Variable picker popup
        from ui.views.automail.variable_picker import VariablePickerPopup
        self._var_picker = VariablePickerPopup(self)
        self._var_picker.variable_chosen.connect(self._on_variable_chosen)

    # ── Data loading ───────────────────────────────────────────────

    def wakeup(self) -> None:
        self._load_templates()

    def _load_templates(self) -> None:
        if self._repo is None or self._template_service is None:
            return

        templates = self._template_service.get_all_templates()

        # Preserve current selection if possible
        current_id = None
        if self._current_template:
            current_id = self._current_template.get("id")

        self._template_combo.blockSignals(True)
        self._template_combo.clear()
        for tpl in templates:
            self._template_combo.addItem(tpl.get("name", "?"), tpl.get("id"))
        self._template_combo.blockSignals(False)

        if current_id is not None:
            idx = self._template_combo.findData(current_id)
            if idx >= 0:
                self._template_combo.setCurrentIndex(idx)

        if self._template_combo.count() > 0:
            self._on_template_selected(0)

    def _on_template_selected(self, index: int) -> None:
        if self._repo is None or index < 0:
            return
        template_id = self._template_combo.itemData(index)
        if template_id is None:
            return
        tpl = self._repo.get_template_by_id(template_id)
        if not tpl:
            return
        self._current_template = tpl
        self._subject_edit.blockSignals(True)
        self._body_editor.blockSignals(True)

        self._subject_edit.setText(tpl.get("subject", ""))
        body_html = tpl.get("body_html", "") or ""
        body_text = tpl.get("body_text", "") or ""
        if body_html.strip():
            self._body_editor.setHtml(body_html)
        else:
            self._body_editor.setPlainText(body_text)

        self._subject_edit.blockSignals(False)
        self._body_editor.blockSignals(False)
        self._update_attach_preview()
        self._render_preview()

    # ── Template CRUD ───────────────────────────────────────────────

    def _on_edit_template(self) -> None:
        if not self._current_template:
            return
        tpl_id = self._current_template["id"]
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog
        dlg = TemplateEditorDialog(self, template=self._current_template)
        if dlg.exec():
            data = dlg.get_data()
            if self._repo:
                self._repo.update_template(tpl_id, data)
                self._load_templates()
                self.templates_changed.emit()

    def _on_duplicate_template(self) -> None:
        if self._repo is None or not self._current_template:
            return
        tpl = self._current_template
        name = (tpl.get("name", "") or "") + " (copy)"
        data = {
            "name": name,
            "subject": tpl.get("subject", ""),
            "body_text": tpl.get("body_text", ""),
            "body_html": tpl.get("body_html", ""),
        }
        self._repo.create_template(data)
        self._load_templates()
        self.templates_changed.emit()

    def _on_new_template(self) -> None:
        if self._repo is None:
            return
        from ui.views.automail.template_editor_dialog import TemplateEditorDialog
        dlg = TemplateEditorDialog(self, template=None)
        if dlg.exec():
            data = dlg.get_data()
            self._repo.create_template(data)
            self._load_templates()
            self.templates_changed.emit()

    def _on_delete_template(self) -> None:
        if self._repo is None or not self._current_template:
            return
        reply = QMessageBox.question(
            self, t("common.confirm", "Confirm"),
            t("automail.confirm_delete_template", "Delete this template?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._repo.delete_template(self._current_template["id"])
        self._current_template = None
        self._load_templates()
        self.templates_changed.emit()

    # ── Variable picker ─────────────────────────────────────────────

    def _open_variable_picker(self, target_field: QWidget, anchor_btn: QWidget) -> None:
        self._var_picker_target = target_field
        self._var_picker.show_popup(anchor_btn)

    def _on_variable_chosen(self, var_name: str) -> None:
        if hasattr(self, "_var_picker_target") and self._var_picker_target:
            target = self._var_picker_target
            text = f"{{{var_name}}}"
            if isinstance(target, QLineEdit):
                cursor_pos = target.cursorPosition()
                current = target.text()
                target.setText(current[:cursor_pos] + text + current[cursor_pos:])
                target.setCursorPosition(cursor_pos + len(text))
            elif isinstance(target, QTextEdit):
                cursor = target.textCursor()
                cursor.insertText(text)
                target.setTextCursor(cursor)

    # ── Preview ─────────────────────────────────────────────────────

    def _schedule_preview_update(self) -> None:
        self._preview_timer.start()

    def _toggle_preview(self) -> None:
        self._preview_mode = not self._preview_mode
        if self._preview_mode:
            self._body_editor.hide()
            self._format_toolbar.hide()
            self._preview_widget.show()
            self._preview_toggle_btn.setText(t("automail.edit", "Edit"))
            self._render_preview()
        else:
            self._preview_widget.hide()
            self._body_editor.show()
            self._format_toolbar.show()
            self._preview_toggle_btn.setText(t("automail.preview", "Preview"))

    def _render_preview(self) -> None:
        if self._template_service is None:
            return

        ctx = get_sample_context()

        subject = self._subject_edit.text()
        subject_rendered = render_template(subject, ctx)
        self._subject_edit.setToolTip(
            t("automail.rendered_subject", "Rendered: {subject}").replace("{subject}", subject_rendered)
        )

        if self._preview_mode:
            body_html = (self._current_template or {}).get("body_html", "") or ""
            body_text = (self._current_template or {}).get("body_text", "") or ""
            content = body_html if body_html.strip() else body_text
            body_rendered = render_template(content, ctx)

            watermark = (
                '<div style="padding:8px;margin-bottom:12px;border:1px dashed #555;'
                'border-radius:6px;color:#888;font-style:italic;font-size:11px;'
                'text-align:center;">Preview with sample data</div>'
            )
            self._preview_widget.setHtml(watermark + body_rendered)
        else:
            body_rendered = self._body_editor.toHtml()
            body_rendered = render_template(body_rendered, ctx)
            self._preview_widget.setHtml(
                '<div style="padding:8px;margin-bottom:12px;border:1px dashed #555;'
                'border-radius:6px;color:#888;font-style:italic;font-size:11px;'
                'text-align:center;">Live preview (variables resolved with sample data)</div>'
                + body_rendered
            )

    # ── Attachment preview ──────────────────────────────────────────

    def _update_attach_preview(self) -> None:
        if self._current_template:
            self._attach_preview.setText(
                t("automail.attach_preview", "Attachments: Invoice PDF ✓ | Signed CMR ✓")
            )
        else:
            self._attach_preview.setText("")

    # ── Save ────────────────────────────────────────────────────────

    def _on_save_template(self) -> None:
        if self._repo is None or not self._current_template:
            return
        tpl_id = self._current_template["id"]
        body_text = self._body_editor.toPlainText()
        subject = self._subject_edit.text()
        self._repo.update_template(tpl_id, {
            "subject": subject,
            "body_text": body_text,
            "body_html": self._body_editor.toHtml(),
        })
        self._current_template["subject"] = subject
        self._current_template["body_text"] = body_text
        self._current_template["body_html"] = self._body_editor.toHtml()
        QMessageBox.information(
            self, t("common.success", "Success"),
            t("automail.template_saved", "Template saved."),
        )

    # ── Send test ───────────────────────────────────────────────────

    def _on_send_test(self) -> None:
        if self._repo is None or self._ops is None:
            return
        nc = self._ops.notification_center
        if not nc:
            QMessageBox.warning(
                self, t("common.error", "Error"),
                t("automail.smtp_not_configured", "SMTP not configured. Please configure email settings first."),
            )
            return

        test_email, ok = QInputDialog.getText(
            self, t("automail.send_test", "Send Test"),
            t("automail.test_email_address", "Recipient email:"),
            text=load_company_config().get("email", ""),
        )
        if not ok or not test_email:
            return

        if self._template_service is None:
            return

        subject = self._subject_edit.text()
        body_html = self._body_editor.toHtml() if self._body_editor.isVisible() else ""
        body_text = self._body_editor.toPlainText()

        ctx = get_sample_context()
        from services.automail.template_service import render_template
        subject_rendered = render_template(subject, ctx)
        body_rendered = render_template(body_html if body_html.strip() else body_text, ctx)

        try:
            nc.send_email(
                to_address=test_email,
                subject=subject_rendered,
                body=body_rendered,
                html=bool(body_html.strip()),
            )
            QMessageBox.information(
                self, t("common.success", "Success"),
                t("automail.test_sent", "Test email sent to {email}.").replace("{email}", test_email),
            )
        except Exception as exc:
            QMessageBox.warning(
                self, t("common.error", "Error"),
                str(exc),
            )
