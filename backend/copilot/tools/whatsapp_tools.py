"""WhatsApp automation tool — §21 Phase 4 item 3.

The Co-Pilot never understands WhatsApp individually (§17 precedent) — it only
orchestrates the deterministic provider methods through the provider-agnostic
``backend.copilot.channels.whatsapp`` registry.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)

# E.164-ish: optional leading +, 7-15 digits.
_PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


class SendMessageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient: str = Field(..., min_length=7, max_length=16, description="Recipient WhatsApp phone number (E.164, e.g. +40712345678)")
    body: str = Field(..., min_length=1, max_length=1600, description="Message body (plain text)")
    confirmation_phrase: str = Field(
        ..., min_length=1, description="Type CONFIRM to authorize sending the message"
    )


@register_tool
class WhatsAppSendMessageTool(BaseTool):
    """Send a WhatsApp message to a single recipient.

    Level 3 (DESTRUCTIVE) because it is an immediate external communication
    that cannot be recalled once sent — mirrors ``email.send_bulk``'s
    discipline (automail_tools.py).  Single-shot: not pausable/resumable and
    not long-running (bulk fan-out is a separate future tool).
    """
    name = "whatsapp.send_message"
    tool_version = "1.0.0"
    description = "Send a WhatsApp message to a recipient phone number"
    required_permission = "whatsapp:send"
    confirmation_level = ConfirmationLevel.DESTRUCTIVE
    supports_undo = False
    supports_pause = False
    supports_resume = False
    long_running = False
    parameters_schema = SendMessageParams

    async def validate(self, params: SendMessageParams, ctx: ToolExecutionContext) -> List[str]:
        errors: List[str] = []
        if not _PHONE_RE.match(params.recipient):
            errors.append(f"Invalid phone number: {params.recipient}")
        if not params.body.strip():
            errors.append("Message body is required")
        if params.confirmation_phrase.strip().upper() != "CONFIRM":
            errors.append("Type CONFIRM to authorize sending the message")
        return errors

    async def execute(self, params: SendMessageParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            # ── Resolve the provider-agnostic channel ────────────────────
            from backend.copilot.channels.whatsapp.registry import get_whatsapp_provider

            provider = get_whatsapp_provider()
            if provider is None or not provider.available:
                # Graceful i18n error — never a crash.
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.whatsapp.error.not_configured",
                )

            # ── Sanitize the message body (established sanitizer discipline) ──
            from backend.middleware.input_sanitizer import sanitize_free_text

            body = sanitize_free_text(params.body, max_length=1600)

            sent = await provider.send_text(params.recipient, body)
            logger.info(
                "whatsapp.send_message sent to %s (company=%d user=%d)",
                params.recipient, ctx.company_id, ctx.user_id,
            )
            return ToolResult(
                status="success",
                data={
                    "recipient": params.recipient,
                    "status": "sent",
                    "provider_id": provider.provider_id,
                    "provider_message_id": (sent or {}).get("messages", [{}])[0].get("id", "") if sent else "",
                },
                message_key="copilot.tool.whatsapp.send_ok",
                message_params={"recipient": params.recipient},
            )

        except Exception as exc:
            logger.warning("whatsapp.send_message failed for %s: %s", params.recipient, exc)
            return ToolResult(
                status="failed",
                data={"recipient": params.recipient, "status": "failed"},
                message_key="copilot.tool.whatsapp.send_failed",
                message_params={"recipient": params.recipient},
            )