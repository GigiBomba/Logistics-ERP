"""Tests for dispatch_models.py — Dispatch create, truck/driver assignment validation, status fields."""
from __future__ import annotations

import pytest
from datetime import datetime
from pydantic import ValidationError
from models.dispatch_models import (
    DispatchCreate,
    DispatchAssign,
    DispatchCancel,
    DispatchResult,
    UnassignedTrip,
    AvailableTruck,
    DispatchBoardResult,
)


class TestDispatchCreate:
    @pytest.mark.parametrize(
        "trip_id, truck_id, driver_id, priority",
        [
            (1, 10, 100, 0),
            (2, None, None, 1),
            (3, 20, 200, 5),
            (4, 30, None, 0),
        ],
    )
    def test_dispatch_create_valid(self, trip_id, truck_id, driver_id, priority):
        d = DispatchCreate(
            trip_id=trip_id,
            truck_id=truck_id,
            driver_id=driver_id,
            priority=priority,
        )
        assert d.trip_id == trip_id
        assert d.truck_id == truck_id
        assert d.driver_id == driver_id
        assert d.priority == priority

    def test_dispatch_create_defaults(self):
        d = DispatchCreate(trip_id=42)
        assert d.truck_id is None
        assert d.driver_id is None
        assert d.scheduled_departure is None
        assert d.priority == 0

    def test_dispatch_create_with_schedule(self):
        dep = datetime(2026, 7, 15, 8, 0)
        d = DispatchCreate(trip_id=5, scheduled_departure=dep, priority=3)
        assert d.scheduled_departure == dep
        assert d.priority == 3


class TestDispatchAssign:
    @pytest.mark.parametrize(
        "dispatch_id, truck_id, driver_id",
        [
            (1, 10, 100),
            (2, 20, 200),
        ],
    )
    def test_dispatch_assign_valid(self, dispatch_id, truck_id, driver_id):
        a = DispatchAssign(dispatch_id=dispatch_id, truck_id=truck_id, driver_id=driver_id)
        assert a.dispatch_id == dispatch_id
        assert a.truck_id == truck_id
        assert a.driver_id == driver_id


class TestDispatchCancel:
    def test_cancel_with_reason(self):
        c = DispatchCancel(dispatch_id=5, reason="No driver available")
        assert c.dispatch_id == 5
        assert c.reason == "No driver available"

    def test_cancel_default_reason_empty(self):
        c = DispatchCancel(dispatch_id=5)
        assert c.reason == ""


class TestDispatchResult:
    @pytest.mark.parametrize(
        "status",
        ["pending", "assigned", "in_transit", "completed", "cancelled"],
    )
    def test_dispatch_result_statuses(self, status):
        now = datetime.now()
        r = DispatchResult(
            id=1,
            trip_id=10,
            status=status,
            priority=0,
            created_at=now,
        )
        assert r.status == status
        assert r.created_at == now

    def test_dispatch_result_defaults(self):
        now = datetime.now()
        r = DispatchResult(id=1, trip_id=10, status="pending", priority=0, created_at=now)
        assert r.truck_id is None
        assert r.truck_plate == ""
        assert r.driver_id is None
        assert r.driver_name == ""
        assert r.scheduled_departure is None
        assert r.updated_at is None


class TestUnassignedTrip:
    def test_unassigned_trip_minimal(self):
        t = UnassignedTrip(
            trip_id=1,
            reference="TRIP-001",
            client_name="Client X",
            pickup="City A",
            delivery="City B",
            distance_km=250.0,
        )
        assert t.priority == 0

    def test_unassigned_trip_with_priority(self):
        t = UnassignedTrip(
            trip_id=2,
            reference="TRIP-002",
            client_name="Client Y",
            pickup="City C",
            delivery="City D",
            distance_km=500.0,
            priority=3,
        )
        assert t.priority == 3


class TestAvailableTruck:
    def test_available_truck_minimal(self):
        t = AvailableTruck(truck_id=10, plate="AB123CD")
        assert t.location == ""
        assert t.available_from is None
        assert t.capacity_kg is None

    def test_available_truck_full(self):
        dt = datetime(2026, 7, 20, 10, 0)
        t = AvailableTruck(
            truck_id=20,
            plate="BC234DE",
            location="Depot A",
            available_from=dt,
            capacity_kg=24000,
        )
        assert t.capacity_kg == 24000
        assert t.available_from == dt


class TestDispatchBoardResult:
    def test_dispatch_board_result(self):
        now = datetime.now()
        assigned = [
            DispatchResult(id=1, trip_id=10, status="assigned", priority=0, created_at=now),
        ]
        unassigned = [
            UnassignedTrip(trip_id=2, reference="T2", client_name="C", pickup="A", delivery="B", distance_km=100),
        ]
        trucks = [
            AvailableTruck(truck_id=1, plate="PLATE1"),
        ]
        board = DispatchBoardResult(assigned=assigned, unassigned=unassigned, available_trucks=trucks)
        assert len(board.assigned) == 1
        assert len(board.unassigned) == 1
        assert len(board.available_trucks) == 1
