"""Unit tests for ExchangeRateService — mocked HTTP and cache I/O.

These tests verify singleton behaviour, rate lookup, currency conversion,
availability reporting, and age tracking.  No real HTTP requests or
filesystem access occurs.
"""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from services.exchange_rate_service import ExchangeRateService, _DEFAULT_RATES

pytestmark = pytest.mark.slow


class TestExchangeRateService:
    """Unit tests for ExchangeRateService."""

    # ── Fixtures ──────────────────────────────────────────────────────

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Reset singleton and prevent file I/O for every test."""
        ExchangeRateService._instance = None
        with patch.multiple(
            ExchangeRateService,
            _load_cache=MagicMock(),
            _save_cache=MagicMock(),
        ):
            self.svc = ExchangeRateService()
            yield

    # ── Singleton ─────────────────────────────────────────────────────

    def test_singleton_returns_same_instance(self):
        svc2 = ExchangeRateService()
        assert self.svc is svc2

    # ── get_rate ──────────────────────────────────────────────────────

    def test_get_rate_eur_returns_one(self):
        assert self.svc.get_rate("EUR") == 1.0

    def test_get_rate_returns_default(self):
        expected = _DEFAULT_RATES["RON"]
        assert self.svc.get_rate("RON") == expected

    def test_get_rate_unknown_returns_one(self):
        assert self.svc.get_rate("XYZ") == 1.0

    # ── convert ───────────────────────────────────────────────────────

    def test_convert_same_currency(self):
        assert self.svc.convert(100, "EUR", "EUR") == 100

    def test_convert_eur_to_ron(self):
        expected = 100 * _DEFAULT_RATES["RON"]
        result = self.svc.convert(100, "EUR", "RON")
        assert abs(result - expected) < 0.01

    def test_convert_usd_to_eur(self):
        expected = 100 / _DEFAULT_RATES["USD"]
        result = self.svc.convert(100, "USD", "EUR")
        assert abs(result - expected) < 0.01

    def test_convert_zero_rate_returns_amount(self):
        self.svc._rates["XYZ"] = 0.0
        assert self.svc.convert(100, "XYZ", "EUR") == 100

    # ── get_all_rates ─────────────────────────────────────────────────

    def test_get_all_rates_returns_dict_copy(self):
        result = self.svc.get_all_rates()
        assert result == _DEFAULT_RATES
        # Mutating the returned dict must not affect internal state
        result["MUTATED"] = 999.0
        assert "MUTATED" not in self.svc._rates

    # ── is_available ──────────────────────────────────────────────────

    def test_is_available_when_never_fetched(self):
        assert self.svc.is_available() is False

    def test_is_available_with_recent_data(self):
        self.svc._last_fetch_ok = True
        self.svc._last_updated = time.time()
        assert self.svc.is_available() is True

    # ── last_updated_str ──────────────────────────────────────────────

    def test_last_updated_str_never(self):
        assert self.svc.last_updated_str() == "never"

    # ── age_seconds ───────────────────────────────────────────────────

    def test_age_seconds_positive_after_update(self):
        self.svc._last_updated = time.time() - 10
        age = self.svc.age_seconds()
        assert age is not None
        assert age >= 9.0
