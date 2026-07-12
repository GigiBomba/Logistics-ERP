"""Tests for backend/schemas/registration.py — RegistrationRequest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.registration import RegistrationRequest


class TestRegistrationRequest:
    """email (required), password (min_length=6), display_name (default ""), company_name (min_length=1)."""

    def test_valid(self):
        inst = RegistrationRequest(
            email="user@company.com",
            password="secret123",
            display_name="John Doe",
            company_name="Acme Corp",
        )
        assert inst.email == "user@company.com"
        assert inst.password == "secret123"
        assert inst.display_name == "John Doe"
        assert inst.company_name == "Acme Corp"

    def test_minimal(self):
        """company_name min_length=1 means at least 1 char, but password must be >= 6."""
        inst = RegistrationRequest(email="a@b.com", password="123456", company_name="A")
        assert inst.display_name == ""
        assert inst.company_name == "A"

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            RegistrationRequest(password="123456", company_name="Acme")  # type: ignore[call-arg]

    def test_missing_password_raises(self):
        with pytest.raises(ValidationError):
            RegistrationRequest(email="a@b.com", company_name="Acme")  # type: ignore[call-arg]

    def test_missing_company_name_raises(self):
        with pytest.raises(ValidationError):
            RegistrationRequest(email="a@b.com", password="123456")  # type: ignore[call-arg]

    def test_password_too_short_raises(self):
        with pytest.raises(ValidationError):
            RegistrationRequest(email="a@b.com", password="12345", company_name="Acme")

    def test_password_exactly_6_chars(self):
        inst = RegistrationRequest(email="a@b.com", password="123456", company_name="Acme")
        assert inst.password == "123456"

    def test_empty_company_name_raises(self):
        with pytest.raises(ValidationError):
            RegistrationRequest(email="a@b.com", password="123456", company_name="")

    def test_empty_email_allowed_by_schema(self):
        """No format validation — any string is accepted for email."""
        inst = RegistrationRequest(email="", password="123456", company_name="A")
        assert inst.email == ""

    def test_extra_field_ignored(self):
        """Pydantic v2 default extra="ignore" — extra fields are silently dropped."""
        inst = RegistrationRequest(email="a@b.com", password="123456", company_name="A", extra="x")
        assert not hasattr(inst, "extra")
