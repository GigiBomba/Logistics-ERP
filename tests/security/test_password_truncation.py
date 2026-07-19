"""Tests for consistent 72-byte bcrypt password truncation.

Verifies that:
1. hash_password truncates passwords > 72 bytes
2. verify_password truncates consistently (same 72 bytes)
3. A password longer than 72 bytes still verifies correctly
4. Multi-byte UTF-8 characters at the 72-byte boundary don't break matching
5. Non-ASCII passwords are handled
"""

import os
import bcrypt
import pytest

from backend.security import hash_password, verify_password


# ── 72-byte boundary tests ─────────────────────────────────────────────

def test_password_under_72_bytes_roundtrips():
    """A short password hashes and verifies correctly."""
    pw = "short-password-123"
    h = hash_password(pw, rounds=4)
    assert verify_password(pw, h)


def test_password_exactly_72_bytes_roundtrips():
    """A password exactly 72 bytes hashes and verifies correctly."""
    pw = "a" * 72
    assert len(pw.encode("utf-8")) == 72
    h = hash_password(pw, rounds=4)
    assert verify_password(pw, h)


def test_password_over_72_bytes_still_verifies():
    """A password > 72 bytes is truncated to 72 bytes and verifies.

    The first 72 bytes of the full password must match the first 72 bytes
    of the truncated version used during hashing.
    """
    pw = "b" * 100
    assert len(pw.encode("utf-8")) == 100
    h = hash_password(pw, rounds=4)
    # Full password should verify because verify_password also truncates
    assert verify_password(pw, h)
    # Explicitly truncated version should also verify
    truncated = pw[:72]
    assert verify_password(truncated, h)


def test_password_over_72_bytes_first_72_determine_match():
    """If two passwords share the first 72 bytes but differ after, they match."""
    base = "c" * 72
    pw_a = base + "AAA"
    pw_b = base + "BBB"
    h = hash_password(pw_a, rounds=4)
    assert verify_password(pw_b, h)  # Both truncated to same 72 bytes


def test_password_over_72_bytes_different_prefix_rejected():
    """If two passwords differ in the first 72 bytes, they don't match."""
    pw_a = "d" * 72 + "extra"
    pw_b = "e" * 72 + "extra"
    h = hash_password(pw_a, rounds=4)
    assert not verify_password(pw_b, h)


# ── Multi-byte UTF-8 boundary tests ────────────────────────────────────

def test_multi_byte_utf8_at_boundary_roundtrips():
    """2-byte UTF-8 chars at the 72-byte boundary are handled."""
    # Each 'é' is 2 bytes in UTF-8; 36 of them = 72 bytes
    pw = "é" * 36
    assert len(pw.encode("utf-8")) == 72
    h = hash_password(pw, rounds=4)
    assert verify_password(pw, h)


def test_multi_byte_utf8_crossing_boundary_roundtrips():
    """A multi-byte char that would cross the 72-byte boundary is truncated whole.

    37 × 'é' = 74 bytes; truncation at 72 bytes cuts the last char.
    """
    pw = "é" * 37
    assert len(pw.encode("utf-8")) == 74
    h = hash_password(pw, rounds=4)
    # Both should match on the truncated version (first 72 bytes = 36 'é')
    assert verify_password(pw, h)
    truncated_pw = "é" * 36
    assert len(truncated_pw.encode("utf-8")) == 72
    assert verify_password(truncated_pw, h)


def test_3_byte_utf8_at_boundary():
    """3-byte UTF-8 chars (e.g., €) at the boundary."""
    # 24 × '€' = 72 bytes
    pw = "€" * 24
    assert len(pw.encode("utf-8")) == 72
    h = hash_password(pw, rounds=4)
    assert verify_password(pw, h)


def test_mixed_ascii_and_utf8_at_boundary():
    """Mixed ASCII + multi-byte at the 72-byte boundary."""
    # 60 ASCII bytes + 6 × 2-byte chars = 72 bytes
    pw = "x" * 60 + "é" * 6
    assert len(pw.encode("utf-8")) == 72
    h = hash_password(pw, rounds=4)
    assert verify_password(pw, h)


# ── Edge cases ─────────────────────────────────────────────────────────

def test_empty_password():
    """An empty password is allowed (bcrypt can hash empty)."""
    pw = ""
    h = hash_password(pw, rounds=4)
    assert verify_password(pw, h)


def test_very_long_password_still_verifies():
    """A 1000-byte password is truncated and verifies correctly."""
    pw = "z" * 1000
    h = hash_password(pw, rounds=4)
    assert verify_password(pw, h)


def test_hash_is_always_60_chars():
    """bcrypt hashes are always 60 characters regardless of input length."""
    for length in [0, 1, 8, 72, 100, 1000]:
        pw = "p" * length
        h = hash_password(pw, rounds=4)
        assert len(h) == 60, f"Expected 60 chars for length {length}, got {len(h)}"
        assert h.startswith("$2b$")


def test_wrong_password_rejected():
    """A completely wrong password is rejected."""
    h = hash_password("correct-password", rounds=4)
    assert not verify_password("wrong-password", h)


def test_wrong_password_same_length_rejected():
    """A wrong password of the same length is rejected."""
    h = hash_password("x" * 72, rounds=4)
    assert not verify_password("y" * 72, h)


def test_invalid_hash_does_not_crash():
    """verify_password returns False (not raises) for an invalid hash."""
    assert not verify_password("any", "not-a-valid-hash")
    assert not verify_password("any", "")
    assert not verify_password("any", "$2b$04$")


# ── Backend schema max_length=72 validation ────────────────────────────

class TestPasswordSchemaMaxLength:
    """Verify that backend Pydantic schemas reject passwords > 72 chars."""

    def test_registration_rejects_over_72(self):
        from backend.schemas.registration import RegistrationRequest
        with pytest.raises(Exception):
            RegistrationRequest(
                email="test@test.com", password="x" * 73,
                display_name="Test", company_name="TestCo",
            )

    def test_registration_accepts_72(self):
        from backend.schemas.registration import RegistrationRequest
        # Should not raise
        r = RegistrationRequest(
            email="test@test.com", password="x" * 72,
            display_name="Test", company_name="TestCo",
        )
        assert len(r.password) == 72

    def test_user_create_rejects_over_72(self):
        from backend.schemas.user import UserCreateRequest
        with pytest.raises(Exception):
            UserCreateRequest(email="test@test.com", password="x" * 73, role="dispatcher")

    def test_user_update_rejects_over_72(self):
        from backend.schemas.user import UserUpdateRequest
        with pytest.raises(Exception):
            UserUpdateRequest(password="x" * 73)

    def test_reset_password_rejects_over_72(self):
        from backend.schemas.auth import ResetPasswordRequest
        with pytest.raises(Exception):
            ResetPasswordRequest(token="valid-token", new_password="x" * 73)

    def test_reset_password_accepts_72(self):
        from backend.schemas.auth import ResetPasswordRequest
        r = ResetPasswordRequest(token="valid-token", new_password="x" * 72)
        assert len(r.new_password) == 72
