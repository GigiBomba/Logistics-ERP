"""BaseTool — the single most important interface in the Co-Pilot system.

Every capability the Co-Pilot can ever perform is a subclass of BaseTool.
If it isn't, the AI cannot do it.

Blueprint: §9
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ConfigDict

from backend.copilot.schemas import ConfirmationLevel, SessionContext, ToolResult


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
