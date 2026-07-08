"""Tests for Celery tasks — execution, retry logic, result handling, error handling.

Uses CELERY_ALWAYS_EAGER=True so tasks run synchronously in the test process.
Environment variables are set BEFORE any celery import to avoid real Redis.
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Force eager mode and memory backend BEFORE any celery imports
os.environ.setdefault("CELERY_ALWAYS_EAGER", "true")
os.environ.setdefault("CELERY_EAGER_PROPAGATES_EXCEPTIONS", "true")
os.environ.setdefault("OPERION_CELERY_BROKER", "memory://")
os.environ.setdefault("OPERION_CELERY_RESULT", "cache+memory://")
os.environ.setdefault("OPERION_REDIS_URL", "memory://")

# Now safe to import
from backend.celery_app.tasks.ocr_tasks import (  # noqa: E402
    batch_ocr_documents,
    flush_gps_batch_to_postgres,
    process_document_ocr,
)
from backend.celery_app.tasks.document_tasks import (  # noqa: E402
    build_email_package,
    generate_document_pdf,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def _mock_db(monkeypatch):
    """Mock DatabaseManager to avoid real file I/O and schema init."""
    mock_db = MagicMock(spec=["conn", "close", "user_company_id", "user_role"])
    mock_conn = MagicMock()
    mock_db.conn = mock_conn

    class _FakePool:
        def __init__(self, c):
            self._db_conn = c

        @property
        def conn(self):
            return self._db_conn

        def close_all(self):
            pass

    def _fake_init(self, db_path, engine=""):
        self._engine = engine or "sqlite"
        self._pool = _FakePool(mock_conn)
        self._pg_conn = None
        self.user_company_id = None
        self.user_role = ""

    monkeypatch.setattr("database.db_manager.DatabaseManager.__init__", _fake_init)
    monkeypatch.setattr("database.db_manager.DatabaseManager.close", lambda self: None)
    return mock_db


@pytest.fixture
def _mock_doc_service(monkeypatch):
    """Mock DocumentService to return a fake document."""
    mock_svc = MagicMock()
    mock_svc.get_by_id.return_value = {
        "id": 1,
        "file_path": "/fake/path.pdf",
        "file_name": "test.pdf",
        "title": "Test Document",
    }
    monkeypatch.setattr(
        "backend.celery_app.tasks.ocr_tasks.DocumentService", lambda db: mock_svc
    )
    monkeypatch.setattr(
        "backend.celery_app.tasks.document_tasks.DocumentService", lambda db: mock_svc
    )
    return mock_svc


@pytest.fixture
def _real_file():
    """Create a temporary file for tasks that need a real file on disk."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(b"dummy pdf content")
    tmp.close()
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


# ── process_document_ocr ────────────────────────────────────────────────────


class TestProcessDocumentOcr:
    def test_document_not_found(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = None
        result = process_document_ocr(999)
        assert result["error"] == "Document not found"
        assert result["document_id"] == 999

    def test_no_file_path(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = {"id": 1, "file_path": ""}
        result = process_document_ocr(1)
        assert result["error"] == "No file path"

    def test_file_not_on_disk(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": "/nonexistent/file.pdf"
        }
        result = process_document_ocr(1)
        assert result["error"] == "File not on disk"

    @patch(
        "services.document_automation.ocr_extractor.extract_ocr_data",
        create=True,
    )
    def test_successful_ocr(
        self, mock_extract, _mock_db, _mock_doc_service, _real_file
    ):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.pdf",
        }
        mock_extract.return_value = {"text": "hello world", "fields": {"amount": 100}}
        result = process_document_ocr(1, engine="tesseract")
        assert result["status"] == "ok"
        assert result["document_id"] == 1
        assert result["engine"] == "tesseract"
        assert result["text_length"] == 11
        assert result["field_count"] == 1

    @patch(
        "services.document_automation.ocr_extractor.extract_ocr_data",
        create=True,
    )
    def test_ocr_returns_none(
        self, mock_extract, _mock_db, _mock_doc_service, _real_file
    ):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.pdf",
        }
        mock_extract.return_value = None
        result = process_document_ocr(1)
        assert result["status"] == "ok"

    @patch(
        "services.document_automation.ocr_extractor.extract_ocr_data",
        create=True,
    )
    def test_extract_raises_exception(
        self, mock_extract, _mock_db, _mock_doc_service, _real_file
    ):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.pdf",
        }
        mock_extract.side_effect = Exception("OCR engine crashed")
        result = process_document_ocr(1)
        assert result["error"] == "OCR engine crashed"

    @patch(
        "services.document_automation.ocr_extractor.extract_ocr_data",
        create=True,
    )
    def test_db_update_fails(
        self, mock_extract, _mock_db, _mock_doc_service, _real_file
    ):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.pdf",
        }
        mock_extract.return_value = {"text": "test", "fields": {}}
        _mock_db.conn.execute.side_effect = Exception("DB locked")
        result = process_document_ocr(1)
        assert "DB update failed" in result["error"]


# ── batch_ocr_documents ─────────────────────────────────────────────────────


class TestBatchOcrDocuments:
    def test_batch_empty_list(self, _mock_db, _mock_doc_service):
        result = batch_ocr_documents([])
        assert result["status"] == "batch_enqueued"
        assert result["tasks"] == []

    def test_batch_with_docs(self, _mock_db, _mock_doc_service):
        """Enqueue three OCR tasks via .delay()."""
        with patch.object(process_document_ocr, "delay") as mock_delay:
            mock_delay.return_value = MagicMock(id="fake-task-id")
            result = batch_ocr_documents([1, 2, 3])
        assert result["status"] == "batch_enqueued"
        assert len(result["tasks"]) == 3
        assert mock_delay.call_count == 3


# ── flush_gps_batch_to_postgres ─────────────────────────────────────────────


class TestFlushGpsBatch:
    def test_redis_unavailable(self, _mock_db):
        with patch("backend.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache._enabled = False
            mock_get_cache.return_value = mock_cache
            result = flush_gps_batch_to_postgres()
        assert result["status"] == "redis_unavailable"

    def test_no_pending_data(self, _mock_db):
        with patch("backend.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache._enabled = True
            mock_cache.lpop.return_value = None
            mock_get_cache.return_value = mock_cache
            result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 0

    def test_flushes_one_item(self, _mock_db):
        with patch("backend.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache._enabled = True
            ping = json.dumps({
                "truck_id": 1, "latitude": 45.0, "longitude": 25.0,
                "speed_kmh": 60, "heading": 90, "driver_id": 1,
                "timestamp": "2025-01-01T00:00:00Z",
            })
            mock_cache.lpop.side_effect = [ping, None]
            mock_get_cache.return_value = mock_cache
            result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 1

    def test_flushes_multiple_items(self, _mock_db):
        with patch("backend.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache._enabled = True
            pings = [
                json.dumps({
                    "truck_id": i, "latitude": 45.0 + i, "longitude": 25.0,
                    "speed_kmh": 60, "heading": 90, "driver_id": 1,
                    "timestamp": "2025-01-01T00:00:00Z",
                })
                for i in range(3)
            ]
            mock_cache.lpop.side_effect = pings + [None]
            mock_get_cache.return_value = mock_cache
            result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 3

    def test_invalid_json_raises(self, _mock_db):
        """Invalid JSON raises — the task does not trap json.loads errors."""
        with patch("backend.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache._enabled = True
            mock_cache.lpop.side_effect = ["not-json", None]
            mock_get_cache.return_value = mock_cache
            with pytest.raises(json.decoder.JSONDecodeError):
                flush_gps_batch_to_postgres()


# ── generate_document_pdf ───────────────────────────────────────────────────


class TestGenerateDocumentPdf:
    def test_document_not_found(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = None
        result = generate_document_pdf(999, "default")
        assert result["error"] == "Document not found"

    def test_source_file_not_found(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": "/nonexistent.pdf"
        }
        result = generate_document_pdf(1, "default")
        assert result["error"] == "Source file not found"

    @patch("services.invoicing.config_manager.load_company_config")
    @patch("services.invoicing.generator.InvoiceGenerator")
    def test_generates_pdf(
        self, mock_gen_cls, mock_load_config, _mock_db, _mock_doc_service, _real_file
    ):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.pdf",
        }
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        result = generate_document_pdf(1, "default")
        assert result["status"] == "ok"
        assert result["document_id"] == 1
        assert result["template"] == "default"
        assert "output_path" in result

    def test_pdf_generation_exception_triggers_retry(
        self, _mock_db, _mock_doc_service
    ):
        """When an exception occurs, the task raises to trigger Celery retry."""
        _mock_doc_service.get_by_id.side_effect = Exception("Unexpected error")
        with pytest.raises(Exception, match="Unexpected error"):
            generate_document_pdf(1, "default")


# ── build_email_package ─────────────────────────────────────────────────────


class TestBuildEmailPackage:
    def test_no_documents(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = None
        result = build_email_package([], "test@test.com")
        assert result["status"] == "ok"
        assert result["document_count"] == 0

    def test_builds_package(self, _mock_db, _mock_doc_service, _real_file):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.txt",
        }
        result = build_email_package([1], "test@test.com")
        assert result["status"] == "ok"
        assert result["document_count"] == 1
        assert result["recipient"] == "test@test.com"
        assert result["zip_size"] > 0

    def test_package_exception_triggers_retry(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.side_effect = Exception("Build failed")
        with pytest.raises(Exception, match="Build failed"):
            build_email_package([1], "test@test.com")
