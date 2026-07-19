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
from typing import Any, Dict, List, Optional

from backend.copilot.schemas import (
    ConfirmationLevel,
    ExecutionPlan,
    ExecutionStep,
    SessionContext,
    ToolResult,
)

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
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
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
    and a simple role-based access table.  Admin can do everything.  Drivers
    are limited to read-only access on trips, fleet, tracking and routes.
    Dispatchers get read/write on operational resources but no delete.
    Managers get nearly everything except system-level operations.
    """
    if not tool.required_permission:
        return True  # No permission required = accessible to all

    if role == "admin":
        return True  # Admin bypass

    # Extract the resource (e.g. "trips" from "trips:read")
    resource = tool.required_permission.split(":")[0]
    operation = tool.required_permission.split(":")[1] if ":" in tool.required_permission else ""

    # Role → allowed resource prefixes
    role_access: dict[str, set[str]] = {
        "manager": {
            "trips", "fleet", "drivers", "dispatch", "clients",
            "invoices", "documents", "routes", "tracking",
            "export", "payments", "automail", "email",
            "analytics", "currency", "freight", "help",
            "maintenance", "proforma", "receipts", "tacho", "system",
        },
        "dispatcher": {
            "trips", "fleet", "drivers", "dispatch", "clients",
            "documents", "routes", "tracking", "currency",
            "freight", "help", "receipts",
        },
        "driver": {
            "trips", "fleet", "tracking", "routes", "help",
        },
    }

    allowed_resources = role_access.get(role, set())
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
    
    When a ceiling is hit, fail gracefully into a clarification question
    rather than silently truncating or looping.
    """
    errors: List[str] = []
    
    if len(plan.steps) > MAX_TOOL_CALLS_PER_PLAN:
        errors.append("copilot.error.too_many_steps")
    
    # Estimate reasoning graph nodes from plan steps + entities
    estimated_nodes = len(plan.steps) * 2 + len(plan.intent.entities)
    if estimated_nodes > MAX_REASONING_GRAPH_NODES_PER_TURN:
        errors.append("copilot.error.too_many_graph_nodes")
    
    # Estimate LLM tokens from utterance length + step count
    estimated_tokens = len(plan.intent.raw_utterance) // 2 + len(plan.steps) * 100
    if estimated_tokens > MAX_LLM_TOKENS_PER_TURN:
        errors.append("copilot.error.too_many_tokens")
    
    return errors


async def execute_plan(
    plan: ExecutionPlan,
    services: Optional[Dict[str, Any]] = None,
) -> ExecutionPlan:
    """Execute an ExecutionPlan through the state machine.

    Phase 1: Level 0 tools only — execute immediately without confirmation.
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
        logger.info("Executing step %s: %s", step.step_id, step.tool_name)

        tool = get_tool(step.tool_name)
        if tool is None:
            step.status = "failed"
            step.error = f"Tool '{step.tool_name}' not found in registry"
            logger.error("Tool not found: %s", step.tool_name)
            continue

        step.status = "running"
        step.started_at = datetime.utcnow()

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
                step.finished_at = datetime.utcnow()
                logger.warning(
                    "Permission denied: tool=%s role=%s user_id=%d",
                    step.tool_name, ctx.role, ctx.user_id,
                )
                continue

            # Construct params from step parameters
            params_dict = step.parameters or {}
            params = tool.parameters_schema(**params_dict)

            # Validate
            validation_errors = await tool.validate(params, ctx)
            if validation_errors:
                step.status = "failed"
                step.error = "; ".join(validation_errors)
                step.finished_at = datetime.utcnow()
                continue

            # Execute
            result = await tool.execute(params, ctx)
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

        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            logger.exception("Step %s failed: %s", step.step_id, exc)

        step.finished_at = datetime.utcnow()

    return plan


async def cancel_plan(plan: ExecutionPlan) -> ExecutionPlan:
    """Cancel an in-flight plan — reachable from any non-terminal state."""
    for step in plan.steps:
        if step.status in ("pending", "running", "awaiting_confirmation"):
            step.status = "skipped"
            step.finished_at = datetime.utcnow()
    logger.info("Plan %s cancelled", plan.plan_id)
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
        if step.status in ("succeeded", "failed", "skipped"):
            continue  # Already processed

        logger.info("Confirm-executing step %s: %s", step.step_id, step.tool_name)

        tool = get_tool(step.tool_name)
        if tool is None:
            step.status = "failed"
            step.error = f"Tool '{step.tool_name}' not found in registry"
            if on_step_update:
                on_step_update(step.step_id, "failed", step.tool_name)
            continue

        step.status = "running"
        step.started_at = datetime.utcnow()
        if on_step_update:
            on_step_update(step.step_id, "running", step.tool_name)

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
                step.finished_at = datetime.utcnow()
                logger.warning(
                    "Permission denied: tool=%s role=%s user_id=%d",
                    step.tool_name, ctx.role, ctx.user_id,
                )
                if on_step_update:
                    on_step_update(step.step_id, "failed", step.tool_name)
                continue

            params_dict = step.parameters or {}
            params = tool.parameters_schema(**params_dict)

            validation_errors = await tool.validate(params, ctx)
            if validation_errors:
                step.status = "failed"
                step.error = "; ".join(validation_errors)
                step.finished_at = datetime.utcnow()
                if on_step_update:
                    on_step_update(step.step_id, "failed", step.tool_name)
                continue

            result = await execute_with_fallback(
                tool.execute(params, ctx),
                fallback_response=ToolResult(
                    status="failed",
                    message_key="copilot.error.timeout",
                ),
                timeout_seconds=TOOL_TIMEOUT_SECONDS,
            )
            step.result = result.model_dump() if result else None
            step.status = "succeeded" if result and result.status == "success" else "failed"
            if result and result.status != "success":
                step.error = result.message_key

        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            logger.exception("Step %s failed: %s", step.step_id, exc)

        step.finished_at = datetime.utcnow()
        if on_step_update:
            on_step_update(step.step_id, step.status, step.tool_name)

        # ── Circuit breaker feedback (§23.1) ──────────────────────────
        if step.status == "failed":
            cb.record_failure(company_id, step.tool_name, step.error or "unknown")
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
