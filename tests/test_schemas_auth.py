"""Tests for backend/schemas/auth.py — RefreshTokenRequest, LogoutRequest,
ForgotPasswordRequest, ResetPasswordRequest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.auth import (
    ForgotPasswordRequest,
    LogoutRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
)


# ── RefreshTokenRequest ────────────────────────────────────────────────────────


class TestRefreshTokenRequest:
    """refresh_token: str(..., min_length=1)."""

    def test_valid(self):
        inst = RefreshTokenRequest(refresh_token="abc123")
        assert inst.refresh_token == "abc123"

    def test_empty_raises(self):
        """min_length=1 — empty string should raise."""
        with pytest.raises(ValidationError):
            RefreshTokenRequest(refresh_token="")

    def test_whitespace_only_is_valid_string(self):
        """Whitespace is a non-empty string; pydantic doesn't strip by default."""
        inst = RefreshTokenRequest(refresh_token="   ")
        assert inst.refresh_token == "   "

    def test_missing_field_raises(self):
        """refresh_token is required."""
        with pytest.raises(ValidationError):
            RefreshTokenRequest()  # type: ignore[call-arg]

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            RefreshTokenRequest(refresh_token=None)  # type: ignore[arg-type]

    def test_non_string_type_raises(self):
        with pytest.raises(ValidationError):
            RefreshTokenRequest(refresh_token=123)  # type: ignore[arg-type]


# ── LogoutRequest ──────────────────────────────────────────────────────────────


class TestLogoutRequest:
    """refresh_token: str(..., min_length=1)."""

    def test_valid(self):
        inst = LogoutRequest(refresh_token="tok_xyz")
        assert inst.refresh_token == "tok_xyz"

    def test_empty_raises(self):
        with pytest.raises(ValidationError):
            LogoutRequest(refresh_token="")

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            LogoutRequest()  # type: ignore[call-arg]

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            LogoutRequest(refresh_token=None)  # type: ignore[arg-type]

    def test_non_string_type_raises(self):
        with pytest.raises(ValidationError):
            LogoutRequest(refresh_token=True)  # type: ignore[arg-type]


# ── ForgotPasswordRequest ──────────────────────────────────────────────────────


class TestForgotPasswordRequest:
    """email: str(..., min_length=5, max_length=255)."""

    def test_valid(self):
        inst = ForgotPasswordRequest(email="user@example.com")
        assert inst.email == "user@example.com"

    def test_min_length_boundary_exact(self):
        """Exactly 5 characters — should be valid."""
        inst = ForgotPasswordRequest(email="a@b.c")
        assert inst.email == "a@b.c"

    def test_min_length_boundary_below(self):
        """4 characters — below min_length=5."""
        with pytest.raises(ValidationError):
            ForgotPasswordRequest(email="a@b.")

    def test_empty_raises(self):
        with pytest.raises(ValidationError):
            ForgotPasswordRequest(email="")

    def test_max_length_boundary_exact(self):
        """Exactly 255 characters."""
        email = "a@" + "b" * 251 + ".c"
        assert len(email) == 255, f"expected 255, got {len(email)}"
        inst = ForgotPasswordRequest(email=email)
        assert inst.email == email

    def test_max_length_boundary_over(self):
        """256 characters — over max_length=255."""
        email = "a@" + "b" * 252 + ".c"
        assert len(email) == 256, f"expected 256, got {len(email)}"
        with pytest.raises(ValidationError):
            ForgotPasswordRequest(email=email)

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            ForgotPasswordRequest()  # type: ignore[call-arg]

    def test_none_raises(self):
        with pytest.raises(ValidationError):
            ForgotPasswordRequest(email=None)  # type: ignore[arg-type]

    def test_non_string_type_raises(self):
        with pytest.raises(ValidationError):
            ForgotPasswordRequest(email=42)  # type: ignore[arg-type]


# ── ResetPasswordRequest ───────────────────────────────────────────────────────


class TestResetPasswordRequest:
    """token: str(..., min_length=1), new_password: str(..., min_length=6, max_length=72)."""

    VALID_TOKEN = "reset-token-123"
    VALID_PASSWORD = "newPass123!"

    def test_valid(self):
        inst = ResetPasswordRequest(token=self.VALID_TOKEN, new_password=self.VALID_PASSWORD)
        assert inst.token == self.VALID_TOKEN
        assert inst.new_password == self.VALID_PASSWORD

    # ── token tests ──

    def test_token_empty_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token="", new_password=self.VALID_PASSWORD)

    def test_token_missing_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(new_password=self.VALID_PASSWORD)  # type: ignore[call-arg]

    def test_token_none_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token=None, new_password=self.VALID_PASSWORD)  # type: ignore[arg-type]

    # ── new_password tests ──

    def test_password_min_length_boundary_exact(self):
        """Exactly 6 characters."""
        inst = ResetPasswordRequest(token=self.VALID_TOKEN, new_password="Abcd12")
        assert inst.new_password == "Abcd12"

    def test_password_min_length_boundary_below(self):
        """5 characters — below min_length=6."""
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token=self.VALID_TOKEN, new_password="Abc12")

    def test_password_empty_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token=self.VALID_TOKEN, new_password="")

    def test_password_max_length_boundary_exact(self):
        """Exactly 72 characters."""
        pw = "A" + "b" * 70 + "1"
        assert len(pw) == 72
        inst = ResetPasswordRequest(token=self.VALID_TOKEN, new_password=pw)
        assert inst.new_password == pw

    def test_password_max_length_boundary_over(self):
        """73 characters — over max_length=72."""
        pw = "A" + "b" * 71 + "1"
        assert len(pw) == 73
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token=self.VALID_TOKEN, new_password=pw)

    def test_password_missing_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token=self.VALID_TOKEN)  # type: ignore[call-arg]

    def test_password_none_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token=self.VALID_TOKEN, new_password=None)  # type: ignore[arg-type]

    def test_password_non_string_type_raises(self):
        with pytest.raises(ValidationError):
            ResetPasswordRequest(token=self.VALID_TOKEN, new_password=12345)  # type: ignore[arg-type]
