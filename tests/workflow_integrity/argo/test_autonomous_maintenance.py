"""ARGO-MNT: Autonomous maintenance — windows block dispatch, reassignment excludes, due ordering.

Covers blueprint §5.3 (Autonomous Maintenance Tests) using the deterministic
``build_argo_world`` fixture (one CRITICAL-maintenance truck + healthy fleet).

The three scenarios assert the REAL guard behaviour:

* **(A) maintenance window blocks dispatch** — a truck whose maintenance is
  due/blocked is refused by ``dispatch.create`` (M-INV-03 intent).  The REAL
  guard (``AvailabilityChecker.check_truck``) blocks the canonical maintenance
  status ``'In Service'`` AND the lowercase ``'maintenance'`` state (plus
  ``active_status=0``), covering both the pinned canonical-block case and the
  as-seeded CRITICAL truck, mirroring ``test_autonomous_dispatch.py``.  We
  also document that ``maintenance.schedule`` (a real Level-2 tool) does
  NOT mutate the truck into a dispatch-blocked state, so booking a window
  alone does not yet refuse dispatch.
* **(B) reassignment excludes the blocked truck** — the real eligibility path
  (``FleetRepository.get_active_trucks`` + ``AvailabilityChecker``) never
  surfaces the CRITICAL-maintenance truck.
* **(C) due-maintenance ordering** — matches the real maintenance repository's
  ORDER BY (records: ``date DESC, id DESC``; schedules-with-overdue:
  ``truck_id, maintenance_type``) and its shared overdue threshold.

Everything is fixture-built and deterministic — no LLM, no network, no clocks
in the assertion path.
"""

from __future__ import annotations

import pytest

from backend.copilot.tools.dispatch_tools import (
    DispatchCreateParams,
    DispatchCreateTool,
)
from backend.copilot.tools.maintenance_tools import (
    MaintenanceScheduleParams,
    MaintenanceScheduleTool,
)
from repositories.fleet_repository import FleetRepository
from services.conflict_service import TripConflictService
from services.dispatch_service.availability import AvailabilityChecker
from services.fleet_maintenance_service import FleetMaintenanceService

from tests.workflow_integrity.argo.fixtures import build_argo_world, make_tool_context
from tests.workflow_integrity.personas.fixtures import seed_trip

pytestmark = [pytest.mark.argo, pytest.mark.asyncio]


# ── Shared deterministic helpers ────────────────────────────────────────────

def _new_planned_trip(db, world) -> int:
    """Insert a fresh, unassigned Planned trip to use as a dispatch target."""
    return seed_trip(
        db,
        company_id=world["company_id"],
        client_id=world["client_ids"][0],
        client_name=f"Client {world['client_ids'][0]}",
        driver_name="Driver Dispatch",
        driver_id=world["driver_ids"][0],
        truck_number="",
        truck_id=None,
        distance_km=100.0,
        total_price_eur=400.0,
        status="Planned",
        net_profit=200.0,
        rate_per_km=4.0,
        gross_per_km=2.0,
    )


def _dispatch_ctx(db, world):
    return make_tool_context(
        db,
        company_id=world["company_id"],
        user_id=world["user_id"],
        role="dispatcher",
    )


def _put_truck_in_maintenance(db, truck_id: int) -> None:
    """Force the dispatch-blocked maintenance state the availability layer guards."""
    db.conn.execute(
        "UPDATE trucks SET status = 'In Service', maintenance_due = '2020-01-01' "
        "WHERE id = ?",
        (truck_id,),
    )
    db.conn.commit()


def _create_params(trip_id: int, truck_id: int) -> DispatchCreateParams:
    """Build ``dispatch.create`` params, bypassing the broken cross-field validator.

    Same documented gap as ``test_autonomous_dispatch.py``: ``DispatchCreateParams``
    always raises because the ``trip_id`` after-validator reads ``info.data``
    before ``truck_id``/``driver_id`` are validated.  ``model_construct`` skips
    only that broken validator — the object the tool's real service code
    consumes is otherwise identical.
    """
    return DispatchCreateParams.model_construct(trip_id=trip_id, truck_id=truck_id)


# ═════════════════════════════════════════════════════════════════════════════
# Scenario A — maintenance window blocks dispatch
# ═════════════════════════════════════════════════════════════════════════════

class TestMaintenanceWindowBlocksDispatch:
    """ARGO-MNT-A: no dispatch into a blocked maintenance window (M-INV-03)."""

    async def test_dispatch_into_blocked_maintenance_window_refused(self, workflow_env, db):
        """A truck with an overdue maintenance window is refused by dispatch.create."""
        world = build_argo_world(db)
        maint_truck = world["maintenance_truck_id"]

        # Force the blocked-maintenance state the availability checker guards.
        _put_truck_in_maintenance(db, maint_truck)

        trip_id = _new_planned_trip(db, world)
        tool = DispatchCreateTool()
        params = _create_params(trip_id, maint_truck)
        result = await tool.execute(params, _dispatch_ctx(db, world))

        # Real guard: the truck is refused and never assigned.
        assert result.status == "failed", result
        assert "Truck is not available (blocked state)" in result.message_params["error"]
        trip = db.conn.execute(
            "SELECT truck_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert trip["truck_id"] is None

    async def test_maintenance_status_truck_is_blocked(self, workflow_env, db):
        """The as-seeded CRITICAL-maintenance truck is refused by dispatch.

        ``AvailabilityChecker.check_truck`` now blocks the lowercase
        ``'maintenance'`` status and ``active_status=0``, so the as-seeded
        CRITICAL truck is refused — no assignment row is written
        (M-INV-03 / GR7).
        """
        world = build_argo_world(db)
        maint_truck = world["maintenance_truck_id"]

        truck_row = db.conn.execute(
            "SELECT status, active_status FROM trucks WHERE id = ?", (maint_truck,)
        ).fetchone()
        assert truck_row["status"] == "maintenance"
        assert truck_row["active_status"] == 0

        trip_id = _new_planned_trip(db, world)
        tool = DispatchCreateTool()
        result = await tool.execute(
            _create_params(trip_id, maint_truck), _dispatch_ctx(db, world)
        )

        assert result.status == "failed", result
        trip = db.conn.execute(
            "SELECT truck_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert trip["truck_id"] is None

    async def test_schedule_maintenance_tool_is_current_gap(self, workflow_env, db):
        """Gap documentation: maintenance.schedule does NOT yet block dispatch.

        Scheduling a maintenance window through the real Level-2 tool writes a
        ``maintenance_schedules`` row but does not mutate the truck's status /
        ``maintenance_due``, so the availability layer still sees it as
        dispatchable.  This is the documented M-INV-03 gap: a window booked via
        the tool does not yet surface in dispatch availability.
        """
        world = build_argo_world(db)
        svc = FleetMaintenanceService(db)
        healthy = world["healthy_truck_ids"][0]

        ctx = make_tool_context(
            db,
            company_id=world["company_id"],
            user_id=world["user_id"],
            role="dispatcher",
            extra_services={"fleet_maintenance_service": svc},
        )
        tool = MaintenanceScheduleTool()
        params = MaintenanceScheduleParams(
            truck_id=healthy, maint_type="brake_check", interval_months=12
        )
        result = await tool.execute(params, ctx)

        assert result.status == "success", result
        schedule_id = result.data["schedule_id"]
        assert schedule_id > 0
        schedules = svc.get_schedules(healthy)
        assert any(s["id"] == schedule_id for s in schedules)

        # The real schedule tool does not flip the truck into a blocked state.
        truck = db.conn.execute(
            "SELECT status, maintenance_due FROM trucks WHERE id = ?", (healthy,)
        ).fetchone()
        assert truck["status"] != "In Service"

        # Consequently dispatch availability still allows the truck.
        trip_id = _new_planned_trip(db, world)
        dres = await DispatchCreateTool().execute(
            _create_params(trip_id, healthy),
            _dispatch_ctx(db, world),
        )
        assert dres.status == "success", dres
        trip = db.conn.execute(
            "SELECT truck_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert trip["truck_id"] == healthy


# ═════════════════════════════════════════════════════════════════════════════
# Scenario B — reassignment excludes the blocked truck
# ═════════════════════════════════════════════════════════════════════════════

class TestReassignmentExcludesBlockedTruck:
    """ARGO-MNT-B: recommendation/dispatch eligibility never includes the blocked truck."""

    async def test_eligible_truck_set_excludes_blocked(self, workflow_env, db):
        """FleetRepository.get_active_trucks — the real eligibility query."""
        world = build_argo_world(db)
        repo = FleetRepository(db)

        eligible_ids = {t["id"] for t in repo.get_active_trucks()}

        assert world["maintenance_truck_id"] not in eligible_ids
        assert set(world["healthy_truck_ids"]) <= eligible_ids

    async def test_availability_marks_blocked_truck_unavailable(self, workflow_env, db):
        """AvailabilityChecker — the per-truck dispatch gate used by assign."""
        world = build_argo_world(db)
        repo = FleetRepository(db)
        conflict_service = TripConflictService(db)
        checker = AvailabilityChecker(
            fleet_repo=repo,
            driver_repo=None,
            conflict_service=conflict_service,
            tacho_repo=None,
        )

        _put_truck_in_maintenance(db, world["maintenance_truck_id"])
        blocked = repo.get_by_id(world["maintenance_truck_id"])
        healthy = repo.get_by_id(world["healthy_truck_ids"][0])

        blocked_avail = checker.check_truck(
            blocked, {"truck_id": world["maintenance_truck_id"]}
        )
        healthy_avail = checker.check_truck(
            healthy, {"truck_id": world["healthy_truck_ids"][0]}
        )

        assert blocked_avail.available is False
        assert healthy_avail.available is True


# ═════════════════════════════════════════════════════════════════════════════
# Scenario C — due-maintenance ordering
# ═════════════════════════════════════════════════════════════════════════════

class TestDueMaintenanceOrdering:
    """ARGO-MNT-C: due items honour the real maintenance repository ordering."""

    async def test_due_maintenance_records_ordered_by_date_desc(self, workflow_env, db):
        """get_maintenance_records orders by ``date DESC, id DESC``."""
        world = build_argo_world(db)
        svc = FleetMaintenanceService(db)
        healthy = world["healthy_truck_ids"][0]

        # Insert records with distinct dates through the real service.
        svc.add_record(healthy, "oil_change", "2026-07-10", cost=100.0)
        svc.add_record(healthy, "brakes", "2026-07-15", cost=200.0)
        svc.add_record(healthy, "engine", "2026-07-12", cost=300.0)

        records = svc.get_records(truck_id=healthy)
        dates = [r["date"] for r in records]

        # The real repository's ORDER BY is date DESC, id DESC.
        assert dates == sorted(dates, reverse=True)
        assert records[0]["date"] == "2026-07-15"  # most recent first

    async def test_due_schedules_flagged_and_ordered_like_repo(self, workflow_env, db):
        """get_maintenance_schedules_with_overdue orders by truck_id, maintenance_type."""
        world = build_argo_world(db)
        svc = FleetMaintenanceService(db)
        repo = FleetRepository(db)
        h0, h1 = world["healthy_truck_ids"][0], world["healthy_truck_ids"][1]

        # Two overdue windows: fixed expiry in the past => overdue.
        svc.add_schedule(h0, "inspection", fixed_expiry_date="2020-01-01")
        svc.add_schedule(h1, "inspection", fixed_expiry_date="2020-01-01")

        due = repo.get_maintenance_schedules_with_overdue()

        # Every returned schedule is overdue per the shared threshold.
        assert len(due) >= 2
        assert all(r["overdue"] for r in due)

        # Ordering matches the repo's ORDER BY truck_id, maintenance_type.
        keys = [(r["truck_id"], r["maintenance_type"]) for r in due]
        assert keys == sorted(keys)