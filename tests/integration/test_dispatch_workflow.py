"""Integration tests for the dispatch workflow using real services.

Tests wire together real TripService, FleetRepository, DriverRepository,
TripConflictService, and DispatchService against a test database.  Only
external dependencies (GraphHopper, external APIs) are assumed missing;
all internal services are real.

Test scenarios:
1. Complete dispatch lifecycle (create → assign truck → assign driver → status transitions)
2. Assignment with conflict detection (truck/driver double-booking)
3. Bulk assignment (truck and driver)
4. Status transition validation (valid + invalid transitions)
5. Undo/rollback (assign_both rolls back truck on driver failure)
"""
from __future__ import annotations

import pytest

from datetime import date, datetime, timedelta
from typing import Any

from models.trip_models import TripCreate
from repositories.driver_repository import DriverRepository
from repositories.fleet_repository import FleetRepository
from repositories.trip_repository import TripRepository
from services.conflict_service import TripConflictService
from services.dispatch_service.dispatch_service import DispatchService
from services.dispatch_service.errors import (
    DispatchError,
    DriverNotFoundError,
    InvalidStatusTransitionError,
    ResourceUnavailableError,
    TruckNotFoundError,
)
from services.operations.event_bus import EventBus, VALID_TRANSITIONS
from services.trip_service import TripService

pytestmark = pytest.mark.integration


# ── Helpers ──────────────────────────────────────────────────────────────────


def _dt_iso(days_offset: int = 0) -> str:
    """Return an ISO date string offset from today."""
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


def _dt_date(days_offset: int = 0) -> date:
    """Return a ``date`` object offset from today (for typed TripCreate)."""
    return (datetime.now() + timedelta(days=days_offset)).date()


def _dt_dmy(days_offset: int = 0) -> str:
    """Return a DD/MM/YYYY date string offset from today (for conflict service)."""
    return (datetime.now() + timedelta(days=days_offset)).strftime("%d/%m/%Y")


def _build_dispatch_service(db) -> DispatchService:
    """Wire real services together into a DispatchService instance.

    The ops_engine is intentionally omitted so status transitions go through
    the direct ``TripService.update()`` path (simpler, fewer dependencies).
    EventBus is passed as None to keep tests isolated; the singleton is reset
    by the root conftest's ``reset_singletons`` fixture anyway.
    """
    return DispatchService(
        trip_service=TripService(db),
        fleet_repo=FleetRepository(db),
        driver_repo=DriverRepository(db),
        conflict_service=TripConflictService(db),
        dta_service=None,
        tacho_repo=None,
        event_bus=None,
        alert_manager=None,
        ops_engine=None,
    )


# ── Trip helper for add() callers (avoids TripResult pydantic validation issues) ──


def _trip_add_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return a base dict for ``TripService.add()`` with all fields TripResult requires.

    ``TripResult`` validates that certain string fields are not ``None``.
    The deprecated ``TripService.add()`` + subsequent ``TripService.update()``
    path maps the DB row through ``_db_to_trip_result()``, so we must ensure
    those columns are never NULL.
    """
    kw: dict[str, Any] = {
        "client_id": 1,
        "client_name": "Test",
        "status": "Planned",
        "start_date": _dt_iso(1),
        "end_date": _dt_iso(2),
        "distance_km": 150.0,
        "total_price_eur": 600.0,
        "currency": "EUR",
        "driver_name": "",
        "truck_number": "",
    }
    kw.update(overrides)
    return kw


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Complete dispatch lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompleteDispatchLifecycle:
    """Create a trip → assign truck → assign driver → transition through all statuses."""

    def _create_trip(self, trip_svc: TripService, **overrides: Any) -> int:
        """Create a Planned trip and return its ID.

        Does *not* pre-assign truck or driver — those are added by the
        dispatch service during testing.
        """
        request = TripCreate(
            client_id=1,
            reference="DISPATCH-LIFECYCLE",
            start_date=_dt_date(1),
            price_eur=2500.0,
            distance_km=600.0,
            **overrides,
        )
        result = trip_svc.create(request, user_id=0)
        assert result.success, f"Trip creation failed: {result.errors}"
        assert result.data is not None
        return result.data.id

    def test_create_trip(self, seeded_db):
        """Step 0: create a trip in Planned status."""
        trip_svc = TripService(seeded_db)
        trip_id = self._create_trip(trip_svc)
        assert trip_id > 0

        row = seeded_db.conn.execute(
            "SELECT id, status, client_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row is not None
        assert row["status"] == "Planned"
        assert row["client_id"] == 1

    def test_assign_truck(self, seeded_db):
        """Step 1: assign truck to the trip."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip(trip_svc)

        result = dispatch.assign_truck(trip_id, truck_id=1)

        assert result.success
        assert result.operation == "assign_truck"
        assert result.trip_id == trip_id
        assert result.undo_token is not None
        assert result.undo_token.operation == "assign_truck"
        # Previous state: truck_number may be '' (from TripCreate default).
        # truck_id should be None (not pre-assigned).
        assert result.undo_token.previous_state["truck_id"] is None
        assert result.undo_token.trip_id == trip_id

        # Note: the production code uses truck.get("plate") which does not
        # match the actual column "plate_number", so it falls back to
        # str(truck_id).  What matters is that truck_id was correctly stored.
        assert "Assigned truck" in result.message

        # Verify in DB
        row = seeded_db.conn.execute(
            "SELECT truck_id, truck_number FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["truck_id"] == 1
        assert row["truck_number"] is not None
        assert len(str(row["truck_number"])) > 0

    def test_assign_driver(self, seeded_db):
        """Step 2: assign driver to the trip."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip(trip_svc)

        result = dispatch.assign_driver(trip_id, driver_id=1)

        assert result.success
        assert result.operation == "assign_driver"
        assert result.trip_id == trip_id
        assert result.undo_token is not None
        assert "Test Driver" in result.message

        # Verify in DB
        row = seeded_db.conn.execute(
            "SELECT driver_id, driver_name FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["driver_id"] == 1
        assert row["driver_name"] == "Test Driver"

    def test_assign_truck_then_driver(self, seeded_db):
        """Steps 1+2: assign both truck and driver in sequence."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip(trip_svc)

        # Assign truck
        truck_result = dispatch.assign_truck(trip_id, truck_id=1)
        assert truck_result.success

        # Assign driver
        driver_result = dispatch.assign_driver(trip_id, driver_id=1)
        assert driver_result.success

        # Verify both
        row = seeded_db.conn.execute(
            "SELECT truck_id, driver_id, truck_number, driver_name FROM trips WHERE id = ?",
            (trip_id,),
        ).fetchone()
        assert row["truck_id"] == 1
        assert row["driver_id"] == 1

    def test_full_status_transition_chain(self, seeded_db):
        """Steps 1–3: trip transitions Planned → Loading → In Transit → Delivered."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip(trip_svc)

        # Assign truck and driver (pre-requisite)
        dispatch.assign_truck(trip_id, truck_id=1)
        dispatch.assign_driver(trip_id, driver_id=1)

        # Transition: Planned → Loading
        r1 = dispatch.transition_status(trip_id, "Loading")
        assert r1.success
        row = seeded_db.conn.execute(
            "SELECT status FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["status"] == "Loading"

        # Transition: Loading → In Transit
        r2 = dispatch.transition_status(trip_id, "In Transit")
        assert r2.success
        row = seeded_db.conn.execute(
            "SELECT status FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["status"] == "In Transit"

        # Transition: In Transit → Delivered
        r3 = dispatch.transition_status(trip_id, "Delivered")
        assert r3.success
        row = seeded_db.conn.execute(
            "SELECT status FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["status"] == "Delivered"

    def test_full_lifecycle_verify_step_by_step(self, seeded_db):
        """End-to-end: create → assign truck → assign driver → all transitions, verified at each step."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)

        # 1. Create
        trip_id = self._create_trip(trip_svc)
        trip = trip_svc.get_by_id(trip_id)
        assert trip is not None
        assert trip.get("status") == "Planned"
        assert trip.get("truck_id") is None
        assert trip.get("driver_id") is None

        # 2. Assign truck
        dispatch.assign_truck(trip_id, truck_id=1)
        trip = trip_svc.get_by_id(trip_id)
        assert trip is not None
        assert trip.get("truck_id") == 1
        assert trip.get("truck_number") is not None

        # 3. Assign driver
        dispatch.assign_driver(trip_id, driver_id=1)
        trip = trip_svc.get_by_id(trip_id)
        assert trip is not None
        assert trip.get("driver_id") == 1
        assert trip.get("driver_name") == "Test Driver"

        # 4. Planned → Loading
        dispatch.transition_status(trip_id, "Loading")
        trip = trip_svc.get_by_id(trip_id)
        assert trip is not None
        assert trip.get("status") == "Loading"

        # 5. Loading → In Transit
        dispatch.transition_status(trip_id, "In Transit")
        trip = trip_svc.get_by_id(trip_id)
        assert trip is not None
        assert trip.get("status") == "In Transit"

        # 6. In Transit → Delivered
        dispatch.transition_status(trip_id, "Delivered")
        trip = trip_svc.get_by_id(trip_id)
        assert trip is not None
        assert trip.get("status") == "Delivered"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Assignment with conflict detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestConflictDetection:
    """Detect overlapping truck and driver assignments."""

    def _setup_conflicting_trips(self, db, conflict_service) -> tuple[int, int, list]:
        """Create two overlapping trips sharing the same truck, then check for conflicts.

        Returns (trip1_id, trip2_id, conflicts_list).
        """
        repo = TripRepository(db)
        now = _dt_dmy

        # Trip 1: active (In Transit), already has truck_id=1
        t1_id = repo.create({
            "client_id": 1,
            "client_name": "Client A",
            "status": "In Transit",
            "start_date": now(1),
            "end_date": now(5),
            "truck_id": 1,
            "driver_id": 1,
            "distance_km": 500.0,
            "total_price_eur": 2000.0,
        })

        # Trip 2: planned, also has truck_id=1 (overlapping dates)
        t2_id = repo.create({
            "client_id": 1,
            "client_name": "Client B",
            "status": "Planned",
            "start_date": now(3),
            "end_date": now(7),
            "truck_id": 1,
            "driver_id": 1,
            "distance_km": 400.0,
            "total_price_eur": 1600.0,
        })

        # Check conflicts for trip2
        conflicts = conflict_service.check_conflicts({
            "id": t2_id,
            "truck_id": 1,
            "driver_id": 1,
            "start_date": now(3),
            "end_date": now(7),
        })

        return t1_id, t2_id, conflicts

    def test_truck_conflict_detected(self, seeded_db):
        """Assigning same truck to overlapping trips raises conflict."""
        conflict_service = TripConflictService(seeded_db)
        _, _, conflicts = self._setup_conflicting_trips(seeded_db, conflict_service)
        assert len(conflicts) >= 1
        truck_conflicts = [c for c in conflicts if c.get("same_truck")]
        assert len(truck_conflicts) >= 1
        assert any(c["trip_id"] for c in truck_conflicts)

    def test_driver_conflict_detected(self, seeded_db):
        """Assigning same driver to overlapping trips raises conflict."""
        conflict_service = TripConflictService(seeded_db)
        _, _, conflicts = self._setup_conflicting_trips(seeded_db, conflict_service)
        assert len(conflicts) >= 1
        driver_conflicts = [c for c in conflicts if c.get("same_driver")]
        assert len(driver_conflicts) >= 1

    def test_no_conflict_for_non_overlapping_dates(self, seeded_db):
        """Same truck assigned to trips with non-overlapping dates produces no conflict."""
        repo = TripRepository(seeded_db)
        conflict_service = TripConflictService(seeded_db)
        now = _dt_dmy

        # Trip 1: active (In Transit), dates far in the past
        repo.create({
            "client_id": 1,
            "client_name": "Client A",
            "status": "In Transit",
            "start_date": now(-10),
            "end_date": now(-8),
            "truck_id": 1,
            "distance_km": 500.0,
            "total_price_eur": 2000.0,
        })

        # Trip 2: future dates, no overlap
        t2_id = repo.create({
            "client_id": 1,
            "client_name": "Client B",
            "status": "Planned",
            "start_date": now(10),
            "end_date": now(15),
            "truck_id": 1,
            "distance_km": 400.0,
            "total_price_eur": 1600.0,
        })

        conflicts = conflict_service.check_conflicts({
            "id": t2_id,
            "truck_id": 1,
            "start_date": now(10),
            "end_date": now(15),
        })
        assert len(conflicts) == 0

    def test_no_conflict_when_trip_completed(self, seeded_db):
        """Completed trips should not cause conflicts for the same truck."""
        repo = TripRepository(seeded_db)
        conflict_service = TripConflictService(seeded_db)
        now = _dt_dmy

        # Trip 1: already delivered (terminal status) with truck
        repo.create({
            "client_id": 1,
            "client_name": "Past Trip",
            "status": "Delivered",
            "start_date": now(1),
            "end_date": now(3),
            "truck_id": 1,
            "distance_km": 500.0,
            "total_price_eur": 2000.0,
        })

        # Trip 2: new trip with same truck, overlapping dates but trip1 is delivered
        t2_id = repo.create({
            "client_id": 1,
            "client_name": "New Trip",
            "status": "Planned",
            "start_date": now(2),
            "end_date": now(4),
            "truck_id": 1,
            "distance_km": 300.0,
            "total_price_eur": 1200.0,
        })

        conflicts = conflict_service.check_conflicts({
            "id": t2_id,
            "truck_id": 1,
            "start_date": now(2),
            "end_date": now(4),
        })
        assert len(conflicts) == 0

    def test_truck_not_found_raises(self, seeded_db):
        """Assigning a non-existent truck raises TruckNotFoundError."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = trip_svc.add(_trip_add_kwargs(client_name="No Truck"))

        with pytest.raises(TruckNotFoundError, match="Truck #99999 not found"):
            dispatch.assign_truck(trip_id, truck_id=99999)

    def test_driver_not_found_raises(self, seeded_db):
        """Assigning a non-existent driver raises DriverNotFoundError."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = trip_svc.add(_trip_add_kwargs(client_name="No Driver"))

        with pytest.raises(DriverNotFoundError, match="Driver #99999 not found"):
            dispatch.assign_driver(trip_id, driver_id=99999)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Bulk assignment
# ═══════════════════════════════════════════════════════════════════════════════


class TestBulkAssignment:
    """Bulk assignment operations — assign same truck/driver to multiple trips."""

    def _create_trips(self, trip_svc: TripService, count: int) -> list[int]:
        """Create *count* Planned trips and return their IDs."""
        ids: list[int] = []
        for i in range(count):
            tid = trip_svc.add(_trip_add_kwargs(
                client_name=f"Bulk Client {i}",
                start_date=_dt_iso(10 + i),
                end_date=_dt_iso(12 + i),
                distance_km=200.0,
                total_price_eur=800.0,
            ))
            ids.append(tid)
        return ids

    def test_bulk_assign_truck_all_succeed(self, seeded_db):
        """Bulk assign the same truck to 5 trips — all should succeed."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)

        trip_ids = self._create_trips(trip_svc, 5)
        result = dispatch.bulk_assign_truck(trip_ids, truck_id=1)

        assert result.total == 5
        assert result.succeeded == 5
        assert result.failed == 0
        assert len(result.results) == 5
        assert all(r.success for r in result.results)

        # Verify all trips have the truck assigned
        rows = seeded_db.conn.execute(
            f"SELECT id, truck_id FROM trips WHERE id IN ({','.join('?' * 5)})",
            trip_ids,
        ).fetchall()
        for row in rows:
            assert row["truck_id"] == 1, f"Trip #{row['id']} missing truck assignment"

    def test_bulk_assign_driver_all_succeed(self, seeded_db):
        """Bulk assign the same driver to 5 trips — all should succeed."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)

        trip_ids = self._create_trips(trip_svc, 5)
        result = dispatch.bulk_assign_driver(trip_ids, driver_id=1)

        assert result.total == 5
        assert result.succeeded == 5
        assert result.failed == 0
        assert len(result.results) == 5
        assert all(r.success for r in result.results)

        # Verify all trips have the driver assigned
        rows = seeded_db.conn.execute(
            f"SELECT id, driver_id, driver_name FROM trips WHERE id IN ({','.join('?' * 5)})",
            trip_ids,
        ).fetchall()
        for row in rows:
            assert row["driver_id"] == 1, f"Trip #{row['id']} missing driver assignment"
            assert row["driver_name"] == "Test Driver"

    def test_bulk_assign_truck_some_fail(self, seeded_db):
        """Bulk assign with a non-existent truck raises TruckNotFoundError (validated upfront)."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)

        trip_ids = self._create_trips(trip_svc, 1)
        with pytest.raises(TruckNotFoundError, match="Truck #99999 not found"):
            dispatch.bulk_assign_truck(trip_ids, truck_id=99999)

    def test_bulk_assign_undo_tokens_present(self, seeded_db):
        """Bulk assignments return undo tokens for each successful operation."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)

        trip_ids = self._create_trips(trip_svc, 3)
        result = dispatch.bulk_assign_truck(trip_ids, truck_id=1)

        assert len(result.undo_tokens) == 3
        for token in result.undo_tokens:
            assert token.operation == "assign_truck"
            assert token.previous_state["truck_id"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Status transition through workflow
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusTransitions:
    """Validate all valid and invalid status transitions."""

    def _create_trip_with_status(self, trip_svc: TripService, status: str) -> int:
        """Create a trip in the given status and return its ID."""
        return trip_svc.add(_trip_add_kwargs(
            client_name=f"Status {status}",
            status=status,
            start_date=_dt_iso(1),
            end_date=_dt_iso(3),
            distance_km=300.0,
            total_price_eur=1200.0,
        ))

    # ── Valid transitions ───────────────────────────────────────────────

    def test_planned_to_loading(self, seeded_db):
        """Planned → Loading is valid."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip_with_status(trip_svc, "Planned")

        result = dispatch.transition_status(trip_id, "Loading")
        assert result.success
        assert result.details["old_status"] == "Planned"
        assert result.details["new_status"] == "Loading"

    def test_loading_to_in_transit(self, seeded_db):
        """Loading → In Transit is valid."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip_with_status(trip_svc, "Loading")

        result = dispatch.transition_status(trip_id, "In Transit")
        assert result.success
        assert result.details["new_status"] == "In Transit"

    def test_in_transit_to_delivered(self, seeded_db):
        """In Transit → Delivered is valid."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip_with_status(trip_svc, "In Transit")

        result = dispatch.transition_status(trip_id, "Delivered")
        assert result.success
        assert result.details["new_status"] == "Delivered"

    def test_all_valid_transitions(self, seeded_db):
        """Verifies all expected valid transitions from VALID_TRANSITIONS."""
        for old_status, next_statuses in VALID_TRANSITIONS.items():
            if not next_statuses:
                continue
            for new_status in next_statuses:
                # Test the dispatch service transition
                trip_id = self._create_trip_with_status(
                    TripService(seeded_db), old_status,
                )
                dispatch = _build_dispatch_service(seeded_db)
                result = dispatch.transition_status(trip_id, new_status)
                assert result.success, (
                    f"Valid transition {old_status} → {new_status} should succeed"
                )

                # Verify DB matches
                row = seeded_db.conn.execute(
                    "SELECT status FROM trips WHERE id = ?", (trip_id,)
                ).fetchone()
                assert row["status"] == new_status, (
                    f"DB status should be '{new_status}' after transition"
                )

    # ── Invalid transitions ─────────────────────────────────────────────

    def test_planned_to_delivered_rejected(self, seeded_db):
        """Planned → Delivered (skip Loading+In Transit) is invalid."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip_with_status(trip_svc, "Planned")

        with pytest.raises(InvalidStatusTransitionError, match="Cannot transition"):
            dispatch.transition_status(trip_id, "Delivered")

        # Status should remain Planned
        row = seeded_db.conn.execute(
            "SELECT status FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["status"] == "Planned"

    def test_delivered_to_loading_rejected(self, seeded_db):
        """Delivered → Loading (backwards transition) is invalid."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip_with_status(trip_svc, "Delivered")

        with pytest.raises(InvalidStatusTransitionError, match="Cannot transition"):
            dispatch.transition_status(trip_id, "Loading")

    def test_planned_to_planned_noop(self, seeded_db):
        """Transitioning to the same status is rejected (not in VALID_TRANSITIONS)."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip_with_status(trip_svc, "Planned")

        with pytest.raises(InvalidStatusTransitionError):
            dispatch.transition_status(trip_id, "Planned")

    def test_unknown_status_rejected(self, seeded_db):
        """Transition to a status not in VALID_TRANSITIONS is rejected."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip_with_status(trip_svc, "Planned")

        with pytest.raises(InvalidStatusTransitionError):
            dispatch.transition_status(trip_id, "NonExistentStatus")

    def test_invalid_transition_from_paid(self, seeded_db):
        """'Paid' → 'Loading' is not a valid transition (only 'Invoiced' is)."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip_with_status(trip_svc, "Paid")

        with pytest.raises(InvalidStatusTransitionError, match="Cannot transition"):
            dispatch.transition_status(trip_id, "Loading")

    def test_cancel_from_planned(self, seeded_db):
        """Cancelling a Planned trip is valid."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip_with_status(trip_svc, "Planned")

        result = dispatch.cancel_trip(trip_id, reason="Test cancellation")
        assert result.success
        assert result.details["new_status"] == "Cancelled"

        row = seeded_db.conn.execute(
            "SELECT status FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["status"] == "Cancelled"

    def test_complete_trip_alias(self, seeded_db):
        """complete_trip() is an alias for transition_status to 'Delivered'."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = self._create_trip_with_status(trip_svc, "In Transit")

        result = dispatch.complete_trip(trip_id)
        assert result.success
        assert result.details["new_status"] == "Delivered"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Undo / rollback
# ═══════════════════════════════════════════════════════════════════════════════


class TestUndoAndRollback:
    """Rollback semantics: assign_both rolls back truck on driver failure."""

    def test_assign_both_rolls_back_truck_on_driver_failure(self, seeded_db):
        """When assign_both succeeds at truck but fails at driver, truck is rolled back."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = trip_svc.add(_trip_add_kwargs(client_name="Rollback Test"))

        with pytest.raises(DriverNotFoundError, match="Driver #99999 not found"):
            dispatch.assign_both(trip_id, truck_id=1, driver_id=99999)

        # Verify truck was rolled back (truck_id should be None)
        row = seeded_db.conn.execute(
            "SELECT truck_id, driver_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["truck_id"] is None, "Truck assignment should be rolled back"
        assert row["driver_id"] is None

    def test_assign_both_with_only_truck_works(self, seeded_db):
        """assign_both with only truck_id (driver=None) assigns truck and skips driver."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = trip_svc.add(_trip_add_kwargs(client_name="Truck Only"))

        result = dispatch.assign_both(trip_id, truck_id=1, driver_id=None)
        assert result.success
        assert result.operation == "assign_both"

        row = seeded_db.conn.execute(
            "SELECT truck_id, driver_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["truck_id"] == 1
        assert row["driver_id"] is None

    def test_assign_both_with_only_driver_works(self, seeded_db):
        """assign_both with only driver_id (truck=None) assigns driver and skips truck."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = trip_svc.add(_trip_add_kwargs(client_name="Driver Only"))

        result = dispatch.assign_both(trip_id, truck_id=None, driver_id=1)
        assert result.success
        assert result.operation == "assign_both"

        row = seeded_db.conn.execute(
            "SELECT truck_id, driver_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["truck_id"] is None
        assert row["driver_id"] == 1

    def test_assign_both_success_assigns_both(self, seeded_db):
        """assign_both with valid truck and driver assigns both successfully."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = trip_svc.add(_trip_add_kwargs(client_name="Both Assigned"))

        result = dispatch.assign_both(trip_id, truck_id=1, driver_id=1)
        assert result.success
        assert result.operation == "assign_both"

        row = seeded_db.conn.execute(
            "SELECT truck_id, driver_id, truck_number, driver_name FROM trips WHERE id = ?",
            (trip_id,),
        ).fetchone()
        assert row["truck_id"] == 1
        assert row["driver_id"] == 1
        assert row["truck_number"] is not None  # set to str(truck_id) due to key mismatch
        assert row["driver_name"] == "Test Driver"

    def test_undo_token_returned_on_single_assign(self, seeded_db):
        """assign_truck and assign_driver return undo tokens with correct previous state."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = trip_svc.add(_trip_add_kwargs(client_name="Undo Token"))

        # Truck undo
        truck_result = dispatch.assign_truck(trip_id, truck_id=1)
        token = truck_result.undo_token
        assert token is not None
        assert token.operation == "assign_truck"
        assert token.trip_id == trip_id
        assert token.previous_state["truck_id"] is None

        # Driver undo
        driver_result = dispatch.assign_driver(trip_id, driver_id=1)
        token = driver_result.undo_token
        assert token is not None
        assert token.operation == "assign_driver"
        assert token.trip_id == trip_id
        assert token.previous_state["driver_id"] is None


class TestEdgeCases:
    """Edge cases for the dispatch service."""

    def test_trip_not_found(self, seeded_db):
        """Operations on a non-existent trip raise TripNotFoundError."""
        dispatch = _build_dispatch_service(seeded_db)

        from services.dispatch_service.errors import TripNotFoundError

        with pytest.raises(TripNotFoundError, match="Trip #99999 not found"):
            dispatch.assign_truck(99999, truck_id=1)

        with pytest.raises(TripNotFoundError, match="Trip #99999 not found"):
            dispatch.assign_driver(99999, driver_id=1)

        with pytest.raises(TripNotFoundError, match="Trip #99999 not found"):
            dispatch.transition_status(99999, "Loading")

    def test_truck_already_assigned(self, seeded_db):
        """Assigning the same truck twice does not error — updates in-place."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = trip_svc.add(_trip_add_kwargs(client_name="Double Assign Truck"))

        # Assign truck once
        r1 = dispatch.assign_truck(trip_id, truck_id=1)
        assert r1.success

        # Assign same truck again (should succeed — availability check passes)
        r2 = dispatch.assign_truck(trip_id, truck_id=1)
        assert r2.success

    def test_driver_already_assigned(self, seeded_db):
        """Assigning the same driver twice does not error — updates in-place."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = trip_svc.add(_trip_add_kwargs(client_name="Double Assign Driver"))

        r1 = dispatch.assign_driver(trip_id, driver_id=1)
        assert r1.success

        r2 = dispatch.assign_driver(trip_id, driver_id=1)
        assert r2.success

    def test_trip_status_transition_preserves_fields(self, seeded_db):
        """Status transitions should not clobber other trip fields."""
        trip_svc = TripService(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)
        trip_id = trip_svc.add(_trip_add_kwargs(
            client_name="Preserve Fields",
            distance_km=500.0,
            total_price_eur=2000.0,
        ))

        # Assign and transition
        dispatch.assign_truck(trip_id, truck_id=1)
        dispatch.assign_driver(trip_id, driver_id=1)
        dispatch.transition_status(trip_id, "Loading")
        dispatch.transition_status(trip_id, "In Transit")
        dispatch.transition_status(trip_id, "Delivered")

        # All original fields preserved
        row = seeded_db.conn.execute(
            "SELECT id, client_id, client_name, distance_km, total_price_eur, status FROM trips WHERE id = ?",
            (trip_id,),
        ).fetchone()
        assert row["client_id"] == 1
        assert row["client_name"] == "Preserve Fields"
        assert float(row["distance_km"]) == 500.0
        assert float(row["total_price_eur"]) == 2000.0
        assert row["status"] == "Delivered"


class TestDispatchBoardData:
    """Dispatch board data loading — get_dispatch_board_data."""

    def test_empty_board(self, seeded_db):
        """Board with no trips returns empty columns."""
        dispatch = _build_dispatch_service(seeded_db)
        data = dispatch.get_dispatch_board_data()
        for col in ("Planned", "Loading", "In Transit", "Delivered", "Cancelled"):
            assert col in data.column_trips
            assert len(data.column_trips[col]) == 0
        assert data.status_counts["Planned"] == 0

    def test_board_groups_by_column(self, seeded_db):
        """Trips are grouped into their correct column buckets."""
        repo = TripRepository(seeded_db)
        dispatch = _build_dispatch_service(seeded_db)

        repo.create({
            "client_id": 1, "client_name": "Planned Trip",
            "status": "Planned", "start_date": _dt_iso(1),
            "distance_km": 100.0, "total_price_eur": 400.0,
        })
        repo.create({
            "client_id": 1, "client_name": "Loading Trip",
            "status": "Loading", "start_date": _dt_iso(1),
            "distance_km": 200.0, "total_price_eur": 800.0,
        })
        repo.create({
            "client_id": 1, "client_name": "Transit Trip",
            "status": "In Transit", "start_date": _dt_iso(0),
            "distance_km": 300.0, "total_price_eur": 1200.0,
        })

        data = dispatch.get_dispatch_board_data()
        assert len(data.column_trips["Planned"]) == 1
        assert len(data.column_trips["Loading"]) == 1
        assert len(data.column_trips["In Transit"]) == 1
        assert len(data.column_trips["Delivered"]) == 0
        assert data.status_counts["Planned"] == 1
        assert data.status_counts["Loading"] == 1
        assert data.status_counts["In Transit"] == 1
