"""Supplemental tests for utils.validation — covers gaps not in test_audit_fixes.py."""

from __future__ import annotations

import pytest

from utils.validation import (
    validate_email_with_reason,
    validate_plate_with_reason,
    validate_positive_number,
)


class TestValidatePositiveNumber:
    def test_large_number(self):
        result = validate_positive_number(1e15)
        assert result == 1e15

    def test_float_string(self):
        result = validate_positive_number("3.14")
        assert result == 3.14

    def test_negative_float(self):
        assert validate_positive_number(-0.5) is None

    def test_zero_as_int(self):
        assert validate_positive_number(0) is None


class TestValidateEmailWithReason:
    def test_whitespace_only(self):
        ok, reason = validate_email_with_reason("   ")
        assert not ok
        assert "empty" in reason.lower()

    def test_no_at_sign(self):
        ok, reason = validate_email_with_reason("notanemail")
        assert not ok
        assert "invalid email format" in reason.lower()

    def test_missing_domain(self):
        ok, reason = validate_email_with_reason("user@")
        assert not ok
        assert reason is not None

    def test_valid_with_whitespace(self):
        ok, reason = validate_email_with_reason("  test@example.com  ")
        assert ok
        assert reason is None


class TestValidatePlateWithReason:
    def test_special_characters(self):
        ok, reason = validate_plate_with_reason("AB@CD")
        assert not ok
        assert reason is not None

    def test_valid_eu_format(self):
        ok, reason = validate_plate_with_reason("ABC-123")
        assert ok
        assert reason is None

    def test_too_long(self):
        ok, reason = validate_plate_with_reason("A" * 13)
        assert not ok
        assert "invalid plate format" in reason.lower()

    def test_too_short(self):
        ok, reason = validate_plate_with_reason("A")
        assert not ok
        assert reason is not None
