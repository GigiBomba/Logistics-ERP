"""Audit Logger — append-only, immutable record of every Co-Pilot action.

Blueprint: §14 — Audit Logging.
Phase 1: Writing to copilot_audit_log table (columns per Alembic migration
          d4e5f6a7b8c4_create_copilot_audit_log.py).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from backend.copilot.schemas import ExecutionStep
from repositories.copilot_repository import CopilotAuditRepository

logger = logging.getLogger(__name__)


# ── Database helpers ─────────────────────────────────────────────────────


def _get_repo(repo: Optional[CopilotAuditRepository] = None) -> Optional[CopilotAuditRepository]:
    """Get a CopilotAuditRepository instance.

    Returns the provided *repo* or creates one with a database connection.
    Returns None if no database is available (acceptable for audit —
    logs to app logger only).
    """
    if repo is not None:
        return repo
    try:
        from backend.config import BackendSettings
        from database.db_manager import DatabaseManager

        config = BackendSettings()
        db = DatabaseManager(config.db_path)
        return CopilotAuditRepository(db)
    except Exception as exc:
        logger.debug("Audit database unavailable (logging to app logger only): %s", exc)
        return None


# ── Public API ────────────────────────────────────────────────────────────


async def log_step_start(
    company_id: int,
    user_id: int,
    conversation_id: str,
    plan_id: str,
    step: ExecutionStep,
    model_used: str,
    provider_id: str,
    prompt_version: str,
    repo: Optional[CopilotAuditRepository] = None,
) -> None:
    """Log the start of a tool execution step.

    Writes to both app logger and copilot_audit_log table.
    """
    now = datetime.utcnow().isoformat()
    logger.info(
        "AUDIT START | company=%d user=%d conv=%s plan=%s step=%s tool=%s v%s level=%d",
        company_id, user_id, conversation_id, plan_id,
        step.step_id, step.tool_name, step.tool_version, step.confirmation_level,
    )

    # Write to database via repository
    # DDL moved to Alembic migration d4e5f6a7b8c4
    r = _get_repo(repo)
    if r is not None:
        try:
            r.log_action(
                conversation_id=conversation_id,
                action="tool_execution_start",
                entity_type="step",
                entity_id=step.step_id,
                new_value=json.dumps({
                    "company_id": company_id,
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "tool_name": step.tool_name,
                    "tool_version": step.tool_version,
                    "parameters": step.parameters,
                    "confirmation_level": step.confirmation_level,
                    "model_used": model_used,
                    "provider_id": provider_id,
                    "prompt_version": prompt_version,
                    "started_at": step.started_at.isoformat() if step.started_at else now,
                }),
                performed_by=str(user_id),
            )
        except Exception as exc:
            logger.warning("Failed to log audit step start: %s", exc)


async def log_step_complete(
    company_id: int,
    user_id: int,
    conversation_id: str,
    plan_id: str,
    step: ExecutionStep,
    model_used: str,
    provider_id: str,
    prompt_version: str,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    repo: Optional[CopilotAuditRepository] = None,
) -> None:
    """Log the completion of a tool execution step.

    Writes to both app logger and copilot_audit_log table.
    """
    status = "succeeded" if not error else "failed"
    now = datetime.utcnow().isoformat()
    logger.info(
        "AUDIT END   | company=%d user=%d conv=%s plan=%s step=%s tool=%s status=%s "
        "model=%s provider=%s prompt_ver=%s",
        company_id, user_id, conversation_id, plan_id,
        step.step_id, step.tool_name, status,
        model_used, provider_id, prompt_version,
    )
    if error:
        logger.error("AUDIT ERROR | step=%s error=%s", step.step_id, error)

    # Calculate execution time if we have started_at
    execution_time_ms = None
    started_at = step.started_at.isoformat() if step.started_at else now
    if step.started_at:
        delta = datetime.utcnow() - step.started_at
        execution_time_ms = int(delta.total_seconds() * 1000)

    # Write to database via repository
    # DDL moved to Alembic migration d4e5f6a7b8c4
    r = _get_repo(repo)
    if r is not None:
        try:
            r.log_action(
                conversation_id=conversation_id,
                action=f"tool_execution_{status}",
                entity_type="step",
                entity_id=step.step_id,
                new_value=json.dumps({
                    "company_id": company_id,
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "tool_name": step.tool_name,
                    "tool_version": step.tool_version,
                    "parameters": step.parameters,
                    "confirmation_level": step.confirmation_level,
                    "model_used": model_used,
                    "provider_id": provider_id,
                    "prompt_version": prompt_version,
                    "status": status,
                    "result": result,
                    "error": error,
                    "execution_time_ms": execution_time_ms,
                    "started_at": started_at,
                    "finished_at": now,
                }),
                performed_by=str(user_id),
            )
        except Exception as exc:
            logger.warning("Failed to log audit step complete: %s", exc)
