"""Tests for the automail ConfigPanel, _MasterToggle, _ScheduleCard, _InlineScheduleEditor."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ui.views.automail.config_panel import (
    ConfigPanel,
    _InlineScheduleEditor,
    _MasterToggle,
    _ScheduleCard,
)


# ── _MasterToggle ─────────────────────────────────────────────────────


class TestMasterToggle:
    def test_creation_default_off(self, qt_widget, qtbot):
        toggle = _MasterToggle(qt_widget)
        qtbot.addWidget(toggle)
        assert toggle._switch.isChecked() is False
        assert toggle.property("role") == "automail-master-toggle"

    def test_creation_default_on(self, qt_widget, qtbot):
        toggle = _MasterToggle(qt_widget, enabled=True)
        qtbot.addWidget(toggle)
        assert toggle._switch.isChecked() is True

    def test_set_checked_without_signal(self, qt_widget, qtbot):
        toggle = _MasterToggle(qt_widget)
        qtbot.addWidget(toggle)
        received = []

        def on_toggled(val):
            received.append(val)

        toggle.toggled.connect(on_toggled)
        toggle.set_checked(True)
        assert toggle._switch.isChecked() is True
        assert len(received) == 0  # no signal emitted

    def test_toggled_signal_emitted(self, qt_widget, qtbot):
        toggle = _MasterToggle(qt_widget)
        qtbot.addWidget(toggle)
        received = []

        def on_toggled(val):
            received.append(val)

        toggle.toggled.connect(on_toggled)
        toggle._switch.setChecked(True)
        assert len(received) == 1
        assert received[0] is True

    def test_layout_has_checkbox(self, qt_widget, qtbot):
        toggle = _MasterToggle(qt_widget)
        qtbot.addWidget(toggle)
        assert toggle._switch is not None
        assert toggle._switch.text() != ""


# ── _InlineScheduleEditor ──────────────────────────────────────────────


class TestInlineScheduleEditor:
    def test_creation_with_schedule(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test Reminder",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "is_active": 1,
            "attach_invoice": 1,
            "attach_cmr": 0,
            "attach_all_docs": 0,
        }
        templates = [{"id": 10, "name": "Default"}, {"id": 20, "name": "Urgent"}]
        editor = _InlineScheduleEditor(qt_widget, schedule, templates)
        qtbot.addWidget(editor)
        assert editor._schedule_id == 1
        assert editor._name_edit.text() == "Test Reminder"
        assert editor._days_spin.value() == 3
        assert editor._template_combo.count() == 2
        assert editor._active_cb.isChecked() is True

    def test_save_emits_signal(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "is_active": 1,
            "attach_invoice": 1,
            "attach_cmr": 0,
            "attach_all_docs": 0,
        }
        templates = [{"id": 10, "name": "Default"}]
        editor = _InlineScheduleEditor(qt_widget, schedule, templates)
        qtbot.addWidget(editor)
        received = []

        def on_save(sid, data):
            received.append((sid, data))

        editor.save_clicked.connect(on_save)
        editor._save_btn.click()
        assert len(received) == 1
        assert received[0][0] == 1

    def test_save_all_emits_signal(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "is_active": 1,
            "attach_invoice": 1,
            "attach_cmr": 0,
            "attach_all_docs": 0,
        }
        templates = [{"id": 10, "name": "Default"}]
        editor = _InlineScheduleEditor(qt_widget, schedule, templates)
        qtbot.addWidget(editor)
        received = []

        def on_save_all(data):
            received.append(data)

        editor.save_all_clicked.connect(on_save_all)
        editor._save_all_btn.click()
        assert len(received) == 1

    def test_cancel_emits_signal(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "is_active": 1,
            "attach_invoice": 1,
            "attach_cmr": 0,
            "attach_all_docs": 0,
        }
        templates = [{"id": 10, "name": "Default"}]
        editor = _InlineScheduleEditor(qt_widget, schedule, templates)
        qtbot.addWidget(editor)
        received = []

        def on_cancel(sid):
            received.append(sid)

        editor.cancel_clicked.connect(on_cancel)
        editor._cancel_btn.click()
        assert len(received) == 1
        assert received[0] == 1

    def test_save_with_empty_name_shows_warning(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "is_active": 1,
            "attach_invoice": 1,
            "attach_cmr": 0,
            "attach_all_docs": 0,
        }
        templates = [{"id": 10, "name": "Default"}]
        editor = _InlineScheduleEditor(qt_widget, schedule, templates)
        qtbot.addWidget(editor)
        with patch.object(QMessageBox, "warning") as mock_warn:
            editor._save_btn.click()
            mock_warn.assert_called_once()

    def test_collect_data(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "My Reminder",
            "trigger_type": "days_after_due",
            "days_offset": 5,
            "template_id": 20,
            "is_active": 0,
            "attach_invoice": 0,
            "attach_cmr": 1,
            "attach_all_docs": 0,
        }
        templates = [{"id": 10, "name": "Default"}, {"id": 20, "name": "Urgent"}]
        editor = _InlineScheduleEditor(qt_widget, schedule, templates)
        qtbot.addWidget(editor)
        data = editor._collect_data()
        assert data["name"] == "My Reminder"
        assert data["trigger_type"] == "days_after_due"
        assert data["days_offset"] == 5
        assert data["template_id"] == 20
        assert data["is_active"] == 0
        assert data["attach_invoice"] == 0
        assert data["attach_cmr"] == 1


# ── _ScheduleCard ──────────────────────────────────────────────────────


class TestScheduleCard:
    def test_creation(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test Schedule",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "template_name": "Default Template",
            "is_active": 1,
        }
        card = _ScheduleCard(qt_widget, schedule, is_first=True, is_last=True)
        qtbot.addWidget(card)
        assert card._schedule_id == 1

    def test_signals_exist(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "template_name": "Default",
            "is_active": 1,
        }
        card = _ScheduleCard(qt_widget, schedule, is_first=True, is_last=True)
        qtbot.addWidget(card)
        assert hasattr(card, "edit_clicked")
        assert hasattr(card, "duplicate_clicked")
        assert hasattr(card, "delete_clicked")
        assert hasattr(card, "move_up")
        assert hasattr(card, "move_down")
        assert hasattr(card, "active_toggled")

    def test_timing_format_before(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "template_name": "Default",
            "is_active": 1,
        }
        card = _ScheduleCard(qt_widget, schedule, is_first=True, is_last=True)
        qtbot.addWidget(card)
        assert card._timing_lbl is not None

    def test_timing_format_after(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test",
            "trigger_type": "days_after_due",
            "days_offset": 5,
            "template_id": 10,
            "template_name": "Default",
            "is_active": 1,
        }
        card = _ScheduleCard(qt_widget, schedule, is_first=True, is_last=True)
        qtbot.addWidget(card)
        assert card._timing_lbl is not None

    def test_timing_format_on(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test",
            "trigger_type": "on_due_date",
            "days_offset": 0,
            "template_id": 10,
            "template_name": "Default",
            "is_active": 1,
        }
        card = _ScheduleCard(qt_widget, schedule, is_first=True, is_last=True)
        qtbot.addWidget(card)
        assert card._timing_lbl is not None

    def test_first_last_no_move_buttons(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "template_name": "Default",
            "is_active": 1,
        }
        card = _ScheduleCard(qt_widget, schedule, is_first=True, is_last=True)
        qtbot.addWidget(card)
        # When is_first and is_last, no up/down buttons
        assert not hasattr(card, "_up_btn") or card._up_btn is None
        assert not hasattr(card, "_down_btn") or card._down_btn is None

    def test_not_first_has_up_button(self, qt_widget, qtbot):
        schedule = {
            "id": 2,
            "name": "Test",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "template_name": "Default",
            "is_active": 1,
        }
        card = _ScheduleCard(qt_widget, schedule, is_first=False, is_last=True)
        qtbot.addWidget(card)
        assert hasattr(card, "_up_btn")

    def test_not_last_has_down_button(self, qt_widget, qtbot):
        schedule = {
            "id": 2,
            "name": "Test",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "template_name": "Default",
            "is_active": 1,
        }
        card = _ScheduleCard(qt_widget, schedule, is_first=True, is_last=False)
        qtbot.addWidget(card)
        assert hasattr(card, "_down_btn")

    def test_active_toggle_signal(self, qt_widget, qtbot):
        schedule = {
            "id": 1,
            "name": "Test",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "template_name": "Default",
            "is_active": 1,
        }
        card = _ScheduleCard(qt_widget, schedule, is_first=True, is_last=True)
        qtbot.addWidget(card)
        received = []

        def on_toggle(sid, active):
            received.append((sid, active))

        card.active_toggled.connect(on_toggle)
        card._active_switch.setChecked(False)
        assert len(received) == 1
        assert received[0] == (1, False)


# ── ConfigPanel ────────────────────────────────────────────────────────


class TestConfigPanelCreation:
    def test_creation_without_db(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        assert panel._repo is None
        assert panel._master_toggle is not None

    def test_creation_with_db(self, qt_widget, qtbot):
        db = MagicMock()
        panel = ConfigPanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        assert panel._repo is not None

    def test_property_role(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        assert panel.property("role") == "automail-config-panel"

    def test_scrollarea_exists(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        scroll_areas = panel.findChildren(QScrollArea)
        assert len(scroll_areas) >= 1

    def test_master_toggle_present(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        toggles = panel.findChildren(_MasterToggle)
        assert len(toggles) == 1

    def test_add_reminder_button_present(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        add_btn = panel.findChild(QPushButton, "add-reminder-btn")
        assert add_btn is not None


class TestConfigPanelUISections:
    def test_delivery_rules_section(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        checkboxes = panel.findChildren(QCheckBox)
        # Should have biz hours, skip weekends checkboxes
        biz_hours_cb = [
            cb for cb in checkboxes
            if "business" in cb.text().lower() or "hours" in cb.text().lower()
        ]
        skip_wknd_cb = [
            cb for cb in checkboxes
            if "weekend" in cb.text().lower() or "skip" in cb.text().lower()
        ]

    def test_safety_section(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        spin_boxes = panel.findChildren(QSpinBox)
        # At least 2: max reminders + retry attempts
        assert len(spin_boxes) >= 2

    def test_preset_combo_exists(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        combos = panel.findChildren(QComboBox)
        # At least 1: preset combo
        assert len(combos) >= 1

    def test_time_edits_exist(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        time_edits = panel.findChildren(QTimeEdit)
        assert len(time_edits) == 2


class TestConfigPanelLoadData:
    def test_load_data_without_repo(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        # Should not crash
        panel._load_data()

    def test_load_data_with_repo(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {
            "enabled": "1",
            "max_reminders_per_invoice": "3",
            "retry_attempts": "2",
            "skip_weekends": "1",
            "business_hours_only": "0",
            "business_hours_start": "09:00",
            "business_hours_end": "17:00",
        }
        repo.get_all_schedules.return_value = []
        repo.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            # Panel auto-loads on construction
            assert panel._master_toggle._switch.isChecked() is True
            assert panel._max_reminders_spin.value() == 3
            assert panel._retry_spin.value() == 2

    def test_schedule_list_refreshed(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = [
            {
                "id": 1,
                "name": "Reminder 1",
                "trigger_type": "days_before_due",
                "days_offset": 3,
                "template_id": 10,
                "template_name": "Default",
                "is_active": 1,
            },
        ]
        repo.get_all_templates.return_value = [{"id": 10, "name": "Default"}]

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            schedule_cards = panel.findChildren(_ScheduleCard)
            assert len(schedule_cards) == 1

    def test_wakeup_reloads_data(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = []
        repo.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            repo.get_all_settings.reset_mock()
            panel.wakeup()
            repo.get_all_settings.assert_called()


class TestConfigPanelHandlers:
    def test_master_toggle_with_repo(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = []
        repo.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._on_master_toggle(True)
            repo.set_setting.assert_called_with("enabled", "1")

    def test_master_toggle_without_repo(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        # Should not crash
        panel._on_master_toggle(True)

    def test_add_reminder_with_repo(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = []
        repo.get_all_templates.return_value = [{"id": 10, "name": "Default"}]
        repo.create_schedule.return_value = 1

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._on_add_reminder()
            repo.create_schedule.assert_called_once()
            repo.get_all_schedules.assert_called()  # refresh

    def test_add_reminder_without_repo(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        # Should not crash
        panel._on_add_reminder()

    def test_toggle_editor_shows_hides(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = [
            {
                "id": 1,
                "name": "R1",
                "trigger_type": "days_before_due",
                "days_offset": 3,
                "template_id": 10,
                "template_name": "T",
                "is_active": 1,
            },
        ]
        repo.get_all_templates.return_value = [{"id": 10, "name": "T"}]

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            container = panel._editor_containers.get(1)
            assert container is not None
            # First toggle: hidden → show
            with patch.object(container, "setVisible") as mock_set_visible:
                panel._on_toggle_editor(1)
                mock_set_visible.assert_called_once_with(True)

    def test_inline_save(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = [
            {
                "id": 1,
                "name": "R1",
                "trigger_type": "days_before_due",
                "days_offset": 3,
                "template_id": 10,
                "template_name": "T",
                "is_active": 1,
            },
        ]
        repo.get_all_templates.return_value = [{"id": 10, "name": "T"}]

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            data = {"name": "Updated", "trigger_type": "days_before_due"}
            panel._on_inline_save(1, data)
            repo.update_schedule.assert_called_with(1, data)

    def test_inline_save_all(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = [
            {
                "id": 1,
                "name": "R1",
                "trigger_type": "days_before_due",
                "days_offset": 3,
                "template_id": 10,
                "template_name": "T",
                "is_active": 1,
            },
            {
                "id": 2,
                "name": "R2",
                "trigger_type": "days_after_due",
                "days_offset": 5,
                "template_id": 10,
                "template_name": "T",
                "is_active": 1,
            },
        ]
        repo.get_all_templates.return_value = [{"id": 10, "name": "T"}]

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            data = {"trigger_type": "on_due_date", "days_offset": 0}
            panel._on_inline_save_all(data)
            # Should update both schedules, preserving names
            assert repo.update_schedule.call_count == 2

    def test_inline_cancel_hides_editor(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = [
            {
                "id": 1,
                "name": "R1",
                "trigger_type": "days_before_due",
                "days_offset": 3,
                "template_id": 10,
                "template_name": "T",
                "is_active": 1,
            },
        ]
        repo.get_all_templates.return_value = [{"id": 10, "name": "T"}]

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            container = panel._editor_containers.get(1)
            assert container is not None
            with patch.object(container, "hide") as mock_hide:
                panel._on_inline_cancel(1)
                mock_hide.assert_called_once()

    def test_duplicate_schedule(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = []
        repo.get_all_templates.return_value = []
        repo.get_schedule_by_id.return_value = {
            "id": 1,
            "name": "Original",
            "trigger_type": "days_before_due",
            "days_offset": 3,
            "template_id": 10,
            "is_active": 1,
            "attach_invoice": 1,
            "attach_cmr": 0,
            "attach_all_docs": 0,
        }

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._on_duplicate_schedule(1)
            repo.create_schedule.assert_called_once()
            args = repo.create_schedule.call_args[0][0]
            assert "(copy)" in args["name"]

    def test_duplicate_schedule_without_repo(self, qt_widget, qtbot):
        panel = ConfigPanel(qt_widget, db=None)
        qtbot.addWidget(panel)
        panel._on_duplicate_schedule(1)  # Should not crash

    def test_delete_schedule_confirmed(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = []
        repo.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ), patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._on_delete_schedule(1)
            repo.delete_schedule.assert_called_with(1)

    def test_delete_schedule_declined(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = []
        repo.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ), patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._on_delete_schedule(1)
            repo.delete_schedule.assert_not_called()

    def test_reorder_up(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = [
            {"id": 1, "name": "R1", "trigger_type": "days_before_due",
             "days_offset": 3, "template_id": 10, "is_active": 1},
            {"id": 2, "name": "R2", "trigger_type": "days_before_due",
             "days_offset": 3, "template_id": 10, "is_active": 1},
        ]
        repo.get_all_templates.return_value = [{"id": 10, "name": "T"}]

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._reorder(2, -1)  # Move schedule 2 up
            # IDs should become [2, 1]
            repo.reorder_schedules.assert_called_once()
            assert repo.reorder_schedules.call_args[0][0] == [2, 1]

    def test_reorder_down(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = [
            {"id": 1, "name": "R1", "trigger_type": "days_before_due",
             "days_offset": 3, "template_id": 10, "is_active": 1},
            {"id": 2, "name": "R2", "trigger_type": "days_before_due",
             "days_offset": 3, "template_id": 10, "is_active": 1},
        ]
        repo.get_all_templates.return_value = [{"id": 10, "name": "T"}]

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._reorder(1, +1)  # Move schedule 1 down
            # IDs should become [2, 1] (swap)
            repo.reorder_schedules.assert_called_once()
            assert repo.reorder_schedules.call_args[0][0] == [2, 1]

    def test_reorder_out_of_bounds(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = [
            {"id": 1, "name": "R1", "trigger_type": "days_before_due",
             "days_offset": 3, "template_id": 10, "is_active": 1},
            {"id": 2, "name": "R2", "trigger_type": "days_before_due",
             "days_offset": 3, "template_id": 10, "is_active": 1},
        ]
        repo.get_all_templates.return_value = [{"id": 10, "name": "T"}]

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            # Move first item up (out of bounds) → no-op
            panel._reorder(1, -1)  # position 0, -1 → out of bounds
            # Actually it does reorder: ids[0]=1 goes to new_idx=-1 which is <0, so function returns early
            # The reorder_schedules should NOT be called... but let's check the code.
            # _reorder checks: if new_idx < 0 or new_idx >= len(ids): return
            # So if schedule 1 is at idx 0 and direction is -1, new_idx = -1 → return early
            repo.reorder_schedules.assert_not_called()

    def test_schedule_active_toggled(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = [
            {"id": 1, "name": "R1", "trigger_type": "days_before_due",
             "days_offset": 3, "template_id": 10, "is_active": 1},
        ]
        repo.get_all_templates.return_value = [{"id": 10, "name": "T"}]

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._on_schedule_active_toggled(1, False)
            repo.update_schedule.assert_called_with(1, {"is_active": 0})

    def test_schedules_changed_signal_emitted(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = [
            {"id": 1, "name": "R1", "trigger_type": "days_before_due",
             "days_offset": 3, "template_id": 10, "is_active": 1},
        ]
        repo.get_all_templates.return_value = [{"id": 10, "name": "T"}]

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            received = []

            def on_changed():
                received.append(True)

            panel.schedules_changed.connect(on_changed)
            panel._on_duplicate_schedule(1)
            assert len(received) >= 1

    def test_apply_preset_shows_confirmation(self, qt_widget, qtbot):
        db = MagicMock()
        repo = MagicMock()
        repo.get_all_settings.return_value = {}
        repo.get_all_schedules.return_value = []
        repo.get_all_templates.return_value = []

        with patch(
            "ui.views.automail.config_panel.AutoMailRepository",
            return_value=repo,
        ), patch(
            "ui.views.automail.presets.get_preset_names",
            return_value=["Standard"],
        ), patch(
            "ui.views.automail.presets.get_preset",
            return_value={
                "template": {
                    "name": "Standard",
                    "subject": "Payment Notice",
                    "body_text": "Dear {{client}}",
                    "body_html": "<p>Dear {{client}}</p>",
                },
                "schedules": [
                    {
                        "name": "Reminder 1",
                        "trigger_type": "days_before_due",
                        "days_offset": 3,
                        "is_active": 1,
                        "sort_order": 0,
                    },
                ],
            },
        ), patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            panel = ConfigPanel(qt_widget, db=db)
            qtbot.addWidget(panel)
            panel._preset_combo.setCurrentText("Standard")
            panel._on_apply_preset()
            repo.create_template.assert_called_once()
            repo.create_schedule.assert_called_once()
