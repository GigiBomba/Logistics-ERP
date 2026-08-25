"""Tests for payment_models.py — Payment create, batch grouping, payment status transitions."""
from __future__ import annotations

import pytest
from datetime import datetime
from pydantic import ValidationError
from models.payment_models import (
    PaymentProfileCreate,
    PaymentProfileResult,
    PaymentBatchRequest,
    PaymentBatchResult,
)


class TestPaymentProfileCreate:
    @pytest.mark.parametrize(
        "name, bank_name, iban, swift, currency, is_default",
        [
            ("Main Account", "BCR", "RO49BCR1234567890", "BUCUROBU", "EUR", True),
            ("Secondary", "BRD", "RO56BRD1234567890", "BRDEROBU", "RON", False),
            ("Fuel Card", "", "", "", "EUR", False),
        ],
    )
    def test_profile_create_valid(self, name, bank_name, iban, swift, currency, is_default):
        p = PaymentProfileCreate(
            name=name,
            bank_name=bank_name,
            iban=iban,
            swift=swift,
            currency=currency,
            is_default=is_default,
        )
        assert p.name == name
        assert p.currency == currency
        assert p.is_default == is_default

    def test_profile_create_defaults(self):
        p = PaymentProfileCreate(name="Default")
        assert p.bank_name == ""
        assert p.iban == ""
        assert p.swift == ""
        assert p.currency == "EUR"
        assert p.is_default is False


class TestPaymentProfileResult:
    def test_profile_result(self):
        r = PaymentProfileResult(
            id=1,
            name="Main",
            bank_name="BCR",
            iban="RO49BCR1234567890",
            swift="BUCUROBU",
            currency="EUR",
            is_default=True,
        )
        assert r.id == 1
        assert r.is_default is True


class TestPaymentBatchRequest:
    def test_batch_request_defaults(self):
        r = PaymentBatchRequest(profile_id=5)
        assert r.invoice_ids == []
        assert r.driver_ids == []
        assert r.start_date is None
        assert r.end_date is None

    @pytest.mark.parametrize(
        "invoice_ids, driver_ids",
        [
            ([1, 2, 3], []),
            ([], [100, 200]),
            ([4, 5], [300]),
        ],
    )
    def test_batch_request_with_ids(self, invoice_ids, driver_ids):
        r = PaymentBatchRequest(profile_id=10, invoice_ids=invoice_ids, driver_ids=driver_ids)
        assert r.invoice_ids == invoice_ids
        assert r.driver_ids == driver_ids

    def test_batch_request_with_dates(self):
        start = datetime(2026, 1, 1)
        end = datetime(2026, 6, 30)
        r = PaymentBatchRequest(profile_id=1, start_date=start, end_date=end)
        assert r.start_date == start
        assert r.end_date == end

    def test_batch_request_complete(self):
        start = datetime(2026, 3, 1)
        end = datetime(2026, 3, 31)
        r = PaymentBatchRequest(
            profile_id=7,
            invoice_ids=[10, 20],
            driver_ids=[30],
            start_date=start,
            end_date=end,
        )
        assert r.profile_id == 7
        assert len(r.invoice_ids) == 2
        assert len(r.driver_ids) == 1


class TestPaymentBatchResult:
    def test_batch_result(self):
        now = datetime.now()
        r = PaymentBatchResult(
            batch_id=42,
            file_path="/payments/batch_42.csv",
            row_count=15,
            total_amount=12500.50,
            currency="EUR",
            generated_at=now,
        )
        assert r.batch_id == 42
        assert r.row_count == 15
        assert r.total_amount == 12500.50
        assert r.currency == "EUR"

    def test_batch_result_zero_amount(self):
        now = datetime.now()
        r = PaymentBatchResult(
            batch_id=1,
            file_path="/payments/empty.csv",
            row_count=0,
            total_amount=0.0,
            currency="RON",
            generated_at=now,
        )
        assert r.total_amount == 0.0
        assert r.row_count == 0
