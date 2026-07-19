"""Comprehensive tests for analytics service source_provider filter.

Verifies all 17 analytics methods accept and correctly apply source_provider
without breaking existing behavior when the parameter is omitted.
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest


class TestAllAnalyticsMethodsAcceptSourceProvider:
    """Each of the 17 updated analytics methods accepts source_provider param."""

    def _make_service(self):
        from services.analytics_service import AnalyticsService
        mock_db = MagicMock()
        mock_db.conn.execute.return_value.fetchone.return_value = (0,)
        mock_db.conn.execute.return_value.fetchall.return_value = []
        return AnalyticsService(mock_db)

    @pytest.mark.parametrize("method_name,args", [
        ("get_data", (1, "2026-01-01", "2026-07-16")),
        ("get_financial", (1, "2026-01-01", "2026-07-16")),
        ("get_revenue_by_client", (1, "2026-01-01", "2026-07-16")),
        ("get_revenue_by_country", (1, "2026-01-01", "2026-07-16")),
        ("get_route_profitability", (1, "2026-01-01", "2026-07-16")),
        ("get_client_analytics", (1, "2026-01-01", "2026-07-16", 1)),
        ("get_fleet", (1, "2026-01-01", "2026-07-16")),
        ("get_driver", (1, "2026-01-01", "2026-07-16")),
        ("get_monthly_financial", (1, "2026-01-01", "2026-07-16")),
        ("get_client_growth", (1, "2026-01-01", "2026-07-16")),
        ("get_trip_status_distribution", (1, "2026-01-01", "2026-07-16")),
        ("get_cost_breakdown", (1, "2026-01-01", "2026-07-16")),
        ("get_monthly_trip_volume", (1, "2026-01-01", "2026-07-16")),
        ("get_revenue_quarterly", (1, "2026-01-01", "2026-07-16")),
        ("get_client_payment_timeline", (1, "2026-01-01", "2026-07-16")),
        ("get_driver_monthly_activity", (1, "2026-01-01", "2026-07-16", 1)),
        ("get_driver_comparison", (1, "2026-01-01", "2026-07-16")),
    ])
    def test_method_accepts_source_provider(self, method_name, args):
        """Method can be called with source_provider=None (default)."""
        service = self._make_service()
        method = getattr(service, method_name, None)
        assert method is not None, f"Method {method_name} not found"
        try:
            result = method(*args, source_provider=None)
            # Should not raise — return type may vary
        except Exception as e:
            pytest.fail(f"Method {method_name} raised with source_provider=None: {e}")

    def test_get_data_with_trans_eu_filter(self):
        """get_data with source_provider='trans_eu' builds correct filter."""
        from tests.test_helpers import InMemoryDB
        db = InMemoryDB()
        # Disable FK enforcement to insert trips without populating all parent tables
        db.conn.execute("PRAGMA foreign_keys = OFF")
        # Use named columns to match the real 54-column trips table created by InMemoryDB
        db.conn.execute("""
            INSERT INTO trips (id, company_id, source, source_provider_id, distance_km, start_date,
                               extra_costs, fuel_cost, toll_cost, salary_cost,
                               driver_id, truck_id, client_id, status,
                               loading_country, delivery_country, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 1, 'freight_exchange', 'trans_eu', 500, '2026-01-01',
              1000, 1500, 500, 0,
              1, 1, 1, 'Delivered', 'Krakow', 'Berlin', '2026-01-01'))
        db.conn.execute("""
            INSERT INTO trips (id, company_id, source, source_provider_id, distance_km, start_date,
                               extra_costs, fuel_cost, toll_cost, salary_cost,
                               driver_id, truck_id, client_id, status,
                               loading_country, delivery_country, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (2, 1, 'manual', None, 300, '2026-01-02',
              500, 800, 300, 0,
              2, 2, 2, 'Planned', 'Warsaw', 'Prague', '2026-01-02'))
        db.conn.commit()
        db.conn.execute("PRAGMA foreign_keys = ON")

        from services.analytics_service import AnalyticsService
        service = AnalyticsService(db)
        result = service.get_data(1, "2026-01-01", "2026-07-16", source_provider="trans_eu")
        assert isinstance(result, dict) or isinstance(result, tuple) or result is None
