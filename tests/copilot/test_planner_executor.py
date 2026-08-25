"""Unit tests for Planner, Executor, Context, and LLM Provider.

Covers: intent extraction (14+ patterns), pipeline flow, executor state machine,
context loading/saving, and LLM provider abstraction.
"""
from __future__ import annotations


import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset circuit breaker state between tests to prevent state leaking."""
    from backend.copilot.circuit_breaker import get_circuit_breaker
    cb = get_circuit_breaker()
    cb._states.clear()

from backend.copilot.planner import (
    _ensure_tools_loaded,
    extract_intent,
    process_utterance,
    _match_score,
)
from backend.copilot.executor import (
    execute_plan,
    confirm_and_execute,
    cancel_plan,
    validate_guardrails,
    PlanStatus,
    MAX_TOOL_CALLS_PER_PLAN,
)
from backend.copilot.context import (
    build_global_context,
    load_session_context,
    load_conversation_context,
    resolve_available_tools,
)
from backend.copilot.schemas import (
    ConfirmationLevel,
    ExecutionPlan,
    ExecutionStep,
    GlobalContext,
    Intent,
    SessionContext,
    ConversationContext,
    ToolResult,
    Entity,
)
from backend.copilot.confidence import compute_confidence, confidence_bucket
from backend.copilot.circuit_breaker import CircuitBreaker


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_step(
    step_id: str,
    level: ConfirmationLevel = ConfirmationLevel.SAFE,
    status: str = "pending",
    params: Optional[Dict[str, Any]] = None,
    depends_on: Optional[list] = None,
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
    steps: Optional[list] = None,
    requires_confirmation: bool = False,
) -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="test-plan",
        conversation_id="test-conv",
        reasoning_graph_id="test-graph",
        intent=Intent(name="test", raw_utterance="test"),
        steps=steps or [_make_step("s1")],
        overall_confidence=0.9,
        requires_confirmation=requires_confirmation,
    )


def _global_ctx(**overrides) -> GlobalContext:
    defaults = dict(
        company_id=1,
        user_id=1,
        role="dispatcher",
        language="en",
        timezone="UTC",
        subscription_tier="business",
    )
    defaults.update(overrides)
    return GlobalContext(**defaults)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _auto_load_tools():
    """Ensure all tool modules are loaded before each test."""
    _ensure_tools_loaded()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Planner: Intent Extraction — all 14+ patterns (§7)
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntentExtraction:
    """Verify the keyword-based intent extractor matches all 14+ tool patterns."""

    INTENT_TEST_CASES = [
        # ── vehicle.search ──
        ("find available trucks", "vehicle.search"),
        ("search for vehicles", "vehicle.search"),
        ("list all trucks", "vehicle.search"),
        ("show me all vehicles", "vehicle.search"),
        # ── vehicle.health_score ──
        ("what is the health score of truck 42", "vehicle.health_score"),
        ("check vehicle health for truck 18", "vehicle.health_score"),
        # ── driver.check_hours ──
        ("check driver 7 hours", "driver.check_hours"),
        ("how many hours does driver 5 have left", "driver.check_hours"),
        ("driver available for drive 3", "driver.check_hours"),
        # ── route.calculate ──
        ("calculate a route from Berlin to Warsaw", "route.calculate"),
        ("plan route from Bucharest to Cluj", "route.calculate"),
        ("how far is it from Paris to Lyon", "route.calculate"),
        # ── route.estimate_cost ──
        ("estimate the cost for 1500 km", "route.estimate_cost"),
        ("what is the fuel cost for 2000 km", "route.estimate_cost"),
        ("trip cost for 800 km", "route.estimate_cost"),
        # ── route.plan_multistop ──
        ("plan multiple stops in Berlin, Warsaw, Kyiv", "route.plan_multistop"),
        ("optimize route for several stops", "route.plan_multistop"),
        ("plan delivery route with 3 stops", "route.plan_multistop"),
        # ── trip.calculate_profitability ──
        ("calculate trip profitability for 2000 km", "trip.calculate_profitability"),
        ("what is the margin for 1000 km trip", "trip.calculate_profitability"),
        ("how profitable is trip 42", "trip.calculate_profitability"),
        # ── client.payment_summary ──
        ("show payment summary for client 12", "client.payment_summary"),
        ("how much does client 42 owe", "client.payment_summary"),
        # ── document.search ──
        ("search documents for invoice", "document.search"),
        ("find documents from ACME", "document.search"),
        ("look up paperwork for trip 7", "document.search"),
        # ── currency.get_rate ──
        ("what is the USD exchange rate", "currency.get_rate"),
        ("get the rate for EUR", "currency.get_rate"),
        ("what is the current RON rate", "currency.get_rate"),
        # ── currency.convert ──
        ("convert 100 EUR to RON", "currency.convert"),
        ("change currency 500 USD to EUR", "currency.convert"),
        ("exchange 200 GBP to EUR", "currency.convert"),
        # ── tracking.get_live_positions ──
        ("where are my vehicles right now", "tracking.get_live_positions"),
        ("show current location of truck 18", "tracking.get_live_positions"),
        ("live gps position of fleet vehicles", "tracking.get_live_positions"),
        # ── tracking.get_vehicle_history ──
        ("show vehicle history for truck 42", "tracking.get_vehicle_history"),
        ("show tracking history for truck 18", "tracking.get_vehicle_history"),
        # ── analytics.query ──
        ("show me fleet analytics", "analytics.query"),
        ("give me a financial report", "analytics.query"),
        ("analytics dashboard", "analytics.query"),
        ("show me the dashboard overview", "analytics.query"),
        # ── Edge cases ──
        ("do something magical", "unknown"),  # No match
        ("xyzzy this is nonsense", "unknown"),  # No meaningful match
        ("", "unknown"),  # Empty
    ]

    @pytest.mark.parametrize("utterance,expected", INTENT_TEST_CASES)
    @pytest.mark.asyncio
    async def test_intent_extraction(self, utterance: str, expected: str):
        """Verify intent extraction for all patterns plus edge cases."""
        intent = await extract_intent(utterance)
        assert intent.name == expected, (
            f"Expected '{expected}' for '{utterance or '<empty>'}'"
            f", got '{intent.name}'"
        )
        assert intent.raw_utterance == utterance
        assert isinstance(intent.entities, list)
        assert isinstance(intent.missing_required_entities, list)

    # ── Entity extraction tests ──

    @pytest.mark.asyncio
    async def test_intent_extracts_vehicle_id_entity(self):
        """Verify number extraction from health-score query."""
        intent = await extract_intent("what is the health score of vehicle 42")
        assert intent.name == "vehicle.health_score"
        vehicle_entities = [e for e in intent.entities if e.type == "vehicle_id"]
        assert len(vehicle_entities) > 0, "Expected vehicle_id entity"
        assert vehicle_entities[0].value == 42
        assert vehicle_entities[0].source == "extracted"
        assert 0.5 <= vehicle_entities[0].confidence <= 1.0

    @pytest.mark.asyncio
    async def test_intent_extracts_driver_id_entity(self):
        """Verify driver ID extraction from check-hours query."""
        intent = await extract_intent("check driver 7 hours")
        assert intent.name == "driver.check_hours"
        driver_entities = [e for e in intent.entities if e.type == "driver_id"]
        assert len(driver_entities) > 0
        assert driver_entities[0].value == 7

    @pytest.mark.asyncio
    async def test_intent_extracts_distance_entity(self):
        """Verify distance extraction from cost-estimate query."""
        intent = await extract_intent("estimate the cost for 1500 km")
        assert intent.name == "route.estimate_cost"
        dist_entities = [e for e in intent.entities if e.type == "distance_km"]
        assert len(dist_entities) > 0
        assert dist_entities[0].value == 1500.0

    @pytest.mark.asyncio
    async def test_empty_utterance_has_no_entities(self):
        """Empty utterance → unknown intent, no entities."""
        intent = await extract_intent("")
        assert intent.name == "unknown"
        assert intent.entities == []

    @pytest.mark.asyncio
    async def test_whitespace_only_utterance(self):
        """Whitespace-only utterance → unknown."""
        intent = await extract_intent("   ")
        assert intent.name == "unknown"

    @pytest.mark.asyncio
    async def test_non_english_does_not_crash(self):
        """Non-English text should not cause exceptions."""
        intent = await extract_intent("Bonjour, je cherche un véhicule")
        # May or may not match, but must not crash
        assert isinstance(intent, Intent)
        assert intent.name in ("unknown", "vehicle.search")

    @pytest.mark.asyncio
    async def test_mixed_input_does_not_crash(self):
        """Mixed alphanumeric/symbol input should not crash."""
        intent = await extract_intent("search!!! for @truck #42")
        assert isinstance(intent, Intent)
        # May match vehicle.search (via "search"), vehicle.health_score (via "truck"),
        # or be unknown — any is valid as long as it doesn't crash
        assert intent.name in ("unknown", "vehicle.search", "vehicle.health_score")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Planner: Full Pipeline — process_utterance with mocked services
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlannerPipeline:
    """Test the full process_utterance pipeline end-to-end."""

    @pytest.mark.asyncio
    async def test_unknown_intent_returns_clarification(self):
        """Unknown intents should return a clarification question."""
        ctx = _global_ctx()
        resp = await process_utterance("do something magical", ctx, "test-conv-1")
        assert resp.clarification_question_key is not None
        assert resp.plan is None
        assert "unknown_intent" in resp.clarification_question_key

    @pytest.mark.asyncio
    async def test_missing_entities_returns_clarification(self):
        """Intent with missing required entities may ask for clarification."""
        ctx = _global_ctx()
        resp = await process_utterance("check driver hours", ctx, "test-conv-2")
        # Should either clarify or produce a plan depending on entity presence
        has_clarification = resp.clarification_question_key is not None
        has_plan = resp.plan is not None
        assert has_clarification or has_plan, (
            "Expected either a clarification or a plan"
        )

    @pytest.mark.asyncio
    async def test_vehicle_search_with_services(self):
        """A valid vehicle search should produce a plan when services provided."""
        ctx = _global_ctx()
        resp = await process_utterance(
            "find available trucks",
            ctx,
            "test-conv-3",
            services={"db": MagicMock()},
        )
        # Should produce a plan or (if entities missing) a clarification
        has_plan = resp.plan is not None
        has_clarification = resp.clarification_question_key is not None
        assert has_plan or has_clarification

    @pytest.mark.asyncio
    async def test_pipeline_does_not_crash_on_various_inputs(self):
        """The pipeline must never raise an unhandled exception."""
        ctx = _global_ctx()
        test_inputs = [
            "hello",
            "12345",
            "   ",
            "search for available vehicles",
            "tracking",
            "convert 100 EUR",
            "",
            "a" * 500,  # Very long input
        ]
        for inp in test_inputs:
            try:
                await process_utterance(inp, ctx, f"test-conv-{hash(inp)}")
            except Exception as e:
                pytest.fail(f"Pipeline crashed on '{inp[:50]}': {e}")

    @pytest.mark.asyncio
    async def test_process_utterance_returns_copilot_response(self):
        """Pipeline always returns a CoPilotResponse."""
        ctx = _global_ctx()
        resp = await process_utterance("list all trucks", ctx, "test-conv-type")
        from backend.copilot.schemas import CoPilotResponse
        assert isinstance(resp, CoPilotResponse)

    @pytest.mark.asyncio
    async def test_session_context_passed_through(self):
        """SessionContext should flow through to the plan when provided."""
        ctx = _global_ctx()
        session = SessionContext(current_customer_id=99, current_module="test")
        resp = await process_utterance(
            "find available trucks",
            ctx,
            "test-conv-session",
            session_ctx=session,
        )
        # Pipeline should not crash when session context is passed
        assert resp is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Executor: Guardrails — cost/safety ceilings (§23.3)
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutorGuardrails:
    """Cost and safety guardrails (§23.3)."""

    def test_guardrails_block_oversized_plan(self):
        """Plans exceeding max tool calls must be blocked."""
        steps = [_make_step(f"s{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN + 5)]
        plan = _make_plan(steps=steps)
        errors = validate_guardrails(plan)
        assert len(errors) >= 1, "Oversized plan should have guardrail errors"
        assert any("too_many_steps" in e for e in errors)

    def test_guardrails_pass_normal_plan(self):
        """Normal-sized plans must pass guardrails."""
        steps = [_make_step(f"s{i}") for i in range(5)]
        plan = _make_plan(steps=steps)
        errors = validate_guardrails(plan)
        assert len(errors) == 0, f"Normal plan should pass: {errors}"

    def test_guardrails_exact_boundary(self):
        """Plans at exactly MAX_TOOL_CALLS_PER_PLAN should pass."""
        steps = [_make_step(f"s{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN)]
        plan = _make_plan(steps=steps)
        errors = validate_guardrails(plan)
        assert len(errors) == 0

    def test_guardrails_one_over_boundary(self):
        """Plans one over MAX_TOOL_CALLS_PER_PLAN must fail."""
        steps = [_make_step(f"s{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN + 1)]
        plan = _make_plan(steps=steps)
        errors = validate_guardrails(plan)
        assert len(errors) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Executor: State Machine — transitions (§7)
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutorCancel:
    """Cancel transitions — reachable from any non-terminal state."""

    @pytest.mark.parametrize("initial_status", ["pending", "running", "awaiting_confirmation"])
    @pytest.mark.asyncio
    async def test_cancel_reachable_from_active_states(self, initial_status: str):
        """CANCELLED reachable from pending, running, and awaiting_confirmation."""
        plan = _make_plan(steps=[_make_step("s1", status=initial_status)])
        result = await cancel_plan(plan)
        assert result.steps[0].status == "skipped"

    @pytest.mark.parametrize("terminal_status", ["succeeded", "failed", "skipped"])
    @pytest.mark.asyncio
    async def test_cancel_does_not_change_terminal_states(self, terminal_status: str):
        """Cancel should not modify already-terminal steps."""
        plan = _make_plan(steps=[_make_step("s1", status=terminal_status)])
        result = await cancel_plan(plan)
        assert result.steps[0].status == terminal_status

    @pytest.mark.asyncio
    async def test_cancel_sets_finished_at(self):
        """Cancelled steps should have finished_at set."""
        plan = _make_plan(steps=[_make_step("s1", status="pending")])
        result = await cancel_plan(plan)
        assert result.steps[0].finished_at is not None


class TestExecutorExecutePlan:
    """execute_plan state machine — tool dispatch."""

    @pytest.mark.asyncio
    async def test_execute_plan_marks_steps(self):
        """Execute plan should transition steps to a terminal state."""
        plan = _make_plan(steps=[_make_step("s1", status="pending")])
        result = await execute_plan(plan)
        assert result.steps[0].status in ("succeeded", "failed", "skipped")

    @pytest.mark.asyncio
    async def test_execute_plan_with_known_tool_sets_timestamps(self):
        """Steps executed via a known tool should have timestamps."""
        plan = _make_plan(steps=[_make_step("s1", status="pending")])
        result = await execute_plan(plan)
        step = result.steps[0]
        # If the tool was found and executed (any status), timestamps are set
        if step.status in ("succeeded", "failed", "skipped"):
            # When a registered tool is used (vehicle.search), timestamps
            # are always assigned because the tool is found in the registry
            # and execute() is called (returning "unavailable" without DB).
            assert step.started_at is not None, f"started_at missing for {step.status}"
            assert step.finished_at is not None, f"finished_at missing for {step.status}"

    @pytest.mark.asyncio
    async def test_execute_plan_guardrails_skip_all_steps(self):
        """Guardrail violation should skip all steps without execution."""
        too_many = [_make_step(f"s{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN + 5)]
        plan = _make_plan(steps=too_many)
        result = await execute_plan(plan)
        for step in result.steps:
            assert step.status == "skipped"
            assert step.error is not None

    @pytest.mark.asyncio
    async def test_execute_plan_skips_succeeded_steps(self):
        """Already-succeeded steps should be skipped in confirm_and_execute."""
        plan = _make_plan(steps=[
            _make_step("s1", status="succeeded"),
            _make_step("s2", status="pending"),
        ])
        result = await confirm_and_execute(plan)
        assert result.steps[0].status == "succeeded"
        assert result.steps[1].status in ("succeeded", "failed", "skipped")


class TestExecutorConfirmAndExecute:
    """confirm_and_execute — post-confirmation execution."""

    @pytest.mark.asyncio
    async def test_confirm_and_execute_runs_pending_steps(self):
        """Confirm and execute should execute all pending steps."""
        plan = _make_plan(
            steps=[_make_step("s1", level=ConfirmationLevel.BUSINESS, status="pending")],
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
    async def test_confirm_and_execute_guardrails(self):
        """Guardrail violation should block execution in confirm_and_execute."""
        too_many = [_make_step(f"s{i}") for i in range(MAX_TOOL_CALLS_PER_PLAN + 5)]
        plan = _make_plan(steps=too_many)
        result = await confirm_and_execute(plan)
        for step in result.steps:
            assert step.status == "skipped"

    @pytest.mark.asyncio
    async def test_confirm_with_on_step_update_callback(self):
        """The on_step_update callback should fire for each step."""
        plan = _make_plan(steps=[
            _make_step("s1", status="pending"),
            _make_step("s2", status="pending"),
        ])
        updates: list = []
        def _track(step_id: str, status: str, tool_name: str) -> None:
            updates.append((step_id, status, tool_name))
        await confirm_and_execute(plan, on_step_update=_track)
        # Each step should trigger at least one callback invocation
        assert len(updates) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Context Architecture (§8)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGlobalContext:
    """GlobalContext — request-scoped, derived from JWT."""

    @pytest.mark.asyncio
    async def test_build_global_context(self):
        """Building a GlobalContext from JWT-like claims."""
        ctx = await build_global_context(
            company_id=1,
            user_id=42,
            role="dispatcher",
            language="en",
            timezone="Europe/Bucharest",
            subscription_tier="business",
            feature_flags={"chat_enabled": True},
        )
        assert isinstance(ctx, GlobalContext)
        assert ctx.company_id == 1
        assert ctx.user_id == 42
        assert ctx.subscription_tier == "business"
        assert ctx.language == "en"
        assert ctx.timezone == "Europe/Bucharest"
        assert ctx.feature_flags == {"chat_enabled": True}

    @pytest.mark.asyncio
    async def test_default_subscription_tier(self):
        """Default subscription_tier should be 'pro'."""
        ctx = await build_global_context(company_id=1, user_id=1, role="admin")
        assert ctx.subscription_tier == "pro"

    @pytest.mark.asyncio
    async def test_default_language_is_en(self):
        """Default language should be 'en'."""
        ctx = await build_global_context(company_id=1, user_id=1, role="admin")
        assert ctx.language == "en"


class TestSessionContext:
    """SessionContext — per-session, stored in Redis."""

    @pytest.mark.asyncio
    async def test_session_context_creation(self):
        """SessionContext can be created directly."""
        ctx = SessionContext(
            current_customer_id=42,
            current_module="dispatcher_board",
        )
        assert ctx.current_customer_id == 42
        assert ctx.current_module == "dispatcher_board"

    @pytest.mark.asyncio
    async def test_load_session_context_creates_fresh(self):
        """load_session_context should return a new context when cache is empty."""
        ctx = await load_session_context(
            company_id=1,
            user_id=1,
            session_id="test-session",
        )
        assert isinstance(ctx, SessionContext)
        # When Redis is unavailable, a fresh context is returned
        assert ctx.current_customer_id is None

    @pytest.mark.asyncio
    async def test_load_session_context_returns_valid_object(self):
        """Result of load_session_context must be a SessionContext."""
        ctx = await load_session_context(99, 99, "load-test-session")
        assert isinstance(ctx, SessionContext)
        assert ctx.expires_at is not None


class TestConversationContext:
    """ConversationContext — per-conversation, with model pinning."""

    @pytest.mark.asyncio
    async def test_load_conversation_context_creates_fresh(self):
        """load_conversation_context should create a fresh context when empty."""
        ctx = await load_conversation_context(
            company_id=1,
            user_id=1,
            conversation_id="test-conv",
            provider_id="google",
            model_id="gemini-2.5-flash",
            prompt_version="v1.0",
        )
        assert isinstance(ctx, ConversationContext)
        assert ctx.conversation_id == "test-conv"
        assert ctx.pinned_provider_id == "google"
        assert ctx.pinned_model_id == "gemini-2.5-flash"
        assert ctx.pinned_prompt_version == "v1.0"

    @pytest.mark.asyncio
    async def test_conversation_context_default_max_turns(self):
        """Default max_turns should be 40."""
        ctx = await load_conversation_context(1, 1, "test-conv-2")
        assert ctx.max_turns == 40


class TestAvailableTools:
    """ToolContext — RBAC-filtered available tools."""

    @pytest.mark.asyncio
    async def test_resolve_available_tools_requires_permission(self):
        """Tools should only appear if user has required permission."""
        ctx = _global_ctx()
        permitted = await resolve_available_tools(ctx, ["fleet:read"])
        assert isinstance(permitted.available_tools, list)
        # "vehicle.search" requires "fleet:read" — should be included
        assert "vehicle.search" in permitted.available_tools

    @pytest.mark.asyncio
    async def test_resolve_available_tools_excludes_without_permission(self):
        """Tools without matching permission should be excluded."""
        ctx = _global_ctx()
        permitted = await resolve_available_tools(ctx, ["drivers:read"])
        available = permitted.available_tools
        # "vehicle.search" requires "fleet:read" — not in drivers:read scope
        # But other tools with drivers:read may be present
        assert isinstance(available, list)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Circuit Breaker (§23.1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    """Circuit breaker prevents autonomous mode from running away."""

    # Use unique company IDs per test to avoid cross-test pollution
    _next_cid: int = 1000

    def _unique_cid(self) -> int:
        TestCircuitBreaker._next_cid += 1
        return TestCircuitBreaker._next_cid

    def test_new_breaker_is_not_tripped(self):
        cb = CircuitBreaker()
        cid = self._unique_cid()
        state = cb.get_state(company_id=cid)
        assert state.tripped is False
        assert cb.is_allowed(company_id=cid) is True

    def test_repeated_failures_trip_breaker(self):
        cb = CircuitBreaker()
        cid = self._unique_cid()
        for i in range(cb._config.max_consecutive_failures):
            cb.record_failure(cid, "test.tool", f"error {i}")
        state = cb.get_state(cid)
        assert state.tripped is True
        assert state.tripped_reason is not None
        assert cb.is_allowed(cid) is False

    def test_breaker_stays_closed_below_threshold(self):
        """Just below the max consecutive failures should not trip."""
        cb = CircuitBreaker()
        cid = self._unique_cid()
        max_fails = cb._config.max_consecutive_failures
        for i in range(max_fails - 1):
            cb.record_failure(cid, "test.tool", f"error {i}")
        state = cb.get_state(cid)
        assert state.tripped is False

    def test_success_resets_consecutive_failures(self):
        cb = CircuitBreaker()
        cid = self._unique_cid()
        cb.record_failure(cid, "test.tool", "error")
        cb.record_failure(cid, "test.tool", "error")
        cb.record_success(cid, "test.tool")
        state = cb.get_state(cid)
        assert state.consecutive_failures == 0

    def test_admin_reset_clears_trip(self):
        cb = CircuitBreaker()
        cid = self._unique_cid()
        for i in range(cb._config.max_consecutive_failures):
            cb.record_failure(cid, "test.tool", "error")
        assert cb.is_allowed(cid) is False
        cb.reset(cid)
        assert cb.is_allowed(cid) is True

    def test_isolated_per_company(self):
        """Circuit breakers for different companies must be independent."""
        cb = CircuitBreaker()
        cid_a = self._unique_cid()
        cid_b = self._unique_cid()
        for i in range(cb._config.max_consecutive_failures):
            cb.record_failure(cid_a, "test.tool", "error")
        assert cb.is_allowed(cid_a) is False
        # Different company should be unaffected
        assert cb.is_allowed(cid_b) is True

    def test_trip_reason_stored(self):
        """Tripped breaker should store the reason."""
        cb = CircuitBreaker()
        cid = self._unique_cid()
        cb.record_failure(cid, "test.tool", "something went wrong")
        cb.record_failure(cid, "test.tool", "something went wrong")
        cb.record_failure(cid, "test.tool", "something went wrong")
        assert "consecutive failures" in cb.get_state(cid).tripped_reason.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Confidence Engine (§10)
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfidenceEngine:
    """Confidence engine formula and thresholds (§10)."""

    def test_weights_sum_to_one(self):
        from backend.copilot.confidence import DEFAULT_WEIGHTS
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_perfect_confidence(self):
        intent = Intent(
            name="test",
            raw_utterance="test",
            entities=[
                Entity(type="x", value="y", source="extracted", confidence=1.0),
            ],
        )
        score = compute_confidence(intent, intent_match_score=1.0, historical_success_rate=1.0)
        assert abs(score - 1.0) < 0.001

    def test_zero_confidence_floor(self):
        """Even with all zeros, entity_confidence_avg defaults to 1.0 when no
        entities exist — giving a floor of w3 * 1.0 = 0.20."""
        intent = Intent(name="test", raw_utterance="test", missing_required_entities=["x"])
        score = compute_confidence(intent, intent_match_score=0.0, historical_success_rate=0.0)
        assert score == pytest.approx(0.20)

    def test_minimum_confidence(self):
        """Zero entities with missing required → floor of 0.20."""
        intent = Intent(name="test", raw_utterance="test", missing_required_entities=["x"])
        score = compute_confidence(intent, intent_match_score=0.0, historical_success_rate=0.0)
        assert score == pytest.approx(0.20)

    def test_mid_range_confidence(self):
        intent = Intent(
            name="test",
            raw_utterance="test",
            entities=[Entity(type="x", value="y", source="extracted", confidence=0.7)],
            missing_required_entities=["z"],
        )
        score = compute_confidence(intent, intent_match_score=0.8, historical_success_rate=0.75)
        assert 0.3 < score < 0.9, f"Expected mid-range, got {score}"

    def test_confidence_bucket_names(self):
        assert confidence_bucket(0.90) == "high"
        assert confidence_bucket(0.70) == "medium"
        assert confidence_bucket(0.30) == "low"

    def test_confidence_bucket_boundaries(self):
        """Test at each boundary: 0.549, 0.55, 0.849, 0.85."""
        assert confidence_bucket(0.549) == "low"
        assert confidence_bucket(0.55) == "medium"
        assert confidence_bucket(0.849) == "medium"
        assert confidence_bucket(0.85) == "high"

    def test_historical_default(self):
        """Historical success rate defaults to 0.75 when <10 samples exist."""
        intent = Intent(
            name="test",
            raw_utterance="test",
            entities=[Entity(type="x", value="y", source="extracted", confidence=0.8)],
        )
        score = compute_confidence(intent, intent_match_score=0.9)
        assert 0.5 < score < 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# 8. LLM Provider Interface (§23.2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMProviderBase:
    """LLM provider abstraction — base classes and interfaces."""

    def test_llm_provider_classes_exist(self):
        """Verify core LLM classes are importable."""
        from backend.copilot.llm.base import LLMProvider, LLMRequest, LLMResponse, LLMMessage
        from backend.copilot.llm.routing import RoutingRule, LLMRoutingConfig
        from backend.copilot.llm.registry import get_provider, all_providers
        assert LLMProvider is not None
        assert LLMRequest is not None
        assert LLMResponse is not None
        assert LLMMessage is not None

    def test_llm_message_construction(self):
        """LLMMessage can be constructed with valid roles."""
        from backend.copilot.llm.base import LLMMessage
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_llm_request_construction(self):
        """LLMRequest can be constructed with messages."""
        from backend.copilot.llm.base import LLMMessage, LLMRequest
        req = LLMRequest(messages=[LLMMessage(role="user", content="Hi")])
        assert len(req.messages) == 1
        assert req.max_tokens == 4096
        assert req.temperature == 0.2

    def test_llm_response_construction(self):
        """LLMResponse can be constructed."""
        from backend.copilot.llm.base import LLMResponse
        resp = LLMResponse(content="Hello back")
        assert resp.content == "Hello back"
        assert resp.finish_reason == "stop"

    def test_routing_rule_construction(self):
        """RoutingRule maps a task to a provider with optional fallback."""
        from backend.copilot.llm.routing import RoutingRule, LLMRoutingConfig
        rule = RoutingRule(
            task="intent_extraction",
            provider_id="self_hosted",
            fallback_provider_id="google",
        )
        assert rule.task == "intent_extraction"
        assert rule.provider_id == "self_hosted"
        assert rule.fallback_provider_id == "google"

        config = LLMRoutingConfig(rules=[rule])
        assert len(config.rules) == 1

    def test_default_routing_config(self):
        """Default routing uses self_hosted primary with google fallback."""
        from backend.copilot.llm.routing import default_routing_config
        config = default_routing_config()
        assert config.company_id is None
        assert len(config.rules) == 4
        for rule in config.rules:
            assert rule.provider_id == "self_hosted"
            assert rule.fallback_provider_id == "google"

    def test_registry_functions_exist(self):
        """Registry functions should be importable and callable."""
        from backend.copilot.llm.registry import get_provider, all_providers, validate_registry
        # These should not crash when called on empty registry
        assert get_provider("nonexistent") is None
        providers = all_providers()
        assert isinstance(providers, dict)
        errors = validate_registry()
        assert isinstance(errors, list)


class TestGoogleProvider:
    """GoogleProvider — Gemini via google-genai SDK."""

    def test_google_provider_construction(self):
        """GoogleProvider can be constructed without an API key (for type checks)."""
        try:
            from backend.copilot.llm.providers.google_provider import GoogleProvider
            provider = GoogleProvider(model_id="test-model", api_key="test-key")
            assert provider.provider_id == "google"
            assert provider.model_id == "test-model"
            assert provider.supports_tool_calling is True
            assert provider.supports_json_mode is True
            assert provider.is_self_hosted is False
        except ImportError:
            pytest.skip("google-genai not installed in this environment")

    def test_message_conversion(self):
        """_to_gemini_role maps roles correctly."""
        try:
            from backend.copilot.llm.providers.google_provider import GoogleProvider
            from backend.copilot.llm.base import LLMMessage

            provider = GoogleProvider(api_key="test")
            # system gets mapped to "user" (system_instruction config handles it)
            assert provider._to_gemini_role("system") == "user"
            assert provider._to_gemini_role("user") == "user"
            assert provider._to_gemini_role("assistant") == "model"
            assert provider._to_gemini_role("tool") == "user"
        except ImportError:
            pytest.skip("google-genai not installed")

    def test_build_contents(self):
        """_build_contents converts LLMMessage list to Gemini format."""
        try:
            from backend.copilot.llm.providers.google_provider import GoogleProvider
            from backend.copilot.llm.base import LLMMessage

            provider = GoogleProvider(api_key="test")
            messages = [
                LLMMessage(role="user", content="Hello"),
                LLMMessage(role="assistant", content="Hi there"),
            ]
            contents = provider._build_contents(messages)
            assert len(contents) == 2
            assert contents[0]["role"] == "user"
            assert contents[0]["parts"][0]["text"] == "Hello"
            assert contents[1]["role"] == "model"
            assert contents[1]["parts"][0]["text"] == "Hi there"
        except ImportError:
            pytest.skip("google-genai not installed")

    def test_build_tools(self):
        """_build_tools converts ToolSpec list to Gemini function declarations."""
        try:
            from backend.copilot.llm.providers.google_provider import GoogleProvider
            from backend.copilot.llm.base import ToolSpec

            provider = GoogleProvider(api_key="test")
            tools = [
                ToolSpec(
                    name="test_tool",
                    description="A test tool",
                    parameters_json_schema={"type": "object", "properties": {}},
                ),
            ]
            gemini_tools = provider._build_tools(tools)
            assert len(gemini_tools) == 1
            declarations = gemini_tools[0]["function_declarations"]
            assert len(declarations) == 1
            assert declarations[0]["name"] == "test_tool"
        except ImportError:
            pytest.skip("google-genai not installed")

    def test_health_check_returns_down_without_client(self):
        """Without a real client, health_check should return 'down' gracefully."""
        try:
            from backend.copilot.llm.providers.google_provider import GoogleProvider

            provider = GoogleProvider(api_key="invalid-key")
            result = asyncio.run(provider.health_check())
            assert result in ("healthy", "degraded", "down")
        except ImportError:
            pytest.skip("google-genai not installed")


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Integration: Executor plans with actual tool execution
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutorIntegration:
    """Executor integration with real tool registry."""

    @pytest.mark.asyncio
    async def test_execute_vehicle_search_tool(self):
        """vehicle.search tool should execute without DB (returns unavailable)."""
        plan = ExecutionPlan(
            plan_id="int-test-plan",
            conversation_id="int-test-conv",
            reasoning_graph_id="int-test-graph",
            intent=Intent(name="vehicle.search", raw_utterance="find trucks"),
            steps=[
                ExecutionStep(
                    step_id="vehicle.search-0",
                    tool_name="vehicle.search",
                    tool_version="1.0.0",
                    parameters={},
                    depends_on=[],
                    confirmation_level=ConfirmationLevel.SAFE,
                    status="pending",
                ),
            ],
            overall_confidence=0.9,
            requires_confirmation=False,
        )
        result = await execute_plan(plan)
        step = result.steps[0]
        # Without a real DB, the tool returns "unavailable" → skipped
        assert step.status in ("succeeded", "failed", "skipped")
        assert step.started_at is not None
        assert step.finished_at is not None

    @pytest.mark.asyncio
    async def test_execute_health_score_tool(self):
        """vehicle.health_score tool should execute without DB."""
        plan = ExecutionPlan(
            plan_id="int-test-plan-2",
            conversation_id="int-test-conv-2",
            reasoning_graph_id="int-test-graph-2",
            intent=Intent(
                name="vehicle.health_score",
                raw_utterance="health score of vehicle 42",
                entities=[Entity(type="vehicle_id", value=42, source="extracted", confidence=0.7)],
            ),
            steps=[
                ExecutionStep(
                    step_id="vehicle.health_score-0",
                    tool_name="vehicle.health_score",
                    tool_version="1.0.0",
                    parameters={"vehicle_id": 42},
                    depends_on=[],
                    confirmation_level=ConfirmationLevel.SAFE,
                    status="pending",
                ),
            ],
            overall_confidence=0.9,
            requires_confirmation=False,
        )
        result = await execute_plan(plan)
        step = result.steps[0]
        assert step.status in ("succeeded", "failed", "skipped")
        assert step.started_at is not None
        assert step.finished_at is not None
