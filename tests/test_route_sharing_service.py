"""Tests for route_sharing_service module."""
from __future__ import annotations

import json
import zlib
from unittest.mock import MagicMock, patch

import pytest

from services.route_sharing_service import (
    OPERIONROUTE_MAGIC,
    OPERIONROUTE_VERSION,
    SHARE_URL_BASE,
    _extract_coordinate_pairs,
    build_google_maps_url,
    build_share_url,
    decode_route_file,
    encode_route_file,
    extract_stops_from_route_result,
    extract_stops_from_state,
    is_share_url,
    parse_share_url,
)


class TestBuildShareUrl:
    def test_build_share_url_basic(self):
        stops = [
            {"lat": 45.9432, "lon": 24.9668},
            {"lat": 46.7712, "lon": 23.6236},
        ]
        url = build_share_url(stops)
        assert url.startswith(SHARE_URL_BASE)
        assert "stops=" in url
        assert "v=1" in url

    def test_build_share_url_with_options(self):
        stops = [{"lat": 45.0, "lon": 24.0}, {"lat": 46.0, "lon": 25.0}]
        url = build_share_url(stops, profile="fastest", truck_id="42", truck_label="AB123CD")
        assert "profile=fastest" in url
        assert "truck_id=42" in url
        assert "truck_label=AB123CD" in url

    def test_build_share_url_no_coords_returns_base(self):
        url = build_share_url([])
        assert url == SHARE_URL_BASE + "?v=1&stops="

    def test_build_share_url_precision(self):
        stops = [{"lat": 45.94321234, "lon": 24.96685678}]
        url = build_share_url(stops)
        # Should round to 5 decimal places
        assert "45.94321" in url
        assert "24.96686" in url


class TestParseShareUrl:
    def test_parse_share_url_basic(self):
        url = f"{SHARE_URL_BASE}?v=1&stops=45.94320,24.96680&profile=fastest"
        result = parse_share_url(url)
        assert len(result["stops"]) == 1
        assert result["stops"][0] == (45.9432, 24.9668)
        assert result["profile"] == "fastest"

    def test_parse_share_url_multiple_stops(self):
        url = f"{SHARE_URL_BASE}?v=1&stops=45.0,24.0;46.0,25.0"
        result = parse_share_url(url)
        assert len(result["stops"]) == 2

    def test_parse_share_url_malformed_pair_skipped(self):
        url = f"{SHARE_URL_BASE}?v=1&stops=45.0,24.0;bad,data;46.0,25.0"
        result = parse_share_url(url)
        assert len(result["stops"]) == 2  # malformed pair skipped

    def test_parse_share_url_no_stops(self):
        result = parse_share_url(f"{SHARE_URL_BASE}?v=1")
        assert result["stops"] == []

    def test_parse_share_url_with_all_params(self):
        url = f"{SHARE_URL_BASE}?v=1&stops=45.0,24.0&profile=eco&truck_id=1&truck_label=AB123CD"
        result = parse_share_url(url)
        assert result["truck_id"] == "1"
        assert result["truck_label"] == "AB123CD"


class TestIsShareUrl:
    def test_is_share_url_match(self):
        assert is_share_url("https://operion.app/route?stops=...") is True

    def test_is_share_url_operion_scheme(self):
        assert is_share_url("operion://app/route?stops=...") is True

    def test_is_share_url_no_match(self):
        assert is_share_url("https://google.com") is False

    def test_is_share_url_blank(self):
        assert is_share_url("") is False


class TestBuildGoogleMapsUrl:
    def test_build_basic(self):
        url = build_google_maps_url((45.0, 24.0), (46.0, 25.0))
        assert url.startswith("https://www.google.com/maps/dir/")
        assert "api=1" in url
        assert "origin=45.00000,24.00000" in url
        assert "destination=46.00000,25.00000" in url
        assert "travelmode=driving" in url

    def test_with_waypoints(self):
        url = build_google_maps_url(
            (45.0, 24.0), (46.0, 25.0),
            waypoints=[(45.5, 24.5)],
        )
        assert "waypoints=" in url

    def test_with_custom_travel_mode(self):
        url = build_google_maps_url((45.0, 24.0), (46.0, 25.0), travel_mode="walking")
        assert "travelmode=walking" in url

    def test_invalid_travel_mode_falls_back(self):
        url = build_google_maps_url((45.0, 24.0), (46.0, 25.0), travel_mode="flying")
        assert "travelmode=driving" in url


class TestEncodeDecodeRouteFile:
    def test_encode_decode_roundtrip(self):
        stops = [
            {"lat": 45.0, "lon": 24.0},
            {"lat": 46.0, "lon": 25.0},
        ]
        data = encode_route_file(
            stops=stops,
            profile="fastest",
            truck_id="42",
            truck_label="AB123CD",
            distance_km=150.0,
            duration_min=120.0,
        )

        assert data[:13] == OPERIONROUTE_MAGIC + bytes([OPERIONROUTE_VERSION])

        decoded = decode_route_file(data)
        assert len(decoded["stops"]) == 2
        assert decoded["stops"][0] == (45.0, 24.0)
        assert decoded["profile"] == "fastest"
        assert decoded["truck_id"] == "42"
        assert decoded["distance_km"] == 150.0
        assert decoded["duration_min"] == 120.0

    def test_decode_invalid_too_short(self):
        with pytest.raises(ValueError, match="too short"):
            decode_route_file(b"too short")

    def test_decode_invalid_magic(self):
        data = b"X" * 13 + b"\x00\x00\x00\x00"
        with pytest.raises(ValueError, match="bad magic"):
            decode_route_file(data)

    def test_decode_corrupt_payload(self):
        header = OPERIONROUTE_MAGIC + bytes([OPERIONROUTE_VERSION])
        header += (4).to_bytes(4, byteorder="big")
        data = header + b"corrupt"
        with pytest.raises(ValueError, match="decompression"):
            decode_route_file(data)

    def test_encode_with_metadata(self):
        stops = [{"lat": 45.0, "lon": 24.0}]
        data = encode_route_file(stops, metadata={"source": "test"})
        decoded = decode_route_file(data)
        assert decoded["metadata"] == {"source": "test"}


class TestExtractStops:
    def test_from_route_result(self):
        route = {"stops": [(45.0, 24.0), (46.0, 25.0)]}
        stops = extract_stops_from_route_result(route)
        assert len(stops) == 2
        assert stops[0]["type"] == "start"
        assert stops[1]["type"] == "destination"

    def test_from_state(self):
        stops_state = [
            {"lat": 45.0, "lon": 24.0, "type": "start"},
            {"lat": 46.0, "lon": 25.0, "type": "stop"},
            {},  # unresolved - should be skipped
        ]
        result = extract_stops_from_state(stops_state)
        assert len(result) == 2

    def test_extract_coordinate_pairs(self):
        stops = [
            {"lat": 45.0, "lon": 24.0},
            {"lat": 46.0, "lng": 25.0},  # uses 'lng' as fallback
        ]
        result = _extract_coordinate_pairs(stops)
        assert result == [(45.0, 24.0), (46.0, 25.0)]
