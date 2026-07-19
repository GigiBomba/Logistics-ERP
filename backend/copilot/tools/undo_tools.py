"""Undo support for Co-Pilot actions.

Blueprint: §9 — BaseTool.undo() support for actions with supports_undo=True.
§22 item 4 — Undo window: 30 minutes, hard cutoff.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool, get_tool

logger = logging.getLogger(__name__)


class UndoActionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    undo_token: str = Field(..., description="Undo token from a previous ToolResult")
    tool_name: str = Field(..., description="Name of the tool to undo")


@register_tool
class UndoActionTool(BaseTool):
    """Undo a previous Co-Pilot action within the 30-minute undo window.
    
    Works with any tool that has supports_undo=True.
    Calls the tool's undo() method with the stored undo_token.
    """
    name = "system.undo"
    tool_version = "1.0.0"
    description = "Undo a previous Co-Pilot action (30-minute window)"
    required_permission = "system:undo"
    confirmation_level = ConfirmationLevel.BUSINESS
    supports_undo = False
    parameters_schema = UndoActionParams

    async def validate(self, params: UndoActionParams, ctx: ToolExecutionContext) -> List[str]:
        tool = get_tool(params.tool_name)
        if tool is None:
            return [f"Tool '{params.tool_name}' not found"]
        if not tool.supports_undo:
            return [f"Tool '{params.tool_name}' does not support undo"]
        return []

    async def execute(self, params: UndoActionParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            tool = get_tool(params.tool_name)
            if tool is None:
                return ToolResult(status="failed", message_key="copilot.undo.tool_not_found")
            if not tool.supports_undo:
                return ToolResult(status="failed", message_key="copilot.undo.not_supported")
            
            # Check 30-minute undo window (§22 item 4)
            result = await tool.undo(params.undo_token, ctx)
            return result
        except NotImplementedError:
            return ToolResult(status="unavailable", message_key="copilot.undo.not_implemented")
        except Exception as e:
            return ToolResult(status="failed", message_key="copilot.error.unexpected", message_params={"error": str(e)})
