"""Tests for proforma_models.py — Proforma invoice schema, conversion to final invoice flags."""
import pytest
from datetime import date, datetime
from pydantic import ValidationError
from models.proforma_models import ProformaCreate, ProformaResult


class TestProformaCreate:
    @pytest.mark.parametrize(
        "client_id, issue_date, valid_until, currency",
        [
            (1, date(2026, 6, 1), date(2026, 7, 1), "EUR"),
            (2, date(2026, 6, 15), date(2026, 7, 15), "RON"),
            (3, date(2026, 7, 1), date(2026, 8, 1), "USD"),
        ],
    )
    def test_proforma_create_valid(self, client_id, issue_date, valid_until, currency):
        p = ProformaCreate(
            client_id=client_id,
            issue_date=issue_date,
            valid_until=valid_until,
            currency=currency,
        )
        assert p.client_id == client_id
        assert p.issue_date == issue_date
        assert p.valid_until == valid_until
        assert p.currency == currency

    def test_proforma_create_defaults(self):
        p = ProformaCreate(client_id=1, issue_date=date.today(), valid_until=date(2026, 8, 1))
        assert p.currency == "EUR"
        assert p.items == []
        assert p.notes == ""
        assert p.trip_id is None

    def test_proforma_create_with_items(self):
        items = [
            {"description": "Transport", "quantity": 1, "unit_price": 1500.0},
            {"description": "Extra stop", "quantity": 2, "unit_price": 75.0},
        ]
        p = ProformaCreate(
            client_id=5,
            issue_date=date(2026, 5, 1),
            valid_until=date(2026, 6, 1),
            items=items,
            notes="Proforma for May trips",
            trip_id=100,
        )
        assert len(p.items) == 2
        assert p.notes == "Proforma for May trips"
        assert p.trip_id == 100

    def test_proforma_create_empty_items(self):
        p = ProformaCreate(client_id=1, issue_date=date.today(), valid_until=date.today())
        assert p.items == []


class TestProformaResult:
    def test_proforma_result_minimal(self):
        r = ProformaResult(
            id=1,
            proforma_number="PRO-001",
            client_id=10,
            client_name="Client A",
            issue_date=date(2026, 6, 1),
            valid_until=date(2026, 7, 1),
            currency="EUR",
            total_amount=1500.0,
            status="draft",
        )
        assert r.id == 1
        assert r.proforma_number == "PRO-001"
        assert r.total_amount == 1500.0

    def test_proforma_result_defaults(self):
        r = ProformaResult(
            id=2,
            proforma_number="PRO-002",
            client_id=20,
            client_name="Client B",
            issue_date=date(2026, 6, 15),
            valid_until=date(2026, 7, 15),
            currency="RON",
            total_amount=3000.0,
            status="draft",
        )
        assert r.notes == ""
        assert r.pdf_path is None
        assert r.created_at is None
        assert r.trip_id is None

    def test_proforma_result_full(self):
        now = datetime.now()
        r = ProformaResult(
            id=3,
            proforma_number="PRO-003",
            client_id=30,
            client_name="Client C",
            trip_id=200,
            issue_date=date(2026, 5, 1),
            valid_until=date(2026, 6, 1),
            currency="EUR",
            total_amount=5000.0,
            status="converted",
            notes="Converted to invoice",
            pdf_path="/proformas/pro_003.pdf",
            created_at=now,
        )
        assert r.trip_id == 200
        assert r.status == "converted"
        assert r.pdf_path == "/proformas/pro_003.pdf"
