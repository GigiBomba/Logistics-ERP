"""E2E: Dunner engine reminders and receipt generation — simplified integration."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from repositories.automail_repository import AutoMailRepository
from repositories.client_repository import ClientRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.receipt_repository import ReceiptRepository
from services.automail.reminder_service import ReminderService
from services.invoicing.receipt_service import ReceiptService
from services.invoicing.service import InvoiceService
from services.operations.dunner_engine import DunnerEngine
from services.operations.notification_center import NotificationCenter
from services.operations.rules import Rules
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


# ── Helpers ───────────────────────────────────────────────────────────


def _dt(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


def _create_client(db) -> int:
    """Create a minimal client and return its id."""
    now = datetime.now().isoformat()
    return ClientRepository(db).create({
        "name": "Dunner Client GmbH",
        "contact_person": "Anna Test",
        "phone": "+49-30-1111111",
        "email": "anna@dunner-test.de",
        "address": "Teststr. 1, Berlin",
        "vat_number": "DE999999999",
        "currency_preference": "EUR",
        "is_active": 1,
        "created_at": now,
        "updated_at": now,
    })


def _create_trip(db, client_id: int, **overrides) -> int:
    """Insert a trip row and return its id."""
    now = datetime.now().isoformat()
    data = {
        "client_name": "Dunner Client GmbH",
        "client_id": client_id,
        "truck_number": "TR-DUN-001",
        "driver_name": "Max Driver",
        "status": "Delivered",
        "total_price_eur": 2500.0,
        "currency": "EUR",
        "created_at": now,
    }
    data.update(overrides)
    cursor = db.conn.execute(
        "INSERT INTO trips (client_name, client_id, truck_number, driver_name, "
        "status, total_price_eur, currency, created_at) "
        "VALUES (:client_name, :client_id, :truck_number, :driver_name, "
        ":status, :total_price_eur, :currency, :created_at)",
        data,
    )
    db.conn.commit()
    return cursor.lastrowid


def _create_invoice(db, trip_id: int, due_date: str) -> int:
    """Insert an unpaid invoice and return its id."""
    now = datetime.now().isoformat()
    cursor = db.conn.execute(
        "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
        "total_amount, status) VALUES (?, ?, ?, ?, ?, 'Unpaid')",
        (trip_id, f"INV-DUN-{trip_id:04d}", now[:10], due_date, 2500.0),
    )
    db.conn.commit()
    return cursor.lastrowid


def _create_automail_template(repo: AutoMailRepository) -> int:
    """Insert a dummy automail template and return its id."""
    return repo.create_template({
        "name": "default_reminder",
        "subject": "Payment Reminder for {invoice_number}",
        "body_text": "Dear customer, please pay {total_amount} by {due_date}.",
        "body_html": "",
        "variables_json": '["invoice_number", "total_amount", "due_date"]',
        "is_default": 1,
    })


def _create_automail_schedule(repo: AutoMailRepository, template_id: int) -> int:
    """Insert an active schedule firing days after due date."""
    return repo.create_schedule({
        "name": "days_after_due_10",
        "trigger_type": "days_after_due",
        "days_offset": 10,
        "template_id": template_id,
        "is_active": 1,
        "sort_order": 1,
    })


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def automail_repo(db):
    return AutoMailRepository(db)


@pytest.fixture
def invoice_repo(db):
    return InvoiceRepository(db)


@pytest.fixture(autouse=True)
def _reset_singletons():
    from services.operations.event_bus import EventBus
    EventBus._instance = None
    from services.operations.alert_manager import AlertManager
    AlertManager._instance = None
    Rules._instance = None


# ── Tests ─────────────────────────────────────────────────────────────


class TestDunnerReminderReceipt:
    """Simplified integration: reminder creation and receipt generation."""

    def test_dunner_sends_reminder_for_overdue_invoice(
        self, db, automail_repo, invoice_repo,
    ):
        """Create client+trip+invoice (overdue), create schedule, mock
        NotificationCenter, run DunnerEngine.evaluate_all(), verify reminder sent."""
        # ── Setup: client, trip, overdue invoice ────────────────────
        client_id = _create_client(db)
        trip_id = _create_trip(db, client_id)
        invoice_id = _create_invoice(db, trip_id, _dt(-10))  # 10 days overdue

        # ── Setup: automail template + schedule ─────────────────────
        tmpl_id = _create_automail_template(automail_repo)
        _create_automail_schedule(automail_repo, tmpl_id)

        # ── Act ─────────────────────────────────────────────────────
        nc = NotificationCenter(db)
        nc.send_email = MagicMock(return_value=True)  # type: ignore[method-assign]

        engine = DunnerEngine(db, notification_center=nc)
        sent_count = engine.evaluate_all()

        # ── Assert ──────────────────────────────────────────────────
        assert sent_count >= 1, "Expected at least 1 reminder sent"

        # Verify a reminder was logged in invoice_reminders
        reminder_count = invoice_repo.get_reminder_count(invoice_id)
        assert reminder_count >= 1, "No reminder recorded in invoice_reminders"

        nc.send_email.assert_called()

    def test_dunner_respects_client_override_disabled(
        self, db, automail_repo, invoice_repo,
    ):
        """Create client override is_disabled=1, verify no reminders sent."""
        client_id = _create_client(db)
        trip_id = _create_trip(db, client_id)
        invoice_id = _create_invoice(db, trip_id, _dt(-10))

        # ── Insert client override with is_disabled=true ────────────
        automail_repo.upsert_override(client_id, {"is_disabled": 1})

        tmpl_id = _create_automail_template(automail_repo)
        _create_automail_schedule(automail_repo, tmpl_id)

        nc = NotificationCenter(db)
        nc.send_email = MagicMock(return_value=True)  # type: ignore[method-assign]

        engine = DunnerEngine(db, notification_center=nc)
        sent_count = engine.evaluate_all()

        assert sent_count == 0, "Expected 0 reminders with client override disabled"
        nc.send_email.assert_not_called()

    def test_dunner_respects_max_reminders_limit(
        self, db, automail_repo, invoice_repo,
    ):
        """Pre-populate 5 sent reminders, max=5, verify 0 new sent."""
        client_id = _create_client(db)
        trip_id = _create_trip(db, client_id)
        invoice_id = _create_invoice(db, trip_id, _dt(-10))

        # Pre-populate 5 sent reminders (max_reminders_per_invoice defaults to 5)
        for i in range(5):
            invoice_repo.insert_reminder(
                invoice_id=invoice_id,
                trip_id=trip_id,
                reminder_type=f"test_{i}",
                days_offset=0,
                sent_at=datetime.now().isoformat(),
                recipient_email="anna@dunner-test.de",
                status="sent",
            )

        tmpl_id = _create_automail_template(automail_repo)
        _create_automail_schedule(automail_repo, tmpl_id)

        nc = NotificationCenter(db)
        nc.send_email = MagicMock(return_value=True)  # type: ignore[method-assign]

        engine = DunnerEngine(db, notification_center=nc)
        sent_count = engine.evaluate_all()

        assert sent_count == 0, "Expected 0 new reminders (max already reached)"

    def test_dunner_duplicate_prevention(
        self, db, automail_repo, invoice_repo,
    ):
        """Send reminder, run evaluate_all() again, verify 0 new."""
        client_id = _create_client(db)
        trip_id = _create_trip(db, client_id)
        invoice_id = _create_invoice(db, trip_id, _dt(-10))

        tmpl_id = _create_automail_template(automail_repo)
        _create_automail_schedule(automail_repo, tmpl_id)

        nc = NotificationCenter(db)
        nc.send_email = MagicMock(return_value=True)  # type: ignore[method-assign]

        engine = DunnerEngine(db, notification_center=nc)
        first_count = engine.evaluate_all()
        assert first_count >= 1, "First run should send a reminder"

        second_count = engine.evaluate_all()
        assert second_count == 0, (
            f"Second run should send 0 reminders (duplicate prevention), got {second_count}"
        )

    def test_receipt_generation_after_invoice_payment(
        self, db,
    ):
        """Create trip+invoice as Paid, generate receipt, verify receipt_number
        + total + related_trip_id."""
        client_id = _create_client(db)
        trip_id = _create_trip(db, client_id)
        now = datetime.now().isoformat()
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
            "total_amount, status) VALUES (?, ?, ?, ?, ?, 'Paid')",
            (trip_id, f"INV-RCT-{trip_id:04d}", now[:10], _dt(30), 2500.0),
        )
        db.conn.commit()

        # Generate receipt via ReceiptService
        receipt_data = {
            "receipt_type": "customer_payment",
            "payment_date": now[:10],
            "currency": "EUR",
            "company_name": "Operion Spedition GmbH",
            "received_from_name": "Dunner Client GmbH",
            "received_from_address": "Teststr. 1, Berlin",
            "payment_method": "Bank Transfer",
            "invoice_reference": f"INV-RCT-{trip_id:04d}",
            "related_trip_id": trip_id,
            "amount": 2500.0,
            "vat_rate": 19.0,
        }

        with patch.object(ReceiptService, "generate", return_value=os.path.join(
            tempfile.gettempdir(), "receipt_test.pdf",
        )):
            svc = ReceiptService(db)
            receipt_number = svc._receipt_repo.get_next_number()
            receipt_data["receipt_number"] = receipt_number
            svc.generate_and_record(receipt_data)

        # Verify receipt in DB
        receipt_repo = ReceiptRepository(db)
        rows = receipt_repo._fetchall(
            "SELECT * FROM receipts WHERE related_trip_id = ? ORDER BY id DESC LIMIT 1",
            (trip_id,),
        )
        assert len(rows) >= 1, "No receipt found in DB"
        receipt = rows[0]
        assert receipt["receipt_number"] == receipt_number
        assert receipt["total"] == 2500.0 + 2500.0 * 19.0 / 100  # amount + vat
        assert receipt["related_trip_id"] == trip_id

    def test_reminder_and_receipt_chain(
        self, db, automail_repo, invoice_repo,
    ):
        """Send reminder, mark invoice Paid, generate receipt, verify both recorded."""
        client_id = _create_client(db)
        trip_id = _create_trip(db, client_id)
        invoice_id = _create_invoice(db, trip_id, _dt(-10))

        # ── Step 1: Send reminder ──────────────────────────────────
        tmpl_id = _create_automail_template(automail_repo)
        _create_automail_schedule(automail_repo, tmpl_id)

        nc = NotificationCenter(db)
        nc.send_email = MagicMock(return_value=True)  # type: ignore[method-assign]

        engine = DunnerEngine(db, notification_center=nc)
        sent_count = engine.evaluate_all()
        assert sent_count >= 1, "Reminder should have been sent"

        # Verify reminder recorded
        reminder_count = invoice_repo.get_reminder_count(invoice_id)
        assert reminder_count >= 1, "Reminder not recorded"

        # ── Step 2: Mark invoice as Paid ────────────────────────────
        db.conn.execute(
            "UPDATE invoices SET status = 'Paid' WHERE id = ?", (invoice_id,),
        )
        db.conn.commit()

        # ── Step 3: Generate receipt ────────────────────────────────
        now = datetime.now().isoformat()
        receipt_data = {
            "receipt_type": "customer_payment",
            "payment_date": now[:10],
            "currency": "EUR",
            "company_name": "Operion Spedition GmbH",
            "received_from_name": "Dunner Client GmbH",
            "payment_method": "Bank Transfer",
            "invoice_reference": f"INV-DUN-{trip_id:04d}",
            "related_trip_id": trip_id,
            "amount": 2500.0,
            "vat_rate": 19.0,
        }

        with patch("services.invoicing.receipt_service.ReceiptGenerator.generate", return_value=os.path.join(
            tempfile.gettempdir(), "receipt_chain_test.pdf",
        )):
            svc = ReceiptService(db)
            receipt_number = svc._receipt_repo.get_next_number()
            receipt_data["receipt_number"] = receipt_number
            svc.generate_and_record(receipt_data)

        # Verify receipt persisted
        receipt_repo = ReceiptRepository(db)
        rows = receipt_repo._fetchall(
            "SELECT * FROM receipts WHERE related_trip_id = ? ORDER BY id DESC LIMIT 1",
            (trip_id,),
        )
        assert len(rows) >= 1, "Receipt not found in DB"
        receipt = rows[0]
        assert receipt["receipt_number"] == receipt_number
        assert receipt["related_trip_id"] == trip_id
        assert receipt["total"] > 0, "Receipt total should be calculated"
