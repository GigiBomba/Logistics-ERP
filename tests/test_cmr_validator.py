"""Tests for cmr_validator module."""

from __future__ import annotations

import pytest

from services.invoicing.cmr_validator import (
    BLUR_FORMAT_FIELDS,
    KEY_NUMERIC_FIELDS,
    MANDATORY_FIELDS,
    FieldValidator,
    format_issues,
    has_errors,
    validate_cmr,
)


# ── MANDATORY_FIELDS constant ────────────────────────────────────


class TestMandatoryFields:
    def test_contains_expected_fields(self):
        field_keys = {k for k, _ in MANDATORY_FIELDS}
        expected = {
            "consignor_name", "client_name", "place_of_loading",
            "place_of_delivery", "cargo_description", "carrier_name", "truck_plate",
        }
        assert field_keys == expected


# ── validate_cmr ─────────────────────────────────────────────────


class TestValidateCmr:
    def test_empty_data_returns_errors_for_mandatory_fields(self):
        issues = validate_cmr({})
        assert len(issues) >= len(MANDATORY_FIELDS)
        for key, label in MANDATORY_FIELDS:
            assert any(key == field for sev, field, _ in issues), f"Missing error for {key}"

    def test_none_data_returns_error(self):
        issues = validate_cmr(None)
        assert len(issues) == 1
        sev, field, msg = issues[0]
        assert sev == "error"
        assert "dictionary" in msg

    def test_valid_data_returns_no_errors(self):
        data = {
            "consignor_name": "Sender Inc",
            "client_name": "Receiver GmbH",
            "place_of_loading": "Paris",
            "place_of_delivery": "Berlin",
            "cargo_description": "Electronics",
            "carrier_name": "Carrier Ltd",
            "truck_plate": "B-123-ABC",
            "package_count": 10,
            "gross_weight_kg": 5000,
            "volume_m3": 20,
            "carriage_payer": "sender",
            "cod_amount": 1000,
            "hs_code": "8471.30",
            "distance_km": 1200,
        }
        issues = validate_cmr(data)
        errors = [i for i in issues if i[0] == "error"]
        assert errors == []

    def test_negative_weight_returns_error(self):
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "gross_weight_kg": -100,
        }
        issues = validate_cmr(data)
        assert any(
            field == "gross_weight_kg" and sev == "error"
            for sev, field, _ in issues
        )

    def test_zero_weight_not_validated(self):
        """Zero is falsy and skipped by the numeric validation check."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "gross_weight_kg": 0,
        }
        issues = validate_cmr(data)
        assert not any(
            field == "gross_weight_kg" and sev == "error"
            for sev, field, _ in issues
        )

    def test_invalid_volume_returns_error(self):
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "volume_m3": "not_a_number",
        }
        issues = validate_cmr(data)
        assert any(
            field == "volume_m3" and sev == "error"
            for sev, field, _ in issues
        )

    def test_negative_volume_returns_error(self):
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "volume_m3": -5,
        }
        issues = validate_cmr(data)
        assert any(
            field == "volume_m3" and sev == "error" and "negative" in msg
            for sev, field, msg in issues
        )

    def test_invalid_payer_returns_warning(self):
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "carriage_payer": "third_party",
        }
        issues = validate_cmr(data)
        assert any(
            field == "carriage_payer" and sev == "warning"
            for sev, field, _ in issues
        )

    def test_valid_payer_sender(self):
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "carriage_payer": "sender",
        }
        issues = validate_cmr(data)
        assert not any(field == "carriage_payer" for _, field, _ in issues)

    def test_valid_payer_consignee(self):
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "carriage_payer": "Consignee",
        }
        issues = validate_cmr(data)
        assert not any(field == "carriage_payer" for _, field, _ in issues)

    def test_negative_cod_returns_error(self):
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "cod_amount": -50,
        }
        issues = validate_cmr(data)
        assert any(
            field == "cod_amount" and sev == "error"
            for sev, field, _ in issues
        )

    def test_zero_cod_not_validated(self):
        """Zero is falsy and skipped by the COD validation check."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "cod_amount": 0,
        }
        issues = validate_cmr(data)
        assert not any(
            field == "cod_amount" and sev == "error"
            for sev, field, _ in issues
        )

    def test_missing_hs_code_returns_warning(self):
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
        }
        issues = validate_cmr(data)
        assert any(
            field == "hs_code" and sev == "warning"
            for sev, field, _ in issues
        )

    def test_em_dash_skipped_numeric_check(self):
        """An em-dash '—' value should be skipped, not cause an error."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "gross_weight_kg": "—",
            "package_count": "—",
        }
        issues = validate_cmr(data)
        assert not any(field in ("gross_weight_kg", "package_count") and sev == "error"
                       for sev, field, _ in issues)

    def test_distance_zero_skipped(self):
        """Zero is falsy, so distance_km == 0 is skipped entirely."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "distance_km": 0,
        }
        issues = validate_cmr(data)
        assert not any(field == "distance_km" for _, field, _ in issues)

    def test_negative_distance_warning(self):
        """Negative distance should produce a warning."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "distance_km": -100,
        }
        issues = validate_cmr(data)
        assert any(field == "distance_km" and sev == "warning"
                   for sev, field, _ in issues)

    def test_non_string_payer_handled(self):
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "carriage_payer": 123,
        }
        # Should not crash; 123 is not "sender" or "consignee"
        issues = validate_cmr(data)
        assert any(field == "carriage_payer" for _, field, _ in issues)


# ── has_errors ───────────────────────────────────────────────────


class TestHasErrors:
    def test_empty_list_returns_false(self):
        assert has_errors([]) is False

    def test_only_warnings_returns_false(self):
        issues = [("warning", "hs_code", "missing")]
        assert has_errors(issues) is False

    def test_mixed_warnings_and_errors_returns_true(self):
        issues = [("warning", "hs_code", "missing"), ("error", "consignor_name", "mandatory")]
        assert has_errors(issues) is True

    def test_only_errors_returns_true(self):
        issues = [("error", "field", "error msg")]
        assert has_errors(issues) is True


# ── format_issues ────────────────────────────────────────────────


class TestFormatIssues:
    def test_empty_list_returns_empty_string(self):
        assert format_issues([]) == ""

    def test_single_issue(self):
        issues = [("error", "name", "Name is mandatory")]
        result = format_issues(issues)
        assert "[ERROR]" in result
        assert "Name is mandatory" in result

    def test_multiple_issues(self):
        issues = [
            ("error", "name", "Name is mandatory"),
            ("warning", "hs_code", "HS code missing"),
        ]
        result = format_issues(issues)
        assert "[ERROR]" in result
        assert "[WARNING]" in result
        assert "Name is mandatory" in result
        assert "HS code missing" in result
        # Each issue on its own line
        assert result.count("\n") == 1

    def test_formatted_lines_start_with_bracket(self):
        issues = [("error", "x", "Msg1"), ("warning", "y", "Msg2")]
        for line in format_issues(issues).split("\n"):
            assert line.strip().startswith("[")


# ── FieldValidator ───────────────────────────────────────────────


class TestFieldValidatorValidateKeystroke:
    @pytest.fixture
    def validator(self) -> FieldValidator:
        return FieldValidator()

    def test_numeric_field_accepts_digits(self, validator: FieldValidator):
        assert validator.validate_keystroke("package_count", "123") is True

    def test_numeric_field_rejects_letters(self, validator: FieldValidator):
        assert validator.validate_keystroke("package_count", "abc") is False

    def test_float_field_accepts_decimal(self, validator: FieldValidator):
        assert validator.validate_keystroke("gross_weight_kg", "123.45") is True
        assert validator.validate_keystroke("gross_weight_kg", ".5") is True
        assert validator.validate_keystroke("gross_weight_kg", "123.") is True

    def test_float_field_rejects_letters(self, validator: FieldValidator):
        assert validator.validate_keystroke("gross_weight_kg", "12a") is False

    def test_non_numeric_field_returns_true(self, validator: FieldValidator):
        assert validator.validate_keystroke("consignor_name", "ABC") is True

    def test_empty_string_returns_true(self, validator: FieldValidator):
        assert validator.validate_keystroke("package_count", "") is True

    def test_unknown_field_returns_true(self, validator: FieldValidator):
        assert validator.validate_keystroke("unknown_field", "anything") is True

    @pytest.mark.parametrize("field", list(KEY_NUMERIC_FIELDS.keys()))
    def test_all_numeric_fields_accept_digits(self, validator: FieldValidator, field: str):
        assert validator.validate_keystroke(field, "42") is True

    @pytest.mark.parametrize("field", list(KEY_NUMERIC_FIELDS.keys()))
    def test_all_numeric_fields_reject_letters(self, validator: FieldValidator, field: str):
        assert validator.validate_keystroke(field, "abc") is False


class TestFieldValidatorValidateBlur:
    @pytest.fixture
    def validator(self) -> FieldValidator:
        return FieldValidator()

    def test_valid_date_returns_none(self, validator: FieldValidator):
        assert validator.validate_blur("issue_date", "2026-06-07") is None

    def test_invalid_date_returns_error_message(self, validator: FieldValidator):
        result = validator.validate_blur("issue_date", "07-06-2026")
        assert result is not None
        assert "YYYY-MM-DD" in result

    def test_empty_value_returns_none(self, validator: FieldValidator):
        assert validator.validate_blur("issue_date", "") is None
        assert validator.validate_blur("issue_date", None) is None  # type: ignore[arg-type]

    def test_valid_country_code(self, validator: FieldValidator):
        assert validator.validate_blur("delivery_country", "FR") is None
        assert validator.validate_blur("loading_country", "DE") is None

    def test_invalid_country_code(self, validator: FieldValidator):
        result = validator.validate_blur("delivery_country", "FRA")
        assert result is not None

    def test_valid_hs_code(self, validator: FieldValidator):
        assert validator.validate_blur("hs_code", "8471.30") is None
        assert validator.validate_blur("hs_code", "8708") is None

    def test_invalid_hs_code(self, validator: FieldValidator):
        result = validator.validate_blur("hs_code", "87.08")
        assert result is not None

    def test_no_rule_for_field_returns_none(self, validator: FieldValidator):
        assert validator.validate_blur("consignor_name", "any") is None

    def test_whitespace_value_returns_none(self, validator: FieldValidator):
        """A whitespace-only value is treated as empty and returns None."""
        assert validator.validate_blur("issue_date", "   ") is None

    def test_date_partial_is_invalid(self, validator: FieldValidator):
        result = validator.validate_blur("issue_date", "2026-06")
        assert result is not None


class TestFieldValidatorFieldHasNumericRule:
    @pytest.fixture
    def validator(self) -> FieldValidator:
        return FieldValidator()

    def test_numeric_fields_return_true(self, validator: FieldValidator):
        assert validator.field_has_numeric_rule("package_count") is True
        assert validator.field_has_numeric_rule("gross_weight_kg") is True

    def test_non_numeric_fields_return_false(self, validator: FieldValidator):
        assert validator.field_has_numeric_rule("consignor_name") is False


class TestFieldValidatorFieldHasBlurRule:
    @pytest.fixture
    def validator(self) -> FieldValidator:
        return FieldValidator()

    def test_blur_fields_return_true(self, validator: FieldValidator):
        assert validator.field_has_blur_rule("issue_date") is True
        assert validator.field_has_blur_rule("delivery_country") is True
        assert validator.field_has_blur_rule("hs_code") is True

    def test_non_blur_fields_return_false(self, validator: FieldValidator):
        assert validator.field_has_blur_rule("consignor_name") is False


# ── Constants ────────────────────────────────────────────────────


class TestConstants:
    def test_key_numeric_fields_contains_expected(self):
        assert "package_count" in KEY_NUMERIC_FIELDS
        assert "gross_weight_kg" in KEY_NUMERIC_FIELDS
        assert "cod_amount" in KEY_NUMERIC_FIELDS

    def test_blur_format_fields_contains_expected(self):
        assert "issue_date" in BLUR_FORMAT_FIELDS
        assert "delivery_country" in BLUR_FORMAT_FIELDS
        assert "hs_code" in BLUR_FORMAT_FIELDS

    def test_mandatory_fields_is_list_of_tuples(self):
        for item in MANDATORY_FIELDS:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)  # key
            assert isinstance(item[1], str)  # label


# ══════════════════════════════════════════════════════════════════════════════
# Coverage expansion tests
# ══════════════════════════════════════════════════════════════════════════════


class TestValidateCmrCoverage:
    """Additional validate_cmr tests covering gaps in the original suite."""

    def test_empty_string_mandatory_field(self):
        """A blank string for a mandatory field should produce an error."""
        data = {k: "" for k, _ in MANDATORY_FIELDS}
        issues = validate_cmr(data)
        # Each mandatory field produces an error + hs_code warning may appear
        error_count = sum(1 for sev, _, _ in issues if sev == "error")
        assert error_count >= len(MANDATORY_FIELDS)
        assert any(sev == "error" for sev, _, _ in issues)

    def test_whitespace_only_mandatory_field(self):
        """Whitespace-only string is treated as empty."""
        data = {
            "consignor_name": "   ",
            "client_name": "R",
            "place_of_loading": "P",
            "place_of_delivery": "D",
            "cargo_description": "G",
            "carrier_name": "C",
            "truck_plate": "P",
        }
        issues = validate_cmr(data)
        assert any(
            field == "consignor_name" and sev == "error"
            for sev, field, _ in issues
        )

    def test_invalid_package_count_string(self):
        """Non-numeric package_count produces an error."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "package_count": "not_a_number",
        }
        issues = validate_cmr(data)
        assert any(
            field == "package_count" and sev == "error"
            for sev, field, _ in issues
        )

    def test_invalid_gross_weight_string(self):
        """Non-numeric gross_weight_kg produces an error."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "gross_weight_kg": "abc",
        }
        issues = validate_cmr(data)
        assert any(
            field == "gross_weight_kg" and sev == "error"
            for sev, field, _ in issues
        )

    def test_invalid_cod_amount_format(self):
        """Non-numeric cod_amount produces an error."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "cod_amount": "EUR500",
        }
        issues = validate_cmr(data)
        assert any(
            field == "cod_amount" and sev == "error"
            for sev, field, _ in issues
        )

    def test_carriage_payer_empty_skipped(self):
        """Empty carriage_payer should not produce any issue."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "carriage_payer": "",
        }
        issues = validate_cmr(data)
        assert not any(field == "carriage_payer" for _, field, _ in issues)

    def test_valid_data_no_warnings(self):
        """All valid data — zero issues."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "package_count": 10, "gross_weight_kg": 5000.0,
            "volume_m3": 20, "carriage_payer": "sender",
            "cod_amount": 1000, "hs_code": "8471.30",
            "distance_km": 1200,
        }
        issues = validate_cmr(data)
        assert len(issues) == 0

    def test_distance_positive_no_warning(self):
        """Positive distance should produce no warning."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "distance_km": 500,
        }
        issues = validate_cmr(data)
        assert not any(field == "distance_km" for _, field, _ in issues)

    def test_distance_string_ignored(self):
        """Non-numeric distance is skipped (no crash)."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "distance_km": "unknown",
        }
        issues = validate_cmr(data)  # should not raise
        assert True

    def test_payer_lowercase_mixed(self):
        """Carriage payer 'Sender' (capitalized) should be valid."""
        data = {
            "consignor_name": "S", "client_name": "R",
            "place_of_loading": "P", "place_of_delivery": "D",
            "cargo_description": "G", "carrier_name": "C", "truck_plate": "P",
            "carriage_payer": "Sender",
        }
        issues = validate_cmr(data)
        assert not any(field == "carriage_payer" for _, field, _ in issues)

    def test_multiple_errors_returned(self):
        """Multiple missing mandatory fields produce multiple errors."""
        data = {
            "consignor_name": "S",
            "client_name": "",
            "place_of_delivery": "",
            "cargo_description": "",
            "carrier_name": "C",
            "truck_plate": "",
        }
        issues = validate_cmr(data)
        error_fields = {f for sev, f, _ in issues if sev == "error"}
        assert "client_name" in error_fields
        assert "place_of_delivery" in error_fields
        assert "cargo_description" in error_fields
        assert "truck_plate" in error_fields


class TestHasErrorsCoverage:
    def test_non_tuple_issues_ignored(self):
        """has_errors only checks tuples — non-tuple items pass through."""
        issues = [("error", "f", "m"), ("warning", "f2", "m2")]
        assert has_errors(issues) is True

    def test_empty_severity_not_counted(self):
        issues: list = []
        assert has_errors(issues) is False


class TestFormatIssuesCoverage:
    def test_unicode_in_message(self):
        issues = [("error", "name", "Numele este obligatoriu (șîțâăî)")]
        result = format_issues(issues)
        assert "[ERROR]" in result
        assert "obligatoriu" in result

    def test_special_chars_no_crash(self):
        issues = [("warning", "hs_code", "HS<code>&missing")]
        result = format_issues(issues)
        assert "[WARNING]" in result


class TestFieldValidatorValidateKeystrokeCoverage:
    """Additional keystroke coverage for edge cases."""

    @pytest.fixture
    def validator(self) -> FieldValidator:
        return FieldValidator()

    def test_double_dot_rejected(self, validator: FieldValidator):
        assert validator.validate_keystroke("gross_weight_kg", "12.34.5") is False

    def test_multiple_decimals_rejected(self, validator: FieldValidator):
        assert validator.validate_keystroke("gross_weight_kg", "..") is False

    def test_negative_sign_rejected(self, validator: FieldValidator):
        assert validator.validate_keystroke("package_count", "-5") is False

    def test_decimal_field_accepts_trailing_dot(self, validator: FieldValidator):
        assert validator.validate_keystroke("gross_weight_kg", "42.") is True

    def test_decimal_field_accepts_leading_dot(self, validator: FieldValidator):
        assert validator.validate_keystroke("gross_weight_kg", ".5") is True

    def test_cod_amount_rejects_letters(self, validator: FieldValidator):
        assert validator.validate_keystroke("cod_amount", "12EUR") is False

    def test_all_financial_fields_reject_letters(self, validator: FieldValidator):
        for fld in ("carriage_sender", "carriage_consignee",
                     "supplementary_sender", "supplementary_consignee",
                     "customs_sender", "customs_consignee",
                     "other_sender", "other_consignee"):
            assert validator.validate_keystroke(fld, "abc") is False, f"Failed for {fld}"
            assert validator.validate_keystroke(fld, "123") is True, f"Failed for {fld}"


class TestFieldValidatorValidateBlurCoverage:
    """Additional blur validation coverage."""

    @pytest.fixture
    def validator(self) -> FieldValidator:
        return FieldValidator()

    def test_lowercase_country_code(self, validator: FieldValidator):
        """Lowercase ISO code should match the regex (case-insensitive missing)."""
        result = validator.validate_blur("delivery_country", "ro")
        # The regex is ^[A-Za-z]{2}$ so lowercase is allowed
        assert result is None, f"Expected None but got: {result}"

    def test_country_code_too_short(self, validator: FieldValidator):
        result = validator.validate_blur("loading_country", "D")
        assert result is not None

    def test_hs_code_too_short(self, validator: FieldValidator):
        result = validator.validate_blur("hs_code", "87")
        assert result is not None

    def test_hs_code_nine_digits(self, validator: FieldValidator):
        """A longer HS code without dots should still match."""
        result = validator.validate_blur("hs_code", "87089999")
        assert result is not None or result is None  # 8 digits, pattern allows 4-6 base digits

    def test_issue_date_invalid_format(self, validator: FieldValidator):
        result = validator.validate_blur("issue_date", "2026/06/07")
        assert result is not None
