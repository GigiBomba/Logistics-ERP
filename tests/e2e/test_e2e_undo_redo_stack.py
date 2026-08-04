"""E2E: Undo/redo lifecycle for trip status transitions.

Tests the UndoStack and TripStatusWorkflow integration to verify
undo/redo of status transitions, max depth eviction, odometer
non-reversion on undo, and mismatch rejection.
"""

from __future__ import annotations

import logging
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from repositories.driver_repository import DriverRepository
from repositories.driver_truck_assignment_repository import DriverTruckAssignmentRepository
from repositories.fleet_repository import FleetRepository
from models.trip_models import TripCreate
from services.fleet_service import FleetService
from services.operations.event_bus import EventBus
from services.operations.trip_status_workflow import TripStatusWorkflow
from services.operations.undo_stack import UndoCommand, UndoStack
from services.trip_service import TripService
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow

logging.disable(logging.CRITICAL)


# ── Helpers ───────────────────────────────────────────────────────────────

def _dt(days_offset: int = 0) -> str:
    return (datetime.now()).strftime("%Y-%m-%d")


def _create_truck(db) -> int:
    svc = FleetService(db)
    return svc.add_truck({
        "plate_number": "TR-UNDO-01",
        "model": "Actros 1845",
        "manufacturer": "Mercedes-Benz",
        "year": 2023,
        "vin": "WDB9634031L999999",
        "fuel_consumption": 28.5,
        "mileage": 50000.0,
        "status": "Active",
        "active_status": 1,
    })


def _create_driver(db) -> int:
    repo = DriverRepository(db)
    now = datetime.now().isoformat()
    return repo.create({
        "name": "Undo Test Driver",
        "phone": "+40-700-000-001",
        "email": "undo.driver@example.com",
        "license_number": "RO/99999/ABC",
        "license_category": "CE",
        "license_expiry": (datetime.now().isoformat()),
        "medical_expiry": (datetime.now().isoformat()),
        "hire_date": (datetime.now().isoformat()),
        "monthly_salary": 3500.0,
        "is_active": 1,
        "created_at": now,
        "updated_at": now,
    })


def _ensure_client(db, client_id: int = 1, name: str = "Undo Client GmbH") -> None:
    """Ensure a client record exists in the test DB."""
    existing = db.conn.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not existing:
        db.conn.execute(
            "INSERT INTO clients (id, name, email, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, datetime('now'), datetime('now'))",
            (client_id, name, "undo@example.com"),
        )
        db.conn.commit()


def _create_trip(db, truck_id, driver_id) -> int:
    svc = TripService(db)
    _ensure_client(db)
    model_fields = TripCreate.model_fields
    raw = {
        "client_id": 1,
        "client_name": "Undo Client GmbH",
        "truck_plate": "TR-UNDO-01",
        "truck_id": truck_id,
        "driver_name": "Undo Test Driver",
        "driver_id": driver_id,
        "start_date": _dt(),
        "end_date": _dt(),
        "distance_km": 500.0,
        "price_eur": 2000.0,
        "rate_per_km": 4.0,
        "fuel_cost": 400.0,
        "toll_cost": 80.0,
        "salary_cost": 300.0,
        "extra_costs": 30.0,
        "net_profit": 1190.0,
        "currency": "EUR",
        "status": "Planned",
    }
    trip_data = {k: v for k, v in raw.items() if k in model_fields}
    result = svc.create(TripCreate(**trip_data))
    return result.data.id


# ── Tests ─────────────────────────────────────────────────────────────────


class TestUndoRedoLifecycle:
    """Undo/redo lifecycle for trip status transitions."""

    def test_single_undo_reverts_status_to_previous(self, db):
        """Transition Planned→Loading→In Transit, undo back to Loading."""
        truck_id = _create_truck(db)
        driver_id = _create_driver(db)
        # Assign driver to truck
        assignment_repo = DriverTruckAssignmentRepository(db)
        assignment_repo.assign(driver_id=driver_id, truck_id=truck_id)
        trip_id = _create_trip(db, truck_id, driver_id)

        eb = EventBus()
        trip_service = TripService(db)
        undo_stack = UndoStack()
        maint_mock = MagicMock()
        workflow = TripStatusWorkflow(
            db=db, trip_service=trip_service,
            event_bus=eb, maintenance_engine=maint_mock,
            undo_stack=undo_stack,
        )

        # Transition Planned → Loading → In Transit via workflow
        ok1 = workflow.force_trip_status(trip_id, "Loading")
        assert ok1 is True
        ok2 = workflow.force_trip_status(trip_id, "In Transit")
        assert ok2 is True

        # Verify current status
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "In Transit"

        # Undo: revert In Transit → Loading
        cmd = undo_stack.undo(current_status="In Transit")
        assert cmd is not None
        assert cmd.old_status == "Loading"
        assert cmd.new_status == "In Transit"
        assert cmd.trip_id == trip_id

        # Apply the undo by forcing back to the old status (skip_undo to avoid re-push)
        ok3 = workflow.force_trip_status(trip_id, cmd.old_status, skip_undo=True)
        assert ok3 is True
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "Loading"

    def test_full_undo_chain_then_redo_chain(self, db):
        """Transition through 4 statuses, undo all 4, redo all 4."""
        truck_id = _create_truck(db)
        driver_id = _create_driver(db)
        assignment_repo = DriverTruckAssignmentRepository(db)
        assignment_repo.assign(driver_id=driver_id, truck_id=truck_id)
        trip_id = _create_trip(db, truck_id, driver_id)

        eb = EventBus()
        trip_service = TripService(db)
        undo_stack = UndoStack()
        maint_mock = MagicMock()
        workflow = TripStatusWorkflow(
            db=db, trip_service=trip_service,
            event_bus=eb, maintenance_engine=maint_mock,
            undo_stack=undo_stack,
        )

        statuses = ["Loading", "In Transit", "Delivered", "Invoiced"]
        for s in statuses:
            ok = workflow.force_trip_status(trip_id, s)
            assert ok is True

        # Verify we are at Invoiced
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "Invoiced"

        # Undo all 4 — reverting to Delivered, In Transit, Loading, Planned
        for expected_old in reversed(statuses):
            trip = trip_service.get_by_id(trip_id)
            cmd = undo_stack.undo(current_status=trip["status"])
            assert cmd is not None
            assert cmd.new_status == expected_old
            ok = workflow.force_trip_status(trip_id, cmd.old_status, skip_undo=True)
            assert ok is True

        # Should be back to Planned
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "Planned"

        # Redo all 4
        for expected_new in statuses:
            cmd = undo_stack.redo(current_status=trip_service.get_by_id(trip_id)["status"])
            assert cmd is not None
            assert cmd.new_status == expected_new
            ok = workflow.force_trip_status(trip_id, cmd.new_status, skip_undo=True)
            assert ok is True

        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "Invoiced"

    def test_undo_mismatch_status_is_rejected(self, db):
        """Undo with wrong current_status returns None."""
        stack = UndoStack()
        stack.push(UndoCommand(trip_id=1, old_status="Planned", new_status="Loading"))

        # Current status "In Transit" does not match expected "Loading"
        cmd = stack.undo(current_status="In Transit")
        assert cmd is None

        # Stack should still have the command
        assert stack.can_undo is True

    def test_redo_clears_when_new_action_pushed(self, db):
        """After undo, push new action, verify redo stack cleared."""
        stack = UndoStack()

        stack.push(UndoCommand(trip_id=1, old_status="Planned", new_status="Loading"))
        stack.push(UndoCommand(trip_id=1, old_status="Loading", new_status="In Transit"))

        # Undo one
        cmd = stack.undo(current_status="In Transit")
        assert cmd is not None
        assert stack.can_redo is True

        # Push a new command — redo stack should be cleared
        stack.push(UndoCommand(trip_id=1, old_status="Loading", new_status="Cancelled"))
        assert stack.can_redo is False

    def test_max_depth_eviction(self, db):
        """Push 22 commands, verify only 20 kept."""
        stack = UndoStack()
        for i in range(22):
            stack.push(UndoCommand(
                trip_id=i,
                old_status=f"old_{i}",
                new_status=f"new_{i}",
            ))

        # Should have only 20 commands (MAX_DEPTH=20)
        assert stack.can_undo is True
        # Pop one and verify it's the 20th (index 2 to 21)
        cmd = stack.undo()
        assert cmd is not None
        assert cmd.trip_id == 21  # most recent

        # The oldest (trip_id=0,1) should have been evicted
        stack2 = UndoStack()
        # Can't directly inspect the internal list, but verify
        # that undoing 20 times exhausts the stack
        for _ in range(19):
            stack.undo()
        assert stack.can_undo is False

    def test_odometer_not_auto_reverted_on_undo(self, db):
        """Transition to Delivered (updates odometer), undo, verify odometer stays updated."""
        truck_id = _create_truck(db)
        driver_id = _create_driver(db)
        assignment_repo = DriverTruckAssignmentRepository(db)
        assignment_repo.assign(driver_id=driver_id, truck_id=truck_id)
        trip_id = _create_trip(db, truck_id, driver_id)

        fleet_repo = FleetRepository(db)
        initial_mileage = fleet_repo.get_by_id(truck_id)["mileage"]

        eb = EventBus()
        trip_service = TripService(db)
        undo_stack = UndoStack()
        maint_mock = MagicMock()

        workflow = TripStatusWorkflow(
            db=db, trip_service=trip_service,
            event_bus=eb, maintenance_engine=maint_mock,
            undo_stack=undo_stack,
        )

        # Transition to Delivered — this updates odometer
        workflow.force_trip_status(trip_id, "Loading")
        workflow.force_trip_status(trip_id, "In Transit")
        workflow.force_trip_status(trip_id, "Delivered")

        # Verify odometer was updated
        truck = fleet_repo.get_by_id(truck_id)
        assert truck["mileage"] == initial_mileage + 500.0

        # Now undo back to In Transit
        cmd = undo_stack.undo(current_status="Delivered")
        assert cmd is not None
        ok = workflow.force_trip_status(trip_id, cmd.old_status, skip_undo=True)
        assert ok is True

        # Verify odometer did NOT revert
        truck = fleet_repo.get_by_id(truck_id)
        assert truck["mileage"] == initial_mileage + 500.0
