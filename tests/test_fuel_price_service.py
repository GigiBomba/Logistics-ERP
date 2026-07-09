"""Unit tests for FuelPriceService — mocked HTTP, cache, and fallback I/O.

These tests verify singleton behaviour, price lookup / conversion, availability
reporting, refresh logic, and debounce semantics.  No real HTTP requests or
filesystem access occurs.
"""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from services.fuel_price_service import FuelPriceService

pytestmark = pytest.mark.slow


class TestFuelPriceService:
    """Unit tests for FuelPriceService."""

    # ── Fixtures ──────────────────────────────────────────────────────

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Reset singleton and prevent file I/O for every test."""
        FuelPriceService._instance = None
        with patch.multiple(
            FuelPriceService,
            _load_fallback=MagicMock(),
            _load_cache=MagicMock(),
            _save_cache=MagicMock(),
        ):
            self.svc = FuelPriceService()
            yield

    # ── Singleton ─────────────────────────────────────────────────────

    def test_singleton_returns_same_instance(self):
        svc2 = FuelPriceService()
        assert self.svc is svc2

    # ── get_price ─────────────────────────────────────────────────────

    def test_get_price_returns_eur_by_default(self):
        self.svc._prices = {"RO": 1.55}
        assert self.svc.get_price("RO") == 1.55

    def test_get_price_unknown_country_falls_back_to_default(self):
        self.svc._prices = {"DEFAULT": 1.60}
        assert self.svc.get_price("XX") == 1.60

    def test_get_price_with_currency_converts(self):
        self.svc._prices = {"RO": 1.50}
        with patch("services.exchange_rate_service.ExchangeRateService") as mock_fx_cls:
            mock_fx = MagicMock()
            mock_fx_cls.return_value = mock_fx
            mock_fx.convert.return_value = 7.50
            result = self.svc.get_price("RO", "RON")
            assert result == 7.50
            mock_fx.convert.assert_called_once_with(1.50, "EUR", "RON")

    # ── get_prices_all ───────────────────────────────────────────────

    def test_get_prices_all_returns_dict(self):
        self.svc._prices = {"RO": 1.55, "DE": 1.65}
        result = self.svc.get_prices_all()
        assert result == {"RO": 1.55, "DE": 1.65}

    # ── get_price_for_country (alias) ─────────────────────────────────

    def test_get_price_for_country_alias(self):
        self.svc._prices = {"RO": 1.55}
        assert self.svc.get_price_for_country("RO") == 1.55

    # ── is_available ──────────────────────────────────────────────────

    def test_is_available_initial_state(self):
        assert self.svc.is_available() is False

    def test_is_available_after_successful_fetch(self):
        self.svc._last_fetch_ok = True
        assert self.svc.is_available() is True

    def test_is_available_after_failed_fetch(self):
        self.svc._last_fetch_ok = False
        self.svc._prices = {}
        assert self.svc.is_available() is False

    # ── last_updated_str ──────────────────────────────────────────────

    def test_last_updated_str_returns_never(self):
        assert self.svc.last_updated_str() == "never"

    def test_last_updated_str_returns_formatted(self):
        ts = datetime(2026, 7, 9, 10, 30, 0).timestamp()
        self.svc._last_updated = ts
        assert self.svc.last_updated_str() == "09/07/2026 10:30"

    # ── age_seconds ───────────────────────────────────────────────────

    def test_age_seconds_returns_none_initially(self):
        assert self.svc.age_seconds() is None

    def test_age_seconds_returns_positive_after_update(self):
        self.svc._last_updated = time.time() - 10
        age = self.svc.age_seconds()
        assert age is not None
        assert age >= 9.0

    # ── refresh (background / foreground / debounce) ──────────────────

    def test_refresh_background_spawns_thread(self):
        with patch.object(self.svc, "_spawn") as mock_spawn:
            result = self.svc.refresh(background=True)
            assert result is True
            mock_spawn.assert_called_once_with(
                "fuel-price-refresh", self.svc._do_refresh_all
            )

    def test_refresh_foreground_runs_sync(self):
        with patch.object(self.svc, "_do_refresh_all", return_value=True) as mock_do:
            result = self.svc.refresh(background=False)
            assert result is True
            mock_do.assert_called_once()

    def test_refresh_debounce_skips_when_in_progress(self):
        self.svc._refresh_in_progress = True
        with patch.object(self.svc, "_do_refresh_all") as mock_do:
            with patch.object(self.svc, "_spawn") as mock_spawn:
                result = self.svc.refresh()
                assert result is True
                mock_do.assert_not_called()
                mock_spawn.assert_not_called()

    # ── refresh_if_stale ──────────────────────────────────────────────

    def test_refresh_if_stale_when_stale(self):
        self.svc._last_updated = time.time() - 200000  # well past 86400 TTL
        with patch.object(self.svc, "refresh", return_value=True) as mock_refresh:
            result = self.svc.refresh_if_stale()
            assert result is True
            mock_refresh.assert_called_once()

    def test_refresh_if_stale_when_fresh(self):
        self.svc._last_updated = time.time() - 10  # well within TTL
        with patch.object(self.svc, "refresh") as mock_refresh:
            result = self.svc.refresh_if_stale()
            assert result is True
            mock_refresh.assert_not_called()
