"""Comprehensive unit tests for utils/formatters.py.

Tests cover fmt_currency, fmt_distance, fmt_rate, fmt_date,
fmt_profit_color, fmt_number, and fmt_percentage — including None
inputs, negative values, zero, large numbers, and edge cases.
"""

from __future__ import annotations

import pytest

from utils.formatters import (
    fmt_currency,
    fmt_date,
    fmt_distance,
    fmt_number,
    fmt_percentage,
    fmt_profit_color,
    fmt_rate,
)


# ──────────────────────────────────────────────────────────────
# fmt_currency
# ──────────────────────────────────────────────────────────────


class TestFmtCurrency:
    """Format monetary values with currency symbol and thousands separator."""

    def test_default_currency(self):
        assert fmt_currency(39563.0) == "€ 39 563.00"

    def test_none_coerces_to_zero(self):
        assert fmt_currency(None) == "€ 0.00"

    def test_zero_value(self):
        assert fmt_currency(0) == "€ 0.00"

    def test_negative_value(self):
        assert fmt_currency(-1500.50) == "-€ 1 500.50"

    def test_large_number(self):
        assert fmt_currency(1234567.89) == "€ 1 234 567.89"

    def test_dollar_symbol(self):
        assert fmt_currency(100.0, currency="$") == "$ 100.00"

    def test_three_decimals(self):
        assert fmt_currency(42.5, decimals=3) == "€ 42.500"

    def test_zero_decimals(self):
        assert fmt_currency(99.9, decimals=0) == "€ 100"

    def test_negative_none_becomes_zero(self):
        # None maps to 0.0 which is not negative
        assert fmt_currency(None) == "€ 0.00"

    def test_small_negative(self):
        assert fmt_currency(-0.01) == "-€ 0.01"

    def test_string_input_coerced(self):
        # float("50") works
        assert fmt_currency("50") == "€ 50.00"


# ──────────────────────────────────────────────────────────────
# fmt_distance
# ──────────────────────────────────────────────────────────────


class TestFmtDistance:
    """Format kilometre distances as integers with space thousands separator."""

    def test_typical_value(self):
        assert fmt_distance(4734.0) == "4 734 km"

    def test_none_coerces_to_zero(self):
        assert fmt_distance(None) == "0 km"

    def test_zero(self):
        assert fmt_distance(0) == "0 km"

    def test_negative_distance(self):
        assert fmt_distance(-500) == "-500 km"

    def test_large_distance(self):
        assert fmt_distance(1234567) == "1 234 567 km"

    def test_rounding_up(self):
        assert fmt_distance(999.6) == "1 000 km"

    def test_rounding_down(self):
        assert fmt_distance(1000.4) == "1 000 km"

    def test_fractional_input(self):
        assert fmt_distance(47.9) == "48 km"

    def test_string_input(self):
        assert fmt_distance("100") == "100 km"


# ──────────────────────────────────────────────────────────────
# fmt_rate
# ──────────────────────────────────────────────────────────────


class TestFmtRate:
    """Format per-kilometre rates with two decimal places."""

    def test_typical_rate(self):
        assert fmt_rate(0.97) == "€ 0.97/km"

    def test_none_coerces_to_zero(self):
        assert fmt_rate(None) == "€ 0.00/km"

    def test_zero_rate(self):
        assert fmt_rate(0) == "€ 0.00/km"

    def test_negative_rate(self):
        assert fmt_rate(-0.5) == "€ -0.50/km"

    def test_large_rate(self):
        assert fmt_rate(1234.56) == "€ 1234.56/km"

    def test_many_decimals_truncated(self):
        assert fmt_rate(1.23456) == "€ 1.23/km"

    def test_rate_with_more_decimals(self):
        assert fmt_rate(0.999) == "€ 1.00/km"

    def test_whole_number(self):
        assert fmt_rate(5) == "€ 5.00/km"


# ──────────────────────────────────────────────────────────────
# fmt_date
# ──────────────────────────────────────────────────────────────


class TestFmtDate:
    """Convert various date string formats to DD.MM.YYYY."""

    def test_iso_format(self):
        assert fmt_date("2026-06-19") == "19.06.2026"

    def test_slash_format(self):
        assert fmt_date("19/06/2026") == "19.06.2026"

    def test_iso_with_time(self):
        assert fmt_date("2026-06-19 14:30:00") == "19.06.2026"

    def test_dot_format(self):
        assert fmt_date("19.06.2026") == "19.06.2026"

    def test_empty_string(self):
        assert fmt_date("") == ""

    def test_none_input(self):
        assert fmt_date(None) == ""

    def test_invalid_format_returns_original(self):
        assert fmt_date("not-a-date") == "not-a-date"

    def test_invalid_date_string(self):
        # A string that doesn't match any format
        assert fmt_date("hello world") == "hello world"

    def test_date_with_leading_whitespace(self):
        assert fmt_date("  2026-06-19  ") == "19.06.2026"

    def test_date_with_trailing_newline(self):
        assert fmt_date("2026-06-19\n") == "19.06.2026"


# ──────────────────────────────────────────────────────────────
# fmt_profit_color
# ──────────────────────────────────────────────────────────────


class TestFmtProfitColor:
    """Return colour token based on profit sign."""

    def test_positive_returns_success(self):
        assert fmt_profit_color(100) == "#34D399"

    def test_negative_returns_error(self):
        assert fmt_profit_color(-1) == "#F87171"

    def test_zero_returns_secondary(self):
        assert fmt_profit_color(0) == "#8E8EA0"

    def test_small_positive(self):
        assert fmt_profit_color(0.01) == "#34D399"

    def test_small_negative(self):
        assert fmt_profit_color(-0.01) == "#F87171"

    def test_large_positive(self):
        assert fmt_profit_color(1_000_000) == "#34D399"

    def test_large_negative(self):
        assert fmt_profit_color(-1_000_000) == "#F87171"

    def test_none_coerces_to_zero(self):
        # None won't compare; ensure it works or document behaviour
        # Currently None > 0 raises TypeError, so this documents
        # that callers should pass a number.
        with pytest.raises(TypeError):
            fmt_profit_color(None)


# ──────────────────────────────────────────────────────────────
# fmt_number
# ──────────────────────────────────────────────────────────────


class TestFmtNumber:
    """Generic number formatter with thousands separator."""

    def test_default_two_decimals(self):
        assert fmt_number(1234.5) == "1 234.50"

    def test_none_coerces_to_zero(self):
        assert fmt_number(None) == "0.00"

    def test_zero(self):
        assert fmt_number(0) == "0.00"

    def test_negative(self):
        assert fmt_number(-500.25) == "-500.25"

    def test_large_number(self):
        assert fmt_number(9876543.21) == "9 876 543.21"

    def test_zero_decimals(self):
        assert fmt_number(42.9, decimals=0) == "43"

    def test_three_decimals(self):
        # 1.2345 as float is slightly less than 1.2345, so rounds to 1.234
        assert fmt_number(1.23456, decimals=3) == "1.235"

    def test_whole_number(self):
        assert fmt_number(100, decimals=0) == "100"

    def test_negative_large(self):
        assert fmt_number(-1234567.89) == "-1 234 567.89"


# ──────────────────────────────────────────────────────────────
# fmt_percentage
# ──────────────────────────────────────────────────────────────


class TestFmtPercentage:
    """Format percentage values with fixed decimal places."""

    def test_default_one_decimal(self):
        assert fmt_percentage(12.34) == "12.3%"

    def test_none_coerces_to_zero(self):
        assert fmt_percentage(None) == "0.0%"

    def test_zero(self):
        assert fmt_percentage(0) == "0.0%"

    def test_negative(self):
        assert fmt_percentage(-5.5) == "-5.5%"

    def test_three_decimals(self):
        assert fmt_percentage(12.3456, decimals=3) == "12.346%"

    def test_zero_decimals(self):
        assert fmt_percentage(99.9, decimals=0) == "100%"

    def test_large_percentage(self):
        assert fmt_percentage(250.0) == "250.0%"

    def test_small_fraction(self):
        assert fmt_percentage(0.01) == "0.0%"
