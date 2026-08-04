"""Schedule editor dialog — create or edit a reminder schedule entry.

Used by :class:`ConfigPanel` when the user hits "Add Reminder" or
clicks "Edit" on an existing schedule card.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_BG_ELEVATED,
    COLOR_TEXT_SECONDARY,
    RADIUS_LG,
    SP,
    SPACE_4,
    SPACE_5,
    SPACE_6,
)

logger = logging.getLogger(__name__)

_TRIGGER_OPTIONS = [
    ("days_before_due", "Days Before Due Date"),
    ("on_due_date",     "On Due Date"),
    ("days_after_due",  "Days After Due Date"),
]


class ScheduleEditorDialog(QDialog):
    """Modal dialog for adding or editing a reminder schedule entry."""

    def __init__(
        self,
        parent: QWidget | None = None,
        templates: Optional[list[dict[str, Any]]] = None,
        schedule: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialise.

        Args:
            parent: Parent widget.
            templates: List of template dicts for the template selector.
            schedule: Existing schedule dict for edit mode (None = create mode).
        """
        super().__init__(parent)
        self._schedule = schedule
        self._templates = templates or []

        self.setWindowTitle(
            t("automail.edit_schedule", "Edit Reminder")
            if schedule
            else t("automail.add_schedule", "Add Reminder")
        )
        self.setMinimumWidth(480)
        self.setModal(True)
        self.setStyleSheet(
            f"QDialog {{ background: {COLOR_BG_ELEVATED}; border-radius: {RADIUS_LG}px; }}"
        )

        self._build_ui()
        if schedule:
            self._populate(schedule)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_6)
        layout.setSpacing(SPACE_4)

        form = QFormLayout()
        form.setSpacing(SPACE_4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Name
        from ui.widgets import StyledLineEdit
        self._name_edit = StyledLineEdit(self, placeholder="e.g. Day 27 Reminder")
        form.addRow(t("common.name", "Name") + ":", self._name_edit)

        # Trigger type
        self._trigger_combo = QComboBox(self)
        for value, label in _TRIGGER_OPTIONS:
            self._trigger_combo.addItem(t(f"automail.trigger_{value}", label), value)
        self._trigger_combo.currentIndexChanged.connect(self._on_trigger_changed)
        form.addRow(t("automail.trigger_type", "Trigger") + ":", self._trigger_combo)

        # Days offset
        self._days_spin = QSpinBox(self)
        self._days_spin.setRange(0, 365)
        self._days_spin.setValue(3)
        self._days_spin.valueChanged.connect(self._update_preview)
        form.addRow(t("automail.days_offset", "Days") + ":", self._days_spin)

        # Preview label (shows human-readable timing)
        self._preview_label = QLabel("", self)
        self._preview_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-style: italic; font-size: 11px;")
        form.addRow("", self._preview_label)
        self._update_preview()

        # Template selector
        self._template_combo = QComboBox(self)
        for tpl in self._templates:
            self._template_combo.addItem(tpl.get("name", "?"), tpl.get("id"))
        form.addRow(t("automail.template", "Template") + ":", self._template_combo)

        # Attachments
        attach_label = QLabel(t("automail.attachments", "Attachments"))
        attach_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(attach_label)

        attach_layout = QHBoxLayout()
        attach_layout.setSpacing(SPACE_4)
        self._attach_invoice = QCheckBox(t("automail.attach_invoice", "Invoice PDF"), self)
        self._attach_invoice.setChecked(True)
        self._attach_cmr = QCheckBox(t("automail.attach_cmr", "Signed CMR"), self)
        self._attach_cmr.setChecked(True)
        self._attach_all = QCheckBox(t("automail.attach_all_docs", "All Trip Documents"), self)
        attach_layout.addWidget(self._attach_invoice)
        attach_layout.addWidget(self._attach_cmr)
        attach_layout.addWidget(self._attach_all)
        layout.addLayout(attach_layout)

        # Active
        self._active_cb = QCheckBox(t("automail.active", "Active"), self)
        self._active_cb.setChecked(True)
        layout.addWidget(self._active_cb)

        layout.addStretch()

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, schedule: dict[str, Any]) -> None:
        """Fill fields from an existing schedule."""
        self._name_edit.setText(schedule.get("name", ""))
        trigger = schedule.get("trigger_type", "days_before_due")
        idx = self._trigger_combo.findData(trigger)
        if idx >= 0:
            self._trigger_combo.setCurrentIndex(idx)
        self._days_spin.setValue(schedule.get("days_offset", 3))
        tpl_id = schedule.get("template_id")
        if tpl_id is not None:
            idx = self._template_combo.findData(tpl_id)
            if idx >= 0:
                self._template_combo.setCurrentIndex(idx)
        self._attach_invoice.setChecked(bool(schedule.get("attach_invoice", 1)))
        self._attach_cmr.setChecked(bool(schedule.get("attach_cmr", 1)))
        self._attach_all.setChecked(bool(schedule.get("attach_all_docs", 0)))
        self._active_cb.setChecked(bool(schedule.get("is_active", 1)))
        self._update_preview()

    def _on_trigger_changed(self) -> None:
        self._update_preview()

    def _update_preview(self) -> None:
        """Update the human-readable timing preview."""
        trigger = self._trigger_combo.currentData() or "days_before_due"
        days = self._days_spin.value()
        if trigger == "days_before_due":
            text = f"Will be sent {days} day(s) BEFORE the due date"
        elif trigger == "days_after_due":
            text = f"Will be sent {days} day(s) AFTER the due date"
        else:
            text = "Will be sent ON the due date"
        self._preview_label.setText(text)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, t("common.error", "Error"),
                                t("automail.name_required", "Schedule name is required."))
            self._name_edit.setFocus()
            return
        self.accept()

    def get_data(self) -> dict[str, Any]:
        """Return the form data as a dict suitable for the repository."""
        return {
            "name": self._name_edit.text().strip(),
            "trigger_type": self._trigger_combo.currentData(),
            "days_offset": self._days_spin.value(),
            "template_id": self._template_combo.currentData(),
            "is_active": 1 if self._active_cb.isChecked() else 0,
            "attach_invoice": 1 if self._attach_invoice.isChecked() else 0,
            "attach_cmr": 1 if self._attach_cmr.isChecked() else 0,
            "attach_all_docs": 1 if self._attach_all.isChecked() else 0,
        }
