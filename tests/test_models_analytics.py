"""Tests for analytics_models.py — Analytics query params, aggregate types, time period bounds."""
import pytest
from datetime import date
from pydantic import ValidationError
from models.analytics_models import (
    AnalyticsRequest,
    RevenueReport,
    OverdueReport,
    KpiDashboard,
)


class TestAnalyticsRequest:
    @pytest.mark.parametrize(
        "start_date, end_date, group_by",
        [
            (date(2026, 1, 1), date(2026, 12, 31), "month"),
            (date(2026, 3, 1), date(2026, 3, 31), "day"),
            (date(2026, 6, 1), date(2026, 8, 31), "week"),
            (date(2025, 1, 1), date(2026, 12, 31), "quarter"),
            (None, None, "year"),
        ],
    )
    def test_analytics_request_valid(self, start_date, end_date, group_by):
        r = AnalyticsRequest(start_date=start_date, end_date=end_date, group_by=group_by)
        assert r.start_date == start_date
        assert r.end_date == end_date
        assert r.group_by == group_by

    def test_analytics_request_defaults(self):
        r = AnalyticsRequest()
        assert r.start_date is None
        assert r.end_date is None
        assert r.client_id is None
        assert r.vehicle_id is None
        assert r.driver_id is None
        assert r.group_by == "month"

    def test_analytics_request_filters(self):
        r = AnalyticsRequest(
            client_id=10,
            vehicle_id=5,
            driver_id=100,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
        )
        assert r.client_id == 10
        assert r.vehicle_id == 5
        assert r.driver_id == 100

    @pytest.mark.parametrize("group_by", ["day", "week", "month", "quarter", "year"])
    def test_analytics_group_by_values(self, group_by):
        r = AnalyticsRequest(group_by=group_by)
        assert r.group_by == group_by


class TestRevenueReport:
    def test_revenue_report_full(self):
        r = RevenueReport(
            total_revenue=100000.0,
            total_cost=75000.0,
            total_profit=25000.0,
            margin_pct=25.0,
            trip_count=50,
            invoice_count=45,
            average_trip_revenue=2000.0,
        )
        assert r.total_revenue == 100000.0
        assert r.margin_pct == 25.0
        assert r.currency == "EUR"

    def test_revenue_report_default_currency(self):
        r = RevenueReport(
            total_revenue=0,
            total_cost=0,
            total_profit=0,
            margin_pct=0,
            trip_count=0,
            invoice_count=0,
            average_trip_revenue=0,
        )
        assert r.currency == "EUR"

    def test_revenue_report_zero_values(self):
        r = RevenueReport(
            total_revenue=0.0,
            total_cost=0.0,
            total_profit=0.0,
            margin_pct=0.0,
            trip_count=0,
            invoice_count=0,
            average_trip_revenue=0.0,
        )
        assert r.trip_count == 0


class TestOverdueReport:
    def test_overdue_report(self):
        r = OverdueReport(total_overdue=5000.0, overdue_count=3, average_days_late=15.5)
        assert r.total_overdue == 5000.0
        assert r.items == []

    def test_overdue_report_with_items(self):
        items = [
            {"invoice_number": "INV-001", "client_name": "A", "amount": 1000.0, "days_late": 10, "alert_level": "warning"},
            {"invoice_number": "INV-002", "client_name": "B", "amount": 2000.0, "days_late": 30, "alert_level": "critical"},
        ]
        r = OverdueReport(
            total_overdue=3000.0,
            overdue_count=2,
            average_days_late=20.0,
            items=items,
        )
        assert len(r.items) == 2
        assert r.items[0]["invoice_number"] == "INV-001"


class TestKpiDashboard:
    def test_kpi_dashboard(self):
        revenue = RevenueReport(
            total_revenue=50000, total_cost=35000, total_profit=15000,
            margin_pct=30.0, trip_count=25, invoice_count=20, average_trip_revenue=2000,
        )
        overdue = OverdueReport(total_overdue=2000, overdue_count=2, average_days_late=12)
        period = (date(2026, 1, 1), date(2026, 3, 31))
        kpi = KpiDashboard(
            revenue=revenue,
            overdue=overdue,
            active_trips=10,
            active_vehicles=8,
            total_distance_km=5000.0,
            total_fuel_liters=1500.0,
            period=period,
            generated_at=date.today(),
        )
        assert kpi.revenue.total_revenue == 50000
        assert kpi.overdue.overdue_count == 2
        assert kpi.active_trips == 10
        assert kpi.total_distance_km == 5000.0
        assert kpi.period == period
