"""Co-Pilot API — Phase 1: Level 0 read-only chat.

Blueprint: §2 — Backend: /api/v1/copilot/*
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.planner import process_utterance
from backend.copilot.schemas import CoPilotResponse, ExecutionPlan, GlobalContext, SessionContext
from backend.copilot.tier_gate import require_feature
from backend.dependencies import get_db
from backend.dependencies_security import get_current_user, require_dispatcher

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


# ── Request/Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    utterance: str = Field(..., min_length=1, max_length=2000, description="Natural language query")
    conversation_id: Optional[str] = Field(None, description="Resume existing conversation")
    language: str = Field(default="en", description="User language code")


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

async def _check_kill_switch(company_id: int) -> None:
    """Check per-company and platform-wide kill switches.
    
    Checked before permission resolution, before tier gating, before 
    anything else in the request path. Uses Redis for fast read on every request.
    
    When tripped: returns a clear 'temporarily unavailable' i18n message.
    Platform-wide kill switch checked second — both must pass.
    
    Blueprint: §26, §15.1.
    """
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


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db = Depends(get_db),
):
    """Process a natural language query through the Co-Pilot pipeline.

    Phase 1: Level 0 read-only tools only. No mutations, no confirmations.

    Returns a CoPilotResponse with timeline of executed steps.
    """
    company_id = current_user.get("company_id", 0)
    user_id = current_user.get("id", 0)
    role = current_user.get("role", "dispatcher")
    language = request.language or "en"

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

    # Process through planner
    try:
        response = await process_utterance(
            utterance=request.utterance,
            global_ctx=global_ctx,
            conversation_id=conversation_id,
            services={"db": db},
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

@router.post("/voice", response_model=ChatResponse)
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

    try:
        response = await process_utterance(
            utterance=request.utterance,
            global_ctx=global_ctx,
            conversation_id=conversation_id,
            services={"db": db},
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

    return {
        "plan_id": plan_id,
        "status": "awaiting_confirmation" if plan.requires_confirmation else "completed",
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
):
    """Cancel an in-flight plan."""
    company_id = current_user.get("company_id", 0)
    await _check_kill_switch(company_id)
    plan = _validate_plan_ownership(plan_id, company_id)

    from backend.copilot.executor import cancel_plan as do_cancel
    plan = await do_cancel(plan)

    _pending_plans.pop(plan_id, None)

    return {
        "plan_id": plan_id,
        "status": "cancelled",
        "message_key": "copilot.plan.cancelled",
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

    from backend.copilot.executor import confirm_and_execute

    # Add user context to services
    services = {
        "db": db,
        "company_id": company_id,
        "user_id": user_id,
        "role": role,
    }

    executed_plan = await confirm_and_execute(plan, services=services)

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
        if cursor:
            rows = db.conn.execute(
                """SELECT id, started_at, ended_at, turn_count, outcome, created_at
                   FROM conversation_summary 
                   WHERE company_id = ? AND user_id = ? AND created_at < ?
                   ORDER BY created_at DESC LIMIT ?""",
                (company_id, user_id, cursor, limit),
            ).fetchall()
        else:
            rows = db.conn.execute(
                """SELECT id, started_at, ended_at, turn_count, outcome, created_at
                   FROM conversation_summary 
                   WHERE company_id = ? AND user_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (company_id, user_id, limit),
            ).fetchall()
        
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
        row = db.conn.execute(
            """SELECT id, started_at, ended_at, turn_count, outcome,
                      pinned_provider_id, pinned_model_id, pinned_prompt_version
               FROM conversation_summary 
               WHERE id = ? AND company_id = ? AND user_id = ?""",
            (conversation_id, company_id, user_id),
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail={
                "message_key": "copilot.plan.not_found",
                "message_params": {"plan_id": conversation_id},
            })
        
        return {
            "conversation_id": str(row["id"]),
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "turn_count": row["turn_count"],
            "outcome": row["outcome"],
            "pinned_provider_id": row["pinned_provider_id"],
            "pinned_model_id": row["pinned_model_id"],
            "pinned_prompt_version": row["pinned_prompt_version"],
            "turns": [],  # Full turn content is in Redis only — not persisted
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
    
    # Look up the plan's undo token from the audit log
    try:
        row = db.conn.execute(
            """SELECT result, tool_name, started_at
               FROM copilot_audit_log
               WHERE plan_id = ? AND company_id = ? AND status = 'succeeded'
                 AND result IS NOT NULL
               ORDER BY started_at DESC LIMIT 1""",
            (plan_id, company_id),
        ).fetchone()
        
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

@router.get("/insights")
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
        if status_filter:
            rows = db.conn.execute(
                """SELECT id, insight_type, payload, severity, status, created_at
                   FROM copilot_insights
                   WHERE company_id = ? AND status = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (company_id, status_filter, limit),
            ).fetchall()
        else:
            rows = db.conn.execute(
                """SELECT id, insight_type, payload, severity, status, created_at
                   FROM copilot_insights
                   WHERE company_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (company_id, limit),
            ).fetchall()
        
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

        while True:
            data = await websocket.receive_text()
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
