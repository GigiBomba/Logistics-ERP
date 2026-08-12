"""AutoMail tools — Level 2 Co-Pilot tools for email automation.

Blueprint: §9.1 — AutoMail.

NOTE: The underlying automail service (DunnerEngine) has no schedule()
method. These tools return "unavailable" until automail scheduling is
implemented in the service layer.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.copilot.schemas import ConfirmationLevel, ToolResult
from backend.copilot.tools.base import BaseTool, ToolExecutionContext
from backend.copilot.tools.registry import register_tool

logger = logging.getLogger(__name__)


class ScheduleReminderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: int = Field(..., gt=0, description="Invoice to send reminder for")
    reminder_type: str = Field(default="overdue", description="Reminder type: overdue, due_soon")
    template: str = Field(default="standard", description="Email template to use")
    send_immediately: bool = Field(default=False, description="Send the reminder email immediately instead of scheduling for later")


@register_tool
class ScheduleReminderTool(BaseTool):
    """Schedule an automated email reminder for an invoice.

    Creates a schedule record via ``AutoMailRepository.create_schedule()``.
    When *send_immediately* is ``True`` the reminder is sent right away
    using ``NotificationCenter.send_email()``.
    """
    name = "automail.schedule_reminder"
    tool_version = "1.0.0"
    description = "Schedule an automated email reminder for an overdue or due-soon invoice"
    required_permission = "automail:write"
    confirmation_level = ConfirmationLevel.BUSINESS  # Level 2 — schedules external communication
    supports_undo = False
    parameters_schema = ScheduleReminderParams

    async def validate(self, params: ScheduleReminderParams, ctx: ToolExecutionContext) -> List[str]:
        valid_types = ("overdue", "due_soon")
        if params.reminder_type not in valid_types:
            return [f"Invalid reminder type: {params.reminder_type}. Must be: {', '.join(valid_types)}"]
        return []

    async def execute(self, params: ScheduleReminderParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(
                    status="unavailable",
                    message_key="copilot.error.no_db",
                    message_params={"tool": self.name},
                )

            from repositories.automail_repository import AutoMailRepository

            repo = AutoMailRepository(db)

            # ── Resolve template ──────────────────────────────────────
            template_id: Optional[int] = None
            all_templates = repo.get_all_templates()
            for t in all_templates:
                if t.get("name", "").lower() == params.template.lower():
                    template_id = t["id"]
                    break

            # ── Create schedule record ────────────────────────────────
            schedule_data: dict[str, Any] = {
                "name": f"Reminder Invoice #{params.invoice_id} ({params.reminder_type})",
                "trigger_type": params.reminder_type,
                "days_offset": 0,
                "is_active": True,
                "sort_order": 0,
            }
            if template_id is not None:
                schedule_data["template_id"] = template_id

            schedule_id = repo.create_schedule(schedule_data)

            # ── Immediate send ────────────────────────────────────────
            sent_immediately = False
            if params.send_immediately:
                try:
                    from services.operations.notification_center import NotificationCenter

                    nc = NotificationCenter()

                    # Try to resolve recipient email from invoice/client
                    recipient_email = ""
                    try:
                        from repositories.invoice_repository import InvoiceRepository
                        from repositories.client_repository import ClientRepository

                        inv_repo = InvoiceRepository(db)
                        invoice = inv_repo.get_by_id(params.invoice_id)
                        if invoice:
                            client_id = invoice.get("client_id")
                            if client_id:
                                client_repo = ClientRepository(db)
                                client = client_repo.get_by_id(int(client_id))
                                if client:
                                    recipient_email = client.get("email", "")
                    except Exception:
                        logger.debug("Could not resolve recipient email for invoice %s", params.invoice_id)

                    if recipient_email:
                        subject = f"{params.reminder_type.title()} Reminder — Invoice #{params.invoice_id}"
                        body = (
                            f"This is a {params.reminder_type} reminder for "
                            f"invoice #{params.invoice_id}.\n\n"
                            f"Please process the payment at your earliest convenience."
                        )
                        success = nc.send_email(
                            to_address=recipient_email,
                            subject=subject,
                            body=body,
                            trip_id=params.invoice_id,
                        )
                        sent_immediately = success
                        if success:
                            repo.log_manual_send(
                                invoice_id=params.invoice_id,
                                trip_id=0,
                                recipient=recipient_email,
                            )
                except Exception as send_exc:
                    logger.warning("Immediate send failed for invoice %s: %s", params.invoice_id, send_exc)

            return ToolResult(
                status="success",
                data={
                    "schedule_id": schedule_id,
                    "invoice_id": params.invoice_id,
                    "reminder_type": params.reminder_type,
                    "sent_immediately": sent_immediately,
                },
                message_key="copilot.automail.schedule_created",
                message_params={
                    "schedule_id": str(schedule_id),
                    "invoice_id": str(params.invoice_id),
                },
            )

        except Exception as exc:
            logger.exception("automail.schedule_reminder failed")
            return ToolResult(
                status="failed",
                message_key="copilot.error.unexpected",
                message_params={"error": str(exc)},
            )


class SendNowParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: int = Field(..., gt=0, description="Invoice to send reminder for")
    recipient_email: str = Field(..., description="Recipient email address")
    subject: str = Field(default="", description="Email subject override")
    body: str = Field(default="", description="Email body override (plain text)")


@register_tool
class SendNowTool(BaseTool):
    """Send an immediate email reminder for an invoice.

    Level 3 (DESTRUCTIVE) because it's an immediate external communication
    that cannot be recalled once sent.
    """
    name = "automail.send_now"
    tool_version = "1.0.0"
    description = "Send an immediate email reminder"
    required_permission = "automail:send"
    confirmation_level = ConfirmationLevel.DESTRUCTIVE
    supports_undo = False
    parameters_schema = SendNowParams

    async def validate(self, params: SendNowParams, ctx: ToolExecutionContext) -> List[str]:
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", params.recipient_email):
            return ["Invalid email address format"]
        return []

    async def execute(self, params: SendNowParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            db = ctx.services.get("db")
            if db is None:
                return ToolResult(status="unavailable", message_key="copilot.error.no_db")

            from services.operations.notification_center import NotificationCenter
            nc = NotificationCenter()

            subject = params.subject or f"Reminder: Invoice #{params.invoice_id}"
            body = params.body or f"Please process invoice #{params.invoice_id}."

            success = nc.send_email(
                to_address=params.recipient_email,
                subject=subject,
                body=body,
                trip_id=params.invoice_id,
            )

            if success:
                return ToolResult(
                    status="success",
                    message_key="copilot.automail.sent",
                    message_params={"recipient": params.recipient_email},
                )
            return ToolResult(status="failed", message_key="copilot.automail.send_failed")
        except Exception as e:
            return ToolResult(status="failed", message_key="copilot.error.unexpected", message_params={"error": str(e)})


class SendBulkParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipients: List[str] = Field(..., min_length=1, max_length=100, description="List of recipient email addresses")
    subject: str = Field(..., min_length=1, description="Email subject")
    body: str = Field(..., min_length=1, description="Email body (HTML supported)")
    trip_id: Optional[int] = Field(None, description="Optional trip ID to associate")


@register_tool
class SendBulkTool(BaseTool):
    """Send a bulk email to multiple recipients.

    Level 3 (DESTRUCTIVE) because bulk external communication
    has high blast radius and cannot be recalled.
    """
    name = "email.send_bulk"
    tool_version = "1.0.0"
    description = "Send bulk email to multiple recipients"
    required_permission = "email:send_bulk"
    confirmation_level = ConfirmationLevel.DESTRUCTIVE
    supports_undo = False
    parameters_schema = SendBulkParams

    async def validate(self, params: SendBulkParams, ctx: ToolExecutionContext) -> List[str]:
        import re
        invalid = [e for e in params.recipients if not re.match(r"[^@]+@[^@]+\.[^@]+", e)]
        if invalid:
            return [f"Invalid email addresses: {', '.join(invalid)}"]
        return []

    async def execute(self, params: SendBulkParams, ctx: ToolExecutionContext) -> ToolResult:
        try:
            from services.operations.notification_center import NotificationCenter
            nc = NotificationCenter()

            sent_count = 0
            failures: List[str] = []

            for recipient in params.recipients:
                try:
                    ok = nc.send_email(
                        to_address=recipient,
                        subject=params.subject,
                        body=params.body,
                        html=True,
                        trip_id=params.trip_id,
                    )
                    if ok:
                        sent_count += 1
                    else:
                        failures.append(recipient)
                except Exception:
                    failures.append(recipient)

            if sent_count > 0:
                return ToolResult(
                    status="success",
                    data={"sent_count": sent_count, "failed_count": len(failures)},
                    message_key="copilot.email.bulk_sent",
                    message_params={"sent": sent_count, "failed": len(failures)},
                )
            return ToolResult(status="failed", message_key="copilot.email.bulk_failed")
        except Exception as e:
            return ToolResult(status="failed", message_key="copilot.error.unexpected", message_params={"error": str(e)})
