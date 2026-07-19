"""Unit tests for WebSocket callback in executor.

Blueprint: §12.1 — WebSocket step update protocol.
"""

import asyncio
from typing import List

import pytest

from backend.copilot.schemas import (
    ConfirmationLevel, ExecutionPlan, ExecutionStep, Intent,
)
from backend.copilot.executor import confirm_and_execute


class TestWebsocketCallbackIntegration:
    """Verify WebSocket callbacks fire during execution."""

    @pytest.mark.asyncio
    async def test_callback_fires_for_each_step(self):
        """Confirm callback fires with correct arguments for each step."""
        updates: List[str] = []

        def on_update(step_id: str, status: str, tool_name: str):
            updates.append(f"{step_id}:{status}:{tool_name}")

        step = ExecutionStep(
            step_id="ws-test", tool_name="vehicle.search", tool_version="1.0.0",
            parameters={}, depends_on=[],
            confirmation_level=ConfirmationLevel.SAFE, status="pending",
        )
        plan = ExecutionPlan(
            plan_id="ws-plan", conversation_id="ws-conv",
            reasoning_graph_id="ws-graph",
            intent=Intent(name="vehicle.search", raw_utterance="test"),
            steps=[step], overall_confidence=1.0, requires_confirmation=False,
        )
        result = await confirm_and_execute(plan, services={}, on_step_update=on_update)
        assert len(updates) >= 1, f"Expected at least 1 callback, got {updates}"
        # Verify at least one status transition was recorded
        first = updates[0].split(":")
        assert len(first) == 3, f"Callback format wrong: {updates[0]}"
        assert first[0] == "ws-test", f"Wrong step_id: {first[0]}"
