"""Tests for backend/schemas/invoice.py, receipt.py, and cmr.py —
InvoiceGenerateRequest, InvoiceSendEmailRequest, ReceiptGenerateRequest,
CmrGenerateRequest."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.cmr import CmrGenerateRequest
from backend.schemas.invoice import InvoiceGenerateRequest, InvoiceSendEmailRequest
from backend.schemas.receipt import ReceiptGenerateRequest


# ── InvoiceGenerateRequest ─────────────────────────────────────────────────────


class TestInvoiceGenerateRequest:
    """trip_id (gt=0), mode (max_length=50), language (max_length=5),
    additional_notes (max_length=2000), extra="forbid"."""

    VALID: Dict[str, Any] = {"trip_id": 42}

    # ── trip_id gt=0 boundary ──

    def test_valid_trip_id_positive(self):
        inst = InvoiceGenerateRequest(trip_id=1)
        assert inst.trip_id == 1

    def test_trip_id_gt_0_boundary_one(self):
        """trip_id=1 — the minimum valid value."""
        inst = InvoiceGenerateRequest(trip_id=1)
        assert inst.trip_id == 1

    def test_trip_id_zero_raises(self):
        """trip_id=0 — not greater than 0."""
        with pytest.raises(ValidationError):
            InvoiceGenerateRequest(trip_id=0)

    def test_trip_id_negative_raises(self):
        with pytest.raises(ValidationError):
            InvoiceGenerateRequest(trip_id=-1)

    def test_trip_id_large_positive(self):
        inst = InvoiceGenerateRequest(trip_id=999999)
        assert inst.trip_id == 999999

    def test_trip_id_none_raises(self):
        with pytest.raises(ValidationError):
            InvoiceGenerateRequest(trip_id=None)  # type: ignore[arg-type]

    def test_trip_id_missing_raises(self):
        with pytest.raises(ValidationError):
            InvoiceGenerateRequest()  # type: ignore[call-arg]

    def test_trip_id_type_mismatch_raises(self):
        with pytest.raises(ValidationError):
            InvoiceGenerateRequest(trip_id="abc")  # type: ignore[arg-type]

    # ── mode ──

    def test_mode_default(self):
        inst = InvoiceGenerateRequest(trip_id=1)
        assert inst.mode == "client"

    def test_mode_max_length_exact(self):
        mode = "a" * 50
        inst = InvoiceGenerateRequest(trip_id=1, mode=mode)
        assert inst.mode == mode

    def test_mode_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            InvoiceGenerateRequest(trip_id=1, mode="a" * 51)

    def test_mode_empty_is_valid(self):
        """No min_length, so empty is allowed."""
        inst = InvoiceGenerateRequest(trip_id=1, mode="")
        assert inst.mode == ""

    # ── language ──

    def test_language_default(self):
        inst = InvoiceGenerateRequest(trip_id=1)
        assert inst.language == "en"

    def test_language_max_length_exact(self):
        inst = InvoiceGenerateRequest(trip_id=1, language="a" * 5)
        assert inst.language == "a" * 5

    def test_language_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            InvoiceGenerateRequest(trip_id=1, language="a" * 6)

    def test_language_empty_is_valid(self):
        inst = InvoiceGenerateRequest(trip_id=1, language="")
        assert inst.language == ""

    # ── additional_notes ──

    def test_additional_notes_none(self):
        inst = InvoiceGenerateRequest(trip_id=1)
        assert inst.additional_notes is None

    def test_additional_notes_max_length_exact(self):
        notes = "x" * 2000
        inst = InvoiceGenerateRequest(trip_id=1, additional_notes=notes)
        assert inst.additional_notes == notes

    def test_additional_notes_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            InvoiceGenerateRequest(trip_id=1, additional_notes="x" * 2001)

    def test_additional_notes_empty_string(self):
        inst = InvoiceGenerateRequest(trip_id=1, additional_notes="")
        assert inst.additional_notes == ""

    # ── invoice_number ──

    def test_invoice_number_none(self):
        inst = InvoiceGenerateRequest(trip_id=1)
        assert inst.invoice_number is None

    def test_invoice_number_max_length_exact(self):
        inv = "x" * 100
        inst = InvoiceGenerateRequest(trip_id=1, invoice_number=inv)
        assert inst.invoice_number == inv

    def test_invoice_number_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            InvoiceGenerateRequest(trip_id=1, invoice_number="x" * 101)

    # ── extra=forbid ──

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            InvoiceGenerateRequest(trip_id=1, unknown_field="x")  # type: ignore[call-arg]

    # ── trip data optional fields ──

    def test_optional_trip_data_fields(self):
        inst = InvoiceGenerateRequest(
            trip_id=1,
            client_name="Client A",
            total_price_eur=1500.50,
            client_id=10,
            created_at="2025-06-01T12:00:00Z",
        )
        assert inst.client_name == "Client A"
        assert inst.total_price_eur == 1500.50
        assert inst.client_id == 10
        assert inst.created_at == "2025-06-01T12:00:00Z"

    def test_trip_data_defaults(self):
        inst = InvoiceGenerateRequest(trip_id=1)
        assert inst.client_name == ""
        assert inst.total_price_eur == 0.0
        assert inst.client_id is None
        assert inst.created_at is None


# ── InvoiceSendEmailRequest ────────────────────────────────────────────────────


class TestInvoiceSendEmailRequest:
    """recipient_email (max_length=255), trip_id (optional), trip_data (optional),
    mode (default="client", max_length=50), subject (max_length=255),
    message (max_length=2000), extra="forbid"."""

    VALID: Dict[str, Any] = {"recipient_email": "user@example.com"}

    def test_minimal_valid(self):
        inst = InvoiceSendEmailRequest(**self.VALID)
        assert inst.recipient_email == "user@example.com"
        assert inst.mode == "client"
        assert inst.trip_id is None
        assert inst.trip_data is None
        assert inst.subject is None
        assert inst.message is None

    def test_all_fields(self):
        inst = InvoiceSendEmailRequest(
            recipient_email="a@b.com",
            trip_id=10,
            trip_data={"key": "val"},
            mode="custom",
            subject="Invoice",
            message="Please find attached.",
        )
        assert inst.trip_id == 10
        assert inst.trip_data == {"key": "val"}
        assert inst.subject == "Invoice"
        assert inst.message == "Please find attached."

    # ── recipient_email ──

    def test_recipient_email_max_length_exact(self):
        email = "a@" + "b" * 251 + ".c"
        assert len(email) == 255, f"expected 255, got {len(email)}"
        inst = InvoiceSendEmailRequest(recipient_email=email)
        assert inst.recipient_email == email

    def test_recipient_email_over_max_length_raises(self):
        email = "a@" + "b" * 252 + ".c"
        assert len(email) == 256, f"expected 256, got {len(email)}"
        with pytest.raises(ValidationError):
            InvoiceSendEmailRequest(recipient_email=email)

    def test_recipient_email_empty_raises(self):
        """Required field — empty string counts as present, but max_length permits it."""
        inst = InvoiceSendEmailRequest(recipient_email="")
        assert inst.recipient_email == ""

    def test_recipient_email_missing_raises(self):
        with pytest.raises(ValidationError):
            InvoiceSendEmailRequest()  # type: ignore[call-arg]

    # ── subject ──

    def test_subject_max_length_exact(self):
        inst = InvoiceSendEmailRequest(recipient_email="a@b.com", subject="x" * 255)
        assert inst.subject == "x" * 255

    def test_subject_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            InvoiceSendEmailRequest(recipient_email="a@b.com", subject="x" * 256)

    def test_subject_none(self):
        inst = InvoiceSendEmailRequest(recipient_email="a@b.com")
        assert inst.subject is None

    def test_subject_empty_string(self):
        inst = InvoiceSendEmailRequest(recipient_email="a@b.com", subject="")
        assert inst.subject == ""

    # ── message ──

    def test_message_max_length_exact(self):
        inst = InvoiceSendEmailRequest(recipient_email="a@b.com", message="x" * 2000)
        assert inst.message == "x" * 2000

    def test_message_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            InvoiceSendEmailRequest(recipient_email="a@b.com", message="x" * 2001)

    def test_message_none(self):
        inst = InvoiceSendEmailRequest(recipient_email="a@b.com")
        assert inst.message is None

    def test_message_empty_string(self):
        inst = InvoiceSendEmailRequest(recipient_email="a@b.com", message="")
        assert inst.message == ""

    # ── mode ──

    def test_mode_max_length_exact(self):
        inst = InvoiceSendEmailRequest(recipient_email="a@b.com", mode="a" * 50)
        assert inst.mode == "a" * 50

    def test_mode_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            InvoiceSendEmailRequest(recipient_email="a@b.com", mode="a" * 51)

    # ── extra=forbid ──

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            InvoiceSendEmailRequest(recipient_email="a@b.com", unknown="x")  # type: ignore[call-arg]


# ── ReceiptGenerateRequest ─────────────────────────────────────────────────────


class TestReceiptGenerateRequest:
    """receipt_data (optional), receipt_number (max_length=100),
    receipt_type (default="payment", max_length=50), currency (max_length=3),
    amount (float, default=0.0), total (optional), vat_rate (optional),
    vat_amount (optional), notes (max_length=2000), language (max_length=5),
    extra="forbid"."""

    def test_defaults(self):
        inst = ReceiptGenerateRequest()
        assert inst.receipt_data is None
        assert inst.receipt_number is None
        assert inst.receipt_type == "payment"
        assert inst.currency == "EUR"
        assert inst.amount == 0.0
        assert inst.total is None
        assert inst.vat_rate is None
        assert inst.vat_amount is None
        assert inst.notes is None
        assert inst.language == "en"

    def test_all_fields(self):
        inst = ReceiptGenerateRequest(
            receipt_data={"item": "test"},
            receipt_number="RCP-001",
            receipt_type="refund",
            issue_date="2025-06-01",
            payment_date="2025-06-02",
            currency="USD",
            amount=100.50,
            total=119.0,
            vat_rate=0.19,
            vat_amount=19.00,
            notes="Paid",
            language="fr",
        )
        assert inst.receipt_data == {"item": "test"}
        assert inst.receipt_number == "RCP-001"
        assert inst.receipt_type == "refund"
        assert inst.issue_date == "2025-06-01"
        assert inst.payment_date == "2025-06-02"
        assert inst.currency == "USD"
        assert inst.amount == 100.50
        assert inst.total == 119.0
        assert inst.vat_rate == 0.19
        assert inst.vat_amount == 19.00
        assert inst.notes == "Paid"
        assert inst.language == "fr"

    # ── amount ──

    def test_amount_negative(self):
        """No constraint — negative amounts accepted."""
        inst = ReceiptGenerateRequest(amount=-10.0)
        assert inst.amount == -10.0

    def test_amount_zero(self):
        inst = ReceiptGenerateRequest(amount=0.0)
        assert inst.amount == 0.0

    def test_amount_positive(self):
        inst = ReceiptGenerateRequest(amount=999.99)
        assert inst.amount == 999.99

    def test_amount_none_raises(self):
        """Pydantic v2 does not coerce None to the default for float."""
        with pytest.raises(ValidationError):
            ReceiptGenerateRequest(amount=None)  # type: ignore[arg-type]

    # ── Vat_rate ──

    def test_vat_rate_none(self):
        inst = ReceiptGenerateRequest()
        assert inst.vat_rate is None

    def test_vat_rate_positive(self):
        inst = ReceiptGenerateRequest(vat_rate=0.19)
        assert inst.vat_rate == 0.19

    def test_vat_rate_negative(self):
        """No constraint — negative VAT accepted."""
        inst = ReceiptGenerateRequest(vat_rate=-0.05)
        assert inst.vat_rate == -0.05

    def test_vat_rate_zero(self):
        inst = ReceiptGenerateRequest(vat_rate=0.0)
        assert inst.vat_rate == 0.0

    # ── total ──

    def test_total_none(self):
        inst = ReceiptGenerateRequest()
        assert inst.total is None

    def test_total_negative(self):
        inst = ReceiptGenerateRequest(total=-5.0)
        assert inst.total == -5.0

    # ── max_length fields ──

    def test_receipt_number_max_length_exact(self):
        inst = ReceiptGenerateRequest(receipt_number="x" * 100)
        assert inst.receipt_number == "x" * 100

    def test_receipt_number_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            ReceiptGenerateRequest(receipt_number="x" * 101)

    def test_receipt_type_max_length_exact(self):
        inst = ReceiptGenerateRequest(receipt_type="a" * 50)
        assert inst.receipt_type == "a" * 50

    def test_receipt_type_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            ReceiptGenerateRequest(receipt_type="a" * 51)

    def test_currency_max_length_exact(self):
        inst = ReceiptGenerateRequest(currency="ABC")
        assert inst.currency == "ABC"

    def test_currency_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            ReceiptGenerateRequest(currency="ABCD")

    def test_notes_max_length_exact(self):
        inst = ReceiptGenerateRequest(notes="x" * 2000)
        assert inst.notes == "x" * 2000

    def test_notes_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            ReceiptGenerateRequest(notes="x" * 2001)

    def test_language_max_length_exact(self):
        inst = ReceiptGenerateRequest(language="a" * 5)
        assert inst.language == "a" * 5

    def test_language_over_max_length_raises(self):
        with pytest.raises(ValidationError):
            ReceiptGenerateRequest(language="a" * 6)

    # ── extra=forbid ──

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            ReceiptGenerateRequest(unknown="x")  # type: ignore[call-arg]


# ── CmrGenerateRequest ─────────────────────────────────────────────────────────


class TestCmrGenerateRequest:
    """trip_data: Dict[str, Any] (required), extra="forbid"."""

    def test_valid(self):
        inst = CmrGenerateRequest(trip_data={"order_id": "ORD-001", "goods": "Electronics"})
        assert inst.trip_data == {"order_id": "ORD-001", "goods": "Electronics"}

    def test_empty_dict(self):
        inst = CmrGenerateRequest(trip_data={})
        assert inst.trip_data == {}

    def test_missing_trip_data_raises(self):
        with pytest.raises(ValidationError):
            CmrGenerateRequest()  # type: ignore[call-arg]

    def test_none_trip_data_raises(self):
        with pytest.raises(ValidationError):
            CmrGenerateRequest(trip_data=None)  # type: ignore[arg-type]

    def test_non_dict_raises(self):
        with pytest.raises(ValidationError):
            CmrGenerateRequest(trip_data="not-a-dict")  # type: ignore[arg-type]

    def test_type_mismatch_list_raises(self):
        """List is not Dict[str, Any]."""
        with pytest.raises(ValidationError):
            CmrGenerateRequest(trip_data=[1, 2, 3])  # type: ignore[arg-type]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            CmrGenerateRequest(trip_data={"a": 1}, extra_field="x")  # type: ignore[call-arg]

    def test_mixed_value_types(self):
        """Dict[str, Any] accepts mixed value types."""
        inst = CmrGenerateRequest(trip_data={"str": "hello", "int": 42, "float": 3.14, "list": [1], "none": None})
        assert inst.trip_data["str"] == "hello"
        assert inst.trip_data["int"] == 42
        assert inst.trip_data["none"] is None
