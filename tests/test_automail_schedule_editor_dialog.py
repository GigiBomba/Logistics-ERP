"""Tests for ScheduleEditorDialog — automail schedule entry dialog."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QSpinBox,
)

from ui.views.automail.schedule_editor_dialog import ScheduleEditorDialog
from ui.widgets import StyledLineEdit


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def sample_templates():
    return [
        {"id": 1, "name": "Friendly Reminder"},
        {"id": 2, "name": "Professional Notice"},
    ]


@pytest.fixture
def sample_schedule():
    return {
        "name": "Day 27 Reminder",
        "trigger_type": "days_before_due",
        "days_offset": 3,
        "template_id": 2,
        "is_active": 1,
        "attach_invoice": 1,
        "attach_cmr": 0,
        "attach_all_docs": 0,
    }


@pytest.fixture
def partial_schedule():
    return {"name": "Minimal", "is_active": 0}


# ── Creation ────────────────────────────────────────────────────────────


class TestScheduleEditorDialogCreation:
    def test_creation_create_mode(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert dlg._schedule is None
        assert dlg._templates == []
        assert "Add Reminder" in dlg.windowTitle() or "Add" in dlg.windowTitle()

    def test_creation_edit_mode(self, qt_widget, qtbot, sample_schedule):
        dlg = ScheduleEditorDialog(qt_widget, schedule=sample_schedule)
        qtbot.addWidget(dlg)
        assert dlg._schedule is sample_schedule
        assert "Edit Reminder" in dlg.windowTitle() or "Edit" in dlg.windowTitle()

    def test_creation_with_templates(self, qt_widget, qtbot, sample_templates):
        dlg = ScheduleEditorDialog(qt_widget, templates=sample_templates)
        qtbot.addWidget(dlg)
        assert dlg._templates is sample_templates
        assert dlg._template_combo.count() == 2

    def test_modal(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert dlg.isModal() is True

    def test_minimum_width(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert dlg.minimumWidth() >= 480


# ── UI Elements ─────────────────────────────────────────────────────────


class TestScheduleEditorDialogUI:
    def test_has_name_edit(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert isinstance(dlg._name_edit, StyledLineEdit)
        assert dlg._name_edit.placeholderText() != ""

    def test_has_trigger_combo(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        combo = dlg._trigger_combo
        assert isinstance(combo, QComboBox)
        assert combo.count() >= 3

    def test_trigger_combo_has_data(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        data = [dlg._trigger_combo.itemData(i) for i in range(dlg._trigger_combo.count())]
        assert "days_before_due" in data
        assert "on_due_date" in data
        assert "days_after_due" in data

    def test_has_days_spin(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        spin = dlg._days_spin
        assert isinstance(spin, QSpinBox)
        assert spin.minimum() == 0
        assert spin.maximum() == 365

    def test_has_preview_label(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert dlg._preview_label.text() != ""

    def test_has_template_combo(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert isinstance(dlg._template_combo, QComboBox)

    def test_has_attach_checkboxes(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert isinstance(dlg._attach_invoice, QCheckBox)
        assert isinstance(dlg._attach_cmr, QCheckBox)
        assert isinstance(dlg._attach_all, QCheckBox)

    def test_attach_defaults(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert dlg._attach_invoice.isChecked() is True
        assert dlg._attach_cmr.isChecked() is True
        assert dlg._attach_all.isChecked() is False

    def test_has_active_checkbox(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        assert isinstance(dlg._active_cb, QCheckBox)
        assert dlg._active_cb.isChecked() is True

    def test_has_buttons(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        buttons = dlg.findChildren(QDialogButtonBox)
        assert len(buttons) >= 1


# ── Populate (edit mode) ────────────────────────────────────────────────


class TestScheduleEditorDialogPopulate:
    def test_populate_name(self, qt_widget, qtbot, sample_schedule):
        dlg = ScheduleEditorDialog(qt_widget, schedule=sample_schedule)
        qtbot.addWidget(dlg)
        assert dlg._name_edit.text() == "Day 27 Reminder"

    def test_populate_trigger(self, qt_widget, qtbot, sample_schedule):
        dlg = ScheduleEditorDialog(qt_widget, schedule=sample_schedule)
        qtbot.addWidget(dlg)
        assert dlg._trigger_combo.currentData() == "days_before_due"

    def test_populate_days(self, qt_widget, qtbot, sample_schedule):
        dlg = ScheduleEditorDialog(qt_widget, schedule=sample_schedule)
        qtbot.addWidget(dlg)
        assert dlg._days_spin.value() == 3

    def test_populate_template(self, qt_widget, qtbot, sample_schedule, sample_templates):
        dlg = ScheduleEditorDialog(qt_widget, templates=sample_templates, schedule=sample_schedule)
        qtbot.addWidget(dlg)
        assert dlg._template_combo.currentData() == 2

    def test_populate_active_unchecked(self, qt_widget, qtbot):
        schedule = {
            "name": "Test",
            "trigger_type": "on_due_date",
            "days_offset": 0,
            "is_active": 0,
            "attach_invoice": 0,
            "attach_cmr": 0,
            "attach_all_docs": 0,
        }
        dlg = ScheduleEditorDialog(qt_widget, schedule=schedule)
        qtbot.addWidget(dlg)
        assert dlg._active_cb.isChecked() is False
        assert dlg._attach_invoice.isChecked() is False
        assert dlg._attach_cmr.isChecked() is False
        assert dlg._attach_all.isChecked() is False

    def test_populate_with_attach_all(self, qt_widget, qtbot):
        schedule = {
            "name": "Test",
            "trigger_type": "on_due_date",
            "days_offset": 0,
            "is_active": 1,
            "attach_invoice": 0,
            "attach_cmr": 0,
            "attach_all_docs": 1,
        }
        dlg = ScheduleEditorDialog(qt_widget, schedule=schedule)
        qtbot.addWidget(dlg)
        assert dlg._attach_all.isChecked() is True


# ── get_data ────────────────────────────────────────────────────────────


class TestScheduleEditorDialogGetData:
    def test_get_data_returns_dict(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        data = dlg.get_data()
        assert isinstance(data, dict)

    def test_get_data_contains_keys(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        data = dlg.get_data()
        assert "name" in data
        assert "trigger_type" in data
        assert "days_offset" in data
        assert "template_id" in data
        assert "is_active" in data
        assert "attach_invoice" in data
        assert "attach_cmr" in data
        assert "attach_all_docs" in data

    def test_get_data_default_values(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        data = dlg.get_data()
        assert data["days_offset"] == 3
        assert data["is_active"] == 1
        assert data["attach_invoice"] == 1
        assert data["attach_cmr"] == 1
        assert data["attach_all_docs"] == 0

    def test_get_data_reflects_user_input(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg._name_edit.setText("My Custom")
        dlg._days_spin.setValue(7)
        dlg._attach_cmr.setChecked(False)
        data = dlg.get_data()
        assert data["name"] == "My Custom"
        assert data["days_offset"] == 7
        assert data["attach_cmr"] == 0


# ── Preview label updates ──────────────────────────────────────────────


class TestScheduleEditorDialogPreview:
    def test_preview_before_due_default(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        text = dlg._preview_label.text().lower()
        assert "before" in text

    def test_preview_on_due_date(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        idx = dlg._trigger_combo.findData("on_due_date")
        dlg._trigger_combo.setCurrentIndex(idx)
        text = dlg._preview_label.text().lower()
        assert "on the due date" in text

    def test_preview_after_due(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        idx = dlg._trigger_combo.findData("days_after_due")
        dlg._trigger_combo.setCurrentIndex(idx)
        text = dlg._preview_label.text().lower()
        assert "after" in text


# ── Validation ──────────────────────────────────────────────────────────


class TestScheduleEditorDialogValidation:
    def test_empty_name_shows_warning(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg._name_edit.setText("")
        with patch.object(QMessageBox, "warning") as mock_warn:
            dlg._on_accept()
            mock_warn.assert_called_once()

    def test_empty_name_does_not_accept(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg._name_edit.setText("")
        with patch.object(QMessageBox, "warning"):
            dlg._on_accept()
            # Dialog should not be accepted
            assert dlg.result() != QMessageBox.DialogCode.Accepted

    def test_valid_name_accepts(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg._name_edit.setText("Valid Reminder")
        with patch.object(QMessageBox, "warning") as mock_warn:
            dlg._on_accept()
            mock_warn.assert_not_called()
        # accept() sets result to QDialog.Accepted (= 1)
        assert dlg.result() == QDialog.Accepted


# ── Lifecycle ───────────────────────────────────────────────────────────


class TestScheduleEditorDialogLifecycle:
    def test_open_and_close(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg.show()
        assert dlg.isVisible() is True
        dlg.close()
        assert dlg.isVisible() is False

    def test_reject_via_button(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        buttons = dlg.findChildren(QDialogButtonBox)
        assert len(buttons) >= 1
        # Clicking Cancel calls reject()
        buttons[0].button(QDialogButtonBox.StandardButton.Cancel).click()
        # Result should be Rejected
        assert dlg.result() == QDialog.Rejected

    def test_trigger_change_emits_preview_update(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        with patch.object(dlg, "_update_preview") as mock_update:
            idx = dlg._trigger_combo.findData("days_after_due")
            dlg._trigger_combo.setCurrentIndex(idx)
            mock_update.assert_called_once()


# ── Edge Cases ─────────────────────────────────────────────────────────


class TestScheduleEditorDialogEdgeCases:
    """Edge-case tests for ScheduleEditorDialog."""

    def test_days_spin_changed_updates_preview(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg._days_spin.setValue(10)
        text = dlg._preview_label.text()
        assert "10" in text

    def test_accept_with_whitespace_name_fails(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget)
        qtbot.addWidget(dlg)
        dlg._name_edit.setText("   ")
        with patch.object(QMessageBox, "warning") as mock_warn:
            dlg._on_accept()
            mock_warn.assert_called_once()
        assert dlg.result() != QDialog.DialogCode.Accepted

    def test_populate_with_partial_data_uses_defaults(
        self, qt_widget, qtbot, partial_schedule
    ):
        dlg = ScheduleEditorDialog(qt_widget, schedule=partial_schedule)
        qtbot.addWidget(dlg)
        assert dlg._trigger_combo.currentData() == "days_before_due"
        assert dlg._days_spin.value() == 3

    def test_template_combo_empty_no_crash(self, qt_widget, qtbot):
        dlg = ScheduleEditorDialog(qt_widget, templates=[])
        qtbot.addWidget(dlg)
        assert dlg._template_combo.count() == 0

    def test_get_data_roundtrip_complete(self, qt_widget, qtbot, sample_templates):
        dlg = ScheduleEditorDialog(qt_widget, templates=sample_templates)
        qtbot.addWidget(dlg)
        dlg._name_edit.setText("Test Roundtrip")
        idx = dlg._trigger_combo.findData("days_after_due")
        dlg._trigger_combo.setCurrentIndex(idx)
        dlg._days_spin.setValue(14)
        dlg._template_combo.setCurrentIndex(1)
        dlg._attach_invoice.setChecked(False)
        dlg._attach_cmr.setChecked(False)
        dlg._attach_all.setChecked(True)
        dlg._active_cb.setChecked(False)

        data = dlg.get_data()
        assert data["name"] == "Test Roundtrip"
        assert data["trigger_type"] == "days_after_due"
        assert data["days_offset"] == 14
        assert data["template_id"] == 2
        assert data["is_active"] == 0
        assert data["attach_invoice"] == 0
        assert data["attach_cmr"] == 0
        assert data["attach_all_docs"] == 1
