"""Core data contracts for the Operion AI Co-Pilot.

These models cross layer boundaries. Defined once here (Pydantic) and mirrored
in ui/copilot/models.py (dataclasses) so both sides serialize/deserialize identically.

Blueprint references: §4 (core contracts), §5.2 (reasoning graph), §8 (context).
"""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum, Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ── §4: Confirmation Levels ───────────────────────────────────────────────

class ConfirmationLevel(IntEnum):
    """Tiered confirmation model — determines whether a tool needs user approval."""
    SAFE = 0            # read-only, executes immediately
    INFORMATIONAL = 1   # creates drafts/reports, executes immediately
    BUSINESS = 2         # changes business data, requires user confirmation
    DESTRUCTIVE = 3      # irreversible/high-impact, always requires confirmation + typed confirmation phrase


# ── §4: Core Execution Models ──────────────────────────────────────────────

class Entity(BaseModel):
    """A single extracted entity — a parameter value the planner resolved from input."""
    type: str                       # e.g. "customer", "vehicle", "date_range", "cargo_weight"
    value: Any
    source: Literal["extracted", "session_context", "user_confirmed"]
    confidence: float = Field(ge=0.0, le=1.0)


class Intent(BaseModel):
    """The planner's interpretation of what the user wants to do."""
    name: str                       # e.g. "dispatch.create", "invoice.generate"
    entities: List[Entity] = []
    missing_required_entities: List[str] = []
    raw_utterance: str


class ExecutionStep(BaseModel):
    """One tool invocation inside an ExecutionPlan."""
    step_id: str
    tool_name: str
    tool_version: str               # stamped at execution time — see §9.2
    parameters: Dict[str, Any]
    depends_on: List[str] = []
    confirmation_level: ConfirmationLevel
    status: Literal["pending", "running", "succeeded", "failed", "skipped", "awaiting_confirmation"]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class ExecutionPlan(BaseModel):
    """A compiled, validated plan ready for execution (or awaiting confirmation)."""
    plan_id: str
    conversation_id: str
    reasoning_graph_id: str          # FK to the ReasoningGraph that produced this plan — never null
    intent: Intent
    steps: List[ExecutionStep]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    requires_confirmation: bool
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ToolResult(BaseModel):
    """Returned by every BaseTool.execute() call."""
    status: Literal["success", "failed", "unavailable", "permission_denied", "needs_confirmation"]
    data: Optional[Dict[str, Any]] = None
    message_key: str                # i18n key, NEVER a raw string — resolved via t() client-side
    message_params: Dict[str, Any] = {}
    undo_token: Optional[str] = None


class CoPilotResponse(BaseModel):
    """The full response model returned by POST /api/v1/copilot/chat."""
    model_config = ConfigDict(extra="ignore")

    conversation_id: str
    reasoning_graph: Optional[dict] = None   # serialized ReasoningGraph, populated once Understand/Plan phases complete
    plan: Optional[ExecutionPlan] = None
    clarification_question_key: Optional[str] = None   # i18n key
    clarification_params: Dict[str, Any] = {}
    timeline: List[ExecutionStep] = []
    summary_key: Optional[str] = None
    summary_params: Dict[str, Any] = {}


# ── §5.2: Reasoning Graph Models ───────────────────────────────────────────

class ReasoningNodeType(str, Enum):
    GOAL = "goal"
    REQUIREMENT = "requirement"       # a slot that must be filled (destination, date, etc.)
    SUB_GOAL = "sub_goal"            # a nested objective requiring tool calls to resolve
    QUERY = "query"                   # a single tool call made to gather information
    COMPARISON = "comparison"         # a derived decision over prior query results — NO tool call
    DECISION = "decision"             # the resolved outcome of a sub_goal or comparison


class ReasoningNode(BaseModel):
    """One node in the ReasoningGraph — a sub-goal, query, comparison, or decision."""
    node_id: str
    type: ReasoningNodeType
    label: str                       # i18n key + params, NOT raw text — e.g. "copilot.reasoning.need_destination"
    label_params: Dict[str, Any] = {}
    status: Literal["unresolved", "resolved", "failed"]
    resolved_value: Optional[Any] = None
    resolved_source: Optional[Literal["extracted", "session_context", "tool_result", "user_confirmed"]] = None
    tool_name: Optional[str] = None       # populated only for QUERY nodes
    tool_version: Optional[str] = None    # stamped alongside tool_name — see §9.2
    tool_result_ref: Optional[str] = None  # populated only for QUERY nodes, points at the ExecutionStep.result once executed
    decision_rationale_key: Optional[str] = None   # i18n key explaining WHY, for DECISION nodes
    decision_rationale_params: Dict[str, Any] = {}
    children: List[str] = []          # node_ids


class ReasoningGraph(BaseModel):
    """A tree of sub-goals, dependencies, and decisions that produces an ExecutionPlan."""
    graph_id: str
    conversation_id: str
    root_node_id: str
    nodes: Dict[str, ReasoningNode]     # node_id -> node
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finalized_at: Optional[datetime] = None   # set once every node reaches resolved/failed


# ── §8: Context Architecture ───────────────────────────────────────────────

# §3.1: Canonical language list — single source of truth for all 22 shipped languages.
# Every module imports this rather than hardcoding its own subset.
SUPPORTED_LANGUAGES = [
    "en", "ro", "de", "fr", "es", "pl", "it", "nl", "pt", "ru", "uk",
    "tr", "hu", "cs", "sk", "sl", "sr", "hr", "bs", "sv", "el", "bg",
]


class GlobalContext(BaseModel):
    """Request-scoped context derived from JWT — read-only, set once per request."""
    company_id: int
    user_id: int
    role: str
    language: str                    # validated against SUPPORTED_LANGUAGES
    timezone: str
    # Canonical DB tiers are 'starter' | 'professional' | 'enterprise'
    # (see the companies CHECK constraints in database/schema.py and
    # schema_pg.sql).  The legacy 'pro' / 'business' values are accepted too
    # so existing callers/tests keep working — the tier gate normalises later.
    subscription_tier: Literal["starter", "pro", "professional", "business", "enterprise"]
    feature_flags: Dict[str, bool] = {}


class SessionContext(BaseModel):
    """Per-session context stored in Redis (TTL 4h, sliding on activity)."""
    current_customer_id: Optional[int] = None
    current_trip_id: Optional[int] = None
    current_driver_id: Optional[int] = None
    current_vehicle_id: Optional[int] = None
    current_module: Optional[str] = None      # e.g. "dispatcher_board", "maintenance_panel"
    expires_at: Optional[datetime] = None


class ConversationContext(BaseModel):
    """Per-conversation context stored in Redis, with model/prompt version pinning."""
    conversation_id: str
    turns: List[dict] = []             # [{role, content_key/content_raw, timestamp}]
    pending_clarification: Optional[str] = None
    last_plan_id: Optional[str] = None
    max_turns: int = 40                 # hard cap; oldest turns pruned, never silently truncate mid-plan
    pinned_provider_id: str             # set on the FIRST turn, never changed mid-conversation
    pinned_model_id: str
    pinned_prompt_version: str          # e.g. a hash or semver of the planner's system prompt at conversation start


class ToolContext(BaseModel):
    """Per-request tool availability — computed server-side from RBAC, never client-cached."""
    available_tools: List[str]          # resolved AFTER permission check, not before
    tool_parameters_schema: Dict[str, dict] = {}


# ── §33: Help Mode Models ───────────────────────────────────────────────────


class GuidedStepType(str, Enum):
    HIGHLIGHT = "highlight"
    DIM = "dim"
    TOOLTIP = "tooltip"
    ARROW = "arrow"
    PULSE = "pulse"
    WAIT_FOR_CLICK = "wait_for_click"
    WAIT_FOR_INPUT = "wait_for_input"
    NAVIGATE = "navigate"
    SHOW_SUCCESS = "show_success"


class GuidedStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str
    type: GuidedStepType
    target_element_id: str | None = None
    tooltip_key: str | None = None
    tooltip_params: dict[str, Any] = {}
    order: int


class GuidedWalkthrough(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_id: str
    title_key: str
    title_params: dict[str, Any] = {}
    steps: list[GuidedStep]
    familiarity_adjusted: bool = False
    doc_corpus_version: str = "1.0.0"


class DocSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    article_id: str
    title_key: str
    url: str
    excerpt: str


class HelpAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_key: str
    answer_params: dict[str, Any] = {}
    sources: list[DocSource]
    doc_corpus_version: str = "1.0.0"


class HelpAnswerParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    active_screen: str | None = None


class GuideWorkflowParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_id: str
