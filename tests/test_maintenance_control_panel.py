"""Tests for the maintenance control panel (refactored Model/View architecture).

Replaces the previous test file that tested the old architecture.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_vm():
    """Mock MaintenanceViewModel with alert_model and tacho_model."""
    from PySide6.QtGui import QStandardItemModel
    vm = MagicMock()
    vm.alert_model = QStandardItemModel(0, 3)
    # tacho_model needs a header_width() method expected by the control panel
    class _TachoModel(QStandardItemModel):
        def header_width(self, col): return 100
    vm.tacho_model = _TachoModel(0, 5)
    vm.get_summary.return_value = {
        "avg_health": 85,
        "trucks_needing_service": 3,
        "overdue_schedules": 1,
        "cost_30d": 1500.0,
        "total_cost": 45000.0,
    }
    return vm


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    return ops


@pytest.fixture
def mock_prefs():
    return MagicMock()


@pytest.fixture
def maintenance_control(qtbot, mock_db, mock_ops, mock_prefs, mock_vm):
    """Create QtMaintenanceControlPanel with mocked dependencies."""
    from PySide6.QtWidgets import QWidget
    _real_fuel_panel = QWidget()
    patchers = [
        patch("ui.views.maintenance_control_panel.MaintenanceViewModel", return_value=mock_vm),
        patch("ui.views.maintenance_control_panel.OperationsEngine", return_value=mock_ops),
        patch("ui.views.maintenance_control_panel.QtFuelPricePanel", return_value=_real_fuel_panel),
    ]
    for p in patchers:
        p.start()

    from ui.views.maintenance_control_panel import QtMaintenanceControlPanel

    widget = QtMaintenanceControlPanel(
        parent=None,
        db=mock_db,
        prefs=mock_prefs,
        ops=mock_ops,
    )
    qtbot.addWidget(widget)
    yield widget

    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        widget.shutdown()
    for p in patchers:
        p.stop()


# =========================================================================
# Tests
# =========================================================================

class TestQtMaintenanceControlPanel:
    """Suite of tests for QtMaintenanceControlPanel (refactored)."""

    def test_initialization(self, maintenance_control):
        """Widget initializes without crashing and stores VM reference."""
        assert maintenance_control is not None
        assert hasattr(maintenance_control, "_vm")

    def test_header_renders(self, maintenance_control):
        """Header contains a PageTitle widget (QLabel with header class)."""
        from PySide6.QtWidgets import QLabel
        titles = maintenance_control.findChildren(QLabel)
        assert len(titles) >= 1

    def test_kpi_row_renders(self, maintenance_control):
        """KPI widgets dict contains expected keys."""
        expected_keys = {"avg_health", "trucks_needing_service",
                         "overdue_schedules", "cost_30d", "total_cost"}
        assert expected_keys.issubset(maintenance_control._kpi_widgets.keys())
        assert expected_keys.issubset(maintenance_control._kpi_value_labels.keys())

    def test_tacho_table_renders(self, maintenance_control):
        """Tacho QTableView exists."""
        assert hasattr(maintenance_control, "_tacho_table")
        assert maintenance_control._tacho_table is not None

    def test_filter_bar_renders(self, maintenance_control):
        """Filter bar components exist."""
        assert maintenance_control._cb_critical is not None
        assert maintenance_control._cb_warning is not None
        assert maintenance_control._cb_info is not None
        assert maintenance_control._c_type is not None
        assert maintenance_control._e_truck is not None
        assert maintenance_control._e_trip is not None
        assert maintenance_control._cb_show_resolved is not None

    def test_severity_checkboxes_default_checked(self, maintenance_control):
        """All severity checkboxes start checked."""
        assert maintenance_control._cb_critical.isChecked()
        assert maintenance_control._cb_warning.isChecked()
        assert maintenance_control._cb_info.isChecked()

    def test_filter_type_combo_has_items(self, maintenance_control):
        """Type combobox has items (All + AlertTypes)."""
        assert maintenance_control._c_type.count() >= 2

    def test_alert_list_renders(self, maintenance_control):
        """QListView for alerts exists."""
        assert hasattr(maintenance_control, "_alert_list")
        assert maintenance_control._alert_list is not None

    def test_fuel_panel_renders(self, maintenance_control):
        """Fuel price panel exists."""
        assert hasattr(maintenance_control, "_fuel_panel")

    def test_shimmer_starts_and_stops(self, maintenance_control):
        """Shimmer timer starts on init and stops on data change."""
        assert maintenance_control._shimmer_timer.isActive()
        # Simulate data_changed signal to stop shimmer
        maintenance_control._on_data_changed()
        assert not maintenance_control._shimmer_timer.isActive()

    def test_shutdown_cleanup(self, maintenance_control):
        """shutdown() stops timers and sets closed flag."""
        maintenance_control.shutdown()
        assert maintenance_control._closed is True
        assert not maintenance_control._refresh_timer.isActive()

    def test_wakeup_refreshes_vm(self, maintenance_control, mock_vm):
        """wakeup() triggers ViewModel refresh_now."""
        before = mock_vm.refresh_now.call_count
        maintenance_control.wakeup()
        assert mock_vm.refresh_now.call_count == before + 1

    def test_filter_changed_updates_proxy(self, maintenance_control, mock_vm):
        """Toggling a filter notifies the proxy model."""
        with patch.object(maintenance_control._alert_proxy, "set_severity_filter") as mock_set:
            maintenance_control._cb_critical.setChecked(False)
            # _on_filter_changed should have been called via signal
            mock_set.assert_called()

    def test_kpis_update_from_summary(self, maintenance_control, mock_vm):
        """_update_kpis reads from ViewModel summary and sets labels."""
        maintenance_control._update_kpis()
        # Avg health label should read "85/100"
        assert hasattr(maintenance_control, "_health_progress")
        assert maintenance_control._health_progress.value() == 85
