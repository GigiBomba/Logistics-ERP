"""Chaos: disk full during OCR processing (Stage B P5-U3).

Injects ``OSError(errno.ENOSPC)`` — "Insufficient disk space for OCR
processing" (blueprint §8.5.7) — into the real OCR processing seam and
asserts the recovery contract:

* Scenario 1 — the real image-processing stage of the OCR pipeline
  (``ImageProcessor.process``) raises ``OSError(ENOSPC)``.  The document
  row uploaded through the real ``UploadService`` survives intact with
  its original filename/path and zero partial/corrupt OCR columns.
* Scenario 2 — after the disk-full failure, re-running OCR through the
  real seam returns the row to Completed: ``ocr_run_at`` is stamped and
  ``ocr_text`` / ``extracted_data_json`` are persisted (blueprint §7.6.5
  ``Failed → Queued → Completed`` retry).
* Scenario 3 — observability probe: on a disk-full OCR failure the
  pipeline publishes a ``retry.triggered`` telemetry event carrying the
  ``doc_id``, failing ``stage`` (``image_processing`` / ``ocr_extraction``),
  and the error details.  No other failure channel (alert, ``ocr_ran``,
  ``ocr_complete``, etc.) fires — recovery still relies on the row staying
  re-runnable.

Real seam mocked (blueprint §8.5.7 "Disk full during OCR image
processing"): ``services.document_automation.image_processor
.ImageProcessor.process``.  The real ``run_for_existing_document`` wraps
the ENOSPC ``OSError`` in a ``RuntimeError`` (``__cause__`` preserved)
and leaves the document row untouched — the upload is never lost.

Pinned statuses (probed from the real code, §7.6.5): there is no OCR
``status`` column.  Queued / Processing / Failed all persist as a row
with ``ocr_run_at`` empty and ``ocr_text`` empty; Completed is
``ocr_run_at`` set to a timestamp with ``ocr_text`` /
``extracted_data_json`` populated.

All assertions are synchronous — background OCR worker threads are shut
down at the end of every test that starts one.
"""
from __future__ import annotations

import errno
import json
import os
import tempfile
from datetime import datetime
from unittest import mock

import pytest

from models.document_models import DocumentUpload
from services.document_service import DocumentService

pytestmark = pytest.mark.chaos_workflow

# Channels the upload/OCR pipeline could use to report a failed OCR run.
# Per the probed real code, only ``retry.triggered`` is published on a
# disk-full failure; the others must stay silent.
_OCR_FAILURE_EVENT_CHANNELS = (
    "document.automation.ocr_complete",
    "document.automation.processed",
    "document.ocr_ran",
    "ocr.low_confidence",
    "retry.triggered",
    "external_api.failed",
    "alert.created",
)

_IMAGE_PROCESS_SEAM = (
    "services.document_automation.image_processor.ImageProcessor.process"
)
_OCR_EXTRACTOR_SEAM = (
    "services.document_automation.ocr_extractor.OcrExtractor.extract"
)


def _make_source_pdf(marker: str) -> str:
    """Create a small fake PDF on disk; return its path."""
    f = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, mode="w")
    f.write(f"%PDF-1.4 {marker} cmr document")
    f.close()
    return f.name


def _upload(db, source_path: str, title: str) -> tuple[DocumentService, int]:
    """Upload through the real DocumentService; returns (svc, doc_id)."""
    svc = DocumentService(db)
    result = svc.upload_document(
        DocumentUpload(source_path=source_path, title=title, category="cmr"),
        user_id=0,
    )
    assert result.success, f"Upload failed: {result.errors}"
    return svc, result.data.id


def _doc_row(db, doc_id: int) -> dict:
    return dict(
        db.conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
    )


def _shutdown_ocr(doc_svc: DocumentService) -> None:
    """Stop the background OCR worker threads of a DocumentService."""
    if doc_svc is None:
        return
    try:
        doc_svc.ocr.shutdown()
    except Exception:
        pass


def _unlink_quietly(path: str) -> None:
    try:
        if path and os.path.isfile(path):
            os.unlink(path)
    except OSError:
        pass


def _seed_document_row(db, source_path: str, title: str) -> int:
    """Insert a documents row directly (no DocumentService, no workers)."""
    from repositories.document_repository import DocumentRepository

    now = datetime.now().isoformat()
    return DocumentRepository(db).create(
        doc_number="DOC-DISKFULL-001",
        title=title,
        category="cmr",
        entity_type="",
        entity_id=None,
        file_path=source_path,
        file_name=os.path.basename(source_path),
        file_size=os.path.getsize(source_path),
        mime_type="application/pdf",
        file_hash="diskfull-retry-hash",
        tags="[]",
        description="",
        uploaded_by="0",
        uploaded_at=now,
        updated_at=now,
    )


class TestDiskFullDuringOcr:
    """Scenario 1 — disk full inside the OCR pipeline cannot lose the upload.

    The document is uploaded through the real upload path; the OCR
    processing stage then hits ``OSError(ENOSPC)``.  The row keeps its
    original filename/path and none of the OCR result columns are
    partially written.
    """

    def test_disk_full_ocr_failure_preserves_uploaded_row(self, db):
        src = _make_source_pdf("preserve")
        doc_svc = None
        doc_id = None
        try:
            from services.document_automation.pipeline import (
                run_for_existing_document,
            )

            # Patch the real processing seam BEFORE the upload so any
            # background OCR worker also fails harmlessly.
            with mock.patch(
                _IMAGE_PROCESS_SEAM,
                side_effect=OSError(
                    errno.ENOSPC, "No space left on device"
                ),
            ):
                doc_svc, doc_id = _upload(
                    db, src, title="diskfull_preserve.pdf"
                )
                original = _doc_row(db, doc_id)
                # Original upload is on disk, untouched by any OCR work.
                assert os.path.isfile(original["file_path"])

                # Drive the real processing seam: the ENOSPC OSError is
                # wrapped by the real pipeline, cause preserved.
                with pytest.raises(RuntimeError) as excinfo:
                    run_for_existing_document(db, doc_id)
                assert "No space left on device" in str(excinfo.value)
                assert isinstance(excinfo.value.__cause__, OSError)
                assert excinfo.value.__cause__.errno == errno.ENOSPC

            after = _doc_row(db, doc_id)
            # Upload survived — original fields fully intact.
            for col in ("doc_number", "title", "category",
                        "file_name", "file_path"):
                assert after[col] == original[col], (
                    f"column {col} mutated by failed OCR: "
                    f"{original[col]!r} -> {after[col]!r}"
                )
            # No partial/corrupt OCR write on the row.
            assert after["ocr_run_at"] in (None, "")
            assert after["ocr_text"] in (None, "")
            assert after["ocr_engine"] in (None, "")
            assert after["extracted_data_json"] in (None, "", "{}")
            # Physical file still present with identical content.
            assert os.path.isfile(after["file_path"])
            with open(src, "rb") as fh:
                expected_bytes = fh.read()
            with open(after["file_path"], "rb") as fh:
                assert fh.read() == expected_bytes, (
                    "uploaded file corrupted by failed OCR"
                )
        finally:
            _shutdown_ocr(doc_svc)
            if doc_id is not None:
                _unlink_quietly(_doc_row(db, doc_id).get("file_path"))
            _unlink_quietly(src)

    def test_disk_full_leaves_no_partial_ocr_state(self, db):
        """Direct seam contract: a failing pipeline run persists nothing.

        The document is seeded straight into the DB (no workers), then
        the real ``run_for_existing_document`` is executed against a
        disk-full image-processing stage.  It raises, and every OCR
        result column is unchanged afterwards.
        """
        from services.document_automation.pipeline import (
            run_for_existing_document,
        )

        src = _make_source_pdf("nopartial")
        doc_id = None
        try:
            doc_id = _seed_document_row(
                db, src, title="nopartial_cmr.pdf"
            )
            original = _doc_row(db, doc_id)
            assert original["ocr_run_at"] in (None, "")

            with mock.patch(
                _IMAGE_PROCESS_SEAM,
                side_effect=OSError(
                    errno.ENOSPC, "Insufficient disk space for OCR processing"
                ),
            ):
                with pytest.raises(RuntimeError, match="Insufficient disk space"):
                    run_for_existing_document(db, doc_id)

            after = _doc_row(db, doc_id)
            assert after["ocr_run_at"] == original["ocr_run_at"]
            assert after["ocr_text"] in (None, "")
            assert after["extracted_data_json"] in (None, "", "{}")
            assert after["ocr_engine"] in (None, "")
            # The document itself is untouched and re-runnable.
            assert after["file_name"] == original["file_name"]
            assert after["file_path"] == original["file_path"]
            assert os.path.isfile(after["file_path"])
        finally:
            if doc_id is not None:
                _unlink_quietly(_doc_row(db, doc_id).get("file_path"))
            _unlink_quietly(src)


class TestOcrRetryAfterDiskFull:
    """Scenario 2 — the retry path returns the document to Completed.

    After the disk-full failure the row is still awaiting OCR (§7.6.5
    Queued/Failed — ``ocr_run_at`` empty).  Re-running OCR with the
    fault removed drives the real persistence state machine: the row
    completes (``ocr_run_at`` stamped, text + extracted data saved).
    """

    def test_retry_after_disk_full_reaches_completed(self, db):
        from services.document_automation.pipeline import (
            run_for_existing_document,
        )
        from services.document_automation.types import (
            ExtractionResult,
            ProcessingResult,
        )

        src = _make_source_pdf("retry")
        doc_id = None
        try:
            doc_id = _seed_document_row(db, src, title="retry_cmr.pdf")
            assert _doc_row(db, doc_id)["ocr_run_at"] in (None, "")

            # 1) Disk full: the real seam fails, state unchanged.
            with mock.patch(
                _IMAGE_PROCESS_SEAM,
                side_effect=OSError(
                    errno.ENOSPC, "No space left on device"
                ),
            ):
                with pytest.raises(RuntimeError):
                    run_for_existing_document(db, doc_id)
            failed = _doc_row(db, doc_id)
            assert failed["ocr_run_at"] in (None, "")
            assert failed["ocr_text"] in (None, "")
            assert failed["file_name"].endswith(".pdf")

            # 2) Disk freed: re-run OCR through the real seam.  Only the
            #    heavyweight engine seams are stubbed — persistence, the
            #    state transition and the returned result are real.
            retry_engine = "diskfull-test"
            retry_text = "Extracted CMR text DISKFULL-RETRY-001"
            proc_result = ProcessingResult(
                pdf_path=src, pages=1, original_size=(100, 100),
                enhanced=False, method="copy",
            )
            extraction = ExtractionResult(
                full_text=retry_text,
                extracted={"cmr_number": "DISKFULL-RETRY-001"},
                confidence=0.91,
                engine=retry_engine,
                pages_processed=1,
            )
            with mock.patch(_IMAGE_PROCESS_SEAM, return_value=proc_result), \
                    mock.patch(_OCR_EXTRACTOR_SEAM, return_value=extraction):
                result = run_for_existing_document(db, doc_id)

            assert result["engine"] == retry_engine
            assert result["extracted"]["cmr_number"] == "DISKFULL-RETRY-001"

            completed = _doc_row(db, doc_id)
            # Completed state: ocr_run_at stamped, results persisted.
            assert completed["ocr_run_at"] not in (None, "")
            assert completed["ocr_text"] == retry_text
            assert completed["ocr_engine"] == retry_engine
            parsed = json.loads(completed["extracted_data_json"])
            assert parsed["cmr_number"] == "DISKFULL-RETRY-001"
        finally:
            if doc_id is not None:
                _unlink_quietly(_doc_row(db, doc_id).get("file_path"))
            _unlink_quietly(src)


class TestOcrFailureObservability:
    """Scenario 3 — observability probe on an OCR disk-full failure.

    Probed real behavior: the upload emits ``document.uploaded``, and the
    OCR pipeline publishes a ``retry.triggered`` telemetry event when image
    processing hits ``OSError(ENOSPC)`` (in addition to logging at error
    level).  The payload carries the ``doc_id``, the failing ``stage``,
    and the error text/type.  No other failure channel (alert, ``ocr_ran``,
    etc.) fires — the event is the sole dedicated observability signal and
    the row remains re-runnable.
    """

    def test_disk_full_ocr_failure_publishes_retry_event(
        self, db, event_monitor, event_bus
    ):
        src = _make_source_pdf("observe")
        doc_svc = None
        doc_id = None
        try:
            import services.document_automation.pipeline as pipeline_module
            from services.document_automation.pipeline import (
                run_for_existing_document,
            )

            event_monitor.track("document.uploaded", *_OCR_FAILURE_EVENT_CHANNELS)

            # Route the pipeline's shared event bus at the same instance the
            # monitor watches (the autouse singleton reset orphans the
            # module-level reference between tests).
            with mock.patch.object(
                pipeline_module, "shared_event_bus", event_bus
            ), mock.patch(
                _IMAGE_PROCESS_SEAM,
                side_effect=OSError(
                    errno.ENOSPC, "No space left on device"
                ),
            ):
                doc_svc, doc_id = _upload(db, src, title="observe_cmr.pdf")
                with pytest.raises(RuntimeError) as excinfo:
                    run_for_existing_document(db, doc_id)
                assert excinfo.value.__cause__.errno == errno.ENOSPC

            # Upload observability works…
            event_monitor.assert_event_count("document.uploaded", 1)
            # …and the failed OCR run now publishes a retry.triggered
            # telemetry event with the doc_id + stage + error payload.
            retry_events = event_monitor.get_events("retry.triggered")
            assert len(retry_events) >= 1, (
                "expected >= 1 retry.triggered events, found "
                f"{len(retry_events)}"
            )
            payload = retry_events[0]["data"]
            assert payload["doc_id"] == doc_id
            assert payload["stage"] == "image_processing"
            assert "No space left on device" in payload["error"]
            assert payload["error_type"] == "OSError"
            # No other failure channel fires.
            for channel in _OCR_FAILURE_EVENT_CHANNELS:
                if channel == "retry.triggered":
                    continue
                event_monitor.assert_event_not_published(channel)
        finally:
            _shutdown_ocr(doc_svc)
            if doc_id is not None:
                _unlink_quietly(_doc_row(db, doc_id).get("file_path"))
            _unlink_quietly(src)
