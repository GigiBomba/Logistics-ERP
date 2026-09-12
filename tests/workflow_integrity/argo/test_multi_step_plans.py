"""ARGO-P4-U5: Multi-step plan tests (blueprint §5.5, §8 scenario 10).

Deterministic by construction — the same ARGO fixtures as the sibling suites
(``build_argo_world`` / ``build_plan`` / ``make_step`` / ``make_tool_context``),
executed through the REAL executor (``backend.copilot.executor``) against the
REAL registry tools.  No planner, no LLM, no clocks in the assertion path.

Real executor methods used (verified signatures, ``backend/copilot/executor.py``):

* ``execute_plan(plan, services=None, on_step_update=None)``
* ``resume_plan(plan, services=None)``        — §13, gate: remaining tools must
  declare ``supports_resume`` (we pin that flag on the registry instances for the
  tool whose DB-only execution path we need — invoice tools are not among the
  §13 long-running Celery tools in production).
* ``stop_plan(plan, services=None)``          — §13, no capability gate.
* ``cancel_plan(plan, services=None)``        — marks remaining steps ``skipped``.

Real facts about the executor that shape these tests:

1. **`depends_on` is ordering metadata, not an executor gate.**  ``execute_plan``
   walks ``plan.steps`` in list order and never parameter-templates one step's
   output into the next.  A chain is therefore expressed as (a) steps ordered in
   dependency order with ``depends_on`` recorded, and (b) the caller feeding a
   downstream step the upstream ``step.result`` when the plan is re-entered —
   exactly how the router re-enters the executor (resume executes the remainder;
   ``execute_plan`` skips already-terminal steps).
2. **Pause halts the loop at a step boundary, not mid-step.**  The executor
   checks ``plan.paused`` before each step, so a pause that arrives while step 1
   is running halts *after* step 1 with the rest still ``pending``.  In-process
   that boundary event is delivered deterministically through the executor's
   real ``on_step_update`` callback (the same channel a supervisor would react
   to).  ``pause_plan`` itself only flips the flag and gate-checks §13 tools;
   the flag-driven loop behavior is what is exercised here.
3. **A failed step does not auto-skip later steps.**  §8 scenario 10 expects the
   plan to stop at the failed step and never run dependent steps; the real
   executor only stops when the supervisor sets ``paused`` at the boundary on a
   failure event, and ``cancel_plan`` is what turns the never-run remainder into
   the ``skipped`` terminal state.  That full path is what scenario C pins.
4. **`dispatch.create` cannot complete through ``execute_plan``** — its
   ``DispatchCreateParams`` cross-field validator runs before ``truck_id`` /
   ``driver_id`` validate, so the executor's params construction always fails
   (Gap 1, documented in ``test_autonomous_dispatch.py``).  Scenario D therefore
   performs the completed step-1 dispatch through the real tool body (the exact
   object ``execute_plan`` would call) with ``model_construct``, then rolls it
   back through a real ``system.undo`` executor step.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from backend.copilot.executor import (
    PlanStatus,
    cancel_plan,
    execute_plan,
    resume_plan,
    stop_plan,
)
from backend.copilot.schemas import ExecutionStep
from backend.copilot.tools import registry as tool_registry
from backend.copilot.tools.dispatch_tools import (
    DispatchCreateParams,
    DispatchCreateTool,
)
from backend.copilot.tools.invoice_tools import (
    InvoiceDraftParams,
    InvoiceDraftTool,
)

from tests.workflow_integrity.argo.fixtures import (
    build_argo_world,
    build_plan,
    make_step,
    make_tool_context,
    reset_circuit_breaker,
)
from tests.workflow_integrity.personas.fixtures import seed_trip

pytestmark = [pytest.mark.argo, pytest.mark.asyncio]

# §7 terminal step statuses (schema.py Literal) — used by the pause callbacks.
_TERMINAL = {"succeeded", "failed", "skipped", "stopped"}


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


# ── Shared deterministic helpers ──────────────────────────────────────────────

def _derived_plan_status(plan) -> PlanStatus:
    """Map a plan to its PlanStatus the way the router's ``_plan_response_status``
    does (§13 / §30, ``backend/api/v1/copilot_router.py``)."""
    if plan.paused:
        return PlanStatus.PAUSED
    if plan.requires_confirmation:
        return PlanStatus.AWAITING_CONFIRMATION
    if any(s.status in ("pending", "running", "paused") for s in plan.steps):
        return PlanStatus.EXECUTING
    if any(s.status in ("failed", "skipped", "stopped") for s in plan.steps):
        return PlanStatus.PARTIALLY_COMPLETED
    return PlanStatus.COMPLETED


def _admin_services(world: Dict[str, Any]) -> Dict[str, Any]:
    """Services dict for ``execute_plan``.

    ``user_id=0`` is the seeded system/admin identity — the ONLY identity the
    invoice service's permission layer accepts for invoice writes; ``role="admin"``
    clears the executor's §15 gate (including the admin-only ``system:undo``).
    """
    return {
        "db": world["db"],
        "company_id": world["company_id"],
        "user_id": 0,
        "role": "admin",
    }


def _draft_params(db, trip_id: int) -> Dict[str, Any]:
    """Deterministic ``invoice.draft`` params for a seeded trip row."""
    row = db.conn.execute(
        "SELECT client_id, total_price_eur FROM trips WHERE id = ?", (trip_id,)
    ).fetchone()
    assert row is not None, f"trip #{trip_id} missing"
    return {
        "client_id": row["client_id"],
        "trip_id": trip_id,
        "amount": float(row["total_price_eur"]),
    }


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


def _dispatch_ctx(db, world):
    """ToolExecutionContext for the ARGO world (Ana, the dispatcher)."""
    return make_tool_context(
        db,
        company_id=world["company_id"],
        user_id=world["user_id"],
        role="dispatcher",
    )


def _dispatch_params(trip_id: int, truck_id=None, driver_id=None) -> DispatchCreateParams:
    """Build ``dispatch.create`` params, bypassing the broken cross-field validator.

    Gap 1 (see test_autonomous_dispatch.py): ``DispatchCreateParams(...)`` raises on
    every construction; ``model_construct`` skips only that broken validator.
    """
    return DispatchCreateParams.model_construct(
        trip_id=trip_id, truck_id=truck_id, driver_id=driver_id
    )


def _invoice_count(db) -> int:
    return db.conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]


def _pause_when(plan_holder: List[Any], step_id: str, when: set):
    """Return an ``on_step_update`` callback that pauses the plan at a boundary.

    Mirrors §13: a pause that arrives while a step runs only takes effect at the
    next step boundary, because ``execute_plan`` checks ``plan.paused`` before
    each step.
    """
    def _callback(updated_step_id: str, status: str, tool_name: str) -> None:
        if updated_step_id == step_id and status in when:
            plan_holder[0].paused = True
    return _callback


# ═════════════════════════════════════════════════════════════════════════════
# Scenario A — dependency chain: list → draft → pdf (§5.5 "end-of-day closeout")
# ═════════════════════════════════════════════════════════════════════════════

class TestMultiStepDependencyChain:
    """ARGO-MSP-A: dependent steps run in order; downstream consumes upstream."""

    async def test_dependency_chain_draft_output_feeds_pdf_step(self, db):
        """trip.list → invoice.draft → invoice.generate_pdf, in dependency order.

        The executor walks the plan in dependency order and records every step's
        result on the step; the PDF step's only valid input is the invoice_id the
        draft step produced, so the chain proves downstream runs after upstream
        succeeded.  A real PDF is never written — the generator seam is patched
        exactly like test_autonomous_invoicing.py.
        """
        world = build_argo_world(db)
        services = _admin_services(world)
        t1 = world["delivered_trip_ids"][0]
        assert _invoice_count(db) == 0

        list_step = make_step("trip.list", {"limit": 200, "offset": 0},
                              step_id="u5a-list")
        draft_step = make_step("invoice.draft", _draft_params(db, t1),
                               step_id="u5a-draft", depends_on=["u5a-list"])

        # Pass 1 — the plan contains only the steps whose inputs are known.
        plan = build_plan(
            "p4-u5-a",
            [list_step, draft_step],
            intent_name="invoice.end_of_day_closeout",
        )
        assert plan.steps[0].depends_on == []
        assert plan.steps[1].depends_on == ["u5a-list"]

        executed = await execute_plan(plan, services=services)

        # Upstream (trip.list) succeeded first and its result is preserved.
        assert [s.status for s in executed.steps] == ["succeeded", "succeeded"]
        list_result = executed.steps[0].result
        assert list_result is not None and list_result["status"] == "success"
        listed_ids = {row["id"] for row in list_result["data"]["trips"]}
        assert t1 in listed_ids, "step-1 result must expose the delivered trip"

        # Downstream (invoice.draft) ran only after step 1 and produced a draft.
        draft_result = executed.steps[1].result
        assert draft_result is not None and draft_result["status"] == "success"
        assert draft_result["data"]["status"] == "draft"
        invoice_id = int(draft_result["data"]["invoice_id"])
        row = db.conn.execute(
            "SELECT id, trip_id, status FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
        assert row is not None and row["trip_id"] == t1 and row["status"] == "draft"
        assert _invoice_count(db) == 1

        # Pass 2 — the PDF step's parameter is the invoice the draft produced;
        # the executor skips the already-terminal steps and runs only the PDF.
        pdf_step = make_step("invoice.generate_pdf", {"invoice_id": invoice_id},
                             step_id="u5a-pdf", depends_on=["u5a-draft"])
        plan2 = build_plan(
            "p4-u5-a-pass2",
            [executed.steps[0], executed.steps[1], pdf_step],
            intent_name="invoice.end_of_day_closeout",
        )
        assert plan2.steps[2].status == "pending"
        assert plan2.steps[2].depends_on == ["u5a-draft"]

        with patch(
            "services.invoicing.generator.InvoiceGenerator.generate",
            return_value="invoices/p4_u5_chain_test.pdf",
        ) as gen:
            done = await execute_plan(plan2, services=services)

        gen.assert_called_once()  # the pdf ran exactly once, after the draft
        assert [s.status for s in done.steps] == ["succeeded", "succeeded", "succeeded"]
        pdf_result = done.steps[2].result
        assert pdf_result is not None
        assert pdf_result["data"]["file_path"] == "invoices/p4_u5_chain_test.pdf"
        pdf_row = db.conn.execute(
            "SELECT pdf_path, status FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
        assert pdf_row["pdf_path"] == "invoices/p4_u5_chain_test.pdf"
        assert pdf_row["status"] == "draft"  # pdf step never mutates status
        assert _invoice_count(db) == 1       # no phantom invoices
        assert _derived_plan_status(done) == PlanStatus.COMPLETED

    async def test_pdf_step_cannot_run_before_draft_provides_invoice(self, db):
        """A PDF step with no upstream draft has no invoice to render → fails.

        Pins the dependency in the other direction: ``invoice.generate_pdf``
        cannot succeed before the draft step exists, so a well-formed chain must
        execute it only after the draft step succeeded.
        """
        world = build_argo_world(db)
        services = _admin_services(world)

        plan = build_plan(
            "p4-u5-a-probe",
            [make_step("invoice.generate_pdf", {"invoice_id": 999999},
                       step_id="u5a-probe-pdf", depends_on=["u5a-probe-draft"])],
            intent_name="invoice.generate_pdf",
        )
        executed = await execute_plan(plan, services=services)

        step = executed.steps[0]
        assert step.status == "failed"
        assert step.error == "copilot.error.service_error"
        assert step.result is not None
        assert "not found" in step.result["message_params"]["detail"].lower()
        assert _invoice_count(db) == 0


# ═════════════════════════════════════════════════════════════════════════════
# Scenario B — §13 pause / resume / stop
# ═════════════════════════════════════════════════════════════════════════════

class TestPauseResumeAndStop:
    """ARGO-MSP-B: a paused plan halts after step 1; resume completes it;
    stop marks the remaining steps stopped."""

    async def test_paused_plan_halts_after_step_one_and_resume_completes(
        self, db, monkeypatch
    ):
        """Pause event at the step boundary → steps 2/3 untouched; resume + a
        fresh executor pass completes them (§8 scenario 10 recovery)."""
        world = build_argo_world(db)
        services = _admin_services(world)
        t1, t2 = world["delivered_trip_ids"][:2]

        # §13 resume gate: resume_plan refuses plans whose remaining tool lacks
        # supports_resume.  Pin that capability on the registry's real
        # invoice.draft instance for the tool whose DB path we execute.
        monkeypatch.setattr(
            tool_registry.get_tool("invoice.draft"), "supports_resume", True
        )

        steps = [
            make_step("trip.list", {"limit": 200, "offset": 0}, step_id="u5b-list"),
            make_step("invoice.draft", _draft_params(db, t1), step_id="u5b-draft",
                      depends_on=["u5b-list"]),
            make_step("invoice.draft", _draft_params(db, t2), step_id="u5b-final",
                      depends_on=["u5b-draft"]),
        ]
        plan = build_plan("p4-u5-b-pause", steps, intent_name="invoice.batch_draft")
        holder = [plan]

        halted = await execute_plan(
            plan,
            services=services,
            on_step_update=_pause_when(holder, "u5b-list", _TERMINAL),
        )

        # Halted after step 1 — remaining steps untouched, plan paused (§13).
        assert [s.status for s in halted.steps] == ["succeeded", "pending", "pending"]
        assert halted.paused is True
        assert _derived_plan_status(halted) == PlanStatus.PAUSED
        assert halted.steps[0].result is not None
        assert halted.steps[1].result is None  # step 2 never started

        # Resume via the real executor function, then re-enter the executor —
        # the router's resume flow (do_resume + do_execute).
        resumed = await resume_plan(halted, services=services)
        assert resumed.paused is False

        done = await execute_plan(resumed, services=services)
        assert [s.status for s in done.steps] == ["succeeded", "succeeded", "succeeded"]
        assert _derived_plan_status(done) == PlanStatus.COMPLETED
        assert _invoice_count(db) == 2  # both drafts, no duplicates

    async def test_stop_marks_remaining_steps_stopped(self, db):
        """stop_plan permanently marks the untouched remainder stopped while the
        completed step-1 result stays valid (executor ``stop_plan``)."""
        world = build_argo_world(db)
        services = _admin_services(world)
        t1, t2 = world["delivered_trip_ids"][:2]

        steps = [
            make_step("trip.list", {"limit": 200, "offset": 0}, step_id="u5s-list"),
            make_step("invoice.draft", _draft_params(db, t1), step_id="u5s-draft",
                      depends_on=["u5s-list"]),
            make_step("invoice.draft", _draft_params(db, t2), step_id="u5s-final",
                      depends_on=["u5s-draft"]),
        ]
        plan = build_plan("p4-u5-b-stop", steps, intent_name="invoice.batch_draft")
        holder = [plan]

        halted = await execute_plan(
            plan,
            services=services,
            on_step_update=_pause_when(holder, "u5s-list", _TERMINAL),
        )
        assert [s.status for s in halted.steps] == ["succeeded", "pending", "pending"]

        stopped = await stop_plan(halted, services=services)

        # Intentional stop: completed step preserved, remainder terminal-stopped.
        assert stopped.paused is False
        assert [s.status for s in stopped.steps] == ["succeeded", "stopped", "stopped"]
        assert stopped.steps[0].result is not None
        assert stopped.steps[1].finished_at is not None
        assert stopped.steps[2].finished_at is not None
        # PlanStatus has no FAILED member — a plan with a stopped/failed step
        # maps to PARTIALLY_COMPLETED (router _plan_response_status semantics).
        assert _derived_plan_status(stopped) == PlanStatus.PARTIALLY_COMPLETED

        # Nothing further executes on re-entry — stopped is terminal.
        again = await execute_plan(stopped, services=services)
        assert [s.status for s in again.steps] == ["succeeded", "stopped", "stopped"]
        # Only the completed read-only step (trip.list) ran before the stop —
        # no write ever reached the database.
        assert _invoice_count(db) == 0


# ═════════════════════════════════════════════════════════════════════════════
# Scenario C — end-of-day closeout with an injected mid-plan failure
# ═════════════════════════════════════════════════════════════════════════════

class TestEndOfDayCloseoutFailure:
    """ARGO-MSP-C (§5.5 closeout / §8 scenario 10): list delivered → draft →
    analytics.  An injected step-2 failure halts the plan; the never-run
    analytics step is cancelled to ``skipped``; step-1 results stay valid."""

    async def test_injected_draft_failure_skips_dependent_analytics_step(self, db):
        """A second closeout run (invoice already drafted) fails the draft step
        deterministically; the dependent analytics step is never executed and is
        finally marked ``skipped``; the listing results remain valid."""
        world = build_argo_world(db)
        services = _admin_services(world)
        t1 = world["delivered_trip_ids"][0]

        # Pre-existing invoice = injected step-2 failure for this closeout run
        # (the real idempotency guard is the UNIQUE constraint on invoices.trip_id).
        ctx = make_tool_context(db, world["company_id"], user_id=0, role="admin")
        seeded = await InvoiceDraftTool().execute(
            InvoiceDraftParams(**_draft_params(db, t1)), ctx
        )
        assert seeded.status == "success", seeded
        assert _invoice_count(db) == 1

        steps = [
            make_step("trip.list", {"limit": 200, "offset": 0}, step_id="u5c-list"),
            make_step("invoice.draft", _draft_params(db, t1), step_id="u5c-draft",
                      depends_on=["u5c-list"]),
            # "analytics/update" — no analytics.write tool exists in the registry;
            # the real read facade is the closest registered analytics step.
            make_step("analytics.query", {"domain": "trip_status"},
                      step_id="u5c-analytics", depends_on=["u5c-draft"]),
        ]
        plan = build_plan(
            "p4-u5-c",
            steps,
            intent_name="invoice.end_of_day_closeout",
        )
        holder = [plan]

        # §8 scenario 10: the supervisor halts the plan when a step fails, so the
        # dependent steps never execute (executor only stops at step boundaries).
        halted = await execute_plan(
            plan,
            services=services,
            on_step_update=_pause_when(holder, "u5c-draft", {"failed"}),
        )

        assert [s.status for s in halted.steps] == ["succeeded", "failed", "pending"]
        assert halted.paused is True

        # Step 2 failed for the real reason — duplicate invoice on the same trip.
        failed = halted.steps[1]
        assert failed.error == "copilot.error.internal"
        assert failed.result is not None
        assert "UNIQUE constraint failed: invoices.trip_id" in failed.result[
            "message_params"
        ]["error"]

        # Step 1 (list delivered trips) remains valid — its results are intact.
        list_result = halted.steps[0].result
        assert list_result is not None and list_result["status"] == "success"
        listed_ids = {row["id"] for row in list_result["data"]["trips"]}
        assert t1 in listed_ids

        # Step 3 (analytics) was never executed — still pending, no result.
        assert halted.steps[2].result is None

        # The caller cancels the broken remainder → the dependent step is
        # skipped; the plan is partially completed (no PlanStatus.FAILED member).
        final = await cancel_plan(halted, services=services)
        assert [s.status for s in final.steps] == ["succeeded", "failed", "skipped"]
        assert _derived_plan_status(final) == PlanStatus.PARTIALLY_COMPLETED

        # No phantom work: still exactly one invoice, the seeded draft.
        assert _invoice_count(db) == 1


# ═════════════════════════════════════════════════════════════════════════════
# Scenario D — rollback after a partial failure (§8 scenario 10 item 7)
# ═════════════════════════════════════════════════════════════════════════════

class TestRollbackDispatchAfterPartialFailure:
    """ARGO-MSP-D: a completed step-1 dispatch is rolled back cleanly through a
    real ``system.undo`` executor step after a later plan step fails.

    ``dispatch.create`` cannot complete through ``execute_plan`` (params-schema
    gap, see test_autonomous_dispatch.py), so the completed dispatch is performed
    through the real ``DispatchCreateTool`` body — the same object the executor
    calls — and ``system.undo`` is driven with the REAL JSON undo token
    ``dispatch.create`` now emits (Gap 4 fixed in test_autonomous_dispatch.py).
    """

    async def test_system_undo_rolls_back_completed_dispatch(self, db):
        world = build_argo_world(db)
        services = _admin_services(world)
        trip_id = _new_planned_trip(db, world)

        _TRIP_COLUMNS = "truck_id, truck_number, driver_id, driver_name, status"
        before = dict(
            db.conn.execute(
                f"SELECT {_TRIP_COLUMNS} FROM trips WHERE id = ?", (trip_id,)
            ).fetchone()
        )

        # ── Completed step-1 dispatch (real tool + real DispatchService path) ──
        truck_id = world["healthy_truck_ids"][0]
        driver_id = world["driver_ids"][0]
        created = await DispatchCreateTool().execute(
            _dispatch_params(trip_id, truck_id, driver_id),
            _dispatch_ctx(db, world),
        )
        assert created.status == "success", created
        # Gap 4 is fixed: assign_both emits a real JSON undo token — drive
        # system.undo with the REAL token from dispatch.create.
        assert created.undo_token is not None
        token = created.undo_token

        # ── A later plan fails mid-way (duplicate invoice.draft on the trip) ──
        draft_params = {
            "client_id": world["client_ids"][0],
            "trip_id": trip_id,
            "amount": 400.0,
        }
        failing_plan = build_plan(
            "p4-u5-d",
            [
                make_step("invoice.draft", draft_params, step_id="u5d-draft-1"),
                make_step("invoice.draft", draft_params, step_id="u5d-draft-2",
                          depends_on=["u5d-draft-1"]),
            ],
            intent_name="invoice.batch_draft",
        )
        executed = await execute_plan(failing_plan, services=services)
        assert [s.status for s in executed.steps] == ["succeeded", "failed"]
        assert executed.steps[1].result is not None
        assert "UNIQUE constraint failed" in executed.steps[1].result[
            "message_params"
        ]["error"]
        assert _derived_plan_status(executed) == PlanStatus.PARTIALLY_COMPLETED

        # ── Rollback: real system.undo executor step restores the trip ──
        undo_plan = build_plan(
            "p4-u5-d-undo",
            [make_step("system.undo",
                       {"undo_token": token, "tool_name": "dispatch.create"},
                       step_id="u5d-undo")],
            intent_name="dispatch.create",
        )
        undone = await execute_plan(undo_plan, services=services)
        assert [s.status for s in undone.steps] == ["succeeded"]

        after = dict(
            db.conn.execute(
                f"SELECT {_TRIP_COLUMNS} FROM trips WHERE id = ?", (trip_id,)
            ).fetchone()
        )
        assert after == before  # clean rollback — no partial state

        # Partial work that triggered the rollback is left intact (not phantom-
        # rolled-back): the draft invoice for the trip still exists.
        invoice_row = db.conn.execute(
            "SELECT id, status FROM invoices WHERE trip_id = ?", (trip_id,)
        ).fetchone()
        assert invoice_row is not None
        assert invoice_row["status"] == "draft"
