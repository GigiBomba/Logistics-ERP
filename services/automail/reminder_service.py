"""Reminder scheduling and status calculation for AutoMail.

Determines which schedule entries apply to each unpaid invoice,
calculates next reminders, and checks stop conditions (client
overrides, max reminders, payment received).
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timedelta
from typing import Any, Optional

from models.automail_models import SendReminderRequest, SendReminderResult, AutomailSendResult
from models.common import ServiceResult, ErrorDetail
from repositories.automail_repository import AutoMailRepository
from services.permission_service import PermissionService

logger = logging.getLogger(__name__)

REMINDER_STATUS_SCHEDULED = "scheduled"
REMINDER_STATUS_SENT = "sent"
REMINDER_STATUS_FAILED = "failed"
REMINDER_STATUS_SKIPPED = "skipped"
REMINDER_STATUS_CANCELLED = "cancelled"

_PAGE_SIZE = 20


class ReminderService:
    """Business logic for reminder schedule evaluation."""

    def __init__(self, db) -> None:
        if db is None:
            raise ValueError("ReminderService requires a valid db connection")
        self._repo = AutoMailRepository(db)
        self._db = db

    # ── Schedule lookup ──────────────────────────────────────────────────

    def get_active_schedules(self) -> list[dict[str, Any]]:
        """Return all active schedule entries with template data."""
        return self._repo.get_active_schedules()

    def get_all_schedules(self) -> list[dict[str, Any]]:
        return self._repo.get_all_schedules()

    # ── Reminder status for an invoice ───────────────────────────────────

    def get_reminder_status_for_invoice(
        self,
        invoice_id: int,
        invoice_due_date: str,
        trip_id: int,
        client_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Return the timeline of all reminders (past + future) for one invoice.

        Each entry has:
            - schedule_name, trigger_type, days_offset
            - status: scheduled/sent/failed/skipped/cancelled
            - scheduled_date: when it *should* be sent
            - sent_at: when it *was* sent (None if future)
            - template_name
        """
        if not invoice_due_date:
            return []

        try:
            due = datetime.strptime(str(invoice_due_date)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return []

        today = date.today()
        schedules = self.get_active_schedules()
        sent = self._get_sent_reminders(invoice_id)
        sent_by_name: dict[str, dict] = {}
        for s in sent:
            rtype = s.get("reminder_type", "")
            if rtype:
                sent_by_name[rtype] = s

        result: list[dict[str, Any]] = []
        for sched in schedules:
            scheduled_date = self._compute_scheduled_date(due, sched)
            past = scheduled_date and scheduled_date <= today

            schedule_name = sched.get("name", f"schedule_{sched['id']}")
            existing = sent_by_name.get(schedule_name)

            if existing:
                status = existing.get("status", "sent")
                sent_at = existing.get("sent_at")
            elif past:
                status = REMINDER_STATUS_SKIPPED
                sent_at = None
            else:
                status = REMINDER_STATUS_SCHEDULED
                sent_at = None

            result.append({
                "schedule_id": sched["id"],
                "schedule_name": schedule_name,
                "trigger_type": sched["trigger_type"],
                "days_offset": sched["days_offset"],
                "target_days": self._compute_target_days(sched),
                "status": status,
                "scheduled_date": str(scheduled_date) if scheduled_date else None,
                "sent_at": sent_at,
                "template_name": sched.get("template_name", ""),
                "invoice_id": invoice_id,
                "trip_id": trip_id,
            })

        return result

    def get_reminder_status_for_all_active(
        self,
        page: int = 0,
        search: str = "",
        status_filter: str = "",
        limit: Optional[int] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return reminder timeline for ALL unpaid invoices (paginated).

        Returns (entries, total_count).  Each entry is a dict with
        invoice + trip + client info plus the computed timeline.
        """
        limit = limit or _PAGE_SIZE
        offset = page * limit

        invoices = self._fetch_unpaid_invoices(search)
        today = date.today()

        # Build timeline for each invoice
        all_entries: list[dict[str, Any]] = []
        for inv in invoices:
            timeline = self.get_reminder_status_for_invoice(
                invoice_id=inv["invoice_id"],
                invoice_due_date=inv["due_date"],
                trip_id=inv["trip_id"],
                client_id=inv.get("client_id"),
            )
            merged = dict(inv)
            merged["timeline"] = timeline
            merged["_sort_date"] = inv.get("due_date", "")
            all_entries.append(merged)

        # Apply status filter
        if status_filter:
            filtered = []
            for entry in all_entries:
                statuses = {e["status"] for e in entry.get("timeline", [])}
                if status_filter == "overdue":
                    # Invoice is past due and past all reminders
                    if self._is_overdue(entry.get("due_date", ""), today) and \
                       {REMINDER_STATUS_SCHEDULED}.isdisjoint(statuses):
                        filtered.append(entry)
                elif status_filter in statuses:
                    filtered.append(entry)
            all_entries = filtered

        # Sort by due date ascending
        all_entries.sort(key=lambda e: e.get("_sort_date") or "")

        total = len(all_entries)
        paginated = all_entries[offset:offset + limit]
        return paginated, total

    # ── Skip / Cancel controls ──────────────────────────────────────────

    def skip_next_reminder(self, invoice_id: int, trip_id: int) -> bool:
        try:
            self._repo.skip_reminder(invoice_id, trip_id)
            return True
        except Exception as exc:
            logger.error("Failed to skip reminder for invoice #%d: %s", invoice_id, exc)
            return False

    def cancel_all_reminders(self, invoice_id: int, trip_id: int) -> bool:
        try:
            self._repo.cancel_all_reminders(invoice_id, trip_id)
            return True
        except Exception as exc:
            logger.error("Failed to cancel reminders for invoice #%d: %s", invoice_id, exc)
            return False

    # ── Typed send methods ──────────────────────────────────────────────

    def send_reminder(self, request: SendReminderRequest, user_id: int) -> AutomailSendResult:
        """Send a reminder email using the specified template.

        Args:
            request: Typed send reminder request with template, recipient, and
                     optional invoice/trip references.
            user_id: ID of the user performing the action.

        Returns:
            AutomailSendResult (``ServiceResult[SendReminderResult]``).
        """
        logger.info(
            "Sending reminder for client #%d, invoice #%s, template #%d by user #%d",
            request.client_id, request.invoice_id, request.template_id, user_id,
        )

        perm = PermissionService(self._repo.db)
        perm_result = perm.can_send_email(user_id)
        if not perm_result.allowed:
            logger.warning(
                "Permission denied for user #%d to send reminder: %s",
                user_id, perm_result.reason,
            )
            return AutomailSendResult(
                success=False,
                errors=[ErrorDetail(message=perm_result.reason, code="permission_denied")],
            )

        try:
            template = self._repo.get_template_by_id(request.template_id)
            if not template:
                logger.warning("Template #%d not found for reminder", request.template_id)
                return AutomailSendResult(
                    success=False,
                    errors=[
                        ErrorDetail(
                            message=f"Template #{request.template_id} not found",
                            code="template_not_found",
                        )
                    ],
                )

            # Build minimal context from request data
            context: dict[str, str] = {
                "client_name": str(request.client_id),
                "client_contact": "",
                "invoice_number": str(request.invoice_id) if request.invoice_id else "",
                "trip_id": str(request.trip_id) if request.trip_id else "",
                "total_amount": "",
                "currency": "",
                "due_date": str(request.send_date) if request.send_date else "",
                "days_overdue": "",
                "company_name": "",
                "truck_plate": "",
                "driver_name": "",
            }

            # Render email via template_service helper
            from services.automail.template_service import render_template

            subject = render_template(template.get("subject", ""), context)
            body_text = render_template(template.get("body_text", ""), context)
            body_html = render_template(template.get("body_html", ""), context)

            sent_at = datetime.utcnow()

            # Log the email
            self._repo.log_email(
                trip_id=request.trip_id,
                recipient=request.recipient_email,
                subject=subject,
                status="sent",
            )

            # Log the manual send record
            if request.invoice_id:
                self._repo.log_manual_send(
                    invoice_id=request.invoice_id,
                    trip_id=request.trip_id or 0,
                    recipient=request.recipient_email,
                )

            result_data = SendReminderResult(
                email_id=0,
                sent_to=request.recipient_email,
                template_name=template.get("name", ""),
                sent_at=sent_at,
                success=True,
            )
            logger.info(
                "Reminder sent to %s for template #%d",
                request.recipient_email, request.template_id,
            )
            return AutomailSendResult(success=True, data=result_data)

        except Exception as exc:
            logger.error("Failed to send reminder: %s", exc)
            error_result = SendReminderResult(
                email_id=0,
                sent_to=request.recipient_email,
                template_name="",
                sent_at=datetime.utcnow(),
                success=False,
                error_message=str(exc),
            )
            return AutomailSendResult(
                success=False,
                data=error_result,
                errors=[ErrorDetail(message=str(exc), code="send_failed")],
            )

    def send_overdue_reminders(self, user_id: int) -> ServiceResult[list[SendReminderResult]]:
        """Send reminders for all overdue invoices.

        Finds all unpaid invoices whose due date is in the past and sends
        a reminder email using the default template.

        Args:
            user_id: ID of the user performing the action.

        Returns:
            ServiceResult containing a list of ``SendReminderResult``.
        """
        logger.info("Sending overdue reminders triggered by user #%d", user_id)

        perm = PermissionService(self._repo.db)
        perm_result = perm.can_send_email(user_id)
        if not perm_result.allowed:
            logger.warning(
                "Permission denied for user #%d to send overdue reminders: %s",
                user_id, perm_result.reason,
            )
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=perm_result.reason, code="permission_denied")],
            )

        try:
            unpaid = self._repo.get_unpaid_invoices_for_reminders()
            today = date.today()
            results: list[SendReminderResult] = []

            default_template = self._repo.get_default_template()
            if not default_template:
                logger.warning("No default template configured for overdue reminders")
                return ServiceResult(
                    success=False,
                    errors=[
                        ErrorDetail(
                            message="No default email template configured",
                            code="no_default_template",
                        )
                    ],
                )

            for inv in unpaid:
                due_date_str = inv.get("due_date", "")
                if not due_date_str:
                    continue
                try:
                    due = datetime.strptime(str(due_date_str)[:10], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    continue

                if due >= today:
                    continue  # not overdue yet

                # Build context from invoice data
                days_overdue = (today - due).days
                context: dict[str, str] = {
                    "invoice_number": inv.get("invoice_number", ""),
                    "total_amount": str(inv.get("total_amount", "")),
                    "currency": inv.get("currency", "EUR"),
                    "due_date": due_date_str,
                    "days_overdue": str(days_overdue),
                    "company_name": "",
                    "client_name": inv.get("client_company_name", inv.get("client_name", "")),
                    "client_contact": "",
                    "trip_id": str(inv.get("trip_id", "")),
                    "truck_plate": "",
                    "driver_name": "",
                }

                recipient = inv.get("client_email", "")
                if not recipient:
                    logger.warning(
                        "No email for invoice #%s, skipping",
                        inv.get("invoice_number"),
                    )
                    continue

                from services.automail.template_service import render_template

                subject = render_template(default_template.get("subject", ""), context)

                try:
                    self._repo.log_email(
                        trip_id=inv.get("trip_id"),
                        recipient=recipient,
                        subject=subject,
                        status="sent",
                    )
                    self._repo.log_manual_send(
                        invoice_id=inv["invoice_id"],
                        trip_id=inv["trip_id"],
                        recipient=recipient,
                    )
                    results.append(SendReminderResult(
                        email_id=0,
                        sent_to=recipient,
                        template_name=default_template.get("name", ""),
                        sent_at=datetime.utcnow(),
                        success=True,
                    ))
                    logger.info(
                        "Overdue reminder sent for invoice #%s to %s",
                        inv.get("invoice_number"), recipient,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to send overdue reminder for invoice #%s: %s",
                        inv.get("invoice_number"), exc,
                    )
                    results.append(SendReminderResult(
                        email_id=0,
                        sent_to=recipient,
                        template_name=default_template.get("name", ""),
                        sent_at=datetime.utcnow(),
                        success=False,
                        error_message=str(exc),
                    ))

            logger.info("Sent %d overdue reminders", len(results))
            return ServiceResult(success=True, data=results)

        except Exception as exc:
            logger.error("Failed to process overdue reminders: %s", exc)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="overdue_reminder_failed")],
            )

    # ── Next reminder calculation ───────────────────────────────────────

    def calculate_next_reminder(
        self,
        invoice_due_date: str,
        client_override: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """Return the next schedule entry that should fire for this invoice.

        Returns None if no schedule applies or all have been sent.
        """
        if not invoice_due_date:
            return None

        try:
            due = datetime.strptime(str(invoice_due_date)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

        today = date.today()
        schedules = self.get_active_schedules()

        for sched in schedules:
            target = self._compute_target_days(sched)
            days_past_due = (today - due).days
            if days_past_due == target:
                return sched

        return None

    def should_skip(
        self,
        invoice_id: int,
        client_override: Optional[dict[str, Any]] = None,
        max_reminders: int = 5,
    ) -> bool:
        """Check whether reminders should be skipped for this invoice."""
        if client_override and client_override.get("is_disabled"):
            return True

        sent_count = self._count_sent_reminders(invoice_id)
        if sent_count >= max_reminders:
            return True

        return False

    # ------------------------------------------------------------------
    # Async execution
    # ------------------------------------------------------------------

    def send_reminder_async(
        self,
        request: SendReminderRequest,
        user_id: int,
        callback,
    ) -> threading.Thread:
        """Send a reminder email in a background thread.

        Args:
            request: Typed send reminder request.
            user_id: ID of the user performing the action.
            callback: Callable that receives the ``AutomailSendResult``
                      when sending completes.

        Returns:
            The background ``threading.Thread`` (daemon) for optional join.
        """
        def _run():
            try:
                result = self.send_reminder(request, user_id)
                callback(result)
            except Exception as e:
                logger.error("Async send reminder failed: %s", e, exc_info=True)
                callback(AutomailSendResult(
                    success=False,
                    errors=[ErrorDetail(message=str(e), code="ASYNC_ERROR")],
                ))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread

    def send_overdue_reminders_async(
        self,
        user_id: int,
        callback,
    ) -> threading.Thread:
        """Send overdue reminders for all unpaid invoices in a background thread.

        Args:
            user_id: ID of the user performing the action.
            callback: Callable that receives the
                      ``ServiceResult[list[SendReminderResult]]`` when processing
                      completes.

        Returns:
            The background ``threading.Thread`` (daemon) for optional join.
        """
        def _run():
            try:
                result = self.send_overdue_reminders(user_id)
                callback(result)
            except Exception as e:
                logger.error("Async overdue reminders failed: %s", e, exc_info=True)
                callback(ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message=str(e), code="ASYNC_ERROR")],
                ))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _compute_target_days(schedule: dict[str, Any]) -> int:
        """Convert a schedule's trigger_type + days_offset into a
        ``days_past_due`` integer value for matching.

        - 'days_before_due': target = -offset  (e.g. 3 days before → -3)
        - 'on_due_date':     target = 0
        - 'days_after_due':  target = offset   (e.g. 3 days after → 3)
        """
        trigger = schedule["trigger_type"]
        offset = schedule["days_offset"]
        if trigger == "days_before_due":
            return -offset
        elif trigger == "days_after_due":
            return offset
        return 0

    def _compute_scheduled_date(
        self,
        due_date: date,
        schedule: dict[str, Any],
    ) -> Optional[date]:
        """Return the concrete calendar date when this schedule should fire."""
        target = self._compute_target_days(schedule)
        return due_date + timedelta(days=target)

    def _is_overdue(self, due_date_str: str, today: date) -> bool:
        try:
            due = datetime.strptime(str(due_date_str)[:10], "%Y-%m-%d").date()
            return due < today
        except (ValueError, TypeError):
            return False

    def _fetch_unpaid_invoices(self, search: str = "") -> list[dict[str, Any]]:
        """Fetch all unpaid invoices with trip and client data."""
        try:
            return self._repo.get_unpaid_invoices_for_reminders(search)
        except Exception as exc:
            logger.error("ReminderService: failed to fetch unpaid invoices: %s", exc)
            return []

    def _get_sent_reminders(self, invoice_id: int) -> list[dict[str, Any]]:
        try:
            return self._repo.get_reminder_status(invoice_id, 0, "sent")
        except Exception:
            return []

    def _count_sent_reminders(self, invoice_id: int) -> int:
        try:
            return self._repo.get_sent_reminder_count(invoice_id)
        except Exception:
            return 0
