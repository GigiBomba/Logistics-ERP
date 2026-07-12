"""Tests for backend/schemas/user.py — UserCreateRequest, UserUpdateRequest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.user import UserCreateRequest, UserUpdateRequest


# ── UserCreateRequest ─────────────────────────────────────────────────────────


class TestUserCreateRequest:
    """email (required), password (min_length=6), role (required), display_name (default "")."""

    def test_valid(self):
        inst = UserCreateRequest(email="user@example.com", password="secret123", role="dispatcher")
        assert inst.email == "user@example.com"
        assert inst.password == "secret123"
        assert inst.role == "dispatcher"
        assert inst.display_name == ""

    def test_with_display_name(self):
        inst = UserCreateRequest(email="a@b.com", password="123456", role="driver", display_name="John")
        assert inst.display_name == "John"

    def test_role_driver(self):
        inst = UserCreateRequest(email="d@d.com", password="abcdef", role="driver")
        assert inst.role == "driver"

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            UserCreateRequest(password="123456", role="dispatcher")  # type: ignore[call-arg]

    def test_missing_role_raises(self):
        with pytest.raises(ValidationError):
            UserCreateRequest(email="a@b.com", password="123456")  # type: ignore[call-arg]

    def test_password_too_short_raises(self):
        with pytest.raises(ValidationError):
            UserCreateRequest(email="a@b.com", password="12345", role="dispatcher")

    def test_empty_password_raises(self):
        with pytest.raises(ValidationError):
            UserCreateRequest(email="a@b.com", password="", role="dispatcher")

    def test_password_exactly_6_chars(self):
        inst = UserCreateRequest(email="a@b.com", password="123456", role="dispatcher")
        assert inst.password == "123456"

    def test_extra_field_ignored(self):
        """Pydantic v2 default extra="ignore" — extra fields are silently dropped."""
        inst = UserCreateRequest(email="a@b.com", password="123456", role="dispatcher", extra_field="x")
        assert not hasattr(inst, "extra_field")

    def test_empty_email_allowed(self):
        """No format validation on email — empty string is accepted."""
        inst = UserCreateRequest(email="", password="123456", role="driver")
        assert inst.email == ""


# ── UserUpdateRequest ─────────────────────────────────────────────────────────


class TestUserUpdateRequest:
    """All fields Optional; display_name, is_active, password (min_length=6), email."""

    def test_empty(self):
        inst = UserUpdateRequest()
        assert inst.display_name is None
        assert inst.is_active is None
        assert inst.password is None
        assert inst.email is None

    def test_partial_update_display_name(self):
        inst = UserUpdateRequest(display_name="New Name")
        assert inst.display_name == "New Name"
        assert inst.is_active is None

    def test_partial_update_is_active(self):
        inst = UserUpdateRequest(is_active=False)
        assert inst.is_active is False

    def test_update_password(self):
        inst = UserUpdateRequest(password="newpass123")
        assert inst.password == "newpass123"

    def test_update_password_too_short_raises(self):
        with pytest.raises(ValidationError):
            UserUpdateRequest(password="12345")

    def test_update_email(self):
        inst = UserUpdateRequest(email="new@example.com")
        assert inst.email == "new@example.com"

    def test_extra_field_ignored(self):
        """Pydantic v2 default extra="ignore" — extra fields are silently dropped."""
        inst = UserUpdateRequest(display_name="x", unknown="y")
        assert not hasattr(inst, "unknown")
