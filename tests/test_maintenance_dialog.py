"""Tests for the per-truck maintenance dialog (QtMaintenanceView)
and the schedule editing sub-dialog (_ScheduleEditDialog).

Covers construction, tab structure (Records / Schedules / Health),
data loading, schedule CRUD operations, health KPI updates,
and the _ScheduleEditDialog form.
"""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
)

from services.fleet_maintenance_service import MaintType
from ui.dialogs.maintenance_view import (
    QtMaintenanceView,
    _ScheduleEditDialog,
)
from ui.widgets import ActionButton, StyledTableWidget


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def maint_view(qt_widget, qtbot):
    """Provide a QtMaintenanceView with fully mocked service layer."""
    db = MagicMock()
    view = QtMaintenanceView(parent=qt_widget, db=db, truck_id=5, truck_plate="AB-12-34")
    qtbot.addWidget(view)
    yield view
    view.close()


@pytest.fixture
def mock_records():
    """Sample maintenance records."""
    return [
        {
            "id": 1,
            "maintenance_type": "oil_change",
            "date": "2026-01-10",
            "notes": "Oil and filter change",
            "cost": 250.0,
            "km": 50000,
        },
        {
            "id": 2,
            "maintenance_type": "brake_inspection",
            "date": "2026-02-15",
            "notes": "Brake pad check",
            "cost": 120.0,
            "km": 52000,
        },
    ]


@pytest.fixture
def mock_schedules():
    """Sample maintenance schedules."""
    return [
        {
            "id": 10,
            "maintenance_type": "oil_change",
            "interval_km": 15000.0,
            "interval_months": 6.0,
            "last_done_date": "2026-01-10",
            "active": True,
        },
        {
            "id": 11,
            "maintenance_type": "tire_replacement",
            "interval_km": 60000.0,
            "interval_months": 24.0,
            "last_done_date": "2025-06-01",
            "active": False,
        },
    ]


@pytest.fixture
def mock_health():
    """Sample health data via view-model."""
    health = MagicMock()
    health.score = 78
    health.compliance_pct = 85.0
    health.overdue_count = 2
    health.recurring_issues = 1
    health.downtime_days = 45
    return health


# ── Init ─────────────────────────────────────────────────────────────────

class TestQtMaintenanceViewInit:
    """Construction and initial state."""

    def test_creation(self, maint_view):
        assert isinstance(maint_view, QtMaintenanceView)
        assert maint_view.windowTitle() != ""

    def test_is_modal(self, maint_view):
        assert maint_view.windowModality() == Qt.ApplicationModal

    def test_resize_called(self, maint_view):
        assert maint_view.width() > 0
        assert maint_view.height() > 0

    def test_stores_truck_data(self, maint_view):
        assert maint_view.truck_id == 5
        assert maint_view.truck_plate == "AB-12-34"

    def test_service_initialized(self, maint_view):
        assert maint_view.service is not None

    def test_view_model_initialized(self, maint_view):
        assert maint_view._vm is not None

    def test_has_tab_widget(self, maint_view):
        tabs = maint_view.findChildren(QTabWidget)
        assert len(tabs) >= 1

    def test_three_tabs(self, maint_view):
        tabs = maint_view.findChildren(QTabWidget)
        assert len(tabs) >= 1
        tab_widget = tabs[0]
        assert tab_widget.count() == 3

    def test_tab_labels_exist(self, maint_view):
        tabs = maint_view.findChildren(QTabWidget)
        tab_widget = tabs[0]
        texts = [tab_widget.tabText(i) for i in range(tab_widget.count())]
        assert any(len(t) > 0 for t in texts)

    def test_i18n_listener_registered(self, maint_view):
        assert maint_view._language_callback is not None

    def test_header_label_exists(self, maint_view):
        assert maint_view._title_lbl is not None
        assert "AB-12-34" in maint_view._title_lbl.text()


# ── Tab 1: Records ───────────────────────────────────────────────────────

class TestQtMaintenanceViewRecords:
    """Records tab."""

    def test_record_table_exists(self, maint_view):
        assert maint_view._record_table is not None

    def test_record_table_is_styled_table(self, maint_view):
        assert isinstance(maint_view._record_table, StyledTableWidget)

    def test_load_records_populates_table(self, maint_view, mock_records):
        maint_view.service.get_records.return_value = mock_records
        maint_view._load_records()
        assert maint_view._record_table.rowCount() == 2

    def test_load_records_handles_empty(self, maint_view):
        maint_view.service.get_records.return_value = []
        maint_view._load_records()
        assert maint_view._record_table.rowCount() == 0

    def test_load_records_handles_exception(self, maint_view):
        maint_view.service.get_records.side_effect = ValueError("DB error")
        # Should not raise
        maint_view._load_records()

    def test_record_table_double_click(self, maint_view, mock_records):
        maint_view.service.get_records.return_value = mock_records
        maint_view._load_records()
        # Simulate row double-click signal
        maint_view._on_record_double_clicked(mock_records[0])
        # Should show a QMessageBox — not crashing is sufficient


# ── Tab 2: Schedules ─────────────────────────────────────────────────────

class TestQtMaintenanceViewSchedules:
    """Schedules tab."""

    def test_schedule_table_exists(self, maint_view):
        assert maint_view._schedule_table is not None

    def test_load_schedules_populates_table(self, maint_view, mock_schedules):
        maint_view.service.get_schedules.return_value = mock_schedules
        maint_view.service.predict_next_service.return_value = {
            "due_by_date": "2026-07-10",
            "due_km": 65000,
            "overdue": False,
        }
        maint_view._load_schedules()
        assert maint_view._schedule_table.rowCount() == 2

    def test_load_schedules_empty(self, maint_view):
        maint_view.service.get_schedules.return_value = []
        maint_view._load_schedules()
        assert maint_view._schedule_table.rowCount() == 0

    def test_load_schedules_handles_exception(self, maint_view):
        maint_view.service.get_schedules.side_effect = ValueError("DB error")
        maint_view._load_schedules()  # Should not raise

    def test_schedule_action_buttons_exist(self, maint_view):
        buttons = maint_view.findChildren(ActionButton)
        assert len(buttons) >= 3  # add, edit, deactivate

    def test_selected_schedule_returns_id(self, maint_view, mock_schedules):
        maint_view.service.get_schedules.return_value = mock_schedules
        maint_view.service.predict_next_service.return_value = {}
        maint_view._load_schedules()
        # Select first row
        maint_view._schedule_table.selectRow(0)
        sched_id = maint_view._selected_schedule()
        assert sched_id is not None

    def test_selected_schedule_none_when_no_selection(self, maint_view):
        assert maint_view._selected_schedule() is None

    def test_edit_schedule_no_selection_shows_info(self, maint_view):
        with patch("ui.dialogs.maintenance_view.QMessageBox.information") as mock_info:
            maint_view._edit_schedule_dialog()
            mock_info.assert_called_once()

    def test_deactivate_schedule_no_selection_shows_info(self, maint_view):
        with patch("ui.dialogs.maintenance_view.QMessageBox.information") as mock_info:
            maint_view._deactivate_schedule()
            mock_info.assert_called_once()


# ── Tab 3: Health ────────────────────────────────────────────────────────

class TestQtMaintenanceViewHealth:
    """Health tab."""

    def test_health_cards_exist(self, maint_view):
        assert len(maint_view._health_cards) == 5
        for key in ("overall", "compliance", "overdue", "recurring", "downtime"):
            assert key in maint_view._health_cards

    def test_health_detail_label_exists(self, maint_view):
        assert maint_view._health_detail is not None

    def test_load_health_sets_card_values(self, maint_view, mock_health):
        maint_view._vm.get_health.return_value = mock_health
        with patch.object(maint_view, "_load_records"):
            with patch.object(maint_view, "_load_schedules"):
                maint_view._load_health()
        # Cards should have values set
        assert "78" in maint_view._health_cards["overall"].value_label.text()

    def test_load_health_with_overdue_warning(self, maint_view, mock_health):
        maint_view._vm.get_health.return_value = mock_health
        with patch.object(maint_view, "_load_records"):
            with patch.object(maint_view, "_load_schedules"):
                maint_view._load_health()
        text = maint_view._health_detail.text()
        assert "2" in text or "overdue" in text.lower()

    def test_load_health_handles_exception(self, maint_view):
        maint_view._vm.get_health.side_effect = ValueError("Error")
        # Should not raise
        maint_view._load_health()

    def test_health_card_count_matches(self, maint_view):
        assert len(maint_view._health_cards) == 5


# ── _load_all ────────────────────────────────────────────────────────────

class TestQtMaintenanceViewLoadAll:
    """Aggregate loading."""

    def test_load_all_loads_all_tabs(self, maint_view):
        with patch.object(maint_view, "_load_records") as mock_rec:
            with patch.object(maint_view, "_load_schedules") as mock_sched:
                with patch.object(maint_view, "_load_health") as mock_health:
                    maint_view._load_all()
        mock_rec.assert_called_once()
        mock_sched.assert_called_once()
        mock_health.assert_called_once()


# ── Schedule CRUD dialogs ────────────────────────────────────────────────

class TestQtMaintenanceViewScheduleCrud:
    """Schedule add / edit / deactivate."""

    def test_add_schedule_dialog(self, maint_view):
        with patch(
            "ui.dialogs.maintenance_view._ScheduleEditDialog",
        ) as mock_dlg_cls:
            mock_dlg = MagicMock()
            mock_dlg.exec.return_value = QDialog.Accepted
            mock_dlg.get_data.return_value = {
                "type": "oil_change",
                "km": 15000.0,
                "months": 6.0,
                "fixed_date": "",
                "last_km": 50000.0,
                "last_date": "2026-01-10",
            }
            mock_dlg_cls.return_value = mock_dlg
            with patch.object(maint_view.service, "add_schedule") as mock_add:
                maint_view._add_schedule_dialog()
                mock_add.assert_called_once()

    def test_edit_schedule_dialog(self, maint_view):
        with patch.object(maint_view, "_selected_schedule", return_value=10):
            maint_view.service._fleet_repo.get_maintenance_schedule.return_value = None
            maint_view.service.get_schedules.return_value = [
                {"id": 10, "maintenance_type": "oil_change"}
            ]
            maint_view.service.predict_next_service.return_value = {}
            with patch(
                "ui.dialogs.maintenance_view._ScheduleEditDialog",
            ) as mock_dlg_cls:
                mock_dlg = MagicMock()
                mock_dlg.exec.return_value = QDialog.Accepted
                mock_dlg.get_data.return_value = {
                    "type": "oil_change", "km": 15000.0, "months": 6.0,
                    "fixed_date": "", "last_km": 50000.0, "last_date": "2026-01-10",
                }
                mock_dlg_cls.return_value = mock_dlg
                with patch.object(maint_view.service, "update_schedule") as mock_upd:
                    maint_view._edit_schedule_dialog()
                    mock_upd.assert_called_once()

    def test_deactivate_schedule(self, maint_view):
        with patch.object(maint_view, "_selected_schedule", return_value=10):
            with patch("ui.dialogs.maintenance_view.QMessageBox.question", return_value=16):  # QMessageBox.Yes
                with patch.object(maint_view.service, "update_schedule") as mock_upd:
                    maint_view._deactivate_schedule()
                    mock_upd.assert_called_once_with(schedule_id=10, active=0)

    def test_deactivate_schedule_declined(self, maint_view):
        with patch.object(maint_view, "_selected_schedule", return_value=10):
            with patch("ui.dialogs.maintenance_view.QMessageBox.question", return_value=65536):  # QMessageBox.No
                with patch.object(maint_view.service, "update_schedule") as mock_upd:
                    maint_view._deactivate_schedule()
                    mock_upd.assert_not_called()


# ── _ScheduleEditDialog ────────────────────────────────────────────────

class TestScheduleEditDialog:
    """The nested schedule-editing dialog."""

    def test_create_new_schedule_dialog(self, qt_widget, qtbot):
        dlg = _ScheduleEditDialog(parent=qt_widget, existing=None)
        qtbot.addWidget(dlg)
        assert isinstance(dlg, _ScheduleEditDialog)
        dlg.close()

    def test_edit_existing_schedule(self, qt_widget, qtbot):
        existing = {
            "maintenance_type": "oil_change",
            "interval_km": 15000.0,
            "interval_months": 6,
            "last_done_km": 50000.0,
            "last_done_date": "2026-01-10",
            "fixed_expiry_date": "",
        }
        dlg = _ScheduleEditDialog(parent=qt_widget, existing=existing)
        qtbot.addWidget(dlg)
        assert dlg._km_spin.value() == 15000.0
        assert dlg._month_spin.value() == 6
        dlg.close()

    def test_get_data_returns_dict(self, qt_widget, qtbot):
        dlg = _ScheduleEditDialog(parent=qt_widget, existing=None)
        qtbot.addWidget(dlg)
        data = dlg.get_data()
        assert isinstance(data, dict)
        assert "type" in data
        assert "km" in data
        assert "months" in data
        dlg.close()

    def test_get_data_type_is_valid(self, qt_widget, qtbot):
        dlg = _ScheduleEditDialog(parent=qt_widget, existing=None)
        qtbot.addWidget(dlg)
        data = dlg.get_data()
        assert data["type"] in [mt.value for mt in MaintType]
        dlg.close()

    def test_form_has_required_fields(self, qt_widget, qtbot):
        dlg = _ScheduleEditDialog(parent=qt_widget, existing=None)
        qtbot.addWidget(dlg)
        assert isinstance(dlg._type_combo, QComboBox)
        assert isinstance(dlg._km_spin, QDoubleSpinBox)
        assert isinstance(dlg._month_spin, QSpinBox)
        assert isinstance(dlg._last_km_spin, QDoubleSpinBox)
        assert isinstance(dlg._last_date_edit, QDateEdit)
        assert isinstance(dlg._fixed_date_edit, QDateEdit)
        dlg.close()

    def test_has_save_and_cancel_buttons(self, qt_widget, qtbot):
        dlg = _ScheduleEditDialog(parent=qt_widget, existing=None)
        qtbot.addWidget(dlg)
        buttons = dlg.findChildren(QPushButton)
        assert len(buttons) >= 2
        dlg.close()

    def test_interval_defaults_from_maint_type(self, qt_widget, qtbot):
        """New dialog should pick default intervals for the first MaintType."""
        dlg = _ScheduleEditDialog(parent=qt_widget, existing=None)
        qtbot.addWidget(dlg)
        # Should have some default set
        assert dlg._month_spin.value() >= 0
        dlg.close()


# ── i18n ─────────────────────────────────────────────────────────────────

class TestQtMaintenanceViewI18n:
    """Internationalisation."""

    def test_on_language_changed_does_not_crash(self, maint_view):
        maint_view._on_language_changed("ro")

    def test_i18n_tag(self, maint_view):
        lbl = maint_view._title_lbl
        maint_view._i18n_tag(lbl, "maint.test_key")
        assert len(maint_view._i18n_widgets) >= 1

    def test_close_event_unregisters_listener(self, maint_view):
        with patch(
            "ui.dialogs.maintenance_view.unregister_listener",
        ) as mock_unreg:
            maint_view.close()
            mock_unreg.assert_called_once_with(maint_view._language_callback)
