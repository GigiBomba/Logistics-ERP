"""ARGO-DISP: §5.1 autonomous dispatch — best-truck dispatch, maintenance blocks, bulk assign, undo.

Deterministic by construction: plans/worlds are built DIRECTLY from the ARGO
fixtures (``build_argo_world`` / ``build_plan`` / ``make_step`` /
``make_tool_context``) — never through the planner, never an LLM.  The
executor's Celery broker check is pinned off so every step runs in-process
against the SQLite harness.

Real tool classes exercised (registry-backed, same code the executor calls):

* ``DispatchCreateTool``     — ``dispatch.create``  (``dispatch_tools.py``)
  wraps ``DispatchService.assign_both`` → real ``assign_truck`` /
  ``assign_driver`` + ``AvailabilityChecker`` + ``TripService.update``.
* ``DispatchBulkAssignTool`` — ``dispatch.bulk_assign`` (``dispatch_tools.py``)
  wraps ``DispatchService.bulk_assign_truck``.
* ``UndoActionTool``         — ``system.undo``      (``undo_tools.py``)
  delegates to ``DispatchCreateTool.undo`` → ``TripService.update``.

Documented gaps (characterized by the ``test_gap_*`` tests — flip when fixed):

1. **`DispatchCreateParams` is unconstructable.**  Its ``trip_id``
   cross-field validator runs before ``truck_id``/``driver_id`` are
   validated, so ``info.data`` never contains them and EVERY construction
   raises ("At least one of truck_id or driver_id must be provided").  The
   executor therefore fails every ``dispatch.create`` step; the tool bodies
   below are exercised with ``model_construct`` (bypasses only the broken
   validator — service code is untouched).
2. **The availability gate only blocked ``status == 'In Service'``** — that is
   the DB's canonical maintenance status (``schema.py``); the ARGO world's
   lowercase ``'maintenance'`` string was silently dispatchable (§5.9
   "maintenance blocks" / GR7).  **Fixed**: ``check_truck`` now blocks every
   maintenance/blocked status (incl. ``'maintenance'``) and ``active_status=0``.
3. **`bulk_assign_*` was per-item, not all-or-nothing** (D-INV-05 gap).
   **Fixed**: each batch now runs inside a repository ``transaction()`` — any
   failing trip rolls the whole batch back, so a partial failure leaves NO
   trip assigned.
4. **`assign_both` never emitted an undo token** (``undo_token=None``), and the
   per-assignment tokens ``assign_truck``/``assign_driver`` DO create serialized
   to a Python ``str()`` that ``json.loads`` cannot parse.  **Fixed**:
   ``assign_both`` now returns a composite ``UndoToken`` snapshotted before any
   assignment, and ``UndoToken.__str__`` returns JSON — so ``dispatch.create``'s
   real token round-trips through ``system.undo`` end to end.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from backend.copilot.executor import (
    UNDO_WINDOW_MINUTES,
    _check_tool_permission,
    execute_plan,
    is_undo_expired,
)
from backend.copilot.tools.dispatch_tools import (
    BulkAssignParams,
    DispatchBulkAssignTool,
    DispatchCreateParams,
    DispatchCreateTool,
)
from backend.copilot.tools.undo_tools import UndoActionParams, UndoActionTool

from tests.workflow_integrity.argo.fixtures import (
    build_argo_world,
    build_plan,
    make_step,
    make_tool_context,
    reset_circuit_breaker,
)
from tests.workflow_integrity.personas.fixtures import seed_trip

pytestmark = pytest.mark.argo


# ── Autouse hygiene ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _force_inline_execution():
    """Pin the executor's §13 Celery gate off so steps never leave-process."""
    with patch("backend.copilot.executor._is_celery_broker_available", return_value=False):
        yield


@pytest.fixture(autouse=True)
def _reset_circuit_breaker_after():
    """CircuitBreaker state is class-level — never leak into the next test."""
    yield
    reset_circuit_breaker()


# ── Deterministic helpers ─────────────────────────────────────────────────────

def _run(coro):
    """Run one async tool/executor call inside a fresh event loop."""
    return asyncio.run(coro)


def _new_planned_trip(db, world) -> int:
    """Insert a fresh, unassigned Planned trip to use as a dispatch target."""
    return seed_trip(
        db,
        company_id=world["company_id"],
        client_id=world["client_ids"][0],
        client_name=f"Client {world['client_ids'][0]}",
        driver_name="",
        driver_id=None,
        truck_number="",
        truck_id=None,
        distance_km=100.0,
        total_price_eur=400.0,
        status="Planned",
        net_profit=200.0,
        rate_per_km=4.0,
        gross_per_km=2.0,
    )


def _dispatch_ctx(db, world, *, role="dispatcher"):
    """ToolExecutionContext for the ARGO world (Ana, the dispatcher by default)."""
    return make_tool_context(
        db,
        company_id=world["company_id"],
        user_id=world["user_id"],
        role=role,
    )


def _create_params(trip_id: int, truck_id=None, driver_id=None) -> DispatchCreateParams:
    """Build ``dispatch.create`` params through the real (fixed) schema.

    Gap 1 is fixed: the cross-field ``@model_validator`` runs AFTER all fields
    are validated, so ``DispatchCreateParams(...)`` constructs directly and the
    tool's real validation/service code is exercised end to end.
    """
    return DispatchCreateParams(trip_id=trip_id, truck_id=truck_id, driver_id=driver_id)


# ═════════════════════════════════════════════════════════════════════════════
# Scenario A — best-truck dispatch
# ═════════════════════════════════════════════════════════════════════════════

class TestBestTruckDispatch:
    """ARGO-DISP-A: a dispatch plan selects the best truck and assigns it."""

    def test_dispatch_create_assigns_best_truck_and_driver(self, db):
        """Highest-margin freight load gets the fleet's best (lowest-mileage) truck."""
        world = build_argo_world(db)
        tool = DispatchCreateTool()
        ctx = _dispatch_ctx(db, world)

        # "Best truck": lowest mileage among the healthy fleet — deterministic.
        mileages = {
            tid: db.conn.execute(
                "SELECT mileage FROM trucks WHERE id = ?", (tid,)
            ).fetchone()[0]
            for tid in world["healthy_truck_ids"]
        }
        best_truck = min(mileages, key=mileages.get)

        # "Best load": highest margin among the seeded freight loads.
        best_load = max(world["freight_loads"], key=lambda load: load["margin_pct"])
        trip_id = best_load["trip_id"]
        driver_id = world["driver_ids"][0]

        result = _run(tool.execute(_create_params(trip_id, best_truck, driver_id), ctx))

        assert result.status == "success", result
        assert result.data["trip_id"] == trip_id
        assert result.data["truck_id"] == best_truck
        assert result.data["driver_id"] == driver_id

        row = db.conn.execute(
            "SELECT truck_id, truck_number, driver_id, driver_name, status "
            "FROM trips WHERE id = ?",
            (trip_id,),
        ).fetchone()
        # The trip row gains the truck + driver...
        assert row["truck_id"] == best_truck
        assert row["driver_id"] == driver_id
        assert row["driver_name"] == f"Driver Ana-{world['driver_ids'].index(driver_id) + 1:02d}"
        # ...and its status stays a legal (non-terminal) dispatch state.
        assert row["status"] == "Planned"
        # Real quirk: DispatchService falls back to str(truck_id) for the plate,
        # so truck_number is set but to the id, not the plate.  Documented gap.
        assert row["truck_number"] is not None

    def test_dispatch_create_params_schema_accepts_xor_rejects_neither(self, db):
        """Gap 1 fixed: the real params schema constructs for valid inputs.

        ``DispatchCreateParams``'s cross-field ``@model_validator`` now runs
        AFTER all fields are validated, so truck-only and driver-only
        constructions succeed; only a neither-provided construction raises.
        """
        # truck XOR driver → accepted.
        p = DispatchCreateParams(trip_id=5, truck_id=7)
        assert p.truck_id == 7 and p.driver_id is None
        p = DispatchCreateParams(trip_id=5, driver_id=3)
        assert p.truck_id is None and p.driver_id == 3
        # Both provided is also legal.
        assert DispatchCreateParams(trip_id=5, truck_id=7, driver_id=3)
        # Neither → still rejected.
        with pytest.raises(ValueError, match="At least one of truck_id or driver_id"):
            DispatchCreateParams(trip_id=5)

    def test_dispatch_plan_via_executor_succeeds_on_params_schema(self, db):
        """Executor-level proof Gap 1 is fixed: the plan dispatches end to end.

        A ``dispatch.create`` plan built through the fixtures (same shape the
        planner would produce) now passes the real parameter schema and the step
        ends ``success`` — the trip row gains the assigned truck and driver.
        """
        world = build_argo_world(db)
        trip_id = _new_planned_trip(db, world)

        plan = build_plan(
            "p4-u1-exec-dispatch",
            [
                make_step(
                    "dispatch.create",
                    {
                        "trip_id": trip_id,
                        "truck_id": world["healthy_truck_ids"][0],
                        "driver_id": world["driver_ids"][0],
                    },
                )
            ],
            intent_name="dispatch.create",
        )
        services = {
            "db": db,
            "company_id": world["company_id"],
            "user_id": world["user_id"],
            "role": "dispatcher",
        }
        try:
            executed = _run(execute_plan(plan, services=services))
        finally:
            reset_circuit_breaker()

        step = executed.steps[0]
        assert step.status == "succeeded", step

        row = db.conn.execute(
            "SELECT truck_id, driver_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["truck_id"] == world["healthy_truck_ids"][0]
        assert row["driver_id"] == world["driver_ids"][0]


# ═════════════════════════════════════════════════════════════════════════════
# Scenario B — maintenance-blocked truck
# ═════════════════════════════════════════════════════════════════════════════

class TestMaintenanceBlockedDispatch:
    """ARGO-DISP-B: the CRITICAL-maintenance truck must never be dispatched."""

    def test_dispatch_create_rejects_in_service_maintenance_truck(self, db):
        """The real availability gate blocks the maintenance truck (no write)."""
        world = build_argo_world(db)
        maint_truck = world["maintenance_truck_id"]

        # AvailabilityChecker only recognizes the canonical maintenance status
        # ('In Service' — see schema.py's trucks.status comment).  Pin the world's
        # CRITICAL truck to that state so the REAL guard fires.
        db.conn.execute(
            "UPDATE trucks SET status = 'In Service' WHERE id = ?", (maint_truck,)
        )
        db.conn.commit()

        trip_id = _new_planned_trip(db, world)
        tool = DispatchCreateTool()
        result = _run(
            tool.execute(
                _create_params(trip_id, maint_truck, world["driver_ids"][0]),
                _dispatch_ctx(db, world),
            )
        )

        # The real guard: ResourceUnavailableError → failed, and nothing written.
        assert result.status == "failed", result
        assert "Truck is not available (blocked state)" in result.message_params["error"]

        row = db.conn.execute(
            "SELECT truck_id, driver_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["truck_id"] is None
        assert row["driver_id"] is None

    def test_maintenance_status_truck_is_blocked(self, db):
        """The as-seeded maintenance truck is refused by the availability gate.

        The ARGO world inserts the CRITICAL truck with ``status='maintenance'``
        and ``active_status=0``.  ``AvailabilityChecker.check_truck`` now
        blocks every maintenance/blocked status and any ``active_status=0``
        truck, so the real guard refuses the dispatch and no assignment row is
        written (§5.9 "maintenance blocks" / GR7).
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
        result = _run(
            tool.execute(
                _create_params(trip_id, maint_truck, world["driver_ids"][0]),
                _dispatch_ctx(db, world),
            )
        )

        assert result.status == "failed", result
        row = db.conn.execute(
            "SELECT truck_id, driver_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["truck_id"] is None
        assert row["driver_id"] is None


# ═════════════════════════════════════════════════════════════════════════════
# Scenario C — bulk assign partial failure
# ═════════════════════════════════════════════════════════════════════════════

class TestBulkAssignPartialFailure:
    """ARGO-DISP-C: bulk dispatch is all-or-nothing — no partial commits."""

    def test_bulk_assign_partial_failure_rolls_back_whole_batch(self, db):
        """One injectable failure → the whole batch rolls back and reports it.

        D-INV-05 fixed: ``bulk_assign_*`` runs the batch inside a repository
        transaction, so the assignment made for the OK trip is rolled back
        (``truck_id`` is ``None``) and the result reports the failure with
        per-item entries (``success_count == 0``).
        """
        world = build_argo_world(db)
        tool = DispatchBulkAssignTool()
        ctx = _dispatch_ctx(db, world)

        trip_ok = _new_planned_trip(db, world)
        trip_missing = 999999  # deterministic per-item failure
        truck_id = world["healthy_truck_ids"][0]

        result = _run(
            tool.execute(
                BulkAssignParams(
                    trip_ids=[trip_ok, trip_missing],
                    assign_type="truck",
                    assign_id=truck_id,
                ),
                ctx,
            )
        )

        # Tool contract intact: per-item counts + failures are still reported.
        assert result.status == "success", result
        data = result.data
        assert data["total"] == 2
        assert data["success_count"] == 0
        assert data["failed_count"] == 2
        assert {
            "trip_id": trip_missing,
            "error": f"Trip #{trip_missing} not found",
        } in data["failures"]

        # All-or-nothing DB truth: the OK trip's assignment was ROLLED BACK.
        row = db.conn.execute(
            "SELECT truck_id FROM trips WHERE id = ?", (trip_ok,)
        ).fetchone()
        assert row["truck_id"] is None


# ═════════════════════════════════════════════════════════════════════════════
# Scenario D — undo
# ═════════════════════════════════════════════════════════════════════════════

class TestUndoDispatch:
    """ARGO-DISP-D: dispatch is reversible; stale/forged tokens are rejected."""

    def test_undo_dispatch_restores_previous_state(self, db):
        """system.undo reverts a completed dispatch through the real undo path."""
        world = build_argo_world(db)
        tool = DispatchCreateTool()
        ctx = _dispatch_ctx(db, world)

        trip_id = _new_planned_trip(db, world)
        before = dict(
            db.conn.execute(
                "SELECT truck_id, truck_number, driver_id, driver_name, status "
                "FROM trips WHERE id = ?",
                (trip_id,),
            ).fetchone()
        )

        truck_id = world["healthy_truck_ids"][0]
        driver_id = world["driver_ids"][0]
        created = _run(
            tool.execute(_create_params(trip_id, truck_id, driver_id), ctx)
        )
        assert created.status == "success", created
        # Gap 4 is fixed: the real assign_both now emits a JSON undo token.
        assert created.undo_token is not None
        token = created.undo_token
        parsed = json.loads(token)
        assert parsed["trip_id"] == trip_id
        assert parsed["operation"] == "assign_both"
        # The token records the exact pre-assignment state we snapshotted.
        assert parsed["previous_state"] == before

        # system.undo is admin-only in the permission matrix.
        assert _check_tool_permission(UndoActionTool(), "dispatcher") is False

        undo_ctx = _dispatch_ctx(db, world, role="admin")
        undone = _run(
            UndoActionTool().execute(
                UndoActionParams(undo_token=token, tool_name="dispatch.create"),
                undo_ctx,
            )
        )

        assert undone.status == "success", undone
        after = dict(
            db.conn.execute(
                "SELECT truck_id, truck_number, driver_id, driver_name, status "
                "FROM trips WHERE id = ?",
                (trip_id,),
            ).fetchone()
        )
        assert after == before

    def test_forged_or_expired_undo_is_rejected(self, db):
        """Forged tokens fail json parsing; stale actions trip the undo window."""
        world = build_argo_world(db)
        undo_ctx = _dispatch_ctx(db, world, role="admin")

        # (a) Forged token — not JSON → rejected by the real undo() path.
        forged = _run(
            UndoActionTool().execute(
                UndoActionParams(undo_token="forged-token", tool_name="dispatch.create"),
                undo_ctx,
            )
        )
        assert forged.status == "failed"
        assert forged.message_key == "copilot.undo.invalid_token"

        # (b) The real expiry check (executor.is_undo_expired, used by the undo
        #     route) rejects actions older than the ~30-minute window.
        fresh = datetime.utcnow() - timedelta(minutes=UNDO_WINDOW_MINUTES - 25)
        stale = datetime.utcnow() - timedelta(minutes=UNDO_WINDOW_MINUTES + 1)
        assert UNDO_WINDOW_MINUTES == 30
        assert is_undo_expired(fresh) is False, "fresh action must be undoable"
        assert is_undo_expired(stale) is True, "31-minute-old action must be rejected"