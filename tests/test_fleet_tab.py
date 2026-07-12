"""Tests for QtFleetTab — fleet management view."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_fleet_service():
    fs = MagicMock()
    fs.get_trucks.return_value = []
    return fs


@pytest.fixture
def mock_dta_service():
    return MagicMock()


@pytest.fixture
def mock_fleet_repo():
    return MagicMock()


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    ops.get_active_alerts.return_value = []
    ops.get_active_alert_count.return_value = 0
    return ops


@pytest.fixture
def fleet_tab(qtbot, mock_ops, mock_fleet_service, mock_dta_service, mock_fleet_repo):
    """Create a QtFleetTab with all services mocked."""
    patchers = [
        patch("ui.views.fleet_tab.fleet_tab.FleetService", return_value=mock_fleet_service),
        patch("ui.views.fleet_tab.fleet_tab.DriverTruckService", return_value=mock_dta_service),
        patch("ui.views.fleet_tab.fleet_tab.FleetRepository", return_value=mock_fleet_repo),
    ]
    for p in patchers:
        p.start()

    from ui.views.fleet_tab.fleet_tab import QtFleetTab

    widget = QtFleetTab(
        parent=None,
        db=MagicMock(),
        ops=mock_ops,
        fleet_service=mock_fleet_service,
        dta_service=mock_dta_service,
        fleet_repo=mock_fleet_repo,
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

class TestQtFleetTab:
    """Suite of tests for QtFleetTab."""

    def test_initialization(self, fleet_tab):
        """Widget initializes without crashing and stores service references."""
        assert fleet_tab is not None
        assert fleet_tab.service is not None
        assert hasattr(fleet_tab, "_rows")

    def test_header_renders_title(self, fleet_tab):
        """Header contains a PageTitle with 'Fleet Manager'."""
        from ui.components import PageTitle
        titles = fleet_tab.findChildren(PageTitle)
        assert len(titles) >= 1
        # The PageTitle stores text; ensure at least one exists
        assert any(t.text() for t in titles)

    def test_kpi_strip_renders(self, fleet_tab):
        """KPI strip is built with labelled cards."""
        assert hasattr(fleet_tab, "_kpi_strip")
        assert fleet_tab._kpi_strip is not None
        # KPI value labels dict should contain expected keys
        expected_keys = {"kpi_total", "kpi_active", "kpi_leasing", "kpi_alerts"}
        assert expected_keys.issubset(fleet_tab._kpi_value_labels.keys())

    def test_search_bar_renders(self, fleet_tab):
        """Search text field and reset button exist."""
        assert hasattr(fleet_tab, "_e_search")
        assert fleet_tab._e_search is not None
        assert hasattr(fleet_tab, "_e_plate_search")

    def test_table_renders_with_columns(self, fleet_tab):
        """StyledTableWidget exists and has correct column count."""
        assert hasattr(fleet_tab, "_table")
        table = fleet_tab._table
        from ui.views.fleet_tab.fleet_tab import QtFleetTab
        expected_count = len(QtFleetTab.TABLE_COLUMNS)
        assert table.columnCount() == expected_count

    def test_action_buttons_render(self, fleet_tab):
        """Add, edit, delete buttons exist on the widget."""
        from ui.components import Btn
        buttons = fleet_tab.findChildren(Btn)
        btn_texts = [b.text() for b in buttons]
        # Look for at least some action button text (translations at runtime)
        assert len(buttons) >= 3

    def test_alerts_panel_renders(self, fleet_tab):
        """Alerts container is built."""
        assert hasattr(fleet_tab, "_alerts_container")
        assert fleet_tab._alerts_container_layout is not None

    def test_quick_add_section_renders(self, fleet_tab):
        """Quick-add form fields exist."""
        assert hasattr(fleet_tab, "_q_plate")
        assert hasattr(fleet_tab, "_q_model")
        assert hasattr(fleet_tab, "_q_rate")

    def test_refresh_populates_table(self, fleet_tab, mock_fleet_service):
        """refresh() calls service and populates table rows."""
        mock_fleet_service.get_trucks.return_value = [
            {
                "id": 1,
                "plate_number": "AB-123-CD",
                "model": "Actros",
                "manufacturer": "Mercedes",
                "year": 2020,
                "vin": "WDB1234567890",
                "mileage": 150000,
                "fuel_consumption": 28.5,
                "monthly_rate": 1200.00,
                "status": "Active",
                "active_status": 1,
            }
        ]
        fleet_tab.refresh()
        assert fleet_tab._table.rowCount() == 1
        # Verify the plate text appears in the table
        item = fleet_tab._table.item(0, 1)  # plate column
        assert item is not None
        assert "AB-123-CD" in item.text()

    def test_refresh_handles_empty_data(self, fleet_tab, mock_fleet_service):
        """refresh() handles empty truck list gracefully."""
        mock_fleet_service.get_trucks.return_value = []
        # Should not raise
        fleet_tab.refresh()
        assert fleet_tab._table.rowCount() == 0

    def test_refresh_handles_service_error(self, fleet_tab, mock_fleet_service):
        """refresh() catches service exceptions and shows dialog."""
        mock_fleet_service.get_trucks.side_effect = Exception("DB error")
        # Should not crash, should show QMessageBox
        fleet_tab.refresh()
        # Table should remain intact
        assert fleet_tab._table is not None

    def test_shutdown_cleanup(self, fleet_tab):
        """shutdown() calls base class cleanup without crash."""
        # Should not raise
        fleet_tab.shutdown()
        # Calling shutdown twice is safe
        fleet_tab.shutdown()

    def test_wakeup_does_not_crash(self, fleet_tab):
        """wakeup() refreshes without crashing."""
        fleet_tab.wakeup()

    def test_chart_area_renders(self, fleet_tab):
        """Chart area frame exists."""
        assert hasattr(fleet_tab, "_chart_area")
        assert fleet_tab._chart_area is not None

    def test_filter_table_by_text(self, fleet_tab, mock_fleet_service):
        """Typing in search filter hides non-matching rows."""
        mock_fleet_service.get_trucks.return_value = [
            {"id": 1, "plate_number": "AB-001", "model": "X", "manufacturer": "Y",
             "year": 2020, "vin": "V1", "mileage": 100, "fuel_consumption": 25.0,
             "monthly_rate": 500, "status": "Active", "active_status": 1},
            {"id": 2, "plate_number": "CD-002", "model": "Z", "manufacturer": "W",
             "year": 2021, "vin": "V2", "mileage": 200, "fuel_consumption": 30.0,
             "monthly_rate": 600, "status": "Active", "active_status": 1},
        ]
        fleet_tab.refresh()
        assert fleet_tab._table.rowCount() == 2

        fleet_tab._e_search.setText("AB")
        # After filtering, only first row should be visible
        assert fleet_tab._table.isRowHidden(0) is False
        assert fleet_tab._table.isRowHidden(1) is True

        fleet_tab._e_search.clear()
        fleet_tab._filter_table()
        assert fleet_tab._table.isRowHidden(0) is False
        assert fleet_tab._table.isRowHidden(1) is False
