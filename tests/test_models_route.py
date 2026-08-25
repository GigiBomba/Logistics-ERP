"""Tests for route_models.py — Route stops, lat/lon bounds, profile enum, required fields."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from models.route_models import RouteStop, RouteCalculateRequest, RouteResult


class TestRouteStop:
    @pytest.mark.parametrize(
        "address, lat, lon, sequence, stop_type",
        [
            ("Str. Victoriei 10", 45.7489, 21.2087, 0, "start"),
            ("Str. Libertatii 5", 45.7500, 21.2100, 1, "pickup"),
            ("Str. Unirii 20", None, None, 2, "delivery"),
            ("Autostrada A1 km 50", 44.3269, 23.7890, 3, "waypoint"),
            ("Str. Mihai Viteazu 1", 46.7712, 23.5906, 4, "end"),
        ],
    )
    def test_route_stop_valid(self, address, lat, lon, sequence, stop_type):
        s = RouteStop(address=address, lat=lat, lon=lon, sequence=sequence, type=stop_type)
        assert s.address == address
        assert s.lat == lat
        assert s.lon == lon
        assert s.sequence == sequence
        assert s.type == stop_type

    def test_route_stop_default_type(self):
        s = RouteStop(address="Somewhere")
        assert s.type == "waypoint"
        assert s.lat is None
        assert s.lon is None
        assert s.sequence == 0


class TestRouteCalculateRequest:
    def test_valid_two_stops(self):
        stops = [
            RouteStop(address="A", lat=45.0, lon=21.0, type="start"),
            RouteStop(address="B", lat=46.0, lon=22.0, type="end"),
        ]
        r = RouteCalculateRequest(stops=stops)
        assert len(r.stops) == 2
        assert r.vehicle_profile == "truck"
        assert r.optimize is True
        assert r.return_geometry is True

    def test_valid_multiple_stops(self):
        stops = [
            RouteStop(address="Start", type="start"),
            RouteStop(address="Pickup", type="pickup"),
            RouteStop(address="Drop", type="delivery"),
            RouteStop(address="End", type="end"),
        ]
        r = RouteCalculateRequest(stops=stops, vehicle_profile="car", avoid_tolls=True)
        assert r.vehicle_profile == "car"
        assert r.avoid_tolls is True

    @pytest.mark.parametrize(
        "num_stops",
        [0, 1],
    )
    def test_less_than_two_stops_raises(self, num_stops):
        stops = [RouteStop(address=f"Stop{i}") for i in range(num_stops)]
        with pytest.raises(ValidationError, match="at least 2 stops"):
            RouteCalculateRequest(stops=stops)

    @pytest.mark.parametrize(
        "profile",
        ["truck", "car", "bike"],
    )
    def test_profile_accepted(self, profile):
        stops = [RouteStop(address="A"), RouteStop(address="B")]
        r = RouteCalculateRequest(stops=stops, vehicle_profile=profile)
        assert r.vehicle_profile == profile

    def test_country_exclusions(self):
        stops = [RouteStop(address="A"), RouteStop(address="B")]
        r = RouteCalculateRequest(
            stops=stops,
            country_exclusions=["HU", "BG"],
            avoid_highways=True,
            return_geometry=False,
        )
        assert r.country_exclusions == ["HU", "BG"]
        assert r.avoid_highways is True
        assert r.return_geometry is False


class TestRouteResult:
    def test_route_result_minimal(self):
        r = RouteResult(distance_km=150.5, duration_minutes=120.0)
        assert r.id is None
        assert r.polyline is None
        assert r.waypoints == []
        assert r.toll_cost_eur == 0.0
        assert r.fuel_cost_eur == 0.0
        assert r.total_cost_eur == 0.0

    def test_route_result_with_all_fields(self):
        wp = [RouteStop(address="WP1"), RouteStop(address="WP2")]
        r = RouteResult(
            id=42,
            distance_km=320.0,
            duration_minutes=240.0,
            polyline="abc123",
            waypoints=wp,
            toll_cost_eur=15.5,
            fuel_cost_eur=85.3,
            total_cost_eur=100.8,
        )
        assert r.id == 42
        assert r.polyline == "abc123"
        assert len(r.waypoints) == 2
        assert r.total_cost_eur == 100.8
