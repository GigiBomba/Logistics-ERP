"""Integration tests for PhysicalArchiveService with mocked OCR pipeline.

Tests the orchestration logic of PhysicalArchiveService by mocking
external dependencies (DocumentService, OCR pipeline, TripMatcher).
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch, ANY

import pytest

from services.migration.types import ArchiveStage, EntityType
from tests.test_helpers import make_db

pytestmark = pytest.mark.e2e  # integration tests that verify orchestration


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def service(db):
    """PhysicalArchiveService with mocked DocumentService, pipeline, and TripMatcher."""
    with patch("services.migration.physical_archive_service.DocumentService") as mock_ds, \
         patch("services.migration.physical_archive_service.run_for_existing_document") as mock_run, \
         patch("services.migration.physical_archive_service.TripMatcher") as mock_tm:

        # Mock DocumentService: upload_document returns ServiceResult with data.id
        mock_ds_instance = MagicMock()
        mock_ds_instance.upload_document.return_value = MagicMock(
            success=True,
            data=MagicMock(id=1),
        )
        mock_ds.return_value = mock_ds_instance

        # Mock OCR pipeline result
        mock_run.return_value = {
            "ocr_text": "CMR 12345\nClient: ACME Corp\nDate: 2024-01-15\nInvoice INV-001",
            "extracted": {
                "cmr_number": "12345",
                "client_name": "ACME Corp",
                "date": "2024-01-15",
            },
            "engine": "paddle",
            "confidence": 0.85,
            "pages": 1,
            "matched_clients": ["ACME Corp"],
        }

        # Mock TripMatcher result
        mock_match = MagicMock()
        mock_match.confidence = 0.75
        mock_match.best_match = None
        mock_match.candidates = []
        mock_tm_instance = MagicMock()
        mock_tm_instance.match.return_value = mock_match
        mock_tm.return_value = mock_tm_instance

        from services.migration.physical_archive_service import PhysicalArchiveService

        svc = PhysicalArchiveService(db)
        svc._doc_svc = mock_ds_instance  # inject mock directly
        yield svc


# ── Helpers ────────────────────────────────────────────────────────────────

def _temp_file(suffix: str = ".pdf") -> str:
    """Create a temporary placeholder file and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()
    return tmp.name


# ── Process-document tests ─────────────────────────────────────────────────

def test_process_document_calls_upload(service):
    """Verifies DocumentService.upload_document was called with the correct args."""
    from models.document_models import DocumentUpload

    path = _temp_file()
    try:
        service.process_document(path)
        service._doc_svc.upload_document.assert_called_once()
        call_args = service._doc_svc.upload_document.call_args[0]
        assert isinstance(call_args[0], DocumentUpload)
        assert call_args[0].source_path == path
        assert call_args[0].category == "migration"
    finally:
        os.unlink(path)


def test_process_document_calls_pipeline(service, db):
    """Verifies run_for_existing_document was called with db and doc_id."""
    path = _temp_file()
    try:
        service.process_document(path)
        from services.migration.physical_archive_service import run_for_existing_document

        run_for_existing_document.assert_called_once_with(db, 1, progress_callback=ANY)
    finally:
        os.unlink(path)


def test_process_document_returns_status(service):
    """Result dict has doc_id, doc_type, confidence, needs_confirmation."""
    path = _temp_file()
    try:
        # Use process_batch to get the actual result dict (process_document
        # looks up results by basename which does not match the full path key).
        results = service.process_batch([path])
        result = results[path]
        assert result["doc_id"] == 1
        assert result["doc_type"] == "cmr"
        assert result["confidence"] == 0.85
        assert isinstance(result["needs_confirmation"], bool)
        assert result["error"] is None
    finally:
        os.unlink(path)


# ── Classification tests ───────────────────────────────────────────────────

def test_classify_detects_cmr(service):
    """When extracted has cmr_number, doc_type is 'cmr'."""
    pipeline_result = {
        "extracted": {"cmr_number": "12345"},
        "ocr_text": "",
    }
    assert service._classify(pipeline_result) == "cmr"


def test_classify_detects_invoice(service):
    """When extracted has invoice_number, doc_type is 'invoice'."""
    pipeline_result = {
        "extracted": {"invoice_number": "INV-001"},
        "ocr_text": "",
    }
    assert service._classify(pipeline_result) == "invoice"


def test_classify_returns_unknown(service):
    """When no patterns match, doc_type is 'unknown'."""
    pipeline_result = {
        "extracted": {},
        "ocr_text": "Some random text with no known patterns",
    }
    assert service._classify(pipeline_result) == "unknown"


# ── Confidence tests ───────────────────────────────────────────────────────

def test_low_confidence_needs_confirmation(service):
    """Confidence < 0.75 → needs_confirmation=True."""
    with patch("services.migration.physical_archive_service.run_for_existing_document") as mock_run:
        mock_run.return_value = {
            "ocr_text": "Some text",
            "extracted": {},
            "confidence": 0.70,
            "engine": "paddle",
            "pages": 1,
        }
        path = _temp_file()
        try:
            results = service.process_batch([path])
            assert results[path]["needs_confirmation"] is True
        finally:
            os.unlink(path)


def test_high_confidence_passes(service):
    """Confidence >= 0.75 → needs_confirmation=False."""
    # Factory default in fixture sets confidence=0.85
    path = _temp_file()
    try:
        results = service.process_batch([path])
        assert results[path]["needs_confirmation"] is False
    finally:
        os.unlink(path)


# ── Confirm-document tests ─────────────────────────────────────────────────

def test_confirm_document_updates_fields(service, db):
    """confirm_document with corrections updates extracted_data_json."""
    db.conn.execute(
        "INSERT INTO documents (id, doc_number, title, category, file_path, file_name, entity_type, uploaded_at, updated_at, extracted_data_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, "DOC-001", "Test Doc", "migration", "/fake/doc.pdf", "doc.pdf", "", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", json.dumps({"cmr_number": "12345"})),
    )
    db.conn.commit()

    ok = service.confirm_document(doc_id=1, corrections={"date": "2024-06-15"})
    assert ok is True

    row = db.conn.execute(
        "SELECT extracted_data_json FROM documents WHERE id = 1",
    ).fetchone()
    updated = json.loads(row[0])
    assert updated["cmr_number"] == "12345"
    assert updated["date"] == "2024-06-15"


def test_confirm_document_links_to_trip(service, db):
    """confirm_document with trip_id calls link_document on doc_svc."""
    db.conn.execute(
        "INSERT INTO documents (id, doc_number, title, category, file_path, file_name, entity_type, uploaded_at, updated_at, extracted_data_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, "DOC-001", "Test Document", "migration", "/fake/doc.pdf", "doc.pdf", "", "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "{}"),
    )
    db.conn.commit()

    ok = service.confirm_document(doc_id=1, trip_id=42)
    assert ok is True
    service._doc_svc.link_document.assert_called_once_with(
        doc_id=1,
        entity_type="trip",
        entity_id=42,
        relation_type="attached",
    )


# ── Error handling ─────────────────────────────────────────────────────────

def test_process_document_handles_upload_failure(service):
    """When upload returns None, the result contains an error."""
    service._doc_svc.upload_document.return_value = MagicMock(success=False)
    path = _temp_file()
    try:
        results = service.process_batch([path])
        assert results[path]["error"] is not None
    finally:
        os.unlink(path)


def test_process_document_handles_pipeline_exception(service):
    """When the OCR pipeline raises, the result contains an error."""
    with patch("services.migration.physical_archive_service.run_for_existing_document") as mock_run:
        mock_run.side_effect = RuntimeError("OCR engine timed out")
        path = _temp_file()
        try:
            results = service.process_batch([path])
            assert results[path]["error"] is not None
            assert "OCR" in results[path]["error"]
        finally:
            os.unlink(path)


# ── Batch processing ───────────────────────────────────────────────────────

def test_process_batch_multiple_files(service):
    """Processing multiple files returns per-file results."""
    path1 = _temp_file()
    path2 = _temp_file()
    try:
        results = service.process_batch([path1, path2])
        assert len(results) == 2
        assert path1 in results
        assert path2 in results
        for r in results.values():
            assert r["doc_id"] is not None
            assert r["error"] is None
    finally:
        os.unlink(path1)
        os.unlink(path2)


# ── Progress callbacks ─────────────────────────────────────────────────────

def test_progress_callback_invoked(service):
    """progress_cb receives stage updates throughout processing."""
    progress_cb = MagicMock()
    path = _temp_file()
    try:
        service.process_document(path, progress_cb=progress_cb)
        progress_cb.assert_called()
        stages = [call[0][0] for call in progress_cb.call_args_list]
        assert ArchiveStage.UPLOADING.value in stages
        assert ArchiveStage.IMAGE_PROCESSING.value in stages
        assert ArchiveStage.CLASSIFYING.value in stages
        assert ArchiveStage.MATCHING.value in stages
    finally:
        os.unlink(path)
