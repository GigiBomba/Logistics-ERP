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


# ── Worker retry policy ─────────────────────────────────────────────────────
# Retrying ``execute_copilot_tool_step`` re-runs the WHOLE dispatched step, so
# it is only safe when the tool being executed is idempotent: re-executing it
# cannot double-apply a side effect (double-send / double-publish /
# double-create).  NOTE: the audit terminal row written by
# :func:`_write_audit_terminal` is purely observational — no pre-run check
# consults ``copilot_audit_log`` to gate re-execution — so audit rows do NOT
# make a non-idempotent tool safe to retry.
#
# Idempotency verdict per ``long_running`` tool the executor can dispatch to
# this task (tests/copilot/test_executor.py keeps this tool list in sync):
#
#   freight.search_loads       → READ-ONLY multi-provider search; no DB /
#                                external writes.  Retry side-effect-free.
#                                RETRYABLE.
#   freight.find_best_trucks   → READ-ONLY fleet scoring; no writes.
#                                RETRYABLE.
#   document.ocr_import        → uploads the file and INSERTs a new documents
#                                row; no dedup / unique guard → a re-run after
#                                partial work duplicates the document.
#                                NOT retried.
#   email.send_bulk            → sends up to 100 external emails; no dedup
#                                guard → a re-run after partial sends
#                                double-sends.  NOT retried.
#   export.generate_pdf_report / export.generate_excel
#                               → write a new report artifact per run (NOT
#                                job-table-backed like
#                                export_tasks.export_trips_job, which is safe
#                                to retry); no guard → a re-run leaves a
#                                duplicate artifact.  NOT retried.
#
# freight.publish_to_exchange / freight.negotiate_offer are NOT long_running —
# the executor never dispatches them to this task (they run inline under the
# §28.1 single-retry policy in the executor instead).
_RETRY_SAFE_IDEMPOTENT_TOOLS: frozenset[str] = frozenset({
    "freight.search_loads",      # read-only §17 provider search
    "freight.find_best_trucks",  # read-only §17 fleet scoring
})


class _TransientStepFailure(Exception):
    """A retry-eligible tool hit a transient failure on a worker attempt.

    Raised from :func:`_execute_step_sync` BEFORE any audit terminal row is
    written so a retry never leaves a ``failed`` terminal row behind a later
    ``succeeded`` one.  Only raised for tools in
    :data:`_RETRY_SAFE_IDEMPOTENT_TOOLS` and only when the retry is enabled on
    a real worker (eager / direct calls keep the historical no-retry path).
    """

    def __init__(self, *, tool_name: str, step_id: str, message: str) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.step_id = step_id
        self.message = message


def _is_transient(exc_or_message: Any) -> bool:
    """§28.1 transient taxonomy for retry decisions (mirrors the executor)."""
    from backend.copilot.executor import ErrorCategory, classify_error
    return classify_error(exc_or_message) == ErrorCategory.TRANSIENT


def _outcome_is_transient(outcome: Dict[str, Any]) -> bool:
    """Whether a step outcome signals a §28.1-transient tool failure.

    Mirrors ``executor.is_transient_result`` over the sync outcome envelope
    produced by :func:`_run_tool_step` (failed status + ToolResult message_key
    / message_params carry the raw provider error text).
    """
    if outcome.get("status") != "failed":
        return False
    result = outcome.get("result")
    result_status = result.get("status") if isinstance(result, dict) else None
    if result_status == "unavailable":
        return True  # provider/service unavailable → transient (§28.1)
    text = str(outcome.get("error") or "")
    if isinstance(result, dict):
        text += " " + str(result.get("message_key") or "")
        text += " " + " ".join(
            str(v) for v in (result.get("message_params") or {}).values()
        )
    return _is_transient(text)


def _retry_allowed(self, tool_name: str) -> bool:
    """Whether THIS worker attempt may auto-retry *tool_name*.

    Auto-retry re-runs the entire dispatched step, so it is limited to tools
    with a verified idempotent profile (see
    :data:`_RETRY_SAFE_IDEMPOTENT_TOOLS`) AND to real worker executions —
    eager / direct invocations (``task_always_eager``, tests, direct calls)
    keep the historical no-retry behaviour so no caller ever sees a retry
    raise.
    """
    if tool_name not in _RETRY_SAFE_IDEMPOTENT_TOOLS:
        return False
    if self.request.is_eager or self.request.called_directly:
        return False
    return self.request.retries < self.max_retries


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
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
    completion notification fired.

    Retry policy: transient failures are retried with exponential backoff
    (30s, 60s, 120s — ``default_retry_delay * 2**retries``) ONLY for tools in
    :data:`_RETRY_SAFE_IDEMPOTENT_TOOLS` (see the allowlist for per-tool
    idempotency verdicts).  Tools without a verified idempotency guard — bulk
    email, OCR import, report export — are never retried: a re-run after
    partial work could double-send / double-publish / double-create.  Eager /
    direct invocations (tests, ``task_always_eager``) keep the historical
    no-retry behaviour, so in that context this never raises — it always
    returns a ``{"status": ...}`` dict.
    """
    retryable = _retry_allowed(self, tool_name)
    try:
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
            retry_on_transient=retryable,
        )
    except _TransientStepFailure as transient:
        # Transient failure of an idempotent tool — safe to re-run the whole
        # step; no audit terminal row has been written for this attempt.
        logger.warning(
            "Retrying idempotent tool %s step %s (task %s) — attempt %d/%d: %s",
            tool_name, step_id, task_id,
            self.request.retries + 1, self.max_retries, transient.message,
        )
        raise self.retry(
            exc=RuntimeError(transient.message),
            countdown=self.default_retry_delay * (2 ** self.request.retries),
        )
    except Exception as exc:
        logger.exception("execute_copilot_tool_step crashed: %s", exc)
        # Worker retry with exponential backoff (30s, 60s, 120s).  Eager /
        # direct invocations (tests, task_always_eager) keep the historical
        # mark-failed-and-return behavior so no caller sees a retry raise.
        # Retries are gated to tools in _RETRY_SAFE_IDEMPOTENT_TOOLS: a retry
        # of a non-idempotent tool after partial work could double-send /
        # double-publish (email.send_bulk, document.ocr_import,
        # export.generate_*), so those never re-queue.
        if retryable and _is_transient(exc):
            raise self.retry(
                exc=exc,
                countdown=self.default_retry_delay * (2 ** self.request.retries),
            )
        write_progress(
            task_id, 100, "copilot.tool.progress.failed", "failed",
            tool_name=tool_name, step_id=step_id,
            conversation_id=conversation_id, plan_id=plan_id,
            error=str(exc),
        )
        return {"status": "failed", "error": str(exc)}


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
    retry_on_transient: bool = False,
) -> Dict[str, Any]:
    """Sync wrapper around :func:`_run_tool_step` (task body, testable directly).

    When *retry_on_transient* is set (a real worker executing a tool in
    :data:`_RETRY_SAFE_IDEMPOTENT_TOOLS` with retry budget left), a transient
    failure raises :class:`_TransientStepFailure` — before any audit terminal
    row is written — so the task can re-queue via ``self.retry``.  Otherwise
    every failure is converted to a ``{"status": "failed", ...}`` outcome
    exactly as before (never raises).
    """
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

        if (
            retry_on_transient
            and outcome.get("status") == "failed"
            and _outcome_is_transient(outcome)
        ):
            raise _TransientStepFailure(
                tool_name=tool_name,
                step_id=step_id,
                message=outcome.get("error") or "transient tool failure",
            )

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
    except _TransientStepFailure:
        raise  # worker retry marker — no audit row written for this attempt
    except Exception as exc:
        logger.exception("execute_copilot_tool_step crashed: %s", exc)
        # A transient infra failure on a retry-eligible worker attempt is
        # surfaced (no audit terminal row written yet) so the task can re-queue;
        # any other failure degrades to the historical failed outcome.
        if retry_on_transient and _is_transient(exc):
            raise
        write_progress(
            task_id, 100, "copilot.tool.progress.failed", "failed",
            tool_name=tool_name, step_id=step_id,
            conversation_id=conversation_id, plan_id=plan_id,
            error=str(exc),
        )
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()