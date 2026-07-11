"""Audit-driven test coverage for edge cases across utils and services."""
import math
import unittest
from datetime import datetime, timedelta
from unittest import mock

from utils.validation import (
    validate_positive_number,
    validate_email,
    validate_plate,
    validate_plate_with_reason,
    validate_email_with_reason,
)
from utils.dates import is_expired, days_ago, parse_date, parse_date_safe
from utils.formatting import format_currency, format_duration, format_distance
from services.route_decoder import decode_polyline
from services.cost_engine import CostEngineService
from services.conflict_service import TripConflictService
from tests.test_helpers import make_db


# =============================================================================
# 1. utils/validation.py
# =============================================================================

class TestValidatePositiveNumber(unittest.TestCase):
    """validate_positive_number must reject special floats and return None."""

    def test_rejects_inf_string(self):
        self.assertIsNone(validate_positive_number("inf"))

    def test_rejects_neg_inf_string(self):
        self.assertIsNone(validate_positive_number("-inf"))

    def test_rejects_nan_string(self):
        self.assertIsNone(validate_positive_number("nan"))

    def test_rejects_negative_number(self):
        self.assertIsNone(validate_positive_number("-5"))

    def test_rejects_zero(self):
        self.assertIsNone(validate_positive_number("0"))

    def test_accepts_valid_positive(self):
        self.assertEqual(validate_positive_number("42.5"), 42.5)

    def test_accepts_positive_integer_string(self):
        self.assertEqual(validate_positive_number("100"), 100.0)

    def test_rejects_non_numeric_string(self):
        self.assertIsNone(validate_positive_number("abc"))

    def test_rejects_none(self):
        self.assertIsNone(validate_positive_number(None))


class TestValidateEmail(unittest.TestCase):
    """validate_email edge cases."""

    def test_empty_string(self):
        self.assertFalse(validate_email(""))

    def test_no_at_sign(self):
        self.assertFalse(validate_email("plainaddress"))

    def test_no_domain(self):
        self.assertFalse(validate_email("user@.com"))

    def test_no_tld(self):
        self.assertFalse(validate_email("user@domain"))

    def test_spaces_in_email(self):
        self.assertFalse(validate_email("user @domain.com"))

    def test_valid_simple(self):
        self.assertTrue(validate_email("test@example.com"))

    def test_valid_with_underscore(self):
        self.assertTrue(validate_email("user_name@domain.co.uk"))

    def test_very_long_email(self):
        local = "a" * 250
        full = f"{local}@b.co"
        self.assertFalse(validate_email(full))

    def test_whitespace_around_valid_email(self):
        self.assertTrue(validate_email("  user@domain.com  "))


class TestValidatePlate(unittest.TestCase):
    """validate_plate edge cases."""

    def test_empty_string(self):
        self.assertFalse(validate_plate(""))

    def test_valid_plate_letters_and_numbers(self):
        self.assertTrue(validate_plate("B-123-ABC"))

    def test_valid_plate_clean(self):
        self.assertTrue(validate_plate("B123ABC"))

    def test_too_short(self):
        self.assertFalse(validate_plate("A"))

    def test_too_long(self):
        self.assertFalse(validate_plate("A" * 13))

    def test_special_characters(self):
        self.assertFalse(validate_plate("AB@123"))

    def test_lowercase_normalized(self):
        self.assertTrue(validate_plate("b-123-abc"))

    def test_whitespace_stripped(self):
        self.assertTrue(validate_plate("  B-123-ABC  "))


class TestValidatePlateWithReason(unittest.TestCase):
    """validate_plate_with_reason returns (bool, reason_or_None)."""

    def test_empty_returns_false_with_reason(self):
        ok, reason = validate_plate_with_reason("")
        self.assertFalse(ok)
        self.assertIsNotNone(reason)

    def test_valid_returns_true_no_reason(self):
        ok, reason = validate_plate_with_reason("B-123-ABC")
        self.assertTrue(ok)
        self.assertIsNone(reason)


class TestValidateEmailWithReason(unittest.TestCase):
    def test_empty_returns_false_with_reason(self):
        ok, reason = validate_email_with_reason("")
        self.assertFalse(ok)
        self.assertIsNotNone(reason)

    def test_valid_returns_true_no_reason(self):
        ok, reason = validate_email_with_reason("test@example.com")
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_exceeds_254_chars(self):
        local = "a" * 250
        ok, reason = validate_email_with_reason(f"{local}@b.co")
        self.assertFalse(ok)
        self.assertIsNotNone(reason)
        assert reason is not None  # help type checker
        self.assertIn("exceeds", reason.lower())


# =============================================================================
# 2. utils/dates.py
# =============================================================================

class TestIsExpired(unittest.TestCase):
    """is_expired returns None for unparseable dates, bool otherwise."""

    def test_unparseable_string_returns_none(self):
        self.assertIsNone(is_expired("not-a-date"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(is_expired(""))

    def test_past_date_returns_true(self):
        self.assertTrue(is_expired("2020-01-01"))

    def test_future_date_returns_false(self):
        # Use a date far in the future so it's never expired
        self.assertFalse(is_expired("2099-12-31"))


class TestDaysAgo(unittest.TestCase):
    """days_ago uses UTC-consistent datetime and returns int or None."""

    def test_unparseable_returns_none(self):
        self.assertIsNone(days_ago("bad-date"))

    def test_empty_returns_none(self):
        self.assertIsNone(days_ago(""))

    def test_known_date_returns_correct_int(self):
        # A date far in the past should yield a large positive integer
        result = days_ago("2000-01-01")
        self.assertIsNotNone(result)
        self.assertGreater(result, 8000)  # type: ignore[arg-type]

    def test_today_returns_zero(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(days_ago(today_str), 0)


class TestParseDate(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(parse_date(""))

    def test_valid_iso_returns_datetime(self):
        dt = parse_date("2024-12-25")
        self.assertIsNotNone(dt)
        if dt:
            self.assertEqual(dt.year, 2024)
            self.assertEqual(dt.month, 12)
            self.assertEqual(dt.day, 25)

    def test_longer_string_truncated(self):
        dt = parse_date("2024-12-25 extra")
        self.assertIsNotNone(dt)

    def test_invalid_format_returns_none(self):
        self.assertIsNone(parse_date("25/12/2024"))

    def test_none_returns_none(self):
        self.assertIsNone(parse_date(None))  # type: ignore[arg-type]


class TestParseDateSafe(unittest.TestCase):
    """NOTE: len(fmt) slicing in the source code means pure date strings
    (without time) fail to parse because format-specifier length != display length.
    E.g. len('%Y-%m-%d') == 8 but '2024-12-25'[:8] == '2024-12-'.
    Only full datetime strings matching the format lengths survive."""

    def test_empty_returns_none(self):
        self.assertIsNone(parse_date_safe(""))

    def test_iso_date_without_time_returns_datetime(self):
        dt = parse_date_safe("2024-12-25")
        self.assertIsNotNone(dt)
        if dt:
            self.assertEqual(dt.year, 2024)
            self.assertEqual(dt.month, 12)
            self.assertEqual(dt.day, 25)

    def test_dd_mm_yyyy_without_time_returns_datetime(self):
        dt = parse_date_safe("25/12/2024")
        self.assertIsNotNone(dt)
        if dt:
            self.assertEqual(dt.year, 2024)
            self.assertEqual(dt.month, 12)
            self.assertEqual(dt.day, 25)

    def test_garbage_returns_none(self):
        self.assertIsNone(parse_date_safe("abcdef"))


# =============================================================================
# 3. utils/formatting.py
# =============================================================================

class TestFormatCurrency(unittest.TestCase):
    def test_default_format(self):
        self.assertEqual(format_currency(1234.5), "€ 1 234.50")

    def test_zero_value(self):
        self.assertEqual(format_currency(0), "€ 0.00")

    def test_custom_decimals(self):
        self.assertEqual(format_currency(1.234, decimals=3), "€ 1.234")

    def test_custom_symbol(self):
        self.assertEqual(format_currency(100, symbol="$"), "$ 100.00")

    def test_large_number(self):
        self.assertEqual(format_currency(987654321.01), "€ 987 654 321.01")


class TestFormatDuration(unittest.TestCase):
    def test_zero_returns_0_min(self):
        self.assertEqual(format_duration(0), "0 min")

    def test_none_is_treated_as_zero(self):
        self.assertEqual(format_duration(None), "0 min")  # type: ignore[arg-type]

    def test_negative_value_uses_absolute(self):
        self.assertEqual(format_duration(-90), "1h 30min")

    def test_only_minutes(self):
        self.assertEqual(format_duration(45), "45min")

    def test_hours_and_minutes(self):
        self.assertEqual(format_duration(150), "2h 30min")

    def test_days_hours_minutes(self):
        # 0h is omitted by the formatter when hours==0
        self.assertEqual(format_duration(2900), "2d 20min")

    def test_exact_one_day(self):
        self.assertEqual(format_duration(1440), "1d")

    def test_large_value(self):
        self.assertEqual(format_duration(10080), "7d")

    def test_rounds_down_float(self):
        self.assertEqual(format_duration(90.7), "1h 30min")


class TestFormatDistance(unittest.TestCase):
    def test_default_format(self):
        self.assertEqual(format_distance(1234.5), "1,234.5 km")

    def test_zero(self):
        self.assertEqual(format_distance(0), "0.0 km")

    def test_small_integer(self):
        self.assertEqual(format_distance(5), "5.0 km")

    def test_custom_decimals(self):
        self.assertEqual(format_distance(1.234, decimals=2), "1.23 km")

    def test_large_number(self):
        self.assertEqual(format_distance(1234567.89), "1,234,567.9 km")


# =============================================================================
# 4. services/route_decoder.py
# =============================================================================

class TestDecodePolyline(unittest.TestCase):
    """decode_polyline edge cases."""

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(decode_polyline(""), [])

    def test_none_returns_empty_list(self):
        self.assertEqual(decode_polyline(None), [])  # type: ignore[arg-type]

    def test_single_character_raises_value_error(self):
        with self.assertRaises(ValueError):
            decode_polyline("x")

    def test_invalid_high_bytes_raises_value_error(self):
        with self.assertRaises(ValueError):
            decode_polyline("\x7f\xff\xff")

    def test_known_valid_polyline(self):
        # Simple encoded polyline for a single point near (52.5, 13.4)
        result = decode_polyline("_izw~A|wdpN")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for lat, lng in result:
            self.assertIsInstance(lat, float)
            self.assertIsInstance(lng, float)

    def test_three_point_polyline(self):
        # Known valid polyline for 3 points (Berlin area)
        result = decode_polyline("_yp_IgdypAgEgEgEgE")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertAlmostEqual(result[0][0], 52.52, places=2)
        self.assertAlmostEqual(result[0][1], 13.405, places=2)

    def test_custom_precision(self):
        result = decode_polyline("_izw~A|wdpN", precision=6)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)


# =============================================================================
# 5. services/cost_engine.py
# =============================================================================

class TestCostEngineEstimate(unittest.TestCase):
    """CostEngineService.estimate with edge cases."""

    def setUp(self):
        # Pass a fixed fuel price to avoid hitting FuelPriceService
        self.engine = CostEngineService(fuel_price_eur_per_liter=1.5)
        self.truck = {"fuel_consumption_l_per_100km": 30.0}

    def test_none_distance_returns_safe_defaults(self):
        result = self.engine.estimate(None, self.truck)  # type: ignore[arg-type]
        self.assertEqual(result["fuel_liters"], 0.0)
        self.assertEqual(result["fuel_cost"], 0.0)
        self.assertEqual(result["toll_cost"], 0.0)
        self.assertEqual(result["total_cost"], 0.0)

    def test_zero_distance_returns_zero_fuel(self):
        result = self.engine.estimate(0, self.truck)
        self.assertEqual(result["fuel_liters"], 0.0)
        self.assertEqual(result["fuel_cost"], 0.0)
        self.assertEqual(result["toll_cost"], 0.0)
        self.assertEqual(result["total_cost"], 0.0)

    def test_valid_inputs_computes_correctly(self):
        result = self.engine.estimate(100.0, self.truck)
        # fuel_liters = (100/100) * 30 = 30
        self.assertAlmostEqual(result["fuel_liters"], 30.0)
        # fuel_cost = 30 * 1.5 = 45
        self.assertAlmostEqual(result["fuel_cost"], 45.0)
        # toll_cost = 100 * 0.22 * 1.0 * 0.5 = 11.0
        self.assertAlmostEqual(result["toll_cost"], 11.0)
        # total = 45 + 11 = 56
        self.assertAlmostEqual(result["total_cost"], 56.0)

    def test_consumption_fallback_to_default(self):
        truck_no_consumption = {}
        result = self.engine.estimate(100.0, truck_no_consumption)
        # Default consumption is 34.0
        self.assertAlmostEqual(result["fuel_liters"], 34.0)

    def test_country_factor_affects_toll(self):
        truck = {"fuel_consumption_l_per_100km": 30.0}
        # France has factor 1.3
        engine = CostEngineService(fuel_price_eur_per_liter=1.5)
        result = engine.estimate(100.0, truck, country_code="FR")
        # toll = 100 * 0.22 * 1.3 * 0.5 = 14.3
        self.assertAlmostEqual(result["toll_cost"], 14.3)

    def test_route_details_road_class_overrides(self):
        truck = {"fuel_consumption_l_per_100km": 30.0}
        result = self.engine.estimate(100.0, truck, route_details={"road_class": 1.0})
        # toll = 100 * 0.22 * 1.0 * 1.0 = 22.0
        self.assertAlmostEqual(result["toll_cost"], 22.0)


# =============================================================================
# 6. services/conflict_service.py
# =============================================================================

class TestTripConflictServiceSameEntity(unittest.TestCase):
    """_same_entity static helper works correctly."""

    def test_same_truck_by_plate(self):
        same_truck, same_driver = TripConflictService._same_entity(
            "B-123-ABC", "B-123-ABC", None, None, None, None
        )
        self.assertTrue(same_truck)
        self.assertFalse(same_driver)

    def test_same_truck_by_id(self):
        same_truck, same_driver = TripConflictService._same_entity(
            "", "", 42, 42, None, None
        )
        self.assertTrue(same_truck)
        self.assertFalse(same_driver)

    def test_different_truck_plate(self):
        same_truck, same_driver = TripConflictService._same_entity(
            "B-123", "B-456", None, None, None, None
        )
        self.assertFalse(same_truck)
        self.assertFalse(same_driver)

    def test_same_driver_by_id(self):
        same_truck, same_driver = TripConflictService._same_entity(
            "", "", None, None, 7, 7
        )
        self.assertFalse(same_truck)
        self.assertTrue(same_driver)

    def test_different_driver_id(self):
        same_truck, same_driver = TripConflictService._same_entity(
            "", "", None, None, 7, 8
        )
        self.assertFalse(same_truck)
        self.assertFalse(same_driver)

    def test_both_same(self):
        same_truck, same_driver = TripConflictService._same_entity(
            "B-123", "B-123", 42, 42, 7, 7
        )
        self.assertTrue(same_truck)
        self.assertTrue(same_driver)

    def test_both_different(self):
        same_truck, same_driver = TripConflictService._same_entity(
            "B-123", "B-456", 42, 43, 7, 8
        )
        self.assertFalse(same_truck)
        self.assertFalse(same_driver)


class TestTripConflictServiceCheckConflicts(unittest.TestCase):
    """check_conflicts with overlapping and non-overlapping trips."""

    def setUp(self):
        self.db = make_db()
        self.service = TripConflictService(self.db)

    def _insert_trip(self, trip_id, start_date, end_date,
                     truck_number="B-100", driver_id=1, status="Planned"):
        self.db.conn.execute(
            """INSERT INTO trips
               (id, truck_number, driver_id, start_date, end_date, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (trip_id, truck_number, driver_id, start_date, end_date, status,
             datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        self.db.conn.commit()

    def test_no_conflicts_when_no_trips(self):
        trip_data = {
            "truck_number": "B-100",
            "driver_id": 1,
            "start_date": "15/06/2026",
            "end_date": "17/06/2026",
        }
        conflicts = self.service.check_conflicts(trip_data)
        self.assertEqual(len(conflicts), 0)

    def test_overlapping_same_truck_detects_conflict(self):
        self._insert_trip(1, "10/06/2026", "20/06/2026",
                          truck_number="B-100", driver_id=1)
        trip_data = {
            "truck_number": "B-100",
            "driver_id": 2,
            "start_date": "15/06/2026",
            "end_date": "25/06/2026",
        }
        conflicts = self.service.check_conflicts(trip_data)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["trip_id"], 1)
        self.assertTrue(conflicts[0]["same_truck"])
        self.assertFalse(conflicts[0]["same_driver"])

    def test_overlapping_same_driver_detects_conflict(self):
        self._insert_trip(1, "10/06/2026", "20/06/2026",
                          truck_number="B-200", driver_id=1)
        trip_data = {
            "truck_number": "B-100",
            "driver_id": 1,
            "start_date": "15/06/2026",
            "end_date": "25/06/2026",
        }
        conflicts = self.service.check_conflicts(trip_data)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["trip_id"], 1)
        self.assertFalse(conflicts[0]["same_truck"])
        self.assertTrue(conflicts[0]["same_driver"])

    def test_non_overlapping_trips_no_conflict(self):
        self._insert_trip(1, "01/06/2026", "05/06/2026",
                          truck_number="B-100", driver_id=1)
        trip_data = {
            "truck_number": "B-100",
            "driver_id": 1,
            "start_date": "10/06/2026",
            "end_date": "15/06/2026",
        }
        conflicts = self.service.check_conflicts(trip_data)
        self.assertEqual(len(conflicts), 0)

    def test_completed_trip_ignored(self):
        self._insert_trip(1, "10/06/2026", "20/06/2026",
                          truck_number="B-100", driver_id=1, status="Delivered")
        trip_data = {
            "truck_number": "B-100",
            "driver_id": 1,
            "start_date": "15/06/2026",
            "end_date": "25/06/2026",
        }
        conflicts = self.service.check_conflicts(trip_data)
        self.assertEqual(len(conflicts), 0)

    def test_self_trip_ignored(self):
        self._insert_trip(1, "10/06/2026", "20/06/2026",
                          truck_number="B-100", driver_id=1)
        trip_data = {
            "id": 1,
            "truck_number": "B-100",
            "driver_id": 1,
            "start_date": "15/06/2026",
            "end_date": "25/06/2026",
        }
        conflicts = self.service.check_conflicts(trip_data)
        self.assertEqual(len(conflicts), 0)

    def test_no_departure_returns_no_conflicts(self):
        trip_data = {
            "truck_number": "B-100",
            "driver_id": 1,
            # No start_date or created_at
        }
        conflicts = self.service.check_conflicts(trip_data)
        self.assertEqual(len(conflicts), 0)

    def test_both_same_truck_and_driver(self):
        self._insert_trip(1, "10/06/2026", "20/06/2026",
                          truck_number="B-100", driver_id=1)
        trip_data = {
            "truck_number": "B-100",
            "driver_id": 1,
            "start_date": "15/06/2026",
            "end_date": "25/06/2026",
        }
        conflicts = self.service.check_conflicts(trip_data)
        self.assertEqual(len(conflicts), 1)
        self.assertTrue(conflicts[0]["same_truck"])
        self.assertTrue(conflicts[0]["same_driver"])


class TestTripConflictServiceAvailability(unittest.TestCase):
    """is_truck_available and is_driver_available helper methods."""

    def setUp(self):
        self.db = make_db()
        self.service = TripConflictService(self.db)

    def _insert_trip(self, trip_id, start_date, end_date,
                     truck_number="B-100", driver_id=1, status="Planned"):
        self.db.conn.execute(
            """INSERT INTO trips
               (id, truck_number, driver_id, start_date, end_date, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (trip_id, truck_number, driver_id, start_date, end_date, status,
             datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        self.db.conn.commit()

    def test_truck_available_with_no_plate_or_id_returns_true(self):
        self.assertTrue(self.service.is_truck_available())

    def test_truck_available_with_conflict(self):
        self._insert_trip(1, "10/06/2026", "20/06/2026",
                          truck_number="B-100")
        self.assertFalse(
            self.service.is_truck_available(
                truck_plate="B-100",
                from_date="15/06/2026",
                to_date="25/06/2026",
            )
        )

    def test_truck_available_no_conflict(self):
        self._insert_trip(1, "01/06/2026", "05/06/2026",
                          truck_number="B-100")
        self.assertTrue(
            self.service.is_truck_available(
                truck_plate="B-100",
                from_date="10/06/2026",
                to_date="15/06/2026",
            )
        )

    def test_driver_available_no_id_returns_true(self):
        self.assertTrue(self.service.is_driver_available(None))  # type: ignore[arg-type]

    def test_driver_available_with_conflict(self):
        self._insert_trip(1, "10/06/2026", "20/06/2026",
                          truck_number="B-100", driver_id=5)
        self.assertFalse(
            self.service.is_driver_available(
                driver_id=5,
                from_date="15/06/2026",
                to_date="25/06/2026",
            )
        )

    def test_driver_available_no_conflict(self):
        self._insert_trip(1, "01/06/2026", "05/06/2026",
                          truck_number="B-100", driver_id=5)
        self.assertTrue(
            self.service.is_driver_available(
                driver_id=5,
                from_date="10/06/2026",
                to_date="15/06/2026",
            )
        )


class TestDescribeConflict(unittest.TestCase):
    def setUp(self):
        self.service = TripConflictService(make_db())

    def test_describe_truck_conflict(self):
        conflict = {
            "same_truck": True,
            "same_driver": False,
            "truck_plate": "B-123",
            "trip_id": 42,
            "driver_name": "",
            "overlap_description": "10/06 - 20/06",
        }
        desc = self.service.describe_conflict(conflict)
        self.assertIn("B-123", desc)
        self.assertIn("TRP-42", desc)
        self.assertIn("10/06", desc)

    def test_describe_driver_conflict(self):
        conflict = {
            "same_truck": False,
            "same_driver": True,
            "truck_plate": "",
            "trip_id": 42,
            "driver_name": "Alice",
            "overlap_description": "10/06 - 20/06",
        }
        desc = self.service.describe_conflict(conflict)
        self.assertIn("Alice", desc)
        self.assertIn("TRP-42", desc)


if __name__ == "__main__":
    unittest.main()
