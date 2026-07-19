"""Comprehensive unit tests for utils/dates — parse_date_safe and is_expired.

Tests cover all supported date formats, edge cases, boundary
conditions (leap year, month boundaries), empty strings, None,
and malformed inputs.
"""

from __future__ import annotations

import datetime
from datetime import datetime as dt
from typing import Optional

import pytest
from freezegun import freeze_time
from utils.dates import is_expired, parse_date_safe


# ────────────────────────────────────────────────────────────────
# parse_date_safe
# ────────────────────────────────────────────────────────────────


class TestParseDateSafe:
    """Parse date in ISO or DD/MM/YYYY format with optional time."""

    # ── Valid ISO formats ────────────────────────────────────

    def test_iso_date_only(self):
        result = parse_date_safe("2024-03-15")
        assert result == dt(2024, 3, 15)

    def test_iso_with_time(self):
        result = parse_date_safe("2024-03-15 14:30")
        assert result == dt(2024, 3, 15, 14, 30)

    def test_iso_with_leading_trailing_whitespace(self):
        result = parse_date_safe("  2024-03-15  ")
        assert result == dt(2024, 3, 15)

    def test_iso_with_time_and_whitespace(self):
        result = parse_date_safe("  2024-03-15 14:30  ")
        assert result == dt(2024, 3, 15, 14, 30)

    # ── Valid DD/MM/YYYY formats ─────────────────────────────

    def test_dmy_date_only(self):
        result = parse_date_safe("15/03/2024")
        assert result == dt(2024, 3, 15)

    def test_dmy_with_time(self):
        result = parse_date_safe("15/03/2024 14:30")
        assert result == dt(2024, 3, 15, 14, 30)

    def test_dmy_with_leading_trailing_whitespace(self):
        result = parse_date_safe("  15/03/2024  ")
        assert result == dt(2024, 3, 15)

    def test_dmy_with_time_and_whitespace(self):
        result = parse_date_safe("  15/03/2024 14:30  ")
        assert result == dt(2024, 3, 15, 14, 30)

    # ── Boundary: month boundaries ───────────────────────────

    def test_january_first(self):
        result = parse_date_safe("2024-01-01")
        assert result == dt(2024, 1, 1)

    def test_december_thirty_first(self):
        result = parse_date_safe("2024-12-31")
        assert result == dt(2024, 12, 31)

    def test_month_end_february_non_leap(self):
        result = parse_date_safe("2023-02-28")
        assert result == dt(2023, 2, 28)

    def test_month_start(self):
        result = parse_date_safe("2024-06-01")
        assert result == dt(2024, 6, 1)

    # ── Boundary: leap year ──────────────────────────────────

    def test_leap_year_feb_29(self):
        result = parse_date_safe("2024-02-29")
        assert result == dt(2024, 2, 29)

    def test_leap_year_feb_29_dmy(self):
        result = parse_date_safe("29/02/2024")
        assert result == dt(2024, 2, 29)

    def test_non_leap_year_feb_29_returns_none(self):
        # 2023 is not a leap year, Feb 29 is invalid
        result = parse_date_safe("2023-02-29")
        assert result is None

    def test_feb_29_dmy_non_leap_returns_none(self):
        result = parse_date_safe("29/02/2023")
        assert result is None

    def test_leap_year_2000(self):
        # Year 2000 is a leap year (divisible by 400)
        result = parse_date_safe("2000-02-29")
        assert result == dt(2000, 2, 29)

    def test_leap_year_1900_not_leap(self):
        # Year 1900 is not a leap year (divisible by 100 but not 400)
        result = parse_date_safe("1900-02-29")
        assert result is None

    # ── Boundary: time boundaries ────────────────────────────

    def test_midnight(self):
        result = parse_date_safe("2024-03-15 00:00")
        assert result == dt(2024, 3, 15, 0, 0)

    def test_end_of_day(self):
        result = parse_date_safe("2024-03-15 23:59")
        assert result == dt(2024, 3, 15, 23, 59)

    # ── Empty / None inputs ──────────────────────────────────

    def test_empty_string(self):
        assert parse_date_safe("") is None

    def test_whitespace_only(self):
        assert parse_date_safe("   ") is None

    def test_none(self):
        assert parse_date_safe(None) is None  # type: ignore[arg-type]

    # ── Malformed / invalid inputs ───────────────────────────

    def test_random_text(self):
        assert parse_date_safe("not-a-date") is None

    def test_reversed_format_iso_as_dmy(self):
        # "03-15-2024" doesn't match any supported format
        assert parse_date_safe("03-15-2024") is None

    def test_invalid_month(self):
        assert parse_date_safe("2024-13-01") is None

    def test_invalid_day(self):
        assert parse_date_safe("2024-01-32") is None

    def test_invalid_hour_falls_back_to_date_only(self):
        # "25:00" fails the full datetime format, but parse_date_safe
        # falls back to %Y-%m-%d which matches the date portion.
        result = parse_date_safe("2024-03-15 25:00")
        assert result == dt(2024, 3, 15)

    def test_invalid_minute_falls_back_to_date_only(self):
        # Same fallback behaviour as invalid hour.
        result = parse_date_safe("2024-03-15 14:60")
        assert result == dt(2024, 3, 15)

    def test_partial_date(self):
        assert parse_date_safe("2024-03") is None

    def test_single_digit_day_month(self):
        # Python's strptime accepts 1-2 digits for %d and %m.
        result = parse_date_safe("1/1/2024")
        assert result == dt(2024, 1, 1)

    def test_mixed_separator(self):
        assert parse_date_safe("2024/03-15") is None

    def test_trailing_garbage(self):
        # The [:expected_len] slicing truncates to 12 chars for
        # %Y-%m-%d; strptime ignores trailing non-matching chars
        # so the date portion still parses correctly.
        result = parse_date_safe("2024-03-15 extra")
        assert result == dt(2024, 3, 15)

    # ── Format priority ──────────────────────────────────────

    def test_iso_date_preferred_over_dmy(self):
        # 2024-03-15 could look like 15/03/2024? No, ISO starts
        # with 4-digit year so it will never match DD/MM/YYYY.
        result = parse_date_safe("2024-03-15")
        assert result == dt(2024, 3, 15)

    def test_iso_with_time_preferred(self):
        result = parse_date_safe("2024-03-15 14:30")
        assert result == dt(2024, 3, 15, 14, 30)

    def test_dmy_date_falls_back(self):
        result = parse_date_safe("15/03/2024")
        assert result == dt(2024, 3, 15)

    def test_dmy_with_time_falls_back(self):
        result = parse_date_safe("15/03/2024 14:30")
        assert result == dt(2024, 3, 15, 14, 30)

    # ── Year boundary ────────────────────────────────────────

    def test_year_9999(self):
        result = parse_date_safe("9999-12-31")
        assert result == dt(9999, 12, 31)

    def test_year_0001(self):
        result = parse_date_safe("0001-01-01")
        assert result == dt(1, 1, 1)

    def test_year_2038_problem(self):
        # Beyond 2038-01-19 on 32-bit systems, but Python handles it
        result = parse_date_safe("2038-01-20")
        assert result == dt(2038, 1, 20)

    def test_year_10000(self):
        # Python datetime supports year up to 9999
        assert parse_date_safe("10000-01-01") is None


# ────────────────────────────────────────────────────────────────
# is_expired
# ────────────────────────────────────────────────────────────────


class TestIsExpired:
    """Check whether a date string is in the past."""

    # ── Past dates (expired) ─────────────────────────────────

    @freeze_time("2024-06-15")
    def test_past_date_iso(self):
        assert is_expired("2024-06-01") is True

    @freeze_time("2024-06-15")
    def test_past_date_dmy(self):
        # is_expired calls days_ago which calls parse_date
        # with the default fmt="%Y-%m-%d", so DD/MM/YYYY
        # passed directly to is_expired will not parse correctly.
        # This test documents the limitation.
        result = is_expired("01/06/2024")
        assert result is None  # parse_date fails → None

    @freeze_time("2024-06-15")
    def test_one_day_ago(self):
        assert is_expired("2024-06-14") is True

    @freeze_time("2024-06-15")
    def test_one_year_ago(self):
        assert is_expired("2023-06-15") is True

    @freeze_time("2024-06-15 23:59")
    def test_past_with_time_ignored(self):
        # is_expired uses parse_date which slices to 10 chars
        assert is_expired("2024-06-14 14:30") is True

    # ── Future dates (not expired) ───────────────────────────

    @freeze_time("2024-06-15")
    def test_future_date_iso(self):
        assert is_expired("2024-07-01") is False

    @freeze_time("2024-06-15")
    def test_one_day_ahead(self):
        assert is_expired("2024-06-16") is False

    @freeze_time("2024-06-15")
    def test_one_year_ahead(self):
        assert is_expired("2025-06-15") is False

    @freeze_time("2024-06-15")
    def test_far_future(self):
        assert is_expired("2099-12-31") is False

    # ── Current date (boundary) ──────────────────────────────

    @freeze_time("2024-06-15")
    def test_today(self):
        # days == 0 → days > 0 is False
        assert is_expired("2024-06-15") is False

    @freeze_time("2024-06-15 12:00")
    def test_today_with_time(self):
        assert is_expired("2024-06-15 08:00") is False

    # ── None date ────────────────────────────────────────────

    def test_none_returns_none(self):
        assert is_expired(None) is None  # type: ignore[arg-type]

    # ── Invalid date string ──────────────────────────────────

    def test_empty_string(self):
        assert is_expired("") is None

    def test_whitespace_only(self):
        assert is_expired("   ") is None

    def test_malformed_string(self):
        assert is_expired("not-a-date") is None

    def test_invalid_day_month(self):
        assert is_expired("2024-13-01") is None

    # ── Custom format ────────────────────────────────────────

    @freeze_time("2024-06-15")
    def test_custom_format_dmy(self):
        # Passing fmt="%d/%m/%Y" allows DD/MM/YYYY parsing
        assert is_expired("01/06/2024", fmt="%d/%m/%Y") is True

    @freeze_time("2024-06-15")
    def test_custom_format_future(self):
        assert is_expired("01/07/2024", fmt="%d/%m/%Y") is False

    @freeze_time("2024-06-15")
    def test_custom_format_with_slashes_today(self):
        assert is_expired("15/06/2024", fmt="%d/%m/%Y") is False

    @freeze_time("2024-06-15")
    def test_custom_format_invalid(self):
        assert is_expired("40/06/2024", fmt="%d/%m/%Y") is None

    # ── Timezone note ────────────────────────────────────────

    @freeze_time("2024-06-15")
    def test_date_without_timezone_compares_date_only(self):
        # days_ago uses (now.date() - dt.date()).days when tzinfo is None
        assert is_expired("2024-06-14") is True
        assert is_expired("2024-06-15") is False
        assert is_expired("2024-06-16") is False
