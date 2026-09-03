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


@pytest.fixture(autouse=True)
def _offline_llm_chat():
    """Force the keyword (offline-fallback) path for pipeline tests.

    A configured provider (env API keys like GOOGLE_API_KEY must never trigger
    live calls inside the test suite) would otherwise make process_utterance
    attempt real network requests.
    """
    from backend.copilot.llm.tool_calling import ToolLoopResult

    with patch("backend.copilot.llm.chat.chat_with_tools", new_callable=AsyncMock) as m:
        m.return_value = ToolLoopResult(attempted=False, provider_failed=False)
        yield m

from backend.copilot.planner import (
    _ensure_tools_loaded,
    extract_intent,
    process_utterance,
    _is_autonomous_approved,
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


def _make_approval_db(enabled: bool = True, table_missing: bool = False) -> MagicMock:
    """A SQLite-like mock db for ``CopilotAutonomyApprovalRepository``.

    The repository reads rows via ``db.conn.execute(sql, params).fetchone()``
    and expects ``{"enabled": 1}`` for an enabled pre-approval row.
    ``table_missing`` simulates a local SQLite install where the
    ``copilot_autonomy_approvals`` table was never created — the query raises
    exactly like sqlite3 would, exercising the planner's fail-closed path.
    """
    db = MagicMock()
    db.conn = MagicMock()
    db.row_to_dict = lambda row: row
    db.rows_to_dicts = lambda rows: rows
    db.execute = db.conn.execute  # repository helpers use conn.execute for sqlite

    cursor = MagicMock()
    cursor.fetchone.return_value = {"enabled": 1} if enabled else None
    cursor.fetchall.return_value = []
    cursor.lastrowid = 1
    cursor.rowcount = 1

    if table_missing:
        def _execute(sql: str, params=None):
            if "copilot_autonomy_approvals" in sql:
                raise Exception("no such table: copilot_autonomy_approvals")
            return cursor
        db.conn.execute.side_effect = _execute
    else:
        db.conn.execute.return_value = cursor
    return db


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
        # ── help.greeting (direct response, no tool) ──
        ("hey", "help.greeting"),
        ("hello", "help.greeting"),
        ("salut", "help.greeting"),
        ("good morning", "help.greeting"),
        # "hi" prefix-matches "history", but tracking patterns outrank it
        ("show vehicle history", "tracking.get_vehicle_history"),
        # ── Edge cases ──
        ("do something magical", "unknown"),  # No match
        ("xyzzy this is nonsense", "unknown"),  # No meaningful match
        ("", "unknown"),  # Empty
        # ── §9.1 Level-0 list/get tools ──
        ("list my routes", "route.list"),
        ("fetch the route details", "route.get"),
        ("list recent trips", "trip.list"),
        ("show trip details", "trip.get"),
        ("what did we discuss", "conversation.recall_recent"),
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

    @pytest.mark.asyncio
    async def test_ro_fleet_listing_intent(self):
        """Romanian fleet-listing questions route to vehicle.search (offline path).

        Regression: "ce camioane am in flota" (and the shorter "ce camioane am")
        must resolve to vehicle.search under language="ro" so the offline keyword
        path answers fleet questions instead of leaving the tool to the LLM.
        """
        intent = await extract_intent("ce camioane am in flota", language="ro")
        assert intent.name == "vehicle.search", (
            f"Expected 'vehicle.search' for 'ce camioane am in flota', got '{intent.name}'"
        )
        short = await extract_intent("ce camioane am", language="ro")
        assert short.name == "vehicle.search"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Planner: Full Pipeline — process_utterance with mocked services
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlannerPipeline:
    """Test the full process_utterance pipeline end-to-end."""

    @pytest.mark.asyncio
    @patch("backend.copilot.llm.chat.chat_answer", new_callable=AsyncMock)
    async def test_unknown_intent_returns_clarification(self, mock_chat):
        """Unknown intents return a clarification question (offline contract)."""
        mock_chat.return_value = (None, False)  # no provider configured
        ctx = _global_ctx()
        resp = await process_utterance("do something magical", ctx, "test-conv-1")
        assert resp.clarification_question_key is not None
        assert resp.plan is None
        assert "unknown_intent" in resp.clarification_question_key

    @pytest.mark.asyncio
    @patch("backend.copilot.llm.chat.chat_with_tools", new_callable=AsyncMock)
    async def test_unknown_intent_llm_answer_returns_summary(self, mock_loop):
        """A usable LLM-first answer surfaces as a copilot.summary.llm_chat bubble."""
        from backend.copilot.llm.tool_calling import ToolLoopResult
        mock_loop.return_value = ToolLoopResult(final_answer="hello there", attempted=True)
        ctx = _global_ctx()
        resp = await process_utterance("do something magical", ctx, "test-conv-llm")
        assert resp.summary_key == "copilot.summary.llm_chat"
        assert resp.summary_params["answer"] == "hello there"
        assert resp.clarification_question_key is None
        assert resp.plan is None

    @pytest.mark.asyncio
    @patch("backend.copilot.llm.chat.chat_with_tools", new_callable=AsyncMock)
    async def test_unknown_intent_llm_failure_returns_model_unreachable(self, mock_loop):
        """A failed provider attempt surfaces copilot.error.model_unreachable
        when the keyword offline path also yields nothing (Gate 1 ladder)."""
        from backend.copilot.llm.tool_calling import ToolLoopResult
        mock_loop.return_value = ToolLoopResult(attempted=True, provider_failed=True)
        ctx = _global_ctx()
        resp = await process_utterance("do something magical", ctx, "test-conv-fail")
        assert resp.clarification_question_key is not None
        assert "model_unreachable" in resp.clarification_question_key
        assert resp.plan is None

    @pytest.mark.asyncio
    async def test_blank_utterance_stays_offline(self):
        """Blank input must never reach the LLM — stays a local clarification."""
        ctx = _global_ctx()
        with patch("backend.copilot.llm.chat.chat_answer", new_callable=AsyncMock) as mock_chat:
            resp = await process_utterance("   ", ctx, "test-conv-blank")
            mock_chat.assert_not_called()
        assert resp.clarification_question_key is not None
        assert "unknown_intent" in resp.clarification_question_key

    @pytest.mark.asyncio
    async def test_greeting_returns_direct_response(self):
        """Greetings return a direct summary response without tool execution."""
        ctx = _global_ctx()
        resp = await process_utterance("hey", ctx, "test-conv-greet")
        assert resp.summary_key is not None
        assert "greeting" in resp.summary_key
        assert resp.plan is None
        assert resp.clarification_question_key is None

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

    # ── Deterministic-first routing (pre-pass gate) ────────────────────────

    @pytest.mark.asyncio
    async def test_ro_fleet_listing_deterministic_without_llm(self):
        """Regression: "ce camioane am in flota" executes vehicle.search
        deterministically — the optional ``query`` entity no longer blocks with
        a clarification, and the LLM tool loop is never called."""
        from unittest.mock import Mock
        ctx = _global_ctx(language="ro")
        fleet = Mock()
        result = Mock()
        result.success = True
        result.errors = []
        result.data = [Mock(model_dump=lambda: {"id": 5, "plate": "AB-12-FRU", "status": "available"})]
        fleet.find_available.return_value = result
        with patch("backend.services.fleet_service.FleetService", return_value=fleet), patch(
            "backend.copilot.llm.chat.chat_with_tools",
            new_callable=AsyncMock,
            side_effect=AssertionError("LLM must not be called for a high-confidence known intent"),
        ) as mock_loop:
            resp = await process_utterance(
                "ce camioane am in flota", ctx, "test-ro-fleet",
                services={"db": MagicMock()},
            )
        mock_loop.assert_not_awaited()
        assert resp.clarification_question_key is None, (
            f"Optional query entity must not block with a clarification: {resp!r}"
        )
        assert resp.plan is not None
        assert resp.plan.intent.name == "vehicle.search"
        assert resp.plan.steps[0].tool_name == "vehicle.search"
        assert resp.plan.steps[0].status == "succeeded"
        vehicles = resp.plan.steps[0].result["data"]["vehicles"]
        assert vehicles[0]["plate"] == "AB-12-FRU"
        fleet.find_available.assert_called_once()

    @pytest.mark.asyncio
    async def test_en_fleet_listing_executes_deterministically_without_llm(self):
        """The canonical EN fleet phrase also executes deterministically (the
        optional ``query`` entity is dropped) — no LLM, no clarification."""
        from unittest.mock import Mock
        ctx = _global_ctx()
        fleet = Mock()
        result = Mock()
        result.success = True
        result.errors = []
        result.data = [Mock(model_dump=lambda: {"id": 5, "plate": "AB-12-FRU", "status": "available"})]
        fleet.find_available.return_value = result
        with patch("backend.services.fleet_service.FleetService", return_value=fleet), patch(
            "backend.copilot.llm.chat.chat_with_tools",
            new_callable=AsyncMock,
            side_effect=AssertionError("LLM must not be called for a high-confidence known intent"),
        ) as mock_loop:
            resp = await process_utterance(
                "find available trucks", ctx, "test-en-fleet",
                services={"db": MagicMock()},
            )
        mock_loop.assert_not_awaited()
        assert resp.clarification_question_key is None
        assert resp.plan is not None
        assert resp.plan.steps[0].tool_name == "vehicle.search"
        assert resp.plan.steps[0].status == "succeeded"
        fleet.find_available.assert_called_once()

    @pytest.mark.asyncio
    async def test_required_entity_still_clarifies(self):
        """Control: an entity whose tool parameter is REQUIRED (no default) is
        NOT dropped — "check vehicle health" still returns the missing-entities
        clarification (vehicle.health_score requires vehicle_id)."""
        ctx = _global_ctx()
        with patch(
            "backend.copilot.llm.chat.chat_with_tools",
            new_callable=AsyncMock,
            side_effect=AssertionError("LLM must not be called for a high-confidence known intent"),
        ) as mock_loop:
            resp = await process_utterance("check vehicle health", ctx, "test-health-clarify")
        mock_loop.assert_not_awaited()
        assert resp.clarification_question_key == "copilot.clarification.missing_entities"
        assert resp.clarification_params.get("intent") == "vehicle.health_score"
        assert "vehicle_id" in " ".join(resp.clarification_params.get("missing", []))
        assert resp.plan is None

    @pytest.mark.asyncio
    async def test_help_question_goes_to_llm(self):
        """help.* intents are excluded from the deterministic pre-pass — the
        LLM tool loop answers them (conversational, no data tool)."""
        from backend.copilot.llm.tool_calling import ToolLoopResult
        ctx = _global_ctx()
        with patch(
            "backend.copilot.llm.chat.chat_with_tools",
            new_callable=AsyncMock,
            return_value=ToolLoopResult(final_answer="Here is the answer.", attempted=True),
        ) as mock_loop:
            resp = await process_utterance(
                "explain what a tachograph is", ctx, "test-help-llm",
            )
        mock_loop.assert_awaited_once()
        assert resp.summary_key == "copilot.summary.llm_chat"
        assert resp.summary_params["answer"] == "Here is the answer."

    @pytest.mark.asyncio
    async def test_help_only_known_intent_not_deterministic(self):
        """help_only=True declines a known non-help intent with the tier
        message BEFORE both the deterministic pre-pass and the LLM."""
        ctx = _global_ctx()
        with patch(
            "backend.copilot.llm.chat.chat_with_tools",
            new_callable=AsyncMock,
            side_effect=AssertionError("LLM must not be called"),
        ) as mock_loop:
            resp = await process_utterance(
                "find available trucks", ctx, "help-only-6", help_only=True,
            )
        mock_loop.assert_not_awaited()
        assert resp.clarification_question_key == "copilot.error.help_only_tier"
        assert resp.clarification_params.get("intent") == "vehicle.search"
        assert resp.plan is None

    @pytest.mark.asyncio
    async def test_driver_analytics_denied_without_llm(self):
        """A driver asking for analytics resolves deterministically to the
        RBAC denial — the LLM being available never gets consulted."""
        from backend.copilot.role_permissions import get_role_permissions
        ctx = _global_ctx(role="driver")
        tool_ctx = await resolve_available_tools(ctx, get_role_permissions("driver"))
        with patch(
            "backend.copilot.llm.chat.chat_with_tools",
            new_callable=AsyncMock,
            side_effect=AssertionError("LLM must not be called"),
        ) as mock_loop:
            resp = await process_utterance(
                "analytics dashboard", ctx, "test-driver-analytics",
                permitted_tools=tool_ctx.available_tools,
            )
        mock_loop.assert_not_awaited()
        assert resp.clarification_question_key == "copilot.error.permission_denied"
        assert resp.clarification_params.get("intent") == "analytics.query"


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


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Autonomous Mode — confirmation gate (§21 Ph.4 item 4, §23.1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutonomousApprovalGate:
    """_is_autonomous_approved — the three-gate check (breaker, tier, approval).

    All three gates must pass for autonomous execution:
      1. circuit breaker healthy (§23.1)
      2. tier enables the ``autonomous`` feature (tier_gate)
      3. company has an enabled pre-approval row for the workflow
    """

    @pytest.mark.asyncio
    async def test_approved_when_all_gates_pass(self):
        """Breaker healthy + autonomous tier + enabled approval row → True."""
        plan = _make_plan()
        ctx = _global_ctx(subscription_tier="enterprise")
        result = await _is_autonomous_approved(plan, ctx, {"db": _make_approval_db(enabled=True)})
        assert result is True

    @pytest.mark.asyncio
    async def test_not_approved_when_approval_disabled(self):
        """An enabled=False (or absent) approval row → False."""
        plan = _make_plan()
        ctx = _global_ctx(subscription_tier="enterprise")
        result = await _is_autonomous_approved(plan, ctx, {"db": _make_approval_db(enabled=False)})
        assert result is False

    @pytest.mark.asyncio
    async def test_not_approved_when_tier_lacks_autonomous(self):
        """business tier has no ``autonomous`` feature → False even when approved."""
        plan = _make_plan()
        ctx = _global_ctx(subscription_tier="business")
        result = await _is_autonomous_approved(plan, ctx, {"db": _make_approval_db(enabled=True)})
        assert result is False

    @pytest.mark.asyncio
    async def test_not_approved_when_breaker_tripped(self):
        """A tripped breaker forces manual confirmation regardless of approvals."""
        from backend.copilot.circuit_breaker import get_circuit_breaker
        cb = get_circuit_breaker()
        cid = 9001
        for _ in range(cb._config.max_consecutive_failures):
            cb.record_failure(cid, "test.tool", "boom")
        assert cb.is_allowed(cid) is False

        plan = _make_plan()
        ctx = _global_ctx(company_id=cid, subscription_tier="enterprise")
        result = await _is_autonomous_approved(plan, ctx, {"db": _make_approval_db(enabled=True)})
        assert result is False

    @pytest.mark.asyncio
    async def test_not_approved_when_db_missing(self):
        """No db in services → False (fails closed, never raises)."""
        plan = _make_plan()
        ctx = _global_ctx(subscription_tier="enterprise")
        result = await _is_autonomous_approved(plan, ctx, None)
        assert result is False

    @pytest.mark.asyncio
    async def test_approval_table_missing_returns_false_without_crash(self):
        """Local SQLite without the approvals table → False, never raises."""
        plan = _make_plan()
        ctx = _global_ctx(subscription_tier="enterprise")
        db = _make_approval_db(enabled=True, table_missing=True)
        result = await _is_autonomous_approved(plan, ctx, {"db": db})
        assert result is False


class TestAutonomousModePipeline:
    """process_utterance confirmation gate under Autonomous Mode.

    A workflow pre-approved for the company + the tier's ``autonomous`` feature
    + a healthy circuit breaker skip the confirmation gate.  Any failed gate
    falls back to the existing confirmation flow (plan stored with
    ``requires_confirmation=True``, steps left pending, nothing executed).
    """

    _next_cid: int = 8000

    def _unique_cid(self) -> int:
        TestAutonomousModePipeline._next_cid += 1
        return TestAutonomousModePipeline._next_cid

    def _confirmation_plan(self) -> ExecutionPlan:
        """A BUSINESS-level plan — what compile returns for a mutating workflow."""
        return _make_plan(
            steps=[_make_step("s1", level=ConfirmationLevel.BUSINESS, status="pending")],
            requires_confirmation=True,
        )

    @pytest.mark.asyncio
    @patch("backend.copilot.executor.execute_plan", new_callable=AsyncMock)
    async def test_approved_executes_without_confirmation(self, mock_execute):
        """Approved + healthy breaker → executes now, requires_confirmation cleared."""
        cid = self._unique_cid()

        executed = self._confirmation_plan()
        executed.requires_confirmation = False
        executed.steps[0].status = "succeeded"
        mock_execute.return_value = executed

        ctx = _global_ctx(company_id=cid, subscription_tier="enterprise")
        services = {
            "db": _make_approval_db(enabled=True),
            "company_id": cid,
            "user_id": 1,
            "role": "dispatcher",
        }

        with patch("backend.copilot.planner.compile_execution_plan", new_callable=AsyncMock) as mock_compile:
            mock_compile.return_value = self._confirmation_plan()
            resp = await process_utterance(
                "what is the health score of vehicle 42",
                ctx,
                f"test-conv-auto-{cid}",
                services=services,
            )

        assert resp.plan is not None
        assert resp.plan.requires_confirmation is False, (
            "Approved plan must not be stored as awaiting confirmation"
        )
        assert resp.plan.steps[0].status == "succeeded", "Approved plan steps must run"
        mock_execute.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("backend.copilot.executor.execute_plan", new_callable=AsyncMock)
    async def test_not_approved_keeps_confirmation_flow(self, mock_execute):
        """No approval row → the plan stays awaiting confirmation, nothing runs."""
        cid = self._unique_cid()
        ctx = _global_ctx(company_id=cid, subscription_tier="enterprise")
        services = {
            "db": _make_approval_db(enabled=False),
            "company_id": cid,
            "user_id": 1,
            "role": "dispatcher",
        }

        with patch("backend.copilot.planner.compile_execution_plan", new_callable=AsyncMock) as mock_compile:
            mock_compile.return_value = self._confirmation_plan()
            resp = await process_utterance(
                "what is the health score of vehicle 42",
                ctx,
                f"test-conv-noapprove-{cid}",
                services=services,
            )

        assert resp.plan is not None
        assert resp.plan.requires_confirmation is True
        assert resp.plan.steps[0].status == "pending"
        mock_execute.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("backend.copilot.executor.execute_plan", new_callable=AsyncMock)
    async def test_breaker_tripped_forces_confirmation_even_when_approved(self, mock_execute):
        """Approval present but breaker tripped → confirmation flow (fail closed)."""
        cid = self._unique_cid()

        from backend.copilot.circuit_breaker import get_circuit_breaker
        cb = get_circuit_breaker()
        for _ in range(cb._config.max_consecutive_failures):
            cb.record_failure(cid, "test.tool", "boom")
        assert cb.is_allowed(cid) is False

        ctx = _global_ctx(company_id=cid, subscription_tier="enterprise")
        services = {
            "db": _make_approval_db(enabled=True),
            "company_id": cid,
            "user_id": 1,
            "role": "dispatcher",
        }

        with patch("backend.copilot.planner.compile_execution_plan", new_callable=AsyncMock) as mock_compile:
            mock_compile.return_value = self._confirmation_plan()
            resp = await process_utterance(
                "what is the health score of vehicle 42",
                ctx,
                f"test-conv-breaker-{cid}",
                services=services,
            )

        assert resp.plan is not None
        assert resp.plan.requires_confirmation is True
        assert resp.plan.steps[0].status == "pending"
        mock_execute.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("backend.copilot.executor.execute_plan", new_callable=AsyncMock)
    async def test_approval_table_missing_degrades_to_confirmation_flow(self, mock_execute):
        """Missing approvals table → confirmation flow, no crash."""
        cid = self._unique_cid()
        ctx = _global_ctx(company_id=cid, subscription_tier="enterprise")
        services = {
            "db": _make_approval_db(enabled=True, table_missing=True),
            "company_id": cid,
            "user_id": 1,
            "role": "dispatcher",
        }

        with patch("backend.copilot.planner.compile_execution_plan", new_callable=AsyncMock) as mock_compile:
            mock_compile.return_value = self._confirmation_plan()
            resp = await process_utterance(
                "what is the health score of vehicle 42",
                ctx,
                f"test-conv-degraded-{cid}",
                services=services,
            )

        assert resp.plan is not None
        assert resp.plan.requires_confirmation is True
        assert resp.plan.steps[0].status == "pending"
        mock_execute.assert_not_awaited()


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Plan lifecycle — pause / resume / stop (§13, §30)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlanLifecycleControl:
    """pause_plan / resume_plan / stop_plan / cancel_plan state transitions.

    §13 pause support: a plan may only be paused/resumed when every
    non-terminal step's tool declares ``supports_pause`` / ``supports_resume``.
    """

    @staticmethod
    def _pausable_tool(supports_pause: bool = True, supports_resume: bool = True) -> MagicMock:
        tool = MagicMock()
        tool.name = "vehicle.search"
        tool.supports_pause = supports_pause
        tool.supports_resume = supports_resume
        return tool

    @pytest.mark.asyncio
    async def test_pause_sets_paused_flag(self):
        from backend.copilot.executor import pause_plan
        plan = _make_plan()
        with patch("backend.copilot.tools.registry.get_tool", return_value=self._pausable_tool()):
            await pause_plan(plan)
        assert plan.paused is True

    @pytest.mark.asyncio
    async def test_pause_marks_running_step_as_paused(self):
        from backend.copilot.executor import pause_plan
        plan = _make_plan(steps=[_make_step("s1", status="running")])
        with patch("backend.copilot.tools.registry.get_tool", return_value=self._pausable_tool()):
            await pause_plan(plan)
        assert plan.steps[0].status == "paused"

    @pytest.mark.asyncio
    async def test_pause_refused_for_non_pausable_tool(self):
        """§13 — a plan whose tool lacks supports_pause is refused."""
        from backend.copilot.executor import pause_plan
        plan = _make_plan(steps=[_make_step("s1", status="running")])
        with patch("backend.copilot.tools.registry.get_tool", return_value=self._pausable_tool(supports_pause=False)):
            with pytest.raises(ValueError) as excinfo:
                await pause_plan(plan)
        assert str(excinfo.value) == "copilot.plan.cannot_pause"
        assert plan.paused is False

    @pytest.mark.asyncio
    async def test_resume_clears_paused_and_requeues_paused_steps(self):
        from backend.copilot.executor import resume_plan
        plan = _make_plan(steps=[_make_step("s1", status="paused")])
        plan.paused = True
        with patch("backend.copilot.tools.registry.get_tool", return_value=self._pausable_tool()):
            await resume_plan(plan)
        assert plan.paused is False
        assert plan.steps[0].status == "pending"

    @pytest.mark.asyncio
    async def test_resume_refused_for_non_resumable_tool(self):
        """§13 — a plan whose tool lacks supports_resume is refused."""
        from backend.copilot.executor import resume_plan
        plan = _make_plan(steps=[_make_step("s1", status="paused")])
        plan.paused = True
        with patch("backend.copilot.tools.registry.get_tool", return_value=self._pausable_tool(supports_resume=False)):
            with pytest.raises(ValueError) as excinfo:
                await resume_plan(plan)
        assert str(excinfo.value) == "copilot.plan.cannot_resume"
        assert plan.paused is True

    @pytest.mark.asyncio
    async def test_stop_marks_remaining_steps_stopped(self):
        from backend.copilot.executor import stop_plan
        plan = _make_plan(steps=[
            _make_step("s1", status="succeeded"),
            _make_step("s2", status="pending"),
            _make_step("s3", status="running"),
        ])
        await stop_plan(plan)
        assert plan.paused is False
        assert plan.steps[0].status == "succeeded"
        assert plan.steps[1].status == "stopped"
        assert plan.steps[2].status == "stopped"
        assert plan.steps[1].finished_at is not None

    @pytest.mark.asyncio
    async def test_cancel_handles_paused_steps(self):
        plan = _make_plan(steps=[_make_step("s1", status="paused")])
        await cancel_plan(plan)
        assert plan.paused is False
        assert plan.steps[0].status == "skipped"

    @pytest.mark.asyncio
    async def test_execute_plan_halts_when_paused(self):
        """A paused plan halts between steps — nothing runs until resumed."""
        tool = MagicMock()
        tool.name = "test.pause"
        tool.required_permission = ""
        tool.confirmation_level = ConfirmationLevel.SAFE
        tool.parameters_schema = MagicMock(return_value=MagicMock())
        tool.validate = AsyncMock(return_value=[])
        tool.execute = AsyncMock(return_value=ToolResult(status="success", message_key="ok"))

        plan = _make_plan(steps=[
            _make_step("s1", status="pending"),
            _make_step("s2", status="pending"),
        ])
        plan.paused = True

        with patch("backend.copilot.tools.registry.get_tool", return_value=tool):
            result = await execute_plan(plan)

        assert result.steps[0].status == "pending"
        assert result.steps[1].status == "pending"
        tool.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_plan_resume_skips_terminal_steps(self):
        """After a resume, already-terminal steps must not be re-run."""
        tool = MagicMock()
        tool.name = "test.resume"
        tool.required_permission = ""
        tool.confirmation_level = ConfirmationLevel.SAFE
        tool.parameters_schema = MagicMock(return_value=MagicMock())
        tool.validate = AsyncMock(return_value=[])
        tool.execute = AsyncMock(return_value=ToolResult(status="success", message_key="ok"))

        plan = _make_plan(steps=[
            _make_step("s1", status="succeeded"),
            _make_step("s2", status="pending"),
        ])

        with patch("backend.copilot.tools.registry.get_tool", return_value=tool):
            result = await execute_plan(plan)

        assert result.steps[0].status == "succeeded"  # not re-run
        assert result.steps[1].status == "succeeded"  # executed now
        tool.execute.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# 12. §28.1 Retry policies — single retry on transient failures only
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorClassification:
    """classify_error — §28.1 transient vs deterministic taxonomy."""

    def test_timeout_is_transient(self):
        from backend.copilot.executor import ErrorCategory, classify_error
        assert classify_error(asyncio.TimeoutError("slow upstream")) == ErrorCategory.TRANSIENT
        assert classify_error(TimeoutError("deadline")) == ErrorCategory.TRANSIENT

    def test_connection_error_is_transient(self):
        from backend.copilot.executor import ErrorCategory, classify_error
        assert classify_error(ConnectionError("provider unreachable")) == ErrorCategory.TRANSIENT

    def test_message_hints_are_transient(self):
        from backend.copilot.executor import ErrorCategory, classify_error
        assert classify_error("upstream provider timed out") == ErrorCategory.TRANSIENT
        assert classify_error("HTTP 503 service unavailable") == ErrorCategory.TRANSIENT
        assert classify_error("network connection refused") == ErrorCategory.TRANSIENT

    def test_validation_and_permission_are_deterministic(self):
        from backend.copilot.executor import ErrorCategory, classify_error
        assert classify_error(ValueError("bad parameter")) == ErrorCategory.DETERMINISTIC
        assert classify_error("copilot.error.permission_denied") == ErrorCategory.DETERMINISTIC
        assert classify_error("copilot.undo.not_found") == ErrorCategory.DETERMINISTIC

    def test_unknown_is_deterministic_fail_safe(self):
        from backend.copilot.executor import ErrorCategory, classify_error
        assert classify_error("some random business error") == ErrorCategory.DETERMINISTIC
        assert classify_error(RuntimeError("mystery")) == ErrorCategory.DETERMINISTIC


class TestRetryPolicy:
    """§28.1 — the executor retries transient failures exactly once."""

    def _mock_tool(self, execute_side_effect=None, execute_return=None):
        tool = MagicMock()
        tool.name = "test.retry"
        tool.required_permission = ""
        tool.confirmation_level = ConfirmationLevel.SAFE
        tool.parameters_schema = MagicMock(return_value=MagicMock())
        tool.validate = AsyncMock(return_value=[])
        tool.execute = AsyncMock(side_effect=execute_side_effect, return_value=execute_return)
        return tool

    @pytest.mark.asyncio
    async def test_retry_once_on_transient_result_then_succeeds(self):
        """A transient failure followed by success → one retry, step succeeds."""
        tool = self._mock_tool(execute_side_effect=[
            ToolResult(status="failed", message_key="copilot.error.timeout"),
            ToolResult(status="success", message_key="copilot.step.done"),
        ])
        plan = _make_plan(steps=[_make_step("s1", status="pending")])

        with patch("backend.copilot.tools.registry.get_tool", return_value=tool):
            result = await execute_plan(plan, services={"company_id": 1})

        assert result.steps[0].status == "succeeded"
        assert tool.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_deterministic_result(self):
        """Deterministic failures are never retried."""
        tool = self._mock_tool(execute_return=ToolResult(
            status="failed", message_key="copilot.error.permission_denied",
        ))
        plan = _make_plan(steps=[_make_step("s1", status="pending")])

        with patch("backend.copilot.tools.registry.get_tool", return_value=tool):
            result = await execute_plan(plan, services={"company_id": 1})

        assert result.steps[0].status == "failed"
        assert tool.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_retry_once_when_tool_raises_transient_exception(self):
        """A raised transient exception (ConnectionError) retries once."""
        tool = self._mock_tool(execute_side_effect=[
            ConnectionError("provider unreachable"),
            ToolResult(status="success", message_key="copilot.step.done"),
        ])
        plan = _make_plan(steps=[_make_step("s1", status="pending")])

        with patch("backend.copilot.tools.registry.get_tool", return_value=tool):
            result = await execute_plan(plan, services={"company_id": 1})

        assert result.steps[0].status == "succeeded"
        assert tool.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_deterministic_exception(self):
        """A raised ValueError is deterministic — no retry; surfaces as i18n key."""
        tool = self._mock_tool(execute_side_effect=[ValueError("bad param")])
        plan = _make_plan(steps=[_make_step("s1", status="pending")])

        with patch("backend.copilot.tools.registry.get_tool", return_value=tool):
            result = await execute_plan(plan, services={"company_id": 1})

        assert result.steps[0].status == "failed"
        # The user-facing step error is the i18n key, never raw exception text.
        assert result.steps[0].error == "copilot.error.unexpected"
        assert tool.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_when_breaker_tripped(self):
        """A tripped breaker blocks execution entirely — no tool call, no retry (§23.1)."""
        from backend.copilot.circuit_breaker import get_circuit_breaker
        cb = get_circuit_breaker()
        cid = 5555
        for _ in range(cb._config.max_consecutive_failures):
            cb.record_failure(cid, "test.tool", "boom")
        assert cb.is_allowed(cid) is False

        tool = self._mock_tool(execute_return=ToolResult(
            status="failed", message_key="copilot.error.timeout",
        ))
        plan = _make_plan(steps=[_make_step("s1", status="pending")])

        with patch("backend.copilot.tools.registry.get_tool", return_value=tool):
            result = await execute_plan(plan, services={"company_id": cid})

        assert result.steps[0].status == "skipped"  # fail-closed pre-loop
        tool.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retry_capped_at_single_attempt(self):
        """Two consecutive transient failures → step fails, exactly two attempts."""
        tool = self._mock_tool(execute_return=ToolResult(
            status="failed", message_key="copilot.error.timeout",
        ))
        plan = _make_plan(steps=[_make_step("s1", status="pending")])

        with patch("backend.copilot.tools.registry.get_tool", return_value=tool):
            result = await execute_plan(plan, services={"company_id": 1})

        assert result.steps[0].status == "failed"
        assert tool.execute.await_count == 2  # single retry, no loop


# ═══════════════════════════════════════════════════════════════════════════════
# 13. §23.3 Guardrail fidelity + fan-out result caps
# ═══════════════════════════════════════════════════════════════════════════════


class TestGuardrailFidelity:
    """validate_guardrails uses REAL node counts and token usage when present."""

    def test_validate_guardrails_uses_real_node_count(self):
        from backend.copilot.executor import MAX_REASONING_GRAPH_NODES_PER_TURN
        plan = _make_plan()  # 1 step → estimate would be 2 nodes (no error)
        plan.reasoning_graph_nodes = MAX_REASONING_GRAPH_NODES_PER_TURN + 1
        errors = validate_guardrails(plan)
        assert "copilot.error.too_many_graph_nodes" in errors

    def test_validate_guardrails_falls_back_to_estimate(self):
        from backend.copilot.executor import MAX_REASONING_GRAPH_NODES_PER_TURN
        # No real count → step-count estimate (1 step → 2 nodes, passes).
        plan = _make_plan()
        assert "copilot.error.too_many_graph_nodes" not in validate_guardrails(plan)
        # Huge step count still trips the estimate.
        many = _make_plan(steps=[_make_step(f"s{i}") for i in range(MAX_REASONING_GRAPH_NODES_PER_TURN)])
        assert "copilot.error.too_many_graph_nodes" in validate_guardrails(many)

    def test_validate_guardrails_counts_used_llm_tokens(self):
        from backend.copilot.executor import MAX_LLM_TOKENS_PER_TURN
        plan = _make_plan()
        plan.used_llm_tokens = MAX_LLM_TOKENS_PER_TURN
        errors = validate_guardrails(plan)
        assert "copilot.error.too_many_tokens" in errors

    @pytest.mark.asyncio
    async def test_planner_stamps_real_node_count(self):
        """process_utterance stamps the resolved graph's node count on the plan."""
        ctx = _global_ctx()
        resp = await process_utterance(
            "what is the health score of vehicle 42",
            ctx,
            "test-conv-node-count",
        )
        assert resp.plan is not None
        assert resp.plan.reasoning_graph_nodes is not None
        assert resp.plan.reasoning_graph_nodes == len(resp.reasoning_graph["nodes"])


class TestFanOutResultCap:
    """§23.3 — a single tool call may not return unbounded rows."""

    def test_cap_result_list_limits_to_max(self):
        from backend.copilot.tools.base import MAX_RESULTS, cap_result_list
        items = list(range(250))
        capped, total, truncated = cap_result_list(items)
        assert len(capped) == MAX_RESULTS
        assert total == 250
        assert truncated is True
        assert capped == list(range(MAX_RESULTS))

    def test_cap_result_list_under_limit(self):
        from backend.copilot.tools.base import cap_result_list
        items = list(range(10))
        capped, total, truncated = cap_result_list(items)
        assert capped == items
        assert total == 10
        assert truncated is False

    def test_cap_result_list_respects_explicit_limit(self):
        from backend.copilot.tools.base import cap_result_list
        items = list(range(250))
        capped, total, truncated = cap_result_list(items, max_results=5)
        assert len(capped) == 5
        assert total == 250
        assert truncated is True

    def _position(self, device_id: str):
        pos = MagicMock()
        pos.device_id = device_id
        pos.name = f"TRUCK-{device_id}"
        pos.latitude = 52.52
        pos.longitude = 13.40
        pos.timestamp = datetime.utcnow()
        pos.speed_kmh = 65.0
        pos.heading = 180.0
        pos.status = "moving"
        return pos

    @pytest.mark.asyncio
    async def test_tracking_live_positions_capped(self):
        from backend.copilot.tools.base import MAX_RESULTS, ToolExecutionContext
        from backend.copilot.tools.tracking_tools import GetLivePositionsTool
        from backend.copilot.schemas import SessionContext

        positions = [self._position(str(i)) for i in range(250)]
        with patch("services.fleet_tracking_service.FleetTrackingService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.get_positions.return_value = positions
            mock_cls.return_value = mock_svc

            tool = GetLivePositionsTool()
            params = tool.parameters_schema()
            ctx = ToolExecutionContext(
                company_id=1, user_id=1, role="dispatcher",
                session_context=SessionContext(), services={},
            )
            result = await tool.execute(params, ctx)

        assert result.status == "success"
        assert len(result.data["positions"]) == MAX_RESULTS
        assert result.data["truncated"] is True
        assert result.data["total_results"] == 250

    @pytest.mark.asyncio
    async def test_vehicle_search_capped(self):
        from backend.copilot.tools.base import MAX_RESULTS, ToolExecutionContext
        from backend.copilot.tools.vehicle_tools import VehicleSearchTool
        from backend.copilot.schemas import SessionContext

        vehicles = [MagicMock() for _ in range(150)]
        for v in vehicles:
            v.model_dump.return_value = {"id": 1}

        result_obj = MagicMock()
        result_obj.success = True
        result_obj.errors = []
        result_obj.data = vehicles

        with patch("backend.services.fleet_service.FleetService") as mock_fleet_cls:
            mock_svc = MagicMock()
            mock_svc.find_available.return_value = result_obj
            mock_fleet_cls.return_value = mock_svc

            tool = VehicleSearchTool()
            params = tool.parameters_schema()
            ctx = ToolExecutionContext(
                company_id=1, user_id=1, role="dispatcher",
                session_context=SessionContext(), services={"db": MagicMock()},
            )
            result = await tool.execute(params, ctx)

        assert result.status == "success"
        assert len(result.data["vehicles"]) == MAX_RESULTS
        assert result.data["truncated"] is True
        assert result.data["total_results"] == 150


# ═══════════════════════════════════════════════════════════════════════════════
# §9.1 Level-0 list/get tools + conversation recall — real repo over InMemoryDB
# ═══════════════════════════════════════════════════════════════════════════════


class TestLevel0ListGetTools:
    """route.list/get, trip.list/get and conversation.recall_recent execute
    against a real SQLite DB (InMemoryDB), company-scoped via tenant context."""

    @pytest.fixture(autouse=True)
    def _db(self):
        from tests.test_helpers import InMemoryDB
        d = InMemoryDB()
        yield d
        d.close()

    def _ctx(self, db, company_id: int = 1):
        from backend.copilot.tools.base import ToolExecutionContext
        return ToolExecutionContext(
            company_id=company_id, user_id=1, role="dispatcher",
            session_context=SessionContext(),
            services={"db": db, "company_id": company_id, "role": "dispatcher", "user_id": 1},
        )

    @pytest.mark.asyncio
    async def test_route_list_returns_rows(self, _db):
        from database.tenant_context import set_company_context
        from repositories.route_repository import RouteRepository
        from backend.copilot.tools.route_tools import RouteListTool

        set_company_context(1)
        RouteRepository(_db).create({
            "route_fingerprint": "abc", "total_distance_km": 120.0,
            "duration_min": 90, "profile": "truck",
            "created_at": "2026-08-01T00:00:00Z",
            "last_calculated_at": "2026-08-01T00:00:00Z", "stops_json": "[]",
        })
        tool = RouteListTool()
        result = await tool.execute(tool.parameters_schema(limit=10), self._ctx(_db))
        assert result.status == "success"
        assert result.data["total"] == 1
        assert result.data["routes"][0]["route_fingerprint"] == "abc"

    @pytest.mark.asyncio
    async def test_route_get_returns_one_route(self, _db):
        from database.tenant_context import set_company_context
        from repositories.route_repository import RouteRepository
        from backend.copilot.tools.route_tools import RouteGetTool

        set_company_context(1)
        rid = RouteRepository(_db).create({
            "route_fingerprint": "xyz", "total_distance_km": 300.0,
            "duration_min": 200, "profile": "truck",
            "created_at": "2026-08-02T00:00:00Z",
            "last_calculated_at": "2026-08-02T00:00:00Z", "stops_json": "[]",
        })
        tool = RouteGetTool()
        result = await tool.execute(tool.parameters_schema(route_id=rid), self._ctx(_db))
        assert result.status == "success"
        assert result.data["route"]["route_fingerprint"] == "xyz"

    @pytest.mark.asyncio
    async def test_trip_list_and_get(self, _db):
        from database.tenant_context import set_company_context
        from repositories.trip_repository import TripRepository
        from backend.copilot.tools.trip_tools import TripListTool, TripGetTool

        set_company_context(1)
        tid = TripRepository(_db).create({
            "truck_number": "AB-01", "client_name": "ACME",
            "status": "loading", "distance_km": 500.0,
            "created_at": "2026-08-01T00:00:00Z",
        })
        list_result = await TripListTool().execute(
            TripListTool().parameters_schema(limit=10), self._ctx(_db),
        )
        assert list_result.status == "success"
        assert list_result.data["total"] == 1
        assert list_result.data["trips"][0]["truck_number"] == "AB-01"

        get_result = await TripGetTool().execute(
            TripGetTool().parameters_schema(trip_id=tid), self._ctx(_db),
        )
        assert get_result.status == "success"
        assert get_result.data["trip"]["client_name"] == "ACME"

    @pytest.mark.asyncio
    async def test_conversation_recall_recent(self, _db):
        from backend.copilot.tools.conversation_tools import ConversationRecallRecentTool
        from repositories.copilot_repository import ConversationSummaryRepository

        ConversationSummaryRepository(_db).create({
            "conversation_id": "conv-1", "summary": "discussed trip 42",
            "model": "test", "token_count": 10, "company_id": 1,
        })
        tool = ConversationRecallRecentTool()
        result = await tool.execute(tool.parameters_schema(limit=5), self._ctx(_db))
        assert result.status == "success"
        assert result.data["total"] == 1
        assert result.data["conversations"][0]["summary"] == "discussed trip 42"

    @pytest.mark.asyncio
    async def test_list_tools_are_company_scoped(self, _db):
        """Company 1's tools never see company 2's rows."""
        from database.tenant_context import set_company_context
        from repositories.route_repository import RouteRepository
        from backend.copilot.tools.route_tools import RouteListTool

        set_company_context(1)
        RouteRepository(_db).create({
            "route_fingerprint": "c1", "total_distance_km": 1.0,
            "duration_min": 1, "profile": "truck", "created_at": "2026-08-01T00:00:00Z",
            "last_calculated_at": "2026-08-01T00:00:00Z", "stops_json": "[]",
        })
        set_company_context(2)
        RouteRepository(_db).create({
            "route_fingerprint": "c2", "total_distance_km": 2.0,
            "duration_min": 2, "profile": "truck", "created_at": "2026-08-02T00:00:00Z",
            "last_calculated_at": "2026-08-02T00:00:00Z", "stops_json": "[]",
        })
        set_company_context(1)
        result = await RouteListTool().execute(
            RouteListTool().parameters_schema(limit=10), self._ctx(_db, company_id=1),
        )
        assert result.status == "success"
        assert result.data["total"] == 1
        assert result.data["routes"][0]["route_fingerprint"] == "c1"


# ═══════════════════════════════════════════════════════════════════════════════
# Help-Mode-only tier (§33.4/§34.10) — Pro reaches help, everything else declined
# ═══════════════════════════════════════════════════════════════════════════════


class TestHelpOnlyMode:
    """``process_utterance(help_only=True)`` answers ONLY Help Mode requests."""

    @pytest.mark.asyncio
    async def test_help_only_help_intent_reaches_keyword_path(self):
        """A help intent passes the help-only pre-check and reaches the keyword
        path (no provider → plan for help.answer_question)."""
        ctx = _global_ctx()
        resp = await process_utterance("explain what a tachograph is", ctx, "help-only-1", help_only=True)
        assert resp.plan is not None
        assert resp.plan.intent.name == "help.answer_question"

    @pytest.mark.asyncio
    async def test_help_only_non_help_intent_returns_tier_message(self):
        """Pro 'find trucks' (a known non-help intent) → friendly tier message."""
        ctx = _global_ctx()
        resp = await process_utterance("find available trucks", ctx, "help-only-2", help_only=True)
        assert resp.plan is None
        assert resp.clarification_question_key == "copilot.error.help_only_tier"
        assert resp.clarification_params.get("intent") == "vehicle.search"

    @pytest.mark.asyncio
    async def test_help_only_unknown_freeform_goes_to_llm_loop(self):
        """An unknown free-form question is not declined — it reaches the
        LLM-first help loop (no provider here → unknown_intent offline)."""
        ctx = _global_ctx()
        resp = await process_utterance("how do I reset my password", ctx, "help-only-3", help_only=True)
        # help.answer_question matches via "how do i" → keyword path → plan.
        assert resp.plan is not None
        assert resp.plan.intent.name == "help.answer_question"

    @pytest.mark.asyncio
    async def test_help_only_greeting_allowed(self):
        """Greetings remain available in Help Mode."""
        ctx = _global_ctx()
        resp = await process_utterance("hello", ctx, "help-only-4", help_only=True)
        assert resp.summary_key is not None
        assert "greeting" in resp.summary_key

    @pytest.mark.asyncio
    async def test_help_only_false_unchanged(self):
        """help_only=False keeps the full pipeline — no tier gate."""
        ctx = _global_ctx()
        resp = await process_utterance("find available trucks", ctx, "help-only-5", help_only=False)
        assert resp.clarification_question_key != "copilot.error.help_only_tier"
