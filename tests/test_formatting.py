"""Comprehensive unit tests for utils/formatting.py.

Tests cover format_currency, format_duration, format_distance,
format_percentage, and format_age — including None inputs, edge
cases, and backward-compatible wrapper behaviour.
"""

from __future__ import annotations

import pytest

from utils.formatting import (
    format_age,
    format_currency,
    format_distance,
    format_duration,
    format_percentage,
)


# ──────────────────────────────────────────────────────────────
# format_currency
# ──────────────────────────────────────────────────────────────


class TestFormatCurrency:
    """Backward-compatible wrapper around fmt_currency."""

    def test_default_currency(self):
        assert format_currency(39563.0) == "€ 39 563.00"

    def test_none_coerces_to_zero(self):
        assert format_currency(None) == "€ 0.00"

    def test_custom_symbol(self):
        assert format_currency(100, symbol="$") == "$ 100.00"

    def test_custom_decimals(self):
        assert format_currency(42.5, decimals=3) == "€ 42.500"

    def test_zero_decimals(self):
        assert format_currency(99.9, decimals=0) == "€ 100"

    def test_negative(self):
        assert format_currency(-50.25) == "-€ 50.25"

    def test_large(self):
        assert format_currency(1_000_000) == "€ 1 000 000.00"


# ──────────────────────────────────────────────────────────────
# format_duration
# ──────────────────────────────────────────────────────────────


class TestFormatDuration:
    """Human-readable day/hour/minute breakdown."""

    def test_zero(self):
        assert format_duration(0) == "0 min"

    def test_none_coerces_to_zero(self):
        assert format_duration(None) == "0 min"

    def test_negative_minutes(self):
        # abs is applied
        assert format_duration(-90) == "1h 30min"

    def test_only_minutes(self):
        assert format_duration(45) == "45min"

    def test_only_hours(self):
        assert format_duration(120) == "2h"

    def test_hours_and_minutes(self):
        assert format_duration(150) == "2h 30min"

    def test_days_only(self):
        assert format_duration(2880) == "2d"

    def test_days_and_hours(self):
        assert format_duration(3000) == "2d 2h"

    def test_days_hours_and_minutes(self):
        assert format_duration(2880 + 120 + 45) == "2d 2h 45min"

    def test_exact_one_day(self):
        assert format_duration(1440) == "1d"

    def test_exact_one_hour(self):
        assert format_duration(60) == "1h"

    def test_one_minute(self):
        assert format_duration(1) == "1min"

    def test_large_duration(self):
        assert format_duration(10080) == "7d"

    def test_fractional_minutes_rounded_down(self):
        # int(abs(...)) truncates fractional
        assert format_duration(90.7) == "1h 30min"

    def test_very_small_positive(self):
        # 0.5 → int(abs(0.5)) → 0
        assert format_duration(0.5) == "0 min"


# ──────────────────────────────────────────────────────────────
# format_distance
# ──────────────────────────────────────────────────────────────


class TestFormatDistance:
    """Backward-compatible wrapper with decimals=0 fallback to fmt_distance."""

    def test_zero_decimals_uses_fmt_distance(self):
        # decimals=0 → integer km with space thousands separator
        result = format_distance(4734.0, decimals=0)
        assert result == "4 734 km"

    def test_default_decimals_legacy(self):
        # decimals=1 → legacy format (Python comma thousands separator)
        result = format_distance(4734.0)
        assert result == "4,734.0 km"

    def test_two_decimals(self):
        result = format_distance(1234.5678, decimals=2)
        assert result == "1,234.57 km"

    def test_none_decimals_zero_falls_through(self):
        # decimals defaults to 1; None km will hit float(None) error
        # but format_distance(km, decimals=0) calls _fmt_distance(km)
        # which handles None
        result = format_distance(None, decimals=0)
        assert result == "0 km"

    def test_none_with_default_decimals_raises(self):
        # float(None) raises TypeError
        with pytest.raises(TypeError):
            format_distance(None)

    def test_large_distance_zero_decimals(self):
        result = format_distance(9_999_999, decimals=0)
        assert result == "9 999 999 km"

    def test_negative_zero_decimals(self):
        result = format_distance(-500, decimals=0)
        assert result == "-500 km"


# ──────────────────────────────────────────────────────────────
# format_percentage
# ──────────────────────────────────────────────────────────────


class TestFormatPercentage:
    """Backward-compatible wrapper around fmt_percentage."""

    def test_default_one_decimal(self):
        assert format_percentage(12.34) == "12.3%"

    def test_none_coerces_to_zero(self):
        assert format_percentage(None) == "0.0%"

    def test_custom_decimals(self):
        assert format_percentage(12.3456, decimals=3) == "12.346%"

    def test_zero(self):
        assert format_percentage(0) == "0.0%"

    def test_negative(self):
        assert format_percentage(-5.5) == "-5.5%"


# ──────────────────────────────────────────────────────────────
# format_age
# ──────────────────────────────────────────────────────────────


class TestFormatAge:
    """Human-readable age from seconds."""

    def test_none_returns_never(self):
        assert format_age(None) == "never"

    def test_under_60_seconds(self):
        assert format_age(30) == "30s"

    def test_exactly_59_seconds(self):
        assert format_age(59) == "59s"

    def test_exactly_60_seconds(self):
        assert format_age(60) == "1m"

    def test_under_3600_seconds(self):
        # 150/60 = 2.5 → f"{2.5:.0f}" rounds to 2 (banker's rounding)
        assert format_age(150) == "2m"

    def test_under_3600_seconds_exact(self):
        assert format_age(180) == "3m"

    def test_exactly_3599_seconds(self):
        assert format_age(3599) == "60m"

    def test_exactly_3600_seconds(self):
        assert format_age(3600) == "1.0h"

    def test_over_3600_seconds(self):
        assert format_age(7200) == "2.0h"

    def test_large_seconds(self):
        assert format_age(86400) == "24.0h"

    def test_zero_seconds(self):
        assert format_age(0) == "0s"

    def test_negative_seconds(self):
        # format just formats the number; sign is preserved in the float display
        assert format_age(-30) == "-30s"
