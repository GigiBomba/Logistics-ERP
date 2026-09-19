"""Headless smoke tests for analytics tabs (P2-AN lane).

Constructs real tabs offscreen with a mocked service, forces a render,
grabs a pixmap (the ``widget.grab()`` pattern from ``tests/test_conftest.py``)
and scans the widget tree for the BUG-08 "LOADING" placeholder regression.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel

from ui.views.analytics.financial_tab import FinancialAnalyticsTab
from ui.views.analytics.route_tab import RouteAnalyticsTab


def _financial_svc():
    svc = MagicMock()
    svc.get_monthly_financial.return_value = [
        {"month": "2026-01", "revenue": 50000, "profit": 12000, "margin_pct": 24.0,
         "trip_count": 45, "invoiced_count": 40, "paid_count": 30},
        {"month": "2026-02", "revenue": 62000, "profit": 15000, "margin_pct": 24.2,
         "trip_count": 52, "invoiced_count": 48, "paid_count": 35},
    ]
    svc.get_revenue_by_client.return_value = [
        {"client": "ACME Corp", "revenue": 30000, "profit": 8000},
    ]
    svc.get_revenue_by_country.return_value = [
        {"country": "DE", "revenue": 45000},
    ]
    svc.get_trip_status_distribution.return_value = [
        {"status": "delivered", "count": 30},
        {"status": "in_transit", "count": 10},
    ]
    svc.get_revenue_quarterly.return_value = []
    svc.get_monthly_trip_volume.return_value = []
    svc.get_cost_breakdown.return_value = []
    svc.get_invoice_aging.return_value = None
    return svc


def _route_svc():
    svc = MagicMock()
    svc.get_route_profitability.return_value = [
        {"route_label": "Paris \u2192 Berlin", "trip_count": 25, "avg_km": 1050,
         "avg_profit": 450, "profit_per_km": 0.43},
        {"route_label": "London \u2192 Amsterdam", "trip_count": 20, "avg_km": 850,
         "avg_profit": 720, "profit_per_km": 0.85},
    ]
    svc.get_profit_per_km_by_country.return_value = [
        {"country": "DE", "profit": 25000, "profit_per_km": 0.65},
        {"country": "FR", "profit": 18000, "profit_per_km": 0.55},
    ]
    return svc


def _assert_clean_smoke(qtbot, tab):
    """Resize, wait, grab a non-null pixmap, and reject 'LOADING' text."""
    tab.resize(900, 700)
    tab.show()
    tab.refresh(force=True)
    QTest.qWait(150)

    pixmap = tab.grab()
    assert pixmap is not None and not pixmap.isNull()

    # BUG-08 regression: the "LOADING" placeholder status must never
    # surface as text in the rendered widget tree.
    loading_labels = [
        lbl.text() for lbl in tab.findChildren(QLabel)
        if "LOADING" in lbl.text().upper()
    ]
    assert loading_labels == []


class TestAnalyticsTabSmoke:
    def test_financial_tab_smoke(self, qt_widget, qtbot):
        tab = FinancialAnalyticsTab(parent=qt_widget, service=_financial_svc())
        qtbot.addWidget(tab)
        _assert_clean_smoke(qtbot, tab)

    def test_route_tab_smoke(self, qt_widget, qtbot):
        tab = RouteAnalyticsTab(parent=qt_widget, service=_route_svc())
        qtbot.addWidget(tab)
        _assert_clean_smoke(qtbot, tab)


class TestOverviewLoadingRegression:
    """BUG-08: the 'LOADING' placeholder must not render as a trip row nor be counted."""

    def test_loading_placeholder_excluded_from_rows_and_count(self, qtbot):
        from unittest.mock import patch

        from PySide6.QtWidgets import QLabel

        from ui.views.overview_view import QtOverviewView

        trip_service = MagicMock()
        trip_service.get_all.return_value = [
            {"id": 1, "status": "LOADING", "truck_number": "TR-01",
             "client_name": "Client A"},
            {"id": 2, "status": "In Progress", "truck_number": "TR-02",
             "client_name": "Client B"},
            {"id": 3, "status": "Delivered", "truck_number": "TR-03",
             "client_name": "Client C"},
        ]

        with patch("ui.views.overview_view.load_company_config",
                   return_value={"company_name": "TestCo"}):
            widget = QtOverviewView(
                parent=None,
                db=MagicMock(),
                ops=MagicMock(),
                trip_service=trip_service,
                fleet_service=MagicMock(),
                analytics_svc=MagicMock(),
            )
        qtbot.addWidget(widget)
        try:
            widget._refresh_active_trips()
            # The LOADING placeholder must not be counted.
            assert widget._trips_count.text() == "1"
            # And must not render as a trip row.
            labels = [lbl.text().upper() for lbl in widget.findChildren(QLabel)]
            assert not any("LOADING" in txt for txt in labels)
        finally:
            with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
                widget.shutdown()