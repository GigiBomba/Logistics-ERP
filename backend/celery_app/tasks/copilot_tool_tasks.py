"""Long-running Co-Pilot tool execution tasks (§13).

Heavy tools (batch OCR, multi-provider freight fan-out, bulk export/email)
declare ``long_running = True``; the executor dispatches their step to
:func:`execute_copilot_tool_step` when a Celery broker is available.  The task
writes observable progress to a Redis key ``copilot:tool-progress:{task_id}``
(driving the WS ``type:"progress"`` channel) and fires a completion
notification via AlertManager on termination.

Graceful degradation: when the broker is unavailable the executor runs the
tool inline and this module is never called.  All cache/notification access is
best-effort — a failure never fails the tool result.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from backend.celery_app.celery import celery_app
from backend.config import BackendSettings

logger = logging.getLogger(__name__)

# ── Progress key helpers ────────────────────────────────────────────────────
# Progress payload written to the cache:
#   {task_id, tool_name, step_id, conversation_id, plan_id, percent,
#    message_key, status, result, error, updated_at}

_PROGRESS_TTL_SECONDS = 3600        # keep completed progress readable for a while
_CONVERSATION_KEYS_TTL_SECONDS = 3600


def progress_key(task_id: str) -> str:
    return f"copilot:tool-progress:{task_id}"


def conversation_progress_key(conversation_id: str) -> str:
    return f"copilot:conversation-progress:{conversation_id}"


def _cache() -> Any:
    """Return the shared Redis cache (safe no-op when Redis is down)."""
    from backend.cache import get_cache
    return get_cache()


def write_progress(
    task_id: str,
    percent: int,
    message_key: str,
    status: str,
    *,
    tool_name: str = "",
    step_id: str = "",
    conversation_id: str = "",
    plan_id: str = "",
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """Write the current progress payload for *task_id* (best-effort)."""
    try:
        _cache().set(
            progress_key(task_id),
            {
                "task_id": task_id,
                "tool_name": tool_name,
                "step_id": step_id,
                "conversation_id": conversation_id,
                "plan_id": plan_id,
                "percent": int(percent),
                "message_key": message_key,
                "status": status,
                "result": result,
                "error": error,
                "updated_at": datetime.utcnow().isoformat(),
            },
            ttl=_PROGRESS_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning("Progress write failed for task %s: %s", task_id, exc)


def read_progress(task_id: str) -> Optional[Dict[str, Any]]:
    """Read the latest progress payload for *task_id* (best-effort)."""
    try:
        return _cache().get(progress_key(task_id))
    except Exception as exc:
        logger.warning("Progress read failed for task %s: %s", task_id, exc)
        return None


def register_conversation_progress(conversation_id: str, task_id: str) -> None:
    """Record a task's progress key on the conversation's progress list.

    The WS handler polls this list to know which progress keys to surface for
    a conversation.  Best-effort; entries expire with the list TTL.
    """
    try:
        cache = _cache()
        cache.rpush(conversation_progress_key(conversation_id), progress_key(task_id))
        # Refresh the list TTL after every append so active conversations
        # keep their progress keys discoverable.
        cache.expire(conversation_progress_key(conversation_id), _CONVERSATION_KEYS_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Conversation progress registration failed: %s", exc)


def get_conversation_progress_keys(conversation_id: str) -> list[str]:
    """Return the progress keys recorded for *conversation_id* (best-effort)."""
    try:
        return list(_cache().lrange(conversation_progress_key(conversation_id)))
    except Exception as exc:
        logger.warning("Conversation progress keys read failed: %s", exc)
        return []


# ── Tool execution task ─────────────────────────────────────────────────────

def _fire_completion_notification(db: Any, *, company_id: int, user_id: int,
                                  tool_name: str, status: str,
                                  step_id: str, plan_id: str,
                                  conversation_id: str) -> None:
    """§13 completion notification — best-effort AlertManager alert."""
    try:
        from services.operations.alert_manager import (
            AlertManager,
            AlertType,
            Severity,
        )

        ok = status == "succeeded"
        AlertManager.get_instance(db=db).create_alert(
            alert_type=AlertType.COPILOT_TOOL_COMPLETED,
            severity=Severity.INFO if ok else Severity.WARNING,
            title="Co-Pilot task completed" if ok else "Co-Pilot task failed",
            message=(
                f"Tool {tool_name} finished for plan {plan_id}."
                if ok else f"Tool {tool_name} failed for plan {plan_id}."
            ),
            entity_type="copilot_step",
            entity_id=step_id,
            metadata={
                "source": "copilot.long_running",
                "tool_name": tool_name,
                "plan_id": plan_id,
                "conversation_id": conversation_id,
                "step_id": step_id,
                "company_id": company_id,
                "status": status,
            },
        )
    except Exception as exc:
        logger.warning("Completion notification skipped: %s", exc)


def _write_audit_terminal(db: Any, *, company_id: int, user_id: int,
                          conversation_id: str, plan_id: str, step_id: str,
                          tool_name: str, tool_version: str,
                          parameters: Dict[str, Any], status: str,
                          result: Optional[Dict[str, Any]], error: Optional[str]) -> None:
    """Write the audit-complete row for the dispatched step (§14).

    Keeps copilot_audit_log accurate for long-running steps: the executor
    wrote the ``running`` start row at dispatch; this terminal row (same
    conversation) satisfies the observability panel's abandonment query.
    """
    try:
        from repositories.copilot_repository import CopilotAuditRepository

        CopilotAuditRepository(db).log_step_execution(
            conversation_id=conversation_id,
            plan_id=plan_id,
            step_id=step_id,
            tool_name=tool_name,
            tool_version=tool_version,
            status=status,
            parameters=parameters,
            company_id=company_id,
            user_id=user_id,
            result=result,
            error=error,
            model_used="",
            provider_id="celery",
            prompt_version="",
            started_at=datetime.utcnow().isoformat(),
        )
    except Exception as exc:
        logger.warning("Audit terminal row skipped for step %s: %s", step_id, exc)


async def _run_tool_step(db: Any, *, task_id: str, tool_name: str, params_json: str,
                         company_id: int, user_id: int, role: str,
                         conversation_id: str, plan_id: str, step_id: str) -> Dict[str, Any]:
    """Instantiate + validate + execute one tool step with progress reporting."""
    from backend.copilot.tools.base import ToolExecutionContext
    from backend.copilot.tools.registry import get_tool
    from backend.copilot.schemas import SessionContext

    tool = get_tool(tool_name)
    if tool is None:
        error = f"Tool '{tool_name}' not found in registry"
        write_progress(
            task_id, 100, "copilot.tool.progress.failed", "failed",
            tool_name=tool_name, step_id=step_id,
            conversation_id=conversation_id, plan_id=plan_id, error=error,
        )
        return {"status": "failed", "error": error}

    try:
        params = tool.parameters_schema(**json.loads(params_json or "{}"))
    except Exception as exc:
        return {"status": "failed", "error": f"Invalid parameters: {exc}"}

    ctx = ToolExecutionContext(
        company_id=company_id,
        user_id=user_id,
        role=role,
        session_context=SessionContext(),
        services={
            "db": db,
            "company_id": company_id,
            "user_id": user_id,
            "role": role,
        },
    )

    write_progress(
        task_id, 10, "copilot.tool.progress.validating", "running",
        tool_name=tool_name, step_id=step_id,
        conversation_id=conversation_id, plan_id=plan_id,
    )

    validation_errors = await tool.validate(params, ctx)
    if validation_errors:
        error = "; ".join(validation_errors)
        write_progress(
            task_id, 100, "copilot.tool.progress.failed", "failed",
            tool_name=tool_name, step_id=step_id,
            conversation_id=conversation_id, plan_id=plan_id, error=error,
        )
        return {"status": "failed", "error": error}

    write_progress(
        task_id, 30, "copilot.tool.progress.executing", "running",
        tool_name=tool_name, step_id=step_id,
        conversation_id=conversation_id, plan_id=plan_id,
    )

    try:
        result = await tool.execute(params, ctx)
    except Exception as exc:
        logger.exception("Long-running tool %s raised: %s", tool_name, exc)
        write_progress(
            task_id, 100, "copilot.tool.progress.failed", "failed",
            tool_name=tool_name, step_id=step_id,
            conversation_id=conversation_id, plan_id=plan_id,
            error=str(exc),
        )
        return {"status": "failed", "error": str(exc)}

    if result is None:
        write_progress(
            task_id, 100, "copilot.tool.progress.failed", "failed",
            tool_name=tool_name, step_id=step_id,
            conversation_id=conversation_id, plan_id=plan_id,
            error="Tool returned no result",
        )
        return {"status": "failed", "error": "Tool returned no result"}

    if result.status == "success":
        write_progress(
            task_id, 100, "copilot.tool.progress.succeeded", "succeeded",
            tool_name=tool_name, step_id=step_id,
            conversation_id=conversation_id, plan_id=plan_id,
            result=result.model_dump(),
        )
        return {"status": "succeeded", "result": result.model_dump()}

    # failed / unavailable / permission_denied / needs_confirmation
    write_progress(
        task_id, 100, "copilot.tool.progress.failed", "failed",
        tool_name=tool_name, step_id=step_id,
        conversation_id=conversation_id, plan_id=plan_id,
        result=result.model_dump(),
        error=result.message_key,
    )
    return {"status": "failed", "error": result.message_key, "result": result.model_dump()}


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def execute_copilot_tool_step(
    self,
    task_id: str,
    tool_name: str,
    params_json: str,
    company_id: int = 0,
    user_id: int = 0,
    role: str = "dispatcher",
    conversation_id: str = "",
    plan_id: str = "",
    step_id: str = "",
) -> Dict[str, Any]:
    """Execute one long-running Co-Pilot tool step in a Celery worker.

    Follows the insight-tasks pattern: tenant context set per run, DB opened
    for the step's service dependencies, progress written to the Redis key,
    completion notification fired.  Never raises — always returns a
    ``{"status": ...}`` dict.
    """
    return _execute_step_sync(
        task_id=task_id,
        tool_name=tool_name,
        params_json=params_json,
        company_id=company_id,
        user_id=user_id,
        role=role,
        conversation_id=conversation_id,
        plan_id=plan_id,
        step_id=step_id,
    )


def _execute_step_sync(
    *,
    task_id: str,
    tool_name: str,
    params_json: str,
    company_id: int = 0,
    user_id: int = 0,
    role: str = "dispatcher",
    conversation_id: str = "",
    plan_id: str = "",
    step_id: str = "",
) -> Dict[str, Any]:
    """Sync wrapper around :func:`_run_tool_step` (task body, testable directly)."""
    from backend.db import DatabaseManager
    from database.tenant_context import set_company_context

    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        set_company_context(company_id)
        outcome = asyncio.run(_run_tool_step(
            db,
            task_id=task_id,
            tool_name=tool_name,
            params_json=params_json,
            company_id=company_id,
            user_id=user_id,
            role=role,
            conversation_id=conversation_id,
            plan_id=plan_id,
            step_id=step_id,
        ))

        _write_audit_terminal(
            db,
            company_id=company_id,
            user_id=user_id,
            conversation_id=conversation_id,
            plan_id=plan_id,
            step_id=step_id,
            tool_name=tool_name,
            tool_version="",
            parameters=json.loads(params_json or "{}"),
            status="succeeded" if outcome.get("status") == "succeeded" else "failed",
            result=outcome.get("result"),
            error=outcome.get("error"),
        )

        _fire_completion_notification(
            db,
            company_id=company_id,
            user_id=user_id,
            tool_name=tool_name,
            status=outcome.get("status", "failed"),
            step_id=step_id,
            plan_id=plan_id,
            conversation_id=conversation_id,
        )
        return outcome
    except Exception as exc:
        logger.exception("execute_copilot_tool_step crashed: %s", exc)
        write_progress(
            task_id, 100, "copilot.tool.progress.failed", "failed",
            tool_name=tool_name, step_id=step_id,
            conversation_id=conversation_id, plan_id=plan_id,
            error=str(exc),
        )
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()