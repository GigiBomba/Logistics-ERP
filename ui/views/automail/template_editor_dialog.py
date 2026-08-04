"""Template editor dialog — edit email template subject, body, and HTML.

Used by :class:`EditorPanel` when the user clicks "Edit" on a template.
Provides a full rich-text editor with live preview.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services.automail.template_service import get_available_variables, render_template
from services.i18n import t
from ui.design_tokens import RADIUS_LG
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_6,
)

logger = logging.getLogger(__name__)


class TemplateEditorDialog(QDialog):
    """Modal dialog for editing an email template."""

    def __init__(
        self,
        parent: QWidget | None = None,
        template: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(parent)
        self.setAccessibleName("Template editor")
        self.setAccessibleDescription("Dialog for editing email templates")
        self._template = template

        self.setWindowTitle(
            t("automail.edit_template", "Edit Template")
            if template
            else t("automail.new_template", "New Template")
        )
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setModal(True)
        self.setStyleSheet(
            f"QDialog {{ background: {COLOR_BG_ELEVATED}; border-radius: {RADIUS_LG}px; }}"
        )

        self._build_ui()
        if template:
            self._populate(template)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_4)

        # Name
        form = QFormLayout()
        form.setSpacing(SPACE_4)

        from ui.widgets import StyledLineEdit
        self._name_edit = StyledLineEdit(self, placeholder="e.g. Professional Reminder")
        self._name_edit.setAccessibleName("Template name")
        form.addRow(t("common.name", "Name") + ":", self._name_edit)
        layout.addLayout(form)

        # Subject
        subj_label = QLabel(t("automail.subject", "Subject") + ":", self)
        subj_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(subj_label)

        self._subject_edit = QLineEdit(self)
        self._subject_edit.setAccessibleName("Template subject")
        self._subject_edit.setStyleSheet(
            f"background: {COLOR_BG_OVERLAY}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: 6px; "
            f"padding: 8px 10px; font-size: 12px;"
        )
        layout.addWidget(self._subject_edit)

        # Body
        body_label = QLabel(t("automail.body", "Body") + ":", self)
        body_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(body_label)

        self._body_editor = QTextEdit(self)
        self._body_editor.setAccessibleName("Template body")
        self._body_editor.setAcceptRichText(True)
        self._body_editor.setStyleSheet(
            f"background: {COLOR_BG_OVERLAY}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: 6px; "
            f"padding: 8px; font-size: 12px;"
        )
        self._body_editor.setMinimumHeight(200)
        layout.addWidget(self._body_editor, 1)

        # Variable reference
        vars_label = QLabel(
            t("automail.available_vars", "Available variables:") + " " +
            ", ".join(f"{{{v['name']}}}" for v in get_available_variables()),
            self,
        )
        vars_label.setWordWrap(True)
        vars_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;")
        layout.addWidget(vars_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        for btn in buttons.buttons():
            btn.setAccessibleName(btn.text())
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, template: dict[str, Any]) -> None:
        self._name_edit.setText(template.get("name", ""))
        self._subject_edit.setText(template.get("subject", ""))
        body_html = template.get("body_html", "") or ""
        body_text = template.get("body_text", "") or ""
        if body_html.strip():
            self._body_editor.setHtml(body_html)
        else:
            self._body_editor.setPlainText(body_text)

    def get_data(self) -> dict[str, Any]:
        """Return the form data as a dict suitable for the repository."""
        body_html = self._body_editor.toHtml()
        body_text = self._body_editor.toPlainText()
        return {
            "name": self._name_edit.text().strip(),
            "subject": self._subject_edit.text().strip(),
            "body_text": body_text,
            "body_html": body_html,
        }
