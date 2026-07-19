"""Comprehensive unit tests for AvailabilityChecker — truck & driver availability checks."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from services.dispatch_service.availability import AvailabilityChecker
from services.dispatch_service.models import DriverAvailability, TruckAvailability

# ── Date constants ─────────────────────────────────────────────────────
# Using far-past / far-future so tests pass whenever they are run.
FAR_PAST = "2020-01-01"
FAR_FUTURE = "2099-06-15"


# ── Helper: build tacho activities within the current week ──────────
# We avoid freezing time because datetime.datetime is a C extension type
# (cannot patch .now) and mocking the whole class breaks isinstance checks
# inside _parse_datetime.  Instead we compute timestamps relative to today.

def _current_monday() -> datetime:
    """Return midnight Monday of the current ISO week."""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _this_week_activity(*, start_hour: int, duration_hours: float,
                         day_offset: int = 0, violation: bool = False) -> dict:
    """Build a single tacho activity dict with a timestamp inside the current week."""
    dt = _current_monday() + timedelta(days=day_offset, hours=start_hour)
    return {
        "start_time": dt.isoformat(),
        "duration_hours": duration_hours,
        "violation": violation,
    }


# ══════════════════════════════════════════════════════════════════════
# check_truck — Blocking conditions
# ══════════════════════════════════════════════════════════════════════


class TestCheckTruck:
    """Each test isolates ONE blocking condition."""

    def setup_method(self):
        self.mock_conflict = MagicMock()
        self.mock_conflict.check_conflicts.return_value = []

        self.checker = AvailabilityChecker(
            fleet_repo=MagicMock(),
            driver_repo=MagicMock(),
            conflict_service=self.mock_conflict,
            tacho_repo=MagicMock(),
        )

        # Baseline valid truck (every field current)
        self.valid_truck = {
            "id": 1,
            "status": "Active",
            "insurance_expiry": FAR_FUTURE,
            "inspection_expiry": FAR_FUTURE,
            "next_maintenance_date": FAR_FUTURE,
        }

    # ── Happy path ──────────────────────────────────────────────────

    def test_available(self):
        """All fields current → truck is available."""
        result = self.checker.check_truck(self.valid_truck, {})
        assert result.available is True
        assert result.blocks == []
        assert result.conflicts == []
        assert result.status_text == "Available"
        assert isinstance(result, TruckAvailability)

    # ── Status ──────────────────────────────────────────────────────

    def test_in_service_status_blocks(self):
        """Status 'In Service' → blocked."""
        truck = {**self.valid_truck, "status": "In Service"}
        result = self.checker.check_truck(truck, {})
        assert result.available is False
        assert "Truck is in service/repair" in result.blocks
        assert len(result.blocks) == 1

    @pytest.mark.parametrize("status_val", ["in service", "In Service", "IN SERVICE", "In service"])
    def test_in_service_status_case_insensitive(self, status_val):
        """Status comparison must be case-insensitive."""
        truck = {**self.valid_truck, "status": status_val}
        result = self.checker.check_truck(truck, {})
        assert result.available is False
        assert "Truck is in service/repair" in result.blocks

    @pytest.mark.parametrize("status_val", ["Active", "On Route", "Available", "", None])
    def test_other_statuses_not_block(self, status_val):
        """Non-'In Service' statuses should NOT block."""
        truck = {**self.valid_truck, "status": status_val}
        result = self.checker.check_truck(truck, {})
        assert result.available is True

    # ── Insurance expiry ────────────────────────────────────────────

    def test_expired_insurance_blocks(self):
        """Insurance date in the past → blocked by Insurance expired."""
        truck = {**self.valid_truck, "insurance_expiry": FAR_PAST}
        result = self.checker.check_truck(truck, {})
        assert result.available is False
        assert "Insurance expired" in result.blocks

    def test_valid_insurance_does_not_block(self):
        """Insurance date in the future → no block."""
        # valid_truck already has FAR_FUTURE insurance
        result = self.checker.check_truck(self.valid_truck, {})
        assert result.available is True

    def test_insurance_fallback_field(self):
        """insurance_valid_until is used when insurance_expiry is absent."""
        truck = {**self.valid_truck, "insurance_expiry": None, "insurance_valid_until": FAR_PAST}
        result = self.checker.check_truck(truck, {})
        assert result.available is False
        assert "Insurance expired" in result.blocks

    def test_no_insurance_date_does_not_block(self):
        """No insurance date at all → no block."""
        truck = {**self.valid_truck, "insurance_expiry": None}
        result = self.checker.check_truck(truck, {})
        assert result.available is True

    # ── Inspection expiry ───────────────────────────────────────────

    def test_expired_inspection_blocks(self):
        """Inspection date in the past → blocked by Inspection (ITP) expired."""
        truck = {**self.valid_truck, "inspection_expiry": FAR_PAST}
        result = self.checker.check_truck(truck, {})
        assert result.available is False
        assert "Inspection (ITP) expired" in result.blocks

    def test_inspection_fallback_field(self):
        """itp_expiry is used when inspection_expiry is absent."""
        truck = {**self.valid_truck, "inspection_expiry": None, "itp_expiry": FAR_PAST}
        result = self.checker.check_truck(truck, {})
        assert result.available is False
        assert "Inspection (ITP) expired" in result.blocks

    def test_no_inspection_date_does_not_block(self):
        """No inspection date at all → no block."""
        truck = {**self.valid_truck, "inspection_expiry": None}
        result = self.checker.check_truck(truck, {})
        assert result.available is True

    # ── Maintenance due ─────────────────────────────────────────────

    def test_overdue_maintenance_blocks(self):
        """Maintenance date in the past → blocked by Maintenance overdue."""
        truck = {**self.valid_truck, "next_maintenance_date": FAR_PAST}
        result = self.checker.check_truck(truck, {})
        assert result.available is False
        assert "Maintenance overdue" in result.blocks

    def test_maintenance_fallback_field(self):
        """maintenance_due is used when next_maintenance_date is absent."""
        truck = {**self.valid_truck, "next_maintenance_date": None, "maintenance_due": FAR_PAST}
        result = self.checker.check_truck(truck, {})
        assert result.available is False
        assert "Maintenance overdue" in result.blocks

    def test_no_maintenance_date_does_not_block(self):
        """No maintenance date at all → no block."""
        truck = {**self.valid_truck, "next_maintenance_date": None}
        result = self.checker.check_truck(truck, {})
        assert result.available is True

    # ── Trip conflict ───────────────────────────────────────────────

    def test_conflict_blocks(self):
        """Conflict service returns overlapping trips → blocked."""
        self.mock_conflict.check_conflicts.return_value = [{"trip_id": 99}]
        result = self.checker.check_truck(self.valid_truck, {"trip_data": True})
        assert result.available is False
        assert "Conflict: 1 overlapping trips" in result.blocks
        assert result.conflicts == [{"trip_id": 99}]

    def test_no_conflicts_does_not_block(self):
        """Empty conflicts list → no block."""
        self.mock_conflict.check_conflicts.return_value = []
        result = self.checker.check_truck(self.valid_truck, {})
        assert result.available is True

    def test_conflict_service_exception_caught(self):
        """Exception from conflict service is caught gracefully."""
        self.mock_conflict.check_conflicts.side_effect = RuntimeError("Conflict service down")
        result = self.checker.check_truck(self.valid_truck, {})
        assert result.available is True  # exception caught, no block
        assert result.blocks == []
        assert result.conflicts == []

    # ── Multiple conditions ─────────────────────────────────────────

    def test_all_conditions_expired(self):
        """All blocking conditions true → multiple blocks reported."""
        truck = {
            **self.valid_truck,
            "status": "In Service",
            "insurance_expiry": FAR_PAST,
            "inspection_expiry": FAR_PAST,
            "next_maintenance_date": FAR_PAST,
        }
        self.mock_conflict.check_conflicts.return_value = [{"trip_id": 99}]
        result = self.checker.check_truck(truck, {})
        assert result.available is False
        assert "Truck is in service/repair" in result.blocks
        assert "Insurance expired" in result.blocks
        assert "Inspection (ITP) expired" in result.blocks
        assert "Maintenance overdue" in result.blocks
        assert "Conflict: 1 overlapping trips" in result.blocks
        assert len(result.blocks) == 5
        assert "Available" not in result.status_text
        assert result.status_text == "; ".join(result.blocks)

    # ── Date-parse edge cases within check context ──────────────────

    def test_insurance_malformed_date_ignored(self):
        """If insurance_expiry is not parseable, it is silently skipped."""
        truck = {**self.valid_truck, "insurance_expiry": "not-a-date"}
        result = self.checker.check_truck(truck, {})
        assert result.available is True

    def test_inspection_malformed_date_ignored(self):
        """If inspection_expiry is not parseable, it is silently skipped."""
        truck = {**self.valid_truck, "inspection_expiry": "not-a-date"}
        result = self.checker.check_truck(truck, {})
        assert result.available is True

    def test_maintenance_malformed_date_ignored(self):
        """If next_maintenance_date is not parseable, it is silently skipped."""
        truck = {**self.valid_truck, "next_maintenance_date": "not-a-date"}
        result = self.checker.check_truck(truck, {})
        assert result.available is True


# ══════════════════════════════════════════════════════════════════════
# check_driver — Blocking conditions
# ══════════════════════════════════════════════════════════════════════


class TestCheckDriver:
    """Each test isolates ONE blocking condition."""

    def setup_method(self):
        self.mock_conflict = MagicMock()
        self.mock_conflict.check_conflicts.return_value = []

        self.mock_tacho = MagicMock()
        self.mock_tacho.get_by_driver.return_value = []

        self.checker = AvailabilityChecker(
            fleet_repo=MagicMock(),
            driver_repo=MagicMock(),
            conflict_service=self.mock_conflict,
            tacho_repo=self.mock_tacho,
        )

        self.valid_driver = {
            "id": 10,
            "status": "Active",
            "license_expiry": FAR_FUTURE,
            "medical_cert_expiry": FAR_FUTURE,
        }

    # ── Happy path ──────────────────────────────────────────────────

    def test_available(self):
        """All fields current → driver is available."""
        result = self.checker.check_driver(self.valid_driver, {})
        assert result.available is True
        assert result.blocks == []
        assert result.conflicts == []
        assert result.status_text == "Available"
        assert result.weekly_hours == 0.0
        assert result.violations == 0
        assert isinstance(result, DriverAvailability)

    # ── License expiry ──────────────────────────────────────────────

    def test_expired_license_blocks(self):
        """License date in the past → blocked by Driving license expired."""
        driver = {**self.valid_driver, "license_expiry": FAR_PAST}
        result = self.checker.check_driver(driver, {})
        assert result.available is False
        assert "Driving license expired" in result.blocks
        assert len(result.blocks) == 1

    def test_license_fallback_field(self):
        """driving_license_expiry used when license_expiry is absent."""
        driver = {**self.valid_driver, "license_expiry": None, "driving_license_expiry": FAR_PAST}
        result = self.checker.check_driver(driver, {})
        assert result.available is False
        assert "Driving license expired" in result.blocks

    def test_no_license_date_does_not_block(self):
        """No license date at all → no block."""
        driver = {**self.valid_driver, "license_expiry": None}
        result = self.checker.check_driver(driver, {})
        assert result.available is True

    # ── Medical certificate expiry ──────────────────────────────────

    def test_expired_medical_blocks(self):
        """Medical cert date in the past → blocked by Medical certificate expired."""
        driver = {**self.valid_driver, "medical_cert_expiry": FAR_PAST}
        result = self.checker.check_driver(driver, {})
        assert result.available is False
        assert "Medical certificate expired" in result.blocks

    def test_medical_fallback_field(self):
        """medical_expiry used when medical_cert_expiry is absent."""
        driver = {**self.valid_driver, "medical_cert_expiry": None, "medical_expiry": FAR_PAST}
        result = self.checker.check_driver(driver, {})
        assert result.available is False
        assert "Medical certificate expired" in result.blocks

    def test_no_medical_date_does_not_block(self):
        """No medical date at all → no block."""
        driver = {**self.valid_driver, "medical_cert_expiry": None}
        result = self.checker.check_driver(driver, {})
        assert result.available is True

    # ── Tacho weekly hours ──────────────────────────────────────────

    def test_tacho_hours_exceeded_blocks(self):
        """Weekly driving hours > 56 → blocked by Hours exceeded."""
        activities = [
            _this_week_activity(day_offset=0, start_hour=8, duration_hours=30),
            _this_week_activity(day_offset=1, start_hour=8, duration_hours=30),
        ]
        self.mock_tacho.get_by_driver.return_value = activities

        result = self.checker.check_driver(self.valid_driver, {})

        assert result.available is False
        assert any("Hours exceeded" in b for b in result.blocks)
        assert result.weekly_hours == 60.0

    def test_tacho_hours_within_limit(self):
        """Weekly driving hours ≤ 56 → no block."""
        activities = [
            _this_week_activity(day_offset=0, start_hour=8, duration_hours=28),
        ]
        self.mock_tacho.get_by_driver.return_value = activities

        result = self.checker.check_driver(self.valid_driver, {})

        assert result.available is True
        assert result.weekly_hours == 28.0
        assert not any("Hours exceeded" in b for b in result.blocks)

    def test_tacho_excessive_violations_blocks(self):
        """More than 3 violations → blocked by Excessive violations."""
        activities = [
            _this_week_activity(day_offset=0, start_hour=8, duration_hours=8, violation=True),
            _this_week_activity(day_offset=1, start_hour=8, duration_hours=8, violation=True),
            _this_week_activity(day_offset=2, start_hour=8, duration_hours=8, violation=True),
            _this_week_activity(day_offset=3, start_hour=8, duration_hours=8, violation=True),
        ]
        self.mock_tacho.get_by_driver.return_value = activities

        result = self.checker.check_driver(self.valid_driver, {})

        assert result.available is False
        assert any("Excessive violations" in b for b in result.blocks)
        assert result.violations == 4

    def test_tacho_uses_start_time_or_timestamp_field(self):
        """Tacho check uses start_time, with fallback to timestamp."""
        activities = [
            {"timestamp": _this_week_activity(day_offset=0, start_hour=8, duration_hours=30)["start_time"],
             "duration_hours": 30, "violation": False},
            {"timestamp": _this_week_activity(day_offset=1, start_hour=8, duration_hours=30)["start_time"],
             "duration_hours": 30, "violation": False},
        ]
        self.mock_tacho.get_by_driver.return_value = activities

        result = self.checker.check_driver(self.valid_driver, {})

        assert result.available is False
        assert result.weekly_hours == 60.0

    def test_tacho_hours_old_activities_excluded(self):
        """Activities before the current week should not count."""
        prev_monday = _current_monday() - timedelta(days=7)
        old_ts = prev_monday.replace(hour=8).isoformat()
        activities = [
            {"start_time": old_ts, "duration_hours": 100, "violation": False},
        ]
        self.mock_tacho.get_by_driver.return_value = activities

        result = self.checker.check_driver(self.valid_driver, {})

        assert result.available is True
        assert result.weekly_hours == 0.0  # excluded because before week_start

    def test_tacho_repo_none_skips_tacho_check(self):
        """When tacho_repo is None, tacho check is skipped entirely."""
        checker = AvailabilityChecker(
            fleet_repo=MagicMock(),
            driver_repo=MagicMock(),
            conflict_service=self.mock_conflict,
            tacho_repo=None,
        )
        # Even with a driver_id, no tacho check happens
        result = checker.check_driver(self.valid_driver, {})
        assert result.available is True
        assert result.weekly_hours == 0.0
        assert result.violations == 0

    def test_tacho_repo_exception_caught(self):
        """Exception from tacho_repo is caught gracefully."""
        self.mock_tacho.get_by_driver.side_effect = RuntimeError("Tacho DB down")
        result = self.checker.check_driver(self.valid_driver, {})
        assert result.available is True  # exception caught, no block
        assert result.weekly_hours == 0.0

    # ── Status ──────────────────────────────────────────────────────

    def test_inactive_status_blocks(self):
        """Status 'Inactive' → blocked by Driver is inactive."""
        driver = {**self.valid_driver, "status": "Inactive"}
        result = self.checker.check_driver(driver, {})
        assert result.available is False
        assert "Driver is inactive" in result.blocks

    def test_active_status_not_block(self):
        """Status 'Active' → NOT blocked by status."""
        driver = {**self.valid_driver, "status": "Active"}
        result = self.checker.check_driver(driver, {})
        assert result.available is True

    @pytest.mark.parametrize("status_val", ["inactive", "Inactive", "INACTIVE"])
    def test_inactive_status_case_insensitive(self, status_val):
        """Status comparison must be case-insensitive."""
        driver = {**self.valid_driver, "status": status_val}
        result = self.checker.check_driver(driver, {})
        assert result.available is False
        assert "Driver is inactive" in result.blocks

    # ── Conflict ────────────────────────────────────────────────────

    def test_conflict_blocks(self):
        """Conflict service returns overlapping trips → blocked."""
        self.mock_conflict.check_conflicts.return_value = [{"trip_id": 42}]
        result = self.checker.check_driver(self.valid_driver, {})
        assert result.available is False
        assert "Conflict: 1 overlapping trips" in result.blocks
        assert result.conflicts == [{"trip_id": 42}]

    def test_conflict_service_exception_caught_driver(self):
        """Exception from conflict service is caught gracefully in check_driver."""
        self.mock_conflict.check_conflicts.side_effect = RuntimeError("Conflict service down")
        result = self.checker.check_driver(self.valid_driver, {})
        assert result.available is True
        assert result.blocks == []
        assert result.conflicts == []

    # ── Multiple conditions ─────────────────────────────────────────

    def test_multiple_blocking_conditions(self):
        """Multiple blocking conditions → all reported."""
        driver = {
            **self.valid_driver,
            "status": "Inactive",
            "license_expiry": FAR_PAST,
            "medical_cert_expiry": FAR_PAST,
        }
        self.mock_conflict.check_conflicts.return_value = [{"trip_id": 42}]

        result = self.checker.check_driver(driver, {})

        assert result.available is False
        assert "Driver is inactive" in result.blocks
        assert "Driving license expired" in result.blocks
        assert "Medical certificate expired" in result.blocks
        assert "Conflict: 1 overlapping trips" in result.blocks

    # ── Current transport (driver current_transport field) ──────────

    def test_driver_with_current_transport_not_blocked(self):
        """Having a current_transport id does NOT block the driver."""
        driver = {**self.valid_driver, "current_transport": 99}
        result = self.checker.check_driver(driver, {})
        assert result.available is True
        # current_transport is not explicitly checked in availability logic
        # so it should not appear in blocks

    # ── Date-parse edge cases within check context ──────────────────

    def test_license_malformed_date_ignored(self):
        """Unparseable license date is silently skipped."""
        driver = {**self.valid_driver, "license_expiry": "invalid-date"}
        result = self.checker.check_driver(driver, {})
        assert result.available is True

    def test_medical_malformed_date_ignored(self):
        """Unparseable medical date is silently skipped."""
        driver = {**self.valid_driver, "medical_cert_expiry": "invalid-date"}
        result = self.checker.check_driver(driver, {})
        assert result.available is True

    # ── Driver without ID (edge case) ───────────────────────────────

    def test_driver_without_id_skips_tacho(self):
        """If driver has no id, tacho check is skipped (no crash)."""
        driver = {**self.valid_driver, "id": None}
        result = self.checker.check_driver(driver, {})
        assert result.available is True


# ══════════════════════════════════════════════════════════════════════
# _parse_date — Helper
# ══════════════════════════════════════════════════════════════════════


class TestParseDate:
    """Edge cases for the internal _parse_date helper."""

    def setup_method(self):
        self.checker = AvailabilityChecker(
            fleet_repo=MagicMock(),
            driver_repo=MagicMock(),
            conflict_service=MagicMock(),
        )

    def test_yyyy_mm_dd(self):
        """%Y-%m-%d format."""
        result = self.checker._parse_date("2026-07-19")
        assert result == date(2026, 7, 19)

    def test_dd_mm_yyyy_slash(self):
        """%d/%m/%Y format."""
        result = self.checker._parse_date("19/07/2026")
        assert result == date(2026, 7, 19)

    def test_dd_mm_yyyy_dot(self):
        """%d.%m.%Y format."""
        result = self.checker._parse_date("19.07.2026")
        assert result == date(2026, 7, 19)

    def test_date_object_passthrough(self):
        """Already a date object → returned as-is."""
        d = date(2026, 7, 19)
        result = self.checker._parse_date(d)
        assert result is d

    def test_datetime_object_extracts_date(self):
        """datetime object → returned as-is because datetime is subclass of date."""
        dt = datetime(2026, 7, 19, 14, 30, 0)
        result = self.checker._parse_date(dt)
        # datetime is a subclass of date, so isinstance(value, date) matches first
        assert result is dt

    def test_empty_string_returns_none(self):
        """Empty string → None."""
        result = self.checker._parse_date("")
        assert result is None

    def test_none_returns_none(self):
        """None → None."""
        result = self.checker._parse_date(None)
        assert result is None

    def test_malformed_string_returns_none(self):
        """Unparseable string → None (no exception)."""
        result = self.checker._parse_date("not-a-date")
        assert result is None

    def test_partial_date_returns_none(self):
        """Partial date like '2026-07' → None (no format matches)."""
        result = self.checker._parse_date("2026-07")
        assert result is None

    def test_string_with_trailing_whitespace(self):
        """Whitespace is stripped before parsing."""
        result = self.checker._parse_date("  2026-07-19  ")
        assert result == date(2026, 7, 19)

    def test_first_matching_format_wins(self):
        """Value that matches multiple formats uses first match (%Y-%m-%d)."""
        # "01-02-2026" — would match %Y-%m-%d as year=01, month=02, day=2026
        # But 2026 as day is invalid, so it falls through
        # Actually let's use a cleaner example:
        # "2026-01-02" matches %Y-%m-%d → date(2026, 1, 2)
        result = self.checker._parse_date("2026-01-02")
        assert result == date(2026, 1, 2)

    def test_alternative_delimiter_after_slice(self):
        """Only first 10 chars are used; extra content after that is ignored."""
        result = self.checker._parse_date("2026-07-19 extra")
        assert result == date(2026, 7, 19)


# ══════════════════════════════════════════════════════════════════════
# _parse_datetime — Helper
# ══════════════════════════════════════════════════════════════════════


class TestParseDatetime:
    """Edge cases for the internal _parse_datetime helper."""

    def setup_method(self):
        self.checker = AvailabilityChecker(
            fleet_repo=MagicMock(),
            driver_repo=MagicMock(),
            conflict_service=MagicMock(),
        )

    def test_iso_format(self):
        """Standard ISO datetime."""
        result = self.checker._parse_datetime("2026-07-19T14:30:00")
        assert result == datetime(2026, 7, 19, 14, 30, 0)

    def test_iso_with_z_suffix(self):
        """ISO datetime with Z suffix → Z replaced with +00:00 (UTC)."""
        result = self.checker._parse_datetime("2026-07-19T14:30:00Z")
        assert result == datetime(2026, 7, 19, 14, 30, 0, tzinfo=timezone.utc)

    def test_iso_with_timezone(self):
        """ISO datetime with explicit timezone offset."""
        result = self.checker._parse_datetime("2026-07-19T14:30:00+02:00")
        # fromisoformat preserves timezone info
        assert result is not None
        assert result.hour == 14
        assert result.minute == 30

    def test_datetime_object_passthrough(self):
        """Already a datetime object → returned as-is."""
        dt = datetime(2026, 7, 19, 14, 30, 0)
        result = self.checker._parse_datetime(dt)
        assert result is dt

    def test_empty_string_returns_none(self):
        """Empty string → None."""
        result = self.checker._parse_datetime("")
        assert result is None

    def test_none_returns_none(self):
        """None → None."""
        result = self.checker._parse_datetime(None)
        assert result is None

    def test_malformed_string_returns_none(self):
        """Unparseable string → None (no exception)."""
        result = self.checker._parse_datetime("not-a-datetime")
        assert result is None

    def test_date_only_string(self):
        """Date-only string '2026-07-19' → midnight datetime."""
        result = self.checker._parse_datetime("2026-07-19")
        assert result == datetime(2026, 7, 19, 0, 0, 0)

    def test_integer_value_returns_none(self):
        """Non-string/non-datetime value → None."""
        result = self.checker._parse_datetime(12345)
        assert result is None
