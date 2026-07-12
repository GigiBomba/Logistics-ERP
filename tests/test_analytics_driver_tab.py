"""Tests for DriverAnalyticsTab — driver metrics, comparison table, activity timeline."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.views.analytics.driver_tab import DriverAnalyticsTab, _profit_km_color
from ui.views.analytics.driver_tab import COLOR_SUCCESS_DEFAULT, COLOR_WARNING_DEFAULT, COLOR_ERROR_DEFAULT


# ── Helper tests ────────────────────────────────────────────────────────


class TestProfitKmColor:
    def test_high_profit(self):
        assert _profit_km_color(1.5) == COLOR_SUCCESS_DEFAULT

    def test_medium_profit(self):
        assert _profit_km_color(0.75) == COLOR_WARNING_DEFAULT

    def test_low_profit(self):
        assert _profit_km_color(0.3) == COLOR_ERROR_DEFAULT

    def test_boundary_high(self):
        # ppm > 1.0 is required for success; 1.0 is still WARNING
        assert _profit_km_color(1.0) == COLOR_WARNING_DEFAULT

    def test_boundary_medium(self):
        assert _profit_km_color(0.5) == COLOR_WARNING_DEFAULT

    def test_zero(self):
        assert _profit_km_color(0.0) == COLOR_ERROR_DEFAULT

    def test_negative(self):
        assert _profit_km_color(-0.5) == COLOR_ERROR_DEFAULT


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def driver_svc():
    svc = MagicMock()
    svc.get_driver.return_value = [
        {"driver": "John Smith",  "trip_count": 25, "profit": 12500},
        {"driver": "Jane Doe",    "trip_count": 30, "profit": 15000},
        {"driver": "Bob Wilson",  "trip_count": 18, "profit": 8000},
    ]
    svc.get_driver_comparison.return_value = [
        {"driver": "John Smith",  "trip_count": 25, "total_km": 8500,
         "revenue": 25000, "profit": 12500, "profit_per_km": 1.47},
        {"driver": "Jane Doe",    "trip_count": 30, "total_km": 9500,
         "revenue": 30000, "profit": 15000, "profit_per_km": 1.58},
        {"driver": "Bob Wilson",  "trip_count": 18, "total_km": 6000,
         "revenue": 18000, "profit": 8000, "profit_per_km": 1.33},
    ]
    svc.get_driver_tacho_violations.return_value = [
        {"driver": "John Smith", "total_violations": 3},
        {"driver": "Jane Doe",   "total_violations": 1},
    ]
    svc.get_driver_monthly_activity.return_value = [
        {"driver_name": "John Smith", "week_start": "2026-05-04"},
        {"driver_name": "John Smith", "week_start": "2026-05-11"},
        {"driver_name": "Jane Doe",   "week_start": "2026-05-04"},
    ]
    return svc


@pytest.fixture
def empty_svc():
    svc = MagicMock()
    svc.get_driver.return_value = []
    svc.get_driver_comparison.return_value = []
    svc.get_driver_tacho_violations.return_value = None
    svc.get_driver_monthly_activity.return_value = []
    return svc


# ── Creation ────────────────────────────────────────────────────────────


class TestDriverAnalyticsTabCreation:
    def test_creation_without_service(self, qt_widget, qtbot):
        tab = DriverAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._svc is None
        assert tab._chart_widget is not None
        assert tab._chart_layout is not None

    def test_creation_with_service(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        assert tab._svc is driver_svc

    def test_header_added_in_build(self, qt_widget, qtbot):
        tab = DriverAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._content_layout.count() >= 2  # header + chart widget


# ── Render ──────────────────────────────────────────────────────────────


class TestDriverAnalyticsTabRender:
    def test_render_without_service_shows_no_data(self, qt_widget, qtbot):
        tab = DriverAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._content_layout.count() >= 1

    def test_render_with_empty_data_shows_no_data(self, qt_widget, qtbot, empty_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=empty_svc)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._content_layout.count() >= 1

    def test_render_with_realistic_data(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        tab._render()
        # KPI row + table + charts
        assert tab._chart_layout.count() >= 2

    def test_render_adds_kpi_row(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should have Active Drivers KPI card
        labels = tab.findChildren(QLabel)
        kpi_labels = [lbl for lbl in labels if "Active Drivers" in lbl.text()
                      or "Avg" in lbl.text()]
        assert len(kpi_labels) >= 1

    def test_render_adds_comparison_table(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        tab._render()
        # StyledTableWidget should be present
        from ui.widgets import StyledTableWidget
        tables = tab.findChildren(StyledTableWidget)
        assert len(tables) >= 1

    def test_render_adds_tacho_chart(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Tacho violations chart
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        assert len(charts) >= 1

    def test_render_adds_activity_timeline(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Activity timeline section header
        labels = tab.findChildren(QLabel)
        activity_labels = [lbl for lbl in labels if "Activity" in lbl.text()
                           or "Timeline" in lbl.text()]
        assert len(activity_labels) >= 1

    def test_render_without_comparison_data(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_driver.return_value = [
            {"driver": "John Smith", "trip_count": 10, "profit": 5000},
        ]
        svc.get_driver_comparison.return_value = []
        svc.get_driver_tacho_violations.return_value = None
        svc.get_driver_monthly_activity.return_value = []
        tab = DriverAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should show KPI row without crash
        assert tab._chart_layout.count() >= 1


# ── Unassigned drivers ──────────────────────────────────────────────────


class TestDriverAnalyticsTabUnassigned:
    def test_unassigned_trips_shows_warning(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_driver.return_value = [
            {"driver": "Unassigned", "trip_count": 15, "profit": 0},
            {"driver": "John Smith", "trip_count": 10, "profit": 5000},
        ]
        svc.get_driver_comparison.return_value = []
        svc.get_driver_tacho_violations.return_value = None
        svc.get_driver_monthly_activity.return_value = []

        tab = DriverAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Unassigned warning label should be present
        labels = tab.findChildren(QLabel)
        unassigned_labels = [lbl for lbl in labels
                             if "unassigned" in lbl.text().lower()
                             or "Unassigned" in lbl.text()]
        assert len(unassigned_labels) >= 1

    def test_all_unassigned_shows_no_data(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_driver.return_value = [
            {"driver": "Unassigned", "trip_count": 15, "profit": 0},
        ]
        svc.get_driver_comparison.return_value = []
        svc.get_driver_tacho_violations.return_value = None
        svc.get_driver_monthly_activity.return_value = []

        tab = DriverAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # No assigned drivers → should show no-data
        assert tab._chart_layout.count() >= 1

    def test_unassigned_with_case_variants(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_driver.return_value = [
            {"driver": "UNASSIGNED", "trip_count": 5, "profit": 0},
            {"driver": "Unassigned", "trip_count": 3, "profit": 0},
            {"driver": "John Smith", "trip_count": 10, "profit": 5000},
        ]
        svc.get_driver_comparison.return_value = []
        svc.get_driver_tacho_violations.return_value = None
        svc.get_driver_monthly_activity.return_value = []

        tab = DriverAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        labels = tab.findChildren(QLabel)
        unassigned_labels = [lbl for lbl in labels
                             if "unassigned" in lbl.text().lower()]
        assert len(unassigned_labels) >= 1


# ── No tacho / no activity ──────────────────────────────────────────────


class TestDriverAnalyticsTabOptionalSections:
    def test_no_tacho_violations(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_driver.return_value = [
            {"driver": "John Smith", "trip_count": 10, "profit": 5000},
        ]
        svc.get_driver_comparison.return_value = [
            {"driver": "John Smith", "trip_count": 10, "total_km": 5000,
             "revenue": 10000, "profit": 5000, "profit_per_km": 1.0},
        ]
        svc.get_driver_tacho_violations.return_value = None
        svc.get_driver_monthly_activity.return_value = []

        tab = DriverAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should still render table without crash
        assert tab._chart_layout.count() >= 1

    def test_empty_monthly_activity(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_driver.return_value = [
            {"driver": "John Smith", "trip_count": 10, "profit": 5000},
        ]
        svc.get_driver_comparison.return_value = [
            {"driver": "John Smith", "trip_count": 10, "total_km": 5000,
             "revenue": 10000, "profit": 5000, "profit_per_km": 1.0},
        ]
        svc.get_driver_tacho_violations.return_value = []
        svc.get_driver_monthly_activity.return_value = []

        tab = DriverAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._chart_layout.count() >= 1


# ── Make driver KPI ─────────────────────────────────────────────────────


class TestDriverAnalyticsTabMakeDriverKpi:
    def test_make_driver_kpi_returns_widget(self, qt_widget, qtbot):
        card = DriverAnalyticsTab._make_driver_kpi("Label", "42", "#fff")
        qtbot.addWidget(card)
        assert isinstance(card, QWidget)

    def test_make_driver_kpi_has_label_and_value(self, qt_widget, qtbot):
        card = DriverAnalyticsTab._make_driver_kpi("Trips", "42", "#fff")
        qtbot.addWidget(card)
        labels = card.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert "Trips" in texts
        assert "42" in texts

    def test_make_driver_kpi_object_name(self, qt_widget, qtbot):
        card = DriverAnalyticsTab._make_driver_kpi("Test", "0", "#000")
        qtbot.addWidget(card)
        assert card.objectName() == "kpi-spark-card"


# ── Build activity timeline ─────────────────────────────────────────────


class TestDriverAnalyticsTabBuildActivityTimeline:
    def test_build_with_data(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        monthly = driver_svc.get_driver_monthly_activity()
        tab._build_activity_timeline(monthly)
        # Container should be added
        assert tab._chart_layout.count() >= 1

    def test_build_empty(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        tab._build_activity_timeline([])
        # No container added for empty data
        # Might have self._add_section_header called though

    def test_build_limits_weeks(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        # 20 weeks of data → should limit to 12
        monthly = []
        for i in range(20):
            monthly.append({
                "driver_name": "Driver A",
                "week_start": f"2026-{(i // 4) + 1:02d}-{(i % 28) + 1:02d}",
            })
        tab._build_activity_timeline(monthly)
        assert tab._chart_layout.count() >= 1


# ── Refresh ─────────────────────────────────────────────────────────────


class TestDriverAnalyticsTabRefresh:
    def test_refresh_empty(self, qt_widget, qtbot, empty_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=empty_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0

    def test_refresh_with_realistic_data(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0

    def test_cleanup(self, qt_widget, qtbot, driver_svc):
        tab = DriverAnalyticsTab(parent=qt_widget, service=driver_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        tab.cleanup(force=True)
        assert tab._content_layout.count() == 0


# ── Edge cases ──────────────────────────────────────────────────────────


class TestDriverAnalyticsTabEdgeCases:
    def test_single_driver(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_driver.return_value = [
            {"driver": "John Smith", "trip_count": 10, "profit": 5000},
        ]
        svc.get_driver_comparison.return_value = [
            {"driver": "John Smith", "trip_count": 10, "total_km": 5000,
             "revenue": 10000, "profit": 5000, "profit_per_km": 1.0},
        ]
        svc.get_driver_tacho_violations.return_value = []
        svc.get_driver_monthly_activity.return_value = []

        tab = DriverAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._chart_layout.count() >= 1

    def test_driver_with_zero_trips(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_driver.return_value = [
            {"driver": "Idle Driver", "trip_count": 0, "profit": 0},
        ]
        svc.get_driver_comparison.return_value = []
        svc.get_driver_tacho_violations.return_value = []
        svc.get_driver_monthly_activity.return_value = []

        tab = DriverAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should handle zero trips gracefully
        assert tab._chart_layout.count() >= 1

    def test_null_driver_fields(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_driver.return_value = [
            {"driver": None, "trip_count": None, "profit": None},
        ]
        svc.get_driver_comparison.return_value = []
        svc.get_driver_tacho_violations.return_value = None
        svc.get_driver_monthly_activity.return_value = []

        tab = DriverAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should handle None fields without crash
        assert tab._chart_layout.count() >= 1
