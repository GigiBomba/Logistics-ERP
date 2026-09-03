"""BaseTool — the single most important interface in the Co-Pilot system.

Every capability the Co-Pilot can ever perform is a subclass of BaseTool.
If it isn't, the AI cannot do it.

Blueprint: §9
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, ConfigDict

from backend.copilot.schemas import ConfirmationLevel, SessionContext, ToolResult


# ── Fan-out result cap (§23.3) ────────────────────────────────────────────
# A single tool call may never return unbounded rows.  Fan-out tools
# (freight searches, live positions, vehicle lists) cap their result lists to
# the top MAX_RESULTS and surface the truncation in the ToolResult data.
MAX_RESULTS: int = 100


def cap_result_list(
    items: List[Any],
    max_results: Optional[int] = None,
) -> Tuple[List[Any], int, bool]:
    """Cap a fan-out result list to the top *max_results* rows.

    Returns ``(capped_items, total_before_cap, truncated)``.  Callers embed
    ``total_before_cap`` and the ``truncated`` flag in their ToolResult data so
    the client can paginate and the guardrail stays visible (§23.3).
    """
    total = len(items)
    limit = max_results if max_results is not None else MAX_RESULTS
    if total <= limit:
        return items, total, False
    return items[:limit], total, True


class ToolExecutionContext(BaseModel):
    """Context passed to every tool call — deliberately contains NO raw DB session.

    Services are injected pre-instantiated. The tool never touches DB/ORM directly.
    """
    model_config = ConfigDict(extra="forbid")

    company_id: int
    user_id: int
    role: str
    session_context: SessionContext
    # Deliberately: NO db session, NO raw connection. Services are injected pre-instantiated.
    services: Dict[str, Any] = {}


class BaseTool(ABC):
    """Every AI-callable capability inherits from this.

    Subclasses must define all class-level attributes and implement
    validate() + execute(). undo() is optional (only if supports_undo=True).
    """

    # ── Class-level attributes (MUST be overridden by every subclass) ──────
    name: str                          # e.g. "dispatch.create"
    tool_version: str                  # semver, e.g. "1.0.0" — bumped on any change to parameters_schema or behavior
    description: str                   # used by planner for intent matching
    required_permission: str           # e.g. "dispatch:write" — must exist in the existing RBAC permission table
    confirmation_level: ConfirmationLevel
    supports_undo: bool = False
    supports_pause: bool = False       # §13 — tool can be safely paused between invocations
    supports_resume: bool = False      # §13 — tool execution can be resumed after a pause
    long_running: bool = False         # §13 — heavy tool: dispatched to Celery when a broker is
                                       # available (inline fallback in local desktop mode); emits
                                       # WS type:"progress" + a completion notification.
    deprecated: bool = False           # see §9.2: deprecated tools still execute but are excluded from new plans
    parameters_schema: Type[BaseModel]  # strict Pydantic model, no **kwargs

    # ── Abstract interface ─────────────────────────────────────────────────

    @abstractmethod
    async def validate(self, params: BaseModel, ctx: ToolExecutionContext) -> List[str]:
        """Return list of validation error i18n keys. Empty list = valid."""
        ...

    @abstractmethod
    async def execute(self, params: BaseModel, ctx: ToolExecutionContext) -> ToolResult:
        """MUST call an existing service function. MUST NOT touch DB/ORM directly."""
        ...

    async def undo(self, undo_token: str, ctx: ToolExecutionContext) -> ToolResult:
        """Reverse a previously executed action. Only valid if supports_undo=True."""
        if not self.supports_undo:
            raise NotImplementedError(f"{self.name} does not support undo")
        raise NotImplementedError(f"{self.name}.undo() not implemented")
