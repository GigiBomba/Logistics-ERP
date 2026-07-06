"""Reminder scheduling and status calculation for AutoMail.

Determines which schedule entries apply to each unpaid invoice,
calculates next reminders, and checks stop conditions (client
overrides, max reminders, payment received).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from repositories.automail_repository import AutoMailRepository

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
