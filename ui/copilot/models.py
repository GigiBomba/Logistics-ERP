"""Desktop-side data model mirrors of backend/copilot/schemas.py.

Plain dataclasses so PySide6 widgets can use them without Pydantic dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional


class ConfirmationLevel(IntEnum):
    SAFE = 0
    INFORMATIONAL = 1
    BUSINESS = 2
    DESTRUCTIVE = 3


@dataclass
class Entity:
    type: str = ""
    value: Any = None
    source: str = "extracted"
    confidence: float = 0.0


@dataclass
class Intent:
    name: str = ""
    entities: List[Entity] = field(default_factory=list)
    missing_required_entities: List[str] = field(default_factory=list)
    raw_utterance: str = ""


@dataclass
class ExecutionStep:
    step_id: str = ""
    tool_name: str = ""
    tool_version: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    confirmation_level: ConfirmationLevel = ConfirmationLevel.SAFE
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


@dataclass
class ExecutionPlan:
    plan_id: str = ""
    conversation_id: str = ""
    reasoning_graph_id: str = ""
    intent: Intent = field(default_factory=Intent)
    steps: List[ExecutionStep] = field(default_factory=list)
    overall_confidence: float = 0.0
    requires_confirmation: bool = False
    created_at: Optional[datetime] = None


@dataclass
class ToolResult:
    status: str = ""
    data: Optional[Dict[str, Any]] = None
    message_key: str = ""
    message_params: Dict[str, Any] = field(default_factory=dict)
    undo_token: Optional[str] = None


@dataclass
class Insight:
    """Desktop-side mirror of backend copilot/insight rows.

    Mirrors the response shape returned by ``GET /copilot/insights``.
    ``created_at`` is stored as ISO string from the API; callers can
    parse with ``datetime.fromisoformat()`` when needed.
    """
    id: str = ""
    conversation_id: str = ""
    insight_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    severity: str = "low"
    status: str = "new"
    created_at: Optional[str] = None


@dataclass
class CoPilotResponse:
    conversation_id: str = ""
    reasoning_graph: Optional[dict] = None
    plan: Optional[ExecutionPlan] = None
    clarification_question_key: Optional[str] = None
    clarification_params: Dict[str, Any] = field(default_factory=dict)
    timeline: List[ExecutionStep] = field(default_factory=list)
    summary_key: Optional[str] = None
    summary_params: Dict[str, Any] = field(default_factory=dict)
