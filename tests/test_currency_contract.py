"""Comprehensive unit tests for services/currency/contract.py.

Tests cover get_non_deterministic_operations and is_deterministic —
validating the operation registry and deterministic checks.
"""

from __future__ import annotations

import pytest

from services.currency.contract import (
    NonDeterminismWarning,
    get_non_deterministic_operations,
    is_deterministic,
)


# ──────────────────────────────────────────────────────────────
# get_non_deterministic_operations
# ──────────────────────────────────────────────────────────────


class TestGetNonDeterministicOperations:
    """Registry of all non-deterministic operations."""

    def test_returns_dict(self):
        ops = get_non_deterministic_operations()
        assert isinstance(ops, dict)

    def test_has_expected_keys(self):
        ops = get_non_deterministic_operations()
        expected_keys = {
            "currency.convert",
            "currency.refresh_rates",
            "exchange_rate.refresh",
            "fuel_price.refresh",
        }
        assert set(ops.keys()) == expected_keys

    def test_each_entry_is_non_determinism_warning(self):
        ops = get_non_deterministic_operations()
        for entry in ops.values():
            assert isinstance(entry, NonDeterminismWarning)

    def test_currency_convert_has_expected_fields(self):
        ops = get_non_deterministic_operations()
        entry = ops["currency.convert"]
        assert entry.method == "CurrencyService.convert"
        assert "exchange rate" in entry.reason.lower()
        assert entry.cache_ttl_seconds == 3600

    def test_currency_refresh_rates_has_expected_fields(self):
        ops = get_non_deterministic_operations()
        entry = ops["currency.refresh_rates"]
        assert entry.method == "CurrencyService.refresh_rates"
        assert entry.cache_ttl_seconds == 3600

    def test_exchange_rate_refresh_has_expected_fields(self):
        ops = get_non_deterministic_operations()
        entry = ops["exchange_rate.refresh"]
        assert entry.method == "ExchangeRateService.refresh"
        assert entry.cache_ttl_seconds == 3600

    def test_fuel_price_refresh_has_expected_fields(self):
        ops = get_non_deterministic_operations()
        entry = ops["fuel_price.refresh"]
        assert entry.method == "FuelPriceService.refresh"
        assert entry.cache_ttl_seconds == 86400

    def test_last_updated_defaults_to_none(self):
        ops = get_non_deterministic_operations()
        for entry in ops.values():
            assert entry.last_updated is None

    def test_external_dependency_is_not_empty(self):
        ops = get_non_deterministic_operations()
        for entry in ops.values():
            assert entry.external_dependency, "external_dependency should not be empty"


# ──────────────────────────────────────────────────────────────
# is_deterministic
# ──────────────────────────────────────────────────────────────


class TestIsDeterministic:
    """Check if a method name is deterministic."""

    def test_known_non_deterministic_returns_false(self):
        assert is_deterministic("currency.convert") is False
        assert is_deterministic("currency.refresh_rates") is False
        assert is_deterministic("exchange_rate.refresh") is False
        assert is_deterministic("fuel_price.refresh") is False

    def test_unknown_method_returns_true(self):
        assert is_deterministic("unknown.method") is True

    def test_random_method_name_returns_true(self):
        assert is_deterministic("some.service.do_stuff") is True

    def test_empty_string_returns_true(self):
        assert is_deterministic("") is True

    def test_partial_match_returns_true(self):
        # Only exact keys match; "currency" alone is not in the registry
        assert is_deterministic("currency") is True

    def test_case_sensitive(self):
        # Registry keys are lower-case; upper-case should not match
        assert is_deterministic("CURRENCY.CONVERT") is True
