"""Executor §13 long-running dispatch tests.

Covers: Celery dispatch when the broker is available, inline fallback when it
is not (graceful degradation), non-long-running tools never dispatch, and the
pause/resume 409-safety contract for long-running plans.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.copilot.schemas import ConfirmationLevel, ExecutionPlan, ExecutionStep, Intent


def _make_plan(tool_name: str = "freight.search_loads", status: str = "pending",
               parameters: dict | None = None, step_id: str = "step-1") -> ExecutionPlan:
    return ExecutionPlan(
        plan_id="plan-lr",
        conversation_id="conv-lr",
        reasoning_graph_id="rg-lr",
        intent=Intent(
            name=tool_name,
            entities=[],
            missing_required_entities=[],
            raw_utterance="search loads",
        ),
        steps=[
            ExecutionStep(
                step_id=step_id,
                tool_name=tool_name,
                tool_version="1.0.0",
                parameters=parameters or {},
                depends_on=[],
                confirmation_level=ConfirmationLevel.SAFE,
                status=status,
            ),
        ],
        overall_confidence=0.9,
        requires_confirmation=False,
    )


class TestLongRunningDispatch:
    @pytest.mark.asyncio
    async def test_long_running_step_dispatched_when_broker_available(self):
        from backend.copilot.executor import execute_plan

        plan = _make_plan(parameters={"origin": "Bucharest"})
        dispatched_payload = {
            "task_id": "task-abc",
            "progress_key": "copilot:tool-progress:task-abc",
            "status": "dispatched",
            "tool_name": "freight.search_loads",
            "celery_task_id": "celery-1",
        }
        with (
            patch("backend.copilot.executor._is_celery_broker_available", return_value=True),
            patch("backend.copilot.executor._dispatch_long_running_step", return_value=dispatched_payload) as mock_dispatch,
            patch("backend.copilot.executor._run_step_with_retry", new_callable=AsyncMock) as mock_run,
        ):
            result = await execute_plan(
                plan,
                services={"company_id": 1, "user_id": 1, "role": "manager"},
            )

        mock_dispatch.assert_called_once()
        mock_run.assert_not_awaited()
        step = result.steps[0]
        assert step.status == "running"                 # stays in-flight
        assert step.result["task_id"] == "task-abc"     # task handle on the step
        assert step.result["progress_key"] == "copilot:tool-progress:task-abc"

    @pytest.mark.asyncio
    async def test_long_running_step_inline_when_no_broker(self):
        from backend.copilot.executor import execute_plan
        from backend.copilot.schemas import ToolResult

        plan = _make_plan(parameters={"origin": "Bucharest"})
        with (
            patch("backend.copilot.executor._is_celery_broker_available", return_value=False),
            patch("backend.copilot.executor._dispatch_long_running_step") as mock_dispatch,
            patch(
                "backend.copilot.executor._run_step_with_retry",
                new_callable=AsyncMock,
                return_value=ToolResult(status="success", message_key="ok"),
            ),
        ):
            result = await execute_plan(
                plan,
                services={"company_id": 1, "user_id": 1, "role": "manager"},
            )

        mock_dispatch.assert_not_called()
        assert result.steps[0].status == "succeeded"    # inline fallback

    @pytest.mark.asyncio
    async def test_dispatch_failure_falls_back_inline(self):
        """A failed Celery send (broker down at send time) degrades to inline."""
        from backend.copilot.executor import execute_plan
        from backend.copilot.schemas import ToolResult

        plan = _make_plan(parameters={"origin": "Bucharest"})
        with (
            patch("backend.copilot.executor._is_celery_broker_available", return_value=True),
            patch("backend.copilot.executor._dispatch_long_running_step", return_value=None),
            patch(
                "backend.copilot.executor._run_step_with_retry",
                new_callable=AsyncMock,
                return_value=ToolResult(status="success", message_key="ok"),
            ),
        ):
            result = await execute_plan(
                plan,
                services={"company_id": 1, "user_id": 1, "role": "manager"},
            )

        assert result.steps[0].status == "succeeded"

    @pytest.mark.asyncio
    async def test_regular_step_never_dispatched(self):
        """A non-long-running tool runs inline even with a broker present."""
        from backend.copilot.executor import execute_plan
        from backend.copilot.schemas import ToolResult

        plan = _make_plan(tool_name="tracking.get_live_positions")
        with (
            patch("backend.copilot.executor._is_celery_broker_available", return_value=True),
            patch("backend.copilot.executor._dispatch_long_running_step") as mock_dispatch,
            patch(
                "backend.copilot.executor._run_step_with_retry",
                new_callable=AsyncMock,
                return_value=ToolResult(status="success", message_key="ok"),
            ),
        ):
            result = await execute_plan(
                plan,
                services={"company_id": 1, "user_id": 1, "role": "manager"},
            )

        mock_dispatch.assert_not_called()
        assert result.steps[0].status == "succeeded"

    @pytest.mark.asyncio
    async def test_confirm_and_execute_dispatches_long_running(self):
        """The /confirm execution path dispatches long-running steps too."""
        from backend.copilot.executor import confirm_and_execute

        plan = _make_plan(parameters={"origin": "Bucharest"})
        dispatched_payload = {
            "task_id": "task-conf",
            "progress_key": "copilot:tool-progress:task-conf",
            "status": "dispatched",
            "tool_name": "freight.search_loads",
            "celery_task_id": "celery-2",
        }
        with (
            patch("backend.copilot.executor._is_celery_broker_available", return_value=True),
            patch("backend.copilot.executor._dispatch_long_running_step", return_value=dispatched_payload),
            patch("backend.copilot.executor._run_step_with_retry", new_callable=AsyncMock) as mock_run,
        ):
            result = await confirm_and_execute(
                plan,
                services={"company_id": 1, "user_id": 1, "role": "manager"},
            )

        mock_run.assert_not_awaited()
        assert result.steps[0].status == "running"
        assert result.steps[0].result["task_id"] == "task-conf"


class TestLongRunningPauseResume:
    def test_pause_allowed_for_long_running_plan(self):
        """Wave-1 409 enforcement is satisfiable: every long-running tool
        declares supports_pause, so pausing must not raise."""
        import asyncio

        from backend.copilot.executor import pause_plan

        plan = _make_plan(parameters={"origin": "Bucharest"}, status="pending")
        result = asyncio.run(pause_plan(plan))
        assert result.paused is True

    def test_resume_allowed_for_long_running_plan(self):
        import asyncio

        from backend.copilot.executor import pause_plan, resume_plan

        plan = _make_plan(parameters={"origin": "Bucharest"}, status="pending")
        paused = asyncio.run(pause_plan(plan))
        resumed = asyncio.run(resume_plan(paused))
        assert resumed.paused is False

    def test_pause_blocked_for_non_pausable_tool(self):
        """A plan whose tool does NOT declare supports_pause still refuses."""
        import asyncio

        from backend.copilot.executor import pause_plan

        plan = _make_plan(tool_name="whatsapp.send_message", status="pending",
                          parameters={"recipient": "+40712345678", "body": "Hi"})
        with pytest.raises(ValueError):
            asyncio.run(pause_plan(plan))

    def test_heavy_tools_declare_long_running_flags(self):
        """The flagged heavy tools carry long_running + pausable/resumable."""
        from backend.copilot.tools.registry import get_tool

        for name in (
            "document.ocr_import",
            "freight.search_loads",
            "freight.find_best_trucks",
            "export.generate_pdf_report",
            "export.generate_excel",
            "email.send_bulk",
        ):
            tool = get_tool(name)
            assert tool is not None, name
            assert tool.long_running is True, name
            assert tool.supports_pause is True, name
            assert tool.supports_resume is True, name