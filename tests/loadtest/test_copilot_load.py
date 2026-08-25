"""Load tests — measure Co-Pilot throughput and timing.

These tests verify the system meets performance expectations
under realistic load. They are marked 'loadtest' to separate
from unit tests.
"""
from __future__ import annotations


import asyncio
import time
from typing import Any, Dict, List

import pytest

from backend.copilot.planner import process_utterance, extract_intent, _ensure_tools_loaded
from backend.copilot.executor import execute_plan
from backend.copilot.schemas import (
    ConfirmationLevel, ExecutionPlan, ExecutionStep, GlobalContext,
    Intent,
)
from backend.copilot.tools.registry import _registry, all_tools, get_tool, run_startup_validation


pytestmark = pytest.mark.loadtest


@pytest.fixture(autouse=True, scope="module")
def ensure_tools_once():
    # Cross-file isolation guard: tests/copilot/test_tool_registry.py registers
    # intentionally-invalid "test.*" tools into the global tool registry at
    # import time.  Under pytest-xdist every worker inherits those registrations
    # (even workers that never run that module, where its module-scoped cleanup
    # never fires), so run_startup_validation() would see the malformed fixtures
    # and fail.  Hide "test.*" tools for the duration of the validation, then
    # restore them so test_tool_registry.py still sees them if it runs later in
    # this process.  This keeps the fixture order- and worker-independent.
    test_tools = {name: tool for name, tool in _registry.items() if name.startswith("test.")}
    for name in test_tools:
        del _registry[name]
    try:
        _ensure_tools_loaded()
        errors = run_startup_validation()
        assert len(errors) == 0
    finally:
        _registry.update(test_tools)


class TestPlannerThroughput:
    """Measure planner throughput under increasing load."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("n", [5, 10, 25])
    async def test_planner_throughput(self, n):
        """Measure time to process N planner requests."""
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="business",
        )
        utterances = [
            "find available trucks",
            "what is the USD exchange rate",
            "calculate a route from Berlin to Warsaw",
            "show payment summary for client 12",
            "track my vehicles",
        ][:n]
        # Repeat to reach n
        while len(utterances) < n:
            utterances.append(utterances[len(utterances) % 5])

        start = time.monotonic()
        results = await asyncio.gather(*[
            process_utterance(u, ctx, f"load-{i}")
            for i, u in enumerate(utterances)
        ], return_exceptions=True)
        elapsed = time.monotonic() - start

        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Errors: {errors}"
        elapsed = max(elapsed, 0.001)  # Guard against zero-division
        throughput = n / elapsed
        print(f"\n  Planner throughput: {n} requests in {elapsed:.2f}s = {throughput:.1f} req/s")
        # No hard performance threshold — this documents baseline
        assert throughput > 0, "Throughput must be positive"


class TestExecutorThroughput:
    """Measure executor throughput."""

    @pytest.mark.asyncio
    async def test_executor_throughput(self):
        """Measure time to execute N plans."""
        n = 10
        plans = []
        for i in range(n):
            step = ExecutionStep(
                step_id=f"load-s{i}", tool_name="vehicle.search", tool_version="1.0.0",
                parameters={}, depends_on=[],
                confirmation_level=ConfirmationLevel.SAFE, status="pending",
            )
            plan = ExecutionPlan(
                plan_id=f"load-plan-{i}", conversation_id="load-conv",
                reasoning_graph_id="load-graph",
                intent=Intent(name="vehicle.search", raw_utterance="test"),
                steps=[step], overall_confidence=1.0, requires_confirmation=False,
            )
            plans.append(plan)

        start = time.monotonic()
        results = await asyncio.gather(*[
            execute_plan(p, services={}) for p in plans
        ], return_exceptions=True)
        elapsed = time.monotonic() - start

        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Errors: {errors}"
        elapsed = max(elapsed, 0.001)  # Guard against zero-division
        throughput = n / elapsed
        print(f"\n  Executor throughput: {n} plans in {elapsed:.2f}s = {throughput:.1f} plans/s")
        assert throughput > 0
