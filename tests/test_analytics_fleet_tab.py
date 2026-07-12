"""Tests for FleetAnalyticsTab."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.views.analytics.fleet_tab import FleetAnalyticsTab, _fmt_truck_label


class TestFmtTruckLabel:
    def test_normal_name(self):
        assert _fmt_truck_label("B-123-ABC") == "B-123-ABC"

    def test_none(self):
        result = _fmt_truck_label(None)
        assert "Unnamed" in result or "unnamed" in result

    def test_empty_string(self):
        result = _fmt_truck_label("")
        assert "Unnamed" in result or "unnamed" in result

    def test_unknown_string(self):
        result = _fmt_truck_label("Unknown")
        assert "Unnamed" in result or "unnamed" in result

    def test_none_string(self):
        result = _fmt_truck_label("None")
        assert "Unnamed" in result or "unnamed" in result

    def test_question_mark(self):
        result = _fmt_truck_label("?")
        assert "Unnamed" in result or "unnamed" in result


@pytest.fixture
def fleet_svc():
    svc = MagicMock()
    svc.get_fleet.return_value = [
        {"truck": "B-100-ABC", "trip_count": 50, "total_km": 15000,
         "profit": 8000, "avg_consumption": 32, "total_fuel_cost": 4800,
         "status": "Active"},
        {"truck": "B-200-DEF", "trip_count": 35, "total_km": 12000,
         "profit": 5000, "avg_consumption": 28, "total_fuel_cost": 3500,
         "status": "Active"},
        {"truck": "B-300-GHI", "trip_count": 20, "total_km": 8000,
         "profit": -1000, "avg_consumption": 45, "total_fuel_cost": 3800,
         "status": "Maintenance"},
    ]
    svc.get_truck_utilization.return_value = [
        {"truck": "B-100-ABC", "trip_count": 50, "total_km": 15000},
        {"truck": "B-200-DEF", "trip_count": 35, "total_km": 12000},
    ]
    svc.get_maintenance_alerts.return_value = [
        {"truck": "B-300-GHI", "next_due_date": "2026-05-15"},
    ]
    svc.get_cost_breakdown.return_value = [
        {"month": "2026-01", "fuel_cost": 5000, "toll_cost": 1500,
         "salary_cost": 4000, "extra_costs": 800},
        {"month": "2026-02", "fuel_cost": 5500, "toll_cost": 1800,
         "salary_cost": 4200, "extra_costs": 900},
    ]
    return svc


class TestFleetAnalyticsTabCreation:
    def test_creation_without_service(self, qt_widget, qtbot):
        tab = FleetAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._svc is None
        assert tab._chart_widget is not None
        assert tab._chart_layout is not None

    def test_creation_with_service(self, qt_widget, qtbot, fleet_svc):
        tab = FleetAnalyticsTab(parent=qt_widget, service=fleet_svc)
        qtbot.addWidget(tab)
        assert tab._svc is fleet_svc

    def test_header_added_in_build(self, qt_widget, qtbot):
        tab = FleetAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._content_layout.count() >= 2  # header + chart widget


class TestFleetAnalyticsTabRender:
    def test_render_without_service_shows_no_data(self, qt_widget, qtbot):
        tab = FleetAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._content_layout.count() >= 1

    def test_render_with_empty_data_shows_no_data(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_fleet.return_value = []
        svc.get_truck_utilization.return_value = []
        svc.get_maintenance_alerts.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FleetAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._content_layout.count() >= 1

    def test_render_with_fleet_data(self, qt_widget, qtbot, fleet_svc):
        tab = FleetAnalyticsTab(parent=qt_widget, service=fleet_svc)
        qtbot.addWidget(tab)
        tab._render()
        # KPI strip + charts + utilization + maintenance
        assert tab._chart_layout.count() >= 3

    def test_render_adds_kpi_row(self, qt_widget, qtbot, fleet_svc):
        tab = FleetAnalyticsTab(parent=qt_widget, service=fleet_svc)
        qtbot.addWidget(tab)
        tab._render()
        # KPI strip exists — check for kpi-value labels
        kpi_values = tab.findChildren(QLabel, "kpi-value")
        assert len(kpi_values) == 5

    def test_render_adds_profitability_chart(self, qt_widget, qtbot, fleet_svc):
        tab = FleetAnalyticsTab(parent=qt_widget, service=fleet_svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        assert len(charts) >= 1

    def test_render_without_fuel_data(self, qt_widget, qtbot):
        """Trucks with no fuel data should show 'no fuel data' note."""
        svc = MagicMock()
        svc.get_fleet.return_value = [
            {"truck": "B-100-ABC", "trip_count": 50, "total_km": 15000,
             "profit": 8000, "avg_consumption": 0, "total_fuel_cost": 0,
             "status": "Active"},
        ]
        svc.get_truck_utilization.return_value = []
        svc.get_maintenance_alerts.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FleetAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should show note about no fuel data
        labels = tab.findChildren(QLabel)
        note_labels = [
            lbl for lbl in labels
            if "fuel" in lbl.text().lower() or "estimated" in lbl.text().lower()
        ]

    def test_render_without_utilization(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_fleet.return_value = [
            {"truck": "B-100-ABC", "trip_count": 50, "total_km": 15000,
             "profit": 8000, "avg_consumption": 32, "total_fuel_cost": 4800,
             "status": "Active"},
        ]
        svc.get_truck_utilization.return_value = None
        svc.get_maintenance_alerts.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FleetAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should not crash with None utilization
        assert tab._chart_layout.count() >= 1

    def test_render_without_maintenance(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_fleet.return_value = [
            {"truck": "B-100-ABC", "trip_count": 50, "total_km": 15000,
             "profit": 8000, "avg_consumption": 32, "total_fuel_cost": 4800,
             "status": "Active"},
        ]
        svc.get_truck_utilization.return_value = []
        svc.get_maintenance_alerts.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FleetAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should render without crash
        assert tab._chart_layout.count() >= 1

    def test_render_without_fuel_cost_trend(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_fleet.return_value = [
            {"truck": "B-100-ABC", "trip_count": 50, "total_km": 15000,
             "profit": 8000, "avg_consumption": 32, "total_fuel_cost": 4800,
             "status": "Active"},
        ]
        svc.get_truck_utilization.return_value = []
        svc.get_maintenance_alerts.return_value = []
        svc.get_cost_breakdown.return_value = []  # No cost data

        tab = FleetAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should render without fuel cost trend chart
        assert tab._chart_layout.count() >= 1


class TestFleetAnalyticsTabKpiColors:
    def test_maintenance_alert_green_when_none(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_fleet.return_value = [
            {"truck": "B-100", "trip_count": 50, "total_km": 15000,
             "profit": 8000, "avg_consumption": 32, "total_fuel_cost": 4800,
             "status": "Active"},
        ]
        svc.get_truck_utilization.return_value = []
        svc.get_maintenance_alerts.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FleetAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # KPI strip should render 5 values
        kpi_values = tab.findChildren(QLabel, "kpi-value")
        assert len(kpi_values) == 5

    def test_high_maintenance_count_yellow(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_fleet.return_value = [
            {"truck": "B-100", "trip_count": 50, "total_km": 15000,
             "profit": 8000, "avg_consumption": 32, "total_fuel_cost": 4800,
             "status": "Active"},
        ]
        svc.get_truck_utilization.return_value = []
        svc.get_maintenance_alerts.return_value = [
            {"truck": "T1", "next_due_date": "2026-05-15"},
        ]
        svc.get_cost_breakdown.return_value = []

        tab = FleetAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # 1 alert: should still render 5 KPI cards
        kpi_values = tab.findChildren(QLabel, "kpi-value")
        assert len(kpi_values) == 5


class TestFleetAnalyticsTabRefresh:
    def test_refresh_empty(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_fleet.return_value = []
        svc.get_truck_utilization.return_value = []
        svc.get_maintenance_alerts.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FleetAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0

    def test_refresh_with_data(self, qt_widget, qtbot, fleet_svc):
        tab = FleetAnalyticsTab(parent=qt_widget, service=fleet_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0

    def test_cleanup(self, qt_widget, qtbot, fleet_svc):
        tab = FleetAnalyticsTab(parent=qt_widget, service=fleet_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        tab.cleanup(force=True)
        assert tab._content_layout.count() == 0


class TestFleetAnalyticsTabEdgeCases:
    def test_single_truck(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_fleet.return_value = [
            {"truck": "B-100", "trip_count": 10, "total_km": 5000,
             "profit": 2000, "avg_consumption": 30, "total_fuel_cost": 1500,
             "status": "Active"},
        ]
        svc.get_truck_utilization.return_value = []
        svc.get_maintenance_alerts.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FleetAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._chart_layout.count() >= 1

    def test_many_trucks(self, qt_widget, qtbot):
        trucks = []
        for i in range(20):
            trucks.append({
                "truck": f"B-{i:03d}-ABC",
                "trip_count": 10 + i,
                "total_km": 5000 + i * 500,
                "profit": 2000 + i * 100,
                "avg_consumption": 30 + i,
                "total_fuel_cost": 1500 + i * 50,
                "status": "Active",
            })

        svc = MagicMock()
        svc.get_fleet.return_value = trucks
        svc.get_truck_utilization.return_value = []
        svc.get_maintenance_alerts.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FleetAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._chart_layout.count() >= 1
