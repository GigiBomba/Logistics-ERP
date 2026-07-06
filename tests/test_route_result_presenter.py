"""Tests for route_result_presenter module."""
from unittest.mock import MagicMock, patch

import pytest

from services.route_result_presenter import (
    extract_route_from_result,
    format_duration_minutes,
    format_history_loaded_info,
    format_success_info,
    parse_error_message,
)
from services.i18n import t


class TestFormatDuration:
    def test_zero_minutes(self):
        result = format_duration_minutes(0)
        assert "0" in result
        assert t("result.minutes") in result

    def test_minutes_only(self):
        result = format_duration_minutes(45)
        assert "45" in result

    def test_hours_and_minutes(self):
        result = format_duration_minutes(90)
        assert "hour" in result
        assert "30" in result or "1" in result

    def test_days_and_hours(self):
        result = format_duration_minutes(1500)
        assert "day" in result
        assert "hour" in result

    def test_negative(self):
        result = format_duration_minutes(-30)
        assert "0" in result  # abs ensures positive

    def test_none(self):
        result = format_duration_minutes(None)
        assert "0" in result


class TestFormatSuccessInfo:
    @patch("services.route_result_presenter.t")
    def test_format_success_info_basic(self, mock_t):
        mock_t.side_effect = lambda k: k
        route = {"distance_km": 150.0, "duration_min": 120.0}
        cost_info = {"fuel_liters": 50, "fuel_cost": 100}

        result = format_success_info(route, cost_info, 2)
        assert "result.distance" in result
        assert "result.duration" in result
        assert "result.stops" in result
        assert "result.fuel" in result

    def test_format_success_info_cached(self):
        route = {"distance_km": 100.0, "duration_min": 60.0, "cached": True}
        cost_info = {"fuel_liters": 30}

        with patch("services.route_result_presenter.t") as mock_t:
            mock_t.side_effect = lambda k: k
            result = format_success_info(route, cost_info, 2)
            assert "cached" in result

    def test_format_success_info_with_currency_conversion(self):
        route = {"distance_km": 100.0, "duration_min": 60.0}
        cost_info = {"fuel_liters": 30, "fuel_cost": 100}

        with patch("services.route_result_presenter.t") as mock_t, \
             patch("services.exchange_rate_service.ExchangeRateService") as mock_er:
            mock_t.side_effect = lambda k: k
            mock_er_instance = MagicMock()
            mock_er_instance.convert.return_value = 500.0
            mock_er.return_value = mock_er_instance

            result = format_success_info(route, cost_info, 2, preferred_currency="RON")
            assert "500" in result or "result.fuel_cost" in result


class TestFormatHistoryLoadedInfo:
    @patch("services.route_result_presenter.t")
    def test_format_history_loaded(self, mock_t):
        mock_t.side_effect = lambda k: k
        record = MagicMock()
        record.duration_min = 120.0
        record.total_distance_km = 150.0

        result = format_history_loaded_info(record)
        assert "result.history_loaded" in result
        assert "result.distance" in result
        assert "result.duration" in result


class TestParseErrorMessage:
    def test_not_an_error_dict(self):
        assert parse_error_message({"data": 42}) is None
        assert parse_error_message([]) is None
        assert parse_error_message(None) is None

    def test_timeout_error(self):
        result = parse_error_message({"error": "timeout", "error_type": "timeout"})
        assert result is not None
        assert "timeout" in result[0].lower() or "result.timeout_error" in result[0]

    def test_geocode_error(self):
        result = parse_error_message({"error": "geocode failed", "error_type": "geocode"})
        assert result is not None

    def test_connection_refused(self):
        result = parse_error_message({"error": "Connection refused", "error_type": "connection"})
        assert result is not None

    def test_invalid_coordinates(self):
        result = parse_error_message({"error": "Invalid coordinates", "error_type": "validation"})
        assert result is not None

    def test_route_not_found(self):
        result = parse_error_message({"error": "not found", "error_type": "route"})
        assert result is not None

    def test_at_least_2_stops(self):
        result = parse_error_message({"error": "at least 2 stops required"})
        assert result is not None

    def test_duplicate_stops(self):
        result = parse_error_message({"error": "duplicate stops"})
        assert result is not None

    def test_generic_error(self):
        result = parse_error_message({"error": "something broke"})
        assert result is not None


class TestExtractRouteFromResult:
    def test_extract_from_list(self):
        result = [{"distance_km": 100.0}]
        route = extract_route_from_result(result)
        assert route == {"distance_km": 100.0}

    def test_extract_from_empty_list(self):
        assert extract_route_from_result([]) is None

    def test_extract_from_non_list(self):
        assert extract_route_from_result({"error": "fail"}) is None

    def test_extract_from_none(self):
        assert extract_route_from_result(None) is None
