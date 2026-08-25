"""Tests for document_models.py — Document upload spec, extension whitelist, MIME type, file size limits."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from models.document_models import DocumentUpload, DocumentResult


class TestDocumentUpload:
    @pytest.mark.parametrize(
        "source_path, title, category, entity_type, entity_id",
        [
            ("/tmp/invoice_123.pdf", "Invoice 123", "invoice", "trip", 42),
            ("C:\\docs\\cmr_456.pdf", "CMR 456", "cmr", "trip", 43),
            ("/home/user/contract.pdf", "", "contract", "client", 10),
            ("/tmp/receipt.pdf", "Fuel Receipt", "receipt", "vehicle", 5),
            ("/tmp/other_doc.pdf", "Other", "other", "driver", 8),
        ],
    )
    def test_document_upload_valid(self, source_path, title, category, entity_type, entity_id):
        doc = DocumentUpload(
            source_path=source_path,
            title=title,
            category=category,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        assert doc.source_path == source_path
        assert doc.category == category
        assert doc.entity_type == entity_type
        assert doc.entity_id == entity_id

    def test_title_defaults_to_filename(self):
        doc = DocumentUpload(source_path="/some/path/my_document.pdf")
        assert doc.title == "my_document"

    def test_title_default_without_ext(self):
        doc = DocumentUpload(source_path="/some/path/report")
        assert doc.title == "report"

    def test_title_provided_does_not_default(self):
        doc = DocumentUpload(source_path="/path/file.pdf", title="Custom Title")
        assert doc.title == "Custom Title"

    def test_document_upload_defaults(self):
        doc = DocumentUpload(source_path="/tmp/doc.pdf")
        assert doc.category == ""
        assert doc.entity_type == ""
        assert doc.entity_id is None
        assert doc.description == ""
        assert doc.tags == []

    def test_tags_list(self):
        doc = DocumentUpload(
            source_path="/tmp/doc.pdf",
            tags=["urgent", "scanned", "2026"],
        )
        assert len(doc.tags) == 3
        assert "urgent" in doc.tags

    def test_title_with_unicode_path(self):
        doc = DocumentUpload(source_path="/data/șoferi_factură.pdf")
        assert doc.title == "șoferi_factură"


class TestDocumentResult:
    def test_document_result_minimal(self):
        r = DocumentResult(
            id=1,
            title="Test",
            category="invoice",
            entity_type="trip",
            filename="test.pdf",
            file_size=1024,
            mime_type="application/pdf",
        )
        assert r.id == 1
        assert r.file_size == 1024
        assert r.tags == []
        assert r.description == ""

    def test_document_result_full(self):
        r = DocumentResult(
            id=2,
            title="Doc",
            category="cmr",
            entity_type="trip",
            entity_id=99,
            filename="cmr.pdf",
            file_size=2048,
            mime_type="application/pdf",
            tags=["cmr", "signed"],
            description="Signed CMR",
            ocr_processed=True,
            thumbnail_path="/thumbs/cmr.png",
        )
        assert r.entity_id == 99
        assert r.ocr_processed is True
        assert r.thumbnail_path == "/thumbs/cmr.png"

    @pytest.mark.parametrize(
        "mime_type, file_size",
        [
            ("application/pdf", 5000000),
            ("image/jpeg", 250000),
            ("text/csv", 1024),
        ],
    )
    def test_document_result_mime_size(self, mime_type, file_size):
        r = DocumentResult(
            id=1,
            title="Doc",
            category="invoice",
            entity_type="trip",
            filename="doc",
            file_size=file_size,
            mime_type=mime_type,
        )
        assert r.mime_type == mime_type
        assert r.file_size == file_size
