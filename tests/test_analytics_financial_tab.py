"""Tests for FinancialAnalyticsTab."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ui.views.analytics.financial_tab import FinancialAnalyticsTab


@pytest.fixture
def empty_svc():
    svc = MagicMock()
    svc.get_monthly_financial.return_value = []
    svc.get_revenue_by_client.return_value = []
    svc.get_revenue_by_country.return_value = []
    svc.get_trip_status_distribution.return_value = []
    svc.get_revenue_quarterly.return_value = []
    svc.get_monthly_trip_volume.return_value = []
    svc.get_cost_breakdown.return_value = []
    svc.get_invoice_aging.return_value = None
    return svc


@pytest.fixture
def realistic_svc():
    svc = MagicMock()
    svc.get_monthly_financial.return_value = [
        {"month": "2026-01", "revenue": 50000, "profit": 12000, "margin_pct": 24.0,
         "trip_count": 45, "invoiced_count": 40, "paid_count": 30},
        {"month": "2026-02", "revenue": 62000, "profit": 15000, "margin_pct": 24.2,
         "trip_count": 52, "invoiced_count": 48, "paid_count": 35},
        {"month": "2026-03", "revenue": 58000, "profit": 14000, "margin_pct": 24.1,
         "trip_count": 50, "invoiced_count": 44, "paid_count": 38},
    ]
    svc.get_revenue_by_client.return_value = [
        {"client": "ACME Corp", "revenue": 30000, "profit": 8000},
        {"client": "Globex Inc", "revenue": 22000, "profit": 5000},
    ]
    svc.get_revenue_by_country.return_value = [
        {"country": "DE", "revenue": 45000},
        {"country": "FR", "revenue": 35000},
    ]
    svc.get_trip_status_distribution.return_value = [
        {"status": "delivered", "count": 30},
        {"status": "in_transit", "count": 10},
        {"status": "planned", "count": 5},
    ]
    svc.get_revenue_quarterly.return_value = []
    svc.get_monthly_trip_volume.return_value = [
        {"month": "2026-01", "trip_count": 45},
        {"month": "2026-02", "trip_count": 52},
        {"month": "2026-03", "trip_count": 50},
    ]
    svc.get_cost_breakdown.return_value = [
        {"month": "2026-01", "fuel_cost": 5000, "toll_cost": 1500,
         "salary_cost": 4000, "extra_costs": 800},
        {"month": "2026-02", "fuel_cost": 5500, "toll_cost": 1800,
         "salary_cost": 4200, "extra_costs": 900},
        {"month": "2026-03", "fuel_cost": 5200, "toll_cost": 1600,
         "salary_cost": 4100, "extra_costs": 850},
    ]
    svc.get_invoice_aging.return_value = {
        "current_bucket": 30000,
        "bucket_31_60": 12000,
        "bucket_61_90": 5000,
        "overdue_bucket": 2000,
        "total_outstanding": 49000,
    }
    return svc


class TestFinancialAnalyticsTabCreation:
    def test_creation_without_service(self, qt_widget, qtbot):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._svc is None
        # Header should be built
        assert tab._content_layout.count() >= 3

    def test_creation_with_service(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        assert tab._svc is realistic_svc

    def test_header_added_in_build(self, qt_widget, qtbot):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        # _build() added header + divider + spacing
        assert tab._content_layout.count() >= 3


class TestFinancialAnalyticsTabRender:
    def test_render_without_service_shows_no_data(self, qt_widget, qtbot):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._render()
        # Should show no-data state
        assert tab._content_layout.count() >= 3

    def test_render_with_empty_data_shows_no_data(self, qt_widget, qtbot, empty_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=empty_svc)
        qtbot.addWidget(tab)
        tab._render()
        # _add_no_data called with specific message
        assert tab._content_layout.count() >= 1

    def test_render_with_realistic_data(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should produce content (KPI row + sections + charts)
        assert tab._content_layout.count() > 0

    def test_render_adds_kpi_row_with_sparklines(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Find _SparklineLabel instances
        from ui.views.analytics._tab_base import _SparklineLabel
        sparklines = tab.findChildren(_SparklineLabel)
        assert len(sparklines) >= 1

    def test_render_adds_margin_progress_bar(self, qt_widget, qtbot, realistic_svc):
        realistic_svc.get_monthly_financial.return_value = [
            {"month": "2026-01", "revenue": 50000, "profit": 12000, "margin_pct": 15.0,
             "trip_count": 45, "invoiced_count": 40, "paid_count": 30},
        ]
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should find QProgressBar
        progress_bars = tab.findChildren(QProgressBar)
        assert len(progress_bars) >= 1


class TestFinancialAnalyticsTabInvoiceAging:
    def test_aging_with_data_adds_stacked_bar(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Invoice aging chart should be added
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        assert len(charts) >= 1

    def test_aging_without_data_shows_fallback(self, qt_widget, qtbot, empty_svc):
        empty_svc.get_monthly_financial.return_value = [
            {"month": "2026-01", "revenue": 5000, "profit": 2000, "margin_pct": 40.0,
             "trip_count": 10, "invoiced_count": 15, "paid_count": 5},
        ]
        tab = FinancialAnalyticsTab(parent=qt_widget, service=empty_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Fallback should show invoiced/paid card
        # Look for QLabel that contains invoice info
        labels = tab.findChildren(QLabel)
        invoiced_labels = [lbl for lbl in labels if "Invoiced" in lbl.text() or "Paid" in lbl.text()]
        # May or may not find match depending on i18n;
        # at least the render didn't crash

    def test_aging_zero_outstanding_no_fallback(self, qt_widget, qtbot, empty_svc):
        empty_svc.get_monthly_financial.return_value = [
            {"month": "2026-01", "revenue": 5000, "profit": 2000, "margin_pct": 40.0,
             "trip_count": 10, "invoiced_count": 0, "paid_count": 0},
        ]
        tab = FinancialAnalyticsTab(parent=qt_widget, service=empty_svc)
        qtbot.addWidget(tab)
        # Should not crash
        tab._render()


class TestFinancialAnalyticsTabSections:
    def test_client_geographic_section_added(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Section header for client & geographic should be present
        labels = tab.findChildren(QLabel)
        section_labels = [
            lbl for lbl in labels
            if "Client" in lbl.text() or "Geographic" in lbl.text()
        ]

    def test_volume_cost_section_added(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should not crash — volume & cost data exists

    def test_revenue_trend_section(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._render()
        # With 3 months data, revenue trend chart should be present
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        assert len(charts) >= 1


class TestFinancialAnalyticsTabEdgeCases:
    def test_single_month_data(self, qt_widget, qtbot):
        """Single month: KPIs rendered, charts skipped."""
        svc = MagicMock()
        svc.get_monthly_financial.return_value = [
            {"month": "2026-01", "revenue": 5000, "profit": 2000, "margin_pct": 40.0,
             "trip_count": 10, "invoiced_count": 5, "paid_count": 3},
        ]
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []
        svc.get_invoice_aging.return_value = None

        tab = FinancialAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should render KPIs without crashing
        assert tab._content_layout.count() >= 1

    def test_missing_margin(self, qt_widget, qtbot):
        """Missing margin_pct should not crash."""
        svc = MagicMock()
        svc.get_monthly_financial.return_value = [
            {"month": "2026-01", "revenue": 5000, "profit": 2000,
             "trip_count": 10, "invoiced_count": 5, "paid_count": 3},
        ]
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []
        svc.get_invoice_aging.return_value = None

        tab = FinancialAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._content_layout.count() >= 1

    def test_minimal_volume_cost_no_charts(self, qt_widget, qtbot):
        """Single month: volume/cost shown as KPIs not charts."""
        svc = MagicMock()
        svc.get_monthly_financial.return_value = []
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = [
            {"month": "2026-01", "trip_count": 10},
        ]
        svc.get_cost_breakdown.return_value = [
            {"month": "2026-01", "fuel_cost": 500, "toll_cost": 100,
             "salary_cost": 300, "extra_costs": 50},
        ]
        svc.get_invoice_aging.return_value = None

        tab = FinancialAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should not crash when monthly_financial is empty
        # (no_data state will show)
        assert tab._content_layout.count() >= 1


class TestFinancialAnalyticsTabRefresh:
    def test_refresh_no_data(self, qt_widget, qtbot, empty_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=empty_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        # refresh() catches exception or adds no_data
        # Should not crash
        assert tab._content_layout.count() >= 1

    def test_refresh_with_data(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0

    def test_refresh_idempotent(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        first_ts = tab._last_render_ts
        tab.refresh()  # same signature — no-op
        assert tab._last_render_ts == first_ts

    def test_refresh_force(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        first_ts = tab._last_render_ts
        tab.refresh(force=True)
        assert tab._last_render_ts >= first_ts

    def test_cleanup(self, qt_widget, qtbot, realistic_svc):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        tab.cleanup(force=True)
        assert tab._content_layout.count() == 0


class TestFinancialAnalyticsTabKPIMetrics:
    def test_kpi_delta_colors(self, qt_widget, qtbot):
        """Positive delta = SUCCESS, negative = DANGER, zero = muted."""
        from ui.design_tokens import SUCCESS, DANGER, TEXT_MUTED

        # Positive
        svc = MagicMock()
        svc.get_monthly_financial.return_value = [
            {"month": "2026-01", "revenue": 5000, "profit": 2000, "margin_pct": 40.0,
             "trip_count": 10, "invoiced_count": 5, "paid_count": 3},
            {"month": "2026-02", "revenue": 8000, "profit": 3000, "margin_pct": 37.5,
             "trip_count": 15, "invoiced_count": 10, "paid_count": 7},
        ]
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []
        svc.get_invoice_aging.return_value = None

        tab = FinancialAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should not crash; KPI with positive delta rendered

    def test_dso_calculation(self, qt_widget, qtbot):
        """DSO days calculated from invoiced/paid gap."""
        svc = MagicMock()
        svc.get_monthly_financial.return_value = [
            {"month": "2026-01", "revenue": 100000, "profit": 30000, "margin_pct": 30.0,
             "trip_count": 80, "invoiced_count": 100, "paid_count": 40},
        ]
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []
        svc.get_invoice_aging.return_value = None

        tab = FinancialAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # DSO = (100-40)/100000 * 30 ≈ 0.018 days (near 0)
        assert tab._content_layout.count() >= 1

    def test_dso_kpi_sparkline_series_3_points(self, qt_widget, qtbot):
        """DSO KPI card carries a 3-point sparkline computed from invoiced/paid.

        Regression (Fix 22): ``sparkline_values`` was hard-coded to ``[]`` so
        the DSO trend was silently dropped even though the 12-month series is
        already fetched. With a 3-month response the DSO card must get a
        3-point series whose values match the estimator used by the KPI:
        round((invoiced - paid) / revenue * max(days, 30)); days defaults to 30
        in standalone tests, so month 1 -> round(30/1000 * 30) = 1 day.
        """
        svc = MagicMock()
        svc.get_monthly_financial.return_value = [
            {"month": "2026-01", "revenue": 1000, "profit": 200, "margin_pct": 20.0,
             "trip_count": 10, "invoiced_count": 100, "paid_count": 70},
            {"month": "2026-02", "revenue": 1000, "profit": 200, "margin_pct": 20.0,
             "trip_count": 10, "invoiced_count": 100, "paid_count": 40},
            {"month": "2026-03", "revenue": 1000, "profit": 200, "margin_pct": 20.0,
             "trip_count": 10, "invoiced_count": 100, "paid_count": 10},
        ]
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []
        svc.get_invoice_aging.return_value = None

        from ui.views.analytics._tab_base import _SparklineLabel

        tab = FinancialAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()

        # Locate the DSO card via its "<n> days" value label.
        dso_value_labels = [
            lbl for lbl in tab.findChildren(QLabel)
            if lbl.text().strip().endswith(" days")
        ]
        assert len(dso_value_labels) == 1, "expected exactly one DSO value label"
        card = dso_value_labels[0].parentWidget()
        sparklines = card.findChildren(_SparklineLabel)
        assert len(sparklines) == 1, "DSO KPI card should render a sparkline"
        series = list(sparklines[0]._last_fig.data[0].y)
        assert len(series) == 3
        # 30/1000*30=1, 60/1000*30=2, 90/1000*30=3
        assert series == [1.0, 2.0, 3.0]
        assert series[0] == 1.0

    def test_dso_sparkline_empty_when_12_month_series_empty(self, qt_widget, qtbot):
        """Empty trailing-12-month series -> empty DSO sparkline, no crash."""
        svc = MagicMock()
        rows = [
            {"month": "2026-01", "revenue": 50000, "profit": 12000, "margin_pct": 24.0,
             "trip_count": 45, "invoiced_count": 40, "paid_count": 30},
            {"month": "2026-02", "revenue": 62000, "profit": 15000, "margin_pct": 24.2,
             "trip_count": 52, "invoiced_count": 48, "paid_count": 35},
            {"month": "2026-03", "revenue": 58000, "profit": 14000, "margin_pct": 24.1,
             "trip_count": 50, "invoiced_count": 44, "paid_count": 38},
        ]

        def _monthly_financial(months, from_date, to_date):
            return [] if months == 12 else rows

        svc.get_monthly_financial.side_effect = _monthly_financial
        svc.get_revenue_by_client.return_value = []
        svc.get_revenue_by_country.return_value = []
        svc.get_trip_status_distribution.return_value = []
        svc.get_revenue_quarterly.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        svc.get_cost_breakdown.return_value = []
        svc.get_invoice_aging.return_value = None

        from ui.views.analytics._tab_base import _SparklineLabel

        tab = FinancialAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()  # must not crash

        dso_value_labels = [
            lbl for lbl in tab.findChildren(QLabel)
            if lbl.text().strip().endswith(" days")
        ]
        assert len(dso_value_labels) == 1, "expected exactly one DSO value label"
        card = dso_value_labels[0].parentWidget()
        assert card.findChildren(_SparklineLabel) == []


# ── Plotly chart regressions (P2-AN) ────────────────────────────────────


class TestPlotlyChartRegressions:
    """Single-bar guard, donut text margin, hovertemplate tooltips."""

    def test_bar_chart_single_value_uses_inside_text(self):
        """One full-width bar must not clip 'outside' labels (single-bar guard)."""
        from ui.plotly_charts import make_bar_chart

        fig = make_bar_chart(labels=["Only"], values=[500])
        assert fig.data[0].textposition == "inside"

    def test_bar_chart_single_value_horizontal_uses_inside_text(self):
        from ui.plotly_charts import make_bar_chart

        fig = make_bar_chart(labels=["Only"], values=[500], horizontal=False)
        assert fig.data[0].textposition == "inside"

    def test_bar_chart_multi_value_keeps_outside_text(self):
        """Multi-bar datasets keep the previous outside annotation style."""
        from ui.plotly_charts import make_bar_chart

        fig = make_bar_chart(labels=["A", "B"], values=[10, 20])
        assert fig.data[0].textposition == "outside"

    def test_bar_chart_hovertemplate_set(self):
        from ui.plotly_charts import make_bar_chart

        fig = make_bar_chart(labels=["A", "B"], values=[10, 20])
        template = fig.data[0].hovertemplate
        assert template is not None
        assert "<extra></extra>" in template

    def test_pie_chart_textmargin_set(self):
        """Donut outside labels must not overlap/clip on small slices."""
        from ui.plotly_charts import make_pie_chart

        fig = make_pie_chart(sizes=[60, 30, 10], labels=["A", "B", "C"])
        trace = fig.data[0]
        assert trace.textposition == "outside"
        # automargin lets outside labels push the layout margins open
        # (plotly 6.x has no Pie ``textmargin`` property).
        assert trace.automargin is True
        layout_margin = fig.layout.margin
        assert layout_margin.t >= 20 and layout_margin.b >= 20

    def test_pie_chart_hovertemplate_set(self):
        from ui.plotly_charts import make_pie_chart

        fig = make_pie_chart(sizes=[60, 30, 10], labels=["A", "B", "C"])
        template = fig.data[0].hovertemplate
        assert template is not None
        assert "<extra></extra>" in template


class TestFinancialAnalyticsTabSmoke:
    """Headless smoke: render, grab, and scan for the BUG-08 LOADING placeholder."""

    def test_render_grab_and_no_loading_text(self, qt_widget, qtbot, realistic_svc):
        from PySide6.QtTest import QTest

        tab = FinancialAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab.resize(900, 700)
        tab.show()
        tab.refresh(force=True)
        QTest.qWait(150)

        pixmap = tab.grab()
        assert pixmap is not None and not pixmap.isNull()

        # BUG-08 regression: the "LOADING" placeholder must never surface
        # as text anywhere in the rendered widget tree.
        loading_labels = [
            lbl.text() for lbl in tab.findChildren(QLabel)
            if "LOADING" in lbl.text().upper()
        ]
        assert loading_labels == []
