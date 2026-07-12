"""Tests for backend/schemas/payment_profile.py — all payment-related schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.payment_profile import (
    PaymentBatchItem,
    PaymentBatchRequest,
    PaymentProfileBase,
    PaymentProfileCreate,
    PaymentProfileResponse,
    PaymentProfileUpdate,
    PaymentRecipientOut,
)


# ── PaymentProfileBase ────────────────────────────────────────────────────────


class TestPaymentProfileBase:
    """All fields have defaults, extra="forbid"."""

    def test_defaults(self):
        inst = PaymentProfileBase()
        assert inst.profile_name == ""
        assert inst.recipient_type == "custom"
        assert inst.bank_name == ""
        assert inst.bank_account == ""
        assert inst.bank_code == ""
        assert inst.bank_bic == ""
        assert inst.iban == ""
        assert inst.payment_reference == ""
        assert inst.contact_name == ""
        assert inst.contact_email == ""
        assert inst.contact_phone == ""
        assert inst.notes == ""
        assert inst.is_active is True

    def test_all_fields(self):
        inst = PaymentProfileBase(
            profile_name="Main Supplier",
            recipient_type="client",
            bank_name="Deutsche Bank",
            bank_account="DE1234567890",
            bank_code="12345678",
            bank_bic="DEUTDEFF",
            iban="DE89370400440532013000",
            payment_reference="INV-001",
            contact_name="Max Mustermann",
            contact_email="max@example.com",
            contact_phone="+49123456789",
            notes="Preferred payment method",
            is_active=True,
        )
        assert inst.profile_name == "Main Supplier"
        assert inst.iban == "DE89370400440532013000"

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            PaymentProfileBase(unknown="x")  # type: ignore[call-arg]


# ── PaymentProfileCreate ──────────────────────────────────────────────────────


class TestPaymentProfileCreate:
    """Extends PaymentProfileBase, extra="allow" — unknown fields are permitted."""

    def test_valid(self):
        inst = PaymentProfileCreate(profile_name="New Profile")
        assert inst.profile_name == "New Profile"

    def test_extra_field_allowed(self):
        inst = PaymentProfileCreate(profile_name="P1", extra_field="value")
        assert inst.extra_field == "value"  # type: ignore[attr-defined]


# ── PaymentProfileResponse ────────────────────────────────────────────────────


class TestPaymentProfileResponse:
    """Extends PaymentProfileBase, adds id (required), created_at (default ""), updated_at (default "")."""

    def test_valid(self):
        inst = PaymentProfileResponse(id=1)
        assert inst.id == 1
        assert inst.created_at == ""
        assert inst.updated_at == ""
        assert inst.profile_name == ""

    def test_all_fields(self):
        inst = PaymentProfileResponse(
            id=1, profile_name="P1", recipient_type="driver",
            created_at="2025-01-01T00:00:00Z", updated_at="2025-01-02T00:00:00Z",
        )
        assert inst.created_at == "2025-01-01T00:00:00Z"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            PaymentProfileResponse()  # type: ignore[call-arg]

    def test_extra_field_ignored(self):
        """extra="ignore"."""
        inst = PaymentProfileResponse(id=1, unknown="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "unknown")


# ── PaymentProfileUpdate ──────────────────────────────────────────────────────


class TestPaymentProfileUpdate:
    """All fields Optional, extra="forbid"."""

    def test_empty(self):
        inst = PaymentProfileUpdate()
        assert inst.profile_name is None
        assert inst.iban is None

    def test_partial(self):
        inst = PaymentProfileUpdate(profile_name="Updated", iban="DE89370400440532013000")
        assert inst.profile_name == "Updated"
        assert inst.iban == "DE89370400440532013000"
        assert inst.bank_name is None

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            PaymentProfileUpdate(profile_name="x", unknown="y")  # type: ignore[call-arg]


# ── PaymentRecipientOut ───────────────────────────────────────────────────────


class TestPaymentRecipientOut:
    """recipient_id, recipient_type, recipient_name required; bank fields default empty."""

    def test_required_only(self):
        inst = PaymentRecipientOut(recipient_id=1, recipient_type="client", recipient_name="Acme")
        assert inst.recipient_id == 1
        assert inst.recipient_type == "client"
        assert inst.recipient_name == "Acme"
        assert inst.bank_name == ""
        assert inst.iban == ""

    def test_all_fields(self):
        inst = PaymentRecipientOut(
            recipient_id=1, recipient_type="driver", recipient_name="John",
            bank_name="Bank", bank_account="ACC", bank_code="CODE",
            bank_bic="BIC", iban="IBAN", payment_reference="REF",
        )
        assert inst.bank_bic == "BIC"

    def test_missing_recipient_id_raises(self):
        with pytest.raises(ValidationError):
            PaymentRecipientOut(recipient_type="c", recipient_name="n")  # type: ignore[call-arg]

    def test_missing_recipient_type_raises(self):
        with pytest.raises(ValidationError):
            PaymentRecipientOut(recipient_id=1, recipient_name="n")  # type: ignore[call-arg]

    def test_missing_recipient_name_raises(self):
        with pytest.raises(ValidationError):
            PaymentRecipientOut(recipient_id=1, recipient_type="c")  # type: ignore[call-arg]

    def test_extra_field_ignored(self):
        """extra="ignore"."""
        inst = PaymentRecipientOut(recipient_id=1, recipient_type="c", recipient_name="n", unknown="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "unknown")


# ── PaymentBatchItem ──────────────────────────────────────────────────────────


class TestPaymentBatchItem:
    """recipient_id, recipient_type, recipient_name required; amount/currency defaults."""

    def test_required_only(self):
        inst = PaymentBatchItem(recipient_id=1, recipient_type="client", recipient_name="Acme")
        assert inst.amount == 0.0
        assert inst.currency == "EUR"
        assert inst.payment_reference == ""

    def test_all_fields(self):
        inst = PaymentBatchItem(
            recipient_id=1, recipient_type="driver", recipient_name="John",
            bank_name="Bank", bank_account="ACC", bank_code="CODE",
            bank_bic="BIC", iban="IBAN", amount=1500.0, currency="USD",
            payment_reference="REF",
        )
        assert inst.amount == 1500.0
        assert inst.currency == "USD"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            PaymentBatchItem(recipient_type="c")  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            PaymentBatchItem(recipient_id=1, recipient_type="c", recipient_name="n", bad="x")  # type: ignore[call-arg]


# ── PaymentBatchRequest ───────────────────────────────────────────────────────


class TestPaymentBatchRequest:
    """items (required list of PaymentBatchItem), batch_name (default "")."""

    def test_with_items(self):
        item = PaymentBatchItem(recipient_id=1, recipient_type="client", recipient_name="Acme")
        inst = PaymentBatchRequest(items=[item])
        assert len(inst.items) == 1
        assert inst.items[0].recipient_name == "Acme"
        assert inst.batch_name == ""

    def test_with_batch_name(self):
        item = PaymentBatchItem(recipient_id=1, recipient_type="client", recipient_name="Acme")
        inst = PaymentBatchRequest(items=[item], batch_name="March payments")
        assert inst.batch_name == "March payments"

    def test_empty_items(self):
        """items is a list — empty list is valid."""
        inst = PaymentBatchRequest(items=[])
        assert inst.items == []

    def test_missing_items_raises(self):
        with pytest.raises(ValidationError):
            PaymentBatchRequest()  # type: ignore[call-arg]

    def test_invalid_item_in_list_raises(self):
        with pytest.raises(ValidationError):
            PaymentBatchRequest(items=[{"invalid": "data"}])  # type: ignore[list-item]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            PaymentBatchRequest(items=[], extra="x")  # type: ignore[call-arg]
