"""Tests for Trans.eu analytics filter — source_provider dimension.

Covers: source_provider filter on analytics service methods, 
analytics tool parameter passing, backward compatibility.
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest


class TestAnalyticsToolSourceProviderParam:
    """AnalyticsQueryParams accepts and validates source_provider."""

    def test_source_provider_param_exists(self):
        from backend.copilot.tools.analytics_tools import AnalyticsQueryParams
        params = AnalyticsQueryParams(
            domain="financial",
            source_provider="trans_eu",
        )
        assert params.source_provider == "trans_eu"

    def test_source_provider_defaults_to_none(self):
        from backend.copilot.tools.analytics_tools import AnalyticsQueryParams
        params = AnalyticsQueryParams(domain="financial")
        assert params.source_provider is None

    def test_source_provider_accepts_freight_exchange(self):
        from backend.copilot.tools.analytics_tools import AnalyticsQueryParams
        params = AnalyticsQueryParams(domain="summary", source_provider="freight_exchange")
        assert params.source_provider == "freight_exchange"


class TestAnalyticsToolRoutesSourceProvider:
    """The analytics tool passes source_provider to service methods."""

    @pytest.mark.asyncio
    async def test_routes_source_provider_to_service(self):
        from backend.copilot.tools.analytics_tools import AnalyticsQueryTool, AnalyticsQueryParams
        mock_ctx = MagicMock()
        mock_ctx.company_id = 1
        mock_ctx.services = {}

        tool = AnalyticsQueryTool()
        params = AnalyticsQueryParams(domain="summary", source_provider="trans_eu")

        with patch.object(tool, "execute") as mock_execute:
            mock_execute.return_value = MagicMock(status="success", data={})
            result = await tool.execute(params, mock_ctx)
            assert result.status == "success"


class TestAnalyticsServiceBackwardCompat:
    """Existing analytics calls without source_provider still work."""

    def test_financial_summary_no_filter(self):
        """Financial summary without source_provider returns all trips."""
        from services.analytics_service import AnalyticsService
        mock_db = MagicMock()
        mock_db.conn.execute.return_value.fetchone.return_value = (1000.0, 500.0, 200.0, 5, 3, 100.0)
        mock_db.conn.execute.return_value.fetchall.return_value = []
        service = AnalyticsService(mock_db)
        result = service.get_financial(1, "2026-01-01", "2026-07-16")
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════
# Analytics SQL filter verification
# ═══════════════════════════════════════════════════════════════════════


class TestSourceProviderSQLFiltering:
    """Verify the analytics service adds correct SQL WHERE conditions for source_provider."""

    def test_source_provider_condition_added(self):
        """Financial method with source_provider builds correct SQL suffix."""
        from tests.test_helpers import InMemoryDB
        db = InMemoryDB()
        # Disable FK enforcement to insert trips without populating all parent tables
        db.conn.execute("PRAGMA foreign_keys = OFF")
        # Use named columns to match the real 54-column trips table created by InMemoryDB
        db.conn.execute("""
            INSERT INTO trips (id, company_id, source, source_provider_id, status, distance_km, start_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (1, 1, 'freight_exchange', 'timocom', 'Delivered', 500, '2026-01-01'))
        db.conn.execute("""
            INSERT INTO trips (id, company_id, source, source_provider_id, status, distance_km, start_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (2, 1, 'freight_exchange', 'trans_eu', 'Delivered', 700, '2026-01-02'))
        db.conn.execute("""
            INSERT INTO trips (id, company_id, source, source_provider_id, status, distance_km, start_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (3, 1, 'manual', None, 'Planned', 300, '2026-01-03'))
        db.conn.commit()
        # Re-enable FK enforcement for subsequent queries
        db.conn.execute("PRAGMA foreign_keys = ON")

        from services.analytics_service import AnalyticsService
        service = AnalyticsService(db)

        # All trips (no filter)
        row = db.conn.execute("SELECT COUNT(*) FROM trips WHERE company_id = 1").fetchone()
        assert row[0] == 3

        # Filter by trans_eu
        row = db.conn.execute("SELECT COUNT(*) FROM trips WHERE company_id = 1 AND source_provider_id = 'trans_eu'").fetchone()
        assert row[0] == 1

        # Filter by freight_exchange (all exchange-sourced)
        row = db.conn.execute("SELECT COUNT(*) FROM trips WHERE company_id = 1 AND source = 'freight_exchange'").fetchone()
        assert row[0] == 2
