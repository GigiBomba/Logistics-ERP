"""QThread worker that runs a single document through the pipeline.

Emits Qt signals at each stage so the UI can update its card live
without polling the database.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import threading
import traceback
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from services.document_automation import (
    DocumentGrouper,
    ImageProcessor,
    OcrExtractor,
    PipelineStage,
    TripMatcher,
)
from services.i18n import t
from services.invoicing.config_manager import load_company_config

logger = logging.getLogger("document_automation.worker")


# A negative run_id is emitted on errors that occur before the DB
# row is created (so the UI can still react to the finished signal).
PIPELINE_ERROR_RUN_ID = -1


def _automation_output_dir(run_id: int) -> str:
    """Return a path for this run's processed files anchored to the
    writable data directory next to the executable (or project root
    during development)."""
    from utils.resource_path import data_path
    return data_path(f"data/documents/automation/run_{run_id}")


def _file_hash(path: str) -> str:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def link_document_to_trip(db, run_id: int, trip_id: int) -> int | None:
    """Manually link a pipeline run's processed document to *trip_id*.

    Standalone function (no Qt dependency) — safe to call after the
    worker thread has finished and its C++ object has been deleted.
    Returns the new (or existing) document id, or ``None`` on failure.

    Delegates document creation + linking to :class:`DocumentGrouper`
    (for the rich OCR-metadata / trip-update logic) and pipeline state
    updates to the pipeline service in ``services.document_automation``.
    """
    # ── Use the pipeline service instead of PipelineRepository directly ──
    from services.document_automation import DocumentGrouper
    from services.document_automation.pipeline import (
        get_run, set_match_result, set_related_documents, update_stage,
    )
    from services.document_automation.types import PipelineStage
    from services.document_service import DocumentService

    run = get_run(db, run_id)
    if not run:
        logger.error("link_document_to_trip: run %s not found", run_id)
        return None
    logger.info("link_document_to_trip: run %s -> trip %s", run_id, trip_id)

    ocr_text = run.get("ocr_text") or ""
    doc_svc = DocumentService(db)

    # ── Create the document and link it to the trip ──────────────────
    # DocumentGrouper.group_and_link handles: document registration
    # (via UploadService), title / tag building, CMR metadata persistence,
    # extraction update, trip metadata (documents_attached, cmr_number),
    # and runs everything inside a single DB transaction.
    grouper = DocumentGrouper(db)
    try:
        doc_id = grouper.group_and_link(run_id, trip_id, ocr_text=ocr_text)
    except Exception:
        logger.exception("link_document_to_trip: group_and_link failed")
        return None

    if doc_id:
        # ── Verify through DocumentService.link_to_entity() (typed) ──
        # This returns a DocumentUploadResult (ServiceResult[DocumentResult])
        # and fires the DOCUMENT_LINKED event.  If the link already
        # exists the INSERT OR IGNORE is a no-op, so the call is safe.
        # link_to_entity() is the typed method returning DocumentUploadResult.
        try:
            result = doc_svc.link_to_entity(doc_id, "trip", trip_id)
            if not result.success:
                logger.warning(
                    "link_document_to_trip: link_to_entity verification "
                    "returned failure for doc %s — continuing anyway",
                    doc_id,
                )
        except Exception:
            logger.exception(
                "link_document_to_trip: link_to_entity failed for doc %s",
                doc_id,
            )

        # ── Persist match result and mark the run complete ───────────
        try:
            set_match_result(
                db, run_id, trip_id, 0.0, {"manual_selection": 1.0},
            )
            update_stage(db, run_id, PipelineStage.COMPLETE.value, "complete")
        except Exception:
            logger.exception(
                "link_document_to_trip: failed to persist match result",
            )

        # ── Discover related documents via DocumentService ───────────
        # (replaces the previous PackageBuilder + raw pipeline call)
        try:
            related = doc_svc.get_documents_for_entity("trip", trip_id)
            if related:
                set_related_documents(
                    db, run_id, [d["id"] for d in related],
                )
        except Exception:
            logger.exception(
                "link_document_to_trip: related docs discovery failed",
            )

    return doc_id


def register_standalone_document(db, run_id: int) -> int | None:
    """Register the processed PDF from a pipeline run as a standalone
    document (no trip association).

    Used by Simple mode when the user chooses not to link the document
    to any trip.  Returns the new document id, or ``None`` on failure.

    Delegates document creation to :class:`DocumentService` (with a
    :class:`DocumentUpload` model) and pipeline state updates to the
    pipeline service in ``services.document_automation``.
    """
    # ── Pipeline service instead of PipelineRepository directly ──────
    from services.document_automation.pipeline import (
        get_run, set_document_id, update_stage,
    )
    from services.document_automation.types import PipelineStage
    from services.document_service import DocumentService
    from models.document_models import DocumentUpload

    run = get_run(db, run_id)
    if not run:
        logger.error("register_standalone_document: run %s not found", run_id)
        return None
    pdf_path = run.get("processed_pdf_path") or run.get("processed_file_path") or ""
    if not pdf_path or not os.path.isfile(pdf_path):
        logger.error(
            "register_standalone_document: processed PDF missing for run %s",
            run_id,
        )
        return None

    # Use the original file name as the document title
    source_name = run.get("source_file_name") or f"run_{run_id}"
    title = os.path.splitext(source_name)[0]

    # ── Build a typed DocumentUpload model ───────────────────────────
    upload_request = DocumentUpload(
        source_path=pdf_path,
        title=title,
        category="documents",
        entity_type="document",
        entity_id=None,
        description="",
        tags=["automation", "standalone"],
    )

    # ── Upload via DocumentService (legacy path to bypass UI perms) ──
    # We use upload_legacy() (the implementation behind the deprecated
    # DocumentService.upload()) because this is a background automation
    # call that must not be blocked by UI permission checks.  The typed
    # DocumentUpload model provides compile-time safety for the fields.
    doc_svc = DocumentService(db)
    try:
        doc_id = doc_svc.upload_legacy(
            source_path=upload_request.source_path,
            title=upload_request.title,
            category=upload_request.category,
            entity_type=upload_request.entity_type,
            entity_id=upload_request.entity_id,
            description=upload_request.description,
            tags=upload_request.tags,
            uploaded_by="automation",
        )
    except Exception:
        logger.exception(
            "register_standalone_document: document creation failed for run %d",
            run_id,
        )
        return None

    if doc_id:
        # ── Finalise pipeline run via pipeline service ───────────────
        try:
            set_document_id(db, run_id, doc_id)
            update_stage(db, run_id, PipelineStage.COMPLETE.value, "complete")
        except Exception:
            logger.exception(
                "register_standalone_document: failed to finalize run %d",
                run_id,
            )
    logger.info(
        "Standalone document #%d registered for run %d", doc_id, run_id
    )
    return doc_id


class PipelineWorker(QThread):
    """One worker per imported file (or per multi-file batch).

    Parameters
    ----------
    mode : str
        ``"advanced"`` (default) — full pipeline with OCR, trip matching,
        and grouping.  ``"simple"`` — crop/transform to PDF only, then
        emit ``processing_done`` and finish so the UI can ask the user
        whether to associate the document with a trip.
    """

    stage_changed = Signal(int, str, str)              # run_id, stage, status
    worker_ready = Signal(int)                          # run_id — emitted once DB row is created
    ocr_extracted = Signal(int, dict, str)             # run_id, extracted, ocr_text
    match_ready = Signal(int, object, float, object)    # run_id, best_match, conf, candidates_serializable
    manual_needed = Signal(int, object)                 # run_id, candidates_serializable
    processing_done = Signal(int, str)                  # run_id, processed_pdf_path — simple mode only
    finished = Signal(int, object, object)              # run_id, document_id_or_None, error_or_None
    log = Signal(int, str)                              # run_id, message

    def __init__(
        self,
        db,
        input_paths: list[str],
        prefs=None,
        mode: str = "advanced",
        parent: QObject | None = None,
        pipeline_repo=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.input_paths = list(input_paths)
        self.prefs = prefs
        self._mode = mode
        # ── Pipeline repository via the document automation service ──
        # (instead of importing PipelineRepository directly)
        from services.document_automation.pipeline import get_pipeline_repo
        self._pipeline_repo = (
            pipeline_repo
            if pipeline_repo is not None
            else get_pipeline_repo(db)
        )
        # ── Initialise AI Vision + PaddleOCR through the service ─────
        from services.document_automation.pipeline import init_pipeline
        init_pipeline(self.db, prefs=prefs)
        self._run_id: int | None = None
        self._matched_trip_id: int | None = None
        self._overridden_trip_id: int | None = None
        self._overridden_signals: dict[str, float] = {}
        self._stop_event = threading.Event()

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    def override_match(self, trip_id: int, signals: dict[str, float]) -> None:
        """Called by the UI when the user manually picks a trip."""
        self._overridden_trip_id = trip_id
        self._overridden_signals = dict(signals or {})

    @property
    def run_id(self) -> int | None:
        return self._run_id

    def _emit_stage(self, stage: str, status: str) -> None:
        if self._run_id is not None:
            self.stage_changed.emit(self._run_id, stage, status)

    def _emit_log(self, message: str) -> None:
        if self._run_id is not None:
            self.log.emit(self._run_id, message)

    def run(self) -> None:
        pipeline = self._pipeline_repo
        if not self.input_paths:
            self.finished.emit(PIPELINE_ERROR_RUN_ID, None, "No input files provided")
            return
        # ── 1. Import ────────────────────────────────────────────────
        first = self.input_paths[0]
        try:
            size = os.path.getsize(first)
        except OSError as exc:
            self.finished.emit(PIPELINE_ERROR_RUN_ID, None, t("automation.err_read_input", default="Cannot read input: {}").format(exc))
            return
        mime = "image/jpeg"  # best guess; refined per file in the processor
        ext = os.path.splitext(first)[1].lower()
        if ext == ".pdf":
            mime = "application/pdf"
        elif ext in {".png"}:
            mime = "image/png"
        elif ext in {".tiff", ".tif"}:
            mime = "image/tiff"
        elif ext in {".bmp"}:
            mime = "image/bmp"
        elif ext in {".webp"}:
            mime = "image/webp"

        try:
            run_id = pipeline.create_run(
                source_file_path=first,
                source_file_name=os.path.basename(first),
                source_mime_type=mime,
                source_file_size=size,
                source_file_hash=_file_hash(first),
            )
        except Exception as exc:
            self.finished.emit(PIPELINE_ERROR_RUN_ID, None, t("automation.err_database", default="Database error: {}").format(exc))
            return
        self._run_id = run_id
        self.worker_ready.emit(run_id)
        if self.isInterruptionRequested():
            self.finished.emit(run_id, None, t("automation.cancelled", default="Cancelled"))
            return

        # Persist the import stage explicitly so the DB matches the signal.
        try:
            pipeline.update_stage(
                run_id, PipelineStage.IMPORT.value, "imported",
            )
        except Exception:
            logger.exception("Failed to persist import stage")
        self._emit_stage(PipelineStage.IMPORT.value, "imported")
        self._emit_log(t("automation.imported", default="Imported {} ({} bytes)").format(os.path.basename(first), size))

        # ── 2. Image processing ──────────────────────────────────────
        output_dir = _automation_output_dir(run_id)
        try:
            processor = ImageProcessor()
            job_id = f"run_{run_id}"
            result = processor.process(self.input_paths, output_dir, job_id=job_id)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.exception("ImageProcessor failed")
            try:
                pipeline.update_stage(
                    run_id, PipelineStage.PROCESSING.value, "failed",
                    error_message=str(exc),
                )
            except Exception:
                logger.exception("Failed to persist processing failure for run %d", run_id)
            self.finished.emit(run_id, None, t("automation.err_processing", default="Processing failed: {}").format(f"{exc}\n{tb[:500]}"))
            return
        if self.isInterruptionRequested():
            self.finished.emit(run_id, None, t("automation.cancelled", default="Cancelled"))
            return

        try:
            pipeline.set_processed_files(
                run_id,
                processed_file_path=result.pdf_path,
                processed_pdf_path=result.pdf_path,
                pages_count=result.pages,
            )
            pipeline.update_stage(
                run_id, PipelineStage.PROCESSING.value, "processing",
            )
        except Exception:
            logger.exception("Failed to persist processed files")
        self._emit_stage(PipelineStage.PROCESSING.value, "processing")
        self._emit_log(
            t("automation.processing_complete", default="Enhanced → {} ({} pages, {} images)").format(result.method, result.pages, len(result.enhanced_image_paths))
        )

        # ── 2b. Simple mode — skip OCR, matching, grouping ──────────
        if self._mode == "simple":
            try:
                pipeline.update_stage(
                    run_id, PipelineStage.PROCESSING.value, "processed",
                )
            except Exception:
                logger.exception(
                    "Failed to persist processed status for run %d", run_id
                )
            self._emit_stage(PipelineStage.PROCESSING.value, "processed")
            self.processing_done.emit(run_id, result.pdf_path)
            self._emit_log(
                t("automation.simple_done", default="Simple mode: processing complete, awaiting user action")
            )
            self.finished.emit(run_id, None, None)
            return

        # ── 3. OCR ───────────────────────────────────────────────────
        if self.isInterruptionRequested():
            self.finished.emit(run_id, None, t("automation.cancelled", default="Cancelled"))
            return
        try:
            ocr = OcrExtractor(db=self.db)
            user_company = (load_company_config().get("company_name") or "").strip()
            extraction = ocr.extract(result.pdf_path, stop_event=self._stop_event, user_company=user_company)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.exception("OcrExtractor failed")
            try:
                pipeline.update_stage(
                    run_id, PipelineStage.OCR.value, "failed",
                    error_message=str(exc),
                )
            except Exception:
                logger.exception("Failed to persist OCR failure for run %d", run_id)
            self.finished.emit(run_id, None, t("automation.err_ocr", default="OCR failed: {}").format(f"{exc}\n{tb[:500]}"))
            return
        try:
            pipeline.set_ocr_result(
                run_id, extraction.full_text, extraction.extracted,
            )
            pipeline.update_stage(
                run_id, PipelineStage.OCR.value, "ocr_done",
            )
        except Exception:
            logger.exception("Failed to persist OCR result — aborting pipeline")
            try:
                pipeline.update_stage(
                    run_id, PipelineStage.OCR.value, "failed",
                    error_message=t("automation.err_ocr_persist", default="OCR persistence failed"),
                )
            except Exception:
                logger.exception("Failed to persist OCR failure for run %d", run_id)
            self.finished.emit(run_id, None, t("automation.err_ocr_persist", default="OCR persistence failed"))
            return
        self._emit_stage(PipelineStage.OCR.value, "ocr_done")
        self.ocr_extracted.emit(run_id, extraction.extracted, extraction.full_text)
        self._emit_log(
            t("automation.ocr_complete", default="OCR complete: {} chars, confidence={}%, engine={}").format(
                len(extraction.full_text), extraction.confidence, extraction.engine
            )
        )

        # ── 4. Trip matching ─────────────────────────────────────────
        try:
            matcher = TripMatcher(self.db)
            match_result = matcher.match(
                extraction.extracted,
                ocr_text=extraction.full_text,
                source_filename=os.path.basename(first),
            )
        except Exception as exc:
            tb = traceback.format_exc()
            logger.exception("TripMatcher failed")
            try:
                pipeline.update_stage(
                    run_id, PipelineStage.MATCHING.value, "failed",
                    error_message=str(exc),
                )
            except Exception:
                logger.exception("Failed to persist matching failure for run %d", run_id)
            self.finished.emit(run_id, None, t("automation.err_matching", default="Matching failed: {}").format(f"{exc}\n{tb[:500]}"))
            return
        # Build a JSON-serialisable list of candidate dicts.
        serialisable_candidates = [
            {
                "trip": c.trip,
                "confidence": c.confidence,
                "signals": c.signals,
            }
            for c in match_result.candidates
        ]
        # If the user already overrode the match, use that.
        best_trip: dict[str, Any] | None = None
        confidence: float = 0.0
        if self._overridden_trip_id is not None:
            chosen_id = int(self._overridden_trip_id)
            chosen_signals = dict(self._overridden_signals)
            if chosen_id:
                try:
                    best_trip = matcher.trips.get_by_id(chosen_id)
                except Exception:
                    logger.exception("Failed to fetch overridden trip %d from DB", chosen_id)
                    best_trip = None
            confidence = 1.0
            self._matched_trip_id = chosen_id
            try:
                pipeline.set_match_result(
                    run_id, chosen_id, confidence, chosen_signals,
                )
                pipeline.update_stage(
                    run_id, PipelineStage.MATCHING.value, "matched",
                )
            except Exception:
                logger.exception("Failed to persist override match result")
        else:
            best_id = (match_result.best_match or {}).get("id")
            best_trip = match_result.best_match
            confidence = match_result.confidence
            self._matched_trip_id = best_id
            try:
                pipeline.set_match_result(
                    run_id,
                    best_id,
                    match_result.confidence,
                    match_result.signals,
                )
                pipeline.update_stage(
                    run_id, PipelineStage.MATCHING.value, "matched",
                )
            except Exception:
                logger.exception("Failed to persist match result — aborting pipeline")
                try:
                    pipeline.update_stage(
                        run_id, PipelineStage.MATCHING.value, "failed",
                        error_message=t("automation.err_match_persist", default="Match persistence failed"),
                    )
                except Exception:
                    logger.exception("Failed to persist match failure for run %d", run_id)
                self.finished.emit(run_id, None, t("automation.err_match_persist", default="Match persistence failed"))
                return
        self.match_ready.emit(run_id, best_trip, confidence, serialisable_candidates)
        self._emit_stage(PipelineStage.MATCHING.value, "matched")
        self._emit_log(
            t("automation.match_found", default="Match: trip #{} confidence={}% ({} candidates)").format(
                self._matched_trip_id, int(confidence * 100), len(serialisable_candidates)
            )
        )

        # ── 5. Grouping / Manual selection ─────────────────────────
        if not self._matched_trip_id:
            if serialisable_candidates:
                # Candidates exist but none auto-matched — let the user pick.
                try:
                    pipeline.update_stage(
                        run_id, PipelineStage.MATCHING.value, "matched",
                    )
                except Exception:
                    logger.exception("Failed to persist manual-needed state for run %d", run_id)
                self.manual_needed.emit(run_id, serialisable_candidates)
                self._emit_stage(PipelineStage.MATCHING.value, "matched")
                self._emit_log(
                    t("automation.match_manual", default="Match required manual selection ({} candidates)").format(len(serialisable_candidates))
                )
                # Emit finished so the worker is cleaned up from _workers
                # and deleteLater is called.  The run stays in "matching"
                # stage — the UI shows manual selection links.
                self.finished.emit(run_id, None, None)
                return
            try:
                pipeline.update_stage(
                    run_id, PipelineStage.GROUPING.value, "complete",
                    error_message=t("automation.no_match", default="No trip match \u2014 run finished without attachment"),
                )
            except Exception:
                logger.exception("Failed to persist no-match completion for run %d", run_id)
            self.finished.emit(run_id, None, None)
            return
        try:
            grouper = DocumentGrouper(self.db)
            doc_id = grouper.group_and_link(
                run_id, int(self._matched_trip_id), ocr_text=extraction.full_text,
            )
        except Exception as exc:
            logger.exception("DocumentGrouper failed")
            with contextlib.suppress(Exception):
                pipeline.update_stage(
                    run_id, PipelineStage.GROUPING.value, "failed",
                    error_message=str(exc),
                )
            self.finished.emit(run_id, None, t("automation.err_grouping", default="Grouping failed: {}").format(exc))
            return
        if not doc_id:
            try:
                pipeline.update_stage(
                    run_id, PipelineStage.GROUPING.value, "failed",
                    error_message=t("automation.err_grouping_no_doc", default="Grouping produced no document"),
                )
            except Exception:
                logger.exception("Failed to persist grouping failure for run %d", run_id)
            self.finished.emit(run_id, None, t("automation.err_grouping_no_doc", default="Grouping produced no document"))
            return
        # Discover related documents already linked to this trip.
        try:
            from services.document_automation.package_builder import PackageBuilder
            builder = PackageBuilder(self.db)
            related = builder.list_trip_documents(self._matched_trip_id)
            if related:
                pipeline.set_related_documents(run_id, [d["id"] for d in related])
        except Exception:
            logger.warning("Failed to discover related documents for trip %s",
                           self._matched_trip_id, exc_info=True)

        try:
            pipeline.update_stage(
                run_id, PipelineStage.COMPLETE.value, "complete",
            )
        except Exception:
            logger.exception("Failed to mark run complete")
        self.finished.emit(run_id, int(doc_id), None)
        self._emit_log(t("automation.linked_doc", default="Linked document #{} to trip #{}").format(doc_id, self._matched_trip_id))
