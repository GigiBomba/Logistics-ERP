"""Tests for export_models.py — Export format enum, filter params, date range bounds."""
from __future__ import annotations

import pytest
from datetime import datetime
from pydantic import ValidationError
from models.export_models import ExportRequest, ExportResult


class TestExportRequest:
    @pytest.mark.parametrize(
        "fmt, entity_type",
        [
            ("pdf", "trip"),
            ("excel", "invoice"),
            ("csv", "receipt"),
            ("pdf", "cmr"),
            ("excel", "dispatch_board"),
        ],
    )
    def test_export_request_valid_format(self, fmt, entity_type):
        r = ExportRequest(format=fmt, entity_type=entity_type)
        assert r.format == fmt
        assert r.entity_type == entity_type

    def test_export_request_invalid_format_raises(self):
        with pytest.raises(ValidationError):
            ExportRequest(format="docx", entity_type="trip")

    def test_export_request_defaults(self):
        r = ExportRequest(entity_type="trip")
        assert r.format == "pdf"
        assert r.entity_id is None
        assert r.entity_ids == []
        assert r.template == "default"
        assert r.filename == ""
        assert r.include_logo is True
        assert r.language == "ro"

    def test_export_request_with_single_id(self):
        r = ExportRequest(entity_type="invoice", entity_id=42)
        assert r.entity_id == 42

    def test_export_request_with_multiple_ids(self):
        r = ExportRequest(entity_type="invoice", entity_ids=[1, 2, 3])
        assert r.entity_ids == [1, 2, 3]

    def test_export_request_all_fields(self):
        r = ExportRequest(
            format="csv",
            entity_type="analytics",
            entity_id=10,
            entity_ids=[10, 20],
            template="detailed",
            filename="report_2026",
            include_logo=False,
            language="en",
        )
        assert r.filename == "report_2026"
        assert r.template == "detailed"
        assert r.language == "en"

    def test_export_request_empty_entity_type_accepted(self):
        r = ExportRequest(entity_type="")
        assert r.entity_type == ""


class TestExportResult:
    def test_export_result_minimal(self):
        now = datetime.now()
        r = ExportResult(
            file_path="/exports/report.pdf",
            format="pdf",
            entity_type="trip",
            file_size=12345,
            generated_at=now,
        )
        assert r.file_path == "/exports/report.pdf"
        assert r.file_size == 12345

    def test_export_result_zero_size(self):
        now = datetime.now()
        r = ExportResult(
            file_path="/exports/empty.csv",
            format="csv",
            entity_type="invoice",
            file_size=0,
            generated_at=now,
        )
        assert r.file_size == 0
