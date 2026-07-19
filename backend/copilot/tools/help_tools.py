"""Help Mode tools — help.answer_question and help.guide_workflow.

Blueprint: §33 (Help Mode), §34 (Guided UI Mentor System).
Both are Level 0 (SAFE) — read-only, no business data touched.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.copilot.schemas import (
    ConfirmationLevel,
    GuideWorkflowParams,
    HelpAnswerParams,
    ToolResult,
)
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool
from backend.services.documentation_service import get_documentation_service
from backend.services.guided_workflow_service import get_guided_workflow_service

logger = logging.getLogger(__name__)


@register_tool
class HelpAnswerQuestionTool(BaseTool):
    """Answer a conceptual/definitional question from documentation.

    Blueprint: §33.1 — help.answer_question.
    """
    name = "help.answer_question"
    tool_version = "1.0.0"
    description = "Answer questions about how Operion ERP features work"
    required_permission = "help:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = HelpAnswerParams

    async def validate(self, params: HelpAnswerParams, ctx: ToolExecutionContext) -> list[str]:
        errors = []
        if not params.question or not params.question.strip():
            errors.append("copilot.help.error.empty_question")
        if len(params.question) > 2000:
            errors.append("copilot.help.error.question_too_long")
        return errors

    async def execute(self, params: HelpAnswerParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            # Derive language from context (default to English)
            language = ctx.session_context.current_module or "en"

            service = get_documentation_service()
            answer = service.search_and_answer(
                question=params.question,
                language=language,
                active_screen=params.active_screen,
            )

            if not answer.sources:
                return ToolResult(
                    status="success",
                    data={"answer": answer.model_dump()},
                    message_key="copilot.help.no_answer",
                    message_params={"question": params.question},
                )

            return ToolResult(
                status="success",
                data={"answer": answer.model_dump()},
                message_key="copilot.help.answer_ready",
                message_params={
                    "article_count": len(answer.sources),
                },
            )
        except Exception as exc:
            logger.exception("Help answer failed")
            return ToolResult(
                status="failed",
                message_key="copilot.help.error.search_failed",
            )


@register_tool
class GuideWorkflowTool(BaseTool):
    """Guide a user through a multi-step workflow in the UI.

    Blueprint: §34.2 — Guided Walkthrough.
    """
    name = "help.guide_workflow"
    tool_version = "1.0.0"
    description = "Walk users through multi-step workflows with interactive UI guidance"
    required_permission = "help:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    parameters_schema = GuideWorkflowParams

    async def validate(self, params: GuideWorkflowParams, ctx: ToolExecutionContext) -> list[str]:
        errors = []
        if not params.workflow_id or not params.workflow_id.strip():
            errors.append("copilot.help.error.empty_workflow")
        else:
            service = get_guided_workflow_service()
            script = service.get_script(params.workflow_id)
            if script is None:
                errors.append("copilot.help.error.workflow_not_found")
        return errors

    async def execute(self, params: GuideWorkflowParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            service = get_guided_workflow_service()
            script = service.get_script(params.workflow_id)

            if script is None:
                return ToolResult(
                    status="failed",
                    message_key="copilot.help.error.workflow_not_found",
                    message_params={"workflow_id": params.workflow_id},
                )

            # Adjust for familiarity (stub: always "new" for now)
            script = service.adjust_for_familiarity(
                script,
                user_id=str(ctx.user_id),
                company_id=str(ctx.company_id),
                familiarity_level="new",
            )

            return ToolResult(
                status="success",
                data={"walkthrough": script.model_dump()},
                message_key="copilot.guided.ready",
                message_params={"workflow_id": params.workflow_id},
            )
        except Exception as exc:
            logger.exception("Guided workflow failed")
            return ToolResult(
                status="failed",
                message_key="copilot.help.error.workflow_failed",
            )
