"""Tests for Celery tasks — execution, retry logic, result handling, error handling.

Uses CELERY_ALWAYS_EAGER=True so tasks run synchronously in the test process.
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Force eager mode BEFORE importing any celery task modules
os.environ.setdefault("CELERY_ALWAYS_EAGER", "true")
os.environ.setdefault("CELERY_EAGER_PROPAGATES_EXCEPTIONS", "true")

from backend.celery_app.tasks.ocr_tasks import (
    batch_ocr_documents,
    flush_gps_batch_to_postgres,
    process_document_ocr,
)
from backend.celery_app.tasks.document_tasks import (
    build_email_package,
    generate_document_pdf,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_db_manager(monkeypatch):
    """Mock DatabaseManager to avoid real file I/O and schema init."""
    mock_db = MagicMock()
    mock_db.conn = MagicMock()
    mock_db.conn.execute.return_value.fetchone.return_value = None
    mock_db.conn.execute.return_value.fetchall.return_value = []
    mock_db.conn.cursor.return_value.lastrowid = 1

    def _fake_init(self, db_path, engine=""):
        self._engine = engine or "sqlite"
        self._pool = None
        self.conn = mock_db.conn
        self.user_company_id = None
        self.user_role = ""

    monkeypatch.setattr("database.db_manager.DatabaseManager.__init__", _fake_init)
    monkeypatch.setattr("database.db_manager.DatabaseManager.close", lambda self: None)
    return mock_db


@pytest.fixture
def mock_doc_service(monkeypatch):
    """Mock DocumentService to return a fake document."""
    mock_svc = MagicMock()
    mock_svc.get_by_id.return_value = {
        "id": 1,
        "file_path": "/fake/path.pdf",
        "file_name": "test.pdf",
        "title": "Test Document",
    }
    monkeypatch.setattr("services.document_service.DocumentService", lambda db: mock_svc)
    return mock_svc


# ── process_document_ocr ────────────────────────────────────────────────────


class TestProcessDocumentOcr:
    def test_document_not_found(self, mock_doc_service):
        mock_doc_service.get_by_id.return_value = None
        result = process_document_ocr(999)
        assert result["error"] == "Document not found"
        assert result["document_id"] == 999

    def test_no_file_path(self, mock_doc_service):
        mock_doc_service.get_by_id.return_value = {"id": 1, "file_path": ""}
        result = process_document_ocr(1)
        assert result["error"] == "No file path"

    def test_file_not_on_disk(self, mock_doc_service):
        mock_doc_service.get_by_id.return_value = {"id": 1, "file_path": "/nonexistent/file.pdf"}
        result = process_document_ocr(1)
        assert result["error"] == "File not on disk"

    @patch("backend.celery_app.tasks.ocr_tasks.extract_ocr_data")
    def test_successful_ocr(self, mock_extract, mock_doc_service, _mock_db_manager):
        mock_extract.return_value = {"text": "hello world", "fields": {"amount": 100}}
        result = process_document_ocr(1, engine="tesseract")
        assert result["status"] == "ok"
        assert result["document_id"] == 1
        assert result["engine"] == "tesseract"
        assert result["text_length"] == 11
        assert result["field_count"] == 1

    @patch("backend.celery_app.tasks.ocr_tasks.extract_ocr_data")
    def test_ocr_returns_none(self, mock_extract, mock_doc_service, _mock_db_manager):
        mock_extract.return_value = None
        result = process_document_ocr(1)
        assert result["status"] == "ok"

    @patch("backend.celery_app.tasks.ocr_tasks.extract_ocr_data")
    def test_extract_raises_exception(self, mock_extract, mock_doc_service, _mock_db_manager):
        mock_extract.side_effect = Exception("OCR engine crashed")
        result = process_document_ocr(1)
        assert result["error"] == "OCR engine crashed"

    def test_db_update_fails(self, mock_doc_service, _mock_db_manager):
        _mock_db_manager.conn.execute.side_effect = Exception("DB locked")
        result = process_document_ocr(1)
        assert "DB update failed" in result["error"]


# ── batch_ocr_documents ─────────────────────────────────────────────────────


class TestBatchOcrDocuments:
    def test_batch_returns_enqueued(self):
        result = batch_ocr_documents([1, 2, 3])
        assert result["status"] == "batch_enqueued"
        assert len(result["tasks"]) == 3
        for task in result["tasks"]:
            assert "task_id" in task

    def test_batch_empty_list(self):
        result = batch_ocr_documents([])
        assert result["status"] == "batch_enqueued"
        assert result["tasks"] == []


# ── flush_gps_batch_to_postgres ─────────────────────────────────────────────


class TestFlushGpsBatch:
    def test_redis_unavailable(self, monkeypatch, _mock_db_manager):
        mock_cache = MagicMock()
        mock_cache._enabled = False
        monkeypatch.setattr("backend.celery_app.tasks.ocr_tasks.get_cache", lambda: mock_cache)
        result = flush_gps_batch_to_postgres()
        assert result["status"] == "redis_unavailable"

    def test_no_pending_data(self, monkeypatch, _mock_db_manager):
        mock_cache = MagicMock()
        mock_cache._enabled = True
        mock_cache.lpop.return_value = None
        monkeypatch.setattr("backend.celery_app.tasks.ocr_tasks.get_cache", lambda: mock_cache)
        result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 0

    def test_flushes_one_item(self, monkeypatch, _mock_db_manager):
        mock_cache = MagicMock()
        mock_cache._enabled = True
        ping = json.dumps({
            "truck_id": 1, "latitude": 45.0, "longitude": 25.0,
            "speed_kmh": 60, "heading": 90, "driver_id": 1, "timestamp": "2025-01-01T00:00:00Z",
        })
        mock_cache.lpop.side_effect = [ping, None]
        monkeypatch.setattr("backend.celery_app.tasks.ocr_tasks.get_cache", lambda: mock_cache)
        result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 1

    def test_flushes_multiple_items(self, monkeypatch, _mock_db_manager):
        mock_cache = MagicMock()
        mock_cache._enabled = True
        pings = [
            json.dumps({"truck_id": i, "latitude": 45.0 + i, "longitude": 25.0,
                        "speed_kmh": 60, "heading": 90, "driver_id": 1,
                        "timestamp": "2025-01-01T00:00:00Z"})
            for i in range(3)
        ]
        mock_cache.lpop.side_effect = pings + [None]
        monkeypatch.setattr("backend.celery_app.tasks.ocr_tasks.get_cache", lambda: mock_cache)
        result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 3

    def test_invalid_json_skipped(self, monkeypatch, _mock_db_manager):
        mock_cache = MagicMock()
        mock_cache._enabled = True
        mock_cache.lpop.side_effect = ["not-json", None]
        monkeypatch.setattr("backend.celery_app.tasks.ocr_tasks.get_cache", lambda: mock_cache)
        result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 0


# ── generate_document_pdf ───────────────────────────────────────────────────


class TestGenerateDocumentPdf:
    def test_document_not_found(self, mock_doc_service):
        mock_doc_service.get_by_id.return_value = None
        result = generate_document_pdf(999, "default")
        assert result["error"] == "Document not found"

    def test_source_file_not_found(self, mock_doc_service):
        mock_doc_service.get_by_id.return_value = {"id": 1, "file_path": "/nonexistent.pdf"}
        result = generate_document_pdf(1, "default")
        assert result["error"] == "Source file not found"

    @patch("backend.celery_app.tasks.document_tasks.InvoiceGenerator")
    @patch("backend.celery_app.tasks.document_tasks.load_company_config")
    def test_generates_pdf(self, mock_load_config, mock_gen_cls, mock_doc_service, _mock_db_manager):
        # Create a real temp file for the source path
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        try:
            mock_doc_service.get_by_id.return_value = {
                "id": 1, "file_path": tmp.name, "file_name": "test.pdf",
            }
            mock_gen = MagicMock()
            mock_gen_cls.return_value = mock_gen
            result = generate_document_pdf(1, "default")
            assert result["status"] == "ok"
            assert result["document_id"] == 1
            assert result["template"] == "default"
            assert "output_path" in result
        finally:
            os.unlink(tmp.name)

    def test_pdf_generation_exception_triggers_retry(self, mock_doc_service, _mock_db_manager):
        """When an exception occurs, the task raises to trigger Celery retry."""
        mock_doc_service.get_by_id.side_effect = Exception("Unexpected error")
        with pytest.raises(Exception, match="Unexpected error"):
            generate_document_pdf(1, "default")


# ── build_email_package ─────────────────────────────────────────────────────


class TestBuildEmailPackage:
    def test_no_documents(self, mock_doc_service, _mock_db_manager):
        mock_doc_service.get_by_id.return_value = None
        result = build_email_package([], "test@test.com")
        assert result["status"] == "ok"
        assert result["document_count"] == 0

    def test_builds_package(self, mock_doc_service, _mock_db_manager):
        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        tmp.write(b"hello")
        tmp.close()
        try:
            mock_doc_service.get_by_id.return_value = {
                "id": 1, "file_path": tmp.name, "file_name": "test.txt",
            }
            result = build_email_package([1], "test@test.com")
            assert result["status"] == "ok"
            assert result["document_count"] == 1
            assert result["recipient"] == "test@test.com"
            assert result["zip_size"] > 0
        finally:
            os.unlink(tmp.name)

    def test_package_exception_triggers_retry(self, mock_doc_service, _mock_db_manager):
        mock_doc_service.get_by_id.side_effect = Exception("Build failed")
        with pytest.raises(Exception, match="Build failed"):
            build_email_package([1], "test@test.com")
