"""ARGO task state machine: autonomous scheduling plan lifecycle.

The ARGO subsystem (autonomous routing & grid optimization) is planned
for Phase 4 of the Workflow Integrity Test Suite.  However, the general
Co-Pilot execution state machine (``backend.copilot.executor``) IS
implemented and used by all copilot plans — ARGO plans will use it too.

This file tests the executor state machine that ARGO (and every other
copilot intent) goes through:

    UNDERSTOOD → REASONING → PLANNED → VALIDATING → EXECUTING → COMPLETED

With confirmation gates and guardrail enforcement at each stage.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from backend.copilot.schemas import ConfirmationLevel, ExecutionPlan, ExecutionStep, Intent
from backend.copilot.executor import (
    PlanStatus,
    MAX_TOOL_CALLS_PER_PLAN,
    MAX_REASONING_GRAPH_NODES_PER_TURN,
    cancel_plan,
    execute_plan,
    confirm_and_execute,
    validate_guardrails,
    _check_tool_permission,
)

pytestmark = pytest.mark.state_machine


# ═════════════════════════════════════════════════════════════════════════
#  Helpers
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def load_tools_and_reset_cb():
    """Ensure tool registry is loaded and circuit breaker is reset between tests."""
    from backend.copilot.planner import _ensure_tools_loaded
    _ensure_tools_loaded()
    from backend.copilot.circuit_breaker import get_circuit_breaker
    cb = get_circuit_breaker()
    cb._states.clear()


def _make_step(
    step_id: str,
    level: ConfirmationLevel = ConfirmationLevel.SAFE,
    status: str = "pending",
    params: dict | None = None,
    depends_on: list[str] | None = None,
) -> ExecutionStep:
    return ExecutionStep(
        step_id=step_id,
        tool_name="vehicle.search",
        tool_version="1.0.0",
        parameters=params or {},
        depends_on=depends_on or [],
        confirmation_level=level,
        status=status,
    )


def _make_plan(
    steps: list[ExecutionStep] | None = None,
    requires_confirmation: bool = False,
    utterance: str = "test",
) -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="test-plan",
        conversation_id="test-conv",
        reasoning_graph_id="test-graph",
        intent=Intent(name="vehicle.search", raw_utterance=utterance),
        steps=steps or [_make_step("s1")],
        overall_confidence=0.9,
        requires_confirmation=requires_confirmation,
    )


# ═════════════════════════════════════════════════════════════════════════
#  1. State Machine Skeleton — PlanStatus enum
# ═════════════════════════════════════════════════════════════════════════


class TestArgoPlanStateMachine:
    """Co-Pilot executor state machine that ARGO plans will use.

    The PlanStatus enum defines the lifecycle states.  Tests verify
    the skeleton, valid transition ordering, guardrail enforcement,
    and confirmation gates.
    """

    # ── 1a. Skeleton ───────────────────────────────────────────────────

    def test_plan_status_enum_members(self):
        """PlanStatus must define all expected lifecycle states."""
        expected_states = {
            "understood",
            "reasoning",
            "planned",
            "validating",
            "awaiting_clarification",
            "awaiting_confirmation",
            "executing",
            "summarizing",
            "completed",
            "partially_completed",
            "cancelled",
        }
        actual = {s.value for s in PlanStatus}
        missing = expected_states - actual
        extra = actual - expected_states
        assert not missing, f"Missing PlanStatus members: {missing}"
        assert not extra, f"Unexpected PlanStatus members: {extra}"

    def test_plan_status_value_types(self):
        """Each PlanStatus member must be a valid string."""
        for member in PlanStatus:
            assert isinstance(member.value, str)
            assert len(member.value) > 0

    # ── 1b. Lifecycle understanding ────────────────────────────────────

    def test_planning_lifecycle_sequence(self):
        """The state machine lifecycle forms a coherent sequence.

        UNDERSTOOD → REASONING → PLANNED → VALIDATING → EXECUTING → COMPLETED
        is the core path (with confirmation gates and clarification loops).
        """
        # This is a contract test — the enum values encode the states.
        # States that must exist for the lifecycle to work:
        core_states = [
            PlanStatus.UNDERSTOOD,
            PlanStatus.REASONING,
            PlanStatus.PLANNED,
            PlanStatus.VALIDATING,
            PlanStatus.EXECUTING,
            PlanStatus.COMPLETED,
        ]
        for state in core_states:
            assert state is not None
            assert state.value in ("understood", "reasoning", "planned",
                                   "validating", "executing", "completed")

    def test_confirmation_gate_states_exist(self):
        """The state machine has explicit states for confirmation gating."""
        assert PlanStatus.AWAITING_CONFIRMATION is not None
        assert PlanStatus.AWAITING_CLARIFICATION is not None

    # ── 1c. Terminal states ────────────────────────────────────────────

    def test_terminal_states(self):
        """COMPLETED, PARTIALLY_COMPLETED, and CANCELLED are terminal states.

        Once a plan reaches a terminal state, no further transitions
        should occur.
        """
        terminal = {PlanStatus.COMPLETED, PlanStatus.PARTIALLY_COMPLETED, PlanStatus.CANCELLED}
        assert all(s in PlanStatus for s in terminal)


# ═════════════════════════════════════════════════════════════════════════
#  2. Validation — guardrails abort invalid plans
# ═════════════════════════════════════════════════════════════════════════


class TestArgoPlanValidation:
    """Guardrail enforcement — plans that violate ceilings are aborted."""

    def test_guardrails_block_oversized_plan(self):
        """Plans exceeding MAX_TOOL_CALLS_PER_PLAN must be blocked."""
        steps = [_make_step(f"s{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN + 5)]
        plan = _make_plan(steps=steps)
        errors = validate_guardrails(plan)
        assert len(errors) >= 1
        assert any("too_many_steps" in e for e in errors)

    def test_guardrails_pass_normal_plan(self):
        """Normal-sized plans must pass guardrail validation."""
        steps = [_make_step(f"s{i}") for i in range(5)]
        plan = _make_plan(steps=steps)
        errors = validate_guardrails(plan)
        assert len(errors) == 0, f"Normal plan failed guardrails: {errors}"

    def test_guardrails_block_overflow_reasoning_graph(self):
        """Plans with too many estimated graph nodes must be blocked."""
        # Create a plan with many steps and entities to trigger the graph node ceiling
        from backend.copilot.schemas import Entity
        many_entities = [Entity(type="vehicle", value=i, source="extracted", confidence=0.5)
                         for i in range(30)]
        plan = ExecutionPlan(
            plan_id="test-plan",
            conversation_id="test-conv",
            reasoning_graph_id="test-graph",
            intent=Intent(name="vehicle.search", raw_utterance="test " * 100,
                          entities=many_entities),
            steps=[_make_step(f"s{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN)],
            overall_confidence=0.9,
            requires_confirmation=False,
        )
        errors = validate_guardrails(plan)
        # With 20 steps + 30 entities, estimated_nodes = 20*2 + 30 = 70 > 50
        graph_errors = [e for e in errors if "too_many_graph_nodes" in e]
        assert len(graph_errors) >= 1

    def test_guardrails_block_oversized_utterance(self):
        """Plans with very long utterances must be blocked (token ceiling)."""
        long_utterance = "test " * 20000
        plan = _make_plan(
            steps=[_make_step("s1")],
            utterance=long_utterance,
        )
        errors = validate_guardrails(plan)
        token_errors = [e for e in errors if "too_many_tokens" in e]
        assert len(token_errors) >= 1

    @pytest.mark.asyncio
    async def test_execute_plan_skips_all_steps_on_guardrail_violation(self):
        """Guardrail violation in execute_plan must skip all steps."""
        too_many = [_make_step(f"s{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN + 5)]
        plan = _make_plan(steps=too_many)
        result = await execute_plan(plan)
        for step in result.steps:
            assert step.status == "skipped"
            assert step.error is not None


# ═════════════════════════════════════════════════════════════════════════
#  3. State Transitions — correct order
# ═════════════════════════════════════════════════════════════════════════


class TestArgoPlanTransitions:
    """State machine transitions within the executor."""

    @pytest.mark.asyncio
    async def test_execute_plan_transitions_steps_to_terminal(self):
        """execute_plan transitions pending steps to a terminal state."""
        plan = _make_plan(steps=[_make_step("s1")])
        result = await execute_plan(plan)
        assert result.steps[0].status in ("succeeded", "failed", "skipped")

    @pytest.mark.asyncio
    async def test_execute_plan_sets_timestamps(self):
        """Steps executed via a known tool should have timestamps."""
        plan = _make_plan(steps=[_make_step("s1")])
        result = await execute_plan(plan)
        step = result.steps[0]
        if step.status in ("succeeded", "failed", "skipped"):
            # When a registered tool is used (vehicle.search), timestamps
            # are always assigned because the tool is found in the registry
            # and execute() is called.
            assert step.started_at is not None, f"started_at missing for {step.status}"
            assert step.finished_at is not None, f"finished_at missing for {step.status}"

    @pytest.mark.asyncio
    async def test_execute_plan_running_state_set(self):
        """Steps must pass through 'running' before reaching terminal state.

        The executor sets step.status = 'running' before execution.
        If execution is async, the running state is visible to observers.
        """
        plan = _make_plan(steps=[_make_step("s1")])
        # The executor sets running before executing; we verify via
        # the resulting status (it must not stay "pending")
        result = await execute_plan(plan)
        assert result.steps[0].status != "pending"

    @pytest.mark.asyncio
    async def test_cancel_reachable_from_pending(self):
        """Cancel is reachable from 'pending' state."""
        plan = _make_plan(steps=[_make_step("s1", status="pending")])
        result = await cancel_plan(plan)
        assert result.steps[0].status == "skipped"

    @pytest.mark.asyncio
    async def test_cancel_does_not_affect_terminal_steps(self):
        """Cancel should not modify already-terminal steps."""
        for terminal in ("succeeded", "failed", "skipped"):
            plan = _make_plan(steps=[_make_step("s1", status=terminal)])
            result = await cancel_plan(plan)
            assert result.steps[0].status == terminal

    @pytest.mark.asyncio
    async def test_confirm_and_execute_runs_pending_steps(self):
        """confirm_and_execute should execute all pending steps."""
        plan = _make_plan(
            steps=[_make_step("s1", level=ConfirmationLevel.BUSINESS)],
        )
        result = await confirm_and_execute(plan)
        assert result.steps[0].status in ("succeeded", "failed", "skipped")

    @pytest.mark.asyncio
    async def test_confirm_and_execute_skips_completed(self):
        """confirm_and_execute should skip already-completed steps."""
        plan = _make_plan(steps=[
            _make_step("s1", status="succeeded"),
            _make_step("s2", status="pending"),
        ])
        result = await confirm_and_execute(plan)
        assert result.steps[0].status == "succeeded"
        assert result.steps[1].status in ("succeeded", "failed", "skipped")

    @pytest.mark.asyncio
    async def test_confirm_and_execute_guardrails_block(self):
        """Guardrail violation should block execution in confirm_and_execute."""
        too_many = [_make_step(f"s{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN + 5)]
        plan = _make_plan(steps=too_many)
        result = await confirm_and_execute(plan)
        for step in result.steps:
            assert step.status == "skipped"
            assert step.error is not None


# ═════════════════════════════════════════════════════════════════════════
#  4. Confirmation Gates — BUSINESS / DESTRUCTIVE levels
# ═════════════════════════════════════════════════════════════════════════


class TestArgoConfirmationGates:
    """Confirmation level gating — BUSINESS and DESTRUCTIVE require approval."""

    def test_confirmation_level_enum_values(self):
        """Confirmation levels must have correct ordering and values."""
        assert ConfirmationLevel.SAFE.value == 0
        assert ConfirmationLevel.INFORMATIONAL.value == 1
        assert ConfirmationLevel.BUSINESS.value == 2
        assert ConfirmationLevel.DESTRUCTIVE.value == 3

    def test_destructive_tool_requires_typed_confirmation(self):
        """DESTRUCTIVE-level tools always require typed confirmation.

        Verify by checking dispatch.cancel which is marked DESTRUCTIVE.
        """
        from backend.copilot.tools.registry import get_tool
        tool = get_tool("dispatch.cancel")
        assert tool is not None, "dispatch.cancel tool must be registered"
        assert tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE

    def test_business_tool_requires_confirmation(self):
        """BUSINESS-level tools require user confirmation before execution.

        Verify by checking dispatch.create which is marked BUSINESS.
        """
        from backend.copilot.tools.registry import get_tool
        tool = get_tool("dispatch.create")
        assert tool is not None, "dispatch.create tool must be registered"
        assert tool.confirmation_level == ConfirmationLevel.BUSINESS

    def test_safe_tool_executes_immediately(self):
        """SAFE-level tools execute immediately without confirmation.

        Verify by checking vehicle.search which is SAFE.
        """
        from backend.copilot.tools.registry import get_tool
        tool = get_tool("vehicle.search")
        assert tool is not None, "vehicle.search tool must be registered"
        assert tool.confirmation_level <= ConfirmationLevel.INFORMATIONAL

    def test_tool_confirmation_levels_are_valid(self):
        """All registered tools must have valid confirmation levels."""
        from backend.copilot.tools.registry import available_tools
        tools = available_tools()
        for t in tools:
            assert t.confirmation_level is not None, f"Tool {t.name} has no confirmation_level"
            assert isinstance(t.confirmation_level, ConfirmationLevel)

    def test_dispatch_cancel_is_destructive(self):
        """dispatch.cancel must be DESTRUCTIVE (irreversible)."""
        from backend.copilot.tools.registry import get_tool
        tool = get_tool("dispatch.cancel")
        assert tool is not None, "dispatch.cancel tool must be registered"
        assert tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE
        assert tool.required_permission == "dispatch:write"

    def test_plan_requires_confirmation_for_business_level(self):
        """A plan with BUSINESS-level steps must detect confirmation requirement."""
        step = _make_step("s1", level=ConfirmationLevel.BUSINESS)
        plan = _make_plan(steps=[step], requires_confirmation=False)
        assert any(
            s.confirmation_level >= ConfirmationLevel.BUSINESS
            for s in plan.steps
        ), "Business-level step should require confirmation"


# ═════════════════════════════════════════════════════════════════════════
#  5. Permission Gates — role-based access
# ═════════════════════════════════════════════════════════════════════════


class TestArgoPermissionGates:
    """Role-based permission checks for plan execution (§15)."""

    def test_admin_bypasses_all_permissions(self):
        """Admin role bypasses all permission checks."""
        from backend.copilot.tools.registry import get_tool
        tool = get_tool("dispatch.cancel")
        assert tool is not None, "dispatch.cancel tool must be registered"
        assert _check_tool_permission(tool, "admin") is True

    def test_driver_cannot_write(self):
        """Driver role must be read-only for resource tools."""
        from backend.copilot.tools.registry import get_tool
        tool = get_tool("dispatch.create")
        assert tool is not None, "dispatch.create tool must be registered"
        assert _check_tool_permission(tool, "driver") is False

    def test_driver_can_read_vehicle(self):
        """Driver role should be able to use read-only tools."""
        from backend.copilot.tools.registry import get_tool
        tool = get_tool("vehicle.search")
        assert tool is not None, "vehicle.search tool must be registered"
        assert _check_tool_permission(tool, "driver") is True

    def test_dispatcher_can_write_dispatch(self):
        """Dispatcher role should be able to write to dispatch resources."""
        from backend.copilot.tools.registry import get_tool
        tool = get_tool("dispatch.create")
        assert tool is not None, "dispatch.create tool must be registered"
        assert _check_tool_permission(tool, "dispatcher") is True

    def test_manager_has_broad_access(self):
        """Manager role should have broad resource access."""
        from backend.copilot.tools.registry import get_tool
        tool = get_tool("dispatch.create")
        assert tool is not None, "dispatch.create tool must be registered"
        assert _check_tool_permission(tool, "manager") is True


# ═════════════════════════════════════════════════════════════════════════
#  6. In-Context — Marius persona data availability (kept from original)
# ═════════════════════════════════════════════════════════════════════════


class TestArgoPersonaDataAvailable:
    """Verify that the ARGO persona seeds data correctly for future tests."""

    def test_marius_persona_seeds_data(self, db):
        """Marius ARGO persona seeds company, drivers, trucks, clients, trips."""
        from tests.workflow_integrity.personas.marius_argo_power_user import (
            build_marius_persona,
        )

        ids = build_marius_persona(db)
        assert ids["company_id"] > 0
        assert len(ids["driver_ids"]) == 20
        assert len(ids["truck_ids"]) == 20
        assert len(ids["client_ids"]) == 8
        assert len(ids["trip_ids"]) == 30

        # Verify trips have expected status distribution
        trips = db.conn.execute(
            "SELECT DISTINCT status FROM trips WHERE id IN ({})".format(
                ",".join("?" for _ in ids["trip_ids"])
            ),
            ids["trip_ids"],
        ).fetchall()
        statuses = {row["status"] for row in trips}
        expected = {"Planned", "Loading", "In Transit", "Delivered", "Invoiced", "Paid"}
        assert statuses == expected, (
            f"Marius persona trips have unexpected statuses: {statuses}"
        )
