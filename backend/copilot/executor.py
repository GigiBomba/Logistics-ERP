"""Execution Engine — state machine enforcing plan lifecycle.

Blueprint: §7 — Execution State Machine.

PHASE 0: State machine skeleton and cost guardrails only.
Phase 1+ will wire actual tool execution.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.copilot.schemas import (
    ConfirmationLevel,
    ExecutionPlan,
    ExecutionStep,
    SessionContext,
    ToolResult,
)

# ── Role → allowed resource prefixes (§15) ────────────────────────────────
# Derived at module load from the authoritative §8.3 permission matrix
# (backend/copilot/role_permissions.py) — the SAME source of truth the
# planner uses via ``resolve_available_tools`` — so the executor gate can
# never drift from what the planner admits (e.g. the historical
# ``analytics.query`` / ``invoices:write`` denial for dispatcher sessions).
# Each ``"resource:operation"`` permission contributes its resource; the
# no-colon permission ``"can_schedule_maintenance"`` is its own resource
# (admin+manager only per role_permissions) and stays distinct from the
# ``"maintenance"`` resource (``maintenance:write``).
from backend.copilot.role_permissions import get_role_permissions

_ROLE_RESOURCE_ACCESS: Dict[str, set[str]] = {
    role: {p.split(":")[0] for p in get_role_permissions(role)}
    for role in ("manager", "dispatcher", "driver")
}

logger = logging.getLogger(__name__)


class PlanStatus(str, Enum):
    """Execution plan lifecycle states. Maps to §7 state machine."""
    UNDERSTOOD = "understood"
    REASONING = "reasoning"
    PLANNED = "planned"
    VALIDATING = "validating"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    EXECUTING = "executing"
    PAUSED = "paused"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    STOPPED = "stopped"
    CANCELLED = "cancelled"


# ── Cost & Runaway-Loop Guardrails (§23.3) ──────────────────────────────────

# Hard ceilings, enforced independent of confidence scoring:
MAX_REASONING_GRAPH_NODES_PER_TURN: int = 50
MAX_TOOL_CALLS_PER_PLAN: int = 20
MAX_LLM_TOKENS_PER_TURN: int = 32000

# Tool-level timeouts for fan-out-heavy tools (freight searches, fleet matchers):
TOOL_TIMEOUT_SECONDS: int = 30

# ── Undo window (§22 item 4) ────────────────────────────────────────────────

UNDO_WINDOW_MINUTES: int = 30  # Hard cutoff — undo not available after this


def is_undo_expired(started_at: Optional[datetime] = None) -> bool:
    """Check if the undo window has expired for an action.
    
    Args:
        started_at: The time the action was performed (from ExecutionStep.started_at).
    
    Returns:
        True if the undo window has expired (action can no longer be undone).
        False if no timestamp is provided (defaults to allowing undo).
    """
    if started_at is None:
        return False  # No timestamp = can't determine age = allow
    elapsed = datetime.utcnow() - started_at
    return elapsed > timedelta(minutes=UNDO_WINDOW_MINUTES)


# ── Undo enforcement — check before reversing any action (§22) ──────────────
# Tools that call undo() must check is_undo_expired() against the
# original action's started_at timestamp before reversing state.


def _check_tool_permission(tool: Any, role: str) -> bool:
    """Permission gate — is this role allowed to use this tool?

    Blueprint: §15 — Permission System.

    Uses the tool's ``required_permission`` attribute (e.g. ``"trips:read"``)
    and the role→resource table derived from the §8.3 permission matrix
    (``backend/copilot/role_permissions.py``).  Admin can do everything.
    Drivers are limited to read-only access on the resources their role
    permissions grant (help, drivers, routes, tracking, documents, currency,
    trips) — never analytics / clients / payments / fleet.  Dispatchers get
    read/write on operational resources but no delete.  Managers get nearly
    everything except system-scope operations (``system:undo``).

    Intentional operation-level denials layered on top of the resource gate:
    - driver  → read-only (any non-``read`` operation is denied)
    - dispatcher → no ``:delete`` operations
    These mirror §8.1 (``AI_ROLE_PERMISSIONS``) and are preserved exactly.
    """
    if not tool.required_permission:
        return True  # No permission required = accessible to all

    if role == "admin":
        return True  # Admin bypass

    # Extract the resource (e.g. "trips" from "trips:read")
    resource = tool.required_permission.split(":")[0]
    operation = tool.required_permission.split(":")[1] if ":" in tool.required_permission else ""

    allowed_resources = _ROLE_RESOURCE_ACCESS.get(role, set())
    if resource not in allowed_resources:
        return False

    # Further restrict by operation for non-manager roles
    if role == "driver" and operation and operation != "read":
        return False  # Drivers: read-only
    if role == "dispatcher" and operation == "delete":
        return False  # Dispatchers: no delete

    return True


def validate_guardrails(plan: ExecutionPlan) -> List[str]:
    """Check whether a plan exceeds cost/safety ceilings. Returns error i18n keys.
    
    Blueprint: §23.3 — Cost & Runaway-Loop Guardrails.
    
    Enforces:
    - MAX_TOOL_CALLS_PER_PLAN: max steps in a single plan
    - MAX_REASONING_GRAPH_NODES_PER_TURN: max nodes in a single reasoning graph
    - MAX_LLM_TOKENS_PER_TURN: max tokens for LLM processing per turn
    
    §23.3 fidelity: the reasoning-graph ceiling uses the REAL node count the
    planner stamped on the plan (``plan.reasoning_graph_nodes``, recorded after
    ``resolve_reasoning_graph``); callers that construct plans directly fall
    back to the old step-based estimate.  LLM tokens are the real accumulated
    usage (``plan.used_llm_tokens``, fed from provider responses that carry
    token usage — see LLMResponse.input_tokens/output_tokens or a tool result's
    ``data["llm_usage"]``) plus an estimate for steps that report no usage; the
    executor's tool loop receives ToolResult, not LLMResponse, so un-executed
    steps cannot contribute a real count and remain estimated.
    
    When a ceiling is hit, fail gracefully into a clarification question
    rather than silently truncating or looping.
    """
    errors: List[str] = []
    
    if len(plan.steps) > MAX_TOOL_CALLS_PER_PLAN:
        errors.append("copilot.error.too_many_steps")
    
    # Reasoning graph nodes — REAL count when the planner resolved the graph,
    # otherwise estimate from plan steps + entities (direct executor callers).
    if plan.reasoning_graph_nodes is not None:
        node_count = plan.reasoning_graph_nodes
    else:
        node_count = len(plan.steps) * 2 + len(plan.intent.entities)
    if node_count > MAX_REASONING_GRAPH_NODES_PER_TURN:
        errors.append("copilot.error.too_many_graph_nodes")
    
    # LLM tokens — real accumulated usage (if any) + estimate for the rest.
    estimated_tokens = len(plan.intent.raw_utterance) // 2 + len(plan.steps) * 100
    total_tokens = int(getattr(plan, "used_llm_tokens", 0) or 0) + estimated_tokens
    if total_tokens > MAX_LLM_TOKENS_PER_TURN:
        errors.append("copilot.error.too_many_tokens")
    
    return errors


# ── Audit logging helpers (§14) ────────────────────────────────────────────
# Every executed step is written to copilot_audit_log (start + complete).
# The audit functions would otherwise fall back to opening the default
# DatabaseManager when no repo is supplied — a heavy, side-effecting path we
# must not trigger from the execution engine — so audit rows are only written
# when the request-scoped ``services["db"]`` is available.

async def _audit_step_start(
    services: Optional[Dict[str, Any]],
    plan: ExecutionPlan,
    step: ExecutionStep,
) -> None:
    db = (services or {}).get("db")
    if db is None:
        return
    try:
        from backend.copilot.audit import log_step_start
        from repositories.copilot_repository import CopilotAuditRepository

        await log_step_start(
            company_id=(services or {}).get("company_id", 0),
            user_id=(services or {}).get("user_id", 0),
            conversation_id=plan.conversation_id,
            plan_id=plan.plan_id,
            step=step,
            model_used="",
            provider_id="",
            prompt_version="",
            repo=CopilotAuditRepository(db),
        )
    except Exception as exc:
        logger.debug("Audit step start skipped: %s", exc)


async def _audit_step_complete(
    services: Optional[Dict[str, Any]],
    plan: ExecutionPlan,
    step: ExecutionStep,
) -> None:
    db = (services or {}).get("db")
    if db is None:
        return
    try:
        from backend.copilot.audit import log_step_complete
        from repositories.copilot_repository import CopilotAuditRepository

        result = step.result if step.status == "succeeded" else None
        error = step.error if step.status in ("failed", "skipped") else None
        await log_step_complete(
            company_id=(services or {}).get("company_id", 0),
            user_id=(services or {}).get("user_id", 0),
            conversation_id=plan.conversation_id,
            plan_id=plan.plan_id,
            step=step,
            model_used="",
            provider_id="",
            prompt_version="",
            result=result,
            error=error,
            repo=CopilotAuditRepository(db),
        )
    except Exception as exc:
        logger.debug("Audit step complete skipped: %s", exc)


async def _finalize_step(
    services: Optional[Dict[str, Any]],
    plan: ExecutionPlan,
    step: ExecutionStep,
    on_step_update: Optional[Any],
) -> None:
    """Stamp the step's terminal state, notify WS listeners, write audit row."""
    step.finished_at = datetime.utcnow()
    if on_step_update:
        on_step_update(step.step_id, step.status, step.tool_name)
    await _audit_step_complete(services, plan, step)


# ── Plan-level audit events (§14) — pause / resume / stop / cancel ─────────

async def _audit_plan_event(
    services: Optional[Dict[str, Any]],
    plan: ExecutionPlan,
    action: str,
    **extra: Any,
) -> None:
    """Write a plan-level audit row (event-style, no step) — best-effort.

    Same gating as the step audits: only written when a request-scoped DB is
    available, and a failure never breaks the state transition (§14).
    """
    db = (services or {}).get("db")
    if db is None:
        return
    try:
        import json

        from repositories.copilot_repository import CopilotAuditRepository

        new_value: Dict[str, Any] = {
            "plan_id": plan.plan_id,
            "intent": plan.intent.name,
            "paused": getattr(plan, "paused", False),
        }
        new_value.update(extra)
        CopilotAuditRepository(db).log_action(
            conversation_id=plan.conversation_id,
            action=action,
            entity_type="plan",
            entity_id=plan.plan_id,
            new_value=json.dumps(new_value),
            performed_by=str((services or {}).get("user_id", 0)),
        )
    except Exception as exc:
        logger.debug("Plan audit event skipped (%s): %s", action, exc)


def _accumulate_llm_usage(plan: ExecutionPlan, step: ExecutionStep) -> None:
    """Accumulate real LLM token usage reported by a step result (§23.3).

    A provider-backed tool may surface its usage in the result data under
    ``data["llm_usage"] = {"input_tokens": n, "output_tokens": m}``; the
    running total feeds ``validate_guardrails``' token ceiling so plans that
    actually consume LLM tokens cannot blow past MAX_LLM_TOKENS_PER_TURN.
    """
    result = step.result or {}
    data = result.get("data") if isinstance(result, dict) else None
    usage = data.get("llm_usage") if isinstance(data, dict) else None
    if isinstance(usage, dict):
        plan.used_llm_tokens += int(usage.get("input_tokens", 0) or 0)
        plan.used_llm_tokens += int(usage.get("output_tokens", 0) or 0)


# ── §28.1 Retry policies ───────────────────────────────────────────────────
# One retry, transient failures only.  Deterministic failures (validation,
# permission, not-found) are never retried.  Retries respect the circuit
# breaker and guardrails so they can never loop.

class ErrorCategory(str, Enum):
    """§28.1 retry policy categories."""
    TRANSIENT = "transient"
    DETERMINISTIC = "deterministic"


# Transient failure hints — network / timeout / HTTP 5xx / provider-unavailable.
# Deliberately aligned with the §28.1 taxonomy in tests/copilot/test_error_taxonomy.py.
_TRANSIENT_HINTS = (
    "timeout", "timed out", "network", "connection", "unreachable",
    "5 0", "5xx", "status 5", "502", "503", "504",
    "unavailable", "provider", "temporary", "throttl", "rate limit",
    "overload", "internal server error", "service_unavailable",
)


def classify_error(exc_or_message: Any) -> ErrorCategory:
    """Classify an exception or message into the §28.1 retry policy.

    - transient: network / timeout / HTTP 5xx / provider-unavailable
    - deterministic: validation / permission / not-found / everything else

    Fail-safe: anything unknown is deterministic and never retried.
    """
    if isinstance(exc_or_message, BaseException):
        if isinstance(exc_or_message, (asyncio.TimeoutError, TimeoutError, ConnectionError)):
            return ErrorCategory.TRANSIENT
        if isinstance(exc_or_message, (ValueError, PermissionError, KeyError, LookupError)):
            return ErrorCategory.DETERMINISTIC
        # HTTP errors carrying a 5xx status are transient.
        status = getattr(exc_or_message, "status_code", None)
        if status is None:
            response = getattr(exc_or_message, "response", None)
            status = getattr(response, "status_code", None)
        if isinstance(status, int) and 500 <= status < 600:
            return ErrorCategory.TRANSIENT

    text = str(exc_or_message or "").lower()
    for hint in _TRANSIENT_HINTS:
        if hint in text:
            return ErrorCategory.TRANSIENT
    return ErrorCategory.DETERMINISTIC


def is_transient_result(result: Any) -> bool:
    """Whether a ToolResult warrants the single §28.1 retry.

    ``status == "unavailable"`` is provider-unavailable → transient.
    ``status == "failed"`` is classified from the i18n message_key + params.
    """
    if result is None:
        return False
    status = getattr(result, "status", None)
    if status == "unavailable":
        return True
    if status != "failed":
        return False
    text = str(getattr(result, "message_key", "") or "")
    params = getattr(result, "message_params", None) or {}
    for value in params.values():
        text += " " + str(value)
    return classify_error(text) == ErrorCategory.TRANSIENT


def _can_retry(plan: ExecutionPlan, services: Optional[Dict[str, Any]]) -> bool:
    """Retries must respect the circuit breaker and cost guardrails.

    A tripped breaker blocks execution entirely (§23.1) and a plan that fails
    guardrails must not be re-entered — both fail closed so a retry can never
    loop or run away.
    """
    from backend.copilot.circuit_breaker import get_circuit_breaker
    cb = get_circuit_breaker()
    if not cb.is_allowed((services or {}).get("company_id", 0)):
        return False
    if validate_guardrails(plan):
        return False
    return True


async def _attempt_tool_once(
    tool: Any,
    params: Any,
    ctx: Any,
) -> Tuple[Optional[ToolResult], Optional[Exception]]:
    """Run one tool attempt. Returns ``(result, None)`` or ``(None, exc)``.

    A timeout maps to a transient ToolResult (fail-closed degradation, §23.5);
    any other exception is surfaced to the caller so it can be classified
    (transient → retried once, deterministic → failed step).
    """
    try:
        return await asyncio.wait_for(tool.execute(params, ctx), timeout=TOOL_TIMEOUT_SECONDS), None
    except asyncio.TimeoutError:
        return ToolResult(status="failed", message_key="copilot.error.timeout"), None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return None, exc


async def _run_step_with_retry(
    tool: Any,
    params: Any,
    ctx: Any,
    plan: ExecutionPlan,
    services: Optional[Dict[str, Any]],
) -> ToolResult:
    """Execute a tool call with the §28.1 single-retry-on-transient policy.

    Transient failures (timeout / network / 5xx / provider-unavailable) are
    retried exactly once, and only when the circuit breaker is healthy and
    guardrails pass.  Deterministic failures are never retried.  Never raises
    (cancellation excepted): both attempts surface as a failed ToolResult.
    """
    result, exc = await _attempt_tool_once(tool, params, ctx)

    if exc is not None:
        if (
            classify_error(exc) == ErrorCategory.TRANSIENT
            and not plan.paused
            and _can_retry(plan, services)
        ):
            logger.info(
                "Retrying transient step (%s) — attempt 2/2",
                exc,
            )
            result, exc = await _attempt_tool_once(tool, params, ctx)
        if exc is not None:
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )
        if result is None:
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": "tool returned no result"},
            )
        return result

    if (
        is_transient_result(result)
        and not plan.paused
        and _can_retry(plan, services)
    ):
        logger.info(
            "Retrying transient step result (%s) — attempt 2/2",
            getattr(result, "message_key", "?"),
        )
        result, exc = await _attempt_tool_once(tool, params, ctx)
        if exc is not None:
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )
    if result is None:
        return ToolResult(
            status="failed",
            message_key="copilot.error.unexpected",
            message_params={"error": "tool returned no result"},
        )
    return result


# ── §13 Long-running dispatch (Celery) ────────────────────────────────────
# Heavy tools (``long_running = True``) are dispatched to a Celery worker when
# a broker is available; otherwise they run inline (graceful degradation in
# local desktop mode).  Dispatched steps keep status "running" and carry
# ``{task_id, progress_key}`` in their result — progress streams over the WS
# channel and completion fires a NotificationCenter alert (§13).

def _is_celery_broker_available() -> bool:
    """Whether a Celery broker is configured (dispatch eligible)."""
    try:
        from backend.celery_app.celery import celery_app
        broker = celery_app.conf.get("broker_url") or ""
        return bool(broker) and not str(broker).startswith("memory://")
    except Exception:
        return False


def _dispatch_long_running_step(
    tool: Any,
    params: Any,
    ctx: Any,
    plan: ExecutionPlan,
    step: ExecutionStep,
) -> Optional[Dict[str, Any]]:
    """Dispatch one long-running step to the Celery task.

    Returns the step-result payload ``{"task_id", "progress_key", "status",
    "celery_task_id"}`` on success, or ``None`` when the broker is unavailable
    / the send fails — the caller falls back to inline execution.
    """
    try:
        import json
        import uuid

        from backend.celery_app.tasks.copilot_tool_tasks import (
            execute_copilot_tool_step,
            progress_key,
            register_conversation_progress,
        )

        task_id = str(uuid.uuid4())
        celery_result = execute_copilot_tool_step.delay(
            task_id=task_id,
            tool_name=step.tool_name,
            params_json=json.dumps(params.model_dump(mode="json")),
            company_id=ctx.company_id,
            user_id=ctx.user_id,
            role=ctx.role,
            conversation_id=plan.conversation_id,
            plan_id=plan.plan_id,
            step_id=step.step_id,
        )
        key = progress_key(task_id)
        register_conversation_progress(plan.conversation_id, task_id)
        return {
            "task_id": task_id,
            "progress_key": key,
            "status": "dispatched",
            "tool_name": step.tool_name,
            "celery_task_id": str(getattr(celery_result, "id", "") or ""),
        }
    except Exception as exc:
        logger.warning("Celery dispatch failed for %s: %s", step.tool_name, exc)
        return None


async def execute_plan(
    plan: ExecutionPlan,
    services: Optional[Dict[str, Any]] = None,
    on_step_update: Optional[Any] = None,
) -> ExecutionPlan:
    """Execute an ExecutionPlan through the state machine.

    Phase 1: Level 0 tools only — execute immediately without confirmation.

    ``on_step_update`` (if provided) is called as
    ``on_step_update(step_id, status, tool_name)`` after each step status
    change — the API layer uses it to push WebSocket timeline updates (§12.1).
    """
    # Validate guardrails BEFORE execution
    guardrail_errors = validate_guardrails(plan)
    if guardrail_errors:
        for step in plan.steps:
            step.status = "skipped"
            step.error = "; ".join(guardrail_errors)
        logger.warning("Plan %s blocked by guardrails: %s", plan.plan_id, guardrail_errors)
        return plan

    # ── Circuit breaker check (§23.1) ──────────────────────────────────
    from backend.copilot.circuit_breaker import get_circuit_breaker
    cb = get_circuit_breaker()
    cb_company_id = (services or {}).get("company_id", 0)
    if not cb.is_allowed(cb_company_id):
        for step in plan.steps:
            step.status = "skipped"
            step.error = "Circuit breaker tripped — manual confirmation required"
        logger.warning("Plan %s blocked by circuit breaker (company=%d)", plan.plan_id, cb_company_id)
        return plan

    from backend.copilot.tools.registry import get_tool
    from backend.copilot.tools.base import ToolExecutionContext

    services = services or {}

    for step in plan.steps:
        # ── §13 pause — the loop halts between steps; resume continues the rest.
        if plan.paused:
            logger.info("Plan %s paused — halting between steps", plan.plan_id)
            break
        # Resumed / partially-executed plans must never re-run terminal steps.
        if step.status in ("succeeded", "failed", "skipped", "stopped"):
            continue

        logger.info("Executing step %s: %s", step.step_id, step.tool_name)

        tool = get_tool(step.tool_name)
        if tool is None:
            step.status = "failed"
            step.error = f"Tool '{step.tool_name}' not found in registry"
            logger.error("Tool not found: %s", step.tool_name)
            await _finalize_step(services, plan, step, on_step_update)
            continue

        step.status = "running"
        step.started_at = datetime.utcnow()
        if on_step_update:
            on_step_update(step.step_id, "running", step.tool_name)
        await _audit_step_start(services, plan, step)

        try:
            # Build execution context with actual user role (not hardcoded)
            ctx = ToolExecutionContext(
                company_id=(services or {}).get("company_id", 0),
                user_id=(services or {}).get("user_id", 0),
                role=(services or {}).get("role", "dispatcher"),
                session_context=SessionContext(),
                services=services,
            )

            # ── Permission gate (§15) — check before any tool execution ──
            if not _check_tool_permission(tool, ctx.role):
                step.status = "failed"
                step.error = f"Tool '{step.tool_name}' not available for role '{ctx.role}'"
                logger.warning(
                    "Permission denied: tool=%s role=%s user_id=%d",
                    step.tool_name, ctx.role, ctx.user_id,
                )
                await _finalize_step(services, plan, step, on_step_update)
                continue

            # Construct params from step parameters
            params_dict = step.parameters or {}
            params = tool.parameters_schema(**params_dict)

            # Validate
            validation_errors = await tool.validate(params, ctx)
            if validation_errors:
                step.status = "failed"
                step.error = "; ".join(validation_errors)
                await _finalize_step(services, plan, step, on_step_update)
                continue

            # ── §13 long-running dispatch — heavy tools run on Celery ─────
            if getattr(tool, "long_running", False) and _is_celery_broker_available():
                dispatched = _dispatch_long_running_step(tool, params, ctx, plan, step)
                if dispatched is not None:
                    # Step stays "running"; result carries the task handle.
                    step.result = dispatched
                    logger.info(
                        "Dispatched long-running step %s (%s) to Celery task %s",
                        step.step_id, step.tool_name, dispatched["task_id"],
                    )
                    continue
                logger.warning(
                    "Long-running step %s (%s) fell back to inline execution",
                    step.step_id, step.tool_name,
                )

            # Execute (§28.1 — single retry on transient failures only)
            result = await _run_step_with_retry(tool, params, ctx, plan, services)
            step.result = result.model_dump() if result else None
            if result is None:
                step.status = "failed"
                step.error = "Tool returned None"
            elif result.status == "success":
                step.status = "succeeded"
            elif result.status in ("unavailable", "needs_confirmation"):
                step.status = "skipped"
                step.error = result.message_key
            elif result.status == "permission_denied":
                step.status = "failed"
                step.error = result.message_key
            else:
                step.status = "failed"
                step.error = result.message_key
            _accumulate_llm_usage(plan, step)

        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            logger.exception("Step %s failed: %s", step.step_id, exc)

        await _finalize_step(services, plan, step, on_step_update)

    return plan


async def cancel_plan(
    plan: ExecutionPlan,
    services: Optional[Dict[str, Any]] = None,
) -> ExecutionPlan:
    """Cancel an in-flight plan — reachable from any non-terminal state."""
    for step in plan.steps:
        if step.status in ("pending", "running", "paused", "awaiting_confirmation"):
            step.status = "skipped"
            step.finished_at = datetime.utcnow()
    plan.paused = False
    logger.info("Plan %s cancelled", plan.plan_id)
    await _audit_plan_event(services, plan, "plan_cancelled")
    return plan


async def pause_plan(
    plan: ExecutionPlan,
    services: Optional[Dict[str, Any]] = None,
) -> ExecutionPlan:
    """Pause a plan — the execution loop halts between steps (§13).

    Remaining steps stay ``pending`` so a later resume continues from exactly
    where the plan stopped.  A step that was mid-flight is marked ``paused``
    for display; resume flips it back to ``pending`` to re-run it.

    §13 pause support: a plan may only be paused when EVERY non-terminal
    step's tool declares ``supports_pause`` — otherwise the caller refuses the
    pause with ``copilot.plan.cannot_pause`` (409-style error key).
    """
    from backend.copilot.tools.registry import get_tool

    for step in plan.steps:
        if step.status in ("pending", "running"):
            tool = get_tool(step.tool_name)
            if tool is None or not getattr(tool, "supports_pause", False):
                raise ValueError("copilot.plan.cannot_pause")

    plan.paused = True
    for step in plan.steps:
        if step.status == "running":
            step.status = "paused"
    logger.info("Plan %s paused", plan.plan_id)
    await _audit_plan_event(services, plan, "plan_paused")
    return plan


async def resume_plan(
    plan: ExecutionPlan,
    services: Optional[Dict[str, Any]] = None,
) -> ExecutionPlan:
    """Resume a paused plan — the next execution pass continues the rest (§13).

    Clears the paused flag and returns ``paused`` steps to ``pending`` so the
    executor re-runs them.  Does NOT execute steps itself — callers (the
    router) follow up with :func:`execute_plan`.

    §13 resume support: a plan may only be resumed when every remaining step's
    tool declares ``supports_resume`` — otherwise the caller refuses the
    resume with ``copilot.plan.cannot_resume`` (409-style error key).
    """
    from backend.copilot.tools.registry import get_tool

    for step in plan.steps:
        if step.status in ("pending", "running", "paused"):
            tool = get_tool(step.tool_name)
            if tool is None or not getattr(tool, "supports_resume", False):
                raise ValueError("copilot.plan.cannot_resume")

    plan.paused = False
    for step in plan.steps:
        if step.status == "paused":
            step.status = "pending"
    logger.info("Plan %s resumed", plan.plan_id)
    await _audit_plan_event(services, plan, "plan_resumed")
    return plan


async def stop_plan(
    plan: ExecutionPlan,
    services: Optional[Dict[str, Any]] = None,
) -> ExecutionPlan:
    """Stop a plan permanently — remaining steps are marked stopped (§13).

    Mirrors cancel's semantics (nothing further executes) but records the
    terminal ``stopped`` step state so pause/resume can distinguish an
    intentional stop from a cancellation.
    """
    plan.paused = False
    for step in plan.steps:
        if step.status in ("pending", "running", "paused", "awaiting_confirmation"):
            step.status = "stopped"
            step.finished_at = datetime.utcnow()
    logger.info("Plan %s stopped", plan.plan_id)
    await _audit_plan_event(services, plan, "plan_stopped")
    return plan


async def confirm_and_execute(
    plan: ExecutionPlan,
    services: Optional[Dict[str, Any]] = None,
    on_step_update: Optional[Any] = None,
) -> ExecutionPlan:
    """Execute a plan after user confirmation.

    Called by POST /api/v1/copilot/plans/{id}/confirm after the user
    has confirmed a plan that was in AWAITING_CONFIRMATION state.

    Args:
        plan: The confirmed ExecutionPlan to execute.
        services: Service dependencies.
        on_step_update: Optional callback for step status changes.
            Called as on_step_update(step_id, status, tool_name) after each step.
    """
    from backend.copilot.tools.registry import get_tool
    from backend.copilot.tools.base import ToolExecutionContext

    services = services or {}

    # Validate guardrails
    guardrail_errors = validate_guardrails(plan)
    if guardrail_errors:
        for step in plan.steps:
            step.status = "skipped"
            step.error = "; ".join(guardrail_errors)
        return plan

    # ── Circuit breaker check (§23.1) — trip on repeated failures ────
    from backend.copilot.circuit_breaker import get_circuit_breaker
    cb = get_circuit_breaker()
    company_id = services.get("company_id", 0)
    if not cb.is_allowed(company_id):
        logger.warning("Circuit breaker tripped for company %d — blocking execution", company_id)
        for step in plan.steps:
            step.status = "skipped"
            step.error = "Autonomous mode temporarily disabled — manual confirmation required"
        return plan

    for step in plan.steps:
        # ── §13 pause — halts between steps; the router refuses to confirm a
        # paused plan, so this is defense-in-depth against a stale request.
        if plan.paused:
            logger.info("Plan %s paused — halting between steps", plan.plan_id)
            break
        if step.status in ("succeeded", "failed", "skipped", "stopped"):
            continue  # Already processed

        logger.info("Confirm-executing step %s: %s", step.step_id, step.tool_name)

        tool = get_tool(step.tool_name)
        if tool is None:
            step.status = "failed"
            step.error = f"Tool '{step.tool_name}' not found in registry"
            await _finalize_step(services, plan, step, on_step_update)
            continue

        step.status = "running"
        step.started_at = datetime.utcnow()
        if on_step_update:
            on_step_update(step.step_id, "running", step.tool_name)
        await _audit_step_start(services, plan, step)

        try:
            ctx = ToolExecutionContext(
                company_id=services.get("company_id", 0),
                user_id=services.get("user_id", 0),
                role=services.get("role", "dispatcher"),
                session_context=SessionContext(),
                services=services,
            )

            # ── Permission gate (§15) — check before any tool execution ──
            if not _check_tool_permission(tool, ctx.role):
                step.status = "failed"
                step.error = f"Tool '{step.tool_name}' not available for role '{ctx.role}'"
                logger.warning(
                    "Permission denied: tool=%s role=%s user_id=%d",
                    step.tool_name, ctx.role, ctx.user_id,
                )
                await _finalize_step(services, plan, step, on_step_update)
                continue

            params_dict = step.parameters or {}
            params = tool.parameters_schema(**params_dict)

            validation_errors = await tool.validate(params, ctx)
            if validation_errors:
                step.status = "failed"
                step.error = "; ".join(validation_errors)
                await _finalize_step(services, plan, step, on_step_update)
                continue

            # ── §13 long-running dispatch — heavy tools run on Celery ─────
            if getattr(tool, "long_running", False) and _is_celery_broker_available():
                dispatched = _dispatch_long_running_step(tool, params, ctx, plan, step)
                if dispatched is not None:
                    step.result = dispatched
                    logger.info(
                        "Dispatched long-running step %s (%s) to Celery task %s",
                        step.step_id, step.tool_name, dispatched["task_id"],
                    )
                    continue
                logger.warning(
                    "Long-running step %s (%s) fell back to inline execution",
                    step.step_id, step.tool_name,
                )

            result = await _run_step_with_retry(tool, params, ctx, plan, services)
            step.result = result.model_dump() if result else None
            step.status = "succeeded" if result and result.status == "success" else "failed"
            if result and result.status != "success":
                step.error = result.message_key
            _accumulate_llm_usage(plan, step)

        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            logger.exception("Step %s failed: %s", step.step_id, exc)

        await _finalize_step(services, plan, step, on_step_update)

        # ── Circuit breaker feedback (§23.1) ──────────────────────────
        if step.status == "failed":
            cb.record_failure(
                company_id,
                step.tool_name,
                step.error or "unknown",
                db=services.get("db"),
                user_id=services.get("user_id", 0),
                conversation_id=plan.conversation_id,
            )
        elif step.status == "succeeded":
            cb.record_success(company_id, step.tool_name)

    return plan


# ── Graceful Degradation (§23.5) — fail closed, never hang ───────────────

async def execute_with_fallback(
    plan_or_fn: Any,
    fallback_response: Any = None,
    timeout_seconds: int = 30,
) -> Any:
    """Execute a plan or function with timeout and fallback.

    If execution times out or raises an exception, returns the fallback
    rather than hanging or crashing. Used for LLM provider calls and
    external service integrations.

    Blueprint: §23.5 — Graceful Degradation.
    """
    try:
        if asyncio.iscoroutine(plan_or_fn):
            result = await asyncio.wait_for(plan_or_fn, timeout=timeout_seconds)
        elif callable(plan_or_fn):
            result = await asyncio.wait_for(
                asyncio.to_thread(plan_or_fn), timeout=timeout_seconds
            )
        else:
            result = plan_or_fn
        return result
    except asyncio.TimeoutError:
        logger.warning("Execution timed out after %ds — returning fallback", timeout_seconds)
        return fallback_response
    except asyncio.CancelledError:
        logger.warning("Execution was cancelled")
        raise  # Re-raise — cancellation should propagate
    except Exception as exc:
        logger.warning("Execution failed — returning fallback: %s", exc)
        return fallback_response
