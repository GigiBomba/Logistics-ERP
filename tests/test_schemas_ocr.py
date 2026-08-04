"""Tests for backend/schemas/ocr.py — OCR request/result/extraction schemas."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.ocr import (
    OcrFieldExtractionRequest,
    OcrFieldExtractionResponse,
    OcrRequest,
    OcrResult,
)


# ── OcrRequest ────────────────────────────────────────────────────────────────


class TestOcrRequest:
    """document_id (required), engine (default "auto"), extra="forbid"."""

    def test_required_only(self):
        inst = OcrRequest(document_id=1)
        assert inst.document_id == 1
        assert inst.engine == "auto"

    def test_custom_engine(self):
        inst = OcrRequest(document_id=5, engine="tesseract")
        assert inst.engine == "tesseract"

    def test_missing_document_id_raises(self):
        with pytest.raises(ValidationError):
            OcrRequest()  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            OcrRequest(document_id=1, unknown="x")  # type: ignore[call-arg]


# ── OcrResult ─────────────────────────────────────────────────────────────────


class TestOcrResult:
    """document_id (required), ocr_text (required), engine_used (required), extracted_fields (default {}), confidence (default 0.0), processing_time_ms (default 0)."""

    def test_required_only(self):
        inst = OcrResult(
            document_id=1, ocr_text="sample text", engine_used="tesseract",
            extracted_fields={},
        )
        assert inst.document_id == 1
        assert inst.ocr_text == "sample text"
        assert inst.engine_used == "tesseract"
        assert inst.extracted_fields == {}
        assert inst.confidence == 0.0
        assert inst.processing_time_ms == 0
        assert inst.status == "pending"  # roadmap 12 default
        assert inst.error is None

    def test_all_fields(self):
        inst = OcrResult(
            document_id=1,
            ocr_text="extracted content",
            engine_used="azure",
            extracted_fields={"amount": 150.0, "date": "2025-01-01"},
            confidence=0.95,
            processing_time_ms=1200,
        )
        assert inst.extracted_fields["amount"] == 150.0
        assert inst.confidence == 0.95

    def test_missing_document_id_raises(self):
        with pytest.raises(ValidationError):
            OcrResult(ocr_text="t", engine_used="e")  # type: ignore[call-arg]

    def test_missing_ocr_text_raises(self):
        with pytest.raises(ValidationError):
            OcrResult(document_id=1, engine_used="e")  # type: ignore[call-arg]

    def test_missing_engine_used_raises(self):
        with pytest.raises(ValidationError):
            OcrResult(document_id=1, ocr_text="t")  # type: ignore[call-arg]

    def test_confidence_range(self):
        """No constraint — any float is accepted."""
        inst = OcrResult(document_id=1, ocr_text="t", engine_used="e", extracted_fields={}, confidence=-1.0)
        assert inst.confidence == -1.0
        inst2 = OcrResult(document_id=1, ocr_text="t", engine_used="e", extracted_fields={}, confidence=1.5)
        assert inst2.confidence == 1.5

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            OcrResult(document_id=1, ocr_text="t", engine_used="e", bad="x")  # type: ignore[call-arg]


# ── OcrFieldExtractionRequest ─────────────────────────────────────────────────


class TestOcrFieldExtractionRequest:
    """document_id (required), fields_to_extract (optional list), extra="forbid"."""

    def test_required_only(self):
        inst = OcrFieldExtractionRequest(document_id=1)
        assert inst.document_id == 1
        assert inst.fields_to_extract is None

    def test_with_fields(self):
        inst = OcrFieldExtractionRequest(document_id=1, fields_to_extract=["amount", "date"])
        assert inst.fields_to_extract == ["amount", "date"]

    def test_empty_fields_list(self):
        inst = OcrFieldExtractionRequest(document_id=1, fields_to_extract=[])
        assert inst.fields_to_extract == []

    def test_missing_document_id_raises(self):
        with pytest.raises(ValidationError):
            OcrFieldExtractionRequest()  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            OcrFieldExtractionRequest(document_id=1, unknown="x")  # type: ignore[call-arg]


# ── OcrFieldExtractionResponse ────────────────────────────────────────────────


class TestOcrFieldExtractionResponse:
    """document_id (required), fields (required dict), errors (default []), extra="forbid"."""

    def test_required_only(self):
        inst = OcrFieldExtractionResponse(document_id=1, fields={"amount": 100.0})
        assert inst.document_id == 1
        assert inst.fields == {"amount": 100.0}
        assert inst.errors == []

    def test_with_errors(self):
        inst = OcrFieldExtractionResponse(
            document_id=1,
            fields={},
            errors=["Field 'amount' not found", "Field 'date' not found"],
        )
        assert len(inst.errors) == 2

    def test_missing_document_id_raises(self):
        with pytest.raises(ValidationError):
            OcrFieldExtractionResponse(fields={})  # type: ignore[call-arg]

    def test_missing_fields_raises(self):
        with pytest.raises(ValidationError):
            OcrFieldExtractionResponse(document_id=1)  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            OcrFieldExtractionResponse(document_id=1, fields={}, bad="x")  # type: ignore[call-arg]
