"""Tests for invoice_models.py — Invoice create (line items, VAT), required fields, status transitions."""
import pytest
from datetime import date
from pydantic import ValidationError
from models.invoice_models import (
    InvoiceLineItem,
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceFinalizeRequest,
    InvoiceResult,
)


class TestInvoiceLineItem:
    @pytest.mark.parametrize(
        "desc, qty, unit_price, vat_rate",
        [
            ("Transport fee", 1, 1200.0, 19.0),
            ("Extra stop", 2, 50.0, 9.0),
            ("Pallet fee", 10, 15.0, 5.0),
            ("Waiting time", 3.5, 40.0, 19.0),
            ("Discount", 1, -100.0, 19.0),
        ],
    )
    def test_line_item_valid(self, desc, qty, unit_price, vat_rate):
        li = InvoiceLineItem(description=desc, quantity=qty, unit_price=unit_price, vat_rate=vat_rate)
        assert li.description == desc
        assert li.quantity == qty
        assert li.unit_price == unit_price
        assert li.vat_rate == vat_rate

    def test_line_item_default_vat(self):
        li = InvoiceLineItem(description="Service", unit_price=1000.0)
        assert li.vat_rate == 19.0
        assert li.quantity == 1.0

    def test_line_item_totals_default_none(self):
        li = InvoiceLineItem(description="Test", unit_price=100.0)
        assert li.total_net is None
        assert li.total_vat is None
        assert li.total_gross is None

    def test_line_item_totals_set_explicitly(self):
        li = InvoiceLineItem(
            description="Test",
            unit_price=100.0,
            quantity=2,
            vat_rate=19.0,
            total_net=200.0,
            total_vat=38.0,
            total_gross=238.0,
        )
        assert li.total_net == 200.0
        assert li.total_vat == 38.0
        assert li.total_gross == 238.0


class TestInvoiceCreate:
    @pytest.mark.parametrize(
        "client_id, invoice_date, due_date, currency",
        [
            (1, date(2026, 1, 15), date(2026, 2, 15), "EUR"),
            (2, date(2026, 3, 1), date(2026, 3, 31), "USD"),
            (3, date(2026, 6, 10), date(2026, 6, 10), "RON"),
        ],
    )
    def test_invoice_create_valid(self, client_id, invoice_date, due_date, currency):
        inv = InvoiceCreate(
            client_id=client_id,
            invoice_date=invoice_date,
            due_date=due_date,
            currency=currency,
        )
        assert inv.client_id == client_id
        assert inv.invoice_date == invoice_date
        assert inv.due_date == due_date
        assert inv.currency == currency
        assert inv.line_items == []

    def test_due_date_before_invoice_date_raises(self):
        with pytest.raises(ValidationError, match="Due date must be on or after"):
            InvoiceCreate(
                client_id=1,
                invoice_date=date(2026, 6, 20),
                due_date=date(2026, 6, 19),
            )

    def test_due_date_equal_to_invoice_date_allowed(self):
        inv = InvoiceCreate(
            client_id=1,
            invoice_date=date(2026, 7, 1),
            due_date=date(2026, 7, 1),
        )
        assert inv.due_date == inv.invoice_date

    def test_invoice_create_with_line_items(self):
        items = [
            InvoiceLineItem(description="Transport", unit_price=500.0),
            InvoiceLineItem(description="Loading", quantity=2, unit_price=75.0, vat_rate=9.0),
        ]
        inv = InvoiceCreate(
            client_id=10,
            invoice_date=date(2026, 5, 1),
            due_date=date(2026, 6, 1),
            line_items=items,
            notes="Test invoice",
        )
        assert len(inv.line_items) == 2
        assert inv.notes == "Test invoice"
        assert inv.trip_id is None

    def test_missing_client_id_raises(self):
        with pytest.raises(ValidationError):
            InvoiceCreate(invoice_date=date.today(), due_date=date.today())

    def test_missing_dates_raises(self):
        with pytest.raises(ValidationError):
            InvoiceCreate(client_id=1)


class TestInvoiceUpdate:
    @pytest.mark.parametrize(
        "updates",
        [
            {"status": "finalized"},
            {"notes": "Updated notes", "status": "cancelled"},
            {"client_id": 99, "currency": "USD"},
        ],
    )
    def test_invoice_update_partial(self, updates):
        u = InvoiceUpdate(**updates)
        for k, v in updates.items():
            assert getattr(u, k) == v

    def test_invoice_update_all_optional(self):
        u = InvoiceUpdate()
        assert u.client_id is None
        assert u.status is None


class TestInvoiceFinalizeRequest:
    def test_finalize_defaults(self):
        r = InvoiceFinalizeRequest(invoice_id=5)
        assert r.invoice_id == 5
        assert r.send_email is False
        assert r.email_recipient == ""

    def test_finalize_with_email(self):
        r = InvoiceFinalizeRequest(invoice_id=5, send_email=True, email_recipient="client@example.com")
        assert r.send_email is True
        assert r.email_recipient == "client@example.com"


class TestInvoiceResult:
    @pytest.mark.parametrize(
        "status",
        ["draft", "finalized", "cancelled", "paid"],
    )
    def test_invoice_result_status(self, status):
        r = InvoiceResult(
            id=1,
            invoice_number="INV-001",
            client_id=10,
            client_name="Client A",
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 2, 1),
            currency="EUR",
            subtotal_net=1000.0,
            total_vat=190.0,
            total_gross=1190.0,
            status=status,
            notes="",
        )
        assert r.status == status

    def test_invoice_result_defaults(self):
        r = InvoiceResult(
            id=1,
            invoice_number="INV-001",
            client_id=10,
            client_name="Client A",
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 2, 1),
            currency="EUR",
            subtotal_net=1000.0,
            total_vat=190.0,
            total_gross=1190.0,
            status="draft",
            notes="",
        )
        assert r.trip_id is None
        assert r.trip_reference == ""
        assert r.pdf_path is None
        assert r.created_at is None

    def test_invoice_result_with_line_items(self):
        items = [InvoiceLineItem(description="A", unit_price=100.0)]
        r = InvoiceResult(
            id=2,
            invoice_number="INV-002",
            client_id=20,
            client_name="Client B",
            invoice_date=date(2026, 3, 1),
            due_date=date(2026, 4, 1),
            currency="EUR",
            line_items=items,
            subtotal_net=100.0,
            total_vat=19.0,
            total_gross=119.0,
            status="draft",
            notes="",
        )
        assert len(r.line_items) == 1
        assert r.line_items[0].description == "A"
