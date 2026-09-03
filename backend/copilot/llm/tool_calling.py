"""LLM-first tool calling — catalog build, JSON tool-call parsing, loop driver (§23.4).

The LLM-first brain: every utterance goes to the LLM together with the app's
RBAC-filtered tool catalog.  The LLM either answers conversationally or emits
tool calls; the app executes them through the EXISTING deterministic machinery
(executor RBAC / audit / confirmation / retry all intact), feeds the results
back, and the LLM synthesizes the final grounded answer.

Channel selection (Gate 1 correction 1): ONE channel per provider call.
  * native ``tools`` when ``provider.supports_tool_calling`` (request.tools);
  * JSON channel otherwise (request.response_format="json" with a strict
    ``{"answer": str|null, "tool_calls": [{name, arguments}]}`` shape parsed
    and validated against the catalog).

Import discipline (§25): this module only imports ``backend.copilot.*`` and
``backend.middleware.input_sanitizer`` — never a vendor SDK.  Imports from
chat.py / planner.py / executor.py are DEFERRED inside functions to avoid a
circular import chain (chat.py imports this module at module load).
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from backend.copilot.llm.base import LLMMessage, LLMRequest, LLMResponse, ToolSpec
from backend.copilot.schemas import (
    ConfirmationLevel,
    ExecutionPlan,
    ExecutionStep,
    Intent,
    ReasoningGraph,
    ReasoningNode,
    ReasoningNodeType,
    ToolContext,
)

logger = logging.getLogger(__name__)

# ── Loop & budget constants (§23.3 guardrails, Gate 1 corrections 2/4) ─────

# Max tool-calling iterations per turn.  Reached → force ONE final synthesis pass.
TOOL_LOOP_MAX_ITERATIONS: int = 5
# Wall-clock budget for the whole turn (~90s).  5 x 30s provider timeouts could
# otherwise hold a sync /chat request for 150s+.  Checked between iterations.
TOOL_LOOP_WALL_CLOCK_BUDGET_S: float = 90.0
# Size budget for the serialized tool catalog sent to the LLM.  The deployment
# model (Ollama gemma3:4b) is now served at a 64k-token context window and the
# budget admits the FULL catalog (~73.6k chars across 81 tools): no truncation
# ever occurs, so every RBAC-permitted tool is LLM-visible and the synthetic
# "help.capabilities" note is never appended.  Worst-case tokens are
# comfortably inside 64k: ~24k catalog + ~10k history (20 x 2000 chars) +
# ~0.5k prompt + 2k output ≈ 36.5k.  The pinned-core mechanism
# (_CORE_CATALOG_TOOLS) stays as a safety net should the registry grow beyond
# the budget; if the catalog ever exceeds it again, tools are dropped in
# stable priority order (core read tools pinned first, then SAFE/INFO, then
# BUSINESS, then DESTRUCTIVE).
CATALOG_MAX_CHARS: int = 80000
# Cap on the structured tool-result envelope fed back to the LLM (context budget).
RESULT_ENVELOPE_MAX_CHARS: int = 2000
# Fallback text when a final synthesis pass produces nothing usable.
_APOLOGY_FALLBACK: str = (
    "I couldn't complete that. The service was unavailable — please try again "
    "in a moment or use the regular app screens."
)

# Confirmation-level ordering used for the catalog's stable priority sort.
_CATALOG_LEVEL_ORDER: Dict[str, int] = {
    "SAFE": 0,
    "INFORMATIONAL": 1,
    "BUSINESS": 2,
    "DESTRUCTIVE": 3,
}

# Core read tools that must ALWAYS survive catalog truncation.  Sorted
# alphabetically within SAFE level, "vehicle.search" (and other 'v'-zone
# tools) would otherwise be dropped when the serialized catalog exceeds
# CATALOG_MAX_CHARS, making basic fleet questions unanswerable by the LLM.
_CORE_CATALOG_TOOLS: frozenset = frozenset({
    "vehicle.search",
    "analytics.query",
    "trip.list",
    "trip.get",
    "driver.check_hours",
    "tracking.get_live_positions",
    "route.list",
    "freight.search_loads",
    "help.answer_question",
    "help.guide_workflow",
    "currency.get_rate",
})


@dataclass
class ToolLoopResult:
    """Outcome of one LLM-first turn (accumulated across loop iterations)."""
    final_answer: Optional[str] = None            # synthesized grounded answer
    pending_plan: Optional[ExecutionPlan] = None  # set when a Level 2+ call needs confirmation
    tool_calls_executed: int = 0                  # per-turn aggregate across iterations
    executed_steps: List[ExecutionStep] = field(default_factory=list)  # executed step outcomes (partial-result responses)
    reasoning_graph: Optional[dict] = None        # DERIVED post-hoc graph (record-only)
    llm_usage: int = 0                            # accumulated LLM tokens across iterations
    provider_failed: bool = False                 # provider errored/returned nothing usable
    attempted: bool = False                       # any provider was usable & attempted


# ── Tool catalog (§23.2, Gate 1 correction 4) ──────────────────────────────

def build_tool_context(permitted_tools: Optional[Any]) -> ToolContext:
    """Build a RBAC-filtered ToolContext from a permitted-tool name set.

    The router already computes the canonical ToolContext via
    ``resolve_available_tools``; this helper reconstructs one from the
    ``permitted_tools`` set handed into ``process_utterance`` (names are
    already permission-filtered and deprecated-excluded there).  When
    ``permitted_tools`` is None, ALL non-deprecated tools are exposed — the
    same "no RBAC restriction" semantics the keyword path applies.
    """
    from backend.copilot.tools.registry import available_tools, get_tool

    if permitted_tools is not None:
        names = sorted(permitted_tools)
    else:
        names = sorted(t.name for t in available_tools() if not t.deprecated)

    schemas: Dict[str, dict] = {}
    for name in names:
        tool = get_tool(name)
        if tool is None:
            continue
        try:
            schemas[name] = tool.parameters_schema.model_json_schema()
        except Exception:
            schemas[name] = {}
    return ToolContext(available_tools=names, tool_parameters_schema=schemas)


def _serialize_catalog(catalog: List[ToolSpec]) -> str:
    """Compact, deterministic serialization used for the size-budget check."""
    return "\n".join(
        json.dumps(spec.model_dump(), sort_keys=True, ensure_ascii=False)
        for spec in catalog
    )


def catalog_to_prompt_text(catalog: List[ToolSpec]) -> str:
    """Render the catalog as prompt text the LLM reads (JSON channel + belt-and-braces)."""
    lines = []
    for spec in catalog:
        schema = (
            json.dumps(spec.parameters_json_schema, sort_keys=True, ensure_ascii=False)
            if spec.parameters_json_schema else "{}"
        )
        lines.append(
            f"- {spec.name} (level={spec.confirmation_level or 'SAFE'}): "
            f"{spec.description} params={schema[:400]}"
        )
    return "\n".join(lines) or "(no tools available)"


def build_tool_catalog(tool_context: ToolContext) -> List[ToolSpec]:
    """Build the LLM-visible tool catalog from a RBAC-filtered ToolContext.

    Each permitted, non-deprecated tool becomes a ToolSpec carrying its name,
    description, parameters JSON schema, and confirmation level (metadata for
    the LLM's pre-announcement only — execution authority stays deterministic).

    Size budget: when the serialized catalog exceeds ``CATALOG_MAX_CHARS``,
    tools are dropped in stable priority order — core read tools first (pinned
    via ``_CORE_CATALOG_TOOLS`` so they always survive), then SAFE/INFORMATIONAL,
    then BUSINESS, then DESTRUCTIVE (sorted by (core, level, name)) — keeping
    the most-used read tools, and a synthetic ``help.capabilities`` note tool is
    appended so the LLM knows the list is truncated.  The note tool is
    non-executable (no registered tool with that name), so a hallucinated call
    to it is rejected by ``validate_tool_call`` like any other unknown tool.
    """
    from backend.copilot.tools.registry import get_tool

    specs: List[ToolSpec] = []
    for name in tool_context.available_tools:
        tool = get_tool(name)
        if tool is None or tool.deprecated:
            continue
        schema = tool_context.tool_parameters_schema.get(name)
        if not schema:
            try:
                schema = tool.parameters_schema.model_json_schema()
            except Exception:
                schema = {}
        specs.append(ToolSpec(
            name=tool.name,
            description=tool.description,
            parameters_json_schema=schema,
            confirmation_level=tool.confirmation_level.name if tool.confirmation_level else "SAFE",
        ))

    # Stable priority: core read tools are PINNED first (so they always survive
    # truncation), then SAFE/INFO, then BUSINESS, then DESTRUCTIVE — each
    # bucket sorted by name for determinism.
    specs.sort(key=lambda s: (
        0 if s.name in _CORE_CATALOG_TOOLS else 1,
        _CATALOG_LEVEL_ORDER.get(s.confirmation_level or "SAFE", 0),
        s.name,
    ))

    if len(_serialize_catalog(specs)) > CATALOG_MAX_CHARS:
        # Core read tools are PINNED first and are never dropped by the size
        # budget: the pinned set alone (~7.8k chars across 11 tools in 2026-08)
        # can exceed CATALOG_MAX_CHARS, so a plain greedy prefix would cut the
        # alphabetical tail (vehicle.search is last of the core set) and leave
        # basic fleet questions unanswerable.  The remaining budget is filled
        # with the highest-priority non-core tools in stable (level, name) order.
        pinned = [s for s in specs if s.name in _CORE_CATALOG_TOOLS]
        rest = [s for s in specs if s.name not in _CORE_CATALOG_TOOLS]
        trimmed: List[ToolSpec] = list(pinned)
        total = len(_serialize_catalog(trimmed))
        for spec in rest:
            size = len(_serialize_catalog([spec]))
            if trimmed and total + size > CATALOG_MAX_CHARS:
                break
            trimmed.append(spec)
            total += size
        specs = trimmed
        specs.append(ToolSpec(
            name="help.capabilities",
            description=(
                "The tool catalog was truncated to fit the model's context budget. "
                "If the user needs a capability NOT listed above, describe what exists "
                "in the app and suggest the matching screen; never invent a tool name."
            ),
            parameters_json_schema={"type": "object", "properties": {}},
            confirmation_level="SAFE",
        ))
        logger.info("LLM tool catalog truncated to %d tools (%d chars budget)", len(specs), CATALOG_MAX_CHARS)

    return specs


# ── Tool-call parsing & validation ─────────────────────────────────────────

_PARSE_ERROR_MESSAGE: str = (
    "Your previous response could not be parsed. Reply with ONLY a valid JSON "
    'object in exactly this shape: {"answer": <string or null>, "tool_calls": '
    '[{"name": "<tool name from the catalog>", "arguments": {<arguments>}}]}. '
    "No markdown fences, no trailing text."
)

# The JSON-channel output-shape instruction appended to the system prompt.  Kept
# as a named constant so the final-synthesis pass can STRIP it (Gate 2 corr. 2) —
# a small model told to "reply with ONLY a single JSON object" will otherwise
# return raw JSON as the visible answer when asked for a plain-text synthesis.
_JSON_OUTPUT_FORMAT_CLAUSE: str = (
    "\n\nOUTPUT FORMAT: reply with ONLY a single JSON object, no markdown: "
    '{"answer": <string|null>, "tool_calls": [{"name": "<catalog tool>", '
    '"arguments": {<parameters>}}]}. Set "tool_calls" to call tools and '
    '"answer" to your final reply (empty list [] when answering directly).'
)


def parse_tool_call_json(text: str) -> Optional[dict]:
    """Parse the strict tool-call JSON shape from a provider's text output.

    Tolerant parsing: strips markdown code fences, finds the FIRST balanced
    ``{...}`` region (handling nested braces and strings), and parses it as
    JSON.  Returns the parsed dict (shape ``{"answer": ..., "tool_calls": [...]}``)
    or ``None`` when no parseable JSON object exists.
    """
    if not text or not text.strip():
        return None
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(cleaned)):
        c = cleaned[i]
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(cleaned[start:i + 1])
                    except (ValueError, TypeError):
                        return None
                    return data if isinstance(data, dict) else None
    return None


def validate_tool_call(call: Any, catalog: List[ToolSpec]) -> Tuple[Optional[Any], Optional[str]]:
    """Validate one tool call against the catalog.

    Returns ``(tool, None)`` on success or ``(None, error)`` where *error* is
    an explicit message for the repair retry.  A tool that is not in the
    catalog is either hallucinated or RBAC-denied → ``"tool X is not available
    to you"`` (the caller logs it and NEVER executes it).  Arguments are
    validated by constructing the tool's Pydantic parameters model (the same
    pattern the executor uses at executor.py:571).
    """
    if not isinstance(call, dict):
        return None, "each tool call must be a JSON object with 'name' and 'arguments'"
    name = call.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "tool call is missing a 'name'"
    if not any(spec.name == name for spec in catalog):
        return None, f"tool '{name}' is not available to you"
    arguments = call.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return None, f"arguments for '{name}' must be a JSON object"

    from backend.copilot.tools.registry import get_tool

    tool = get_tool(name)
    if tool is None or tool.deprecated:
        return None, f"tool '{name}' is not available to you"
    try:
        tool.parameters_schema(**arguments)
    except Exception as exc:
        return None, f"invalid arguments for '{name}': {str(exc)[:300]}"
    return tool, None


# ── Message building & result envelope ─────────────────────────────────────

def _build_tool_loop_messages(
    utterance: str,
    language: str,
    catalog_text: str,
    history: Optional[list] = None,
    json_mode: bool = False,
    context_note: Optional[str] = None,
    help_only: bool = False,
) -> List[LLMMessage]:
    """Sanitize the utterance and build the tool-loop message list.

    Reuses chat.py's history rendering (``_turn_to_text`` / ``MAX_HISTORY_TURNS``)
    so multi-turn context behaves exactly like the free-form chat path.  When
    ``json_mode`` is True (JSON channel), an output-shape instruction is
    appended to the system prompt.  ``context_note`` (sanitized UI/session
    context, §11 parity) is appended to the system prompt as DATA.  When
    ``help_only`` is True (Pro-tier Help Mode, §34.10) the Help Mode system
    prompt is used instead of the general tool-loop prompt.
    """
    # Deferred import: chat.py imports this module at load, so module-level
    # imports from chat.py would create a circular import.
    from backend.copilot.i18n_scope import LANGUAGE_NAMES
    from backend.copilot.llm.chat import (
        HELP_MODE_SYSTEM_PROMPT,
        MAX_HISTORY_TURNS,
        TOOL_LOOP_SYSTEM_PROMPT,
        _turn_to_text,
    )

    sanitized = utterance.strip()
    try:
        from backend.middleware.input_sanitizer import sanitize_free_text
        sanitized = sanitize_free_text(sanitized, max_length=2000)
    except ImportError:  # pragma: no cover — packaged build may skip middleware
        sanitized = sanitized[:2000]

    lang_code = (language or "en").strip().lower()
    lang_name = LANGUAGE_NAMES.get(lang_code, lang_code)
    prompt_template = HELP_MODE_SYSTEM_PROMPT if help_only else TOOL_LOOP_SYSTEM_PROMPT
    system_content = prompt_template.format(
        language_name=lang_name,
        language_code=lang_code,
        catalog=catalog_text,
    )
    if json_mode:
        system_content += _JSON_OUTPUT_FORMAT_CLAUSE
    if context_note:
        system_content += "\n\n" + context_note

    messages: List[LLMMessage] = [LLMMessage(role="system", content=system_content)]
    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        role = turn.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _turn_to_text(turn)
        if not text.strip():
            continue
        messages.append(LLMMessage(role=role, content=text[:2000]))
    messages.append(LLMMessage(role="user", content=sanitized))
    return messages


def _context_note(
    ui_context: Optional[Any],
    session_ctx: Optional[Any],
) -> Optional[str]:
    """Render the sanitized UI/session context as DATA for the LLM (§11 parity).

    The LLM-first path must know what the user has selected on screen ("this
    trip / this truck") exactly like the keyword path's ``_apply_ui_context``
    entity resolution.  Values are sanitized through the standard free-text
    sanitizer (defense-in-depth) and presented as a read-only context line —
    data, never instructions.
    """
    parts: List[str] = []
    if ui_context is not None:
        bits: List[str] = []
        screen = getattr(ui_context, "active_screen", None)
        etype = getattr(ui_context, "selected_entity_type", None)
        eid = getattr(ui_context, "selected_entity_id", None)
        if screen:
            bits.append(f"screen={screen}")
        if etype is not None:
            bits.append(f"selected entity type={etype}")
        if eid is not None:
            bits.append(f"id={eid}")
        if bits:
            parts.append(" ".join(bits))
    if session_ctx is not None:
        sbits: List[str] = []
        for attr, label in (
            ("current_vehicle_id", "current vehicle"),
            ("current_driver_id", "current driver"),
            ("current_trip_id", "current trip"),
            ("current_client_id", "current client"),
            ("current_module", "current module"),
        ):
            val = getattr(session_ctx, attr, None)
            if val is not None:
                sbits.append(f"{label}={val}")
        if sbits:
            parts.append(" ".join(sbits))
    if not parts:
        return None
    try:
        from backend.middleware.input_sanitizer import sanitize_free_text
        parts = [sanitize_free_text(p, max_length=300) for p in parts]
    except ImportError:  # pragma: no cover — packaged build may skip middleware
        parts = [p[:300] for p in parts]
    return "User's current UI context: " + "; ".join(parts) + "."


def _result_envelope(tool_name: str, plan: ExecutionPlan) -> str:
    """Structured tool-result envelope — data reads as data, never instructions.

    Pure JSON per the provider-adapter contract (Gate 2 BLOCK fix): the Google
    adapter's ``_parse_tool_content`` reads ``{"tool_name"/"name", "response"}``
    so the name is recovered and the payload becomes the ``functionResponse``
    body; the OcrAIProvider (JSON channel) reads ``role="tool"`` content as
    text, and the self-describing JSON string keeps the tool name + outcome
    legible there too.

    Shape: ``{"tool_name": <name>, "response": {"status": ..., "data": ..., "error": ...}}``
    """
    step = plan.steps[0] if plan.steps else None
    status = "success"
    data = None
    error = None
    if step is not None:
        status = "success" if step.status == "succeeded" else ("error" if step.status == "failed" else str(step.status))
        if step.result is not None:
            if step.result.get("status") == "success":
                data = step.result.get("data")
            else:
                error = step.result.get("message_key")
        elif step.error:
            error = step.error
    payload = {"status": status, "data": data, "error": error}
    envelope = json.dumps({"tool_name": tool_name, "response": payload}, ensure_ascii=False, default=str)
    if len(envelope) > RESULT_ENVELOPE_MAX_CHARS:
        payload["data"] = "(truncated)"
        envelope = json.dumps({"tool_name": tool_name, "response": payload}, ensure_ascii=False, default=str)
    return envelope


# ── Execution plan construction ────────────────────────────────────────────

def _build_call_plan(
    call: dict,
    tool: Any,
    conversation_id: str,
    global_ctx: Any,
    utterance: str,
) -> ExecutionPlan:
    """Compile a single-step ExecutionPlan for one validated tool call.

    Reuses the ExecutionStep/ExecutionPlan shapes the rest of the pipeline
    consumes (the router persists ``requires_confirmation`` plans), so RBAC /
    audit / confirmation / retry machinery stays intact.
    """
    intent = Intent(
        name=tool.name,
        entities=[],
        missing_required_entities=[],
        raw_utterance=utterance,
    )
    step = ExecutionStep(
        step_id=f"{tool.name}-{uuid.uuid4().hex[:8]}",
        tool_name=tool.name,
        tool_version=tool.tool_version,
        parameters=dict(call.get("arguments") or {}),
        depends_on=[],
        confirmation_level=tool.confirmation_level,
        status="pending",
    )
    return ExecutionPlan(
        plan_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        reasoning_graph_id=str(uuid.uuid4()),
        intent=intent,
        steps=[step],
        overall_confidence=0.8,
        requires_confirmation=(tool.confirmation_level >= ConfirmationLevel.BUSINESS),
    )


# ── Derived reasoning graph (Gate 1 decision (a)) ──────────────────────────

def derive_reasoning_graph(
    tool_calls: List[dict],
    final_answer: Optional[str],
    conversation_id: str = "",
) -> dict:
    """Derive a POST-HOC reasoning graph from the executed tool calls + answer.

    QUERY node per tool call, REQUIREMENT nodes from its arguments, and a
    DECISION node for the final answer with a short rationale.  Record-only —
    no gating, no extra LLM pass.  Mirrors the ReasoningGraph node shapes from
    ``build_reasoning_graph`` (backend/copilot/reasoning.py) so the existing
    persistence + response contract keeps working.
    """
    root_id = "goal-llm-turn"
    nodes: Dict[str, ReasoningNode] = {
        root_id: ReasoningNode(
            node_id=root_id,
            type=ReasoningNodeType.GOAL,
            label="copilot.intent.llm_turn",
            status="resolved",
            children=[],
        ),
    }
    for i, call in enumerate(tool_calls):
        name = str(call.get("name") or "tool")
        args = call.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        query_id = f"query-{i}"
        nodes[query_id] = ReasoningNode(
            node_id=query_id,
            type=ReasoningNodeType.QUERY,
            label="copilot.reasoning.tool_call",
            label_params={"tool": name},
            status="failed" if call.get("denied") else "resolved",
            tool_name=name,
            tool_result_ref=f"step-{name}-{i}",
            resolved_source="tool_result",
            children=[],
        )
        nodes[root_id].children.append(query_id)
        for key, value in args.items():
            req_id = f"req-{i}-{key}"
            nodes[req_id] = ReasoningNode(
                node_id=req_id,
                type=ReasoningNodeType.REQUIREMENT,
                label=f"copilot.reasoning.have_{key}",
                status="resolved",
                resolved_value=value,
                children=[],
            )
            nodes[query_id].children.append(req_id)
    if final_answer:
        decision_id = "decision-final"
        nodes[decision_id] = ReasoningNode(
            node_id=decision_id,
            type=ReasoningNodeType.DECISION,
            label="copilot.reasoning.llm_answer",
            status="resolved",
            resolved_value=final_answer[:500],
            decision_rationale_key="copilot.reasoning.grounded_in_tool_results",
            children=[],
        )
        nodes[root_id].children.append(decision_id)

    graph = ReasoningGraph(
        graph_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        root_node_id=root_id,
        nodes=nodes,
        finalized_at=None,
    )
    return graph.model_dump(mode="json")


# ── Loop driver ────────────────────────────────────────────────────────────

async def run_tool_loop(
    utterance: str,
    language: str,
    history: Optional[list],
    global_ctx: Any,
    services: Optional[dict],
    catalog: List[ToolSpec],
    provider: Any,
    conversation_id: str,
    permitted_tools: Optional[Any] = None,
    on_step_update: Optional[Any] = None,
    ui_context: Optional[Any] = None,
    session_ctx: Optional[Any] = None,
    help_only: bool = False,
) -> ToolLoopResult:
    """Drive the LLM-first tool-calling turn.

    Loop rules (Gate 1 corrections 2/3/4 + Gate 2 corrections):
      * max ``TOOL_LOOP_MAX_ITERATIONS`` (5) + ``TOOL_LOOP_WALL_CLOCK_BUDGET_S``
        (~90s) wall clock, checked between iterations.
      * ONE channel per provider call: native ``tools`` when
        ``provider.supports_tool_calling``, else the JSON channel.
      * Stop conditions: no tool calls + answer → final answer; N reached →
        one forced final synthesis pass; parse/validation failure → ONE repair
        retry with the explicit error, then a final pass explaining the failure
        (the final pass neutralizes the JSON OUTPUT FORMAT clause — Gate 2
        corr. 2 — and injected corrections are user-role — Gate 2 corr. 4).
      * Level ≤1 calls execute in-loop via ``executor.execute_plan`` (RBAC /
        audit / retry / on_step_update intact); the FIRST Level 2+ call
        compiles a plan with ``requires_confirmation=True`` and ENDS the turn —
        unless ``_is_autonomous_approved`` allows executing it immediately.
      * Permission-denied / hallucinated tools are NEVER executed: logged via
        logger.warning, repair-retried, then an apologetic final answer.
      * Guardrail accounting accumulates tool calls + LLM tokens ACROSS
        iterations (MAX_TOOL_CALLS_PER_PLAN / MAX_LLM_TOKENS_PER_TURN).
      * Tool results feed back as ``role="tool"`` messages with the originating
        call's id forwarded in ``tool_call_id`` (native-channel Gemini
        functionResponse pairing — Gate 2 corr. 1).
      * Sanitized UI/session context is injected into the system prompt as DATA
        (§11 parity — Gate 2 corr. 3).
    """
    from backend.copilot.executor import (
        MAX_LLM_TOKENS_PER_TURN,
        MAX_TOOL_CALLS_PER_PLAN,
        execute_plan,
        execute_with_fallback,
    )
    from backend.copilot.llm.chat import (
        LLM_CHAT_MAX_TOKENS,
        LLM_CHAT_TIMEOUT_S,
        MAX_ANSWER_CHARS,
    )
    from backend.copilot.planner import _is_autonomous_approved

    native_channel = bool(getattr(provider, "supports_tool_calling", False))
    catalog_text = catalog_to_prompt_text(catalog)
    context_note = _context_note(ui_context, session_ctx)
    messages = _build_tool_loop_messages(
        utterance, language, catalog_text, history,
        json_mode=not native_channel, context_note=context_note, help_only=help_only,
    )

    result = ToolLoopResult()
    tool_calls_so_far = 0
    llm_tokens_so_far = 0
    executed_calls: List[dict] = []  # for the derived reasoning graph
    repair_used = False
    repair_error: Optional[str] = None
    wall_start = time.monotonic()

    async def _generate(override_messages: Optional[List[LLMMessage]] = None, allow_tools: bool = True) -> LLMResponse:
        msgs = list(override_messages if override_messages is not None else messages)
        request = LLMRequest(messages=msgs, max_tokens=LLM_CHAT_MAX_TOKENS, temperature=0.2)
        if native_channel and allow_tools:
            request.tools = catalog
        elif not native_channel and allow_tools:
            request.response_format = "json"
        # Final synthesis passes (allow_tools=False) request plain text so the
        # model answers conversationally instead of emitting the JSON envelope.
        return await execute_with_fallback(
            provider.generate(request),
            fallback_response=LLMResponse(content="", finish_reason="error"),
            timeout_seconds=LLM_CHAT_TIMEOUT_S,
        )

    async def _final_synthesis(reason: str) -> Optional[str]:
        """One last generation asking for a plain-text answer (no tools).

        Neutralizes the JSON OUTPUT FORMAT clause baked into the system prompt
        (Gate 2 corr. 2) — a small model told to reply with "ONLY a single JSON
        object" will otherwise return raw JSON as the visible answer.  The
        corrective override is a ``role="user"`` message (Gate 2 corr. 4):
        OpenAI-compat backends 400 on non-leading system messages.
        """
        msgs: List[LLMMessage] = []
        for m in messages:
            if m.role == "system":
                msgs.append(LLMMessage(
                    role="system",
                    content=m.content.replace(_JSON_OUTPUT_FORMAT_CLAUSE, ""),
                ))
            else:
                msgs.append(m)
        msgs.append(LLMMessage(
            role="user",
            content=(
                "IGNORE the earlier JSON output-format instruction — answer in "
                f"plain text now. {reason}"
            ),
        ))
        resp = await _generate(override_messages=msgs, allow_tools=False)
        if getattr(resp, "finish_reason", "error") == "error":
            return None
        content = (getattr(resp, "content", "") or "").strip()
        return content[:MAX_ANSWER_CHARS] if content else None

    async def _set_final_answer(answer: Optional[str]) -> None:
        result.final_answer = answer or _APOLOGY_FALLBACK

    for iteration in range(TOOL_LOOP_MAX_ITERATIONS):
        if result.final_answer is not None or result.pending_plan is not None:
            break
        # Wall-clock budget, checked between iterations.
        if iteration > 0 and (time.monotonic() - wall_start) > TOOL_LOOP_WALL_CLOCK_BUDGET_S:
            await _set_final_answer(await _final_synthesis(
                "The tool-calling budget for this turn was exhausted. Answer the user "
                "now in plain text; do not call any more tools."
            ))
            break

        # Inject a pending repair error (one per failure) before the next call.
        # Corrections are user-role — OpenAI-compat backends reject non-leading
        # system messages (Gate 2 corr. 4).
        if repair_error is not None:
            messages.append(LLMMessage(role="user", content=repair_error))
            repair_error = None

        resp = await _generate()
        llm_tokens_so_far += int(getattr(resp, "input_tokens", 0) or 0)
        llm_tokens_so_far += int(getattr(resp, "output_tokens", 0) or 0)

        if getattr(resp, "finish_reason", "error") == "error":
            result.provider_failed = True
            return result

        content = (getattr(resp, "content", "") or "").strip()

        if native_channel:
            tool_calls = list(getattr(resp, "tool_calls", []) or [])
            answer = content
        else:
            parsed = parse_tool_call_json(content)
            if parsed is None:
                if not repair_used:
                    repair_used = True
                    repair_error = _PARSE_ERROR_MESSAGE
                    continue
                await _set_final_answer(await _final_synthesis(
                    "Your previous message could not be parsed as a tool call. "
                    "Answer the user directly in plain text now; do not call tools."
                ))
                break
            answer = parsed.get("answer")
            tool_calls = parsed.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                tool_calls = []

        if not tool_calls:
            if answer and str(answer).strip():
                result.final_answer = str(answer).strip()[:MAX_ANSWER_CHARS]
                break
            if not repair_used:
                repair_used = True
                repair_error = "Your response contained neither an answer nor tool calls. " + _PARSE_ERROR_MESSAGE
                continue
            result.provider_failed = True
            return result

        # ── Process this batch of tool calls ───────────────────────────────
        batch_failed = False
        for call in tool_calls:
            tool, err = validate_tool_call(call, catalog)
            if err is not None:
                logger.warning(
                    "LLM tool call denied (NOT executed): tool=%s error=%s company=%d user=%d",
                    call.get("name") if isinstance(call, dict) else "?", err,
                    getattr(global_ctx, "company_id", 0),
                    getattr(global_ctx, "user_id", 0),
                )
                executed_calls.append({
                    "name": call.get("name") if isinstance(call, dict) else "?",
                    "arguments": call.get("arguments") if isinstance(call, dict) else {},
                    "denied": True,
                })
                if not repair_used:
                    repair_used = True
                    repair_error = f"ERROR: {err}. Fix your tool call and try again, or answer directly without tools."
                else:
                    await _set_final_answer(await _final_synthesis(
                        f"The tool you requested is not available: {err}. "
                        "Explain this to the user in plain text and do not call tools."
                    ))
                batch_failed = True
                break

            # Per-turn aggregate guardrail: tool-call cap.
            if tool_calls_so_far + 1 > MAX_TOOL_CALLS_PER_PLAN:
                await _set_final_answer(await _final_synthesis(
                    "The maximum number of tool calls for this turn was reached. "
                    "Summarize what was done and answer the user in plain text."
                ))
                break

            plan = _build_call_plan(call, tool, conversation_id, global_ctx, utterance)

            # ── Confirmation gate for Level 2+ (§23.1 / §21 Ph.4) ──────
            if tool.confirmation_level >= ConfirmationLevel.BUSINESS:
                autonomous = await _is_autonomous_approved(plan, global_ctx, services)
                if not autonomous:
                    # Turn ends immediately — no further iterations, no synthesis.
                    # After /confirm the deterministic summary shows (Phase 2 deviation).
                    result.pending_plan = plan
                    result.llm_usage = llm_tokens_so_far
                    result.tool_calls_executed = tool_calls_so_far
                    result.reasoning_graph = derive_reasoning_graph(executed_calls, None, conversation_id)
                    return result
                plan.requires_confirmation = False
                logger.info(
                    "Autonomous mode: LLM-requested %s executed without confirmation "
                    "(company=%d user=%d)",
                    tool.name, global_ctx.company_id, global_ctx.user_id,
                )

            plan = await execute_plan(plan, services=services, on_step_update=on_step_update)

            executed_calls.append({
                "name": tool.name,
                "arguments": dict(call.get("arguments") or {}),
            })
            tool_calls_so_far += 1
            result.tool_calls_executed = tool_calls_so_far
            result.executed_steps.append(plan.steps[0])
            llm_tokens_so_far += int(getattr(plan, "used_llm_tokens", 0) or 0)
            # Forward the originating call id so the provider pairs the result
            # with the correct function_call (Gemini functionResponse.id).
            messages.append(LLMMessage(
                role="tool",
                content=_result_envelope(tool.name, plan),
                tool_call_id=call.get("id") if isinstance(call, dict) else None,
            ))

        if batch_failed:
            continue
        if result.final_answer is not None:
            break
        if llm_tokens_so_far >= MAX_LLM_TOKENS_PER_TURN:
            await _set_final_answer(await _final_synthesis(
                "The token budget for this turn was reached. Answer the user now in plain text."
            ))
            break
        # Loop continues: the LLM may call more tools or synthesize.

    # N reached without an answer / plan → force one final synthesis pass.
    if result.final_answer is None and result.pending_plan is None and not result.provider_failed:
        await _set_final_answer(await _final_synthesis(
            "You have reached the maximum number of tool-calling iterations. "
            "Answer the user in plain text now, summarizing what was accomplished; do not call more tools."
        ))

    result.llm_usage = llm_tokens_so_far
    result.reasoning_graph = derive_reasoning_graph(executed_calls, result.final_answer, conversation_id)
    return result