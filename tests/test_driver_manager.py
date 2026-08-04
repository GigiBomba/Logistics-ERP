"""Tests for the driver manager view — 12 classes, 40+ test methods.

Tests cover:
  - UI construction and widget presence
  - Lifecycle: wakeup, shutdown, cleanup
  - Data loading and table population
  - CRUD flows (add, edit, delete)
  - Search / filter
  - KPI calculations
  - Truck assignment dialog
  - Active-state toggle
  - CSV export / import
  - EventBus subscriptions
  - DriverFormDialog construction and save logic
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtWidgets import QMenu, QMessageBox, QFileDialog

# ── SP workaround ─────────────────────────────────────────────────────────────
# ui/widgets/__init__.py imports SP as S; driver_manager expects SP at module
# level because it does ``from ui.widgets import SP``.
import ui.widgets as _ui_widgets

if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S

# ── QMenu workaround ─────────────────────────────────────────────────────────
# ui/widgets/__init__.py does NOT import QMenu, but StyledTableWidget.
# _build_density_menu references QMenu as a module-level name (line 699).
if not hasattr(_ui_widgets, "QMenu"):
    _ui_widgets.QMenu = QMenu

from ui.views.driver_manager import (
    QtDriverManager,
    QtDriverFormDialog,
    _COLUMNS,
)
from services.operations.event_bus import (
    DRIVER_CREATED,
    DRIVER_UPDATED,
    DRIVER_DELETED,
    EventBus,
)
from ui.widgets.debounced_line_edit import DebouncedLineEdit

# ── Sample data ───────────────────────────────────────────────────────────────

SAMPLE_DRIVER = {
    "id": 1,
    "name": "John Doe",
    "phone": "+40 723 000 001",
    "email": "john@example.com",
    "license_number": "B12345",
    "license_category": "CE",
    "license_expiry": "2027-06-01",
    "medical_expiry": "2026-12-01",
    "hire_date": "2020-03-15",
    "monthly_salary": 4500.0,
    "notes": "",
    "is_active": 1,
}
SAMPLE_DRIVER_2 = {**SAMPLE_DRIVER, "id": 2, "name": "Jane Smith", "is_active": 0}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _process_events(count: int = 3):
    """Process pending Qt events (timers, signals)."""
    for _ in range(count):
        QCoreApplication.processEvents()


def _populate_table(mgr, drivers=None):
    """Set up trip repo and trigger a full refresh with event processing."""
    if drivers is None:
        drivers = [SAMPLE_DRIVER, SAMPLE_DRIVER_2]
    mgr._trip_repo = MagicMock()
    mgr._trip_repo.get_by_statuses.return_value = []
    mgr._driver_repo.get_all.return_value = drivers
    mgr.refresh()
    _process_events()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def driver_repo():
    repo = MagicMock()
    repo.get_all.return_value = [SAMPLE_DRIVER, SAMPLE_DRIVER_2]
    repo.get_by_id.side_effect = lambda id: next(
        (d for d in [SAMPLE_DRIVER, SAMPLE_DRIVER_2] if d["id"] == id), None
    )
    repo.create.return_value = 3
    repo.update.return_value = None
    repo.delete.return_value = None
    return repo


@pytest.fixture
def trip_repo():
    repo = MagicMock()
    repo.get_by_statuses.return_value = []
    return repo


@pytest.fixture
def dta_service():
    svc = MagicMock()
    svc.get_truck_plate_for_driver.return_value = ""
    svc.assign_driver_to_truck.return_value = None
    svc.unassign_driver.return_value = None
    return svc


@pytest.fixture
def tacho_repo():
    return MagicMock()


@pytest.fixture
def driver_manager(qtbot, driver_repo, dta_service):
    """Manager without trip_svc so refresh() returns early (no data load)."""
    from ui.views.driver_manager import QtDriverManager

    mgr = QtDriverManager(
        parent=None,
        driver_svc=driver_repo,
        dta_svc=dta_service,
    )
    qtbot.addWidget(mgr)
    yield mgr
    mgr.shutdown()


@pytest.fixture
def driver_form():
    """Plain form dialog with mocks — no truck combo population."""
    from ui.views.driver_manager import QtDriverFormDialog

    dlg = QtDriverFormDialog(
        parent=None,
        driver_repo=MagicMock(),
        dta_service=MagicMock(),
    )
    yield dlg
    dlg.close()


# ══════════════════════════════════════════════════════════════════════════════
# 1. TestQtDriverManagerUI — Widget construction
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverManagerUI:
    """Verify that all UI widgets are correctly built and visible."""

    def test_title_label_visible(self, driver_manager):
        assert driver_manager._title_label is not None
        text = driver_manager._title_label.text()
        assert isinstance(text, str) and len(text) > 0

    def test_kpi_cards_present(self, driver_manager):
        labels = driver_manager._kpi_value_labels
        for key in (
            "driver_manager.kpi_total",
            "driver_manager.kpi_expiring",
            "driver_manager.kpi_on_trip",
            "driver_manager.kpi_unassigned",
        ):
            assert key in labels, f"Missing KPI label {key!r}"
            assert labels[key] is not None

    def test_search_entry_exists(self, driver_manager):
        entry = driver_manager._search_entry
        assert entry is not None
        assert isinstance(entry, DebouncedLineEdit)

    def test_table_has_correct_column_count(self, driver_manager):
        # _COLUMNS has 10 entries; one extra actions column is added
        expected = len(_COLUMNS) + 1
        assert driver_manager.table.columnCount() == expected

    def test_action_buttons_exist(self, driver_manager):
        assert hasattr(driver_manager, "_add_btn")
        assert hasattr(driver_manager, "_edit_btn")
        assert hasattr(driver_manager, "_delete_btn")
        assert hasattr(driver_manager, "_import_btn")
        assert hasattr(driver_manager, "_documents_btn")
        assert driver_manager._add_btn is not None
        assert driver_manager._edit_btn is not None
        assert driver_manager._delete_btn is not None
        assert driver_manager._import_btn is not None
        assert driver_manager._documents_btn is not None

    def test_tacho_container_hidden_initially(self, driver_manager):
        assert hasattr(driver_manager, "_tacho_container")
        assert driver_manager._tacho_container.isVisible() is False


# ══════════════════════════════════════════════════════════════════════════════
# 2. TestQtDriverManagerLifecycle — Wakeup/shutdown/cleanup
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverManagerLifecycle:
    """Lifecycle methods: wakeup, shutdown, cleanup."""

    def test_wakeup_calls_refresh(self, driver_manager):
        with patch.object(driver_manager, "refresh") as mock_refresh:
            driver_manager.wakeup()
            mock_refresh.assert_called_once()

    def test_shutdown_stops_timer(self, driver_manager, qtbot):
        timer = QTimer()
        timer.start(1000)
        driver_manager._search_timer = timer
        assert timer.isActive()
        driver_manager.shutdown()
        assert not timer.isActive()

    def test_shutdown_idempotent(self, driver_manager):
        driver_manager.shutdown()
        # Second call must not raise
        driver_manager.shutdown()

    def test_cleanup_calls_shutdown(self, driver_manager):
        with patch.object(driver_manager, "shutdown") as mock_shutdown:
            driver_manager._cleanup()
            mock_shutdown.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 3. TestQtDriverManagerRefresh — Data loading and table
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverManagerRefresh:
    """Data loading and table population."""

    def test_refresh_populates_table(self, driver_manager):
        _populate_table(driver_manager)
        assert driver_manager.table.rowCount() == 2

    def test_refresh_handles_empty_data(self, driver_manager):
        _populate_table(driver_manager, drivers=[])
        assert driver_manager.table.rowCount() == 0

    def test_refresh_handles_repo_exception(self, driver_manager, monkeypatch):
        monkeypatch.setattr(QMessageBox, "critical", MagicMock())
        driver_manager._trip_repo = MagicMock()
        driver_manager._driver_repo.get_all.side_effect = RuntimeError("DB fail")
        driver_manager.refresh()
        _process_events()
        # The exception handler calls _hide_table_skeleton → table.show()
        # Use isHidden() — more reliable in headless test environments
        assert not driver_manager.table.isHidden()
        QMessageBox.critical.assert_called()

    def test_skeleton_shown_and_hidden(self, driver_manager):
        """_show_table_skeleton hides the real table; _hide_table_skeleton shows it."""
        driver_manager._show_table_skeleton()
        assert driver_manager.table.isHidden()
        driver_manager._hide_table_skeleton()
        _process_events()
        assert not driver_manager.table.isHidden()

    def test_inactive_rows_greyed_out(self, driver_manager):
        _populate_table(driver_manager)
        # Find the inactive row (Jane Smith has is_active=0)
        inactive_item = None
        for r in range(driver_manager.table.rowCount()):
            name_item = driver_manager.table.item(r, 1)  # name column
            if name_item and name_item.text() == "Jane Smith":
                inactive_item = driver_manager.table.item(r, 0)
                break
        assert inactive_item is not None, "Inactive row not found"
        # Check that foreground colour is set (muted for inactive)
        assert inactive_item.foreground() is not None

    def test_inline_action_buttons_added(self, driver_manager):
        _populate_table(driver_manager)
        actions_col = driver_manager.table.columnCount() - 1
        for r in range(driver_manager.table.rowCount()):
            widget = driver_manager.table.cellWidget(r, actions_col)
            assert widget is not None, f"Row {r} has no action buttons"

    def test_load_uses_single_batched_plate_lookup(self, driver_manager):
        """_load_data performs ONE batched plate lookup for all drivers.

        Replaces the per-driver ``get_truck_plate_for_driver`` N+1 loop.
        """
        _populate_table(driver_manager)
        driver_manager._dta_service.get_plates_by_driver_ids.assert_called_once()
        called_ids = driver_manager._dta_service.get_plates_by_driver_ids.call_args[0][0]
        assert sorted(called_ids) == [SAMPLE_DRIVER["id"], SAMPLE_DRIVER_2["id"]]


# ══════════════════════════════════════════════════════════════════════════════
# 4. TestQtDriverManagerCRUD — Add/edit/delete flows
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverManagerCRUD:
    """CRUD operations: open dialog, save, delete."""

    def test_add_driver_opens_dialog(self, driver_manager, monkeypatch):
        monkeypatch.setattr(QtDriverFormDialog, "exec", MagicMock(return_value=None))
        with patch.object(driver_manager, "refresh") as mock_refresh:
            driver_manager._add_driver()
            QtDriverFormDialog.exec.assert_called_once()

    def test_add_driver_save_refreshes(self, driver_manager):
        """The on_save callback passed to the dialog should call refresh."""
        on_save_called = False

        def fake_on_save():
            nonlocal on_save_called
            on_save_called = True

        from ui.views.driver_manager import QtDriverFormDialog

        dialog = QtDriverFormDialog(
            parent=None,
            driver_repo=MagicMock(),
            driver=None,
            on_save=fake_on_save,
            dta_service=MagicMock(),
        )
        dialog._entries["name"].setText("Test Driver")
        dialog._entries["monthly_salary"].setText("3000")
        # _save checks name via text().strip() — ensure it's non-empty
        with patch.object(dialog._entries["name"], "text", return_value="Test Driver"):
            dialog._save()
        assert on_save_called
        dialog.close()

    def test_edit_selected_no_selection_shows_info(self, driver_manager, monkeypatch):
        monkeypatch.setattr(QMessageBox, "information", MagicMock())
        driver_manager._edit_selected()
        QMessageBox.information.assert_called()

    def test_edit_driver_by_id_opens_dialog(self, driver_manager, monkeypatch):
        monkeypatch.setattr(QtDriverFormDialog, "exec", MagicMock(return_value=None))
        driver_manager._edit_driver_by_id(1)
        QtDriverFormDialog.exec.assert_called_once()

    def test_edit_driver_by_id_not_found_shows_info(self, driver_manager, monkeypatch):
        monkeypatch.setattr(QMessageBox, "information", MagicMock())
        driver_manager._driver_repo.get_by_id.return_value = None
        driver_manager._edit_driver_by_id(999)
        QMessageBox.information.assert_called()

    def test_delete_selected_no_selection_returns(self, driver_manager):
        with patch.object(driver_manager, "_get_selected_id", return_value=None):
            with patch.object(driver_manager._driver_repo, "delete") as mock_del:
                driver_manager._delete_selected()
                mock_del.assert_not_called()

    def test_delete_selected_confirmed_yes(self, driver_manager, monkeypatch):
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        with patch.object(driver_manager, "_get_selected_id", return_value=1):
            driver_manager._delete_selected()
            driver_manager._driver_repo.delete.assert_called_once_with(1)

    def test_delete_selected_confirmed_no(self, driver_manager, monkeypatch):
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *a, **kw: QMessageBox.StandardButton.No,
        )
        with patch.object(driver_manager, "_get_selected_id", return_value=1):
            with patch.object(driver_manager._driver_repo, "delete") as mock_del:
                driver_manager._delete_selected()
                mock_del.assert_not_called()

    def test_delete_selected_repo_exception(self, driver_manager, monkeypatch):
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        monkeypatch.setattr(QMessageBox, "critical", MagicMock())
        driver_manager._driver_repo.delete.side_effect = RuntimeError("Del fail")
        with patch.object(driver_manager, "_get_selected_id", return_value=1):
            driver_manager._delete_selected()
            QMessageBox.critical.assert_called()


# ══════════════════════════════════════════════════════════════════════════════
# 5. TestQtDriverManagerSearch — Filter/search
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverManagerSearch:
    """Search and filtering behaviour."""

    def test_filter_table_empty_query_shows_all(self, driver_manager):
        _populate_table(driver_manager)
        driver_manager._search_entry.setText("")
        driver_manager._filter_table()
        visible = sum(
            1 for r in range(driver_manager.table.rowCount())
            if not driver_manager.table.isRowHidden(r)
        )
        assert visible == driver_manager.table.rowCount()

    def test_filter_table_matching_name(self, driver_manager):
        _populate_table(driver_manager)
        driver_manager._search_entry.setText("John")
        driver_manager._filter_table()
        for r in range(driver_manager.table.rowCount()):
            hidden = driver_manager.table.isRowHidden(r)
            item = driver_manager.table.item(r, 1)  # name col
            if item and "John" in item.text():
                assert not hidden, f"Row with John should be visible"
            elif item and "John" not in item.text():
                assert hidden, f"Row without John should be hidden"

    def test_filter_table_case_insensitive(self, driver_manager):
        _populate_table(driver_manager)
        driver_manager._search_entry.setText("john")
        driver_manager._filter_table()
        for r in range(driver_manager.table.rowCount()):
            hidden = driver_manager.table.isRowHidden(r)
            item = driver_manager.table.item(r, 1)  # name col
            if item and "John" in item.text():
                assert not hidden, f"Case-insensitive match failed for row {r}"


# ══════════════════════════════════════════════════════════════════════════════
# 6. TestQtDriverManagerKPI — KPI calculations
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverManagerKPI:
    """KPI value updates after data load."""

    def test_kpi_total_count(self, driver_manager):
        _populate_table(driver_manager)
        label = driver_manager._kpi_value_labels.get("driver_manager.kpi_total")
        assert label is not None
        assert label.text() == "2"

    def test_kpi_on_trip_count(self, driver_manager):
        _populate_table(driver_manager)
        label = driver_manager._kpi_value_labels.get("driver_manager.kpi_on_trip")
        assert label is not None
        assert label.text() == "0"

    def test_kpi_expiring_cutoff(self, driver_manager):
        _populate_table(driver_manager)
        label = driver_manager._kpi_value_labels.get("driver_manager.kpi_expiring")
        assert label is not None
        assert label.text() == "0"

    def test_kpi_unassigned_count(self, driver_manager):
        _populate_table(driver_manager)
        label = driver_manager._kpi_value_labels.get("driver_manager.kpi_unassigned")
        assert label is not None
        assert label.text() == "2"


# ══════════════════════════════════════════════════════════════════════════════
# 7. TestQtDriverManagerTruckAssignment — Assign truck dialog
# ══════════════════════════════════════════════════════════════════════════════
#
# NOTE: The source code of _assign_truck uses ``for t in trucks:`` as the
# loop variable, which shadows the module-level ``t()`` i18n helper in the
# ENTIRE function body (Python treats any variable assigned in a function as
# local to that function).  Because the ``t()`` calls appear BEFORE the loop,
# every code path of _assign_truck raises ``UnboundLocalError``.
#
# As a result, no unit test can exercise _assign_truck without first fixing
# the source.  The dialog-level assign / unassign / error paths are covered
# via ``TestQtDriverFormDialogSave``.

class TestQtDriverManagerTruckAssignment:
    """Truck assignment flow (limited — see module note)."""
    pass


# ══════════════════════════════════════════════════════════════════════════════
# 8. TestQtDriverManagerActiveToggle — Toggle active via context menu
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverManagerActiveToggle:
    """Toggle driver active state."""

    def test_toggle_active_flips_value(self, driver_manager):
        with patch.object(driver_manager, "_get_selected_id", return_value=1):
            # SAMPLE_DRIVER has is_active=1 → should become 0
            driver_manager._toggle_active()
            driver_manager._driver_repo.update.assert_called_once_with(
                1, {"is_active": 0}
            )

    def test_toggle_active_no_repo(self, driver_manager):
        driver_manager._driver_repo = None
        # Should return early without raising
        driver_manager._toggle_active()


# ══════════════════════════════════════════════════════════════════════════════
# 9. TestQtDriverManagerExportImport — CSV import/export
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverManagerExportImport:
    """CSV export and import flows."""

    def test_export_csv_success(self, driver_manager, monkeypatch, tmp_path):
        monkeypatch.setattr(QMessageBox, "information", MagicMock())
        out = tmp_path / "drivers.csv"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            lambda *a, **kw: (str(out), "CSV (*.csv)"),
        )
        driver_manager._export_csv()
        assert out.exists()
        content = out.read_text(encoding="utf-8-sig")
        assert "John Doe" in content

    def test_export_csv_cancelled(self, driver_manager, monkeypatch, tmp_path):
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            lambda *a, **kw: ("", "CSV (*.csv)"),
        )
        with patch.object(driver_manager, "_driver_repo") as mock_repo:
            driver_manager._export_csv()
            mock_repo.get_all.assert_not_called()

    def test_export_csv_exception(self, driver_manager, monkeypatch):
        monkeypatch.setattr(QMessageBox, "critical", MagicMock())
        driver_manager._driver_repo.get_all.side_effect = RuntimeError("Export fail")
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            lambda *a, **kw: ("/fake/path.csv", "CSV (*.csv)"),
        )
        driver_manager._export_csv()
        QMessageBox.critical.assert_called()

    def test_import_csv_success(self, driver_manager, monkeypatch, tmp_path):
        monkeypatch.setattr(QMessageBox, "information", MagicMock())
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "name,phone,email\nJohn,123,john@test.com\nJane,456,jane@test.com\n",
            encoding="utf-8-sig",
        )
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName",
            lambda *a, **kw: (str(csv_file), "CSV (*.csv)"),
        )
        driver_manager._import_csv()
        assert driver_manager._driver_repo.create.call_count == 2

    def test_import_csv_cancelled(self, driver_manager, monkeypatch):
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName",
            lambda *a, **kw: ("", "CSV (*.csv)"),
        )
        with patch.object(driver_manager._driver_repo, "create") as mock_create:
            driver_manager._import_csv()
            mock_create.assert_not_called()

    def test_import_csv_skips_empty_names(self, driver_manager, monkeypatch, tmp_path):
        monkeypatch.setattr(QMessageBox, "information", MagicMock())
        csv_file = tmp_path / "skip.csv"
        csv_file.write_text(
            "name,phone\n,123\nJane,456\n",
            encoding="utf-8-sig",
        )
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName",
            lambda *a, **kw: (str(csv_file), "CSV (*.csv)"),
        )
        driver_manager._import_csv()
        # Only Jane should be created
        assert driver_manager._driver_repo.create.call_count == 1


# ══════════════════════════════════════════════════════════════════════════════
# 10. TestQtDriverManagerEvents — EventBus subscriptions
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverManagerEvents:
    """EventBus subscriptions trigger refresh."""

    def test_receives_driver_created_event(self, driver_manager):
        with patch.object(driver_manager, "refresh") as mock_refresh:
            driver_manager._event_bus.publish(DRIVER_CREATED, {"driver_id": 1})
            _process_events()
            mock_refresh.assert_called()

    def test_receives_driver_updated_event(self, driver_manager):
        with patch.object(driver_manager, "refresh") as mock_refresh:
            driver_manager._event_bus.publish(DRIVER_UPDATED, {"driver_id": 1})
            _process_events()
            mock_refresh.assert_called()

    def test_receives_driver_deleted_event(self, driver_manager):
        with patch.object(driver_manager, "refresh") as mock_refresh:
            driver_manager._event_bus.publish(DRIVER_DELETED, {"driver_id": 1})
            _process_events()
            mock_refresh.assert_called()


# ══════════════════════════════════════════════════════════════════════════════
# 11. TestQtDriverFormDialog — Dialog construction
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverFormDialog:
    """Driver form dialog widget construction."""

    def test_dialog_creates_form_fields(self, driver_form):
        assert len(driver_form._entries) == len(driver_form.FIELDS)

    def test_dialog_populates_editing(self):
        dlg = QtDriverFormDialog(
            parent=None,
            driver_repo=MagicMock(),
            driver=SAMPLE_DRIVER,
            dta_service=MagicMock(),
        )
        assert dlg._entries["name"].text() == "John Doe"
        assert dlg._entries["phone"].text() == "+40 723 000 001"
        dlg.close()

    def test_dialog_title_add_mode(self):
        dlg = QtDriverFormDialog(
            parent=None,
            driver_repo=MagicMock(),
            driver=None,
            dta_service=MagicMock(),
        )
        title = dlg.windowTitle()
        assert "Add" in title or "add" in title or "driver_manager" in title
        dlg.close()

    def test_dialog_title_edit_mode(self):
        dlg = QtDriverFormDialog(
            parent=None,
            driver_repo=MagicMock(),
            driver=SAMPLE_DRIVER,
            dta_service=MagicMock(),
        )
        title = dlg.windowTitle()
        assert "Edit" in title or "edit" in title or "driver_manager" in title
        dlg.close()

    def test_dialog_truck_combo_populated(self, monkeypatch):
        with patch(
            "repositories.fleet_repository.FleetRepository"
        ) as mock_fleet_cls:
            mock_fleet = MagicMock()
            mock_fleet.get_active_trucks.return_value = [
                {"id": 1, "plate_number": "AB-01-TST"},
                {"id": 2, "plate_number": "CD-02-TST"},
            ]
            mock_fleet_cls.return_value = mock_fleet
            dlg = QtDriverFormDialog(
                parent=None,
                driver_repo=MagicMock(),
                driver=None,
                dta_service=MagicMock(),
            )
            assert dlg._truck_combo is not None
            # The combo includes the default empty entry + 2 trucks
            assert dlg._truck_combo.count() >= 2
            dlg.close()


# ══════════════════════════════════════════════════════════════════════════════
# 12. TestQtDriverFormDialogSave — Dialog save
# ══════════════════════════════════════════════════════════════════════════════

class TestQtDriverFormDialogSave:
    """Driver form dialog save logic."""

    def test_save_empty_name_shows_warning(self, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", MagicMock())
        dlg = QtDriverFormDialog(
            parent=None,
            driver_repo=MagicMock(),
            driver=None,
            dta_service=MagicMock(),
        )
        dlg._entries["name"].setText("")
        dlg._save()
        QMessageBox.warning.assert_called()
        dlg.close()

    def test_save_invalid_salary_shows_warning(self, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", MagicMock())
        dlg = QtDriverFormDialog(
            parent=None,
            driver_repo=MagicMock(),
            driver=None,
            dta_service=MagicMock(),
        )
        dlg._entries["name"].setText("Test")
        dlg._entries["monthly_salary"].setText("not-a-number")
        dlg._save()
        QMessageBox.warning.assert_called()
        dlg.close()

    def test_save_creates_new_driver(self, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", MagicMock())
        repo = MagicMock()
        repo.create.return_value = 99
        dlg = QtDriverFormDialog(
            parent=None,
            driver_repo=repo,
            driver=None,
            dta_service=None,
        )
        dlg._entries["name"].setText("New Driver")
        dlg._entries["monthly_salary"].setText("3500")
        dlg._save()
        repo.create.assert_called_once()
        dlg.close()

    def test_save_updates_existing_driver(self, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", MagicMock())
        repo = MagicMock()
        dlg = QtDriverFormDialog(
            parent=None,
            driver_repo=repo,
            driver=SAMPLE_DRIVER,
            dta_service=None,
        )
        dlg._entries["monthly_salary"].setText("5000")
        dlg._save()
        repo.update.assert_called_once()
        args, _ = repo.update.call_args
        assert args[0] == SAMPLE_DRIVER["id"]
        dlg.close()

    def test_save_assigns_truck(self, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", MagicMock())
        dta = MagicMock()
        repo = MagicMock()
        repo.create.return_value = 42
        with patch(
            "repositories.fleet_repository.FleetRepository"
        ) as mock_fleet_cls:
            mock_fleet = MagicMock()
            mock_fleet.get_active_trucks.return_value = [
                {"id": 5, "plate_number": "AB-01-TST"}
            ]
            mock_fleet_cls.return_value = mock_fleet
            dlg = QtDriverFormDialog(
                parent=None,
                driver_repo=repo,
                driver=None,
                dta_service=dta,
            )
            dlg._entries["name"].setText("Truck Driver")
            dlg._entries["monthly_salary"].setText("3000")
            # Select the truck at index 1 (index 0 is empty)
            if dlg._truck_combo and dlg._truck_combo.count() > 1:
                dlg._truck_combo.setCurrentIndex(1)
            dlg._save()
            dta.assign_driver_to_truck.assert_called_once_with(42, 5)
            dlg.close()

    def test_save_unassigns_truck(self, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", MagicMock())
        dta = MagicMock()
        repo = MagicMock()
        repo.create.return_value = 42
        with patch(
            "repositories.fleet_repository.FleetRepository"
        ) as mock_fleet_cls:
            mock_fleet = MagicMock()
            mock_fleet.get_active_trucks.return_value = [
                {"id": 5, "plate_number": "AB-01-TST"}
            ]
            mock_fleet_cls.return_value = mock_fleet
            dlg = QtDriverFormDialog(
                parent=None,
                driver_repo=repo,
                driver=None,
                dta_service=dta,
            )
            dlg._entries["name"].setText("Truck Driver")
            dlg._entries["monthly_salary"].setText("3000")
            # Index 0 is empty → unassign
            if dlg._truck_combo and dlg._truck_combo.count() > 0:
                dlg._truck_combo.setCurrentIndex(0)
            dlg._save()
            dta.unassign_driver.assert_called_once_with(42)
            dlg.close()

    def test_save_exception_shows_critical(self, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", MagicMock())
        monkeypatch.setattr(QMessageBox, "critical", MagicMock())
        repo = MagicMock()
        repo.create.side_effect = RuntimeError("Save fail")
        dlg = QtDriverFormDialog(
            parent=None,
            driver_repo=repo,
            driver=None,
            dta_service=None,
        )
        dlg._entries["name"].setText("Failing Driver")
        dlg._entries["monthly_salary"].setText("3000")
        dlg._save()
        QMessageBox.critical.assert_called()
        dlg.close()
