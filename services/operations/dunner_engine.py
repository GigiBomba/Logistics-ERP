"""Dunner Engine — automated invoice reminder dispatch.

Evaluates unpaid invoices each daily cycle and sends proactive email
reminders based on configurable schedule entries stored in the
``automail_schedules`` table.

Each email includes all documents linked to the trip as attachments.
Duplicate sends are prevented via the ``invoice_reminders`` table.
Per-client overrides in ``automail_client_overrides`` are respected.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any, Optional

from repositories.automail_repository import AutoMailRepository
from repositories.client_repository import ClientRepository
from repositories.invoice_repository import InvoiceRepository
from services.automail.reminder_service import ReminderService
from services.automail.template_service import TemplateService
from services.document_automation.package_builder import PackageBuilder
from services.invoicing.config_manager import load_company_config
from services.operations.event_bus import DAILY_CHECK, EventBus
from services.operations.notification_center import NotificationCenter
from services.operations.rules import Rules

logger = logging.getLogger("operations.dunner_engine")


class DunnerEngine:
    """Evaluates unpaid invoices and dispatches automated reminders.

    Connects to the :class:`EventBus` ``DAILY_CHECK`` event to run
    its evaluation cycle.  Schedule entries, templates, and per-client
    overrides are read from the database on every cycle.
    """

    def __init__(
        self,
        db,
        notification_center: Optional[NotificationCenter] = None,
        prefs=None,
    ) -> None:
        self._db = db
        self._notification_center = notification_center
        self._prefs = prefs
        self._event_bus = EventBus()
        self._rules = Rules()
        self._subscribe()

    def _subscribe(self) -> None:
        self._event_bus.subscribe(DAILY_CHECK, self._on_daily_check)
        logger.info("DunnerEngine subscribed to events")

    def shutdown(self) -> None:
        try:
            self._event_bus.unsubscribe(DAILY_CHECK, self._on_daily_check)
            logger.debug("DunnerEngine unsubscribed events")
        except Exception:
            pass

    # ── Event handlers ──────────────────────────────────────────────

    def _on_daily_check(self, ev: dict[str, Any]) -> None:
        self.evaluate_all()

    # ── Evaluation ──────────────────────────────────────────────────

    def evaluate_all(self) -> int:
        """Run the full dunner evaluation cycle.

        Loads active schedules from the database, fetches all unpaid
        invoices, and dispatches any reminder that matches the current
        ``days_past_due`` value.

        Returns the number of reminder emails sent.
        """
        if not self._rules.get("dunner_enabled", True):
            logger.debug("DunnerEngine is disabled via rules, skipping")
            return 0

        if not self._notification_center:
            logger.warning("DunnerEngine: no notification_center available, skipping")
            return 0

        if self._db is None:
            logger.warning("DunnerEngine: no database available, skipping")
            return 0

        # Load configuration from database
        repo = AutoMailRepository(self._db)
        template_service = TemplateService(self._db)

        schedules = repo.get_active_schedules()
        if not schedules:
            logger.debug("DunnerEngine: no active schedules, skipping")
            return 0

        templates = {t["id"]: t for t in repo.get_all_templates()}
        overrides = {o["client_id"]: o for o in repo.get_all_overrides()}
        settings = repo.get_all_settings()

        max_reminders = int(settings.get("max_reminders_per_invoice", "5"))
        company_name = load_company_config().get("company_name", "Operion ERP")
        today = date.today()
        sent_count = 0

        invoices = self._fetch_due_invoices()
        if not invoices:
            logger.debug("DunnerEngine: no unpaid invoices found")
            return 0

        for inv in invoices:
            try:
                due_str = inv.get("due_date", "")
                if not due_str:
                    continue

                due_date = datetime.strptime(str(due_str)[:10], "%Y-%m-%d").date()
                days_past_due = (today - due_date).days

                client_id = inv.get("client_id")
                override = overrides.get(client_id) if client_id else None

                if override and override.get("is_disabled"):
                    logger.debug(
                        "Dunner: client #%s has disabled reminders, skipping invoice #%d",
                        client_id, inv["invoice_id"],
                    )
                    continue

                # Check max reminders per invoice
                if self._count_sent_for_invoice(inv["invoice_id"]) >= max_reminders:
                    logger.debug(
                        "Dunner: max reminders (%d) reached for invoice #%d, skipping",
                        max_reminders, inv["invoice_id"],
                    )
                    continue

                client_email = self._resolve_client_email(inv)
                if not client_email:
                    logger.info(
                        "No email for client of invoice #%d (trip #%d), skipping reminder",
                        inv["invoice_id"], inv["trip_id"],
                    )
                    continue

                total_amount_val = inv.get("total_amount") or 0

                # Build common template context
                template_context = {
                    "invoice_number": inv["invoice_number"],
                    "total_amount": f"{total_amount_val:,.2f}",
                    "currency": inv.get("currency", "EUR"),
                    "due_date": str(due_date),
                    "days_overdue": str(max(0, days_past_due)),
                    "company_name": company_name,
                    "client_name": inv.get("client_company_name") or inv.get("client_name", ""),
                    "client_contact": inv.get("client_contact", ""),
                    "trip_id": str(inv["trip_id"]),
                    "truck_plate": inv.get("truck_plate", ""),
                    "driver_name": inv.get("driver_name", ""),
                }

                # Try each schedule
                for sched in schedules:
                    target = ReminderService._compute_target_days(sched)
                    if days_past_due < target:
                        continue

                    reminder_type = sched.get("name", f"schedule_{sched['id']}")

                    if self._has_been_sent(inv["invoice_id"], reminder_type):
                        logger.debug(
                            "Reminder %s already sent for invoice #%d, skipping",
                            reminder_type, inv["invoice_id"],
                        )
                        continue

                    # Re-check invoice payment status right before sending,
                    # since the invoice may have been paid between fetch and send.
                    try:
                        cur = self._db.conn.execute(
                            "SELECT status FROM invoices WHERE id = ?", (inv["invoice_id"],)
                        )
                        row = cur.fetchone()
                        if row and row[0] != "Unpaid":
                            logger.info(
                                "Invoice #%d is no longer unpaid (status=%s), skipping reminder",
                                inv["invoice_id"], row[0],
                            )
                            continue
                    except Exception as exc:
                        logger.debug(
                            "Dunner: failed to re-check invoice #%d status: %s",
                            inv["invoice_id"], exc,
                        )

                    # Resolve template (respect client override)
                    template_id = sched["template_id"]
                    if override and override.get("custom_template_id"):
                        template_id = override["custom_template_id"]

                    template = templates.get(template_id)
                    if not template:
                        logger.warning(
                            "Template id=%d not found for schedule #%d, skipping",
                            template_id, sched["id"],
                        )
                        continue

                    # Render the email
                    subject, body_text, body_html = template_service.render_email(
                        template, template_context,
                    )
                    has_html = bool(body_html and body_html.strip())

                    attachments = self._collect_trip_documents(inv["trip_id"])

                    ok = self._notification_center.send_email(
                        to_address=client_email,
                        subject=subject,
                        body=body_html if has_html else body_text,
                        attachments=attachments,
                        html=has_html,
                        trip_id=inv["trip_id"],
                    )

                    if ok:
                        self._log_sent(
                            invoice_id=inv["invoice_id"],
                            trip_id=inv["trip_id"],
                            reminder_type=reminder_type,
                            days_offset=days_past_due,
                            recipient_email=client_email,
                        )
                        sent_count += 1
                        logger.info(
                            "Dunner: sent %s reminder for invoice #%d to %s",
                            reminder_type, inv["invoice_id"], client_email,
                        )
                    else:
                        logger.warning(
                            "Dunner: failed to send %s reminder for invoice #%d",
                            reminder_type, inv["invoice_id"],
                        )

            except Exception as exc:
                logger.exception(
                    "Dunner: error processing invoice #%d: %s",
                    inv.get("invoice_id"), exc,
                )

        logger.info("DunnerEngine evaluation complete: %d reminder(s) sent", sent_count)
        return sent_count

    # ── Queries ─────────────────────────────────────────────────────

    def _fetch_due_invoices(self) -> list[dict[str, Any]]:
        """Return all unpaid invoices with their trip and client data."""
        try:
            return InvoiceRepository(self._db).get_dunner_due_invoices()
        except Exception as exc:
            logger.error("Dunner: failed to fetch due invoices: %s", exc)
            return []

    # ── Email resolution ────────────────────────────────────────────

    def _resolve_client_email(self, inv: dict[str, Any]) -> Optional[str]:
        """Get the client email from the invoice data.

        Prefers the JOINed ``clients.email``; falls back to a
        name-based lookup for trips whose ``client_id`` has not been
        backfilled yet.
        """
        email = (inv.get("client_email") or "").strip()
        if email:
            return email

        client_name = (inv.get("client_name") or "").strip()
        if not client_name:
            return None

        try:
            email = ClientRepository(self._db).get_client_email_by_name(client_name)
            if email:
                return email
        except Exception as exc:
            logger.debug("Dunner: name-based client email lookup failed: %s", exc)

        return None

    # ── Document attachments ────────────────────────────────────────

    def _collect_trip_documents(self, trip_id: int) -> list[str]:
        """Return file paths of all documents linked to *trip_id*.

        Uses the existing :class:`PackageBuilder` to locate documents
        via ``document_links`` and the trip's ``documents_attached``
        JSON column.
        """
        try:
            builder = PackageBuilder(self._db)
            docs = builder.list_trip_documents(trip_id)
            paths: list[str] = []
            for d in docs:
                fp = d.get("file_path", "")
                if fp and os.path.isfile(fp):
                    paths.append(fp)
            return paths
        except Exception as exc:
            logger.debug("Dunner: failed to collect documents for trip #%d: %s", trip_id, exc)
            return []

    # ── Duplicate prevention ────────────────────────────────────────

    def _has_been_sent(self, invoice_id: int, reminder_type: str) -> bool:
        """Check whether a given reminder has already been sent for this invoice."""
        if self._db is None:
            return False
        try:
            return InvoiceRepository(self._db).has_reminder_been_sent(invoice_id, reminder_type)
        except Exception as exc:
            logger.debug("Dunner: duplicate check failed for invoice #%d: %s", invoice_id, exc)
            return False

    def _count_sent_for_invoice(self, invoice_id: int) -> int:
        """Count how many reminders have been sent for this invoice."""
        if self._db is None:
            return 0
        try:
            return InvoiceRepository(self._db).get_reminder_count(invoice_id)
        except Exception:
            return 0

    def _log_sent(
        self,
        invoice_id: int,
        trip_id: int,
        reminder_type: str,
        days_offset: int,
        recipient_email: str,
    ) -> None:
        """Record a sent reminder in the database."""
        if self._db is None:
            return
        try:
            InvoiceRepository(self._db).insert_reminder(
                invoice_id=invoice_id,
                trip_id=trip_id,
                reminder_type=reminder_type,
                days_offset=days_offset,
                sent_at=datetime.now().isoformat(),
                recipient_email=recipient_email,
                status="sent",
            )
        except Exception as exc:
            logger.error("Dunner: failed to log reminder for invoice #%d: %s", invoice_id, exc)
