"""Tests for Celery tasks — execution, retry logic, result handling, error handling.

Uses CELERY_ALWAYS_EAGER=True so tasks run synchronously in the test process.
Environment variables are set BEFORE any celery import to avoid real Redis.
"""

from __future__ import annotations

import json
import logging
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
    yield mock_db
    # Tasks such as flush_gps_batch_to_postgres call set_company_context;
    # reset the tenant context so it does not leak into unrelated tests.
    from database.tenant_context import clear_context
    clear_context()


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
        result = process_document_ocr(999, company_id=1)
        assert result["error"] == "Document not found"
        assert result["document_id"] == 999

    def test_no_file_path(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = {"id": 1, "file_path": ""}
        result = process_document_ocr(1, company_id=1)
        assert result["error"] == "No file path"

    def test_file_not_on_disk(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": "/nonexistent/file.pdf"
        }
        result = process_document_ocr(1, company_id=1)
        assert result["error"] == "File not on disk"

    @patch(
        "services.document_automation.ocr_extractor.OcrExtractor.extract",
        create=True,
    )
    def test_successful_ocr(
        self, mock_extract, _mock_db, _mock_doc_service, _real_file
    ):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.pdf",
        }
        from services.document_automation.ocr_extractor import ExtractionResult
        mock_extract.return_value = ExtractionResult(
            full_text="hello world", extracted={"amount": 100},
            confidence=0.95, engine="tesseract", pages_processed=1,
        )
        result = process_document_ocr(1, company_id=1, engine="tesseract")
        assert result["status"] == "ok"
        assert result["document_id"] == 1
        assert result["engine"] == "tesseract"
        assert result["text_length"] == 11
        assert result["field_count"] == 1

    @patch(
        "services.document_automation.ocr_extractor.OcrExtractor.extract",
        create=True,
    )
    def test_ocr_returns_none(
        self, mock_extract, _mock_db, _mock_doc_service, _real_file
    ):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.pdf",
        }
        mock_extract.return_value = None
        result = process_document_ocr(1, company_id=1)
        assert result["status"] == "ok"

    @patch(
        "services.document_automation.ocr_extractor.OcrExtractor.extract",
        create=True,
    )
    def test_extract_raises_exception(
        self, mock_extract, _mock_db, _mock_doc_service, _real_file
    ):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.pdf",
        }
        mock_extract.side_effect = Exception("OCR engine crashed")
        result = process_document_ocr(1, company_id=1)
        assert result["error"] == "OCR engine crashed"

    @patch(
        "services.document_automation.ocr_extractor.OcrExtractor.extract",
        create=True,
    )
    def test_db_update_fails(
        self, mock_extract, _mock_db, _mock_doc_service, _real_file
    ):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.pdf",
        }
        from services.document_automation.ocr_extractor import ExtractionResult
        mock_extract.return_value = ExtractionResult(
            full_text="test", extracted={},
            confidence=0.9, engine="tesseract", pages_processed=1,
        )
        _mock_db.conn.execute.side_effect = Exception("DB locked")
        result = process_document_ocr(1, company_id=1)
        assert "DB update failed" in result["error"]


# ── batch_ocr_documents ─────────────────────────────────────────────────────


class TestBatchOcrDocuments:
    def test_batch_empty_list(self, _mock_db, _mock_doc_service):
        result = batch_ocr_documents([], company_id=1)
        assert result["status"] == "batch_enqueued"
        assert result["tasks"] == []

    def test_batch_with_docs(self, _mock_db, _mock_doc_service):
        """Enqueue three OCR tasks via .delay()."""
        with patch.object(process_document_ocr, "delay") as mock_delay:
            mock_delay.return_value = MagicMock(id="fake-task-id")
            result = batch_ocr_documents([1, 2, 3], company_id=1)
        assert result["status"] == "batch_enqueued"
        assert len(result["tasks"]) == 3
        assert mock_delay.call_count == 3


# ── flush_gps_batch_to_postgres ─────────────────────────────────────────────


class TestFlushGpsBatch:
    """GPS batch flush: per-company queues, tenant-safe writes, retry-safe drain.

    The task is scheduled globally (beat, every 30 s).  It drains the
    per-company ``gps:batch:{company_id}`` queues, so every test stubs
    ``CompanyRepository.get_active_ids`` and asserts the tenant-scoped key.
    """

    def test_redis_unavailable(self, _mock_db):
        with patch("backend.cache.get_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache._enabled = False
            mock_get_cache.return_value = mock_cache
            result = flush_gps_batch_to_postgres()
        assert result["status"] == "redis_unavailable"

    def test_no_pending_data(self, _mock_db):
        with (
            patch("backend.cache.get_cache") as mock_get_cache,
            patch(
                "repositories.company_repository.CompanyRepository.get_active_ids",
                return_value=[1],
            ),
        ):
            mock_cache = MagicMock()
            mock_cache._enabled = True
            mock_cache.lrange.return_value = []
            mock_get_cache.return_value = mock_cache
            result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 0
        mock_cache.ltrim.assert_not_called()

    def test_flushes_one_item(self, _mock_db):
        with (
            patch("backend.cache.get_cache") as mock_get_cache,
            patch(
                "repositories.company_repository.CompanyRepository.get_active_ids",
                return_value=[1],
            ),
        ):
            mock_cache = MagicMock()
            mock_cache._enabled = True
            ping = json.dumps({
                "truck_id": 1, "latitude": 45.0, "longitude": 25.0,
                "speed_kmh": 60, "heading": 90, "driver_id": 1,
                "timestamp": "2025-01-01T00:00:00Z",
            })
            mock_cache.lrange.return_value = [ping]
            mock_get_cache.return_value = mock_cache
            result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 1
        # Drains the TENANT-scoped queue key, then removes the processed
        # items AFTER the DB insert/commit (delete-after-commit).
        mock_cache.lrange.assert_called_once_with("gps:batch:1", 0, -1)
        mock_cache.ltrim.assert_called_once_with("gps:batch:1", 1, -1)

    def test_flushes_multiple_items(self, _mock_db):
        with (
            patch("backend.cache.get_cache") as mock_get_cache,
            patch(
                "repositories.company_repository.CompanyRepository.get_active_ids",
                return_value=[1],
            ),
        ):
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
            mock_cache.lrange.return_value = pings
            mock_get_cache.return_value = mock_cache
            result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 3
        mock_cache.ltrim.assert_called_once_with("gps:batch:1", 3, -1)

    def test_flushes_each_company_queue_separately(self, _mock_db):
        """Every company drains its OWN ``gps:batch:{company_id}`` key."""
        with (
            patch("backend.cache.get_cache") as mock_get_cache,
            patch(
                "repositories.company_repository.CompanyRepository.get_active_ids",
                return_value=[1, 2],
            ),
        ):
            mock_cache = MagicMock()
            mock_cache._enabled = True
            ping = json.dumps({
                "truck_id": 1, "latitude": 45.0, "longitude": 25.0,
                "speed_kmh": 60, "heading": 90, "driver_id": 1,
                "timestamp": "2025-01-01T00:00:00Z",
            })
            mock_cache.lrange.return_value = [ping]
            mock_get_cache.return_value = mock_cache
            result = flush_gps_batch_to_postgres()
        assert result["status"] == "ok"
        assert result["flushed"] == 2
        keys = [call.args[0] for call in mock_cache.lrange.call_args_list]
        assert keys == ["gps:batch:1", "gps:batch:2"]

    def test_invalid_json_raises(self, _mock_db):
        """Invalid JSON raises — Celery retries the task (no silent loss)."""
        with (
            patch("backend.cache.get_cache") as mock_get_cache,
            patch(
                "repositories.company_repository.CompanyRepository.get_active_ids",
                return_value=[1],
            ),
        ):
            mock_cache = MagicMock()
            mock_cache._enabled = True
            mock_cache.lrange.return_value = ["not-json"]
            mock_get_cache.return_value = mock_cache
            with pytest.raises(json.decoder.JSONDecodeError):
                flush_gps_batch_to_postgres()
        # The queue is NOT trimmed on failure → the item is retried, not lost.
        mock_cache.ltrim.assert_not_called()


# ── GpsTelemetryRepository.create_many ──────────────────────────────────────
# Real in-memory DB: company_id injection from tenant context + idempotent
# dedup against the idx_gps_telemetry_unique(truck_id, recorded_at) index.


class TestGpsTelemetryRepository:
    @pytest.fixture
    def db(self):
        from tests.test_helpers import InMemoryDB
        from database.tenant_context import clear_context

        db = InMemoryDB()
        yield db
        clear_context()
        db.close()

    def test_create_many_injects_company_id_from_context(self, db):
        """Records without company_id get it stamped from the tenant context."""
        from database.tenant_context import set_company_context
        from repositories.gps_telemetry_repository import GpsTelemetryRepository

        set_company_context(42)
        repo = GpsTelemetryRepository(db)
        repo.create_many([{
            "truck_id": 1, "latitude": 44.0, "longitude": 25.0,
            "speed_kmh": 60, "heading": 90, "driver_id": 3,
            "recorded_at": "2026-01-01T00:00:00Z",
        }])
        rows = db.rows_to_dicts(db.conn.execute(
            "SELECT * FROM gps_telemetry"
        ).fetchall())
        assert len(rows) == 1
        assert rows[0]["company_id"] == 42

    def test_create_many_preserves_explicit_company_id(self, db):
        """An explicit company_id on the record is never overwritten."""
        from database.tenant_context import set_company_context
        from repositories.gps_telemetry_repository import GpsTelemetryRepository

        set_company_context(7)
        repo = GpsTelemetryRepository(db)
        repo.create_many([{
            "truck_id": 1, "latitude": 44.0, "longitude": 25.0,
            "speed_kmh": 60, "heading": 90, "driver_id": 3,
            "company_id": 99, "recorded_at": "2026-01-01T00:00:00Z",
        }])
        rows = db.rows_to_dicts(db.conn.execute(
            "SELECT * FROM gps_telemetry"
        ).fetchall())
        assert rows[0]["company_id"] == 99

    def test_create_many_dedup_via_unique_index(self, db):
        """A replayed insert (same truck_id + recorded_at) is a no-op."""
        from database.tenant_context import set_company_context
        from repositories.gps_telemetry_repository import GpsTelemetryRepository

        set_company_context(1)
        repo = GpsTelemetryRepository(db)
        record = {
            "truck_id": 7, "latitude": 44.0, "longitude": 25.0,
            "speed_kmh": 60, "heading": 90, "driver_id": 3,
            "recorded_at": "2026-01-01T00:00:00Z",
        }
        first = repo.create_many([record])
        replayed = repo.create_many([record])  # retry / double-process
        rows = db.rows_to_dicts(db.conn.execute(
            "SELECT * FROM gps_telemetry"
        ).fetchall())
        assert first == 1
        assert replayed == 1  # method reports what was attempted
        assert len(rows) == 1, "unique index must suppress the duplicate"
        assert rows[0]["truck_id"] == 7

    def test_flush_uses_insert_or_ignore_sql(self, _mock_db):
        """create_many issues INSERT OR IGNORE (SQLite) for idempotency."""
        from repositories.gps_telemetry_repository import GpsTelemetryRepository

        mock_db = MagicMock()
        mock_db._engine = "sqlite"
        repo = GpsTelemetryRepository(mock_db)
        repo.create_many([{
            "truck_id": 1, "latitude": 44.0, "longitude": 25.0,
            "recorded_at": "2026-01-01T00:00:00Z",
        }])
        sql = mock_db.executemany.call_args[0][0]
        assert "INSERT OR IGNORE INTO gps_telemetry" in sql


# ── generate_document_pdf ───────────────────────────────────────────────────


class TestGenerateDocumentPdf:
    def test_document_not_found(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = None
        result = generate_document_pdf(999, 1, "default")
        assert result["error"] == "Document not found"

    def test_source_file_not_found(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": "/nonexistent.pdf"
        }
        result = generate_document_pdf(1, 1, "default")
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
        result = generate_document_pdf(1, 1, "default")
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
            generate_document_pdf(1, 1, "default")


# ── build_email_package ─────────────────────────────────────────────────────


class TestBuildEmailPackage:
    def test_no_documents(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.return_value = None
        result = build_email_package([], "test@test.com", company_id=1)
        assert result["status"] == "ok"
        assert result["document_count"] == 0

    def test_builds_package(self, _mock_db, _mock_doc_service, _real_file):
        _mock_doc_service.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.txt",
        }
        result = build_email_package([1], "test@test.com", company_id=1)
        assert result["status"] == "ok"
        assert result["document_count"] == 1
        assert result["recipient"] == "test@test.com"
        assert result["zip_size"] > 0

    def test_package_exception_triggers_retry(self, _mock_db, _mock_doc_service):
        _mock_doc_service.get_by_id.side_effect = Exception("Build failed")
        with pytest.raises(Exception, match="Build failed"):
            build_email_package([1], "test@test.com", company_id=1)


# ── build_email_package dedup (roadmap 12) ─────────────────────────────


class TestBuildEmailPackageDedup:
    """Email double-send protection via the sent_emails dedup table.

    UNIQUE(document_id, recipient) + INSERT OR IGNORE means only the first
    invocation that claims the pending row actually sends; a Celery retry
    (or concurrent duplicate) is skipped, and a failed send removes the claim
    so the retry can re-attempt.
    """

    SMTP_PREFS = {"smtp_server": "smtp.test.com", "smtp_user": "user"}

    def test_email_document_signature_accepts_prefs(self):
        """C1 regression: build_email_package calls ``email_document(...,
        prefs=...)`` with the task's SMTP-prefs dict; the real callee
        signature must accept that kwarg.

        This fails on the pre-fix code where ``email_document`` had no
        ``prefs`` parameter (a TypeError at runtime) — invisible to the
        dedup tests because they replace ``email_document`` with a
        ``MagicMock`` that swallows arbitrary kwargs.
        """
        import inspect

        from services.document_service import DocumentService

        sig = inspect.signature(DocumentService.email_document)
        assert "prefs" in sig.parameters, (
            "email_document must accept a prefs kwarg (build_email_package "
            "passes prefs=); found params: %s" % list(sig.parameters)
        )

    @pytest.fixture
    def _dedup_db(self, monkeypatch, tmp_path):
        """File-backed SQLite DB so the sent_emails table is live.

        A file DB is used (not ``:memory:``) because ``build_email_package``
        closes its ``DatabaseManager`` in ``finally`` — an in-memory pool
        would drop the schema/data for the post-task assertions.
        """
        db_path = str(tmp_path / "dedup_email.db")
        import sqlite3
        from database.db_manager import DatabaseManager

        db = DatabaseManager(db_path)
        # sent_emails.document_id has an FK to documents(id) (ON DELETE
        # CASCADE) and SQLite runs with PRAGMA foreign_keys=ON, so the dedup
        # rows need a real document to reference.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR IGNORE INTO documents "
            "(id, doc_number, title, category, entity_type, file_path, "
            " file_name, uploaded_at, updated_at) "
            "VALUES (1, 'DOC-1', 'Test Doc', 'other', '', '/tmp/test.pdf', "
            "        'test.pdf', '2025-01-01T00:00:00', '2025-01-01T00:00:00')"
        )
        conn.commit()
        conn.close()
        monkeypatch.setattr(
            "backend.celery_app.tasks.document_tasks.DatabaseManager",
            lambda *a, **k: db,
        )
        yield db, db_path
        db.close()

    @pytest.fixture
    def _dedup_doc_service(self, monkeypatch, _real_file):
        """Mock DocumentService whose email_document we control per test.

        ``build_email_package`` resolves the service twice: the module-level
        ``DocumentService`` (zip build) and an inner ``from
        backend.services.document_service import DocumentService as DS``
        (email send) — patch both so ``email_document`` is our mock.
        """
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {
            "id": 1, "file_path": _real_file, "file_name": "test.pdf",
            "title": "Test Document",
        }
        monkeypatch.setattr(
            "backend.celery_app.tasks.document_tasks.DocumentService",
            lambda db: mock_svc,
        )
        monkeypatch.setattr(
            "backend.services.document_service.DocumentService",
            lambda db: mock_svc,
        )
        return mock_svc

    def _sent_rows(self, db_path):
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM sent_emails").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def test_first_send_claims_pending_then_marks_sent(
        self, _dedup_db, _dedup_doc_service
    ):
        _, db_path = _dedup_db
        svc = _dedup_doc_service
        svc.email_document = MagicMock()
        result = build_email_package(
            [1], "dedup@test.com", company_id=1, prefs=self.SMTP_PREFS,
        )
        assert result["status"] == "ok"
        assert result["email_sent"] is True
        svc.email_document.assert_called_once()
        rows = self._sent_rows(db_path)
        assert len(rows) == 1
        assert rows[0]["document_id"] == 1
        assert rows[0]["recipient"] == "dedup@test.com"
        assert rows[0]["status"] == "sent"
        assert rows[0]["sent_at"]

    def test_duplicate_call_skips_second_send(self, _dedup_db, _dedup_doc_service):
        _, db_path = _dedup_db
        svc = _dedup_doc_service
        svc.email_document = MagicMock()
        build_email_package([1], "dedup@test.com", company_id=1, prefs=self.SMTP_PREFS)
        dup = build_email_package([1], "dedup@test.com", company_id=1, prefs=self.SMTP_PREFS)
        assert svc.email_document.call_count == 1
        assert dup["email_sent"] is False
        assert dup["email_deduplicated"] is True
        assert len(self._sent_rows(db_path)) == 1  # no second send / row

    def test_send_failure_removes_pending_and_retry_succeeds(
        self, _dedup_db, _dedup_doc_service
    ):
        _, db_path = _dedup_db
        svc = _dedup_doc_service
        svc.email_document = MagicMock(side_effect=RuntimeError("SMTP down"))
        result = build_email_package(
            [1], "dedup@test.com", company_id=1, prefs=self.SMTP_PREFS,
        )
        assert result["email_sent"] is False
        assert "SMTP down" in result["email_error"]
        assert self._sent_rows(db_path) == []  # claim removed → retry allowed
        # Retry now succeeds and records a single sent row.
        svc.email_document = MagicMock()
        retry = build_email_package(
            [1], "dedup@test.com", company_id=1, prefs=self.SMTP_PREFS,
        )
        assert retry["email_sent"] is True
        rows = self._sent_rows(db_path)
        assert len(rows) == 1
        assert rows[0]["status"] == "sent"


# ── request_id correlation (F5) ─────────────────────────────────────────
# Entry tasks accept an optional ``request_id`` (the HTTP correlation id)
# and log it in the first line so async failures can be traced back to the
# originating request.


class TestTaskRequestId:
    def test_process_document_ocr_logs_request_id(
        self, _mock_db, _mock_doc_service, caplog
    ):
        _mock_doc_service.get_by_id.return_value = None
        with caplog.at_level(logging.INFO):
            process_document_ocr(999, company_id=1, request_id="req-abc-123")
        assert any(
            "request_id=req-abc-123" in r.message for r in caplog.records
        )

    def test_generate_document_pdf_logs_request_id(
        self, _mock_db, _mock_doc_service, caplog
    ):
        _mock_doc_service.get_by_id.return_value = None
        with caplog.at_level(logging.INFO):
            generate_document_pdf(999, 1, "default", request_id="req-pdf-1")
        assert any(
            "request_id=req-pdf-1" in r.message for r in caplog.records
        )

    def test_build_email_package_logs_request_id(
        self, _mock_db, _mock_doc_service, caplog
    ):
        _mock_doc_service.get_by_id.return_value = None
        with caplog.at_level(logging.INFO):
            build_email_package([1], "x@test.com", company_id=1, request_id="req-mail-1")
        assert any(
            "request_id=req-mail-1" in r.message for r in caplog.records
        )

    def test_request_id_optional_and_defaults_to_none(self, _mock_db, _mock_doc_service):
        """Existing positional callers without request_id keep working."""
        _mock_doc_service.get_by_id.return_value = None
        result = process_document_ocr(999, company_id=1)
        assert result["error"] == "Document not found"
