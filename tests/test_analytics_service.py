"""Tests for services.analytics_service — caching layer over the repository."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from services.analytics_service import AnalyticsService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    svc = AnalyticsService.__new__(AnalyticsService)
    svc.db = MagicMock()
    svc._repo = mock_repo
    svc._caches = {}
    svc._cache_lock = MagicMock()
    svc._key_locks = {}
    svc._key_locks_lock = MagicMock()
    return svc


class TestDelegation:
    """Service methods delegate to the repository."""

    def test_get_financial_delegates(self, service, mock_repo):
        mock_repo.get_financial_analytics.return_value = {"rev": 100}
        result = service.get_financial(from_date="2026-01-01", to_date="2026-01-31")
        mock_repo.get_financial_analytics.assert_called_once_with(
            "2026-01-01", "2026-01-31"
        )
        assert result == {"rev": 100}

    def test_get_fleet_delegates(self, service, mock_repo):
        service.get_fleet("2026-01-01", "2026-01-31")
        mock_repo.get_fleet_analytics.assert_called_once()

    def test_get_driver_delegates(self, service, mock_repo):
        service.get_driver("2026-01-01", "2026-01-31")
        mock_repo.get_driver_analytics.assert_called_once()

    def test_get_document_delegates(self, service, mock_repo):
        service.get_document()
        mock_repo.get_document_analytics.assert_called_once()

    def test_get_client_analytics_delegates(self, service, mock_repo):
        service.get_client_analytics("2026-01-01", "2026-01-31")
        mock_repo.get_client_analytics.assert_called_once()

    def test_get_revenue_by_client_delegates(self, service, mock_repo):
        service.get_revenue_by_client()
        mock_repo.get_revenue_by_client.assert_called_once()

    def test_get_maintenance_alerts_delegates(self, service, mock_repo):
        service.get_maintenance_alerts()
        mock_repo.get_maintenance_alerts.assert_called_once()

    def test_get_client_growth_delegates(self, service, mock_repo):
        service.get_client_growth(months=6)
        mock_repo.get_client_growth.assert_called_once_with(6, None, None)


class TestCache:
    """Service caches results and returns cached data within TTL."""

    @pytest.fixture(autouse=True)
    def _real_cache(self, service):
        service._cache_lock = __import__("threading").Lock()
        service._caches = {}

    def test_cache_hit_returns_cached_data(self, service, mock_repo):
        mock_repo.get_financial_analytics.return_value = {"rev": 100}

        first = service.get_financial()
        second = service.get_financial()

        assert first == second == {"rev": 100}
        mock_repo.get_financial_analytics.assert_called_once()

    def test_cache_miss_on_different_args(self, service, mock_repo):
        mock_repo.get_financial_analytics.return_value = {"rev": 100}

        service.get_financial("2026-01-01", "2026-01-31")
        service.get_financial("2026-02-01", "2026-02-28")

        assert mock_repo.get_financial_analytics.call_count == 2

    def test_invalidate_clears_cache(self, service, mock_repo):
        mock_repo.get_financial_analytics.return_value = {"rev": 100}

        service.get_financial()
        service.invalidate()
        service.get_financial()

        assert mock_repo.get_financial_analytics.call_count == 2

    def test_cache_ttl_expiry(self, service, mock_repo):
        mock_repo.get_financial_analytics.return_value = {"rev": 100}

        service.get_financial()

        key = ("financial", (None, None))
        service._caches[key] = (
            service._caches[key][0],
            time.time() - 600,  # expired
            service._caches[key][2],
        )

        service.get_financial()
        assert mock_repo.get_financial_analytics.call_count == 2


class TestCacheKeyedByArgs:
    def test_same_args_hit_cache(self, service, mock_repo):
        mock_repo.get_revenue_by_client.return_value = {"Client A": 5000}

        service.get_revenue_by_client("2026-01-01", "2026-01-31")
        service.get_revenue_by_client("2026-01-01", "2026-01-31")

        mock_repo.get_revenue_by_client.assert_called_once()

    def test_different_args_miss(self, service, mock_repo):
        mock_repo.get_revenue_by_client.return_value = {"Client A": 5000}

        service.get_revenue_by_client("2026-01-01", "2026-01-31")
        service.get_revenue_by_client("2026-02-01", "2026-02-28")

        assert mock_repo.get_revenue_by_client.call_count == 2
