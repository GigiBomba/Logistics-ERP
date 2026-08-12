"""Audit Logger — append-only, immutable record of every Co-Pilot action.

Blueprint: §14 — Audit Logging.

PHASE 0: Logging stub. Phase 1+ will write to copilot_audit_log table.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from backend.copilot.schemas import ExecutionStep

logger = logging.getLogger(__name__)


async def log_step_start(
    company_id: int,
    user_id: int,
    conversation_id: str,
    plan_id: str,
    step: ExecutionStep,
    model_used: str,
    provider_id: str,
    prompt_version: str,
) -> None:
    """Log the start of a tool execution step.

    PHASE 0 STUB — logs to app logger only. Phase 1 will insert into copilot_audit_log.
    """
    logger.info(
        "AUDIT START | company=%d user=%d conv=%s plan=%s step=%s tool=%s v%s level=%d",
        company_id, user_id, conversation_id, plan_id,
        step.step_id, step.tool_name, step.tool_version, step.confirmation_level,
    )


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
) -> None:
    """Log the completion of a tool execution step.

    PHASE 0 STUB — logs to app logger only. Phase 1 will insert into copilot_audit_log.
    """
    status = "succeeded" if not error else "failed"
    logger.info(
        "AUDIT END   | company=%d user=%d conv=%s plan=%s step=%s tool=%s status=%s "
        "model=%s provider=%s prompt_ver=%s",
        company_id, user_id, conversation_id, plan_id,
        step.step_id, step.tool_name, status,
        model_used, provider_id, prompt_version,
    )
    if error:
        logger.error("AUDIT ERROR | step=%s error=%s", step.step_id, error)
