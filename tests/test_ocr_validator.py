"""Tests for ocr_validator module."""
import pytest

from services.document_automation.ocr_validator import (
    _check_structure,
    _entropy,
    _has_vowel,
    _missing_critical,
    _score_completeness,
    _score_text_quality,
    validate,
)


class TestValidate:
    def test_validate_cmr_perfect(self):
        extracted = {
            "doc_type": "cmr",
            "client_name": "ACME Corp",
            "truck_plate": "AB123CD",
            "date": "2024-01-15",
            "cmr_number": "CMR001",
        }
        result = validate(extracted, "Some OCR text here", 95.0, "paddle")
        assert result.score > 0.5
        assert result.needs_ai_fallback is False

    def test_validate_cmr_missing_fields(self):
        extracted = {"doc_type": "cmr", "client_name": ""}
        result = validate(extracted, "", 10.0, "paddle")
        assert result.score < 0.5
        assert result.needs_ai_fallback is True
        assert "truck_plate" in result.missing_fields
        assert "date" in result.missing_fields

    def test_validate_empty_extracted(self):
        result = validate({}, "", 0.0, "none")
        # Score = completeness(0.0)*0.5 + text_quality(0.0)*0.3 + structure(1.0)*0.2 = 0.2
        assert result.score == 0.2
        assert result.needs_ai_fallback is True

    def test_validate_invoice(self):
        extracted = {
            "doc_type": "invoice",
            "client_name": "ACME",
            "invoice_number": "INV-001",
            "date": "2024-06-15",
        }
        result = validate(extracted, "Invoice text", 85.0, "paddle")
        assert result.score > 0.5

    def test_validate_delivery_note(self):
        extracted = {
            "doc_type": "delivery_note",
            "client_name": "ACME",
            "date": "2024-06-15",
        }
        result = validate(extracted, "Delivery note text", 75.0, "paddle")
        assert result.score > 0.5

    def test_validate_other_type(self):
        extracted = {"doc_type": "other", "date": "2024-06-15"}
        result = validate(extracted, "Some text", 50.0, "paddle")
        # Should have date at minimum
        assert result.score > 0.0


class TestScoreCompleteness:
    def test_all_critical_found(self):
        profile = {"critical_fields": {"a", "b"}, "optional_fields": {"c"}}
        score = _score_completeness({"a": "val1", "b": "val2", "c": "val3"}, profile)
        assert score == 1.0

    def test_half_critical_found(self):
        profile = {"critical_fields": {"a", "b"}, "optional_fields": {"c"}}
        score = _score_completeness({"a": "val1"}, profile)
        # critical_ratio = 0.5, optional_ratio = 0.0
        # 0.5 * 0.7 + 0.0 * 0.3 = 0.35
        assert score == pytest.approx(0.35)

    def test_no_fields(self):
        profile = {"critical_fields": set(), "optional_fields": set()}
        score = _score_completeness({}, profile)
        assert score == 0.0


class TestScoreTextQuality:
    def test_empty_text(self):
        assert _score_text_quality("") == 0.0
        assert _score_text_quality(None) == 0.0

    def test_good_text(self):
        text = "Hello world this is a good OCR result with proper words"
        score = _score_text_quality(text)
        assert score > 0.3

    def test_garbage_text(self):
        text = "11111 aaaaa bbbb cccc"
        score = _score_text_quality(text)
        # Garbage should score lower than good text
        assert score < 0.5


class TestCheckStructure:
    def test_valid_plate(self):
        assert _check_structure({"truck_plate": "AB123CD"}, "cmr") is True

    def test_invalid_plate_too_short(self):
        assert _check_structure({"truck_plate": "A1"}, "cmr") is False

    def test_invalid_plate_no_letters(self):
        assert _check_structure({"truck_plate": "123456"}, "cmr") is False

    def test_valid_cmr_number(self):
        assert _check_structure({"cmr_number": "CMR001"}, "cmr") is True

    def test_invalid_cmr_no_digits(self):
        assert _check_structure({"cmr_number": "ABCDEF"}, "cmr") is False

    def test_no_fields_to_check(self):
        assert _check_structure({}, "other") is True


class TestHelpers:
    def test_has_vowel(self):
        assert _has_vowel("hello") is True
        assert _has_vowel("hll") is False
        assert _has_vowel("") is False

    def test_entropy(self):
        assert _entropy("") == 0.0
        assert _entropy("a") == 0.0
        assert _entropy("abcdef") > 2.0
        # Repeated characters should have lower entropy
        assert _entropy("aaaaaa") < 1.0

    def test_missing_critical(self):
        profile = {"critical_fields": {"a", "b", "c"}}
        missing = _missing_critical({"a": "val"}, profile)
        assert "b" in missing
        assert "c" in missing
        assert "a" not in missing
