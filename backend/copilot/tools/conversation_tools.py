"""Conversation tools — §11 conversation-summary recall.

Level-0 read tools wrapping the ``conversation_summary`` repository.  The
recall tool answers "what did we discuss" — it returns the most recent
persisted conversation summaries for the caller's company.  It NEVER
hallucinates content: every row comes from ``conversation_summary``, which is
written by the pipeline after each turn.
"""

from __future__ import annotations

import logging
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool
from repositories.copilot_repository import ConversationSummaryRepository

logger = logging.getLogger(__name__)


class ConversationRecallParams(BaseModel):
    """Input parameters for ``conversation.recall_recent``."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(10, ge=1, le=50, description="Max recent conversations to recall")


@register_tool
class ConversationRecallRecentTool(BaseTool):
    """Recall what was recently discussed with the Co-Pilot.

    Returns the most recent conversation summaries persisted for the caller's
    company (conversation_id, summary, model, created_at).  Content is read
    from the conversation_summary store only — never invented.
    """

    name = "conversation.recall_recent"
    tool_version = "1.0.0"
    description = (
        "Recall what was recently discussed: return the most recent "
        "conversation summaries for the company (what the user and the "
        "Co-Pilot talked about). Never invents content — reads only."
    )
    # Permission: ``documents:read`` is the closest "records" permission present
    # in EVERY role's set (driver/dispatcher/manager), so every authenticated
    # copilot caller may recall their own company's conversation summaries.
    # (A dedicated ``conversations:read`` permission would be cleaner but would
    # require adding it to backend/copilot/role_permissions.py — out of scope.)
    required_permission = "documents:read"
    confirmation_level = ConfirmationLevel.SAFE
    supports_undo = False
    deprecated = False
    parameters_schema = ConversationRecallParams

    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        return []

    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        p: ConversationRecallParams = params  # type: ignore[assignment]
        db = ctx.services.get("db")
        if db is None:
            return ToolResult(
                status="unavailable",
                message_key="copilot.error.no_db",
                message_params={"tool": self.name},
            )
        try:
            company_id = ctx.services.get("company_id", 0)
            rows = ConversationSummaryRepository(db).list_by_company(company_id, limit=p.limit)
            rows = rows or []
            return ToolResult(
                status="success",
                data={"conversations": rows, "total": len(rows)},
                message_key="copilot.conversation.recall.success",
                message_params={"total": len(rows)},
            )
        except Exception as exc:
            logger.exception("conversation.recall_recent failed")
            return ToolResult(
                status="failed",
                message_key="copilot.conversation.recall.error",
                message_params={"error": str(exc)},
            )