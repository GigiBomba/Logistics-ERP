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
from ui.design_tokens import SPACE_4, SPACE_6
from ui.widgets import StyledLineEdit

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
        subj_label.setProperty("fontRole", "sm-secondary")
        layout.addWidget(subj_label)

        self._subject_edit = QLineEdit(self)
        self._subject_edit.setAccessibleName("Template subject")
        self._subject_edit.setProperty("role", "panel-input")
        layout.addWidget(self._subject_edit)

        # Body
        body_label = QLabel(t("automail.body", "Body") + ":", self)
        body_label.setProperty("fontRole", "sm-secondary")
        layout.addWidget(body_label)

        self._body_editor = QTextEdit(self)
        self._body_editor.setAccessibleName("Template body")
        self._body_editor.setAcceptRichText(True)
        self._body_editor.setProperty("role", "panel-input")
        self._body_editor.setMinimumHeight(200)
        layout.addWidget(self._body_editor, 1)

        # Variable reference
        vars_label = QLabel(
            t("automail.available_vars", "Available variables:") + " " +
            ", ".join(f"{{{v['name']}}}" for v in get_available_variables()),
            self,
        )
        vars_label.setWordWrap(True)
        vars_label.setProperty("fontRole", "xs-muted")
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
