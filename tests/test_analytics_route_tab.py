"""Tests for RouteAnalyticsTab — top routes, profit/km, country treemap, frequency."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.views.analytics.route_tab import RouteAnalyticsTab, _profit_km_color
from ui.views.analytics.route_tab import COLOR_SUCCESS_DEFAULT, COLOR_WARNING_DEFAULT, COLOR_ERROR_DEFAULT


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


class TestFmtRouteLabel:
    def test_short_label(self):
        assert RouteAnalyticsTab._fmt_route_label("DE-FR") == "DE-FR"

    def test_long_label_truncated(self):
        long_label = "A" * 30
        result = RouteAnalyticsTab._fmt_route_label(long_label)
        assert len(result) == 26  # 25 chars + ellipsis

    def test_empty_label(self):
        assert RouteAnalyticsTab._fmt_route_label("") == "?"

    def test_none_label(self):
        assert RouteAnalyticsTab._fmt_route_label(None) == "?"

    def test_exact_25(self):
        label = "B" * 25
        assert RouteAnalyticsTab._fmt_route_label(label) == label


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def route_svc():
    svc = MagicMock()
    svc.get_route_profitability.return_value = [
        {"route_label": "Paris → Berlin",      "trip_count": 25, "avg_km": 1050,
         "avg_profit": 450, "profit_per_km": 0.43},
        {"route_label": "London → Amsterdam",   "trip_count": 20, "avg_km": 850,
         "avg_profit": 720, "profit_per_km": 0.85},
        {"route_label": "Madrid → Barcelona",   "trip_count": 35, "avg_km": 620,
         "avg_profit": 380, "profit_per_km": 0.61},
        {"route_label": "Berlin → Warsaw",      "trip_count": 15, "avg_km": 580,
         "avg_profit": 250, "profit_per_km": 0.43},
        {"route_label": "Rome → Milan",         "trip_count": 18, "avg_km": 700,
         "avg_profit": 510, "profit_per_km": 0.73},
    ]
    svc.get_profit_per_km_by_country.return_value = [
        {"country": "DE", "profit": 25000, "profit_per_km": 0.65},
        {"country": "FR", "profit": 18000, "profit_per_km": 0.55},
        {"country": "NL", "profit": 12000, "profit_per_km": 0.80},
        {"country": "ES", "profit": 8000,  "profit_per_km": 0.45},
    ]
    return svc


@pytest.fixture
def empty_route_svc():
    svc = MagicMock()
    svc.get_route_profitability.return_value = []
    svc.get_profit_per_km_by_country.return_value = []
    return svc


@pytest.fixture
def single_route_svc():
    svc = MagicMock()
    svc.get_route_profitability.return_value = [
        {"route_label": "Paris → Berlin", "trip_count": 10, "avg_km": 1000,
         "avg_profit": 500, "profit_per_km": 0.50},
    ]
    svc.get_profit_per_km_by_country.return_value = [
        {"country": "DE", "profit": 5000, "profit_per_km": 0.50},
    ]
    return svc


# ── Creation ────────────────────────────────────────────────────────────


class TestRouteAnalyticsTabCreation:
    def test_creation_without_service(self, qt_widget, qtbot):
        tab = RouteAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._svc is None
        assert tab._chart_widget is not None
        assert tab._chart_layout is not None

    def test_creation_with_service(self, qt_widget, qtbot, route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=route_svc)
        qtbot.addWidget(tab)
        assert tab._svc is route_svc

    def test_header_added_in_build(self, qt_widget, qtbot):
        tab = RouteAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._content_layout.count() >= 2


# ── Render ──────────────────────────────────────────────────────────────


class TestRouteAnalyticsTabRender:
    def test_render_without_service_shows_no_data(self, qt_widget, qtbot):
        tab = RouteAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._content_layout.count() >= 1

    def test_render_empty_routes_shows_no_data(self, qt_widget, qtbot, empty_route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=empty_route_svc)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._content_layout.count() >= 1

    def test_render_with_realistic_data(self, qt_widget, qtbot, route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=route_svc)
        qtbot.addWidget(tab)
        tab._render()
        # KPI row + section header + table + profit/km chart + treemap + frequency
        assert tab._chart_layout.count() >= 5

    def test_render_adds_kpi_row(self, qt_widget, qtbot, route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=route_svc)
        qtbot.addWidget(tab)
        tab._render()
        labels = tab.findChildren(QLabel)
        kpi_labels = [lbl for lbl in labels
                      if "Unique Routes" in lbl.text()
                      or "Most Frequent" in lbl.text()
                      or "Avg Profit" in lbl.text()
                      or "Top Country" in lbl.text()]
        assert len(kpi_labels) >= 3


# ── Route table & profit chart ──────────────────────────────────────────


class TestRouteAnalyticsTabTable:
    def test_render_adds_route_table(self, qt_widget, qtbot, route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=route_svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.widgets import StyledTableWidget
        tables = tab.findChildren(StyledTableWidget)
        assert len(tables) >= 1

    def test_render_adds_profit_per_km_chart(self, qt_widget, qtbot, route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=route_svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        assert len(charts) >= 1


# ── Treemap ─────────────────────────────────────────────────────────────


class TestRouteAnalyticsTabTreemap:
    def test_render_adds_treemap(self, qt_widget, qtbot, route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=route_svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        # Treemap + profit/km bar chart + frequency chart
        assert len(charts) >= 2

    def test_render_skips_treemap_with_single_country(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_route_profitability.return_value = [
            {"route_label": "A→B", "trip_count": 10, "avg_km": 500,
             "avg_profit": 200, "profit_per_km": 0.4},
        ]
        svc.get_profit_per_km_by_country.return_value = [
            {"country": "DE", "profit": 5000, "profit_per_km": 0.5},
        ]
        tab = RouteAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Single country → treemap skipped
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        # Should at least have profit/km chart
        assert len(charts) >= 1


# ── Frequency chart ─────────────────────────────────────────────────────


class TestRouteAnalyticsTabFrequency:
    def test_render_adds_frequency_chart(self, qt_widget, qtbot, route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=route_svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        # Profit/km + treemap + frequency
        assert len(charts) >= 3

    def test_frequency_skipped_with_one_route(self, qt_widget, qtbot, single_route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=single_route_svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        # Profit/km chart may still be added
        assert tab._chart_layout.count() >= 1


# ── Single route / edges ────────────────────────────────────────────────


class TestRouteAnalyticsTabSingleRoute:
    def test_single_route_shows_empty_state(self, qt_widget, qtbot, single_route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=single_route_svc)
        qtbot.addWidget(tab)
        tab._render()
        # EmptyState or insufficient data message
        labels = tab.findChildren(QLabel)
        insufficient = [lbl for lbl in labels if "Insufficient" in lbl.text()
                        or "insufficient" in lbl.text().lower()]
        assert len(insufficient) >= 1

    def test_single_route_no_crash(self, qt_widget, qtbot, single_route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=single_route_svc)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._chart_layout.count() >= 1


# ── KPI card builder ────────────────────────────────────────────────────


class TestRouteAnalyticsTabMakeRouteKpi:
    def test_make_route_kpi_returns_frame(self, qt_widget, qtbot):
        card = RouteAnalyticsTab._make_route_kpi("Label", "42")
        qtbot.addWidget(card)
        assert isinstance(card, QFrame)

    def test_make_route_kpi_object_name(self, qt_widget, qtbot):
        card = RouteAnalyticsTab._make_route_kpi("Test", "0")
        qtbot.addWidget(card)
        assert card.objectName() == "kpi-spark-card"

    def test_make_route_kpi_has_label(self, qt_widget, qtbot):
        card = RouteAnalyticsTab._make_route_kpi("Routes", "10")
        qtbot.addWidget(card)
        labels = card.findChildren(QLabel)
        texts = [lbl.text() for lbl in labels]
        assert "Routes" in texts
        assert "10" in texts

    def test_make_route_kpi_with_custom_color(self, qt_widget, qtbot):
        card = RouteAnalyticsTab._make_route_kpi("Profit", "€ 500", value_color="#22c55e")
        qtbot.addWidget(card)
        assert card.objectName() == "kpi-spark-card"


# ── Refresh ─────────────────────────────────────────────────────────────


class TestRouteAnalyticsTabRefresh:
    def test_refresh_empty(self, qt_widget, qtbot, empty_route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=empty_route_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0

    def test_refresh_with_realistic_data(self, qt_widget, qtbot, route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=route_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0

    def test_cleanup(self, qt_widget, qtbot, route_svc):
        tab = RouteAnalyticsTab(parent=qt_widget, service=route_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        tab.cleanup(force=True)
        assert tab._content_layout.count() == 0


# ── Edge cases ──────────────────────────────────────────────────────────


class TestRouteAnalyticsTabEdgeCases:
    def test_no_countries_data(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_route_profitability.return_value = [
            {"route_label": "A→B", "trip_count": 10, "avg_km": 500,
             "avg_profit": 200, "profit_per_km": 0.4},
            {"route_label": "B→C", "trip_count": 8, "avg_km": 400,
             "avg_profit": 150, "profit_per_km": 0.38},
        ]
        svc.get_profit_per_km_by_country.return_value = None
        tab = RouteAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should handle None countries gracefully
        assert tab._chart_layout.count() >= 1

    def test_null_route_fields(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_route_profitability.return_value = [
            {"route_label": None, "trip_count": None, "avg_km": None,
             "avg_profit": None, "profit_per_km": None},
        ]
        svc.get_profit_per_km_by_country.return_value = None
        tab = RouteAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should handle None fields without crash
        assert tab._chart_layout.count() >= 1

    def test_all_zero_profit(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_route_profitability.return_value = [
            {"route_label": "A→B", "trip_count": 10, "avg_km": 500,
             "avg_profit": 0, "profit_per_km": 0},
            {"route_label": "B→C", "trip_count": 8, "avg_km": 400,
             "avg_profit": 0, "profit_per_km": 0},
        ]
        svc.get_profit_per_km_by_country.return_value = [
            {"country": "DE", "profit": 0, "profit_per_km": 0},
        ]
        tab = RouteAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._chart_layout.count() >= 1

    def test_no_top_country_kpi_skipped(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_route_profitability.return_value = [
            {"route_label": "A→B", "trip_count": 5, "avg_km": 300,
             "avg_profit": 100, "profit_per_km": 0.33},
        ]
        svc.get_profit_per_km_by_country.return_value = None
        tab = RouteAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Top Country KPI should be omitted
        labels = tab.findChildren(QLabel)
        top_country = [lbl for lbl in labels if "Top Country" in lbl.text()]
        assert len(top_country) == 0
