"""E2E: AutoMail lifecycle — templates, reminders, history, and full pipeline.

Tests the template CRUD, reminder scheduling, skip/cancel, history
stats/pagination, and the complete DunnerEngine pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from repositories.automail_repository import AutoMailRepository
from repositories.client_repository import ClientRepository
from repositories.invoice_repository import InvoiceRepository
from services.automail.history_service import HistoryService
from services.automail.reminder_service import (
    REMINDER_STATUS_CANCELLED,
    REMINDER_STATUS_SCHEDULED,
    REMINDER_STATUS_SKIPPED,
    ReminderService,
)
from services.automail.template_service import TemplateService, render_template
from services.invoicing.service import InvoiceService
from services.operations.dunner_engine import DunnerEngine
from services.operations.event_bus import EventBus
from services.trip_service import TripService
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow

logging.disable(logging.CRITICAL)


# ── Helpers ───────────────────────────────────────────────────────────────

def _dt(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


def _create_client(db) -> int:
    repo = ClientRepository(db)
    now = datetime.now().isoformat()
    return repo.create({
        "name": "AutoMail Client GmbH",
        "contact_person": "Klaus Schmidt",
        "phone": "+49-30-12345679",
        "email": "klaus@automail-client.de",
        "address": "Hauptstrasse 1, 10115 Berlin",
        "vat_number": "DE999999999",
        "currency_preference": "EUR",
        "is_active": 1,
        "created_at": now,
        "updated_at": now,
    })


def _create_trip(db, client_id, status="Delivered") -> int:
    svc = TripService(db)
    now = datetime.now().isoformat()
    return svc.add({
        "client_name": "AutoMail Client GmbH",
        "client_id": client_id,
        "truck_number": "TR-AUTO-001",
        "driver_name": "AutoMail Driver",
        "start_date": _dt(-10),
        "end_date": _dt(-8),
        "distance_km": 600.0,
        "total_price_eur": 2400.0,
        "rate_per_km": 4.0,
        "fuel_cost": 480.0,
        "toll_cost": 90.0,
        "salary_cost": 300.0,
        "extra_costs": 40.0,
        "net_profit": 1490.0,
        "currency": "EUR",
        "status": status,
        "created_at": now,
        "cargo_description": "Automail cargo",
        "package_count": 12,
        "gross_weight_kg": 6000.0,
    })


def _create_invoice(db, trip_id, amount=2400.0, due_date=None):
    repo = InvoiceRepository(db)
    inv_number = f"INV-AUTO-{datetime.now().year}-{trip_id:04d}"
    due = due_date or _dt(30)
    repo.db.conn.execute(
        "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
        "VALUES (?, ?, ?, ?, ?, 'Unpaid')",
        (trip_id, inv_number, _dt(0), due, amount),
    )
    repo.db.conn.commit()
    return inv_number


def _create_schedule(db, name, trigger_type, days_offset, template_id):
    repo = AutoMailRepository(db)
    # template_id might be a ServiceResult; extract its data id
    if hasattr(template_id, "data") and isinstance(template_id.data, dict):
        tid = template_id.data["id"]
    elif hasattr(template_id, "data") and hasattr(template_id.data, "id"):
        tid = template_id.data.id
    else:
        tid = template_id
    return repo.create_schedule({
        "name": name,
        "trigger_type": trigger_type,
        "days_offset": days_offset,
        "template_id": tid,
        "is_active": 1,
        "sort_order": 0,
        "attach_invoice": 0,
        "attach_cmr": 0,
        "attach_all_docs": 0,
    })


# ── Tests ─────────────────────────────────────────────────────────────────


class TestAutoMailLifecycle:
    """AutoMail lifecycle: templates, reminders, history, and DunnerEngine."""

    def test_template_crud_and_render(self, db):
        """Create template, get it back, render with context variables."""
        svc = TemplateService(db)
        data = {
            "name": "Payment Reminder",
            "subject": "Invoice {invoice_number} is due",
            "body_text": "Dear {client_name}, your invoice {invoice_number} of {total_amount} {currency} is due.",
            "body_html": "<p>Dear {client_name},</p>",
            "is_default": 1,
        }
        result = svc.create_template(data)
        assert result.success is True
        tid = result.data["id"]
        assert tid > 0

        fetched = svc.get_template_by_id(tid)
        assert fetched is not None
        assert fetched["name"] == "Payment Reminder"
        assert fetched["is_default"] == 1

        # Render with context
        ctx = {
            "invoice_number": "INV-2026-0042",
            "total_amount": "1,250.00",
            "currency": "EUR",
            "client_name": "ACME GmbH",
        }
        subject, body_text, body_html = svc.render_email(fetched, ctx)
        assert "INV-2026-0042" in subject
        assert "ACME GmbH" in body_text
        assert "1,250.00" in body_text

    def test_reminder_timeline_for_invoice(self, db):
        """Create invoice with due_date, create 3 schedules, check reminder status."""
        client_id = _create_client(db)
        trip_id = _create_trip(db, client_id)
        inv_number = _create_invoice(db, trip_id, due_date=_dt(15))

        # Create a template first
        tmpl_svc = TemplateService(db)
        tmpl_result = tmpl_svc.create_template({
            "name": "Due Reminder Template",
            "subject": "Payment reminder for {invoice_number}",
            "body_text": "Please pay {total_amount} by {due_date}.",
            "is_default": 0,
        })
        assert tmpl_result.success is True
        tid = tmpl_result.data["id"]

        # Create 3 schedules: before, on, after due
        tmpl_id = tid  # _create_schedule handles ServiceResult
        sched1 = _create_schedule(db, "3 days before", "days_before_due", 3, tmpl_id)
        sched2 = _create_schedule(db, "On due date", "on_due_date", 0, tmpl_id)
        sched3 = _create_schedule(db, "5 days after", "days_after_due", 5, tmpl_id)
        assert sched1 > 0
        assert sched2 > 0
        assert sched3 > 0

        # Get the invoice_id
        inv_repo = InvoiceRepository(db)
        invoice = inv_repo.get_by_trip_id(trip_id)
        assert invoice is not None
        invoice_id = invoice["id"]

        reminder_svc = ReminderService(db)
        timeline = reminder_svc.get_reminder_status_for_invoice(
            invoice_id=invoice_id,
            invoice_due_date=_dt(15),
            trip_id=trip_id,
            client_id=client_id,
        )

        # We should have at least 3 timeline entries (DB may have seeded defaults)
        assert len(timeline) >= 3

        # Statuses should be "scheduled" since due date is in the future
        for entry in timeline:
            assert entry["status"] == REMINDER_STATUS_SCHEDULED

    def test_reminder_skip_and_cancel(self, db):
        """Create reminder, skip it, verify skipped record in DB."""
        client_id = _create_client(db)
        trip_id = _create_trip(db, client_id)
        inv_number = _create_invoice(db, trip_id)

        inv_repo = InvoiceRepository(db)
        invoice = inv_repo.get_by_trip_id(trip_id)
        invoice_id = invoice["id"]

        reminder_svc = ReminderService(db)

        # Skip the next reminder
        ok = reminder_svc.skip_next_reminder(invoice_id=invoice_id, trip_id=trip_id)
        assert ok is True

        # Verify a skipped record exists in the DB
        repo = AutoMailRepository(db)
        rows = repo.get_reminder_status(invoice_id, trip_id, "manual_skip")
        assert len(rows) >= 1
        assert rows[0]["status"] == "skipped"

        # Now cancel all reminders
        ok = reminder_svc.cancel_all_reminders(invoice_id=invoice_id, trip_id=trip_id)
        assert ok is True

        # Verify cancelled record exists
        cancelled = repo.get_reminder_status(invoice_id, trip_id, "manual_cancel_all")
        assert len(cancelled) >= 1
        assert cancelled[0]["status"] == "cancelled"

    def test_history_service_stats(self, db):
        """Insert email logs, call get_stats(), verify counts."""
        repo = AutoMailRepository(db)

        # Create minimal trips so FK constraints are satisfied
        for i in range(4):
            db.conn.execute(
                "INSERT INTO trips (id, client_name, status) VALUES (?, ?, 'Delivered')",
                (i + 1, f"Client {i}"),
            )
        db.conn.commit()

        # Insert 3 sent emails
        for i in range(3):
            repo.log_email(trip_id=i + 1, recipient=f"client{i}@test.com",
                           subject=f"Reminder #{i + 1}", status="sent")

        # Insert 1 failed email
        repo.log_email(trip_id=4, recipient="failed@test.com",
                       subject="Failed Reminder", status="failed")

        history_svc = HistoryService(db)
        stats = history_svc.get_stats(days=30)

        assert stats["emails_sent"] >= 3
        assert stats["emails_failed"] >= 1

    def test_history_service_pagination(self, db):
        """Insert 25 email logs, get page 0 size 10, verify pagination."""
        repo = AutoMailRepository(db)

        # Create minimal trips so FK constraints are satisfied
        for i in range(25):
            db.conn.execute(
                "INSERT INTO trips (id, client_name, status) VALUES (?, ?, 'Delivered')",
                (i + 1, f"Client {i}"),
            )
        db.conn.commit()

        for i in range(25):
            repo.log_email(trip_id=i + 1, recipient=f"user{i}@test.com",
                           subject=f"Email #{i + 1}", status="sent")

        history_svc = HistoryService(db)

        # Get page 0, size 10
        page0, total0 = history_svc.get_email_history(page=0, page_size=10)
        assert len(page0) == 10
        assert total0 >= 25

        # Get page 2, size 10
        page2, total2 = history_svc.get_email_history(page=2, page_size=10)
        assert len(page2) == 5
        assert total2 >= 25

    def test_full_automail_pipeline(self, db):
        """Create template→schedule→client→trip→invoice→run DunnerEngine,
        verify email sent + reminder recorded."""
        # 1. Create template
        tmpl_svc = TemplateService(db)
        tmpl_result = tmpl_svc.create_template({
            "name": "Pipeline Reminder",
            "subject": "Invoice {invoice_number} is due",
            "body_text": "Dear {client_name}, please pay {total_amount} {currency}.",
            "is_default": 0,
        })
        assert tmpl_result.success is True
        tid = tmpl_result.data["id"]
        assert tid > 0

        # 2. Create schedule — 1 day after due (invoice due_date is yesterday, so days_past_due=1)
        sched_id = _create_schedule(db, "1 day after due pipeline", "days_after_due", 1, tid)
        assert sched_id > 0

        # 3. Create client with email
        client_id = _create_client(db)

        # 4. Create trip
        trip_id = _create_trip(db, client_id)

        # 5. Create invoice with due_date = yesterday (so it's due)
        inv_repo = InvoiceRepository(db)
        yesterday = _dt(-1)
        inv_number = _create_invoice(db, trip_id, amount=2400.0, due_date=yesterday)

        invoice = inv_repo.get_by_trip_id(trip_id)
        assert invoice is not None

        # 6. Run DunnerEngine — mock NotificationCenter.send_email
        nc = MagicMock()
        nc.send_email.return_value = True

        engine = DunnerEngine(db=db, notification_center=nc)
        sent_count = engine.evaluate_all()

        # Should have sent at least 1 reminder
        assert sent_count >= 1

        # 7. Verify a reminder was recorded
        reminder_count = inv_repo.get_reminder_count(invoice["id"])
        assert reminder_count >= 1
