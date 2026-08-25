"""AI Planner — intent detection, entity extraction, and plan compilation.

Blueprint: §7 pipeline placement.

Phase 1: Keyword-based intent extraction (no LLM dependency).
Extracts intent name, entities, and builds a reasoning graph → execution plan.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.copilot.confidence import compute_confidence
from backend.copilot.human_handoff import HandoffTracker, should_handoff
from backend.copilot.reasoning import build_reasoning_graph, resolve_reasoning_graph
from backend.copilot.schemas import (
    CoPilotResponse,
    ConfirmationLevel,
    Entity,
    ExecutionPlan,
    ExecutionStep,
    GlobalContext,
    Intent,
    SessionContext,
    ToolResult,
)
from backend.copilot.tools.registry import available_tools, get_tool

logger = logging.getLogger(__name__)

# i18n key surfaced when an intent's tool is not in the caller's permitted
# tool set (§15 — permission system).  The client resolves it via ``t()``
# exactly like every other ``copilot.*`` message key.
PERMISSION_DENIED_KEY = "copilot.error.permission_denied"

# ── Tool auto-loading ───────────────────────────────────────────────────────

def _ensure_tools_loaded() -> None:
    """Import all tool modules to trigger @register_tool decorators."""
    try:
        import backend.copilot.tools.vehicle_tools       # noqa: F401
        import backend.copilot.tools.driver_tools        # noqa: F401
        import backend.copilot.tools.route_tools         # noqa: F401
        import backend.copilot.tools.trip_tools          # noqa: F401
        import backend.copilot.tools.client_tools        # noqa: F401
        import backend.copilot.tools.document_tools      # noqa: F401
        import backend.copilot.tools.currency_tools      # noqa: F401
        import backend.copilot.tools.tracking_tools      # noqa: F401
        import backend.copilot.tools.analytics_tools     # noqa: F401
        import backend.copilot.tools.freight_tools      # noqa: F401
        import backend.copilot.tools.help_tools         # noqa: F401
    except ImportError:
        pass  # Tools not yet implemented


def _ensure_llm_providers_loaded() -> None:
    """Import all LLM provider modules to trigger @register_llm_provider decorators.

    Must be called before any LLM routing decision so that the provider
    registry is populated and routing validation can pass.

    Same pattern as _ensure_tools_loaded() — each provider module
    self-registers at import time via its decorator.
    """
    try:
        import backend.copilot.llm.providers.google_provider   # noqa: F401
        import backend.copilot.llm.providers.ocr_ai_provider   # noqa: F401
    except ImportError:
        pass  # Providers not yet available

# ── Phase 1: Keyword-based intent mapping ───────────────────────────────────
# Maps user query patterns to (intent_name, entity_mappings)

# Each pattern: (keyword_hints, intent_name, entity_types)
# Matching uses partial word overlap — stronger than substring, weaker than phrase match.
# Split each keyword on spaces and check all words appear somewhere in utterance.

_STOPWORDS = frozenset({
    "a", "an", "as", "at", "be", "by", "do", "for", "he", "i", "in",
    "is", "it", "me", "of", "on", "or", "this", "to", "up", "we",
})


def _match_score(keyword_hints: str, utterance: str) -> int:
    """Score a keyword hint against the utterance.

    Uses word-boundary prefix matching (``\\bword\\w*``) so that:
    - ``how`` does **not** match inside ``show`` (word boundary at start)
    - ``document`` matches ``documents`` (prefix + trailing word chars)
    - ``profit`` matches ``profitability`` (stem extension)

    Common stopwords (``me``, ``do``, ``i``, ``to``, ``for`` …) are filtered
    out so they cannot inflate scores for unrelated intents.

    Full matches (all significant words present) score **double** to
    prioritise precise phrase hits over scattered partial overlaps.
    """
    significant = [w for w in keyword_hints.split() if w not in _STOPWORDS]
    if not significant:
        return 0
    matches = sum(
        1 for w in significant
        if re.search(r"\b" + re.escape(w) + r"\w*", utterance)
    )
    if matches == 0:
        return 0
    return matches * 2 if matches == len(significant) else matches


INTENT_PATTERNS: List[tuple] = [
    # (keyword_hints_list, intent_name, entity_types)

    # -- Vehicle --
    (["search vehicles", "find vehicles", "available trucks", "find truck", "look up vehicle",
      "list trucks", "show trucks", "which vehicles", "show all vehicles", "list all trucks"],
     "vehicle.search", [("query", "vehicle")]),

    (["vehicle health", "truck health", "health score", "vehicle score", "truck score",
      "check vehicle", "vehicle condition", "truck condition", "fleet health"],
     "vehicle.health_score", [("vehicle_id", "vehicle")]),

    # -- Driver --
    (["driver hours", "check driver", "hours left", "driver available",
      "remaining hours", "how many hours", "driver schedule", "driver time"],
     "driver.check_hours", [("driver_id", "driver")]),

    # -- Route --
    (["calculate route", "plan route", "route distance", "how far", "distance between",
      "route from", "route to", "compute route", "get directions", "navigate to"],
     "route.calculate", [("stops", "route")]),

    (["cost estimate", "estimate cost", "fuel cost", "toll cost",
      "how much cost", "cost of route", "cost for trip", "expense estimate",
      "calculate cost", "trip cost", "route cost"],
     "route.estimate_cost", [("distance_km", "distance")]),

    (["multi stop", "multiple stops", "optimize route", "plan stops",
      "best route", "plan delivery", "delivery route", "tour plan",
      "multi destination", "several stops"],
     "route.plan_multistop", [("stops", "route")]),

    # -- Trip --
    (["profit", "profitability", "trip profit", "calculate profit", "margin",
      "how profitable", "trip margin", "revenue estimate", "earnings estimate",
      "calculate earnings", "how much money"],
     "trip.calculate_profitability", [("km", "distance")]),

    # -- Client --
    (["client payment", "payment summary", "client owes", "client balance",
      "how much client", "client billed", "client invoice", "client debt",
      "outstanding balance", "unpaid invoices"],
     "client.payment_summary", [("client_id", "client")]),

    # -- Document --
    (["search document", "find document", "document for", "look up document",
      "find paperwork", "find file", "search file", "locate document",
      "look up paperwork"],
     "document.search", [("query", "document")]),

    # -- Currency --
    (["exchange rate", "currency rate", "what is rate",
      "get rate", "show rate", "current rate", "fx rate"],
     "currency.get_rate", [("code", "currency")]),

    (["convert currency", "convert money", "convert to", "change currency",
      "currency conversion", "exchange to", "how much in"],
     "currency.convert", [("amount", "currency"), ("from_currency", "from_currency"), ("to_currency", "to_currency")]),

    # -- Tracking --
    (["track vehicle", "live position", "where is", "vehicle location", "gps position",
      "find location", "track fleet", "vehicle tracking",
      "where are", "current location", "show position", "locate vehicle"],
     "tracking.get_live_positions", []),

    (["vehicle history", "track history", "position history", "route history",
      "past locations", "where was", "previous route", "truck route history",
      "vehicle location history", "tracking history"],
     "tracking.get_vehicle_history", [("vehicle_id", "vehicle")]),

    # -- Analytics --
    (["analytics", "report", "statistics", "summary", "overview", "dashboard",
      "financial overview", "fleet analytics", "driver stats", "business report",
      "company overview", "performance report", "fleet report", "financial report",
      "revenue report", "profit report", "fleet summary"],
     "analytics.query", [("domain", "analytics")]),

    # -- Help / Documentation --
    (["how do i", "what is", "what does", "how does", "where is", "where do i",
      "explain", "help with", "show me how", "what's a", "whats a",
      "tell me about", "i don't understand", "can you explain",
      "what does this", "how does this", "what's this", "what is this"],
     "help.answer_question", []),

    (["walk me through", "guide me", "show me the steps", "tutorial",
      "how to", "teach me", "step by step", "navigate to",
      "take me to", "show me how to"],
     "help.guide_workflow", []),
]


async def extract_intent(utterance: str) -> Intent:
    """Extract intent from user utterance using keyword matching (Phase 1).

    Phase 2+ will use LLMProvider for NLP-based extraction.
    """
    utterance_lower = utterance.lower()

    best_match: Optional[tuple] = None
    best_score = 0

    for keywords, intent_name, entity_mappings in INTENT_PATTERNS:
        score = 0
        seen_sigs: set[tuple[str, ...]] = set()
        for kw in keywords:
            sig = tuple(sorted(w for w in kw.split() if w not in _STOPWORDS))
            if not sig or sig in seen_sigs:
                continue
            seen_sigs.add(sig)
            score += _match_score(kw, utterance_lower)
        if score > best_score:
            best_score = score
            best_match = (keywords, intent_name, entity_mappings)

    # Phase 1: require at least 2 total match points to avoid
    # false-positive matches from single common words (e.g. "is", "in").
    MIN_MATCH_THRESHOLD = 2
    if best_match and best_score >= MIN_MATCH_THRESHOLD:
        _, intent_name, entity_mappings = best_match
        entities: List[Entity] = []
        missing: List[str] = []

        for entity_type, _ in entity_mappings:
            # Try to extract numbers/IDs from the utterance
            import re
            # Extract vehicle IDs, driver IDs, client IDs, etc.
            numbers = re.findall(r'\b(\d+)\b', utterance)
            if numbers and entity_type in ("vehicle_id", "driver_id", "client_id", "distance_km"):
                entities.append(Entity(
                    type=entity_type,
                    value=int(numbers[0]) if entity_type.endswith("_id") else float(numbers[0]),
                    source="extracted",
                    confidence=0.7,
                ))
            else:
                missing.append(entity_type)

        # For entity-less intents (tracking), all good
        return Intent(
            name=intent_name,
            entities=entities,
            missing_required_entities=missing,
            raw_utterance=utterance,
        )

    # No match found
    return Intent(
        name="unknown",
        entities=[],
        missing_required_entities=["intent"],
        raw_utterance=utterance,
    )


async def process_utterance(
    utterance: str,
    global_ctx: GlobalContext,
    conversation_id: str,
    session_ctx: Optional[SessionContext] = None,
    services: Optional[Dict[str, Any]] = None,
    permitted_tools: Optional[List[str]] = None,
) -> CoPilotResponse:
    """Process a user utterance through the full Co-Pilot pipeline.

    Pipeline: Understand → Build ReasoningGraph → Resolve → Compile ExecutionPlan
              → Execute (Level 0 only) → Summarize

    ``permitted_tools`` is the server-side RBAC-resolved set of tool names the
    caller may use (see ``backend/copilot/context.py:resolve_available_tools``).
    When provided, any intent whose tool is outside this set is rejected with a
    clear denial BEFORE a plan is compiled — the tool is never executed.
    """
    # ── Graceful degradation (§23.5) — LLM provider calls should use
    # executor.execute_with_fallback() with a sensible timeout and a
    # fallback CoPilotResponse asking the user to try again or use
    # the normal UI. This is wired here as infrastructure; Phase 6+
    # will use it when LLM-based intent extraction is enabled.

    # Normalise the permitted set once — callers may pass a list or a set.
    permitted_set: Optional[set] = set(permitted_tools) if permitted_tools is not None else None

    # ── 0. Ensure all tool modules are loaded ───────────────────────────
    _ensure_tools_loaded()

    try:
        # ── 0b. Ensure LLM providers are loaded ────────────────────────────
        _ensure_llm_providers_loaded()

        # ── 1. Understand: Extract intent ───────────────────────────────────
        intent = await extract_intent(utterance)

        # Detect unknown intents
        if intent.name == "unknown":
            return CoPilotResponse(
                conversation_id=conversation_id,
                clarification_question_key="copilot.clarification.unknown_intent",
                clarification_params={"utterance": utterance[:200]},
            )

        # Check if the tool exists in the registry (not deprecated, available)
        tool = get_tool(intent.name)
        if tool is None or tool.deprecated:
            return CoPilotResponse(
                conversation_id=conversation_id,
                clarification_question_key="copilot.clarification.tool_unavailable",
                clarification_params={"intent": intent.name},
            )

        # ── 1b. RBAC permission gate (§15) ─────────────────────────────────
        # ``get_tool`` is a registry lookup, NOT an authorization check.  The
        # permitted set was resolved server-side from the caller's JWT role
        # before this request entered the pipeline (copilot_router →
        # resolve_available_tools).  An intent whose tool is missing from that
        # set must never be compiled or executed.
        if permitted_set is not None and intent.name not in permitted_set:
            logger.warning(
                "RBAC denied tool '%s' for role '%s' user=%s company=%s",
                intent.name, global_ctx.role, global_ctx.user_id, global_ctx.company_id,
            )
            return CoPilotResponse(
                conversation_id=conversation_id,
                clarification_question_key=PERMISSION_DENIED_KEY,
                clarification_params={
                    "intent": intent.name,
                    "role": global_ctx.role,
                },
            )

        # ── 2. Confidence check ─────────────────────────────────────────────
        confidence = compute_confidence(intent, intent_match_score=0.8)
        from backend.copilot.confidence import needs_clarification, needs_recap

        if needs_clarification(confidence):
            return CoPilotResponse(
                conversation_id=conversation_id,
                clarification_question_key="copilot.clarification.low_confidence",
                clarification_params={"utterance": utterance[:200]},
            )

        # ── 2b. De-escalation check (§23.7) ────────────────────────────────
        handoff = HandoffTracker.get(conversation_id)
        if handoff and should_handoff(handoff, intent.name):
            logger.info("Handing off conversation %s to manual UI (de-escalation triggered)", conversation_id)
            return CoPilotResponse(
                conversation_id=conversation_id,
                clarification_question_key="copilot.handoff.message",
                clarification_params={
                    "intent": intent.name,
                    "reason": handoff.reason,
                },
            )

        # ── 3. Build Reasoning Graph ────────────────────────────────────────
        from backend.copilot.telemetry import set_phase
        set_phase("REASONING")
        graph = await build_reasoning_graph(conversation_id, intent)

        # ── 4. Resolve graph ─────────────────────────────────────────────────
        graph = await resolve_reasoning_graph(
            graph,
            company_id=global_ctx.company_id,
            user_id=global_ctx.user_id,
            role=global_ctx.role,
            session_context=session_ctx,
            services=services,
        )

        # ── 5. Check if all requirements are resolved ───────────────────────
        unresolved = [
            node for node in graph.nodes.values()
            if node.status == "unresolved"
        ]
        if unresolved:
            missing_names = [node.label for node in unresolved]
            return CoPilotResponse(
                conversation_id=conversation_id,
                reasoning_graph=graph.model_dump(mode="json"),
                clarification_question_key="copilot.clarification.missing_entities",
                clarification_params={
                    "intent": intent.name,
                    "missing": missing_names,
                    "example": _build_clarification_example(intent),
                },
            )

        # ── 6. Compile ExecutionPlan (Level 0 only) ─────────────────────────
        plan = await compile_execution_plan(
            conversation_id=conversation_id,
            reasoning_graph_id=graph.graph_id,
            intent=intent,
            global_ctx=global_ctx,
            session_ctx=session_ctx,
            services=services,
            permitted_tools=permitted_set,
        )

        if plan is None:
            return CoPilotResponse(
                conversation_id=conversation_id,
                reasoning_graph=graph.model_dump(mode="json"),
                clarification_question_key="copilot.clarification.cannot_compile",
            )

        # ── 7. Check if any step needs confirmation ─────────────────────────
        needs_confirmation = any(s.confirmation_level >= ConfirmationLevel.BUSINESS for s in plan.steps)

        if needs_confirmation:
            logger.info("Plan %s requires user confirmation (%d steps)", plan.plan_id, len(plan.steps))
        else:
            # ── 7. Execute ─────────────────────────────────────────
            from backend.copilot.telemetry import set_phase
            set_phase("EXECUTING")
            from backend.copilot.executor import execute_plan as do_execute
            plan = await do_execute(plan, services=services)

        # ── 8. Build response ───────────────────────────────────────────────
        summary_parts = []
        for step in plan.steps:
            if step.status == "succeeded" and step.result:
                summary_parts.append(step.result.get("message_key", ""))
            elif step.status == "failed":
                summary_parts.append(step.error or "Failed")

        summary_key = f"copilot.summary.{intent.name}"
        summary_params = {
            "intent": intent.name,
            "steps_total": len(plan.steps),
            "steps_succeeded": sum(1 for s in plan.steps if s.status == "succeeded"),
        }

        for step in plan.steps:
            if step.status == "succeeded" and step.result:
                result_data = step.result.get("data", {})
                if isinstance(result_data, dict):
                    for k, v in result_data.items():
                        if isinstance(v, (str, int, float, bool)):
                            summary_params[k] = v

        return CoPilotResponse(
            conversation_id=conversation_id,
            reasoning_graph=graph.model_dump(mode="json"),
            plan=plan,
            timeline=plan.steps,
            summary_key=summary_key,
            summary_params=summary_params,
        )
    except Exception as exc:
        logger.exception("process_utterance failed: %s", exc)
        return CoPilotResponse(
            conversation_id=conversation_id,
            clarification_question_key="copilot.error.internal",
            clarification_params={"error": str(exc)},
        )


async def compile_execution_plan(
    conversation_id: str,
    reasoning_graph_id: str,
    intent: Intent,
    global_ctx: GlobalContext,
    session_ctx: Optional[SessionContext] = None,
    services: Optional[Dict[str, Any]] = None,
    permitted_tools: Optional[set] = None,
) -> Optional[ExecutionPlan]:
    """Compile an ExecutionPlan from a resolved ReasoningGraph and Intent.

    Phase 1: Creates a single-step ExecutionPlan for the resolved intent.
    Each entity becomes a parameter in the tool call.

    Defense-in-depth RBAC: when ``permitted_tools`` is provided and
    ``intent.name`` is not in it, NO step is created and ``None`` is
    returned (the caller surfaces a denial).  The authoritative check also
    runs earlier in :func:`process_utterance`; this guards any direct callers.
    """
    tool = get_tool(intent.name)
    if tool is None:
        return None

    if permitted_tools is not None and intent.name not in permitted_tools:
        logger.warning(
            "compile_execution_plan: RBAC denied tool '%s' for role '%s'",
            intent.name, global_ctx.role,
        )
        return None

    # Build parameters from entities
    params = {}
    for entity in intent.entities:
        params[entity.type] = entity.value

    # Seed free-text params (e.g. ``question`` on help.answer_question) from
    # the raw utterance.  Entity-less text intents otherwise reach execution
    # with an empty ``parameters`` dict and fail pydantic validation, dumping
    # a raw validation error into the UI instead of answering.
    model_fields = getattr(tool.parameters_schema, "model_fields", {})
    if "question" in model_fields and "question" not in params:
        params["question"] = intent.raw_utterance

    # For Phase 1: single-step plan
    step = ExecutionStep(
        step_id=f"{intent.name}-0",
        tool_name=intent.name,
        tool_version=tool.tool_version,
        parameters=params,
        depends_on=[],
        confirmation_level=tool.confirmation_level,
        status="pending",
    )

    plan = ExecutionPlan(
        plan_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        reasoning_graph_id=reasoning_graph_id,
        intent=intent,
        steps=[step],
        overall_confidence=compute_confidence(intent, intent_match_score=0.8),
        requires_confirmation=(tool.confirmation_level >= ConfirmationLevel.BUSINESS),
    )

    return plan


def _build_clarification_example(intent: Intent) -> str:
    """Build a human-readable example of what's needed."""
    entity_map = {
        "distance_km": "1500",
        "vehicle_id": "42",
        "driver_id": "7",
        "client_id": "12",
        "km": "1500",
        "query": "ACME Corp",
        "domain": "financial",
        "code": "USD",
        "stops": "Berlin, Warsaw, Kyiv",
    }
    examples = ", ".join(
        f"{m}={entity_map.get(m, '?')}" for m in intent.missing_required_entities
    )
    return f"{intent.name}({examples})" if examples else intent.name
