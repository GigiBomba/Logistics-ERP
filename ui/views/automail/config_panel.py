"""Left panel — automation configuration for AutoMail.

Contains:
    - Master enable/disable toggle
    - Reminder schedule list (add/edit/duplicate/delete/reorder)
    - Delivery rules (business hours, skip weekends)
    - Safety settings (max reminders, retry attempts)
    - Preset selector
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from repositories.automail_repository import AutoMailRepository
from services.i18n import t
from ui.components import Btn
from ui.widgets import SectionHeader
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_NEUTRAL_TEXT,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_TEXT,
    FONT_WEIGHT_MEDIUM,
    RADIUS_LG,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
    SPACE_8,
)

logger = logging.getLogger(__name__)


class _MasterToggle(QFrame):
    """Large enable/disable pill switch with label."""

    toggled = Signal(bool)

    def __init__(self, parent: QWidget, enabled: bool = False) -> None:
        super().__init__(parent)
        self.setProperty("role", "automail-master-toggle")
        self.setStyleSheet(
            f"background: {COLOR_BG_ELEVATED}; border: 1px solid {COLOR_BORDER_SUBTLE}; "
            f"border-radius: {RADIUS_LG}px; padding: {SPACE_4}px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_4, SPACE_5, SPACE_4)
        layout.setSpacing(SPACE_3)

        self._switch = QCheckBox(
            t("automail.enable_reminders", "Enable Automatic Payment Reminders"), self
        )
        self._switch.blockSignals(True)
        self._switch.setChecked(enabled)
        self._switch.blockSignals(False)
        self._switch.setStyleSheet(
            f"font-size: 13px; font-weight: {FONT_WEIGHT_MEDIUM}; color: {COLOR_TEXT_PRIMARY}; spacing: {SPACE_3}px;"
        )
        self._switch.stateChanged.connect(lambda st: self.toggled.emit(bool(st)))
        layout.addWidget(self._switch, 1)

    def set_checked(self, enabled: bool) -> None:
        """Set the toggle state without emitting ``toggled``."""
        self._switch.blockSignals(True)
        self._switch.setChecked(enabled)
        self._switch.blockSignals(False)


class _InlineScheduleEditor(QFrame):
    """Inline editor that appears below a schedule card when editing."""

    save_clicked = Signal(int, dict)   # (schedule_id, data)
    save_all_clicked = Signal(dict)     # data applied to ALL schedules
    cancel_clicked = Signal(int)        # schedule_id

    def __init__(
        self,
        parent: QWidget,
        schedule: dict[str, Any],
        templates: list[dict[str, Any]],
    ) -> None:
        super().__init__(parent)
        self._schedule_id = schedule["id"]
        self.setProperty("role", "inline-schedule-editor")
        self.setStyleSheet(
            f"background: {COLOR_BG_ELEVATED}; border: 1px solid {COLOR_BORDER_SUBTLE}; "
            f"border-radius: {RADIUS_LG}px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)
        layout.setSpacing(SPACE_2)

        # Name
        name_row = QHBoxLayout()
        name_row.setSpacing(SPACE_2)
        name_row.addWidget(QLabel(t("common.name", "Name") + ":", self))
        from ui.widgets import StyledLineEdit
        self._name_edit = StyledLineEdit(self, text=schedule.get("name", ""))
        name_row.addWidget(self._name_edit, 1)
        layout.addLayout(name_row)

        # Trigger + Days
        trigger_row = QHBoxLayout()
        trigger_row.setSpacing(SPACE_2)

        self._trigger_combo = QComboBox(self)
        _TRIGGER_OPTIONS = [
            ("days_before_due", "Days Before"),
            ("on_due_date", "On Due Date"),
            ("days_after_due", "Days After"),
        ]
        trigger_val = schedule.get("trigger_type", "days_before_due")
        for value, label in _TRIGGER_OPTIONS:
            self._trigger_combo.addItem(t(f"automail.trigger_{value}", label), value)
        idx = self._trigger_combo.findData(trigger_val)
        if idx >= 0:
            self._trigger_combo.setCurrentIndex(idx)
        trigger_row.addWidget(QLabel(t("automail.trigger_type", "When") + ":", self))
        trigger_row.addWidget(self._trigger_combo)

        self._days_spin = QSpinBox(self)
        self._days_spin.setRange(0, 365)
        self._days_spin.setValue(schedule.get("days_offset", 3))
        trigger_row.addWidget(QLabel(t("automail.days_offset", "Days") + ":", self))
        trigger_row.addWidget(self._days_spin)
        trigger_row.addStretch()
        layout.addLayout(trigger_row)

        # Template
        tpl_row = QHBoxLayout()
        tpl_row.setSpacing(SPACE_2)
        self._template_combo = QComboBox(self)
        for tpl in templates:
            self._template_combo.addItem(tpl.get("name", "?"), tpl.get("id"))
        tpl_id = schedule.get("template_id")
        if tpl_id is not None:
            idx = self._template_combo.findData(tpl_id)
            if idx >= 0:
                self._template_combo.setCurrentIndex(idx)
        tpl_row.addWidget(QLabel(t("automail.template", "Template") + ":", self))
        tpl_row.addWidget(self._template_combo, 1)
        layout.addLayout(tpl_row)

        # Attachments
        attach_row = QHBoxLayout()
        attach_row.setSpacing(SPACE_3)
        self._attach_invoice = QCheckBox(t("automail.attach_invoice", "Invoice"), self)
        self._attach_invoice.setChecked(bool(schedule.get("attach_invoice", 1)))
        self._attach_cmr = QCheckBox(t("automail.attach_cmr", "CMR"), self)
        self._attach_cmr.setChecked(bool(schedule.get("attach_cmr", 1)))
        self._attach_all = QCheckBox(t("automail.attach_all_docs", "All Docs"), self)
        self._attach_all.setChecked(bool(schedule.get("attach_all_docs", 0)))
        attach_row.addWidget(self._attach_invoice)
        attach_row.addWidget(self._attach_cmr)
        attach_row.addWidget(self._attach_all)
        self._active_cb = QCheckBox(t("automail.active", "Active"), self)
        self._active_cb.setChecked(bool(schedule.get("is_active", 1)))
        attach_row.addWidget(self._active_cb)
        attach_row.addStretch()
        layout.addLayout(attach_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACE_2)

        self._save_btn = QPushButton(t("common.save", "Save"), self)
        self._save_btn.setFixedHeight(28)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_ACCENT_PRIMARY}; color: #FFFFFF;
                border: none; border-radius: 4px; font-size: 11px; font-weight: 600;
                padding: 0 12px;
            }}
            QPushButton:hover {{ background: {COLOR_ACCENT_PRIMARY}CC; }}
        """)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        self._save_all_btn = QPushButton(
            t("automail.save_all", "Save for All"), self
        )
        self._save_all_btn.setFixedHeight(28)
        self._save_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_BG_OVERLAY}; color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_ACCENT_PRIMARY}; border-radius: 4px;
                font-size: 11px; font-weight: 600; padding: 0 12px;
            }}
            QPushButton:hover {{ background: {COLOR_BG_HOVER}; }}
        """)
        self._save_all_btn.clicked.connect(self._on_save_all)
        btn_row.addWidget(self._save_all_btn)

        self._cancel_btn = QPushButton(t("common.cancel", "Cancel"), self)
        self._cancel_btn.setFixedHeight(28)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: 4px;
                font-size: 11px; padding: 0 12px;
            }}
            QPushButton:hover {{ background: {COLOR_BG_HOVER}; color: {COLOR_TEXT_PRIMARY}; }}
        """)
        self._cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self._schedule_id))
        btn_row.addWidget(self._cancel_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _collect_data(self) -> dict[str, Any]:
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

    def _on_save(self) -> None:
        data = self._collect_data()
        if not data["name"]:
            QMessageBox.warning(self, t("common.error", "Error"),
                                t("automail.name_required", "Name is required."))
            return
        self.save_clicked.emit(self._schedule_id, data)

    def _on_save_all(self) -> None:
        data = self._collect_data()
        if not data["name"]:
            QMessageBox.warning(self, t("common.error", "Error"),
                                t("automail.name_required", "Name is required."))
            return
        self.save_all_clicked.emit(data)


class _ScheduleCard(QFrame):
    """A single reminder schedule entry card."""

    edit_clicked = Signal(int)
    duplicate_clicked = Signal(int)
    delete_clicked = Signal(int)
    move_up = Signal(int)
    move_down = Signal(int)
    active_toggled = Signal(int, bool)

    def __init__(self, parent: QWidget, schedule: dict[str, Any], is_first: bool, is_last: bool) -> None:
        super().__init__(parent)
        self._schedule_id = schedule["id"]
        self.setProperty("role", "schedule-card")
        self.setStyleSheet(
            f"background: {COLOR_BG_OVERLAY}; border: 1px solid {COLOR_BORDER_SUBTLE}; "
            f"border-radius: {RADIUS_LG}px; padding: {SPACE_3}px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)
        layout.setSpacing(SPACE_2)

        # Top row: timing label + active toggle
        top = QHBoxLayout()
        top.setSpacing(SPACE_3)
        timing_text = self._format_timing(schedule)
        self._timing_lbl = QLabel(timing_text, self)
        timing_color = COLOR_ACCENT_PRIMARY if schedule.get("is_active") else COLOR_TEXT_TERTIARY
        self._timing_lbl.setStyleSheet(f"color: {timing_color}; font-size: 12px; font-weight: {FONT_WEIGHT_MEDIUM};")
        top.addWidget(self._timing_lbl, 1)

        self._active_switch = QCheckBox("", self)
        self._active_switch.setChecked(bool(schedule.get("is_active", 1)))
        self._active_switch.stateChanged.connect(
            lambda st: self.active_toggled.emit(self._schedule_id, bool(st))
        )
        top.addWidget(self._active_switch)
        layout.addLayout(top)

        # Template name
        tpl_name = schedule.get("template_name") or "?"
        self._tpl_lbl = QLabel(tpl_name, self)
        self._tpl_lbl.setStyleSheet(
            f"color: {COLOR_NEUTRAL_TEXT}; font-size: 11px;"
        )
        layout.addWidget(self._tpl_lbl)

        # Action buttons
        actions = QHBoxLayout()
        actions.setSpacing(SPACE_2)

        self._edit_btn = Btn(self, text=t("common.edit", "Edit"), variant="ghost", size="sm",
                             command=lambda: self.edit_clicked.emit(self._schedule_id))
        actions.addWidget(self._edit_btn)

        self._dup_btn = Btn(self, text=t("common.duplicate", "Duplicate"), variant="ghost", size="sm",
                            command=lambda: self.duplicate_clicked.emit(self._schedule_id))
        actions.addWidget(self._dup_btn)

        self._del_btn = Btn(self, text=t("common.delete", "Delete"), variant="ghost", size="sm",
                            command=lambda: self.delete_clicked.emit(self._schedule_id))
        actions.addWidget(self._del_btn)

        actions.addStretch()

        if not is_first:
            self._up_btn = Btn(self, text="↑", variant="ghost", size="sm",
                               command=lambda: self.move_up.emit(self._schedule_id))
            actions.addWidget(self._up_btn)
        if not is_last:
            self._down_btn = Btn(self, text="↓", variant="ghost", size="sm",
                                 command=lambda: self.move_down.emit(self._schedule_id))
            actions.addWidget(self._down_btn)

        layout.addLayout(actions)

    def _format_timing(self, sched: dict[str, Any]) -> str:
        trigger = sched.get("trigger_type", "")
        offset = sched.get("days_offset", 0)
        if trigger == "days_before_due":
            return t("automail.timing_before", "{n} day(s) before due date").replace("{n}", str(offset))
        elif trigger == "days_after_due":
            return t("automail.timing_after", "{n} day(s) after due date").replace("{n}", str(offset))
        else:
            return t("automail.timing_on", "On due date")


class ConfigPanel(QFrame):
    """Left configuration panel for the AutoMail tab."""

    schedules_changed = Signal()

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
        self._schedule_cards: list[_ScheduleCard] = []
        self._inline_editors: dict[int, _InlineScheduleEditor] = {}
        self._editor_containers: dict[int, QWidget] = {}

        self.setProperty("role", "automail-config-panel")
        self.setStyleSheet(f"background: {COLOR_BG_ELEVATED}; border-radius: {RADIUS_LG}px;")

        self._build_ui()
        self._load_data()

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

        # ── Master Toggle ───────────────────────────────────────────
        self._master_toggle = _MasterToggle(content)
        self._master_toggle.toggled.connect(self._on_master_toggle)
        self._content_layout.addWidget(self._master_toggle)

        # ── Schedule Section ────────────────────────────────────────
        self._content_layout.addWidget(SectionHeader(
            content, t("automail.schedule_section", "Reminder Schedule")
        ))

        self._add_btn = QPushButton(
            "+ " + t("automail.add_reminder", "Add Reminder"), content
        )
        self._add_btn.setObjectName("add-reminder-btn")
        self._add_btn.setFixedHeight(34)
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.setStyleSheet(f"""
            QPushButton#add-reminder-btn {{
                background: {COLOR_ACCENT_PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 16px;
            }}
            QPushButton#add-reminder-btn:hover {{
                background: {COLOR_ACCENT_PRIMARY}CC;
            }}
            QPushButton#add-reminder-btn:pressed {{
                background: {COLOR_ACCENT_PRIMARY}AA;
            }}
        """)
        self._add_btn.clicked.connect(self._on_add_reminder)
        self._content_layout.addWidget(self._add_btn)

        self._schedule_container = QWidget(content)
        self._schedule_container.setStyleSheet("background: transparent;")
        self._schedule_list_layout = QVBoxLayout(self._schedule_container)
        self._schedule_list_layout.setContentsMargins(0, 0, 0, 0)
        self._schedule_list_layout.setSpacing(SPACE_2)
        self._schedule_list_layout.setAlignment(Qt.AlignTop)
        self._content_layout.addWidget(self._schedule_container)

        # ── Delivery Rules ──────────────────────────────────────────
        self._content_layout.addSpacing(SPACE_3)
        self._content_layout.addWidget(SectionHeader(
            content, t("automail.delivery_rules", "Delivery Rules")
        ))

        self._biz_hours_cb = QCheckBox(
            t("automail.business_hours_only", "Only send during business hours"), content
        )
        self._biz_hours_cb.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px;")
        self._content_layout.addWidget(self._biz_hours_cb)

        hours_row = QHBoxLayout()
        hours_row.setSpacing(SPACE_2)
        self._start_time = QTimeEdit(content)
        self._start_time.setDisplayFormat("HH:mm")
        self._start_time.setTime(self._start_time.time().fromString("08:00", "HH:mm"))
        self._end_time = QTimeEdit(content)
        self._end_time.setDisplayFormat("HH:mm")
        self._end_time.setTime(self._end_time.time().fromString("18:00", "HH:mm"))
        hours_row.addWidget(QLabel(t("common.from", "From") + ":", content))
        hours_row.addWidget(self._start_time)
        hours_row.addWidget(QLabel(t("common.to", "To") + ":", content))
        hours_row.addWidget(self._end_time)
        hours_row.addStretch()
        self._content_layout.addLayout(hours_row)

        self._skip_weekends_cb = QCheckBox(
            t("automail.skip_weekends", "Skip weekends"), content
        )
        self._skip_weekends_cb.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px;")
        self._content_layout.addWidget(self._skip_weekends_cb)

        # ── Safety ──────────────────────────────────────────────────
        self._content_layout.addSpacing(SPACE_3)
        self._content_layout.addWidget(SectionHeader(
            content, t("automail.safety", "Safety")
        ))

        safety_row = QHBoxLayout()
        safety_row.setSpacing(SPACE_2)
        safety_row.addWidget(QLabel(
            t("automail.max_reminders", "Max reminders per invoice") + ":", content
        ))
        self._max_reminders_spin = QSpinBox(content)
        self._max_reminders_spin.setRange(1, 50)
        self._max_reminders_spin.setValue(5)
        safety_row.addWidget(self._max_reminders_spin)
        safety_row.addStretch()
        self._content_layout.addLayout(safety_row)

        retry_row = QHBoxLayout()
        retry_row.setSpacing(SPACE_2)
        retry_row.addWidget(QLabel(
            t("automail.retry_attempts", "Retry attempts") + ":", content
        ))
        self._retry_spin = QSpinBox(content)
        self._retry_spin.setRange(0, 10)
        self._retry_spin.setValue(3)
        retry_row.addWidget(self._retry_spin)
        retry_row.addStretch()
        self._content_layout.addLayout(retry_row)

        # ── Presets ─────────────────────────────────────────────────
        self._content_layout.addSpacing(SPACE_3)
        self._content_layout.addWidget(SectionHeader(
            content, t("automail.presets", "Presets")
        ))

        preset_row = QHBoxLayout()
        preset_row.setSpacing(SPACE_2)
        self._preset_combo = QComboBox(content)
        self._preset_combo.setMinimumWidth(120)
        preset_row.addWidget(self._preset_combo)

        self._apply_preset_btn = Btn(
            content,
            text=t("automail.apply_preset", "Apply Preset"),
            variant="secondary",
            command=self._on_apply_preset,
        )
        preset_row.addWidget(self._apply_preset_btn)
        preset_row.addStretch()
        self._content_layout.addLayout(preset_row)

        self._content_layout.addStretch()

    # ── Data loading ───────────────────────────────────────────────

    def _load_data(self) -> None:
        if self._repo is None:
            return

        # Load settings
        settings = self._repo.get_all_settings()
        self._master_toggle.set_checked(settings.get("enabled", "0") == "1")
        self._max_reminders_spin.setValue(
            int(settings.get("max_reminders_per_invoice", "5"))
        )
        self._retry_spin.setValue(
            int(settings.get("retry_attempts", "3"))
        )
        self._skip_weekends_cb.setChecked(
            settings.get("skip_weekends", "1") == "1"
        )
        self._biz_hours_cb.setChecked(
            settings.get("business_hours_only", "0") == "1"
        )
        biz_start = settings.get("business_hours_start", "08:00")
        biz_end = settings.get("business_hours_end", "18:00")
        self._start_time.setTime(self._start_time.time().fromString(biz_start, "HH:mm"))
        self._end_time.setTime(self._end_time.time().fromString(biz_end, "HH:mm"))

        # Load schedules
        self._refresh_schedule_list()

        # Load presets
        from ui.views.automail.presets import get_preset_names
        self._preset_combo.clear()
        for name in get_preset_names():
            self._preset_combo.addItem(name)

    def _refresh_schedule_list(self) -> None:
        if self._repo is None:
            return

        # Clear existing cards, editors, and containers
        for card in self._schedule_cards:
            self._schedule_list_layout.removeWidget(card)
            card.deleteLater()
        self._schedule_cards.clear()
        for sid, container in self._editor_containers.items():
            self._schedule_list_layout.removeWidget(container)
            container.deleteLater()
        self._editor_containers.clear()
        self._inline_editors.clear()

        schedules = self._repo.get_all_schedules()
        templates = self._repo.get_all_templates()
        count = len(schedules)
        for i, sched in enumerate(schedules):
            card = _ScheduleCard(
                self._schedule_container, sched,
                is_first=(i == 0),
                is_last=(i == count - 1),
            )
            card.edit_clicked.connect(self._on_toggle_editor)
            card.duplicate_clicked.connect(self._on_duplicate_schedule)
            card.delete_clicked.connect(self._on_delete_schedule)
            card.move_up.connect(self._on_move_up)
            card.move_down.connect(self._on_move_down)
            card.active_toggled.connect(self._on_schedule_active_toggled)
            self._schedule_list_layout.addWidget(card)
            self._schedule_cards.append(card)

            # Create hidden inline editor container
            editor = _InlineScheduleEditor(
                self._schedule_container, sched, templates,
            )
            editor.save_clicked.connect(self._on_inline_save)
            editor.save_all_clicked.connect(self._on_inline_save_all)
            editor.cancel_clicked.connect(self._on_inline_cancel)
            container = QWidget(self._schedule_container)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.addWidget(editor)
            container.hide()
            self._schedule_list_layout.addWidget(container)
            self._inline_editors[sched["id"]] = editor
            self._editor_containers[sched["id"]] = container

    def wakeup(self) -> None:
        self._load_data()

    # ── Handlers ───────────────────────────────────────────────────

    def _on_master_toggle(self, enabled: bool) -> None:
        if self._repo:
            self._repo.set_setting("enabled", "1" if enabled else "0")

    def _on_add_reminder(self) -> None:
        if self._repo is None:
            return
        templates = self._repo.get_all_templates()
        default_tpl_id = None
        if templates:
            default_tpl_id = templates[0]["id"]
        data = {
            "name": t("automail.new_schedule_default", "New Reminder"),
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": default_tpl_id,
            "is_active": 1,
            "attach_invoice": 1,
            "attach_cmr": 1,
            "attach_all_docs": 0,
        }
        new_id = self._repo.create_schedule(data)
        self._refresh_schedule_list()
        self.schedules_changed.emit()
        # Open the inline editor for the new schedule
        if new_id in self._editor_containers:
            for sid, container in self._editor_containers.items():
                container.setVisible(sid == new_id)

    def _on_toggle_editor(self, schedule_id: int) -> None:
        """Toggle the inline editor for a schedule card."""
        # Close any other open editor first
        for sid, container in self._editor_containers.items():
            if sid != schedule_id:
                container.hide()

        container = self._editor_containers.get(schedule_id)
        if container:
            container.setVisible(not container.isVisible())

    def _on_inline_save(self, schedule_id: int, data: dict[str, Any]) -> None:
        """Save changes for a single schedule."""
        if self._repo is None:
            return
        self._repo.update_schedule(schedule_id, data)
        container = self._editor_containers.get(schedule_id)
        if container:
            container.hide()
        self._refresh_schedule_list()
        self.schedules_changed.emit()

    def _on_inline_save_all(self, data: dict[str, Any]) -> None:
        """Apply the same data (except name) to ALL schedules."""
        if self._repo is None:
            return
        schedules = self._repo.get_all_schedules()
        for sched in schedules:
            sid = sched["id"]
            merged = dict(data)
            merged["name"] = sched.get("name", "")
            self._repo.update_schedule(sid, merged)

        # Hide all editors
        for container in self._editor_containers.values():
            container.hide()
        self._refresh_schedule_list()
        self.schedules_changed.emit()

    def _on_inline_cancel(self, schedule_id: int) -> None:
        """Cancel editing and hide the inline editor."""
        container = self._editor_containers.get(schedule_id)
        if container:
            container.hide()

    def _on_duplicate_schedule(self, schedule_id: int) -> None:
        if self._repo is None:
            return
        sched = self._repo.get_schedule_by_id(schedule_id)
        if not sched:
            return
        data = {
            "name": (sched.get("name", "") or "") + " (copy)",
            "trigger_type": sched["trigger_type"],
            "days_offset": sched["days_offset"],
            "template_id": sched["template_id"],
            "is_active": sched.get("is_active", 1),
            "attach_invoice": sched.get("attach_invoice", 1),
            "attach_cmr": sched.get("attach_cmr", 1),
            "attach_all_docs": sched.get("attach_all_docs", 0),
        }
        self._repo.create_schedule(data)
        self._refresh_schedule_list()
        self.schedules_changed.emit()

    def _on_delete_schedule(self, schedule_id: int) -> None:
        if self._repo is None:
            return
        reply = QMessageBox.question(
            self,
            t("common.confirm", "Confirm"),
            t("automail.confirm_delete_schedule", "Delete this reminder?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._repo.delete_schedule(schedule_id)
            self._refresh_schedule_list()
            self.schedules_changed.emit()

    def _on_move_up(self, schedule_id: int) -> None:
        self._reorder(schedule_id, -1)

    def _on_move_down(self, schedule_id: int) -> None:
        self._reorder(schedule_id, +1)

    def _reorder(self, schedule_id: int, direction: int) -> None:
        if self._repo is None:
            return
        schedules = self._repo.get_all_schedules()
        ids = [s["id"] for s in schedules]
        idx = ids.index(schedule_id)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(ids):
            return
        ids[idx], ids[new_idx] = ids[new_idx], ids[idx]
        self._repo.reorder_schedules(ids)
        self._refresh_schedule_list()
        self.schedules_changed.emit()

    def _on_schedule_active_toggled(self, schedule_id: int, active: bool) -> None:
        if self._repo:
            self._repo.update_schedule(schedule_id, {"is_active": 1 if active else 0})
            self._refresh_schedule_list()
            self.schedules_changed.emit()

    def _on_apply_preset(self) -> None:
        if self._repo is None:
            return
        name = self._preset_combo.currentText()
        if not name:
            return
        from ui.views.automail.presets import get_preset
        preset = get_preset(name)
        if not preset:
            return
        reply = QMessageBox.question(
            self,
            t("common.confirm", "Confirm"),
            t("automail.confirm_preset",
              "This will replace ALL your current reminders and templates. Continue?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Create preset template
            tpl_data = preset["template"]
            tpl_id = self._repo.create_template({
                "name": tpl_data["name"],
                "subject": tpl_data["subject"],
                "body_text": tpl_data["body_text"],
                "body_html": tpl_data["body_html"],
            })

            # Remove existing schedules
            for s in self._repo.get_all_schedules():
                self._repo.delete_schedule(s["id"])

            # Create preset schedules
            for s in preset["schedules"]:
                self._repo.create_schedule({
                    "name": s["name"],
                    "trigger_type": s["trigger_type"],
                    "days_offset": s["days_offset"],
                    "template_id": tpl_id,
                    "is_active": s["is_active"],
                    "sort_order": s["sort_order"],
                })

            self._refresh_schedule_list()
            self.schedules_changed.emit()
            logger.info("Applied AutoMail preset: %s", name)
        except Exception as exc:
            logger.exception("Failed to apply preset %s: %s", name, exc)
            QMessageBox.warning(self, t("common.error", "Error"),
                                str(exc))
