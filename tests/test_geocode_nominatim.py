"""Tests for geocode_nominatim service."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import services.geocode_nominatim as _gn
from services.geocode_nominatim import (
    RATE_LIMIT_DELAY,
    _apply_rate_limit,
    _last_request_time,
    _rate_lock,
    geocode_batch,
    geocode_place,
)


class TestGeocodePlace:
    def setup_method(self):
        _gn._last_request_time = 0

    @patch("services.geocode_nominatim.requests.get")
    def test_successful_geocode(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"lat": "45.9432", "lon": "24.9668"}]
        mock_get.return_value = mock_resp

        result = geocode_place("Sibiu, Romania")
        assert result == (45.9432, 24.9668)

    @patch("services.geocode_nominatim.requests.get")
    def test_invalid_place_none(self, mock_get):
        assert geocode_place(None) is None
        mock_get.assert_not_called()

    @patch("services.geocode_nominatim.requests.get")
    def test_invalid_place_empty(self, mock_get):
        assert geocode_place("") is None
        mock_get.assert_not_called()

    @patch("services.geocode_nominatim.requests.get")
    def test_no_results(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp

        result = geocode_place("Nowhereland")
        assert result is None

    @patch("services.geocode_nominatim.requests.get")
    def test_network_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Network down")
        result = geocode_place("Sibiu")
        assert result is None

    @patch("services.geocode_nominatim.requests.get")
    def test_timeout_retry(self, mock_get):
        import requests
        mock_get.side_effect = [
            requests.exceptions.Timeout("timeout"),
            MagicMock(status_code=200, json=lambda: [{"lat": "45.0", "lon": "24.0"}]),
        ]
        result = geocode_place("Sibiu", retries=2)
        assert result == (45.0, 24.0)
        assert mock_get.call_count == 2

    @patch("services.geocode_nominatim.requests.get")
    def test_all_retries_exhausted(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("timeout")
        result = geocode_place("Sibiu", retries=1)
        assert result is None
        assert mock_get.call_count == 2  # retries + 1 initial

    @patch("services.geocode_nominatim.requests.get")
    def test_http_429_rate_limit(self, mock_get):
        mock_429 = MagicMock(status_code=429)
        mock_200 = MagicMock(status_code=200, json=lambda: [{"lat": "45.0", "lon": "24.0"}])
        mock_get.side_effect = [mock_429, mock_200]
        with patch("services.geocode_nominatim.time.sleep") as mock_sleep:
            result = geocode_place("Sibiu", retries=2)
            assert result == (45.0, 24.0)

    @patch("services.geocode_nominatim.requests.get")
    def test_too_many_429s_raises(self, mock_get):
        mock_429 = MagicMock(status_code=429)
        mock_get.side_effect = [mock_429, mock_429, mock_429, mock_429]
        with pytest.raises(RuntimeError, match="Nominatim rate limit exceeded"):
            geocode_place("Sibiu", retries=3)

    @patch("services.geocode_nominatim.requests.get")
    def test_null_island_rejected(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"lat": "0.0", "lon": "0.0"}]
        mock_get.return_value = mock_resp

        result = geocode_place("Null Island")
        assert result is None

    @patch("services.geocode_nominatim.requests.get")
    def test_invalid_coordinates_rejected(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"lat": "999", "lon": "999"}]
        mock_get.return_value = mock_resp

        result = geocode_place("Invalid")
        assert result is None

    @patch("services.geocode_nominatim.requests.get")
    def test_request_headers_set(self, mock_get):
        mock_resp = MagicMock(status_code=200, json=lambda: [{"lat": "45.0", "lon": "24.0"}])
        mock_get.return_value = mock_resp

        geocode_place("Sibiu")
        _, kwargs = mock_get.call_args
        assert "User-Agent" in kwargs["headers"]
        assert kwargs["headers"]["User-Agent"] == "logistics-app/1.0"
        assert kwargs["params"]["format"] == "json"
        assert kwargs["params"]["limit"] == 1


class TestRateLimiting:
    def test_rate_limit_applied(self):
        with patch("services.geocode_nominatim._last_request_time", time.time()), \
             patch("services.geocode_nominatim.time.sleep") as mock_sleep:
            _apply_rate_limit()
            mock_sleep.assert_called_once()

    def test_rate_limit_not_needed(self):
        with patch("services.geocode_nominatim._last_request_time", 0), \
             patch("services.geocode_nominatim.time.sleep") as mock_sleep, \
             patch("services.geocode_nominatim.time.time", return_value=10.0):
            _apply_rate_limit()
            mock_sleep.assert_not_called()


class TestGeocodeBatch:
    def setup_method(self):
        _gn._last_request_time = 0

    @patch("services.geocode_nominatim.geocode_place")
    def test_batch_all_successful(self, mock_geocode):
        mock_geocode.side_effect = [(45.0, 24.0), (46.0, 25.0)]
        results = geocode_batch(["Sibiu", "Cluj"])
        assert results == [(45.0, 24.0), (46.0, 25.0)]
        assert mock_geocode.call_count == 2

    @patch("services.geocode_nominatim.geocode_place")
    def test_batch_with_failures_skip(self, mock_geocode):
        mock_geocode.side_effect = [(45.0, 24.0), None, (46.0, 25.0)]
        results = geocode_batch(["Sibiu", "Nowhere", "Cluj"], skip_failed=True)
        assert results == [(45.0, 24.0), None, (46.0, 25.0)]

    @patch("services.geocode_nominatim.geocode_place")
    def test_batch_with_failures_raises(self, mock_geocode):
        mock_geocode.side_effect = [(45.0, 24.0), None]
        with pytest.raises(ValueError, match="Geocoding failed for"):
            geocode_batch(["Sibiu", "Nowhere"], skip_failed=False)
