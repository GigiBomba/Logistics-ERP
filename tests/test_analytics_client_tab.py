"""Tests for ClientAnalyticsTab."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.views.analytics.client_tab import ClientAnalyticsTab


@pytest.fixture
def realistic_svc():
    svc = MagicMock()
    svc.get_revenue_by_client.return_value = [
        {"client": "ACME Corp", "revenue": 50000, "profit": 15000, "trip_count": 30},
        {"client": "Globex Inc", "revenue": 35000, "profit": 8000, "trip_count": 22},
        {"client": "Umbrella Ltd", "revenue": 28000, "profit": 5000, "trip_count": 18},
        {"client": "Stark Ind", "revenue": 22000, "profit": -2000, "trip_count": 15},
        {"client": "Wayne Ent", "revenue": 18000, "profit": 6000, "trip_count": 12},
    ]
    svc.get_client_analytics.return_value = [
        {"client": "ACME Corp", "trip_count": 30, "revenue": 50000,
         "profit": 15000, "avg_payment_delay_days": 15},
        {"client": "Globex Inc", "trip_count": 22, "revenue": 35000,
         "profit": 8000, "avg_payment_delay_days": 35},
        {"client": "Umbrella Ltd", "trip_count": 18, "revenue": 28000,
         "profit": 5000, "avg_payment_delay_days": 50},
    ]
    svc.get_client_growth.return_value = [
        {"month": "2026-01", "new_clients": 3},
        {"month": "2026-02", "new_clients": 2},
        {"month": "2026-03", "new_clients": 4},
    ]
    svc.get_revenue_concentration.return_value = [
        {"client": "ACME Corp", "revenue": 50000, "profit": 15000},
        {"client": "Globex Inc", "revenue": 35000, "profit": 8000},
        {"client": "Umbrella Ltd", "revenue": 28000, "profit": 5000},
        {"client": "Stark Ind", "revenue": 22000, "profit": -2000},
        {"client": "Wayne Ent", "revenue": 18000, "profit": 6000},
    ]
    return svc


class TestClientAnalyticsTabCreation:
    def test_creation_without_service(self, qt_widget, qtbot):
        tab = ClientAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._svc is None
        assert tab._chart_widget is not None
        assert tab._chart_layout is not None

    def test_creation_with_service(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        assert tab._svc is realistic_svc

    def test_header_added_in_build(self, qt_widget, qtbot):
        tab = ClientAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._content_layout.count() >= 2  # header + chart widget


class TestClientAnalyticsTabRender:
    def test_render_without_service_shows_no_data(self, qt_widget, qtbot):
        tab = ClientAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._render()
        # No-data state should be present
        assert tab._content_layout.count() >= 1

    def test_render_with_empty_data_shows_no_data(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_revenue_by_client.return_value = []
        svc.get_client_analytics.return_value = []
        svc.get_client_growth.return_value = []
        svc.get_revenue_concentration.return_value = []

        tab = ClientAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should show no-data state
        assert tab._content_layout.count() >= 1

    def test_render_with_realistic_data(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should have KPI row + charts
        assert tab._chart_layout.count() >= 3  # KPI row + chart row + more

    def test_render_adds_kpi_row(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._render()
        # KPI row should exist: 4 KPI cards
        from ui.plotly_renderer import PlotlyChartWidget
        # There should be PlotlyChartWidget instances for charts
        charts = tab.findChildren(PlotlyChartWidget)
        assert len(charts) >= 1


class TestClientAnalyticsTabMakeClientKpi:
    def test_make_client_kpi_single_line(self, qt_widget, qtbot):
        card = ClientAnalyticsTab._make_client_kpi(
            label="Total Clients", value="42"
        )
        qtbot.addWidget(card)
        assert isinstance(card, QFrame)
        labels = card.findChildren(QLabel)
        assert len(labels) >= 2  # label + value

    def test_make_client_kpi_multiline(self, qt_widget, qtbot):
        card = ClientAnalyticsTab._make_client_kpi(
            label="Top Client", value="ACME\n€ 50,000", multiline=True
        )
        qtbot.addWidget(card)
        assert isinstance(card, QFrame)

    def test_make_client_kpi_with_color(self, qt_widget, qtbot):
        card = ClientAnalyticsTab._make_client_kpi(
            label="Avg Payment Delay", value="45 days",
            value_color="#F59E0B",
        )
        qtbot.addWidget(card)
        assert isinstance(card, QFrame)


class TestClientAnalyticsTabInsightBanner:
    def test_build_insight_banner_info(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._build_insight_banner("Test insight text")
        # Banner was added to chart_layout
        assert tab._chart_layout.count() >= 1

    def test_build_insight_banner_warning(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._build_insight_banner("Warning insight", warning=True)
        assert tab._chart_layout.count() >= 1

    def test_insight_banner_has_icon_qlabel(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab._build_insight_banner("Test")
        # Find the icon label
        labels = tab.findChildren(QLabel)
        icon_labels = [lbl for lbl in labels if lbl.text() == "\U0001f4a1"]
        assert len(icon_labels) >= 1


class TestClientAnalyticsTabPaymentTimeline:
    def test_build_payment_timeline(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        clients = realistic_svc.get_client_analytics()
        tab._build_payment_timeline(clients)
        assert tab._chart_layout.count() >= 1

    def test_build_payment_timeline_empty(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        # Empty list → no-op
        tab._build_payment_timeline([])
        # Only spacing was added — no container

    def test_build_payment_timeline_no_delays(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        clients = [
            {"client": "Fast Payer", "avg_payment_delay_days": 0},
        ]
        tab._build_payment_timeline(clients)
        # No positive delay → returns early


class TestClientAnalyticsTabRefresh:
    def test_refresh_empty(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_revenue_by_client.return_value = []
        svc.get_client_analytics.return_value = []
        svc.get_client_growth.return_value = []
        svc.get_revenue_concentration.return_value = []

        tab = ClientAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0
        assert tab._content_layout.count() >= 1

    def test_refresh_with_realistic_data(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0

    def test_cleanup(self, qt_widget, qtbot, realistic_svc):
        tab = ClientAnalyticsTab(parent=qt_widget, service=realistic_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        tab.cleanup(force=True)
        assert tab._content_layout.count() == 0


class TestClientAnalyticsTabEdgeCases:
    def test_no_revenue_by_client(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_revenue_by_client.return_value = []
        svc.get_client_analytics.return_value = [
            {"client": "ACME", "trip_count": 10, "revenue": 5000,
             "profit": 1000, "avg_payment_delay_days": 5},
        ]
        svc.get_client_growth.return_value = []
        svc.get_revenue_concentration.return_value = []

        tab = ClientAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should still render with client_analytics data
        assert tab._chart_layout.count() >= 1

    def test_revenue_concentration_few_clients(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_revenue_by_client.return_value = [
            {"client": "ACME", "revenue": 5000, "profit": 1000},
        ]
        svc.get_client_analytics.return_value = [
            {"client": "ACME", "trip_count": 10, "revenue": 5000,
             "profit": 1000, "avg_payment_delay_days": 5},
        ]
        svc.get_client_growth.return_value = []
        svc.get_revenue_concentration.return_value = [
            {"client": "ACME", "revenue": 5000, "profit": 1000},
        ]

        tab = ClientAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Pie chart requires >3 entries → skipped
        assert tab._chart_layout.count() >= 1

    def test_no_growth_data(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_revenue_by_client.return_value = [
            {"client": "ACME", "revenue": 5000, "profit": 1000},
        ]
        svc.get_client_analytics.return_value = []
        svc.get_client_growth.return_value = None
        svc.get_revenue_concentration.return_value = []

        tab = ClientAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should not crash with None growth data
        assert tab._chart_layout.count() >= 1
