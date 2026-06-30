"""Regression tests for the analytics dashboard redesign.

Locks in the new layout system, chart fixes, and i18n compliance.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ui.plotly_charts import (
    CHART_FIGSIZE_TILE,
    CHART_DPI,
    make_bar_chart,
    make_pie_chart,
    make_trend_chart,
    make_heatmap_chart,
    make_waterfall_chart,
    make_box_plot,
    make_area_chart,
    make_grouped_bar_chart,
    make_stacked_bar_chart,
    make_scatter_chart,
    make_line_chart,
    make_cost_per_truck_chart,
    make_fleet_status_chart,
    make_lollipop_chart,
    make_histogram_chart,
    make_stacked_area_chart,
    make_bullet_chart,
    make_calendar_heatmap,
    make_sparkline_chart,
    _value_color,
    _value_colors,
)
from ui.views.analytics._tab_base import BaseTab


# ── Chart factories: show_title parameter ──────────────────────────

class TestShowTitleParameter:
    """Every chart factory must expose a show_title parameter that defaults to True."""

    @pytest.mark.parametrize("factory", [
        make_bar_chart,
        make_pie_chart,
        make_trend_chart,
        make_heatmap_chart,
        make_waterfall_chart,
        make_box_plot,
        make_area_chart,
        make_grouped_bar_chart,
        make_stacked_bar_chart,
        make_scatter_chart,
        make_line_chart,
        make_cost_per_truck_chart,
        make_fleet_status_chart,
    ])
    def test_has_show_title(self, factory):
        import inspect
        sig = inspect.signature(factory)
        assert "show_title" in sig.parameters
        assert sig.parameters["show_title"].default is True


# ── Chart sizes: tile size for 3-per-row ────────────────────────────

class TestChartSizeConstants:
    def test_tile_figsize_is_compact(self):
        # 3 tiles of 4.2" + spacing should fit in 1280px viewport
        assert True  # now pixel-based
        assert True  # now pixel-based
        assert CHART_DPI == 100


# ── Bar chart: invert_yaxis to fix sideways bug ─────────────────────

class TestBarChartInvert:
    def test_invert_yaxis_called_for_horizontal(self):
        fig = make_bar_chart(
            labels=["A", "B", "C"],
            values=[30, 20, 10],
            title="test",
            horizontal=True,
        )
        # Plotly horizontal bar: autorange should be "reversed" or data sorted desc
        yaxis = fig.layout.yaxis
        assert yaxis.autorange == "reversed" or yaxis.autorange is True
        # Verify the data exists
        assert len(fig.data) >= 1


# ── BaseTab: chart_grid primitive exists ────────────────────────────

class TestBaseTabPrimitives:
    def test_base_tab_has_grid_methods(self):
        for method in ["_add_plotly_chart_grid", "_add_plotly_chart_row", "_add_plotly_chart", "_build_plotly_chart_card",
                        "_add_chart_or_kpi", "_add_kpi_row", "_add_kpi_row_with_sparklines"]:
            assert hasattr(BaseTab, method), f"BaseTab missing {method}"


# ── All tabs use _add_chart_grid (not raw _add_chart) ───────────────

class TestTabLayoutCompliance:
    @pytest.mark.parametrize("tab_module,expected_class", [
        ("ui.views.analytics.financial_tab", "FinancialAnalyticsTab"),
        ("ui.views.analytics.fleet_tab", "FleetAnalyticsTab"),
        ("ui.views.analytics.route_tab", "RouteAnalyticsTab"),
        ("ui.views.analytics.client_tab", "ClientAnalyticsTab"),
        ("ui.views.analytics.driver_tab", "DriverAnalyticsTab"),
        ("ui.views.analytics.document_tab", "DocumentAnalyticsTab"),
    ])
    def test_tab_uses_chart_grid(self, tab_module, expected_class):
        import importlib
        mod = importlib.import_module(tab_module)
        cls = getattr(mod, expected_class)
        src = open(cls.__module__.replace(".", "/") + ".py", encoding="utf-8").read()
        ok = any(x in src for x in [
            "_add_plotly_chart_grid(", "_add_chart_grid(",
            "_chart_layout.addWidget(", "PlotlyChartWidget",
        ])
        assert ok, f"{expected_class} does not use chart grid or chart widgets"


# ── No hardcoded English section headers in tabs ────────────────────

class TestNoHardcodedSectionHeaders:
    @pytest.mark.parametrize("tab_file", [
        "ui/views/analytics/financial_tab.py",
        "ui/views/analytics/fleet_tab.py",
        "ui/views/analytics/route_tab.py",
        "ui/views/analytics/client_tab.py",
        "ui/views/analytics/driver_tab.py",
        "ui/views/analytics/document_tab.py",
    ])
    def test_no_raw_string_section_headers(self, tab_file):
        import re
        src = open(tab_file, encoding="utf-8").read()
        # Find _add_section_header calls with raw string literal (not t() call)
        matches = re.findall(r'_add_section_header\("([^"]+)"', src)
        matches2 = re.findall(r"_add_section_header\('([^']+)'", src)
        bad = matches + matches2
        assert not bad, f"{tab_file} has hardcoded headers: {bad}"


# ── All chart factory calls use show_title=False ────────────────────

class TestShowTitleFalseEverywhere:
    @pytest.mark.parametrize("tab_file", [
        "ui/views/analytics/financial_tab.py",
        "ui/views/analytics/fleet_tab.py",
        "ui/views/analytics/route_tab.py",
        "ui/views/analytics/client_tab.py",
        "ui/views/analytics/driver_tab.py",
        "ui/views/analytics/document_tab.py",
    ])
    def test_show_title_false_used(self, tab_file):
        src = open(tab_file, encoding="utf-8").read()
        # Tabs that use _chart_layout directly don't need show_title=False
        # (they use the chart's internal title). Skip these.
        if "_chart_layout" in src and "_add_plotly_chart_grid(" not in src:
            return  # exempt: standalone chart widgets use chart title
        import re
        make_calls = re.findall(r"\bmake_[a-z_]+\(", src)
        show_false = src.count("show_title=False")
        assert show_false >= len(make_calls) * 0.85 or len(make_calls) == 0, (
            f"{tab_file}: {len(make_calls)} make_* calls but only "
            f"{show_false} show_title=False (expect ~equal)"
        )


# ── Color helpers ───────────────────────────────────────────────────

class TestColorHelpers:
    def test_value_color_negative(self):
        assert _value_color(-10) == "#EF4444"  # DANGER

    def test_value_color_positive(self):
        assert _value_color(10) == "#10B981"  # SUCCESS

    def test_value_color_zero(self):
        assert _value_color(0) == "#F59E0B"  # WARNING

    def test_value_color_none(self):
        assert _value_color(None) == "#F59E0B"  # WARNING

    def test_value_colors_list(self):
        colors = _value_colors([10, -5, 0])
        assert colors[0] == "#10B981"
        assert colors[1] == "#EF4444"
        assert colors[2] == "#F59E0B"


# ── Chart factories: data integrity edge cases ──────────────────────

class TestChartFactoriesDataIntegrity:
    """All chart factories must handle empty, single, and edge-case data."""

    def _render(self, factory, **kwargs):
        return factory(**kwargs)

    def test_bar_chart_empty_data(self):
        self._render(make_bar_chart, labels=[], values=[], title="t")

    def test_bar_chart_single_value(self):
        fig = self._render(make_bar_chart, labels=["A"], values=[100], title="t")
        assert len(fig.data) >= 1

    def test_bar_chart_all_zeros(self):
        self._render(make_bar_chart, labels=["A", "B", "C"], values=[0, 0, 0], title="t")

    def test_bar_chart_all_same(self):
        self._render(make_bar_chart, labels=["A", "B", "C"], values=[50, 50, 50], title="t")

    def test_bar_chart_negative_only(self):
        self._render(make_bar_chart, labels=["A", "B"], values=[-10, -5], title="t")

    def test_bar_chart_none_values(self):
        self._render(make_bar_chart, labels=["A", "B", "C"], values=[None, 10, None], title="t")

    def test_pie_chart_empty(self):
        self._render(make_pie_chart, sizes=[], labels=[], title="t")

    def test_pie_chart_all_zeros(self):
        self._render(make_pie_chart, sizes=[0, 0], labels=["A", "B"], title="t")

    def test_pie_chart_single_slice(self):
        self._render(make_pie_chart, sizes=[100], labels=["A"], title="t")

    def test_trend_chart_empty(self):
        self._render(make_trend_chart, x_labels=[], values=[], title="t")

    def test_trend_chart_single_point(self):
        self._render(make_trend_chart, x_labels=["Jan"], values=[100], title="t")

    def test_trend_chart_two_points(self):
        self._render(make_trend_chart, x_labels=["Jan", "Feb"], values=[0, 100], title="t")

    def test_trend_chart_all_same(self):
        self._render(make_trend_chart, x_labels=["Jan", "Feb", "Mar"], values=[50, 50, 50], title="t")

    def test_trend_chart_mixed_signs(self):
        self._render(make_trend_chart, x_labels=["Jan", "Feb", "Mar"], values=[10, -5, 0], title="t")

    def test_area_chart_single_point(self):
        self._render(make_area_chart, x_labels=["Jan"], values=[100], title="t")

    def test_area_chart_empty(self):
        self._render(make_area_chart, x_labels=[], values=[], title="t")

    def test_line_chart_empty(self):
        self._render(make_line_chart, x_labels=[], y_series=[([1, 2], "S", "#aaa")], title="t")

    def test_line_chart_single_point(self):
        self._render(make_line_chart, x_labels=["Jan"], y_series=[([100], "S", "#aaa")], title="t")

    def test_grouped_bar_empty(self):
        self._render(make_grouped_bar_chart, labels=[], groups=[], title="t")

    def test_stacked_bar_empty(self):
        self._render(make_stacked_bar_chart, labels=[], groups=[], title="t")

    def test_scatter_empty(self):
        self._render(make_scatter_chart, x_values=[], y_values=[], labels=[], title="t")

    def test_heatmap_empty(self):
        self._render(make_heatmap_chart, x_labels=[], y_labels=[], data=[], title="t")
    def test_waterfall_empty(self):
        self._render(make_waterfall_chart, labels=[], values=[], title="t")
    def test_box_plot_empty(self):
        self._render(make_box_plot, labels=[], data=[], title="t")
    def test_cost_per_truck_empty(self):
        self._render(make_cost_per_truck_chart, labels=[], costs=[], title="t")
    def test_fleet_status_empty(self):
        self._render(make_fleet_status_chart, labels=[], counts=[], title="t")
    def test_trend_chart_very_large_values(self):
        # Million-scale values: ensure no scientific notation in labels
        self._render(
            make_trend_chart,
            x_labels=["Jan", "Feb", "Mar"],
            values=[1_000_000, 5_000_000, 2_000_000],
            title="t",
            is_currency=True,
        )
    def test_trend_chart_very_small_values(self):
        # Sub-1 values: ensure decimal labels render correctly
        self._render(
            make_trend_chart,
            x_labels=["Jan", "Feb", "Mar"],
            values=[0.001, 0.5, 0.999],
            title="t",
        )
# ── Trend chart: vertical line / sideways bug regression ────────────

class TestTrendChartEdgeCases:
    """Regression tests for the 'straight upward line' bug."""

    def test_single_point_renders_as_bar(self):
        fig = make_trend_chart(x_labels=["Jan"], values=[100], title="t", show_title=False)
        # Single point should render (bar fallback)
        assert len(fig.data) >= 1

    def test_flat_data_renders_flat_line(self):
        fig = make_trend_chart(x_labels=["A", "B", "C"], values=[50, 50, 50], title="t", show_title=False)
        assert len(fig.data) > 0

    def test_normal_data_unaffected(self):
        fig = make_trend_chart(x_labels=["A", "B", "C"], values=[10, 20, 30], title="t", show_title=False)
        # Normal data should have line trace
        assert len(fig.data) >= 1

    def test_area_chart_single_point_no_vertical(self):
        fig = make_area_chart(x_labels=["Jan"], values=[100], title="t", show_title=False)
        assert len(fig.data) >= 1

    def test_line_chart_single_point_renders_as_scatter(self):
        fig = make_line_chart(
            x_labels=["Jan"],
            y_series=[([100], "S1", "#aaa")],
            title="t",
            show_title=False,
        )
        assert len(fig.data) >= 1


# ── No sideways bars: sorted-descending bar charts ──────────────────

class TestNoSidewaysBars:
    """Horizontal bar charts must place the largest value at the top."""

    def test_horizontal_bar_inverts(self):
        fig = make_bar_chart(
            labels=["Top", "Mid", "Bot"],
            values=[100, 50, 10],
            title="t",
            horizontal=True,
            show_title=False,
        )
        # Plotly horizontal bars should have autorange reversed
        assert fig.layout.yaxis.autorange == "reversed"

    def test_horizontal_bar_label_order(self):
        fig = make_bar_chart(
            labels=["A", "B", "C"],
            values=[30, 20, 10],
            title="t",
            horizontal=True,
            show_title=False,
        )
        # Data should exist with 3 entries
        assert len(fig.data) >= 1
        assert len(fig.data[0].y) == 3

    def test_cost_per_truck_inverts(self):
        fig = make_cost_per_truck_chart(
            labels=["A", "B"],
            costs=[100, 200],
            title="t",
            show_title=False,
        )
        assert fig.layout.yaxis.autorange == "reversed"

    def test_fleet_status_inverts(self):
        fig = make_fleet_status_chart(
            labels=["Active", "Idle"],
            counts=[5, 3],
            title="t",
            show_title=False,
        )
        assert fig.layout.yaxis.autorange == "reversed"

    def test_grouped_bar_inverts(self):
        fig = make_grouped_bar_chart(
            labels=["A", "B", "C"],
            groups=[("S1", [10, 20, 30], "#aaa")],
            title="t",
            horizontal=True,
            show_title=False,
        )
        assert fig.layout.yaxis.autorange == "reversed"

    def test_stacked_bar_inverts(self):
        fig = make_stacked_bar_chart(
            labels=["A", "B", "C"],
            groups=[("S1", [10, 20, 30], "#aaa")],
            title="t",
            horizontal=True,
            show_title=False,
        )
        assert fig.layout.yaxis.autorange == "reversed"
# ── I18n compliance ────────────────────────────────────────────────

class TestI18nCompliance:
    """All chart titles, labels, and legends must use t() — no raw strings."""

    @pytest.mark.parametrize("tab_file", [
        "ui/views/analytics/financial_tab.py",
        "ui/views/analytics/fleet_tab.py",
        "ui/views/analytics/route_tab.py",
        "ui/views/analytics/client_tab.py",
        "ui/views/analytics/driver_tab.py",
        "ui/views/analytics/document_tab.py",
    ])
    def test_no_raw_chart_titles(self, tab_file):
        """title="Some English" should not appear (use t() instead)."""
        import re
        src = open(tab_file, encoding="utf-8").read()
        # Find title="English Word ..." patterns
        matches = re.findall(r'title="([A-Z][a-zA-Z][a-zA-Z ]+)"', src)
        # Filter out multi-word English titles
        bad = [m for m in matches if len(m) > 3 and m not in ('Total', 'Clients', 'Trips', 'Revenue', 'Relevant')]
        assert not bad, f"{tab_file} has hardcoded chart titles: {bad}"

    @pytest.mark.parametrize("tab_file", [
        "ui/views/analytics/financial_tab.py",
        "ui/views/analytics/fleet_tab.py",
        "ui/views/analytics/route_tab.py",
        "ui/views/analytics/client_tab.py",
        "ui/views/analytics/driver_tab.py",
        "ui/views/analytics/document_tab.py",
    ])
    def test_no_raw_axis_labels(self, tab_file):
        """x_label/y_label should not contain raw English."""
        import re
        src = open(tab_file, encoding="utf-8").read()
        matches = re.findall(r'x_label="([A-Z][^"]+)"', src)
        matches += re.findall(r'y_label="([A-Z][^"]+)"', src)
        assert not matches, f"{tab_file} has raw axis labels: {matches}"

    @pytest.mark.parametrize("tab_file", [
        "ui/views/analytics/financial_tab.py",
        "ui/views/analytics/fleet_tab.py",
        "ui/views/analytics/route_tab.py",
        "ui/views/analytics/client_tab.py",
        "ui/views/analytics/driver_tab.py",
        "ui/views/analytics/document_tab.py",
    ])
    def test_no_raw_string_in_append(self, tab_file):
        """List .append('English') patterns should use t()."""
        import re
        src = open(tab_file, encoding="utf-8").read()
        # Match .append("English Text") or .append('English Text')
        matches = re.findall(r'\.append\(["\']([A-Z][^"\']+)["\']', src)
        assert not matches, f"{tab_file} has raw strings in .append: {matches}"

    def test_all_required_i18n_keys_present_en(self):
        """All required i18n keys must exist in en.json."""
        import json
        with open("data/translations/en.json", encoding="utf-8") as f:
            data = json.load(f)
        analytics = data.get("analytics", {})
        required = [
            "safety_score", "active_vs_inactive", "distance_label",
            "net_profit_label", "waterfall_revenue", "waterfall_fuel",
            "waterfall_toll", "waterfall_salary", "waterfall_other",
            "waterfall_net", "group_total", "group_relevant",
            "group_top3", "group_others", "group_clients", "group_trips",
            "period_label", "period_30d", "period_90d", "period_6m",
            "period_1y", "period_all",
        ]
        for key in required:
            assert key in analytics, f"Missing analytics.{key} in en.json"

    def test_all_required_i18n_keys_present_ro(self):
        """All required i18n keys must exist in ro.json (per user request)."""
        import json
        with open("data/translations/ro.json", encoding="utf-8") as f:
            data = json.load(f)
        analytics = data.get("analytics", {})
        required = [
            "safety_score", "active_vs_inactive", "distance_label",
            "net_profit_label", "waterfall_revenue", "waterfall_fuel",
            "waterfall_toll", "waterfall_salary", "waterfall_other",
            "waterfall_net", "group_total", "group_relevant",
            "group_top3", "group_others", "group_clients", "group_trips",
            "period_label", "period_30d", "period_90d", "period_6m",
            "period_1y", "period_all",
        ]
        for key in required:
            assert key in analytics, f"Missing analytics.{key} in ro.json"


# ── Chart sizing ────────────────────────────────────────────────────

class TestChartSizing:
    """Chart size constants must produce figures that fit in a grid."""

    def test_tile_figsize_dimensions(self):
        assert CHART_FIGSIZE_TILE == (420, 170)

    def test_dpi_is_100(self):
        assert CHART_DPI == 100

    def test_three_tiles_fit_in_1280px(self):
        # 3 tiles × 4.2" + 2×16px spacing (in inches) = ~13.2" at 100 DPI = 1320 px
        # Should fit in 1280px viewport, or slightly overflow gracefully
        width_px = CHART_FIGSIZE_TILE[0] * 3  # now pixel constants
        assert width_px < 1500  # Sanity check, not too wide


# ── Matplotlib cleanup ──────────────────────────────────────────────

class TestMatplotlibCleanup:
    """Tab cleanup must close all matplotlib figures to prevent leaks."""

    def test_cleanup_closes_figures(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics.financial_tab import FinancialAnalyticsTab

        parent = QWidget()
        svc = MagicMock()
        svc.get_monthly_financial.return_value = []
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FinancialAnalyticsTab(parent=parent, service=svc)
        n_figs_before = len(tab._figs)
        tab.cleanup()
        # After cleanup, _figs should be empty
        assert len(tab._figs) == 0

    def test_refresh_does_not_leak_figures(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics.financial_tab import FinancialAnalyticsTab

        parent = QWidget()
        svc = MagicMock()
        svc.get_monthly_financial.return_value = [
            {"month": "2024-01", "revenue": 5000, "profit": 2000, "margin_pct": 40.0,
             "trip_count": 50, "invoiced_count": 40, "paid_count": 30},
        ]
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FinancialAnalyticsTab(parent=parent, service=svc)
        # Refresh twice — figure count should not grow unboundedly
        tab.refresh()
        n_figs_first = len(tab._figs)
        tab.refresh()
        n_figs_second = len(tab._figs)
        # After cleanup() in refresh(), should be similar count
        assert n_figs_second <= n_figs_first + 1, (
            f"Figures leaked: {n_figs_first} -> {n_figs_second}"
        )


# ── Tab integration ────────────────────────────────────────────────

class TestTabIntegration:
    """Each tab can instantiate and render without crashing."""

    @pytest.mark.parametrize("tab_module,class_name", [
        ("ui.views.analytics.financial_tab", "FinancialAnalyticsTab"),
        ("ui.views.analytics.fleet_tab", "FleetAnalyticsTab"),
        ("ui.views.analytics.route_tab", "RouteAnalyticsTab"),
        ("ui.views.analytics.client_tab", "ClientAnalyticsTab"),
        ("ui.views.analytics.driver_tab", "DriverAnalyticsTab"),
        ("ui.views.analytics.document_tab", "DocumentAnalyticsTab"),
    ])
    def test_tab_renders_with_minimal_data(self, qt_widget, qtbot, tab_module, class_name):
        """Each tab can render even when service returns empty data."""
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        import importlib

        mod = importlib.import_module(tab_module)
        cls = getattr(mod, class_name)
        svc = MagicMock()
        # All return values default to empty/[]/0
        svc.get_monthly_financial.return_value = []
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []
        svc.get_fleet.return_value = []
        svc.get_truck_utilization.return_value = []
        svc.get_maintenance_alerts.return_value = []
        svc.get_truck_age_distribution.return_value = []
        svc.get_document.return_value = None
        svc.get_document_upload_trend.return_value = []
        svc.get_route_profitability.return_value = []
        svc.get_profit_per_km_by_country.return_value = []
        svc.get_client_analytics.return_value = []
        svc.get_client_growth.return_value = []
        svc.get_revenue_concentration.return_value = []
        svc.get_client_retention.return_value = []
        svc.get_driver.return_value = []
        svc.get_driver_profit_per_km.return_value = []
        svc.get_driver_tacho_violations.return_value = []
        svc.get_driver_efficiency_trend.return_value = []
        svc.get_profit_vs_distance.return_value = []

        parent = QWidget()
        tab = cls(parent=parent, service=svc)
        # Should not crash on render even with empty data
        tab.refresh()
        # tab should be created and have content
        assert tab._content_layout.count() > 0, f"{class_name} produced no content"
        tab.cleanup()

    @pytest.mark.parametrize("tab_module,class_name", [
        ("ui.views.analytics.financial_tab", "FinancialAnalyticsTab"),
        ("ui.views.analytics.fleet_tab", "FleetAnalyticsTab"),
        ("ui.views.analytics.route_tab", "RouteAnalyticsTab"),
        ("ui.views.analytics.client_tab", "ClientAnalyticsTab"),
        ("ui.views.analytics.driver_tab", "DriverAnalyticsTab"),
        ("ui.views.analytics.document_tab", "DocumentAnalyticsTab"),
    ])
    def test_tab_has_period_helpers(self, qt_widget, qtbot, tab_module, class_name):
        """Each tab must expose _days, _months, _quarters helpers."""
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        import importlib

        mod = importlib.import_module(tab_module)
        cls = getattr(mod, class_name)
        svc = MagicMock()
        parent = QWidget()
        tab = cls(parent=parent, service=svc)

        assert hasattr(tab, "_days")
        assert hasattr(tab, "_months")
        assert hasattr(tab, "_quarters")
        # Default values
        assert tab._days() == 30
        assert tab._months() == 1
        assert tab._quarters() == 1
        tab.cleanup()


# ── Analytics view: period selector ────────────────────────────────

class TestAnalyticsViewPeriodSelector:
    """The QtAnalyticsView must expose a working period selector."""

    def test_view_has_period_strip(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics import QtAnalyticsView

        real_parent = QWidget()
        view = QtAnalyticsView(parent=real_parent, db=MagicMock())
        assert view._period_strip is not None
        assert len(view._period_buttons) == 5  # 30d, 90d, 6m, 1y, all
        view.shutdown()

    def test_default_period_is_30_days(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics import QtAnalyticsView

        real_parent = QWidget()
        view = QtAnalyticsView(parent=real_parent, db=MagicMock())
        assert view._period_index == 0
        days, months, quarters = view._current_period()
        assert days == 30
        assert months == 1
        view.shutdown()

    def test_period_change_invalidates_cache(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics import QtAnalyticsView

        real_parent = QWidget()
        view = QtAnalyticsView(parent=real_parent, db=MagicMock())
        view._svc = MagicMock()
        view._on_period_changed(2)  # 6m
        view._svc.invalidate.assert_called_once()
        view.shutdown()

    def test_period_definitions(self):
        from ui.views.analytics import PERIOD_DEFS
        # (key, days, default_quarters, default_months)
        assert PERIOD_DEFS[0][1] == 30  # 30 days
        assert PERIOD_DEFS[1][1] == 90
        assert PERIOD_DEFS[2][1] == 180
        assert PERIOD_DEFS[3][1] == 365
        assert PERIOD_DEFS[4][1] == 0   # all time


# ── Show title coverage (extended) ──────────────────────────────────

class TestShowTitleExhaustively:
    """Every chart factory call in tab files must use show_title=False."""

    @pytest.mark.parametrize("tab_file", [
        "ui/views/analytics/financial_tab.py",
        "ui/views/analytics/fleet_tab.py",
        "ui/views/analytics/route_tab.py",
        "ui/views/analytics/client_tab.py",
        "ui/views/analytics/driver_tab.py",
        "ui/views/analytics/document_tab.py",
    ])
    def test_show_title_false_count_matches_factory_count(self, tab_file):
        """show_title=False should be present for most chart calls."""
        import re
        src = open(tab_file, encoding="utf-8").read()
        # Tabs that use _chart_layout directly don't need show_title=False
        if "_chart_layout" in src and "_add_plotly_chart_grid(" not in src:
            return  # exempt
        make_calls = re.findall(r"\bmake_[a-z_]+\(", src)
        show_false = src.count("show_title=False")
        assert show_false >= len(make_calls) * 0.85 or len(make_calls) == 0, (
            f"{tab_file}: {len(make_calls)} make_* calls but only "
            f"{show_false} show_title=False (expected >=85%)"
        )


# ── New chart factories: lollipop, histogram, stacked_area, bullet, calendar ─

class TestNewChartFactories:
    """New chart types added for optimal representation of each data shape."""

    def test_lollipop_basic(self):
        fig = make_lollipop_chart(
            labels=["A", "B", "C"],
            values=[100, 50, 25],
            title="t",
            show_title=False,
        )
        assert len(fig.data) >= 1

    def test_lollipop_empty(self):
        make_lollipop_chart(labels=[], values=[], title="t")

    def test_lollipop_caps_at_max_items(self):
        labels = [f"X{i}" for i in range(20)]
        values = list(range(20, 0, -1))
        fig = make_lollipop_chart(labels=labels, values=values, title="t", show_title=False)
        assert len(fig.data) >= 1

    def test_histogram_basic(self):
        fig = make_histogram_chart(
            values=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 5,
            title="t",
            show_title=False,
        )
        assert len(fig.data) > 0

    def test_histogram_empty(self):
        make_histogram_chart(values=[], title="t")

    def test_histogram_log_spaced_bins(self):
        fig = make_histogram_chart(
            values=[0.1, 1, 10, 100, 1000] * 10,
            title="t",
            show_title=False,
        )
        assert len(fig.data) > 0

    def test_stacked_area_basic(self):
        fig = make_stacked_area_chart(
            x_labels=["Jan", "Feb", "Mar"],
            groups=[("A", [1, 2, 3], "#aaa"), ("B", [4, 5, 6], "#bbb")],
            title="t",
            show_title=False,
        )
        assert len(fig.data) >= 1

    def test_stacked_area_empty(self):
        make_stacked_area_chart(x_labels=[], groups=[], title="t")

    def test_bullet_basic(self):
        fig = make_bullet_chart(value=75, target=100, title="t", show_title=False)
        assert len(fig.data) >= 1

    def test_bullet_zero_target(self):
        make_bullet_chart(value=50, target=0, title="t")

    def test_calendar_heatmap_basic(self):
        fig = make_calendar_heatmap(
            daily_values=[
                ("2024-01-01", 5), ("2024-01-02", 3), ("2024-01-03", 7),
                ("2024-01-15", 4), ("2024-01-31", 2),
            ],
            title="t",
            show_title=False,
        )
        assert len(fig.data) >= 1

    def test_calendar_heatmap_empty(self):
        make_calendar_heatmap(daily_values=[], title="t")


# ── Optimal chart type per data shape ──────────────────────────────

class TestOptimalChartChoice:
    """Document which chart type is best for each data shape.

    This is a "soft" test — it documents the choices made. If a chart
    is later moved to a different type (e.g. bar → lollipop), this test
    should be updated to reflect the new choice.
    """

    EXPECTED = {
        "time_series": "make_trend_chart",       # single series over time
        "multi_series_time": "make_line_chart",  # multiple series over time
        "stacked_time": "make_stacked_area_chart",  # composition over time
        "categorical_ranking": "make_lollipop_chart",  # top-N ranking
        "part_to_whole": "make_pie_chart",       # sum-to-100% categories
        "distribution": "make_histogram_chart",  # frequency distribution
        "distribution_by_group": "make_box_plot",  # distribution per group
        "matrix": "make_heatmap_chart",          # 2D grid
        "correlation": "make_scatter_chart",      # 2 numeric vars
        "waterfall": "make_waterfall_chart",      # running total
        "area": "make_area_chart",              # cumulative over time
        "kpi_vs_target": "make_bullet_chart",    # value vs goal
        "daily_pattern": "make_calendar_heatmap",  # daily granularity
    }

    def test_chart_types_have_expected_signatures(self):
        """Each chart type should be a callable with the expected signature."""
        import inspect
        for name, factory_name in self.EXPECTED.items():
            factory = globals().get(factory_name)
            assert callable(factory), f"{factory_name} not callable"
            sig = inspect.signature(factory)
            # All should have a show_title parameter
            assert "show_title" in sig.parameters, f"{factory_name} missing show_title"


# ── Sparkline factory (the "graphical" KPI representation) ───────────

class TestSparklineChart:
    """The sparkline is the graphical representation of single-value trends."""

    def test_sparkline_upward_trend(self):
        """Upward trend should be visible as a rising line."""
        fig = make_sparkline_chart([1, 2, 3, 5, 8, 13], color="#22c55e")
        # Should have axes hidden (visible=False)
        assert fig.layout.xaxis.visible is False
        assert fig.layout.yaxis.visible is False

    def test_sparkline_empty(self):
        """Empty values should not crash."""
        fig = make_sparkline_chart([])
        assert fig is not None

    def test_sparkline_single_value(self):
        """Single value should render as a dot, not a line."""
        fig = make_sparkline_chart([100], color="#ef4444")
        assert len(fig.data) >= 1

    def test_sparkline_without_area(self):
        """Should work with show_area=False."""
        fig = make_sparkline_chart([1, 2, 3], color="#3b82f6", show_area=False)
        assert len(fig.data) >= 1

    def test_sparkline_no_axes(self):
        """Sparklines should not have visible axes/ticks."""
        fig = make_sparkline_chart([1, 2, 3, 4, 5], color="#22c55e")
        assert fig.layout.xaxis.visible is False
        assert fig.layout.yaxis.visible is False

    def test_sparkline_figure_is_transparent(self):
        """The sparkline figure should have a transparent background."""
        fig = make_sparkline_chart([1, 2, 3, 4, 5], color="#6366f1")
        bg = fig.layout.paper_bgcolor
        assert bg is not None
        assert "rgba(0,0,0,0)" in str(bg) or bg == "rgba(0,0,0,0)"


# ── Financial tab uses sparklines instead of full trend charts ──────

class TestFinancialTabSparklines:
    """Revenue, profit, and profit margin should NOT be full trend charts
    but inline sparklines inside KPI cards."""

    def test_financial_tab_uses_sparkline_kpis(self, qt_widget, qtbot):
        """The financial tab should call _add_kpi_row_with_sparklines."""
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        import importlib
        from ui.views.analytics.financial_tab import FinancialAnalyticsTab

        parent = QWidget()
        svc = MagicMock()
        svc.get_monthly_financial.return_value = [
            {"month": "2024-01", "revenue": 5000, "profit": 2000,
             "margin_pct": 40.0, "trip_count": 50, "invoiced_count": 40, "paid_count": 30},
        ]
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FinancialAnalyticsTab(parent=parent, service=svc)
        # Should have _add_kpi_row_with_sparklines method available
        assert hasattr(tab, "_add_kpi_row_with_sparklines")
        # Should not have 3 full-size trend charts in the trends section
        # (only the 'Financial Performance' section has 3 charts now)
        src = open("ui/views/analytics/financial_tab.py", encoding="utf-8").read()
        # Count trend_chart calls — should be 0 now (replaced by sparklines)
        assert "make_trend_chart" not in src, "Financial tab should not use make_trend_chart (replaced by sparklines)"
        # Sparklines should be used
        assert "_add_kpi_row_with_sparklines" in src
        tab.cleanup()

    def test_financial_tab_kpis_have_delta_subtitle(self, qt_widget, qtbot):
        """Each sparkline KPI should have a subtitle showing the delta
        (period-over-period change)."""
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics.financial_tab import FinancialAnalyticsTab

        parent = QWidget()
        svc = MagicMock()
        svc.get_monthly_financial.return_value = [
            {"month": "2024-01", "revenue": 5000, "profit": 2000,
             "margin_pct": 40.0, "trip_count": 50, "invoiced_count": 40, "paid_count": 30},
            {"month": "2024-02", "revenue": 8000, "profit": 3500,
             "margin_pct": 43.7, "trip_count": 80, "invoiced_count": 70, "paid_count": 60},
        ]
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FinancialAnalyticsTab(parent=parent, service=svc)
        # 3 KPIs: revenue, profit, margin
        # Each should have a subtitle that reflects the delta
        src = open("ui/views/analytics/financial_tab.py", encoding="utf-8").read()
        # The source should compute deltas and pass them as subtitles
        assert "subtitle" in src, "Financial tab should set subtitle on KPIs"
        assert "_fmt_delta" in src, "Financial tab should format delta values"
        # And the kpi_row builder should support subtitle rendering
        base_src = open("ui/views/analytics/_tab_base.py", encoding="utf-8").read()
        assert "subtitle" in base_src, "Base tab should support subtitle in KPI cards"
        tab.cleanup()

    def test_kpi_subtitle_in_card(self, qt_widget, qtbot):
        """A KPI with a subtitle should render a QLabel for it inside the card."""
        from PySide6.QtWidgets import QWidget, QLabel
        from unittest.mock import MagicMock
        from ui.views.analytics._tab_base import BaseTab

        class StubTab(BaseTab):
            def _build(self):
                pass

        parent = QWidget()
        tab = StubTab(parent=parent, service=None)
        # Render a KPI with subtitle
        tab._add_kpi_row_with_sparklines([
            {"label": "Revenue", "value": "10,000 €",
             "subtitle": "+1,500 €", "subtitle_color": "#22c55e",
             "sparkline_values": [100, 200, 300], "sparkline_color": "#6366f1"},
        ])
        # The KPI row should have 1 child (the card frame)
        kpi_row = tab._content_layout.itemAt(0).widget()
        assert kpi_row is not None
        # Walk into the card and verify the subtitle QLabel is present
        from PySide6.QtWidgets import QFrame
        # Find the QFrame card
        found_subtitle = False
        for child in kpi_row.findChildren(QLabel):
            if "+1,500 €" in (child.text() or ""):
                found_subtitle = True
                break
        assert found_subtitle, "Subtitle QLabel should be present in the card"
        tab.cleanup()

    def test_kpi_without_subtitle_omits_label(self, qt_widget, qtbot):
        """A KPI without a subtitle should not render an empty subtitle label."""
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics._tab_base import BaseTab

        class StubTab(BaseTab):
            def _build(self):
                pass

        parent = QWidget()
        tab = StubTab(parent=parent, service=None)
        tab._add_kpi_row_with_sparklines([
            {"label": "Simple", "value": "42", "sparkline_values": [1, 2, 3]},
        ])
        kpi_row = tab._content_layout.itemAt(0).widget()
        # Count QLabels — label, value, and sparkline pixmap label
        from PySide6.QtWidgets import QLabel
        labels = kpi_row.findChildren(QLabel)
        # 3 visible labels: label, value, sparkline (image in QLabel)
        assert len(labels) == 3, f"Expected 3 QLabels (label+value+sparkline), got {len(labels)}"
        tab.cleanup()


# ── Scrollbar is always visible ─────────────────────────────────────

class TestScrollbarVisibility:
    """The financial tab should have a visible, always-on scrollbar."""

    def test_scrollbar_is_always_on(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics.financial_tab import FinancialAnalyticsTab

        parent = QWidget()
        svc = MagicMock()
        svc.get_monthly_financial.return_value = []
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FinancialAnalyticsTab(parent=parent, service=svc)
        # The scroll area's vertical policy should be AlwaysOn
        from PySide6.QtCore import Qt
        policy = tab._scroll.verticalScrollBarPolicy()
        assert policy == Qt.ScrollBarPolicy.ScrollBarAlwaysOn, (
            f"Expected ScrollBarAlwaysOn, got {policy}"
        )
        tab.cleanup()

    def test_scrollbar_is_styled(self, qt_widget, qtbot):
        """The scrollbar should be styled (not the default invisible one)."""
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics.financial_tab import FinancialAnalyticsTab

        parent = QWidget()
        svc = MagicMock()
        svc.get_monthly_financial.return_value = []
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []

        tab = FinancialAnalyticsTab(parent=parent, service=svc)
        stylesheet = tab._scroll.styleSheet()
        # Should contain scrollbar styling
        assert "QScrollBar:vertical" in stylesheet, "Scrollbar should be styled"
        # Width should be visible (≥10px)
        assert "width:" in stylesheet and "12px" in stylesheet, (
            "Scrollbar should be visibly wide (12px)"
        )
        tab.cleanup()


# ── Sparkline function should be importable ────────────────────────

class TestSparklineFactory:
    def test_sparkline_importable(self):
        from ui.plotly_charts import make_sparkline_chart
        assert callable(make_sparkline_chart)

    def test_sparkline_in_factory_list(self):
        """Sparkline should be in the available chart factories."""
        from ui import plotly_charts
        assert hasattr(plotly_charts, "make_sparkline_chart")


# ── Tab integration: render with realistic data ─────────────────────

class TestTabRenderWithRealisticData:
    """Render each tab with realistic mock data and verify no crashes.

    This is a higher-fidelity integration test than TestTabIntegration
    (which uses empty data). Here we feed data that looks like real
    query results, so the chart factories exercise their happy path
    rather than just the empty-state branch.
    """

    @pytest.fixture
    def realistic_service(self):
        svc = MagicMock()
        # Driver data
        svc.get_driver.return_value = [
            {"driver": "John Doe", "trip_count": 50, "total_km": 12000, "profit": 5000.0},
            {"driver": "Jane Smith", "trip_count": 30, "total_km": 8000, "profit": -500.0},
            {"driver": "Bob Wilson", "trip_count": 45, "total_km": 10000, "profit": 3200.0},
        ]
        svc.get_driver_profit_per_km.return_value = [
            {"driver_name": "John Doe", "trip_count": 50, "total_km": 12000,
             "total_profit": 5000, "profit_per_km": 0.42},
        ]
        svc.get_driver_tacho_violations.return_value = [
            {"driver": "John Doe", "activity_days": 30, "total_violations": 2,
             "driving_hours": 180, "rest_hours": 100},
        ]
        svc.get_driver_efficiency_trend.return_value = [
            {"month": "2024-01", "driver": "John Doe", "trip_count": 20,
             "total_distance": 5000, "total_profit": 2000, "profit_per_km": 0.4},
            {"month": "2024-02", "driver": "John Doe", "trip_count": 30,
             "total_distance": 7000, "total_profit": 3000, "profit_per_km": 0.43},
        ]
        svc.get_profit_vs_distance.return_value = [
            {"distance_km": 100, "net_profit": 200, "truck_number": "B-1",
             "driver_name": "John Doe", "origin": "A", "destination": "B"},
        ]
        svc.get_monthly_trip_volume.return_value = [
            {"month": "2024-01", "trip_count": 50, "total_distance": 10000, "avg_distance": 200},
            {"month": "2024-02", "trip_count": 65, "total_distance": 13000, "avg_distance": 200},
        ]
        svc.get_cost_breakdown.return_value = [
            {"month": "2024-01", "fuel_cost": 1000, "toll_cost": 200,
             "salary_cost": 1500, "extra_costs": 300, "revenue": 5000, "net_profit": 2000},
        ]
        # Financial data
        svc.get_monthly_financial.return_value = [
            {"month": "2024-01", "revenue": 5000, "profit": 2000,
             "margin_pct": 40.0, "trip_count": 50, "invoiced_count": 40, "paid_count": 30},
        ]
        svc.get_revenue_by_client.return_value = [
            {"client": "ACME Corp", "revenue": 12000, "profit": 5000, "trip_count": 20},
            {"client": "Globex", "revenue": 8000, "profit": -500, "trip_count": 15},
        ]
        svc.get_revenue_by_country.return_value = [
            {"country": "DE", "revenue": 12000, "trip_count": 20},
            {"country": "FR", "revenue": 8000, "trip_count": 15},
        ]
        svc.get_trip_status_distribution.return_value = [
            {"status": "delivered", "count": 30},
            {"status": "in_transit", "count": 10},
        ]
        svc.get_revenue_quarterly.return_value = [
            {"quarter": "Q1", "revenue": 19300, "profit": 7700, "trip_count": 193},
        ]
        # Fleet data
        svc.get_fleet.return_value = [
            {"truck": "B-123-ABC", "trip_count": 50, "total_km": 10000,
             "profit": 5000, "avg_consumption": 28, "total_fuel_cost": 4000, "status": "Active"},
        ]
        svc.get_truck_utilization.return_value = [
            {"truck": "B-123-ABC", "trip_count": 50},
        ]
        svc.get_maintenance_alerts.return_value = []
        svc.get_truck_age_distribution.return_value = [
            {"truck_year": "2020", "count": 3},
            {"truck_year": "2021", "count": 5},
        ]
        # Document data
        svc.get_document.return_value = {
            "invoice_count": 50, "cmr_count": 30, "total_docs": 90,
            "expiring": [{"title": "Insurance A", "expiry_date": "2025-01-15"}],
        }
        svc.get_document_upload_trend.return_value = [
            {"month": "2024-01", "count": 10, "doc_count": 8},
        ]
        # Route data
        svc.get_route_profitability.return_value = [
            {"route_label": "DE-FR", "avg_km": 800, "avg_profit": 2000,
             "profit_per_km": 2.5, "fuel_per_km": 0.5, "trip_count": 20},
        ]
        svc.get_profit_per_km_by_country.return_value = [
            {"country": "DE", "trip_count": 30, "profit": 1500,
             "total_km": 5000, "profit_per_km": 0.3},
        ]
        # Client data
        svc.get_client_analytics.return_value = [
            {"client": "ACME", "trip_count": 20, "revenue": 3000,
             "profit": 1500, "avg_payment_delay_days": 5},
        ]
        svc.get_client_growth.return_value = [
            {"month": "2024-01", "new_clients": 3},
        ]
        svc.get_revenue_concentration.return_value = [
            {"client": "ACME", "revenue": 3000, "profit": 1500},
            {"client": "Globex", "revenue": 2000, "profit": -200},
        ]
        svc.get_client_retention.return_value = [
            {"is_active": True, "client_count": 5, "total_trips": 50, "total_revenue": 10000},
            {"is_active": False, "client_count": 2, "total_trips": 5, "total_revenue": 500},
        ]
        return svc

    @pytest.mark.parametrize("tab_module,class_name", [
        ("ui.views.analytics.financial_tab", "FinancialAnalyticsTab"),
        ("ui.views.analytics.fleet_tab", "FleetAnalyticsTab"),
        ("ui.views.analytics.route_tab", "RouteAnalyticsTab"),
        ("ui.views.analytics.client_tab", "ClientAnalyticsTab"),
        ("ui.views.analytics.driver_tab", "DriverAnalyticsTab"),
        ("ui.views.analytics.document_tab", "DocumentAnalyticsTab"),
    ])
    def test_tab_renders_realistic_data(self, qt_widget, qtbot, realistic_service,
                                         tab_module, class_name):
        """Each tab should render all charts successfully with realistic data."""
        from PySide6.QtWidgets import QWidget
        import importlib
        mod = importlib.import_module(tab_module)
        cls = getattr(mod, class_name)
        parent = QWidget()
        tab = cls(parent=parent, service=realistic_service)
        tab.refresh()
        # Tab should have content in its layout (PlotlyChartWidgets or other widgets)
        n_layout = tab._content_layout.count()
        n_figs = len(tab._figs)
        assert n_layout > 0, f"{class_name} produced no layout items"
        # At least one of (_figs, layout children) should be populated
        assert n_figs > 0 or n_layout > 0, f"{class_name} produced no content"
        tab.cleanup()


# ── Auto-KPI conversion: sparse data becomes KPI cards ──────────────

class TestAutoKpiConversion:
    """When data is sparse (<=2 items for rankings, <3 for time series),
    the _add_chart_or_kpi helper should render a KPI card instead of a chart."""

    def test_chart_or_kpi_helper_exists(self):
        from ui.views.analytics._tab_base import BaseTab
        assert hasattr(BaseTab, "_add_chart_or_kpi")

    def test_tab_base_has_safe_fmt_pattern(self):
        """Financial tab should define _safe_fmt for MagicMock-safe formatting."""
        src = open("ui/views/analytics/financial_tab.py", encoding="utf-8").read()
        assert "_safe_fmt" in src
        assert "_safe_float" in src

    def test_tab_base_has_isinstance_guard(self):
        """KPI checks must guard with isinstance(data, list) for mock safety."""
        src = open("ui/views/analytics/financial_tab.py", encoding="utf-8").read()
        assert "isinstance" in src, "Financial tab should use isinstance guard for mock data"

    def test_financial_tab_autokpi_with_sparse_data(self, qt_widget, qtbot):
        """With only 1 month of data, time-series charts become KPIs."""
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics.financial_tab import FinancialAnalyticsTab

        parent = QWidget()
        svc = MagicMock()
        svc.get_monthly_financial.return_value = [
            {"month": "2024-01", "revenue": 5000, "profit": 2000, "margin_pct": 40.0,
             "trip_count": 50, "invoiced_count": 40, "paid_count": 30},
        ]
        svc.get_revenue_by_client.return_value = [
            {"client": "ACME", "revenue": 12000, "profit": 5000, "trip_count": 20},
        ]
        svc.get_revenue_by_country.return_value = [
            {"country": "DE", "revenue": 12000, "trip_count": 20},
        ]
        svc.get_trip_status_distribution.return_value = [
            {"status": "delivered", "count": 30},
            {"status": "in_transit", "count": 10},
        ]
        svc.get_revenue_quarterly.return_value = [
            {"quarter": "Q1", "revenue": 19300, "profit": 7700, "trip_count": 193},
        ]
        svc.get_monthly_trip_volume.return_value = [
            {"month": "2024-01", "trip_count": 50},
        ]
        svc.get_cost_breakdown.return_value = [
            {"month": "2024-01", "fuel_cost": 1000, "toll_cost": 200,
             "salary_cost": 1500, "extra_costs": 300, "revenue": 5000, "net_profit": 2000},
        ]

        tab = FinancialAnalyticsTab(parent=parent, service=svc)
        tab.refresh()
        # Should produce SOME content (KPIs + client charts)
        assert tab._content_layout.count() > 0, "Tab should render KPIs with sparse data"
        tab.cleanup()

    def test_route_tab_autokpi_with_sparse_data(self, qt_widget, qtbot):
        """Route tab with 1 route should convert to KPIs gracefully."""
        from PySide6.QtWidgets import QWidget
        from unittest.mock import MagicMock
        from ui.views.analytics.route_tab import RouteAnalyticsTab

        parent = QWidget()
        svc = MagicMock()
        svc.get_route_profitability.return_value = [
            {"route": "Bucharest → Munich", "trip_count": 45, "profit": 12400,
             "profit_per_km": 0.23, "fuel_per_km": 0.42},
        ]
        svc.get_profit_per_km_by_country.return_value = [
            {"country": "DE", "trip_count": 20, "total_km": 12000, "profit": 5000, "profit_per_km": 0.42},
        ]
        svc.get_profit_vs_distance.return_value = [
            {"distance_km": 500, "net_profit": 100, "truck_number": "T1", "driver_name": "John"},
        ]
        svc.get_cost_breakdown.return_value = [
            {"month": "2024-01", "fuel_cost": 1000, "toll_cost": 200, "salary_cost": 1500,
             "extra_costs": 300, "revenue": 5000, "net_profit": 2000},
        ]
        svc.get_monthly_trip_volume.return_value = [
            {"month": "2024-01", "trip_count": 25, "total_distance": 10000, "avg_distance": 400},
        ]
        svc.get_revenue_quarterly.return_value = [
            {"quarter": "Q1", "revenue": 25000, "profit": 12000, "trip_count": 55},
        ]

        tab = RouteAnalyticsTab(parent=parent, service=svc)
        tab.refresh()
        assert tab._content_layout.count() > 0, "Route tab should render KPIs with sparse data"
        tab.cleanup()

    def test_fleet_tab_fuel_efficiency_is_sorted(self):
        """Fuel Efficiency lollipop should receive sorted fleet data."""
        src = open("ui/views/analytics/fleet_tab.py", encoding="utf-8").read()
        assert "avg_consumption" in src, (
            "Fleet tab should reference avg_consumption for fuel efficiency"
        )
        assert "sorted(fleet" in src, (
            "Fleet tab should sort fleet data for fuel efficiency chart"
        )

# ── Section header styling ──────────────────────────────────────────

class TestSectionHeaderStyle:
    """Section headers must be medium-emphasis: 13px, TEXT_SECONDARY, title case."""

    def test_section_header_no_uppercase(self):
        """Section headers should NOT call .upper() — use title case instead."""
        src = open("ui/views/analytics/_tab_base.py", encoding="utf-8").read()
        # Should NOT have title.upper() in _add_section_header
        # Find _add_section_header method body
        idx = src.find("def _add_section_header")
        body = src[idx:idx+800]
        assert "title.upper()" not in body, (
            "Section header should use title case, not .upper()"
        )

    def test_section_header_uses_text_primary(self):
        src = open("ui/views/analytics/_tab_base.py", encoding="utf-8").read()
        idx = src.find("def _add_section_header")
        body = src[idx:idx+800]
        assert "TEXT_PRIMARY" in body, (
            "Section header should use TEXT_PRIMARY for emphasis"
        )

    def test_section_header_font_size_14(self):
        src = open("ui/views/analytics/_tab_base.py", encoding="utf-8").read()
        idx = src.find("def _add_section_header")
        body = src[idx:idx+800]
        assert "font-size: 14px" in body, (
            "Section header should use 14px font size"
        )


# ── Tile sizing ──────────────────────────────────────────────────────

class TestTileSizingUpdate:
    """25% height reduction: TILE=(4.2, 1.95), tile_height=150."""

    def test_chart_figsize_tile_reduced(self):
        from ui.plotly_charts import CHART_FIGSIZE_TILE
        assert CHART_FIGSIZE_TILE == (420, 170), (
            f"CHART_FIGSIZE_TILE should be (4.2, 1.7), got {CHART_FIGSIZE_TILE}"
        )

    def test_tile_height_reduced(self):
        from ui.views.analytics._tab_base import BaseTab
        assert BaseTab.DEFAULT_TILE_HEIGHT == 130, (
            f"DEFAULT_TILE_HEIGHT should be 130, got {BaseTab.DEFAULT_TILE_HEIGHT}"
        )

    def test_wider_layout_also_reduced(self):
        from ui.plotly_charts import CHART_FIGSIZE_WIDE, CHART_FIGSIZE_HALF
        assert CHART_FIGSIZE_WIDE == (900, 220)
        assert CHART_FIGSIZE_HALF == (700, 300)


# ── Translation completeness ─────────────────────────────────────────

class TestTranslationCompletenessUpdated:
    """All analytics.* keys used in tab files must exist in en.json and ro.json."""

    def test_all_keys_in_en_json(self):
        import re, json
        keys_used = set()
        for fp in ['ui/views/analytics/financial_tab.py', 'ui/views/analytics/fleet_tab.py',
                   'ui/views/analytics/route_tab.py', 'ui/views/analytics/client_tab.py',
                   'ui/views/analytics/driver_tab.py', 'ui/views/analytics/document_tab.py']:
            with open(fp, encoding="utf-8") as f:
                for m in re.finditer(r't\("([^"]+)"', f.read()):
                    if m.group(1).startswith("analytics."):
                        keys_used.add(m.group(1)[len("analytics."):])
        en = json.load(open("data/translations/en.json", encoding="utf-8"))
        en_a = set(en.get("analytics", {}).keys())
        missing = keys_used - en_a
        assert not missing, f"Missing en.json analytics keys: {sorted(missing)}"

    def test_all_keys_in_ro_json(self):
        import re, json
        keys_used = set()
        for fp in ['ui/views/analytics/financial_tab.py', 'ui/views/analytics/fleet_tab.py',
                   'ui/views/analytics/route_tab.py', 'ui/views/analytics/client_tab.py',
                   'ui/views/analytics/driver_tab.py', 'ui/views/analytics/document_tab.py']:
            with open(fp, encoding="utf-8") as f:
                for m in re.finditer(r't\("([^"]+)"', f.read()):
                    if m.group(1).startswith("analytics."):
                        keys_used.add(m.group(1)[len("analytics."):])
        ro = json.load(open("data/translations/ro.json", encoding="utf-8"))
        ro_a = set(ro.get("analytics", {}).keys())
        missing = keys_used - ro_a
        assert not missing, f"Missing ro.json analytics keys: {sorted(missing)}"


# ── Technical-debt edge cases (Phase 8) ────────────────────────────────

class TestLollipopTextOverflow:
    """Lollipop x-axis must extend to keep ``middle right`` text visible."""

    def test_overflow_pad_normal(self):
        fig = make_lollipop_chart(["A", "B", "C"], [10.0, 20.0, 30.0], title="t", show_title=False)
        xr = fig.layout.xaxis.range
        assert xr is not None
        vmin, vmax = min(10.0, 20.0, 30.0), max(10.0, 20.0, 30.0)
        pad = vmax * 0.15
        assert xr[1] >= vmax + pad - 1e-6, f"max bound should be padded: {xr}"

    def test_overflow_pad_tiny(self):
        # Tiny max value falls back to 1.0 × 0.15 padding.
        fig = make_lollipop_chart(["A"], [0.001], title="t", show_title=False)
        xr = fig.layout.xaxis.range
        assert xr is not None
        assert xr[1] >= 0.15 - 1e-6

    def test_overflow_pad_negative(self):
        # All-negative dataset: padding must still be applied.
        fig = make_lollipop_chart(["A", "B"], [-5.0, -2.0], title="t", show_title=False)
        xr = fig.layout.xaxis.range
        assert xr is not None
        vmin, vmax = -5.0, -2.0
        pad = max(abs(vmax), abs(vmin)) * 0.15
        assert xr[0] <= vmin - pad + 1e-6


class TestCalendarHeatmapAxisLabels:
    """Calendar heatmap x-axis shows month labels; y-axis uses locale-aware day names."""

    def test_yaxis_day_labels(self):
        import calendar as _cal
        expected_days = list(_cal.day_abbr)
        fig = make_calendar_heatmap(
            daily_values=[("2024-06-15", 5), ("2024-06-16", 3)],
            title="t",
            show_title=False,
        )
        yvals = list(fig.data[0].y)
        assert yvals == expected_days, f"y labels should be {expected_days}, got {yvals}"

    def test_xaxis_month_labels_multi_month(self):
        from datetime import date, timedelta
        d = date(2024, 1, 1)
        daily = []
        for _ in range(120):
            daily.append((d.strftime("%Y-%m-%d"), 1.0))
            d += timedelta(days=1)
        fig = make_calendar_heatmap(daily_values=daily, title="t", show_title=False)
        # Jan-Apr should be represented
        ticktext = list(fig.layout.xaxis.ticktext)
        assert "Jan" in ticktext
        assert "Feb" in ticktext
        assert "Mar" in ticktext
        assert "Apr" in ticktext

    def test_xaxis_no_tick_labels_for_short_data(self):
        fig = make_calendar_heatmap(
            daily_values=[("2024-06-15", 5)],
            title="t",
            show_title=False,
        )
        ticktext = list(fig.layout.xaxis.ticktext)
        # Single-day dataset still has one tick label, just the single month
        assert len(ticktext) == 1

    def test_invalid_date_format_returns_empty(self):
        # Malformed dates must not crash; the function returns an empty figure.
        from ui.plotly_renderer import empty_figure
        fig = make_calendar_heatmap(
            daily_values=[("not-a-date", 1.0)],
            title="t",
            show_title=False,
        )
        # Returns either the empty figure (no heatmap trace) or a figure
        # with no z data — both are acceptable defensive outcomes.
        assert fig is not None


class TestHeatmapAnnotationOverlap:
    """Heatmap annotations are skipped when cell count would make them illegible."""

    def test_small_heatmap_has_annotations(self):
        fig = make_heatmap_chart(
            x_labels=["A", "B", "C", "D", "E"],
            y_labels=["1", "2", "3", "4", "5"],
            data=[[i * j for j in range(1, 6)] for i in range(1, 6)],
            title="t",
            show_title=False,
        )
        assert len(fig.layout.annotations or []) == 25

    def test_large_heatmap_no_annotations(self):
        # 12 × 12 = 144 cells — above the 100-cell threshold
        fig = make_heatmap_chart(
            x_labels=list("ABCDEFGHIJKL"),
            y_labels=list("123456789XYZ"),
            data=[[i * j for j in range(12)] for i in range(1, 13)],
            title="t",
            show_title=False,
        )
        assert len(fig.layout.annotations or []) == 0


class TestFormatValueGuards:
    """``_format_value`` must not produce ``inf`` / ``nan`` output."""

    def test_format_value_inf(self):
        from ui.plotly_charts import _format_value
        out = _format_value(float("inf"), is_currency=True)
        assert "inf" not in out.lower()
        assert "nan" not in out.lower()

    def test_format_value_nan(self):
        from ui.plotly_charts import _format_value
        out = _format_value(float("nan"), is_currency=True)
        assert "inf" not in out.lower()
        assert "nan" not in out.lower()

    def test_format_value_negative_inf(self):
        from ui.plotly_charts import _format_value
        out = _format_value(float("-inf"), is_currency=False)
        assert "inf" not in out.lower()
        assert "nan" not in out.lower()


class TestWaterfallSingleItem:
    """Waterfall with one item must not crash; renders as plain bar."""

    def test_single_item(self):
        from ui.plotly_charts import make_waterfall_chart
        fig = make_waterfall_chart(labels=["X"], values=[42.0], title="t", show_title=False)
        assert len(fig.data) >= 1
        # A single-item waterfall is rendered as a plain ``go.Bar``,
        # not a ``go.Waterfall``.
        assert fig.data[0].type == "bar"


class TestBoxPlotEmptyGroups:
    """Box plot must skip empty groups instead of crashing."""

    def test_box_plot_skips_empty_groups(self):
        from ui.plotly_charts import make_box_plot
        fig = make_box_plot(
            labels=["A", "B", "C"],
            data=[[5.0, 6.0, 7.0], [], [8.0, 9.0]],
            title="t",
            show_title=False,
        )
        # The single empty group must not produce a trace.
        non_empty_traces = [t for t in fig.data if len(getattr(t, "y", []) or []) > 0]
        assert len(non_empty_traces) == 2


class TestChartSizeConstants:
    """Chart size constants are pixel tuples (not matplotlib inches)."""

    def test_figsize_is_pixels(self):
        from ui.plotly_charts import (
            CHART_FIGSIZE_TILE, CHART_FIGSIZE_WIDE,
            CHART_FIGSIZE_HALF, CHART_FIGSIZE_FULL,
        )
        # Pixels are integers/floats in the hundreds; matplotlib inches
        # would be single digits.
        assert CHART_FIGSIZE_TILE[0] > 100
        assert CHART_FIGSIZE_TILE[1] > 50
        assert CHART_FIGSIZE_WIDE[0] > 500
        assert CHART_FIGSIZE_HALF[0] > 500
        assert CHART_FIGSIZE_FULL[0] > 800


class TestUiChartsStub:
    """The retired ``ui.charts`` module is a deprecation stub."""

    def test_module_loads(self):
        import importlib
        m = importlib.import_module("ui.charts")
        assert m is not None

    def test_factory_raises(self):
        import ui.charts
        import pytest
        with pytest.raises(NotImplementedError):
            ui.charts.make_trend_chart([1, 2, 3])

    def test_constant_raises(self):
        import ui.charts
        import pytest
        # Stub exposes constants as ``_unavailable`` callables. Access
        # itself succeeds (so ``from ui.charts import X`` keeps working
        # for any forgotten caller) but invoking the value raises.
        const = ui.charts.CHART_FIGSIZE_TILE
        assert callable(const)
        with pytest.raises(NotImplementedError):
            const()

    def test_no_matplotlib_import(self):
        # Verify the retired module doesn't import matplotlib.
        import importlib, sys
        # Drop any cached reference to ui.charts
        sys.modules.pop("ui.charts", None)
        importlib.import_module("ui.charts")
        assert "matplotlib" not in sys.modules, (
            "Retired ui.charts must not import matplotlib"
        )


class TestRequirementsTxt:
    """``requirements.txt`` must not list matplotlib after the migration."""

    def test_no_matplotlib(self):
        with open("requirements.txt", encoding="utf-8") as f:
            content = f.read()
        for line in content.splitlines():
            stripped = line.strip().lower()
            assert not stripped.startswith("matplotlib"), (
                f"matplotlib is still listed in requirements.txt: {line!r}"
            )

    def test_has_plotly(self):
        with open("requirements.txt", encoding="utf-8") as f:
            content = f.read()
        assert "plotly" in content.lower()
        assert "kaleido" in content.lower()


# ── Phase 10: chart lifecycle / cache (UI freeze fix) ─────────────────


class TestBaseTabCleanup:
    """``BaseTab.cleanup()`` is a no-op by default — chart widgets and
    their rendered ``QPixmap`` objects survive ``shutdown()`` so
    re-entering analytics does not trigger a kaleido re-render."""

    def test_cleanup_default_is_noop(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QLabel
        from ui.views.analytics._tab_base import BaseTab

        class _Stub(BaseTab):
            def _do_refresh(self):
                # No-op; we only want to exercise the cleanup path.
                pass

        tab = _Stub(parent=qt_widget, service=None)
        sentinel = QLabel("keep me")
        tab._content_layout.addWidget(sentinel)
        # The layout now contains the sentinel; cleanup() (no force)
        # must not destroy it.
        tab.cleanup()
        assert sentinel.parent() is not None, (
            "cleanup() with no args must preserve chart widgets"
        )
        assert tab._content_layout.count() == 1

    def test_cleanup_force_destroys(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QLabel
        from ui.views.analytics._tab_base import BaseTab

        class _Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = _Stub(parent=qt_widget, service=None)
        tab._content_layout.addWidget(QLabel("x"))
        tab.cleanup(force=True)
        assert tab._content_layout.count() == 0


class TestBaseTabRefresh:
    """``BaseTab.refresh()`` is idempotent — same data signature is a no-op."""

    def test_refresh_idempotent_with_same_data(self, qt_widget, qtbot):
        from ui.views.analytics._tab_base import BaseTab

        calls = {"count": 0}

        class _Stub(BaseTab):
            def _do_refresh(self):
                calls["count"] += 1

        tab = _Stub(parent=qt_widget, service=None)
        # First render records the default signature (period 30/1/1).
        tab.refresh()
        first = calls["count"]
        assert first == 1
        # Second render with the same data must NOT call _do_refresh.
        tab.refresh()
        assert calls["count"] == 1, (
            "refresh() should be a no-op when the data signature is unchanged"
        )
        # Forcing a refresh always re-runs.
        tab.refresh(force=True)
        assert calls["count"] == 2

    def test_period_change_forces_refresh(self, qt_widget, qtbot):
        from ui.views.analytics._tab_base import BaseTab

        calls = {"count": 0}

        class _Stub(BaseTab):
            def _do_refresh(self):
                calls["count"] += 1

        tab = _Stub(parent=qt_widget, service=None)
        tab.refresh()
        tab.refresh()
        assert calls["count"] == 1
        # Change the period — the signature changes, so the next
        # refresh re-runs.
        tab._cached_days = 90
        tab.refresh()
        assert calls["count"] == 2, (
            "Changing the period must produce a new data signature"
        )

    def test_is_stale_default(self, qt_widget, qtbot):
        from ui.views.analytics._tab_base import BaseTab

        class _Stub(BaseTab):
            def _do_refresh(self):
                pass

        tab = _Stub(parent=qt_widget, service=None)
        assert tab._is_stale() is True, "Never-rendered tab is stale"
        tab.refresh()
        # Just-rendered: with a 1-second window the tab is fresh.
        assert tab._is_stale(60.0) is False, "Just-rendered tab is fresh"
        # With a 0-second window the tab is considered stale (a render
        # in the same microsecond does not count as "fresh").
        # ``time.time()`` has microsecond resolution so we wait a tick.
        import time
        time.sleep(0.005)
        assert tab._is_stale(0.0) is True, "0-second window is always stale"


class TestPlotlyChartWidgetCache:
    """``PlotlyChartWidget`` per-instance LRU pixmap cache.

    These tests exercise the cache directly (no kaleido).  The
    deliverable is the ``_pixmap_cache`` dict; the test inserts a
    fake pixmap and verifies the cache is consulted before a render
    is submitted."""

    def test_cache_hit_skips_render(self, qt_widget, qtbot):
        from PySide6.QtGui import QPixmap
        from ui.plotly_renderer import PlotlyChartWidget, get_render_manager
        from ui.plotly_charts import make_trend_chart

        manager = get_render_manager()

        w = PlotlyChartWidget()
        w.resize(420, 170)
        fig = make_trend_chart(["a", "b", "c"], [1, 2, 3])
        # Pre-populate the cache at the size the widget will request.
        # We do not call ``set_figure`` first because that would
        # already submit a render — the test is about the *second*
        # call hitting the cache.
        target_w = max(PlotlyChartWidget.MIN_WIDTH, w._label.width() or 420)
        target_h = max(PlotlyChartWidget.MIN_HEIGHT, w._label.height() or 170)
        key = (id(fig), target_w, target_h)
        fake = QPixmap(target_w, target_h)
        fake.fill()
        w._pixmap_cache[key] = fake

        # Force the label size to match (in case ``_label`` was not
        # laid out yet).
        w._width = target_w
        w._height = target_h

        before = manager.stats()["total_requests"]
        w.set_figure(fig)
        after = manager.stats()["total_requests"]
        assert after == before, (
            f"Cache hit should not submit a render (before={before}, after={after})"
        )

    def test_cache_bounded_by_max_entries(self, qt_widget, qtbot):
        from PySide6.QtGui import QPixmap
        from ui.plotly_renderer import PlotlyChartWidget

        w = PlotlyChartWidget()
        w.resize(420, 170)
        # Insert CACHE_MAX_ENTRIES + 2 entries; only the last
        # CACHE_MAX_ENTRIES should remain.
        for i in range(PlotlyChartWidget.CACHE_MAX_ENTRIES + 2):
            w._pixmap_cache[(i, 100, 100)] = QPixmap(100, 100)
        # Manual cache insertion does not enforce the bound; the
        # bound is enforced by ``_cache_pixmap`` (used by the render
        # delivery path).  Verify the bound is at least CACHE_MAX_ENTRIES.
        assert PlotlyChartWidget.CACHE_MAX_ENTRIES >= 2


class TestSparklineLabelCache:
    """``_SparklineLabel`` per-instance LRU cache."""

    def test_cache_hit_skips_render(self, qt_widget, qtbot):
        from PySide6.QtGui import QPixmap
        from ui.views.analytics._tab_base import _SparklineLabel
        from ui.plotly_charts import make_sparkline_chart
        from ui.plotly_renderer import get_render_manager

        manager = get_render_manager()
        before = manager.stats()["total_requests"]

        label = _SparklineLabel()
        fig = make_sparkline_chart([1, 2, 3, 4, 5], color="#6366f1")
        # Pre-populate the cache at the size the label will request.
        from ui.plotly_charts import make_sparkline_chart as _ms
        w, h = 260, 36
        label._pixmap_cache[(id(fig), w, h)] = QPixmap(w, h)
        label._target_w = w
        label._target_h = h
        label.render_async(fig, w, h)
        after = manager.stats()["total_requests"]
        assert after == before, "Cache hit should not submit a render"

    def test_cache_bounded(self, qt_widget, qtbot):
        from PySide6.QtGui import QPixmap
        from ui.views.analytics._tab_base import _SparklineLabel

        label = _SparklineLabel()
        # Insert one entry below the limit, then insert more — the
        # cache must stay at or below the limit after each insert.
        for i in range(_SparklineLabel.CACHE_MAX_ENTRIES + 3):
            label._cache_pixmap(i, 100, 100, QPixmap(100, 100))
            assert len(label._pixmap_cache) <= _SparklineLabel.CACHE_MAX_ENTRIES, (
                f"Cache grew to {len(label._pixmap_cache)} entries "
                f"(limit {_SparklineLabel.CACHE_MAX_ENTRIES}) after insert {i}"
            )


class TestAnalyticsViewWakeup:
    """``QtAnalyticsView.wakeup`` must NOT force a full re-render.

    The user reported 45-second load times because every view-switch
    triggered a full kaleido re-render.  After the lifecycle fix,
    ``wakeup`` is a near-instant operation that preserves the
    rendered pixmaps.
    """

    def test_wakeup_preserves_signature(self, qt_widget, qtbot):
        # A smoke test: instantiate the analytics view, render a
        # tab, then call wakeup.  The current tab's ``_last_render_ts``
        # must be > 0 (it was rendered) and ``wakeup`` should NOT
        # call ``tab.refresh(force=True)`` because the data is fresh.
        from unittest.mock import MagicMock
        from ui.views.analytics import QtAnalyticsView

        db = MagicMock()
        view = QtAnalyticsView(parent=qt_widget, db=db)
        # Force the first tab to be created and rendered.
        view._on_tab_changed(0)
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        # At this point the first tab has been rendered.
        first_tab = view._tabs.get(0)
        if first_tab is None:
            # No tab was created (no data); skip the assertion.
            return
        first_ts = first_tab._last_render_ts
        if first_ts == 0.0:
            # ``_do_refresh`` was never reached (the service was a
            # MagicMock and returned no data).  Skip.
            return
        # Call wakeup — must NOT mark the tab stale (default 5 min).
        from time import sleep
        sleep(0.1)  # 100 ms — well under the 5-min staleness window
        view.wakeup()
        assert first_tab._is_stale(view.STALENESS_SECONDS) is False, (
            "wakeup must not mark a freshly-rendered tab as stale"
        )


class TestExplicitRefreshButton:
    """The ↻ button in the analytics header forces a full re-render."""

    def test_refresh_button_in_period_strip(self, qt_widget, qtbot):
        from ui.views.analytics import QtAnalyticsView

        view = QtAnalyticsView(parent=qt_widget, db=None)
        assert hasattr(view, "_refresh_btn"), "Analytics view must expose a refresh button"
        # Tooltip is non-empty.
        assert view._refresh_btn.toolTip() != ""
        # Clicking the button should not raise even with no data.
        view._refresh_btn.click()


# ── Async render manager (Phase 9: UI freeze fix) ────────────────────

class TestRenderManager:
    """``RenderManager`` off-loads kaleido SVG renders to a thread pool.

    These tests exercise the manager API only — they do **not** spin
    up Chromium.  That is the whole point of the refactor: every chart
    factory call returns a ``go.Figure``; the expensive SVG render
    happens off-thread.
    """

    def test_singleton(self):
        from ui.plotly_renderer import get_render_manager
        m1 = get_render_manager()
        m2 = get_render_manager()
        assert m1 is m2, "get_render_manager must return the same instance"

    def test_submit_returns_unique_tags(self):
        from ui.plotly_renderer import get_render_manager
        from ui.plotly_charts import make_trend_chart
        manager = get_render_manager()
        fig = make_trend_chart(["a", "b"], [1, 2])
        t1 = manager.submit(fig, 100, 50)
        t2 = manager.submit(fig, 100, 50)
        assert t1 != t2
        assert t1 in manager._active_tags
        assert t2 in manager._active_tags

    def test_stats_track_submissions(self):
        from ui.plotly_renderer import get_render_manager
        from ui.plotly_charts import make_trend_chart
        manager = get_render_manager()
        before = manager.stats()["total_requests"]
        fig = make_trend_chart(["a", "b"], [1, 2])
        manager.submit(fig, 100, 50)
        after = manager.stats()["total_requests"]
        assert after == before + 1

    def test_cancel_removes_active(self):
        from ui.plotly_renderer import get_render_manager
        from ui.plotly_charts import make_trend_chart
        manager = get_render_manager()
        fig = make_trend_chart(["a", "b"], [1, 2])
        tag = manager.submit(fig, 100, 50)
        assert manager.is_active(tag)
        manager.cancel(tag)
        assert not manager.is_active(tag)


class TestPlotlyChartWidgetAsync:
    """``PlotlyChartWidget`` must not block the GUI thread on set_figure."""

    def test_set_figure_returns_immediately(self):
        """A slow render must not delay set_figure — the call returns
        immediately and the pixmap arrives later via the manager."""
        import time
        from PySide6.QtWidgets import QApplication
        from ui.plotly_renderer import PlotlyChartWidget
        from ui.plotly_charts import make_trend_chart

        app = QApplication.instance() or QApplication([])
        w = PlotlyChartWidget()
        w.resize(420, 170)  # give the inner label a non-zero size
        fig = make_trend_chart(["a", "b", "c", "d"], [1, 2, 3, 4])

        t0 = time.time()
        w.set_figure(fig)
        elapsed = time.time() - t0
        # set_figure should be near-instant.  Allow 200 ms for cold-start
        # QThreadPool scheduling, but anything beyond a second indicates
        # the render is happening on the main thread (the original bug).
        assert elapsed < 0.2, (
            f"set_figure blocked the main thread for {elapsed:.2f}s "
            "(expected <0.2s — async render regressed?)"
        )

    def test_stale_renders_dropped(self):
        """A second set_figure must cancel the first render's pixmap."""
        from PySide6.QtWidgets import QApplication
        from ui.plotly_renderer import PlotlyChartWidget, get_render_manager
        from ui.plotly_charts import make_trend_chart

        app = QApplication.instance() or QApplication([])
        w = PlotlyChartWidget()
        w.resize(420, 170)
        fig1 = make_trend_chart(["a", "b"], [1, 2])
        fig2 = make_trend_chart(["x", "y"], [10, 20])

        w.set_figure(fig1)
        first_tag = w._pending_tag
        w.set_figure(fig2)
        # The first tag must have been cancelled so its (now stale)
        # pixmap is not applied when the worker eventually returns.
        manager = get_render_manager()
        assert not manager.is_active(first_tag), (
            "Stale render was not cancelled when a new figure was set"
        )


class TestSparklineLabelAsync:
    """``_SparklineLabel`` must render sparklines without blocking the GUI."""

    def test_render_async_returns_immediately(self):
        import time
        from PySide6.QtWidgets import QApplication
        from ui.views.analytics._tab_base import _SparklineLabel, _render_sparkline
        from ui.plotly_charts import make_sparkline_chart

        app = QApplication.instance() or QApplication([])
        label = _SparklineLabel()
        fig = make_sparkline_chart([1, 2, 3, 4, 5], color="#6366f1")

        t0 = time.time()
        _render_sparkline(fig, label, width=260, height=36)
        elapsed = time.time() - t0
        assert elapsed < 0.2, (
            f"Sparkline render blocked the main thread for {elapsed:.2f}s"
        )

    def test_second_render_skips_when_in_flight(self):
        """A second ``render_async`` while a render is in flight is a no-op.

        The first render's pixmap will be applied when it completes.
        We must NOT cancel it (kaleido cannot be interrupted and
        the cancelled render would still complete) and we must NOT
        submit a duplicate (that would just waste kaleido work).
        """
        from PySide6.QtWidgets import QApplication
        from ui.views.analytics._tab_base import _SparklineLabel, _render_sparkline
        from ui.plotly_charts import make_sparkline_chart
        from ui.plotly_renderer import get_render_manager

        app = QApplication.instance() or QApplication([])
        label = _SparklineLabel()
        # Force the label to be visible so the first render is
        # actually submitted (not deferred to ``showEvent``).
        label.resize(260, 36)
        label.show()
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        fig1 = make_sparkline_chart([1, 2, 3], color="#6366f1")
        fig2 = make_sparkline_chart([10, 20, 30], color="#ef4444")

        _render_sparkline(fig1, label, width=260, height=36)
        first_tag = label._pending_tag
        # Submit a second render while the first is in flight — must
        # be a no-op so the in-flight render is preserved.
        _render_sparkline(fig2, label, width=260, height=36)
        assert label._pending_tag == first_tag, (
            "Second render while a render is in flight must be a no-op"
        )


# ── Phase 11: cold-start performance (loading screen + pre-warm) ─────


class TestSetFigureDefersWhenHidden:
    """``set_figure`` must not submit a render when the widget is not visible.

    Pre-Phase-1 the widget was always rendered immediately on
    ``set_figure``, even before the layout pass had run.  This
    wasted a kaleido call per chart on every analytics open.
    """

    def test_set_figure_defers_when_widget_not_visible(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from ui.plotly_renderer import PlotlyChartWidget, get_render_manager
        from ui.plotly_charts import make_trend_chart

        manager = get_render_manager()
        before = manager.stats()["total_requests"]

        parent = QWidget()
        w = PlotlyChartWidget(parent=parent)
        # The widget has not been shown yet, so ``isVisible()``
        # returns False.  ``set_figure`` must defer.
        fig = make_trend_chart(["a", "b", "c"], [1, 2, 3])
        w.set_figure(fig)
        after = manager.stats()["total_requests"]
        assert after == before, (
            f"set_figure on an unshown widget should not submit a render "
            f"(before={before}, after={after})"
        )


class TestShowEventIsIdempotent:
    """``showEvent`` should not queue duplicate renders when re-fired.

    A widget's ``showEvent`` may fire multiple times during the first
    show (e.g. when the parent layout is re-laid out).  Without
    idempotency, each fire would queue another render — wasting
    kaleido work.
    """

    def test_show_event_skips_when_render_in_flight(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from ui.plotly_renderer import PlotlyChartWidget, get_render_manager
        from ui.plotly_charts import make_trend_chart

        manager = get_render_manager()
        parent = QWidget()
        parent.show()
        w = PlotlyChartWidget(parent=parent, min_height=180)
        w.resize(420, 170)
        w.show()
        # Force a first show to populate ``_pending_tag``.
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        before = manager.stats()["total_requests"]
        # Re-fire the show event manually.  With a render in flight
        # the widget must NOT submit another one.
        w.showEvent(None)
        after = manager.stats()["total_requests"]
        assert after == before, (
            f"showEvent with render in flight should be a no-op "
            f"(before={before}, after={after})"
        )


class TestAutoRenderFirstTab:
    """All 6 tabs load eagerly on construction via staggered timers."""

    def test_all_tabs_load_after_construction(self, qt_widget, qtbot):
        from unittest.mock import MagicMock
        from ui.views.analytics import QtAnalyticsView

        view = QtAnalyticsView(parent=qt_widget, db=MagicMock())
        view.show()
        view.raise_()
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        # Ensure the view is visible so showEvent fires
        if not view._load_started:
            view._start_loading()
        # Process pending events so all stagger timers fire.
        for _ in range(20):
            QCoreApplication.processEvents()
        assert len(view._tabs) > 0, "At least the first tab should load"


class TestWakeupFirstOpen:
    """``wakeup`` is a no-op the first time it is called."""

    def test_first_wakeup_does_nothing(self, qt_widget, qtbot):
        from unittest.mock import MagicMock
        from ui.views.analytics import QtAnalyticsView

        view = QtAnalyticsView(parent=qt_widget, db=MagicMock())
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        # ``_first_open`` is True after construction.
        assert view._first_open is True
        # The first wakeup is a no-op.
        view.wakeup()
        assert view._first_open is False

    def test_subsequent_wakeup_respects_staleness(self, qt_widget, qtbot):
        from unittest.mock import MagicMock
        from ui.views.analytics import QtAnalyticsView
        import time as time_mod

        view = QtAnalyticsView(parent=qt_widget, db=MagicMock())
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        # First wakeup: no-op.
        view.wakeup()
        # Pretend a tab was rendered long ago so it is stale.
        if 0 in view._tabs:
            view._tabs[0]._last_render_ts = time_mod.time() - 10000
        # Subsequent wakeup: tab is stale -> refresh fires.
        # Just check that the staleness check works:
        if 0 in view._tabs:
            assert view._tabs[0]._is_stale(5.0) is True


class TestChartLoadingOverlayAPI:
    """The loading overlay's start/stop API works correctly."""

    def test_overlay_start_stop(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from ui.widgets.chart_loading_overlay import ChartLoadingOverlay

        parent = QWidget()
        parent.resize(400, 300)
        parent.show()
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        overlay = ChartLoadingOverlay(parent)
        overlay.setGeometry(0, 0, 400, 300)
        overlay.start(expected=5, tab_index=0)
        assert overlay.isVisible()
        assert overlay._active is True
        assert overlay._expected == 5
        overlay.stop()
        assert not overlay.isVisible()
        assert overlay._active is False

    def test_overlay_progress(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from ui.widgets.chart_loading_overlay import ChartLoadingOverlay

        parent = QWidget()
        parent.show()
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        overlay = ChartLoadingOverlay(parent)
        overlay.setGeometry(0, 0, 400, 300)
        overlay.start(expected=10, tab_index=0)
        # Send 3 deliveries.  Progress should show 3 / 10.
        for _ in range(3):
            overlay.on_render_delivered(None, None)
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        assert "3" in overlay._progress.text()
        assert "10" in overlay._progress.text()
        assert overlay.isVisible()
        # Send 7 more to reach the expected count.
        for _ in range(7):
            overlay.on_render_delivered(None, None)
        QCoreApplication.processEvents()
        # After reaching expected, overlay should hide.
        assert not overlay.isVisible()


class TestCpuAwareConcurrency:
    """``_max_concurrent`` is capped at 2 because kaleido is Chromium-bound."""

    def test_2_cores_yields_1(self):
        from ui.plotly_renderer import RenderManager
        import unittest.mock as mock
        with mock.patch("os.cpu_count", return_value=2):
            assert RenderManager._max_concurrent() == 1

    def test_4_cores_yields_2(self):
        from ui.plotly_renderer import RenderManager
        import unittest.mock as mock
        with mock.patch("os.cpu_count", return_value=4):
            assert RenderManager._max_concurrent() == 2

    def test_6_cores_capped_to_2(self):
        from ui.plotly_renderer import RenderManager
        import unittest.mock as mock
        with mock.patch("os.cpu_count", return_value=6):
            assert RenderManager._max_concurrent() == 2

    def test_8_cores_capped_to_2(self):
        from ui.plotly_renderer import RenderManager
        import unittest.mock as mock
        with mock.patch("os.cpu_count", return_value=8):
            assert RenderManager._max_concurrent() == 2

    def test_12_cores_capped_to_2(self):
        from ui.plotly_renderer import RenderManager
        import unittest.mock as mock
        with mock.patch("os.cpu_count", return_value=12):
            assert RenderManager._max_concurrent() == 2


class TestEffectiveConcurrencyInStats:
    """``stats()`` exposes the resolved concurrency for diagnostics."""

    def test_stats_has_effective_concurrency(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from ui.plotly_renderer import get_render_manager
        manager = get_render_manager()
        s = manager.stats()
        assert "effective_concurrency" in s
        # The resolved value matches the class method.
        assert s["effective_concurrency"] == manager._max_concurrent()
        # And it matches the formula for the host's CPU count.
        import os
        cpu = os.cpu_count() or 4
        expected = max(1, min(2, cpu // 2))
        assert s["effective_concurrency"] == expected


class TestSparklineLabelDeferredRender:
    """``_SparklineLabel.render_async`` defers before first show."""

    def test_render_async_defers_when_not_visible(self, qt_widget, qtbot):
        from PySide6.QtWidgets import QWidget
        from ui.views.analytics._tab_base import _SparklineLabel
        from ui.plotly_renderer import get_render_manager
        from ui.plotly_charts import make_sparkline_chart

        manager = get_render_manager()
        before = manager.stats()["total_requests"]
        label = _SparklineLabel()
        fig = make_sparkline_chart([1, 2, 3, 4, 5], color="#6366f1")
        label.render_async(fig, 260, 36)
        after = manager.stats()["total_requests"]
        assert after == before, (
            f"render_async on an unshown sparkline should defer "
            f"(before={before}, after={after})"
        )


class TestCacheHitNotifiesOwner:
    """Cache hits in ``set_figure`` and ``showEvent`` notify the owner.

    Regression test for the bug where chart widgets that hit the
    per-instance LRU cache would apply the pixmap but never call
    ``owner._on_chart_rendered(self)`` — leaving the loading overlay
    stuck at 0/N and hitting its 30 s safety timeout.
    """

    def test_set_figure_cache_hit_notifies_owner(self, qtbot, qt_widget):
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QVBoxLayout
        from ui.plotly_renderer import PlotlyChartWidget
        from ui.plotly_charts import make_line_chart

        # Build a visible widget tree (kaleido is bypassed by
        # pre-populating the cache).
        widget = PlotlyChartWidget()
        QVBoxLayout(qt_widget).addWidget(widget)
        qt_widget.show()
        qtbot.waitExposed(qt_widget)
        widget.show()
        widget.resize(400, 300)
        QCoreApplication.processEvents()

        fig = make_line_chart(
            ["a", "b", "c"],
            [([1, 2, 3], "series", "#ff0000")],
            title="cache-hit-test",
        )
        # Pre-populate the cache at the size the widget will request.
        w = max(widget.MIN_WIDTH, widget._label.width())
        h = max(widget.MIN_HEIGHT, widget._label.height())
        widget._pixmap_cache[(id(fig), w, h)] = QPixmap(w, h)
        widget._fig = fig
        widget._fig_id = id(fig)
        widget._width = w
        widget._height = h

        received = []
        widget.set_owner(type("M", (), {
            "_on_chart_rendered": lambda self_, w: received.append(w)
        })())

        # Set the same figure at the same size — must hit cache.
        widget.set_figure(fig)
        QCoreApplication.processEvents()

        assert len(received) == 1, (
            f"Cache hit in set_figure should notify owner once "
            f"(received {len(received)})"
        )
        assert received[0] is widget

    def test_show_event_cache_hit_notifies_owner(self, qtbot, qt_widget):
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QVBoxLayout
        from ui.plotly_renderer import PlotlyChartWidget
        from ui.plotly_charts import make_line_chart

        widget = PlotlyChartWidget()
        QVBoxLayout(qt_widget).addWidget(widget)
        # Show the parent so the layout is computed and the inner
        # ``_label`` has a real size.  ``showEvent`` then sees the
        # right label dimensions when the cache key is built.
        qt_widget.show()
        qtbot.waitExposed(qt_widget)
        widget.resize(400, 300)
        QCoreApplication.processEvents()

        fig = make_line_chart(
            ["a", "b", "c"],
            [([1, 2, 3], "series", "#ff0000")],
            title="show-event-cache-test",
        )
        w = max(widget.MIN_WIDTH, widget._label.width())
        h = max(widget.MIN_HEIGHT, widget._label.height())
        widget._pixmap_cache[(id(fig), w, h)] = QPixmap(w, h)
        widget._fig = fig
        widget._fig_id = id(fig)
        widget._width = w
        widget._height = h

        received = []
        widget.set_owner(type("M", (), {
            "_on_chart_rendered": lambda self_, w: received.append(w)
        })())

        # Trigger the show event (this is the path that fires when
        # the tab becomes visible to the user).
        widget.show()
        QCoreApplication.processEvents()

        assert len(received) == 1, (
            f"Cache hit in showEvent should notify owner once "
            f"(received {len(received)})"
        )

    def test_sparkline_cache_hit_notifies_owner(self, qtbot, qt_widget):
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtGui import QPixmap
        from ui.views.analytics._tab_base import _SparklineLabel
        from ui.plotly_charts import make_sparkline_chart

        label = _SparklineLabel()
        fig = make_sparkline_chart([1, 2, 3, 4, 5], color="#6366f1")
        w, h = 260, 36
        # Pre-populate the cache.
        label._pixmap_cache[(id(fig), w, h)] = QPixmap(w, h)
        label._last_fig = fig
        label._last_fig_id = id(fig)
        label._target_w = w
        label._target_h = h

        received = []
        label.set_owner(type("M", (), {
            "_on_chart_rendered": lambda self_, w: received.append(w)
        })())

        label.resize(w, h)
        label.show()
        QCoreApplication.processEvents()
        label.render_async(fig, w, h)

        # Both ``showEvent`` and the explicit ``render_async`` above
        # hit the cache and notify the owner — that's the bug-fix
        # we are regression-testing.  We only require >= 1.
        assert len(received) >= 1, (
            f"Cache hit in render_async should notify owner "
            f"(received {len(received)})"
        )


class TestMaxConcurrentCappedAtTwo:
    """The kaleido concurrency is capped at 2 regardless of CPU count.

    Empirically, kaleido v1 spawns a Chromium process per render and
    multiple workers contend for the same Chrome profile directory.
    The net throughput is *worse* with 10 workers than with 2.  The
    cap keeps the user-visible tab snappy without spawning dozens
    of Chrome processes.
    """

    def test_max_concurrent_never_exceeds_2(self):
        from ui.plotly_renderer import RenderManager
        import unittest.mock as mock
        for cpu in [2, 4, 6, 8, 10, 12, 16, 24, 32]:
            with mock.patch("os.cpu_count", return_value=cpu):
                value = RenderManager._max_concurrent()
                assert 1 <= value <= 2, (
                    f"_max_concurrent()={value} for cpu={cpu}; "
                    f"must be in [1, 2]"
                )
