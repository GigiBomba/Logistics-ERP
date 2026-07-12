"""Unit tests for payment validation functions in utils.validation."""

from __future__ import annotations

import pytest

from utils.validation import (
    validate_iban,
    validate_bic,
    validate_bank_account,
    validate_payment_info,
)


class TestValidateIBAN:
    def test_valid_iban_de(self):
        assert validate_iban("DE89370400440532013000") is True

    def test_valid_iban_gb(self):
        assert validate_iban("GB29NWBK60161331926819") is True

    def test_valid_iban_ro(self):
        assert validate_iban("RO49AAAA1B31007593840000") is True

    def test_valid_iban_with_spaces(self):
        assert validate_iban("DE89 3704 0044 0532 0130 00") is True

    def test_valid_iban_lowercase(self):
        assert validate_iban("de89370400440532013000") is True

    def test_empty_iban(self):
        assert validate_iban("") is True  # optional field

    def test_invalid_iban_short(self):
        assert validate_iban("DE89") is False

    def test_invalid_iban_no_country(self):
        assert validate_iban("1234567890") is False

    def test_invalid_iban_special_chars(self):
        assert validate_iban("DE89!7040") is False


class TestValidateBIC:
    def test_valid_bic(self):
        assert validate_bic("DEUTDEFF") is True

    def test_valid_bic_11chars(self):
        assert validate_bic("DEUTDEFF500") is True

    def test_valid_bic_lowercase(self):
        assert validate_bic("deutdeff") is True

    def test_empty_bic(self):
        assert validate_bic("") is True  # optional field

    def test_invalid_bic_short(self):
        assert validate_bic("DEUT") is False

    def test_invalid_bic_digits_first(self):
        assert validate_bic("1234DEFF") is False


class TestValidateBankAccount:
    def test_valid_account(self):
        assert validate_bank_account("1234567890") is True

    def test_valid_account_with_spaces(self):
        assert validate_bank_account("1234 5678 90") is True

    def test_valid_account_with_dashes(self):
        assert validate_bank_account("1234-5678-90") is True

    def test_empty_account(self):
        assert validate_bank_account("") is True  # optional field

    def test_invalid_too_short(self):
        assert validate_bank_account("1234") is False


class TestValidatePaymentInfo:
    def test_valid_with_bank_account(self):
        errors = validate_payment_info({"bank_account": "1234567890"})
        assert errors == []

    def test_valid_with_iban(self):
        errors = validate_payment_info({"iban": "DE89370400440532013000"})
        assert errors == []

    def test_valid_with_both(self):
        errors = validate_payment_info({
            "bank_account": "1234567890",
            "iban": "DE89370400440532013000",
            "bank_bic": "DEUTDEFF",
        })
        assert errors == []

    def test_missing_both(self):
        errors = validate_payment_info({"bank_account": "", "iban": ""})
        assert len(errors) >= 1
        assert any("bank_account" in e.lower() or "iban" in e.lower() for e in errors)

    def test_missing_all_keys(self):
        errors = validate_payment_info({})
        assert len(errors) >= 1

    def test_invalid_iban(self):
        errors = validate_payment_info({"iban": "INVALID"})
        assert len(errors) == 1
        assert "iban" in errors[0].lower()

    def test_invalid_bic(self):
        errors = validate_payment_info({
            "bank_account": "1234567890",
            "bank_bic": "BAD",
        })
        assert len(errors) == 1
        assert "bic" in errors[0].lower()
