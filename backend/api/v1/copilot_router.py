"""Co-Pilot API — Phase 1: Level 0 read-only chat.

Blueprint: §2 — Backend: /api/v1/copilot/*
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.planner import process_utterance
from backend.copilot.schemas import CoPilotResponse, ExecutionPlan, GlobalContext, SessionContext, UIContext
from backend.copilot.tier_gate import has_feature, require_any_feature, require_feature
from backend.dependencies import get_db
from backend.dependencies_security import (
    get_current_user,
    require_admin,
    require_dispatcher,
)
from backend.middleware.input_sanitizer import (
    sanitize_free_text,
    contains_injection,
    detect_suspicious_content,
)
from repositories.copilot_repository import (
    ConversationSummaryRepository,
    CopilotAuditRepository,
    CopilotInsightRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/copilot", tags=["copilot"])

# ── In-memory plan store (Phase 2 — Redis in production) ─────────────────

_pending_plans: Dict[str, ExecutionPlan] = {}
_plan_owners: Dict[str, int] = {}  # plan_id → company_id
_company_conversations: Dict[int, set] = {}

def _validate_plan_ownership(plan_id: str, company_id: int) -> ExecutionPlan:
    """Validate a plan belongs to the requesting company and return it."""
    plan = _pending_plans.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail={"message_key": "copilot.plan.not_found", "message_params": {"plan_id": plan_id}})
    # Verify plan belongs to this company
    owner = _plan_owners.get(plan_id)
    if owner is not None and owner != company_id:
        raise HTTPException(status_code=403, detail={"message_key": "copilot.plan.not_owned"})
    return plan


def _plan_response_status(plan: ExecutionPlan) -> str:
    """Derive the plan's current status for API responses (§13, §30)."""
    if plan.paused:
        return "paused"
    if plan.requires_confirmation:
        return "awaiting_confirmation"
    if any(s.status in ("pending", "running", "paused") for s in plan.steps):
        return "executing"
    # All steps terminal — distinguish the executor's COMPLETED vs
    # PARTIALLY_COMPLETED semantics (§7).
    if any(s.status in ("failed", "skipped", "stopped") for s in plan.steps):
        return "partially_completed"
    return "completed"


def _all_steps_terminal(plan: ExecutionPlan) -> bool:
    """Whether every step reached a terminal state (nothing left to run)."""
    return all(s.status in ("succeeded", "failed", "skipped", "stopped") for s in plan.steps)


def _plan_services(plan_id: str, current_user: Dict[str, Any], db) -> Dict[str, Any]:
    """Request-scoped services dict for executor calls on an owned plan."""
    return {
        "db": db,
        "company_id": current_user.get("company_id", 0),
        "user_id": current_user.get("id", 0),
        "role": current_user.get("role", "dispatcher"),
    }


# ── Request/Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    utterance: str = Field(..., min_length=1, max_length=2000, description="Natural language query")
    conversation_id: Optional[str] = Field(None, description="Resume existing conversation")
    language: str = Field(default="en", description="User language code")
    ui_context: Optional[UIContext] = Field(
        None,
        description="Desktop client's current screen/selection — used to resolve "
                    "missing entities before asking for clarification (§8, §11, §30)",
    )


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversation_id: str
    summary_key: Optional[str] = None
    summary_params: Dict[str, Any] = {}
    clarification_question_key: Optional[str] = None
    clarification_params: Dict[str, Any] = {}
    timeline: list = []
    plan_id: Optional[str] = None


# ── Kill switch check (checked FIRST, before anything else — §26) ──────────
# Short-TTL in-process memo: each copilot request would otherwise pay two
# synchronous Redis reads for data that changes rarely (kill switches).
# Successful (pass-through) results are memoized for ~2s; a flip of the
# switch propagates within the TTL window (≤2s).  Raised 503s are NEVER
# memoized, so an engaged switch trips the very next request.

_KILL_SWITCH_MEMO_TTL_SECONDS = 2.0
# scope → (monotonic timestamp, tripped) — only tripped=False is ever stored.
_kill_switch_memo: Dict[str, tuple[float, bool]] = {}


def _kill_switch_memo_now() -> float:
    """Monotonic time source for the kill-switch memo (patchable in tests)."""
    return time.monotonic()


async def _check_kill_switch(company_id: int) -> None:
    """Check per-company and platform-wide kill switches.
    
    Checked before permission resolution, before tier gating, before 
    anything else in the request path. Uses Redis for fast read on every request.
    
    When tripped: returns a clear 'temporarily unavailable' i18n message.
    Platform-wide kill switch checked second — both must pass.
    
    Results are memoized in-process for ``_KILL_SWITCH_MEMO_TTL_SECONDS``
    (≈2s), so consecutive requests skip the two Redis reads while the memo is
    fresh.  Kill-switch flips propagate within that TTL window (≤2s); a switch
    that is ENGAGED trips the next request immediately because tripped results
    are never memoized.  Fail-closed behavior on Redis outage is unchanged —
    memo misses fall through to the real Redis reads and any exception
    propagates.  The platform check is always evaluated before the per-company
    check.

    Blueprint: §26, §15.1.
    """
    memo_key = f"company:{company_id}"
    now = _kill_switch_memo_now()

    # Fast path — a fresh pass-through memo skips both Redis reads entirely.
    platform_hit = _kill_switch_memo.get("platform")
    if platform_hit is not None and now - platform_hit[0] < _KILL_SWITCH_MEMO_TTL_SECONDS:
        return
    company_hit = _kill_switch_memo.get(memo_key)
    if company_hit is not None and now - company_hit[0] < _KILL_SWITCH_MEMO_TTL_SECONDS:
        return

    from backend.cache import get_cache
    
    cache = get_cache()
    
    # 1. Platform-wide kill switch (checked first — fastest path)
    platform_killed = cache.get("copilot:kill_switch:platform")
    if platform_killed:
        raise HTTPException(
            status_code=503,
            detail={"message_key": "copilot.error.unavailable"},
        )
    
    # 2. Per-company kill switch
    company_killed = cache.get(f"copilot:kill_switch:company:{company_id}")
    if company_killed:
        raise HTTPException(
            status_code=503,
            detail={"message_key": "copilot.error.unavailable"},
        )

    # Both checks passed — memoize the pass-through for the TTL window.
    _kill_switch_memo["platform"] = (now, False)
    _kill_switch_memo[memo_key] = (now, False)


# ── Conversation memory (§11) ─────────────────────────────────────────────

async def _load_conversation_history(
    company_id: int, user_id: int, conversation_id: str,
) -> list:
    """Load the last turns of a conversation for LLM context (§11).

    Best-effort: when the memory store is unreachable the conversation simply
    starts fresh (no history) rather than failing the request.
    """
    try:
        from backend.copilot.context import load_conversation_context
        ctx = await load_conversation_context(company_id, user_id, conversation_id)
        return ctx.turns[-20:]
    except Exception:
        logger.debug("Conversation history load skipped", exc_info=True)
        return []


async def _record_conversation_memory(
    company_id: int,
    user_id: int,
    conversation_id: str,
    utterance: str,
    response: CoPilotResponse,
) -> None:
    """Append the user + assistant turns to the conversation memory store."""
    try:
        from backend.copilot.context import append_conversation_turn
        await append_conversation_turn(company_id, user_id, conversation_id, "user", utterance)
        await append_conversation_turn(company_id, user_id, conversation_id, "assistant", {
            "summary_key": response.summary_key,
            "summary_params": response.summary_params,
            "clarification_question_key": response.clarification_question_key,
        })
    except Exception:
        logger.debug("Conversation memory append skipped", exc_info=True)


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_any_feature("chat", "help_mode"))])
async def chat(
    request: ChatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Process a natural language query through the Co-Pilot pipeline.

    Phase 1: Level 0 read-only tools only. No mutations, no confirmations.

    Tier gate (§16, §33.4): the endpoint is reachable with ``chat`` OR
    ``help_mode``.  Pro tiers lack ``chat`` but have Help Mode — those callers
    get a ``help_only`` pipeline that answers documentation questions only and
    declines live-data/action requests with a friendly tier message.

    Returns a CoPilotResponse with timeline of executed steps.
    """
    company_id = current_user.get("company_id", 0)
    user_id = current_user.get("id", 0)
    role = current_user.get("role", "dispatcher")
    language = request.language or "en"

    tier = str(current_user.get("subscription_tier", "") or "")
    help_only = bool(has_feature(tier, "help_mode") and not has_feature(tier, "chat"))

    # Kill switch first (§26)
    await _check_kill_switch(company_id)

    # Build or resume conversation
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # ── Set correlation context for telemetry (§23.6) ─────────────────
    from backend.copilot.telemetry import set_correlation_context, set_phase
    set_correlation_context(
        conversation_id=conversation_id,
        company_id=company_id,
        user_id=user_id,
    )
    set_phase("UNDERSTAND")

    # Build GlobalContext
    global_ctx = GlobalContext(
        company_id=company_id,
        user_id=user_id,
        role=role,
        language=language,
        timezone=current_user.get("timezone", "UTC"),
        subscription_tier=current_user.get("subscription_tier", "pro"),
        feature_flags={},
    )

    # ── RBAC: resolve the caller's permitted tool set (§15) ────────────
    # Computed server-side from the JWT role on EVERY request — never from
    # a stored session or client hint.  The permitted set is handed into the
    # planner, which rejects any intent outside it before a plan is compiled.
    from backend.copilot.context import resolve_available_tools
    from backend.copilot.role_permissions import get_role_permissions
    user_perms = get_role_permissions(role)
    tool_ctx = await resolve_available_tools(global_ctx, user_perms)
    permitted_tools = set(tool_ctx.available_tools)

    # ── Sanitize user utterance before processing ───────────────────
    # Strict sanitization for AI-directed input — the highest-risk
    # user-supplied text in the system.
    utterance = sanitize_free_text(request.utterance, max_length=2000)
    has_inj, categories = contains_injection(request.utterance)
    if has_inj:
        logger.warning(
            "Prompt injection detected in /chat utterance: "
            "categories=%s company=%d user=%d conversation=%s",
            categories, company_id, user_id, conversation_id,
        )
    susp = detect_suspicious_content(request.utterance)
    if susp:
        logger.warning(
            "Suspicious content in /chat utterance: %s company=%d user=%d",
            susp, company_id, user_id,
        )

    # ── Load conversation memory (§11) for multi-turn LLM context ──────
    conversation_history = await _load_conversation_history(
        company_id, user_id, conversation_id,
    )

    # Process through planner (§23.6 — per-turn pipeline timing)
    from backend.copilot.telemetry import PhaseTimer
    try:
        with PhaseTimer("PIPELINE", conversation_id=conversation_id):
            response = await process_utterance(
                utterance=utterance,
                global_ctx=global_ctx,
                conversation_id=conversation_id,
                services={"db": db, "role": role, "user_id": user_id, "company_id": company_id},
                permitted_tools=permitted_tools,
                conversation_history=conversation_history,
                on_step_update=_make_step_update_callback(conversation_id),
                ui_context=request.ui_context,
                help_only=help_only,
            )
    except Exception as exc:
        logger.exception("Co-Pilot chat failed")
        raise HTTPException(
            status_code=500,
            detail={"message_key": "copilot.error.internal", "detail": str(exc)},
        )

    # Store plan if it needs confirmation
    if response.plan and response.plan.requires_confirmation:
        response.plan.plan_id = response.plan.plan_id or str(uuid.uuid4())
        _pending_plans[response.plan.plan_id] = response.plan
        _plan_owners[response.plan.plan_id] = company_id
        _company_conversations.setdefault(company_id, set()).add(response.plan.plan_id)

    # ── Persist conversation memory + quota usage (§11, §16) ───────────
    await _record_conversation_memory(
        company_id, user_id, conversation_id, utterance, response,
    )
    from backend.copilot.tier_gate import record_usage
    try:
        await asyncio.to_thread(record_usage, company_id)
    except Exception:
        pass

    # Build simplified response
    return ChatResponse(
        conversation_id=response.conversation_id,
        summary_key=response.summary_key,
        summary_params=response.summary_params,
        clarification_question_key=response.clarification_question_key,
        clarification_params=response.clarification_params,
        timeline=[
            {
                "step_id": s.step_id,
                "tool_name": s.tool_name,
                "status": s.status,
                "result": s.result,
                "error": s.error,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            }
            for s in response.timeline
        ],
        plan_id=response.plan.plan_id if response.plan else None,
    )


# ── Voice Input (§3.2, §30) ────────────────────────────────────────────

@router.post("/voice", response_model=ChatResponse, dependencies=[Depends(require_feature("voice"))])
async def voice_input(
    request: ChatRequest,  # Same schema — utterance contains STT transcript
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Submit a voice input result (post-STT transcript + detected language).
    
    Voice is an input modality to the same pipeline as /chat — 
    the same Understand → Reason → Plan → Execute → Summarize flow.
    The detected_language comes from the STT engine, or falls back
    to the user's GlobalContext.language.
    
    Blueprint: §3.2, §30.
    """
    company_id = current_user.get("company_id", 0)
    user_id = current_user.get("id", 0)
    role = current_user.get("role", "dispatcher")
    language = request.language or "en"

    await _check_kill_switch(company_id)

    conversation_id = request.conversation_id or str(uuid.uuid4())

    # ── Set correlation context for telemetry (§23.6) ─────────────────
    from backend.copilot.telemetry import set_correlation_context, set_phase
    set_correlation_context(
        conversation_id=conversation_id,
        company_id=company_id,
        user_id=user_id,
    )
    set_phase("UNDERSTAND")

    global_ctx = GlobalContext(
        company_id=company_id,
        user_id=user_id,
        role=role,
        language=language,
        timezone=current_user.get("timezone", "UTC"),
        subscription_tier=current_user.get("subscription_tier", "pro"),
        feature_flags={},
    )

    # ── RBAC: resolve the caller's permitted tool set (§15) ────────────
    # Same server-side resolution as /chat — voice is the same pipeline.
    from backend.copilot.context import resolve_available_tools
    from backend.copilot.role_permissions import get_role_permissions
    user_perms = get_role_permissions(role)
    tool_ctx = await resolve_available_tools(global_ctx, user_perms)
    permitted_tools = set(tool_ctx.available_tools)

    # ── Sanitize voice transcript before processing ─────────────────
    utterance = sanitize_free_text(request.utterance, max_length=2000)
    has_inj, categories = contains_injection(request.utterance)
    if has_inj:
        logger.warning(
            "Prompt injection detected in /voice utterance: "
            "categories=%s company=%d user=%d",
            categories, company_id, user_id,
        )

    # ── Load conversation memory (§11) for multi-turn LLM context ──────
    conversation_history = await _load_conversation_history(
        company_id, user_id, conversation_id,
    )

    # Process through planner (§23.6 — per-turn pipeline timing)
    from backend.copilot.telemetry import PhaseTimer
    try:
        with PhaseTimer("PIPELINE", conversation_id=conversation_id):
            response = await process_utterance(
                utterance=utterance,
                global_ctx=global_ctx,
                conversation_id=conversation_id,
                services={"db": db, "role": role, "user_id": user_id, "company_id": company_id},
                permitted_tools=permitted_tools,
                conversation_history=conversation_history,
                on_step_update=_make_step_update_callback(conversation_id),
                ui_context=request.ui_context,
            )
    except Exception as exc:
        logger.exception("Co-Pilot voice input failed")
        raise HTTPException(
            status_code=500,
            detail={"message_key": "copilot.error.internal", "detail": str(exc)},
        )

    # Store plan if it needs confirmation
    if response.plan and response.plan.requires_confirmation:
        response.plan.plan_id = response.plan.plan_id or str(uuid.uuid4())
        _pending_plans[response.plan.plan_id] = response.plan
        _plan_owners[response.plan.plan_id] = company_id
        _company_conversations.setdefault(company_id, set()).add(response.plan.plan_id)

    # ── Persist conversation memory + quota usage (§11, §16) ───────────
    await _record_conversation_memory(
        company_id, user_id, conversation_id, utterance, response,
    )
    from backend.copilot.tier_gate import record_usage
    try:
        await asyncio.to_thread(record_usage, company_id)
    except Exception:
        pass

    return ChatResponse(
        conversation_id=response.conversation_id,
        summary_key=response.summary_key,
        summary_params=response.summary_params,
        clarification_question_key=response.clarification_question_key,
        clarification_params=response.clarification_params,
        timeline=[
            {
                "step_id": s.step_id,
                "tool_name": s.tool_name,
                "status": s.status,
                "result": s.result,
                "error": s.error,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            }
            for s in response.timeline
        ],
        plan_id=response.plan.plan_id if response.plan else None,
    )


@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get the status of a specific execution plan."""
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)
    plan = _pending_plans.get(plan_id)
    if plan is None:
        return {"plan_id": plan_id, "status": "not_found", "message_key": "copilot.plan.not_found"}

    # §13 fidelity — reconcile-before-read: apply any terminal long-running
    # worker outcomes so a refresh always shows current truth.
    _reconcile_stored_plan(plan, plan.conversation_id)

    return {
        "plan_id": plan_id,
        "status": _plan_response_status(plan),
        "conversation_id": plan.conversation_id,
        "steps": [
            {
                "step_id": s.step_id,
                "tool_name": s.tool_name,
                "status": s.status,
                "result": s.result,
                "error": s.error,
            }
            for s in plan.steps
        ],
        "intent": plan.intent.name,
        "overall_confidence": plan.overall_confidence,
    }


@router.post("/plans/{plan_id}/cancel")
async def cancel_plan(
    plan_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Cancel an in-flight plan."""
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)
    plan = _validate_plan_ownership(plan_id, company_id)

    from backend.copilot.executor import cancel_plan as do_cancel
    plan = await do_cancel(plan, services=_plan_services(plan_id, current_user, db))

    _pending_plans.pop(plan_id, None)

    return {
        "plan_id": plan_id,
        "status": "cancelled",
        "message_key": "copilot.plan.cancelled",
        "message_params": {"plan_id": plan_id},
    }


# ── Plan pause / resume / stop (§13, §30) ────────────────────────────────

@router.post("/plans/{plan_id}/pause")
async def pause_plan(
    plan_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Pause an in-flight plan — the execution loop halts between steps (§13).

    The plan stays in the pending store with ``paused=True``; resume continues
    the remaining steps from where they stopped.
    """
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)
    plan = _validate_plan_ownership(plan_id, company_id)

    if _all_steps_terminal(plan):
        raise HTTPException(status_code=409, detail={
            "message_key": "copilot.plan.not_pausable",
            "message_params": {"plan_id": plan_id},
        })

    from backend.copilot.executor import pause_plan as do_pause
    try:
        plan = await do_pause(plan, services=_plan_services(plan_id, current_user, db))
    except ValueError as exc:
        # §13 — a plan whose tools do not support pause is refused (409).
        raise HTTPException(status_code=409, detail={
            "message_key": str(exc),
            "message_params": {"plan_id": plan_id},
        })

    return {
        "plan_id": plan_id,
        "status": "paused",
        "message_key": "copilot.plan.paused",
        "message_params": {"plan_id": plan_id},
    }


@router.post("/plans/{plan_id}/resume")
async def resume_plan(
    plan_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Resume a paused plan — continues executing the remaining steps (§13).

    Executes the pending steps immediately (respecting the circuit breaker and
    guardrails in the executor).  A plan that still awaits confirmation stays
    awaiting confirmation instead of executing.
    """
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)
    plan = _validate_plan_ownership(plan_id, company_id)

    if not plan.paused:
        raise HTTPException(status_code=409, detail={
            "message_key": "copilot.plan.not_paused",
            "message_params": {"plan_id": plan_id},
        })

    from backend.copilot.executor import (
        resume_plan as do_resume,
        execute_plan as do_execute,
    )
    services = _plan_services(plan_id, current_user, db)
    try:
        plan = await do_resume(plan, services=services)
    except ValueError as exc:
        # §13 — a plan whose tools do not support resume is refused (409).
        raise HTTPException(status_code=409, detail={
            "message_key": str(exc),
            "message_params": {"plan_id": plan_id},
        })

    if not plan.requires_confirmation:
        plan = await do_execute(
            plan,
            services=services,
            on_step_update=_make_step_update_callback(plan.conversation_id),
        )

    if _all_steps_terminal(plan):
        _pending_plans.pop(plan_id, None)
        _plan_owners.pop(plan_id, None)

    return {
        "plan_id": plan_id,
        "status": _plan_response_status(plan),
        "steps": [
            {
                "step_id": s.step_id,
                "tool_name": s.tool_name,
                "status": s.status,
                "result": s.result,
                "error": s.error,
            }
            for s in plan.steps
        ],
        "message_key": "copilot.plan.resumed",
        "message_params": {"plan_id": plan_id},
    }


@router.post("/plans/{plan_id}/stop")
async def stop_plan(
    plan_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Stop a plan permanently — remaining steps are marked stopped (§13).

    Mirrors cancel (nothing further executes) but records the ``stopped``
    terminal step state so pause/resume can distinguish an intentional stop.
    """
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)
    plan = _validate_plan_ownership(plan_id, company_id)

    from backend.copilot.executor import stop_plan as do_stop
    plan = await do_stop(plan, services=_plan_services(plan_id, current_user, db))

    _pending_plans.pop(plan_id, None)
    _plan_owners.pop(plan_id, None)

    return {
        "plan_id": plan_id,
        "status": "stopped",
        "message_key": "copilot.plan.stopped",
        "message_params": {"plan_id": plan_id},
    }


@router.post("/plans/{plan_id}/confirm")
async def confirm_plan(
    plan_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Confirm and execute a plan awaiting confirmation."""
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)
    user_id = current_user.get("id", 0)
    role = current_user.get("role", "dispatcher")

    plan = _validate_plan_ownership(plan_id, company_id)

    # §13 — a paused plan must be resumed before it can be confirmed.
    if plan.paused:
        raise HTTPException(status_code=409, detail={
            "message_key": "copilot.plan.paused",
            "message_params": {"plan_id": plan_id},
        })

    from backend.copilot.executor import confirm_and_execute

    # Add user context to services
    services = {
        "db": db,
        "company_id": company_id,
        "user_id": user_id,
        "role": role,
    }

    executed_plan = await confirm_and_execute(
        plan,
        services=services,
        on_step_update=_make_step_update_callback(plan.conversation_id),
    )

    _pending_plans.pop(plan_id, None)

    return {
        "plan_id": plan_id,
        "status": "completed",
        "steps": [
            {
                "step_id": s.step_id,
                "tool_name": s.tool_name,
                "status": s.status,
                "result": s.result,
                "error": s.error,
            }
            for s in executed_plan.steps
        ],
    }


# ── Conversation History (§11, §30) ─────────────────────────────────────

@router.get("/conversations")
async def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Pagination cursor (conversation_id)"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """List the calling user's own conversations, newest first.
    
    Blueprint: §11 — conversation history as a first-class feature.
    """
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)
    user_id = current_user.get("id", 0)
    
    try:
        # Query conversation_summary table
        cs_repo = ConversationSummaryRepository(db)
        if cursor:
            rows = cs_repo._fetchall(
                """SELECT id, started_at, ended_at, turn_count, outcome, created_at
                   FROM conversation_summary 
                   WHERE company_id = ? AND user_id = ? AND created_at < ?
                   ORDER BY created_at DESC LIMIT ?""",
                (company_id, user_id, cursor, limit),
            )
        else:
            rows = cs_repo._fetchall(
                """SELECT id, started_at, ended_at, turn_count, outcome, created_at
                   FROM conversation_summary 
                   WHERE company_id = ? AND user_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (company_id, user_id, limit),
            )
        
        conversations = []
        for row in rows:
            conversations.append({
                "conversation_id": str(row["id"]),
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "turn_count": row["turn_count"],
                "outcome": row["outcome"],
            })
        
        next_cursor = str(rows[-1]["id"]) if len(rows) == limit else None
        
        return {
            "items": conversations,
            "next_cursor": next_cursor,
            "limit": limit,
        }
    except Exception as exc:
        logger.warning("Failed to list conversations: %s", exc)
        return {"items": [], "next_cursor": None, "limit": limit}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Get details and turn history for a specific conversation.
    
    Sources from Redis if still active, falls back to conversation_summary.
    Blueprint: §11, §30.
    """
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)
    user_id = current_user.get("id", 0)
    
    try:
        # Try Postgres summary
        cs_repo = ConversationSummaryRepository(db)
        row = cs_repo._fetchone(
            """SELECT id, started_at, ended_at, turn_count, outcome,
                      pinned_provider_id, pinned_model_id, pinned_prompt_version
               FROM conversation_summary 
               WHERE id = ? AND company_id = ? AND user_id = ?""",
            (conversation_id, company_id, user_id),
        )
        
        if not row:
            raise HTTPException(status_code=404, detail={
                "message_key": "copilot.plan.not_found",
                "message_params": {"plan_id": conversation_id},
            })

        # ── Turn history lives in the conversation memory store (§11) ──
        # Full turn content is kept in Redis (4h sliding TTL) — read it from
        # the store instead of returning an empty list.
        from backend.copilot.context import get_conversation_turns
        try:
            turns = await get_conversation_turns(company_id, user_id, conversation_id)
        except Exception:
            logger.debug("Conversation turn load skipped", exc_info=True)
            turns = []

        return {
            "conversation_id": str(row["id"]),
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "turn_count": row["turn_count"],
            "outcome": row["outcome"],
            "pinned_provider_id": row["pinned_provider_id"],
            "pinned_model_id": row["pinned_model_id"],
            "pinned_prompt_version": row["pinned_prompt_version"],
            "turns": turns,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to get conversation %s: %s", conversation_id, exc)
        raise HTTPException(status_code=500, detail={
            "message_key": "copilot.error.internal",
        })


# ── Plan Undo (§30, §21 Phase 3) ───────────────────────────────────────

@router.post("/plans/{plan_id}/undo")
async def undo_plan(
    plan_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Reverse a completed step where supports_undo=True.
    
    Subject to the 30-minute undo window (§22 item 4).
    Blueprint: §30.
    """
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)

    # §13 — a paused plan must be resumed before it can be undone.
    pending_plan = _pending_plans.get(plan_id)
    if pending_plan is not None and pending_plan.paused:
        raise HTTPException(status_code=409, detail={
            "message_key": "copilot.plan.paused",
            "message_params": {"plan_id": plan_id},
        })

    # Look up the plan's undo token from the audit log
    try:
        audit_repo = CopilotAuditRepository(db)
        row = audit_repo._fetchone(
            """SELECT result, tool_name, started_at
               FROM copilot_audit_log
               WHERE plan_id = ? AND company_id = ? AND status = 'succeeded'
                 AND result IS NOT NULL
               ORDER BY started_at DESC LIMIT 1""",
            (plan_id, company_id),
        )
        
        if not row:
            raise HTTPException(status_code=404, detail={
                "message_key": "copilot.undo.not_found",
                "message_params": {"plan_id": plan_id},
            })
        
        import json
        result = json.loads(row["result"]) if isinstance(row["result"], str) else row["result"]
        undo_token = result.get("undo_token") if isinstance(result, dict) else None
        
        if not undo_token:
            raise HTTPException(status_code=400, detail={
                "message_key": "copilot.undo.not_available",
            })
        
        # Check undo window (§22 item 4)
        from backend.copilot.executor import is_undo_expired
        started_at = row["started_at"]
        if started_at and is_undo_expired(started_at):
            raise HTTPException(status_code=400, detail={
                "message_key": "copilot.undo.expired",
            })
        
        # Call the tool's undo method
        from backend.copilot.tools.registry import get_tool
        from backend.copilot.tools.base import ToolExecutionContext
        from backend.copilot.schemas import SessionContext
        
        tool = get_tool(row["tool_name"])
        if not tool or not tool.supports_undo:
            raise HTTPException(status_code=400, detail={
                "message_key": "copilot.undo.not_supported",
            })
        
        ctx = ToolExecutionContext(
            company_id=company_id,
            user_id=current_user.get("id", 0),
            role=current_user.get("role", "dispatcher"),
            session_context=SessionContext(),
            services={"db": db},
        )
        
        result = await tool.undo(undo_token, ctx)
        
        return {
            "plan_id": plan_id,
            "undo_status": result.status,
            "message_key": result.message_key,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Undo failed for plan %s", plan_id)
        raise HTTPException(status_code=500, detail={
            "message_key": "copilot.error.internal",
        })


# ── Proactive Insights Queue (§18, §30) ────────────────────────────────

@router.get("/insights", dependencies=[Depends(require_feature("background_monitoring"))])
async def list_insights(
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="Filter by status: new/reviewed/dismissed"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """List proactive insights for the company's review queue.
    
    Enterprise feature (§18). Read-only — approving an insight routes
    back through the normal plan → confirm → execute pipeline.
    Blueprint: §30.
    """
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)
    
    try:
        insight_repo = CopilotInsightRepository(db)
        if status_filter:
            rows = insight_repo._fetchall(
                """SELECT id, insight_type, payload, severity, status, created_at
                   FROM copilot_insights
                   WHERE company_id = ? AND status = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (company_id, status_filter, limit),
            )
        else:
            rows = insight_repo._fetchall(
                """SELECT id, insight_type, payload, severity, status, created_at
                   FROM copilot_insights
                   WHERE company_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (company_id, limit),
            )
        
        insights = []
        for row in rows:
            import json
            payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row.get("payload", {})
            insights.append({
                "id": str(row["id"]),
                "insight_type": row["insight_type"],
                "payload": payload if isinstance(payload, dict) else {},
                "severity": row["severity"],
                "status": row["status"],
                "created_at": row["created_at"],
            })
        
        return {"items": insights, "limit": limit}
    except Exception as exc:
        logger.warning("Failed to list insights: %s", exc)
        return {"items": [], "limit": limit}


# ── Observability (§23.6) ──────────────────────────────────────────────────

_HIGH_CONFIDENCE_THRESHOLD = 0.85   # mirrors backend/copilot/confidence.py
_MEDIUM_CONFIDENCE_THRESHOLD = 0.55


def _live_confidence_from_metrics() -> Optional[Dict[str, int]]:
    """Return live ``copilot.confidence.high/medium/low`` counters if any exist.

    The planner increments these in ``utils.observability.metrics`` per plan;
    prefer them over the audit-log derivation so the panel shows current
    numbers. Returns ``None`` when no counter has been incremented yet.
    """
    try:
        from utils.observability import metrics

        snapshot = metrics.snapshot()
        counters = snapshot.get("counters", {}) or {}
        values = {
            "high": int(counters.get("copilot.confidence.high", 0)),
            "medium": int(counters.get("copilot.confidence.medium", 0)),
            "low": int(counters.get("copilot.confidence.low", 0)),
        }
        if values["high"] or values["medium"] or values["low"]:
            return values
    except Exception:
        logger.debug("Copilot observability: live confidence counters unavailable")
    return None


def _query_copilot_audit_aggregates(
    audit_repo: CopilotAuditRepository,
    company_id: int,
) -> Dict[str, Any]:
    """Read-only copilot_audit_log aggregates (tool failures, abandonment, confidence).

    Tolerates both schemas — the SQLite ``action`` column and the Alembic
    ``status`` column — mirroring what the desktop panel does in LOCAL mode.
    """
    company_filter = " AND company_id = ?" if company_id else ""
    params: tuple = (company_id,) if company_id else ()

    result: Dict[str, Any] = {
        "tool_failures": {"total": 0, "failures": 0, "successes": 0},
        "abandonment": {"started": 0, "finished": 0},
        "confidence": {"high": 0, "medium": 0, "low": 0},
        "audit_rows": 0,
    }

    # Confidence distribution — live counters preferred, else stored scores.
    live = _live_confidence_from_metrics()
    if live is not None:
        result["confidence"] = live
    else:
        rows = audit_repo._fetchall(
            "SELECT "
            " COALESCE(SUM(CASE WHEN confidence_score >= ? THEN 1 ELSE 0 END),0) AS high, "
            " COALESCE(SUM(CASE WHEN confidence_score >= ? AND confidence_score < ? THEN 1 ELSE 0 END),0) AS medium, "
            " COALESCE(SUM(CASE WHEN confidence_score < ? THEN 1 ELSE 0 END),0) AS low "
            " FROM copilot_audit_log WHERE confidence_score IS NOT NULL" + company_filter,
            (_HIGH_CONFIDENCE_THRESHOLD, _MEDIUM_CONFIDENCE_THRESHOLD,
             _HIGH_CONFIDENCE_THRESHOLD, _MEDIUM_CONFIDENCE_THRESHOLD, *params),
        ) or [{}]
        result["confidence"] = rows[0]

    # Tool failure / abandonment — ``action`` column first (SQLite schema),
    # ``status`` column fallback (Alembic migration schema).
    try:
        rows = audit_repo._fetchall(
            "SELECT COUNT(*) AS total, "
            " COALESCE(SUM(CASE WHEN action = 'tool_execution_failed' THEN 1 ELSE 0 END),0) AS failures, "
            " COALESCE(SUM(CASE WHEN action = 'tool_execution_succeeded' THEN 1 ELSE 0 END),0) AS successes "
            " FROM copilot_audit_log "
            " WHERE action IN ('tool_execution_start','tool_execution_succeeded','tool_execution_failed')"
            + company_filter,
            params,
        ) or [{}]
        result["tool_failures"] = rows[0]

        rows = audit_repo._fetchall(
            "SELECT COUNT(DISTINCT conversation_id) AS conversations, "
            " COUNT(DISTINCT CASE WHEN action = 'tool_execution_start' THEN conversation_id END) AS started, "
            " COUNT(DISTINCT CASE WHEN action IN ('tool_execution_succeeded','tool_execution_failed') "
            "   THEN conversation_id END) AS finished "
            " FROM copilot_audit_log "
            " WHERE conversation_id IS NOT NULL AND conversation_id != ''" + company_filter,
            params,
        ) or [{}]
        result["abandonment"] = rows[0]
    except Exception:
        logger.debug(
            "Copilot observability: action-column queries unavailable, trying status column"
        )
        rows = audit_repo._fetchall(
            "SELECT COUNT(*) AS total, "
            " COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END),0) AS failures, "
            " COALESCE(SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END),0) AS successes "
            " FROM copilot_audit_log "
            " WHERE status IN ('succeeded','failed')" + company_filter,
            params,
        ) or [{}]
        result["tool_failures"] = rows[0]

        rows = audit_repo._fetchall(
            "SELECT COUNT(DISTINCT conversation_id) AS started, "
            " COUNT(DISTINCT CASE WHEN status = 'succeeded' THEN conversation_id END) AS finished "
            " FROM copilot_audit_log "
            " WHERE status IS NOT NULL AND status != ''" + company_filter,
            params,
        ) or [{}]
        result["abandonment"] = rows[0]

    total_rows = audit_repo._fetchone(
        "SELECT COUNT(*) AS total FROM copilot_audit_log" + company_filter,
        params,
    )
    result["audit_rows"] = (total_rows or {}).get("total", 0)
    return result


def _query_circuit_breaker_state() -> Dict[str, Any]:
    """Read the in-memory per-company circuit-breaker state (read-only)."""
    from backend.copilot.circuit_breaker import get_circuit_breaker

    cb = get_circuit_breaker()
    states = getattr(cb, "_states", {}) or {}
    tripped = [s for s in states.values() if getattr(s, "tripped", False)]
    companies = [
        {
            "company_id": getattr(s, "company_id", 0),
            "tripped": bool(getattr(s, "tripped", False)),
            "tripped_reason": getattr(s, "tripped_reason", None) or "",
        }
        for s in sorted(states.values(), key=lambda s: getattr(s, "company_id", 0))
    ]
    return {"tracked": len(states), "tripped": len(tripped), "companies": companies}


def _query_phase_timings() -> List[Dict[str, Any]]:
    """Read per-phase timings recorded by PhaseTimer into the metrics registry."""
    from utils.observability import metrics

    snapshot = metrics.snapshot()
    counters = snapshot.get("counters", {}) or {}
    gauges = snapshot.get("gauges", {}) or {}
    rows: List[Dict[str, Any]] = []
    for key, count in counters.items():
        if key.startswith("copilot.phase.") and key.endswith(".count"):
            phase = key[len("copilot.phase."):-len(".count")]
            rows.append({
                "phase": phase,
                "count": int(count),
                "last_ms": gauges.get(f"copilot.phase.{phase}.last_ms"),
            })
    rows.sort(key=lambda r: r["last_ms"] if r["last_ms"] is not None else -1, reverse=True)
    return rows


@router.get("/observability")
async def get_copilot_observability(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Read-only Co-Pilot observability aggregates for the dev-toolkit panel (§23.6).

    Returns the aggregates the desktop panel renders: tool failure rate,
    abandonment rate, circuit-breaker trips, confidence distribution and
    per-phase timings — tenant-scoped on the caller's company.  Every query is
    read-only and schema-tolerant (``action`` vs ``status`` columns).
    """
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)

    payload: Dict[str, Any] = {
        "tool_failures": {"total": 0, "failures": 0, "successes": 0},
        "abandonment": {"started": 0, "finished": 0},
        "confidence": {"high": 0, "medium": 0, "low": 0},
        "circuit_breaker": {"tracked": 0, "tripped": 0, "companies": []},
        "phase_timings": [],
        "audit_rows": 0,
    }
    try:
        audit_repo = CopilotAuditRepository(db)
        payload.update(_query_copilot_audit_aggregates(audit_repo, company_id))
    except Exception as exc:
        logger.warning("Copilot observability: audit query failed: %s", exc)
    try:
        payload["circuit_breaker"] = _query_circuit_breaker_state()
    except Exception as exc:
        logger.debug("Copilot observability: circuit-breaker state unavailable: %s", exc)
    try:
        payload["phase_timings"] = _query_phase_timings()
    except Exception as exc:
        logger.debug("Copilot observability: phase timings unavailable: %s", exc)
    return payload


class InsightActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(..., pattern="^(approve|dismiss|remind)$", description="approve → reviewed, dismiss → dismissed, remind → reminded")


@router.post("/insights/{insight_id}/action")
async def insight_action(
    insight_id: int,
    request: InsightActionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Approve, dismiss, or snooze-remind an insight in the review queue (§18).

    ``approve`` moves the insight to ``reviewed``; ``dismiss`` to ``dismissed``;
    ``remind`` (Remind Later, §18) moves it to ``reminded``.  Tenant-scoped on
    the caller's company_id.
    """
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)

    _ACTION_TO_STATUS = {
        "approve": "reviewed",
        "dismiss": "dismissed",
        "remind": "reminded",
    }
    _ACTION_TO_KEY = {
        "approve": "copilot.insight.action.review",
        "dismiss": "copilot.insight.action.dismiss",
        "remind": "copilot.insight.action.remind",
    }
    status = _ACTION_TO_STATUS[request.action]
    message_key = _ACTION_TO_KEY[request.action]

    try:
        insight_repo = CopilotInsightRepository(db)
        updated = insight_repo.update_status(insight_id, company_id, status)
    except Exception as exc:
        logger.warning("Failed to update insight %s: %s", insight_id, exc)
        raise HTTPException(status_code=500, detail={
            "message_key": "copilot.error.internal",
        })

    if not updated:
        raise HTTPException(status_code=404, detail={
            "message_key": "copilot.insight.not_found",
            "message_params": {"insight_id": insight_id},
        })

    return {
        "id": insight_id,
        "status": status,
        "message_key": message_key,
    }


# ── Active WebSocket connections for real-time updates ──────────────────────

_ws_connections: Dict[str, list[WebSocket]] = {}

async def _push_plan_update(step_id: str, status: str, tool_name: str, conversation_id: str):
    """Push a step status update to all WebSocket listeners for this conversation."""
    connections = _ws_connections.get(conversation_id, [])
    message = {
        "type": "step_update",
        "step_id": step_id,
        "status": status,
        "tool_name": tool_name,
        "timestamp": str(datetime.utcnow()),
    }
    for ws in connections[:]:
        try:
            await ws.send_json(message)
        except Exception:
            connections.remove(ws)


def _make_step_update_callback(conversation_id: str):
    """Return a synchronous ``on_step_update`` callback that pushes WS updates.

    The executor invokes ``on_step_update(step_id, status, tool_name)``
    synchronously, while ``_push_plan_update`` is async — the adapter
    schedules the push on the running loop when one exists (FastAPI request
    path) and runs it inline otherwise (§12.1).
    """

    async def _push(step_id: str, status: str, tool_name: str) -> None:
        try:
            await _push_plan_update(step_id, status, tool_name, conversation_id)
        except Exception:
            logger.exception("WS step update failed for conversation %s", conversation_id)

    def _callback(step_id: str, status: str, tool_name: str) -> None:
        try:
            asyncio.create_task(_push(step_id, status, tool_name))
        except RuntimeError:
            # No running event loop — run inline (tests / sync callers).
            try:
                asyncio.run(_push(step_id, status, tool_name))
            except Exception:
                pass

    return _callback


# ── §13 long-running progress over WebSocket ────────────────────────────────
# Heavy tools run on Celery (executor dispatches them); the task writes
# progress to ``copilot:tool-progress:{task_id}``.  The WS handler polls the
# conversation's progress-key list (registered by the executor on dispatch)
# and pushes ``type:"progress"`` messages with percent + message_key.

_WS_PROGRESS_POLL_SECONDS = 2.0


async def _push_progress_message(
    websocket: WebSocket,
    conversation_id: str,
    progress: Dict[str, Any],
    task_id: str,
) -> None:
    """Push a single ``type:"progress"`` message for a running long-running step."""
    message = {
        "type": "progress",
        "task_id": task_id,
        "step_id": progress.get("step_id", ""),
        "tool_name": progress.get("tool_name", ""),
        "percent": progress.get("percent", 0),
        "message_key": progress.get("message_key", ""),
        "status": progress.get("status", "running"),
        "plan_id": progress.get("plan_id", ""),
        "result": progress.get("result"),
        "error": progress.get("error"),
        "timestamp": str(datetime.utcnow()),
    }
    await websocket.send_json(message)


async def _poll_and_push_progress(
    websocket: WebSocket,
    conversation_id: str,
    sent_progress: Dict[str, Any],
) -> None:
    """Poll the conversation's long-running progress keys and push new/changed
    progress payloads.  ``sent_progress`` tracks the last payload per key so
    unchanged progress is not re-sent.  Also reconciles the stored plans for
    this conversation so terminal worker outcomes are back-written (§13)."""
    try:
        from backend.celery_app.tasks.copilot_tool_tasks import (
            get_conversation_progress_keys,
            read_progress,
        )

        for key in get_conversation_progress_keys(conversation_id):
            task_id = key.rsplit(":", 1)[-1] if ":" in key else key
            progress = read_progress(task_id)
            if not progress or not isinstance(progress, dict):
                continue
            if sent_progress.get(key) == progress:
                continue
            sent_progress[key] = progress
            await _push_progress_message(websocket, conversation_id, progress, task_id)

        # §13 fidelity — back-write terminal worker outcomes into the in-memory
        # stored plans so GET /plans/{id} reflects current truth.
        for plan in _pending_plans.values():
            if plan.conversation_id == conversation_id:
                _reconcile_stored_plan(plan, conversation_id)
    except Exception as exc:
        logger.debug("WS progress poll failed for conversation %s: %s", conversation_id, exc)


# ── §13 long-running plan reconciliation ────────────────────────────────────
# The executor dispatches long-running steps to Celery and leaves the step
# ``running`` with a ``{task_id, progress_key}`` handle.  The worker writes
# progress (incl. the terminal outcome) to the Redis key; these helpers apply
# that terminal outcome back to the stored plan so a plan refresh shows the
# step's real result.  Failure-safe: unknown plans / tasks / malformed payloads
# are skipped silently.

_TERMINAL_PROGRESS_STATUSES = frozenset({"succeeded", "failed"})
_STEP_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "skipped", "stopped"})


def _apply_terminal_progress_to_plan(plan: ExecutionPlan, progress: Dict[str, Any]) -> bool:
    """Back-write one terminal progress payload onto a stored plan's step.

    Returns True when the plan changed.  Non-terminal payloads, unknown step
    ids and already-terminal steps are skipped (no-op).
    """
    status = progress.get("status")
    step_id = progress.get("step_id")
    if status not in _TERMINAL_PROGRESS_STATUSES or not step_id:
        return False
    step = next((s for s in plan.steps if s.step_id == step_id), None)
    if step is None or step.status in _STEP_TERMINAL_STATUSES:
        return False
    step.status = status
    result = progress.get("result")
    if isinstance(result, dict):
        step.result = result
    error = progress.get("error")
    if error:
        step.error = str(error)
    step.finished_at = datetime.utcnow()
    logger.info(
        "Reconciled long-running step %s (%s) → %s for plan %s",
        step.step_id, step.tool_name, step.status, plan.plan_id,
    )
    return True


def _reconcile_stored_plan(plan: ExecutionPlan, conversation_id: str) -> bool:
    """Apply any terminal progress payloads for *conversation_id* onto *plan*.

    Returns True when at least one step was back-written.  Never raises —
    cache misses / malformed payloads are skipped.
    """
    try:
        from backend.celery_app.tasks.copilot_tool_tasks import (
            get_conversation_progress_keys,
            read_progress,
        )

        changed = False
        for key in get_conversation_progress_keys(conversation_id):
            task_id = key.rsplit(":", 1)[-1] if ":" in key else key
            progress = read_progress(task_id)
            if not progress or not isinstance(progress, dict):
                continue
            if _apply_terminal_progress_to_plan(plan, progress):
                changed = True
        return changed
    except Exception as exc:
        logger.debug("Plan reconciliation skipped for %s: %s", plan.plan_id, exc)
        return False


@router.websocket("/ws/{conversation_id}")
async def copilot_websocket(
    websocket: WebSocket,
    conversation_id: str,
    token: str = Query(None),
):
    """WebSocket for real-time execution timeline updates (§12.1).

    Authentication: JWT token passed as ?token= query parameter.
    The executor pushes step status changes through _ws_connections.
    """
    # Validate token before accepting
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    try:
        from backend.security import decode_access_token
        payload = decode_access_token(token)
        company_id = payload.get("company_id", 0)
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # ── Kill switch (§26) — the same gate the REST endpoints apply ────
    try:
        await _check_kill_switch(company_id)
    except HTTPException:
        await websocket.close(code=4003, reason="Co-Pilot unavailable")
        return

    await websocket.accept()
    logger.info("Co-Pilot WebSocket connected: conversation=%s company=%d", conversation_id, company_id)

    # Register connection
    _ws_connections.setdefault(conversation_id, []).append(websocket)

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "conversation_id": conversation_id,
        })

        # Per-connection tracker so progress payloads are only pushed once.
        sent_progress: Dict[str, Any] = {}

        async def _poll_progress() -> None:
            await _poll_and_push_progress(websocket, conversation_id, sent_progress)

        # Initial poll — surface any already-running long-running progress.
        await _poll_progress()

        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=_WS_PROGRESS_POLL_SECONDS,
                )
            except asyncio.TimeoutError:
                # Bounded poll while long-running steps are in flight (§13).
                await _poll_progress()
                continue
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("Co-Pilot WebSocket disconnected: conversation=%s", conversation_id)
    except Exception as exc:
        logger.exception("Co-Pilot WebSocket error: %s", exc)
    finally:
        # Unregister
        try:
            _ws_connections.get(conversation_id, []).remove(websocket)
        except ValueError:
            pass
        try:
            await websocket.close()
        except Exception:
            pass


# ── Kill switch management helpers (§26) ────────────────────────────────

async def _set_kill_switch(company_id: Optional[int] = None, killed: bool = True) -> None:
    """Toggle kill switch for a company or platform-wide.
    
    Args:
        company_id: None for platform-wide, specific int for per-company.
        killed: True to enable (kill the Co-Pilot), False to disable.
    """
    from backend.cache import get_cache
    
    cache = get_cache()
    if company_id is None:
        cache.set("copilot:kill_switch:platform", killed, ttl=86400)
    else:
        cache.set(f"copilot:kill_switch:company:{company_id}", killed, ttl=86400)
    
    if killed:
        logger.warning("KILL SWITCH ACTIVATED: company=%s", company_id or "PLATFORM")
    
    # If activating, cancel all in-flight plans for this company
    if killed:
        await _cancel_inflight_plans(company_id)


async def _cancel_inflight_plans(company_id: Optional[int] = None) -> None:
    """Cancel all in-flight AWAITING_CONFIRMATION plans for a company."""
    from backend.copilot.executor import cancel_plan
    
    cancelled = 0
    plan_ids = list(_pending_plans.keys())
    
    for plan_id in plan_ids:
        owner = _plan_owners.get(plan_id)
        if company_id is not None and owner != company_id:
            continue
        plan = _pending_plans.get(plan_id)
        if plan:
            plan = await cancel_plan(plan)
            _pending_plans.pop(plan_id, None)
            _plan_owners.pop(plan_id, None)
            # Clean up company_conversations tracking
            if company_id is None:
                _company_conversations.clear()
            else:
                _company_conversations.pop(company_id, None)
            cancelled += 1
    
    if cancelled:
        logger.info("Kill switch: cancelled %d in-flight plans for company=%s", cancelled, company_id or "ALL")


# ── Admin kill-switch endpoint (§26) ──────────────────────────────────────

class KillSwitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enable: bool = Field(..., description="True to engage the kill switch, False to release")
    scope: str = Field(..., pattern="^(platform|company)$", description="platform-wide or per-company")
    company_id: Optional[int] = Field(None, description="Required when scope=company")


@router.post("/admin/kill-switch")
async def set_kill_switch_endpoint(
    request: KillSwitchRequest,
    current_user: Dict[str, Any] = Depends(require_admin),
):
    """Admin-only endpoint to toggle the Co-Pilot kill switch (§26).

    ``scope="platform"`` kills the Co-Pilot for every company;
    ``scope="company"`` requires ``company_id`` and kills it for that tenant.
    Engaging the switch also cancels that scope's in-flight plans.
    """
    if request.scope == "platform":
        await _set_kill_switch(company_id=None, killed=request.enable)
        return {"scope": "platform", "enabled": request.enable}

    if not request.company_id:
        raise HTTPException(
            status_code=422,
            detail={"message_key": "copilot.error.internal"},
        )
    await _set_kill_switch(company_id=request.company_id, killed=request.enable)
    return {
        "scope": "company",
        "company_id": request.company_id,
        "enabled": request.enable,
    }


# ── Autonomous-mode workflow approvals (§21 Ph.4 item 4) ─────────────────

class AutonomyApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_id: int = Field(..., description="Target company")
    workflow: str = Field(..., min_length=1, max_length=200, description="Plan intent name, e.g. dispatch.cancel")
    enabled: bool = Field(True, description="True to pre-approve the workflow, False to revoke approval")


@router.post("/admin/autonomy/approvals")
async def set_autonomy_approval(
    request: AutonomyApprovalRequest,
    current_user: Dict[str, Any] = Depends(require_admin),
    db = Depends(get_db),
):
    """Admin-only per-workflow opt-in for Autonomous Mode (§21 Ph.4 item 4).

    Enabling a workflow pre-approves it so the autonomous execution path in
    the planner may skip the confirmation gate (still gated by the tier's
    ``autonomous`` feature flag and the circuit breaker, §23.1).
    """
    from repositories.copilot_repository import CopilotAutonomyApprovalRepository

    try:
        CopilotAutonomyApprovalRepository(db).set_approved(
            company_id=request.company_id,
            workflow=request.workflow,
            enabled=request.enabled,
            performed_by=str(current_user.get("id", 0)),
        )
    except Exception as exc:
        logger.warning(
            "Autonomy approval write failed: company=%d workflow=%s: %s",
            request.company_id, request.workflow, exc,
        )
        raise HTTPException(
            status_code=503,
            detail={"message_key": "copilot.error.autonomy_approval_unavailable"},
        )

    logger.info(
        "Autonomy approval set by admin user=%s: company=%d workflow=%s enabled=%s",
        current_user.get("id", 0), request.company_id, request.workflow, request.enabled,
    )
    return {
        "company_id": request.company_id,
        "workflow": request.workflow,
        "enabled": request.enabled,
    }
