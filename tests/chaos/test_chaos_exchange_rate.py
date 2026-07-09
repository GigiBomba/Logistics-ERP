"""Chaos tests: Exchange-rate API failures.

The ``ExchangeRateService`` (singleton) fetches rates from a primary
and a fallback API URL.  If both fail it keeps the last-known-good
rates from its cache file, or falls back to ``_DEFAULT_RATES``.

These tests patch ``requests.get`` (which ``_do_refresh`` calls) to
simulate API-level failures and verify graceful degradation.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.exchange_rate_service import (
    ExchangeRateService,
    _DEFAULT_RATES,
)

pytestmark = pytest.mark.chaos


class TestChaosExchangeRate:
    """Simulate exchange-rate API failures — the service should fall
    back to cached or default rates."""

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _reset_singleton():
        """Force re-initialisation of the singleton for test isolation."""
        ExchangeRateService._instance = None

    def setup_method(self):
        self._reset_singleton()

    # ── Tests ────────────────────────────────────────────────────────

    def test_exchange_rate_api_connection_refused(self, client, auth_admin):
        """When the primary API is unreachable, the service uses fallback
        or default rates — no crash."""
        with patch.object(ExchangeRateService, "_load_cache", return_value=None):
            with patch("services.exchange_rate_service.requests.get") as mock_get:
                mock_get.side_effect = ConnectionError("Connection refused")
                # Instantiate the singleton — it will try to refresh
                svc = ExchangeRateService()
                ok = svc._do_refresh()
                assert ok is False, "Refresh should fail when API is down"
                # Default rates should still be available
                rate = svc.get_rate("RON")
                assert rate == _DEFAULT_RATES["RON"], (
                    f"Expected default rate 4.97, got {rate}"
                )

    def test_exchange_rate_timeout(self, client, auth_admin):
        """When the API times out, the service falls back to defaults."""
        with patch.object(ExchangeRateService, "_load_cache", return_value=None):
            with patch("services.exchange_rate_service.requests.get") as mock_get:
                mock_get.side_effect = requests.exceptions.Timeout(
                    "Connection timed out",
                )
                svc = ExchangeRateService()
                ok = svc._do_refresh()
                assert ok is False
                rate = svc.get_rate("USD")
                assert rate == _DEFAULT_RATES["USD"], (
                    f"Expected default rate 1.08, got {rate}"
                )

    def test_exchange_rate_malformed_response(self, client, auth_admin):
        """When the API returns non-JSON, the service keeps prior rates."""
        with patch.object(ExchangeRateService, "_load_cache", return_value=None):
            with patch("services.exchange_rate_service.requests.get") as mock_get:
                mock_resp = MagicMock(spec=requests.Response)
                mock_resp.status_code = 200
                mock_resp.json.side_effect = json.JSONDecodeError(
                    "Expecting value", "", 0,
                )
                mock_get.return_value = mock_resp
                svc = ExchangeRateService()
                ok = svc._do_refresh()
                assert ok is False
                # Default rates preserved
                rate = svc.get_rate("GBP")
                assert rate == _DEFAULT_RATES["GBP"], (
                    f"Expected default rate 0.86, got {rate}"
                )

    def test_exchange_rate_all_sources_fail(self, client, auth_admin):
        """When both primary and fallback APIs fail, ``_DEFAULT_RATES``
        are used and the service remains functional."""
        with patch.object(ExchangeRateService, "_load_cache", return_value=None):
            with patch("services.exchange_rate_service.requests.get") as mock_get:
                mock_get.side_effect = ConnectionError("All APIs unreachable")
                svc = ExchangeRateService()
                ok = svc._do_refresh()
                assert ok is False, "Refresh must fail when all sources are down"

                # All default rates should be accessible
                for code, expected in _DEFAULT_RATES.items():
                    assert svc.get_rate(code) == expected, (
                        f"Rate for {code}: expected {expected}, got {svc.get_rate(code)}"
                    )

                # Conversion should still work with defaults
                converted = svc.convert(100, "EUR", "USD")
                assert abs(converted - 108.0) < 0.01, (
                    f"Expected ~108 USD for 100 EUR, got {converted}"
                )
