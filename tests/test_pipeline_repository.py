"""Tests for repositories.pipeline_repository — CRUD + query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from repositories.pipeline_repository import PipelineRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> PipelineRepository:
    return PipelineRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _run(db: InMemoryDB, **kw: Any) -> int:
    """Insert a pipeline run directly (bypassing sanitization for test setup)."""
    import uuid
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    defaults: Dict[str, Any] = dict(
        run_uuid=uuid.uuid4().hex,
        source_file_path="/tmp/test.pdf",
        source_file_name="test.pdf",
        source_mime_type="application/pdf",
        source_file_size=1024,
        source_file_hash="abc123",
        status="imported",
        stage="import",
        error_message="",
        processed_file_path="",
        processed_pdf_path="",
        pages_count=0,
        ocr_text="",
        extracted_data_json="{}",
        matched_trip_id=None,
        match_confidence=0.0,
        match_signals_json="{}",
        document_id=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    defaults.update(kw)
    cols = ", ".join(defaults.keys())
    vals = ", ".join("?" for _ in defaults)
    db.conn.execute(
        f"INSERT INTO document_pipeline_runs ({cols}) VALUES ({vals})",
        list(defaults.values()),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── append_related_document ──────────────────────────────────────────


class TestAppendRelatedDocument:
    def test_append_related_document_adds_to_empty(self, db, repo):
        run_id = repo.create_run("/tmp/doc.pdf", "doc.pdf", "application/pdf", 500)
        repo.append_related_document(run_id, 42)
        row = repo.get_run_by_id(run_id)
        signals = json.loads(row["match_signals_json"])
        assert signals["related_document_ids"] == [42]

    def test_append_related_document_idempotent(self, db, repo):
        run_id = repo.create_run("/tmp/doc.pdf", "doc.pdf", "application/pdf", 500)
        repo.append_related_document(run_id, 7)
        repo.append_related_document(run_id, 7)
        row = repo.get_run_by_id(run_id)
        signals = json.loads(row["match_signals_json"])
        assert signals["related_document_ids"] == [7]

    def test_append_related_document_appends_to_existing(self, db, repo):
        run_id = repo.create_run("/tmp/doc.pdf", "doc.pdf", "application/pdf", 500)
        repo.append_related_document(run_id, 10)
        repo.append_related_document(run_id, 20)
        row = repo.get_run_by_id(run_id)
        signals = json.loads(row["match_signals_json"])
        assert signals["related_document_ids"] == [10, 20]

    def test_append_related_document_transaction_rollback(self, db, repo):
        """Transaction is rolled back when the UPDATE fails."""
        from unittest.mock import patch
        run_id = repo.create_run("/tmp/doc.pdf", "doc.pdf", "application/pdf", 500)
        repo.append_related_document(run_id, 1)

        # Patch _execute on the repo instance to fail on the UPDATE call
        original_execute = repo._execute

        def failing_execute(query, params=(), commit=True):
            if "match_signals_json" in query:
                raise RuntimeError("simulated failure")
            return original_execute(query, params, commit)

        with patch.object(repo, "_execute", side_effect=failing_execute):
            with pytest.raises(Exception):
                repo.append_related_document(run_id, 99)

        # Verify the first append is still intact (no partial corruption)
        row = repo.get_run_by_id(run_id)
        signals = json.loads(row["match_signals_json"])
        assert signals["related_document_ids"] == [1]  # first append survives


# ── recover_stuck_runs ───────────────────────────────────────────────


class TestRecoverStuckRuns:
    def test_recover_stuck_runs_marks_imported_as_failed(self, db, repo):
        run_id = _run(db, status="imported", stage="import")
        count = repo.recover_stuck_runs()
        assert count > 0
        row = repo.get_run_by_id(run_id)
        assert row["status"] == "failed"
        assert "Recovered from crash" in row["error_message"]

    def test_recover_stuck_runs_skips_completed_and_failed(self, db, repo):
        c_id = _run(db, status="complete", stage="complete")
        f_id = _run(db, status="failed", stage="failed")
        repo.recover_stuck_runs()
        assert repo.get_run_by_id(c_id)["status"] == "complete"
        assert repo.get_run_by_id(f_id)["status"] == "failed"

    def test_recover_stuck_runs_skips_processed(self, db, repo):
        p_id = _run(db, status="processed", stage="verify")
        repo.recover_stuck_runs()
        assert repo.get_run_by_id(p_id)["status"] == "processed"


# ── get_match_signals ────────────────────────────────────────────────


class TestGetMatchSignals:
    def test_get_match_signals_parses_json_and_coerces_float(self, db, repo):
        run_id = _run(
            db,
            match_signals_json=json.dumps({
                "score": "0.95",
                "count": 3,
                "threshold": "0.5",
            }),
        )
        signals = repo.get_match_signals(run_id)
        assert signals["score"] == 0.95
        assert signals["count"] == 3.0
        assert signals["threshold"] == 0.5


# ── create_run ───────────────────────────────────────────────────────


class TestCreateRun:
    def test_create_run_defaults(self, db, repo):
        run_id = repo.create_run(
            source_file_path="/tmp/invoice.pdf",
            source_file_name="invoice.pdf",
            source_mime_type="application/pdf",
            source_file_size=2048,
        )
        row = repo.get_run_by_id(run_id)
        assert row is not None
        assert row["status"] == "imported"
        assert row["stage"] == "import"
        assert row["run_uuid"]  # auto-generated
        assert row["created_at"]
        assert row["updated_at"]

    def test_create_run_sanitizes_inputs(self, db, repo):
        run_id = repo.create_run(
            source_file_path="/tmp/invoice.pdf\x00with_NUL",
            source_file_name="invoice\nfile\rname.pdf",
            source_mime_type="application/pdf",
            source_file_size=2048,
        )
        row = repo.get_run_by_id(run_id)
        assert "\x00" not in row["source_file_path"]
        assert "\n" not in row["source_file_name"]
        assert "\r" not in row["source_file_name"]


# ── update_stage ─────────────────────────────────────────────────────


class TestUpdateStage:
    def test_update_stage_sets_completed_at_for_terminal(self, db, repo):
        run_id = repo.create_run("/tmp/f.pdf", "f.pdf", "application/pdf", 100)
        assert repo.get_run_by_id(run_id)["completed_at"] is None
        repo.update_stage(run_id, stage="complete", status="complete")
        row = repo.get_run_by_id(run_id)
        assert row["completed_at"] is not None


# ── set_match_result ─────────────────────────────────────────────────


class TestSetMatchResult:
    def test_set_match_result_stores_json_signals(self, db, repo):
        run_id = repo.create_run("/tmp/m.pdf", "m.pdf", "application/pdf", 300)
        signals = {"score": 0.98, "confidence": 0.85}
        repo.set_match_result(run_id, matched_trip_id=10, match_confidence=0.98, match_signals=signals)
        row = repo.get_run_by_id(run_id)
        assert row["matched_trip_id"] == 10
        assert row["match_confidence"] == 0.98
        stored = json.loads(row["match_signals_json"])
        assert stored == signals
