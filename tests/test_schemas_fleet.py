"""Tests for backend/schemas/fleet.py — TruckBase, TruckResponse, GpsPing, GpsPosition."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.fleet import GpsPing, GpsPosition, TruckBase, TruckResponse


# ── TruckBase ─────────────────────────────────────────────────────────────────


class TestTruckBase:
    """plate, brand have defaults; year int; extra="forbid"."""

    def test_defaults(self):
        inst = TruckBase()
        assert inst.plate == ""
        assert inst.brand == ""
        assert inst.year == 0

    def test_all_fields(self):
        inst = TruckBase(plate="AB-123-CD", brand="Volvo", year=2022)
        assert inst.plate == "AB-123-CD"
        assert inst.year == 2022

    def test_year_negative(self):
        """No constraint — any int is accepted."""
        inst = TruckBase(year=-1)
        assert inst.year == -1

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            TruckBase(plate="x", unknown="y")  # type: ignore[call-arg]


# ── TruckResponse ─────────────────────────────────────────────────────────────


class TestTruckResponse:
    """Extends TruckBase, adds id (required), is_active (default True)."""

    def test_valid(self):
        inst = TruckResponse(id=1)
        assert inst.id == 1
        assert inst.is_active is True
        assert inst.plate == ""

    def test_all_fields(self):
        inst = TruckResponse(id=1, plate="AB-123", brand="Scania", year=2021, is_active=False)
        assert inst.plate == "AB-123"
        assert inst.is_active is False

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            TruckResponse()  # type: ignore[call-arg]

    def test_extra_field_ignored(self):
        """extra="ignore"."""
        inst = TruckResponse(id=1, unknown="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "unknown")


# ── GpsPing ───────────────────────────────────────────────────────────────────


class TestGpsPing:
    """truck_id (required), latitude (required), longitude (required), speed/heading defaults, driver_id optional."""

    def test_required_only(self):
        inst = GpsPing(truck_id=1, latitude=48.8566, longitude=2.3522)
        assert inst.truck_id == 1
        assert inst.latitude == 48.8566
        assert inst.longitude == 2.3522
        assert inst.speed_kmh == 0.0
        assert inst.heading == 0
        assert inst.timestamp == ""
        assert inst.driver_id is None

    def test_all_fields(self):
        inst = GpsPing(
            truck_id=1, latitude=48.8566, longitude=2.3522,
            speed_kmh=65.5, heading=90, timestamp="2025-01-01T12:00:00Z", driver_id=5,
        )
        assert inst.speed_kmh == 65.5
        assert inst.heading == 90
        assert inst.driver_id == 5

    def test_missing_truck_id_raises(self):
        with pytest.raises(ValidationError):
            GpsPing(latitude=0.0, longitude=0.0)  # type: ignore[call-arg]

    def test_missing_latitude_raises(self):
        with pytest.raises(ValidationError):
            GpsPing(truck_id=1, longitude=0.0)  # type: ignore[call-arg]

    def test_missing_longitude_raises(self):
        with pytest.raises(ValidationError):
            GpsPing(truck_id=1, latitude=0.0)  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            GpsPing(truck_id=1, latitude=0.0, longitude=0.0, extra="x")  # type: ignore[call-arg]


# ── GpsPosition ───────────────────────────────────────────────────────────────


class TestGpsPosition:
    """Similar to GpsPing but uses recorded_at instead of timestamp."""

    def test_required_only(self):
        inst = GpsPosition(truck_id=1, latitude=48.8566, longitude=2.3522)
        assert inst.truck_id == 1
        assert inst.recorded_at == ""
        assert inst.driver_id is None

    def test_all_fields(self):
        inst = GpsPosition(
            truck_id=1, latitude=48.8566, longitude=2.3522,
            speed_kmh=50.0, heading=180, recorded_at="2025-01-01T12:00:00Z", driver_id=3,
        )
        assert inst.heading == 180
        assert inst.recorded_at == "2025-01-01T12:00:00Z"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            GpsPosition(truck_id=1, latitude=0.0)  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            GpsPosition(truck_id=1, latitude=0.0, longitude=0.0, bad="x")  # type: ignore[call-arg]
