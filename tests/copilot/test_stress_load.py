"""Stress and load tests — push the Co-Pilot system to its limits.

Tests cover:
- Concurrent plan execution (many plans at once)
- Many tools registered simultaneously
- Large parameter payloads
- Rapid succession of chat requests
- Repeating identical operations many times
"""
from __future__ import annotations


import asyncio
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.executor import (
    execute_plan, cancel_plan, confirm_and_execute,
    validate_guardrails, MAX_TOOL_CALLS_PER_PLAN,
)
from backend.copilot.schemas import (
    ConfirmationLevel, ExecutionPlan, ExecutionStep, GlobalContext,
    Intent, SessionContext, ToolResult,
)
from backend.copilot.planner import process_utterance, extract_intent, _ensure_tools_loaded
from backend.copilot.circuit_breaker import CircuitBreaker, CircuitBreakerConfig


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def ensure_tools():
    _ensure_tools_loaded()

@pytest.fixture(autouse=True)
def reset_cb():
    from backend.copilot.circuit_breaker import get_circuit_breaker
    get_circuit_breaker()._states.clear()


# ── Stress: Concurrent Plans ─────────────────────────────────────────────

class TestConcurrentExecution:
    """Stress test: many plans executing concurrently."""

    @pytest.mark.asyncio
    async def test_10_concurrent_safe_plans(self):
        """Execute 10 SAFE plans concurrently — no crashes, all complete."""
        plans = []
        for i in range(10):
            step = ExecutionStep(
                step_id=f"stress-s{i}", tool_name="vehicle.search", tool_version="1.0.0",
                parameters={}, depends_on=[], confirmation_level=ConfirmationLevel.SAFE,
                status="pending",
            )
            plan = ExecutionPlan(
                plan_id=f"stress-plan-{i}", conversation_id="stress-conv",
                reasoning_graph_id="stress-graph",
                intent=Intent(name="vehicle.search", raw_utterance="test"),
                steps=[step], overall_confidence=1.0, requires_confirmation=False,
            )
            plans.append(plan)

        results = await asyncio.gather(*[
            execute_plan(p, services={}) for p in plans
        ], return_exceptions=True)

        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Concurrent execution errors: {errors}"
        assert all(
            result.steps[0].status in ("succeeded", "failed", "skipped")
            for result in results if not isinstance(result, Exception)
        ), "All plans should complete"

    @pytest.mark.asyncio
    async def test_5_concurrent_confirmed_plans(self):
        """Execute 5 confirmed plans concurrently."""
        plans = []
        for i in range(5):
            step = ExecutionStep(
                step_id=f"stress-c{i}", tool_name="vehicle.search", tool_version="1.0.0",
                parameters={}, depends_on=[], confirmation_level=ConfirmationLevel.BUSINESS,
                status="pending",
            )
            plan = ExecutionPlan(
                plan_id=f"stress-conf-{i}", conversation_id="stress-conv",
                reasoning_graph_id="stress-graph",
                intent=Intent(name="vehicle.search", raw_utterance="test"),
                steps=[step], overall_confidence=1.0, requires_confirmation=True,
            )
            plans.append(plan)

        results = await asyncio.gather(*[
            confirm_and_execute(p, services={}) for p in plans
        ], return_exceptions=True)

        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Concurrent confirmation errors: {errors}"

    @pytest.mark.asyncio
    async def test_20_planner_requests_in_rapid_succession(self):
        """20 rapid planner requests should all complete without crashing."""
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="business",
        )
        utterances = [f"search for {i}" for i in range(20)]
        results = await asyncio.gather(*[
            process_utterance(u, ctx, f"rapid-{i}")
            for i, u in enumerate(utterances)
        ], return_exceptions=True)

        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Rapid planner errors: {errors}"


# ── Stress: Circuit Breaker ──────────────────────────────────────────────

class TestCircuitBreakerStress:
    """Circuit breaker behavior under stress (§23.1)."""

    def test_breaker_trips_after_repeated_failures(self):
        """Breaker should trip after max_consecutive_failures."""
        cb = CircuitBreaker()
        max_fails = cb._config.max_consecutive_failures
        for i in range(max_fails):
            assert cb.is_allowed(1) is True, f"Should still be allowed at failure {i}"
            cb.record_failure(1, "test.tool", f"error {i}")
        assert cb.is_allowed(1) is False, "Should be tripped after max failures"

    def test_breaker_recovers_after_admin_reset(self):
        """Admin can reset a tripped breaker."""
        cb = CircuitBreaker()
        for i in range(cb._config.max_consecutive_failures):
            cb.record_failure(1, "test.tool", "error")
        assert cb.is_allowed(1) is False
        cb.reset(1)
        assert cb.is_allowed(1) is True, "Should recover after reset"

    def test_breaker_tracks_per_company(self):
        """Circuit breaker state is per-company, not global."""
        cb = CircuitBreaker()
        for i in range(cb._config.max_consecutive_failures):
            cb.record_failure(1, "test.tool", "error")
        assert cb.is_allowed(2) is True, "Company 2 should be unaffected"


# ── Stress: Large Parameter Sets ─────────────────────────────────────────

class TestLargeParameterStress:
    """Stress test with large parameter payloads."""

    def test_large_stops_list(self):
        """Route planning with many stops should not crash."""
        from backend.copilot.tools.registry import get_tool
        route_tool = get_tool("route.plan_multistop")
        if route_tool is None:
            pytest.skip("route.plan_multistop not registered")

        # Create params with 50 stops
        stops = [f"Stop {i}, City {i}" for i in range(50)]
        params = route_tool.parameters_schema(stops=stops)
        assert len(params.stops) == 50

    def test_many_document_ids(self):
        """Export tools with many entity IDs should not crash."""
        from backend.copilot.tools.registry import get_tool
        export_tool = get_tool("export.generate_pdf_report")
        if export_tool is None:
            pytest.skip("export.generate_pdf_report not registered")
        entity_ids = list(range(100))
        params = export_tool.parameters_schema(
            entity_type="trip", entity_ids=entity_ids
        )
        assert len(params.entity_ids) == 100
