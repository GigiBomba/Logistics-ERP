"""Tests for ocr_models.py — OCR result with confidence score, extracted fields, engine enum."""
from __future__ import annotations

import pytest
from datetime import datetime
from pydantic import ValidationError
from models.ocr_models import (
    OcrProcessRequest,
    ExtractedFields,
    MatchedTrip,
    OcrResult,
)


class TestOcrProcessRequest:
    @pytest.mark.parametrize(
        "doc_id, language, extract_fields, match_to_trips",
        [
            (1, "auto", True, True),
            (2, "ro", False, False),
            (3, "en", True, False),
            (4, "de", False, True),
        ],
    )
    def test_ocr_request_valid(self, doc_id, language, extract_fields, match_to_trips):
        r = OcrProcessRequest(
            document_id=doc_id,
            language=language,
            extract_fields=extract_fields,
            match_to_trips=match_to_trips,
        )
        assert r.document_id == doc_id
        assert r.language == language

    def test_ocr_request_defaults(self):
        r = OcrProcessRequest(document_id=5)
        assert r.language == "auto"
        assert r.extract_fields is True
        assert r.match_to_trips is True


class TestExtractedFields:
    def test_extracted_fields_defaults(self):
        f = ExtractedFields()
        assert f.document_number is None
        assert f.amount is None
        assert f.raw_text == ""
        assert f.confidence == 0.0
        assert f.additional_fields == {}

    @pytest.mark.parametrize(
        "doc_num, doc_date, client, amount, currency, ref, confidence",
        [
            ("INV-123", "2026-06-15", "Client A", 1500.50, "EUR", "REF-001", 0.95),
            ("CMR-456", "2026-06-20", "Client B", None, None, None, 0.87),
            (None, None, None, None, None, None, 0.0),
        ],
    )
    def test_extracted_fields_parametrize(self, doc_num, doc_date, client, amount, currency, ref, confidence):
        f = ExtractedFields(
            document_number=doc_num,
            document_date=doc_date,
            client_name=client,
            amount=amount,
            currency=currency,
            reference=ref,
            confidence=confidence,
        )
        assert f.document_number == doc_num
        assert f.confidence == confidence

    def test_extracted_fields_with_additional(self):
        f = ExtractedFields(
            raw_text="Invoice text here",
            confidence=0.92,
            additional_fields={"vat_number": "RO123456", "iban": "RO49BCR1234"},
        )
        assert f.additional_fields["vat_number"] == "RO123456"
        assert len(f.additional_fields) == 2

    def test_extracted_fields_text_only(self):
        f = ExtractedFields(raw_text="Some raw OCR text")
        assert f.raw_text == "Some raw OCR text"
        assert f.confidence == 0.0


class TestMatchedTrip:
    def test_matched_trip_defaults(self):
        m = MatchedTrip(trip_id=42, trip_reference="TRIP-042", confidence=0.88)
        assert m.match_reason == ""

    def test_matched_trip_with_reason(self):
        m = MatchedTrip(
            trip_id=100,
            trip_reference="TRIP-100",
            confidence=0.95,
            match_reason="Invoice number matches trip reference",
        )
        assert m.match_reason == "Invoice number matches trip reference"

    @pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
    def test_matched_trip_confidence(self, confidence):
        m = MatchedTrip(trip_id=1, trip_reference="T1", confidence=confidence)
        assert m.confidence == confidence


class TestOcrResult:
    def test_ocr_result_minimal(self):
        r = OcrResult(document_id=10, success=True)
        assert r.success is True
        assert r.extracted_fields.document_number is None
        assert r.matched_trips == []
        assert r.processing_time_ms == 0.0
        assert r.error_message == ""
        assert r.processed_at is None

    def test_ocr_result_failure(self):
        r = OcrResult(document_id=10, success=False, error_message="Unable to read file")
        assert r.success is False
        assert r.error_message == "Unable to read file"

    def test_ocr_result_with_fields_and_matches(self):
        fields = ExtractedFields(
            document_number="INV-999",
            amount=2500.0,
            confidence=0.97,
        )
        matches = [
            MatchedTrip(trip_id=1, trip_reference="T1", confidence=0.99, match_reason="Amount match"),
        ]
        now = datetime.now()
        r = OcrResult(
            document_id=20,
            success=True,
            extracted_fields=fields,
            matched_trips=matches,
            processing_time_ms=1234.56,
            processed_at=now,
        )
        assert r.extracted_fields.amount == 2500.0
        assert len(r.matched_trips) == 1
        assert r.matched_trips[0].trip_reference == "T1"
        assert r.processing_time_ms == 1234.56
