"""Comprehensive tests for the public route-demo API endpoint.

Tests cover:

*   ``_calculate_costs`` — pure-function cost computation
*   ``calculate_route_demo`` (POST /route-demo/calculate) — public endpoint
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.v1.route_demo import _calculate_costs


# ======================================================================
# _calculate_costs  (pure function)
# ======================================================================

class TestCalculateCosts:
    """_calculate_costs() — computes cost metrics from distance and duration."""

    def test_returns_all_expected_keys(self):
        """The result dict contains all expected cost keys."""
        result = _calculate_costs(1000.0, 540.0)  # 1000 km, 9 h
        expected_keys = {
            "distance_km", "duration_hours",
            "fuelCost", "tollCost", "salaryCost", "extraCosts",
            "totalCost", "profit",
        }
        assert set(result.keys()) == expected_keys

    def test_no_surplus_keys(self):
        """No extra keys like 'days' leak into the result."""
        result = _calculate_costs(500.0, 300.0)
        assert "days" not in result

    # ── Known values smoke test ──────────────────────────────────────

    def test_known_values(self):
        """With 1000 km / 540 min (9 h), each field matches the expected formula.

        Calculations:
            hours         = 540 / 60        = 9.0
            days          = max(1, ceil(9/9)) = 1
            fuelCost      = (1000/100)*32*1.65 = 528 → round = 528
            tollCost      = 1000 * 0.22     = 220 → round = 220
            salaryCost    = 1 * 100         = 100
            extraCosts    = 1000*0.03 + 1*12 = 42 → round = 42
            totalCost     = 528 + 220 + 100 + 42 = 890
            profit        = 1000*1.5 - 890  = 610
        """
        result = _calculate_costs(1000.0, 540.0)
        assert result["distance_km"] == 1000.0
        assert result["duration_hours"] == 9.0
        assert result["fuelCost"] == 528
        assert result["tollCost"] == 220
        assert result["salaryCost"] == 100
        assert result["extraCosts"] == 42
        assert result["totalCost"] == 890
        assert result["profit"] == 610

    # ── Rounding behaviour ───────────────────────────────────────────

    def test_distance_km_rounded_to_one_decimal(self):
        """distance_km is rounded to 1 decimal place."""
        result = _calculate_costs(1050.55, 600.0)
        # Python's round uses banker's rounding: 1050.55 → 1050.5 (not 1050.6)
        assert result["distance_km"] == 1050.5

    def test_duration_hours_rounded_to_one_decimal(self):
        """duration_hours is rounded to 1 decimal place."""
        result = _calculate_costs(1000.0, 605.0)  # 10.0833… h
        assert result["duration_hours"] == 10.1

    def test_fuel_cost_rounded_to_integer(self):
        """fuelCost is rounded (banker's / built-in round) to an integer."""
        result = _calculate_costs(100.0, 300.0)
        # (100/100)*32*1.65 = 52.8 → round = 53
        assert result["fuelCost"] == 53

    def test_toll_cost_rounded_to_integer(self):
        """tollCost is rounded to an integer."""
        result = _calculate_costs(17.0, 120.0)
        # 17 * 0.22 = 3.74 → round = 4
        assert result["tollCost"] == 4

    # ── Short routes (duration < 9 h) ────────────────────────────────

    def test_short_route_days_is_one(self):
        """When duration is less than 9 h, days is set to 1."""
        result = _calculate_costs(50.0, 120.0)  # 2 h
        # salaryCost = 1 * 100 = 100
        assert result["salaryCost"] == 100
        # extraCosts = 50*0.03 + 1*12 = 1.5 + 12 = 13.5 → round = 14
        assert result["extraCosts"] == 14

    def test_exactly_9h_days_is_one(self):
        """Exactly 9 hours → days = 1."""
        result = _calculate_costs(100.0, 540.0)
        assert result["salaryCost"] == 100  # 1 * 100

    def test_slightly_over_9h_days_is_two(self):
        """A bit more than 9 h → days = ceil(9.1/9) = 2."""
        result = _calculate_costs(100.0, 546.0)  # 9.1 h
        assert result["salaryCost"] == 200  # 2 * 100

    # ── Zero / edge cases ────────────────────────────────────────────

    def test_zero_distance(self):
        """Zero distance still produces valid (zero) costs."""
        result = _calculate_costs(0.0, 60.0)
        assert result["distance_km"] == 0.0
        assert result["fuelCost"] == 0
        assert result["tollCost"] == 0
        assert result["salaryCost"] == 100  # still 1 day minimum
        assert result["totalCost"] > 0
        assert result["profit"] < 0  # revenue = 0, costs > 0

    def test_zero_duration(self):
        """Zero duration → hours = 0.0, days = 1."""
        result = _calculate_costs(100.0, 0.0)
        assert result["duration_hours"] == 0.0
        assert result["salaryCost"] == 100  # max(1, ceil(0/9)) = 1

    def test_large_values_no_overflow(self):
        """Large distances / durations produce sensible numeric results (no NaN/Inf)."""
        import math
        result = _calculate_costs(99999.9, 99999.0)
        assert result["distance_km"] == 99999.9  # round(99999.9, 1) = 99999.9
        assert result["duration_hours"] == 1666.7  # 99999/60 = 1666.65 → 1666.7
        assert math.isfinite(result["fuelCost"])
        assert math.isfinite(result["tollCost"])
        assert math.isfinite(result["salaryCost"])
        assert math.isfinite(result["extraCosts"])
        assert math.isfinite(result["totalCost"])
        assert math.isfinite(result["profit"])
        assert result["totalCost"] > 0


# ======================================================================
# calculate_route_demo  (POST /route-demo/calculate)
# ======================================================================

class TestCalculateRouteDemoEndpoint:
    """POST /api/v1/route-demo/calculate — public route cost estimation."""

    BASE = "/api/v1/route-demo/calculate"

    # ── Success path ──────────────────────────────────────────────────

    def test_success_returns_standard_and_optimized(self, app):
        """On success both 'standard' and 'optimized' cost objects are returned."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo, \
             patch("backend.services.route_service.GraphHopperClient") as mock_gh_cls:

            # Geocoding: Berlin → (52.52, 13.405), Paris → (48.8566, 2.3522)
            mock_geo.side_effect = [
                (52.52, 13.405),
                (48.8566, 2.3522),
            ]

            mock_gh = MagicMock()
            mock_gh.route.side_effect = [
                {"distance_km": 1050.5, "duration_min": 720.0},   # standard
                {"distance_km": 980.2, "duration_min": 660.0},    # optimized
            ]
            mock_gh_cls.return_value = mock_gh

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "Berlin", "destination": "Paris"},
            )

            assert resp.status_code == 200
            data = resp.json()
            assert "standard" in data
            assert "optimized" in data

            std = data["standard"]
            assert std["distance_km"] == 1050.5
            assert std["duration_hours"] == 12.0  # 720 / 60

            opt = data["optimized"]
            assert opt["distance_km"] == 980.2
            assert opt["duration_hours"] == 11.0  # 660 / 60

            # Verify GraphHopperClient was called with correct profiles
            assert mock_gh.route.call_count == 2
            calls = mock_gh.route.call_args_list
            assert calls[0][1]["profile"] == "truck"
            assert calls[1][1]["profile"] == "truck_fast"

    def test_success_response_contains_all_cost_keys(self, app):
        """Both cost objects include all expected cost metrics."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo, \
             patch("backend.services.route_service.GraphHopperClient") as mock_gh_cls:

            mock_geo.side_effect = [(52.52, 13.405), (48.8566, 2.3522)]
            mock_gh = MagicMock()
            mock_gh.route.return_value = {"distance_km": 500.0, "duration_min": 360.0}
            mock_gh_cls.return_value = mock_gh

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "Berlin", "destination": "Munich"},
            )

            assert resp.status_code == 200
            cost_keys = {
                "distance_km", "duration_hours", "fuelCost", "tollCost",
                "salaryCost", "extraCosts", "totalCost", "profit",
            }
            assert set(resp.json()["standard"].keys()) == cost_keys
            assert set(resp.json()["optimized"].keys()) == cost_keys

    # ── Validation: missing / empty fields ────────────────────────────

    def test_missing_origin_returns_400(self, app):
        """When origin is missing, returns 400."""
        client = TestClient(app)
        resp = client.post(
            self.BASE,
            json={"destination": "Paris"},
        )
        assert resp.status_code == 400
        assert "origin and destination" in resp.json()["detail"]

    def test_missing_destination_returns_400(self, app):
        """When destination is missing, returns 400."""
        client = TestClient(app)
        resp = client.post(
            self.BASE,
            json={"origin": "Berlin"},
        )
        assert resp.status_code == 400
        assert "origin and destination" in resp.json()["detail"]

    def test_empty_origin_returns_400(self, app):
        """When origin is an empty string after strip, returns 400."""
        client = TestClient(app)
        resp = client.post(
            self.BASE,
            json={"origin": "  ", "destination": "Paris"},
        )
        assert resp.status_code == 400

    def test_empty_destination_returns_400(self, app):
        """When destination is an empty string after strip, returns 400."""
        client = TestClient(app)
        resp = client.post(
            self.BASE,
            json={"origin": "Berlin", "destination": ""},
        )
        assert resp.status_code == 400

    def test_both_missing_returns_400(self, app):
        """When both fields are missing, returns 400."""
        client = TestClient(app)
        resp = client.post(self.BASE, json={})
        assert resp.status_code == 400

    # ── Geocoding failures ───────────────────────────────────────────

    def test_origin_geocoding_returns_none(self, app):
        """When ``geocode_place`` returns None for origin, returns 400."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo:
            mock_geo.side_effect = [None, (48.8566, 2.3522)]

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "Atlantis", "destination": "Paris"},
            )
            assert resp.status_code == 400
            assert "geocode origin" in resp.json()["detail"].lower()

    def test_destination_geocoding_returns_none(self, app):
        """When ``geocode_place`` returns None for destination, returns 400."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo:
            mock_geo.side_effect = [(52.52, 13.405), None]

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "Berlin", "destination": "El Dorado"},
            )
            assert resp.status_code == 400
            assert "geocode destination" in resp.json()["detail"].lower()

    def test_origin_geocoding_raises_exception(self, app):
        """When ``geocode_place`` throws for origin, returns 400 with details."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo:
            mock_geo.side_effect = [RuntimeError("Nominatim timeout"), None]

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "Nowhere", "destination": "Paris"},
            )
            assert resp.status_code == 400
            assert "geocoding failed" in resp.json()["detail"].lower()

    def test_destination_geocoding_raises_exception(self, app):
        """When ``geocode_place`` throws for destination, returns 400 with details."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo:
            mock_geo.side_effect = [(52.52, 13.405), RuntimeError("HTTP 429")]

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "Berlin", "destination": "Faraway"},
            )
            assert resp.status_code == 400
            assert "geocoding failed" in resp.json()["detail"].lower()

    # ── GraphHopper failures ─────────────────────────────────────────

    def test_standard_route_fails_returns_502(self, app):
        """When the standard (truck) route call fails, returns 502."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo, \
             patch("backend.services.route_service.GraphHopperClient") as mock_gh_cls:

            mock_geo.side_effect = [(52.52, 13.405), (48.8566, 2.3522)]
            mock_gh = MagicMock()
            mock_gh.route.side_effect = [
                RuntimeError("GraphHopper returned 500"),
                # optimized shouldn't be reached
            ]
            mock_gh_cls.return_value = mock_gh

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "Berlin", "destination": "Paris"},
            )
            assert resp.status_code == 502
            assert "standard" in resp.json()["detail"].lower()

    def test_optimized_route_fails_returns_502(self, app):
        """When the optimized (truck_fast) route call fails, returns 502."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo, \
             patch("backend.services.route_service.GraphHopperClient") as mock_gh_cls:

            mock_geo.side_effect = [(52.52, 13.405), (48.8566, 2.3522)]
            mock_gh = MagicMock()
            mock_gh.route.side_effect = [
                {"distance_km": 1000.0, "duration_min": 600.0},  # standard succeeds
                RuntimeError("Truck fast unavailable"),           # optimized fails
            ]
            mock_gh_cls.return_value = mock_gh

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "Berlin", "destination": "Paris"},
            )
            assert resp.status_code == 502
            assert "optimized" in resp.json()["detail"].lower()

    def test_both_routes_fail_returns_first_502(self, app):
        """When both routes fail, the first error (standard) is raised as 502."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo, \
             patch("backend.services.route_service.GraphHopperClient") as mock_gh_cls:

            mock_geo.side_effect = [(52.52, 13.405), (48.8566, 2.3522)]
            mock_gh = MagicMock()
            mock_gh.route.side_effect = RuntimeError("Network error")
            mock_gh_cls.return_value = mock_gh

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "Berlin", "destination": "Paris"},
            )
            assert resp.status_code == 502

    # ── No auth required ─────────────────────────────────────────────

    def test_no_auth_required(self, app):
        """The route-demo endpoint is public and returns 200 without any auth token."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo, \
             patch("backend.services.route_service.GraphHopperClient") as mock_gh_cls:

            mock_geo.side_effect = [(52.52, 13.405), (48.8566, 2.3522)]
            mock_gh = MagicMock()
            mock_gh.route.return_value = {"distance_km": 100.0, "duration_min": 60.0}
            mock_gh_cls.return_value = mock_gh

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "A", "destination": "B"},
            )
            assert resp.status_code == 200

    # ── Verify a complete end-to-end calculation ─────────────────────

    def test_costs_computed_correctly(self, app):
        """Verify the calculated costs with known geocoding and route data."""
        with patch("services.geocode_nominatim.geocode_place") as mock_geo, \
             patch("backend.services.route_service.GraphHopperClient") as mock_gh_cls:

            mock_geo.side_effect = [(52.52, 13.405), (48.8566, 2.3522)]
            mock_gh = MagicMock()
            mock_gh.route.return_value = {"distance_km": 1000.0, "duration_min": 540.0}
            mock_gh_cls.return_value = mock_gh

            client = TestClient(app)
            resp = client.post(
                self.BASE,
                json={"origin": "Berlin", "destination": "Paris"},
            )

            assert resp.status_code == 200
            data = resp.json()
            # Both standard and optimized get the same mock route result here
            for key in ("standard", "optimized"):
                costs = data[key]
                assert costs["distance_km"] == 1000.0
                assert costs["duration_hours"] == 9.0
                assert costs["fuelCost"] == 528   # (1000/100)*32*1.65 ≈ 528
                assert costs["tollCost"] == 220   # 1000 * 0.22
                assert costs["salaryCost"] == 100  # 1 day
                assert costs["extraCosts"] == 42   # 1000*0.03 + 1*12 = 42
                assert costs["totalCost"] == 890   # 528+220+100+42
                assert costs["profit"] == 610       # 1500 - 890
