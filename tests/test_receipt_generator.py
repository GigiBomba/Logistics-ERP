"""Tests for ReceiptGenerator."""
import os
from unittest.mock import MagicMock, patch

import pytest

from services.invoicing.receipt_generator import ReceiptGenerator


@pytest.fixture
def generator():
    with patch("services.invoicing.receipt_generator.data_path",
               return_value=os.path.join(os.path.dirname(__file__), "..", "data", "documents", "receipts")):
        with patch("services.invoicing.receipt_generator.os.makedirs"):
            with patch("services.invoicing.receipt_generator.load_company_config",
                       return_value={"company_name": "Test Corp", "cui": "RO123",
                                     "reg_number": "J123", "address": "Addr",
                                     "phone": "0712345678", "email": "t@t.com",
                                     "logo_path": "", "company_color": "#6366f1",
                                     "signature_path": "", "stamp_path": ""}):
                gen = ReceiptGenerator()
                return gen


def test_generate_basic_receipt(generator):
    data = {
        "receipt_number": "RCT-000001",
        "issue_date": "2026-06-01",
        "payment_date": "2026-06-01",
        "currency": "EUR",
        "received_from_name": "Client A",
        "received_from_address": "Address A",
        "received_by_name": "Our Company",
        "amount": 1000.0,
        "vat_rate": 19.0,
        "total": 1190.0,
        "purpose": "Transport services",
    }
    path = generator.generate(data)
    assert path is not None
    assert path.endswith(".pdf")


def test_generate_with_logistics_info(generator):
    data = {
        "receipt_number": "RCT-000002",
        "issue_date": "2026-06-01",
        "currency": "EUR",
        "received_from_name": "Client B",
        "amount": 500.0,
        "total": 500.0,
        "pickup_location": "Berlin",
        "delivery_location": "Paris",
        "related_trip": "TRIP-42",
    }
    path = generator.generate(data)
    assert path is not None


def test_generate_with_custom_company(generator):
    data = {
        "receipt_number": "RCT-000003",
        "issue_date": "2026-06-01",
        "currency": "EUR",
        "received_from_name": "Client C",
        "amount": 250.0,
        "total": 250.0,
        "company_config": {
            "company_name": "Custom Co",
            "cui": "RO999",
            "address": "Custom Address",
            "phone": "0711111111",
            "email": "c@c.com",
        },
    }
    path = generator.generate(data)
    assert path is not None


def test_generate_with_optional_fields(generator):
    data = {
        "receipt_number": "RCT-000004",
        "issue_date": "2026-06-01",
        "payment_method": "Bank Transfer",
        "reference_number": "REF-123",
        "transaction_id": "TXN-456",
        "currency": "EUR",
        "received_from_name": "Client D",
        "received_from_vat": "VAT123",
        "amount": 2000.0,
        "vat_rate": 19.0,
        "notes": "Payment for invoice INV-001",
    }
    path = generator.generate(data)
    assert path is not None


def test_tr_helper(generator):
    result = ReceiptGenerator._tr("receipt.title", "en")
    assert result is not None
    assert isinstance(result, str)
