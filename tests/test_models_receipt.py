"""Tests for receipt_models.py — Receipt create/result, fiscal fields validation."""
import pytest
from datetime import date, datetime
from pydantic import ValidationError
from models.receipt_models import ReceiptLineItem, ReceiptCreate, ReceiptResult


class TestReceiptLineItem:
    @pytest.mark.parametrize(
        "desc, amount, qty",
        [
            ("Fuel", 450.50, 1.0),
            ("Toll", 25.0, 2.0),
            ("Parking", 15.0, 1.0),
            ("Maintenance", 1200.0, 1.0),
        ],
    )
    def test_line_item_valid(self, desc, amount, qty):
        li = ReceiptLineItem(description=desc, amount=amount, quantity=qty)
        assert li.description == desc
        assert li.amount == amount
        assert li.quantity == qty

    def test_line_item_default_quantity(self):
        li = ReceiptLineItem(description="Service", amount=100.0)
        assert li.quantity == 1.0


class TestReceiptCreate:
    @pytest.mark.parametrize(
        "client_id, receipt_date, currency",
        [
            (1, date(2026, 6, 15), "EUR"),
            (2, date(2026, 6, 20), "RON"),
            (3, date(2026, 7, 1), "USD"),
        ],
    )
    def test_receipt_create_valid(self, client_id, receipt_date, currency):
        r = ReceiptCreate(client_id=client_id, receipt_date=receipt_date, currency=currency)
        assert r.client_id == client_id
        assert r.receipt_date == receipt_date
        assert r.currency == currency

    def test_receipt_create_defaults(self):
        r = ReceiptCreate(client_id=1, receipt_date=date.today())
        assert r.currency == "EUR"
        assert r.items == []
        assert r.total_amount is None
        assert r.notes == ""
        assert r.trip_id is None
        assert r.invoice_id is None
        assert r.vehicle_id is None

    def test_receipt_create_with_items(self):
        items = [
            ReceiptLineItem(description="Fuel", amount=350.0),
            ReceiptLineItem(description="Oil", amount=120.0, quantity=2),
        ]
        r = ReceiptCreate(
            client_id=5,
            receipt_date=date(2026, 7, 10),
            items=items,
            total_amount=470.0,
            notes="Fuel receipt",
            trip_id=42,
        )
        assert len(r.items) == 2
        assert r.total_amount == 470.0
        assert r.trip_id == 42

    def test_receipt_with_vehicle_link(self):
        r = ReceiptCreate(
            client_id=1,
            receipt_date=date.today(),
            vehicle_id=10,
            invoice_id=200,
        )
        assert r.vehicle_id == 10
        assert r.invoice_id == 200


class TestReceiptResult:
    def test_receipt_result_minimal(self):
        now = datetime.now()
        items = [ReceiptLineItem(description="Fuel", amount=100.0)]
        r = ReceiptResult(
            id=1,
            receipt_number="REC-001",
            client_id=10,
            client_name="Client A",
            receipt_date=date(2026, 1, 15),
            currency="EUR",
            items=items,
            total_amount=100.0,
            created_at=now,
        )
        assert r.id == 1
        assert r.receipt_number == "REC-001"
        assert r.total_amount == 100.0

    def test_receipt_result_with_relations(self):
        items = [ReceiptLineItem(description="Test", amount=50.0)]
        r = ReceiptResult(
            id=2,
            receipt_number="REC-002",
            client_id=20,
            client_name="Client B",
            trip_id=99,
            invoice_id=55,
            vehicle_id=7,
            vehicle_plate="AB123CD",
            receipt_date=date(2026, 1, 20),
            currency="RON",
            items=items,
            total_amount=50.0,
            pdf_path="/receipts/rec_002.pdf",
        )
        assert r.trip_id == 99
        assert r.invoice_id == 55
        assert r.vehicle_id == 7
        assert r.vehicle_plate == "AB123CD"
        assert r.pdf_path == "/receipts/rec_002.pdf"
