"""Tests for document_automation.types module."""

from __future__ import annotations

from dataclasses import fields
from enum import Enum

import pytest

from services.document_automation.types import (
    NON_TERMINAL_STAGES,
    CustomerInfo,
    ExtractionResult,
    MatchCandidate,
    MatchResult,
    OcrLine,
    PipelineStage,
    ProcessingResult,
    ValidationResult,
)


class TestPipelineStage:
    def test_is_str_enum(self):
        assert issubclass(PipelineStage, str)
        assert issubclass(PipelineStage, Enum)

    def test_enum_values(self):
        assert PipelineStage.IMPORT.value == "import"
        assert PipelineStage.PROCESSING.value == "processing"
        assert PipelineStage.OCR.value == "ocr"
        assert PipelineStage.COMPLETE.value == "complete"
        assert PipelineStage.FAILED.value == "failed"
        assert PipelineStage.AUTO_ATTACH.value == "auto_attach"
        assert PipelineStage.GROUPING.value == "grouping"

    def test_ordered_returns_correct_order(self):
        ordered = PipelineStage.ordered()
        assert len(ordered) == 14
        assert ordered[0] == PipelineStage.IMPORT
        assert ordered[1] == PipelineStage.PROCESSING
        assert ordered[2] == PipelineStage.ENHANCE
        assert ordered[3] == PipelineStage.OCR
        assert ordered[4] == PipelineStage.VALIDATE
        assert ordered[5] == PipelineStage.AI_FALLBACK
        assert ordered[6] == PipelineStage.MATCHING
        assert ordered[7] == PipelineStage.AUTO_ATTACH
        assert ordered[8] == PipelineStage.GROUPING
        assert ordered[9] == PipelineStage.VERIFY
        assert ordered[10] == PipelineStage.PACKAGE
        assert ordered[11] == PipelineStage.EMAIL
        assert ordered[12] == PipelineStage.COMPLETE
        assert ordered[13] == PipelineStage.FAILED

    def test_ordered_includes_all_stages(self):
        all_stages = set(PipelineStage)
        ordered_set = set(PipelineStage.ordered())
        assert ordered_set == all_stages

    def test_compare_by_value(self):
        assert PipelineStage("import") == PipelineStage.IMPORT
        assert PipelineStage("complete") == PipelineStage.COMPLETE


class TestNonTerminalStages:
    def test_contents(self):
        expected = [
            "import", "processing", "enhance", "ocr",
            "validate", "ai_fallback", "matching",
            "auto_attach", "grouping", "verify", "package", "email",
        ]
        assert list(NON_TERMINAL_STAGES) == expected

    def test_complete_not_included(self):
        assert "complete" not in NON_TERMINAL_STAGES

    def test_failed_not_included(self):
        assert "failed" not in NON_TERMINAL_STAGES

    def test_is_tuple(self):
        assert isinstance(NON_TERMINAL_STAGES, tuple)

    def test_values_match_pipeline_stages(self):
        for stage_str in NON_TERMINAL_STAGES:
            assert PipelineStage(stage_str) is not None


class TestProcessingResult:
    def test_all_fields(self):
        result = ProcessingResult(
            pdf_path="/tmp/doc.pdf",
            pages=3,
            original_size=(1920, 1080),
            enhanced=True,
            method="opencv",
            enhanced_image_paths=["/tmp/page1.jpg", "/tmp/page2.jpg"],
        )
        assert result.pdf_path == "/tmp/doc.pdf"
        assert result.pages == 3
        assert result.original_size == (1920, 1080)
        assert result.enhanced is True
        assert result.method == "opencv"
        assert len(result.enhanced_image_paths) == 2

    def test_default_enhanced_image_paths(self):
        result = ProcessingResult(
            pdf_path="/tmp/doc.pdf",
            pages=1,
            original_size=(100, 200),
            enhanced=False,
            method="none",
        )
        assert result.enhanced_image_paths == []

    def test_dataclass_fields(self):
        field_names = {f.name for f in fields(ProcessingResult)}
        expected = {"pdf_path", "pages", "original_size", "enhanced", "method", "enhanced_image_paths"}
        assert field_names == expected


class TestExtractionResult:
    def test_all_fields(self):
        result = ExtractionResult(
            full_text="Invoice #123",
            extracted={"invoice_number": "123"},
            confidence=0.95,
            engine="paddleocr",
            pages_processed=1,
        )
        assert result.full_text == "Invoice #123"
        assert result.extracted == {"invoice_number": "123"}
        assert result.confidence == 0.95
        assert result.engine == "paddleocr"
        assert result.pages_processed == 1

    def test_dataclass_fields(self):
        field_names = {f.name for f in fields(ExtractionResult)}
        expected = {"full_text", "extracted", "confidence", "engine", "pages_processed"}
        assert field_names == expected


class TestOcrLine:
    def test_has_text_and_confidence(self):
        line = OcrLine(text="Hello", confidence=0.98)
        assert line.text == "Hello"
        assert line.confidence == 0.98
        assert line.bbox is None

    def test_with_bbox(self):
        line = OcrLine(text="World", confidence=0.85, bbox=[10, 20, 100, 50])
        assert line.text == "World"
        assert line.bbox == [10, 20, 100, 50]

    def test_is_named_tuple(self):
        line = OcrLine(text="Test", confidence=0.9)
        assert line[0] == "Test"
        assert line[1] == 0.9
        assert line[2] is None

    def test_unpacking(self):
        text, conf, bbox = OcrLine(text="test", confidence=0.9, bbox=[1, 2, 3, 4])
        assert text == "test"
        assert conf == 0.9
        assert bbox == [1, 2, 3, 4]


class TestValidationResult:
    def test_all_fields(self):
        result = ValidationResult(
            score=0.85,
            needs_ai_fallback=False,
            missing_fields=["invoice_number"],
            text_quality=0.9,
            structure_ok=True,
        )
        assert result.score == 0.85
        assert result.needs_ai_fallback is False
        assert result.missing_fields == ["invoice_number"]
        assert result.text_quality == 0.9
        assert result.structure_ok is True

    def test_dataclass_fields(self):
        field_names = {f.name for f in fields(ValidationResult)}
        expected = {"score", "needs_ai_fallback", "missing_fields", "text_quality", "structure_ok"}
        assert field_names == expected

    def test_boundary_values(self):
        result = ValidationResult(
            score=0.0,
            needs_ai_fallback=True,
            missing_fields=[],
            text_quality=0.0,
            structure_ok=False,
        )
        assert result.score == 0.0
        assert result.needs_ai_fallback is True
        assert result.missing_fields == []
        assert result.structure_ok is False


class TestMatchCandidate:
    def test_all_fields(self):
        candidate = MatchCandidate(
            trip={"id": 1, "client": "ACME"},
            confidence=0.92,
            signals={"name_match": 0.9, "date_match": 0.95},
        )
        assert candidate.trip == {"id": 1, "client": "ACME"}
        assert candidate.confidence == 0.92
        assert candidate.signals == {"name_match": 0.9, "date_match": 0.95}

    def test_default_signals(self):
        candidate = MatchCandidate(trip={"id": 1}, confidence=0.5)
        assert candidate.signals == {}

    def test_dataclass_fields(self):
        field_names = {f.name for f in fields(MatchCandidate)}
        expected = {"trip", "confidence", "signals"}
        assert field_names == expected


class TestMatchResult:
    @pytest.fixture
    def candidate(self):
        return MatchCandidate(trip={"id": 1}, confidence=0.96, signals={"plate": 0.98})

    def test_is_auto_attach_high_confidence(self):
        result = MatchResult(
            best_match={"id": 1},
            confidence=0.96,
            candidates=[],
            signals={"plate": 0.98},
        )
        assert result.is_auto_attach is True
        assert result.is_suggested is False
        assert result.needs_manual is False

    def test_is_suggested_medium_confidence(self):
        result = MatchResult(
            best_match={"id": 1},
            confidence=0.80,
            candidates=[],
            signals={},
        )
        assert result.is_auto_attach is False
        assert result.is_suggested is True
        assert result.needs_manual is False

    def test_needs_manual_low_confidence(self):
        result = MatchResult(
            best_match={"id": 1},
            confidence=0.50,
            candidates=[],
            signals={},
        )
        assert result.is_auto_attach is False
        assert result.is_suggested is False
        assert result.needs_manual is True

    def test_no_best_match_all_false(self):
        result = MatchResult(
            best_match=None,
            confidence=0.0,
            candidates=[],
            signals={},
        )
        assert result.is_auto_attach is False
        assert result.is_suggested is False
        assert result.needs_manual is True  # no match → needs manual

    def test_boundary_auto_attach(self):
        """Confidence exactly 0.95 should be auto_attach."""
        result = MatchResult(
            best_match={"id": 1},
            confidence=0.95,
            candidates=[],
            signals={},
        )
        assert result.is_auto_attach is True
        assert result.is_suggested is False  # >= 0.95 is auto, not suggested

    def test_boundary_suggested_lower(self):
        """Confidence exactly 0.70 should be suggested."""
        result = MatchResult(
            best_match={"id": 1},
            confidence=0.70,
            candidates=[],
            signals={},
        )
        assert result.is_auto_attach is False
        assert result.is_suggested is True
        assert result.needs_manual is False

    def test_boundary_suggested_upper(self):
        """Confidence just below 0.95 should be suggested."""
        result = MatchResult(
            best_match={"id": 1},
            confidence=0.949999,
            candidates=[],
            signals={},
        )
        assert result.is_auto_attach is False
        assert result.is_suggested is True
        assert result.needs_manual is False

    def test_boundary_manual(self):
        """Confidence just below 0.70 should be manual."""
        result = MatchResult(
            best_match={"id": 1},
            confidence=0.699999,
            candidates=[],
            signals={},
        )
        assert result.is_auto_attach is False
        assert result.is_suggested is False
        assert result.needs_manual is True

    def test_dataclass_fields(self):
        field_names = {f.name for f in fields(MatchResult)}
        expected = {"best_match", "confidence", "candidates", "signals"}
        assert field_names == expected


class TestCustomerInfo:
    def test_all_fields(self):
        info = CustomerInfo(
            client={"id": 1, "name": "ACME"},
            primary_contact={"email": "bob@acme.com"},
            all_emails=["bob@acme.com", "alice@acme.com"],
            default_email="bob@acme.com",
        )
        assert info.client == {"id": 1, "name": "ACME"}
        assert info.primary_contact == {"email": "bob@acme.com"}
        assert info.all_emails == ["bob@acme.com", "alice@acme.com"]
        assert info.default_email == "bob@acme.com"

    def test_none_client_and_contact(self):
        info = CustomerInfo(
            client=None,
            primary_contact=None,
            all_emails=[],
            default_email="",
        )
        assert info.client is None
        assert info.primary_contact is None
        assert info.all_emails == []
        assert info.default_email == ""

    def test_dataclass_fields(self):
        field_names = {f.name for f in fields(CustomerInfo)}
        expected = {"client", "primary_contact", "all_emails", "default_email"}
        assert field_names == expected
