"""ARGO-FAIL: §5.6 failure modes — tool raise, guardrails, permissions, destructive confirmation, graph cap.

Deterministic by construction: plans/worlds are built DIRECTLY from the ARGO
fixtures (``build_argo_world`` / ``build_plan`` / ``make_step`` /
``make_tool_context``) — never through the planner, never an LLM.  The
executor's Celery broker check is pinned off so every step runs in-process
against the SQLite harness.

Real executor code exercised (``backend/copilot/executor.py``):

* ``MAX_TOOL_CALLS_PER_PLAN`` (20) / ``MAX_REASONING_GRAPH_NODES_PER_TURN``
  (50) — the §23.3 ceilings enforced by ``validate_guardrails``.
* ``validate_guardrails(plan) -> List[str]`` — real return shape is a list of
  i18n keys (``copilot.error.too_many_steps``,
  ``copilot.error.too_many_graph_nodes``, ``copilot.error.too_many_tokens``).
* ``classify_error`` / ``ErrorCategory`` (``TRANSIENT`` / ``DETERMINISTIC``)
  — the §28.1 classifier that decides whether a raised tool error is retried.
* ``_check_tool_permission(tool, role)`` — the §15 gate that denies a
  low-privilege role BEFORE the tool ever runs.
* ``execute_plan`` / ``confirm_and_execute`` — the state-machine execution
  paths.

Real tool classes exercised (registry-backed, same code the executor calls):

* ``TripGetTool``        — ``trip.get``        (SAFE, ``trips:read``)
* ``DispatchCreateTool`` — ``dispatch.create`` (BUSINESS, ``dispatch:write``)
* ``DispatchCancelTool`` — ``dispatch.cancel`` (DESTRUCTIVE, ``dispatch:write``)

Documented gaps (characterized by the ``test_gap_*`` tests — flip when fixed):

1. **~~The executor has no confirmation gate~~ — FIXED.**  ``execute_plan`` now
   refuses DESTRUCTIVE plans whose ``requires_confirmation=True`` is still set:
   every step is marked skipped with the ``copilot.timeline.confirmation_needed``
   key and nothing executes (defense-in-depth behind the router gate, which
   persists such plans and only runs them via POST ``/plans/{id}/confirm`` →
   ``confirm_and_execute`` — see ``backend/api/v1/copilot_router.py``).  The
   typed confirmation phrase itself is a UI-layer concern (§5.6 — skipped
   here, nothing executable at this layer).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.copilot.executor import (
    ErrorCategory,
    MAX_REASONING_GRAPH_NODES_PER_TURN,
    MAX_TOOL_CALLS_PER_PLAN,
    _check_tool_permission,
    classify_error,
    confirm_and_execute,
    execute_plan,
    validate_guardrails,
)
from backend.copilot.schemas import ConfirmationLevel
from backend.copilot.tools.dispatch_tools import (
    DispatchCancelTool,
    DispatchCreateTool,
)
from backend.copilot.tools.trip_tools import TripGetTool

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
    """Run one async executor call inside a fresh event loop."""
    return asyncio.run(coro)


def _new_planned_trip(db, world) -> int:
    """Insert a fresh, unassigned Planned trip to use as a dispatch/cancel target."""
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


def _services(db, world, *, role: str = "dispatcher") -> dict:
    """Executor ``services`` dict for the ARGO world (dispatcher by default)."""
    return {
        "db": db,
        "company_id": world["company_id"],
        "user_id": world["user_id"],
        "role": role,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Scenario A — a tool raises mid-execution
# ═════════════════════════════════════════════════════════════════════════════

class TestScenarioA_ToolRaises:
    """ARGO-FAIL-A: a raising tool ends the step failed with the classified category.

    Real path: the executor gates the permission, validates params, then calls
    the tool via ``_run_step_with_retry``, which feeds the exception to
    ``classify_error`` (§28.1).  Deterministic errors are never retried;
    transient errors get exactly one retry.  Either way the step terminates
    ``failed`` with an i18n ``message_key`` — never a raw exception leak.
    """

    def test_deterministic_tool_raise_fails_step_with_classified_category(self, db):
        """A deterministic (ValueError) tool raise → failed step, no retry."""
        world = build_argo_world(db)
        plan = build_plan(
            "p4-u6-a-deterministic",
            [make_step("trip.get", {"trip_id": 5})],
            intent_name="trip.get",
        )
        # Patch the class method — the registry singleton the executor calls
        # resolves through the same class attribute, so the whole real path
        # (gate → params → validate → _run_step_with_retry → classify) runs.
        with patch.object(
            TripGetTool,
            "execute",
            new=AsyncMock(side_effect=ValueError("disk exploded")),
        ) as mock_execute:
            executed = _run(execute_plan(plan, services=_services(db, world)))

        # The §28.1 classifier buckets this as deterministic → no retry.
        assert classify_error(ValueError("disk exploded")) == ErrorCategory.DETERMINISTIC
        assert mock_execute.await_count == 1, "deterministic errors must never be retried"

        step = executed.steps[0]
        assert step.status == "failed"
        assert step.error == "copilot.error.unexpected"
        # The ToolResult the executor stored carries the i18n key + error param.
        assert step.result is not None
        assert step.result["status"] == "failed"
        assert step.result["message_key"] == "copilot.error.unexpected"
        assert step.result["message_params"]["error"] == "disk exploded"

    def test_transient_tool_raise_is_retried_once_then_fails(self, db):
        """A transient (ConnectionError) tool raise → one retry, then failed."""
        world = build_argo_world(db)
        plan = build_plan(
            "p4-u6-a-transient",
            [make_step("trip.get", {"trip_id": 5})],
            intent_name="trip.get",
        )
        with patch.object(
            TripGetTool,
            "execute",
            new=AsyncMock(side_effect=ConnectionError("provider unreachable")),
        ) as mock_execute:
            executed = _run(execute_plan(plan, services=_services(db, world)))

        # The §28.1 classifier buckets this as transient → exactly one retry.
        assert classify_error(ConnectionError("provider unreachable")) == ErrorCategory.TRANSIENT
        assert mock_execute.await_count == 2, "transient errors get a single retry"

        step = executed.steps[0]
        assert step.status == "failed"
        assert step.error == "copilot.error.unexpected"
        assert step.result is not None
        assert step.result["message_params"]["error"] == "provider unreachable"


# ═════════════════════════════════════════════════════════════════════════════
# Scenario B — plan call-count guard (MAX_TOOL_CALLS_PER_PLAN)
# ═════════════════════════════════════════════════════════════════════════════

class TestScenarioB_ToolCallGuard:
    """ARGO-FAIL-B: a plan past MAX_TOOL_CALLS_PER_PLAN is flagged, never executed."""

    def test_plan_exceeding_max_tool_calls_is_skipped_by_executor(self, db):
        """21+ steps → guardrail error; the executor skips every step gracefully."""
        world = build_argo_world(db)
        steps = [
            make_step("dispatch.create", {"trip_id": 1, "truck_id": 1, "driver_id": 1})
            for _ in range(MAX_TOOL_CALLS_PER_PLAN + 1)
        ]
        plan = build_plan("p4-u6-b-over", steps, intent_name="dispatch.create")

        # Real return shape: a list of i18n keys.
        errors = validate_guardrails(plan)
        assert errors == ["copilot.error.too_many_steps"], errors

        executed = _run(execute_plan(plan, services=_services(db, world)))

        # No truncation-and-run: every remaining step is skipped, none executes.
        assert len(executed.steps) == MAX_TOOL_CALLS_PER_PLAN + 1
        for step in executed.steps:
            assert step.status == "skipped"
            assert step.error == "copilot.error.too_many_steps"
            assert step.result is None, "a skipped step must never have executed"

    def test_plan_at_exact_max_tool_calls_passes_guardrails(self, db):
        """Exactly MAX_TOOL_CALLS_PER_PLAN steps is still within budget."""
        steps = [
            make_step("trip.get", {"trip_id": i + 1})
            for i in range(MAX_TOOL_CALLS_PER_PLAN)
        ]
        plan = build_plan("p4-u6-b-boundary", steps, intent_name="trip.get")
        assert validate_guardrails(plan) == []


# ═════════════════════════════════════════════════════════════════════════════
# Scenario C — permission denied for a low-privilege role
# ═════════════════════════════════════════════════════════════════════════════

class TestScenarioC_PermissionDenied:
    """ARGO-FAIL-C: a driver-role session is denied dispatch steps before execution."""

    def test_driver_role_dispatch_step_is_denied_by_executor(self, db):
        """dispatch.create under role='driver' → failed step with the §15 gate message."""
        world = build_argo_world(db)
        trip_id = _new_planned_trip(db, world)

        plan = build_plan(
            "p4-u6-c-permission",
            [
                make_step(
                    "dispatch.create",
                    {"trip_id": trip_id, "truck_id": world["healthy_truck_ids"][0]},
                )
            ],
            intent_name="dispatch.create",
        )

        # Role comes from make_tool_context(role="driver") → the executor reads
        # the same ``services`` dict the context carries.
        ctx = make_tool_context(
            db,
            company_id=world["company_id"],
            user_id=world["user_id"],
            role="driver",
        )
        assert ctx.role == "driver"

        executed = _run(execute_plan(plan, services=dict(ctx.services)))

        # The §15 gate denies BEFORE the tool runs: failed step, no ToolResult.
        step = executed.steps[0]
        assert step.status == "failed"
        assert step.error == "Tool 'dispatch.create' not available for role 'driver'"
        assert step.result is None, "a denied step must never have executed"

        # The trip stayed untouched.
        row = db.conn.execute(
            "SELECT truck_id, driver_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["truck_id"] is None
        assert row["driver_id"] is None

    def test_permission_gate_denies_driver_allows_dispatcher(self, db):
        """The real §15 gate shape for dispatch.create across roles."""
        world = build_argo_world(db)
        tool = DispatchCreateTool()

        # driver lacks the "dispatch" resource → denied.
        assert _check_tool_permission(tool, "driver") is False
        # dispatcher has dispatch:write (non-delete) → granted.
        assert _check_tool_permission(tool, "dispatcher") is True
        # admin bypasses the gate entirely.
        assert _check_tool_permission(tool, "admin") is True


# ═════════════════════════════════════════════════════════════════════════════
# Scenario D — DESTRUCTIVE (L3) requires confirmation
# ═════════════════════════════════════════════════════════════════════════════

class TestScenarioD_DestructiveConfirmation:
    """ARGO-FAIL-D: a DESTRUCTIVE step forces requires_confirmation; only
    ``confirm_and_execute`` runs it.  The typed confirmation phrase itself is
    UI-only (§5.6 — documented skip at this layer)."""

    def test_destructive_step_requires_confirmation_and_confirm_executes(self, db):
        """dispatch.cancel is L3 → plan flags confirmation; confirm_and_execute proceeds."""
        tool = DispatchCancelTool()
        assert tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE
        # Planner rule (planner.py): any step >= BUSINESS forces the gate.
        assert tool.confirmation_level >= ConfirmationLevel.BUSINESS

        world = build_argo_world(db)
        trip_id = _new_planned_trip(db, world)
        plan = build_plan(
            "p4-u6-d-confirm",
            [
                make_step(
                    "dispatch.cancel",
                    {"trip_id": trip_id, "reason": "customer no-show"},
                    level=ConfirmationLevel.DESTRUCTIVE,
                )
            ],
            intent_name="dispatch.cancel",
            requires_confirmation=True,
        )

        # Post-confirmation path executes the real dispatch.cancel tool → the
        # Planned trip is actually cancelled.
        executed = _run(confirm_and_execute(plan, services=_services(db, world)))
        step = executed.steps[0]
        assert step.status == "succeeded", step
        assert step.result is not None
        assert step.result["status"] == "success"

        row = db.conn.execute(
            "SELECT status FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["status"] == "Cancelled"

    def test_executor_refuses_unconfirmed_destructive_plan(self, db):
        """Defense-in-depth: ``execute_plan`` refuses unconfirmed DESTRUCTIVE plans.

        Even if a caller skips the router's gate and sends a DESTRUCTIVE plan
        with ``requires_confirmation=True`` straight to ``execute_plan``, the
        executor refuses — every step is marked skipped with a
        confirmation-required i18n key and nothing executes.  The plan keeps
        its ``requires_confirmation`` flag, so the router's
        ``_plan_response_status`` still reports ``awaiting_confirmation``.
        ``confirm_and_execute`` remains the only path that runs DESTRUCTIVE
        steps (see ``test_destructive_step_requires_confirmation_and_confirm_executes``).
        """
        world = build_argo_world(db)
        trip_id = _new_planned_trip(db, world)
        plan = build_plan(
            "p4-u6-d-unconfirmed",
            [
                make_step(
                    "dispatch.cancel",
                    {"trip_id": trip_id, "reason": "driver unassigned"},
                    level=ConfirmationLevel.DESTRUCTIVE,
                )
            ],
            intent_name="dispatch.cancel",
            requires_confirmation=True,
        )

        executed = _run(execute_plan(plan, services=_services(db, world)))
        step = executed.steps[0]
        # Refusal: skipped with the confirmation-required message key, plan
        # still flagged → router reports "awaiting_confirmation".
        assert step.status == "skipped", step
        assert step.error == "copilot.timeline.confirmation_needed", step.error
        assert plan.requires_confirmation is True

        # No side effects — the Planned trip was never cancelled.
        row = db.conn.execute(
            "SELECT status FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row["status"] == "Planned"


# ═════════════════════════════════════════════════════════════════════════════
# Scenario E — reasoning graph over the node cap
# ═════════════════════════════════════════════════════════════════════════════

class TestScenarioE_ReasoningGraphGuard:
    """ARGO-FAIL-E: reasoning_graph_nodes past MAX_REASONING_GRAPH_NODES_PER_TURN
    yields the simplification warning."""

    def test_reasoning_graph_over_cap_returns_simplification_warning(self, db):
        """51 nodes → the real guardrail key, exactly the list shape."""
        plan = build_plan(
            "p4-u6-e-over",
            [make_step("trip.get", {"trip_id": 1})],
            intent_name="trip.get",
            reasoning_graph_nodes=MAX_REASONING_GRAPH_NODES_PER_TURN + 1,
        )
        errors = validate_guardrails(plan)
        assert errors == ["copilot.error.too_many_graph_nodes"], errors

    def test_reasoning_graph_at_cap_passes(self, db):
        """Exactly 50 nodes is still under budget."""
        plan = build_plan(
            "p4-u6-e-boundary",
            [make_step("trip.get", {"trip_id": 1})],
            intent_name="trip.get",
            reasoning_graph_nodes=MAX_REASONING_GRAPH_NODES_PER_TURN,
        )
        assert validate_guardrails(plan) == []

    def test_reasoning_graph_over_cap_skips_steps_via_executor(self, db):
        """An over-cap plan is skipped gracefully through the real executor."""
        world = build_argo_world(db)
        plan = build_plan(
            "p4-u6-e-exec",
            [make_step("trip.get", {"trip_id": 1})],
            intent_name="trip.get",
            reasoning_graph_nodes=MAX_REASONING_GRAPH_NODES_PER_TURN + 1,
        )
        executed = _run(execute_plan(plan, services=_services(db, world)))
        step = executed.steps[0]
        assert step.status == "skipped"
        assert step.error == "copilot.error.too_many_graph_nodes"
        assert step.result is None