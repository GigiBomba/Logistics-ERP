"""OCR service — basic text extraction + full automation pipeline orchestration.

Handles the background OCR worker queue used by Document Center uploads
and the trip-matching auto-link flow that runs after OCR completes.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from datetime import datetime
from typing import Any

from database.db_manager import DatabaseManager
from repositories.document_repository import DocumentRepository

logger = logging.getLogger("document_ocr_service")

MAX_OCR_WORKERS = 2
MAX_PDF_SIZE_FOR_OCR = 50 * 1024 * 1024
MAX_OCR_TEXT_LENGTH = 5000


class OcrService:

    def __init__(self, db: DatabaseManager, repo: DocumentRepository) -> None:
        self.db = db
        self._repo = repo
        self._ocr_queue: queue.Queue = queue.Queue()
        self._ocr_workers: list = []
        self._ocr_running = True
        self._ocr_lock = threading.Lock()
        self._ocr_db = db
        self._start_ocr_workers()

    def _start_ocr_workers(self):
        with self._ocr_lock:
            if self._ocr_workers:
                return
            self._ocr_running = True
            for i in range(MAX_OCR_WORKERS):
                t = threading.Thread(target=self._ocr_worker, daemon=True,
                                     name=f"ocr-worker-{i}")
                t.start()
                self._ocr_workers.append(t)

    def _ocr_worker(self):
        while self._ocr_running:
            try:
                doc_id, file_path, mime_type = self._ocr_queue.get(timeout=2)
            except queue.Empty:
                continue
            try:
                from services.document_automation.pipeline import (
                    run_for_existing_document,
                )
                result = run_for_existing_document(self._ocr_db, doc_id)
                if result and result.get("extracted"):
                    source = os.path.basename(file_path) if file_path else ""
                    self._match_and_link_after_ocr(
                        doc_id, result, source_filename=source,
                    )
            except Exception as e:
                logger.debug(
                    "Full OCR pipeline failed for doc %d: %s — "
                    "falling back to basic OCR", doc_id, e,
                )
                try:
                    text = self.extract_text(file_path, mime_type)
                    if text:
                        self._repo.update(
                            doc_id, text_content=text,
                            updated_at=datetime.now().isoformat(),
                        )
                except Exception as e2:
                    logger.debug(
                        "Basic OCR also failed for doc %d: %s", doc_id, e2,
                    )
            finally:
                try:
                    self._ocr_queue.task_done()
                except Exception:
                    logger.debug("ocr worker: task_done() failed for doc %d", doc_id)

    def shutdown(self):
        self._ocr_running = False
        for t in self._ocr_workers:
            t.join(timeout=3)
        self._ocr_workers.clear()

    def _match_and_link_after_ocr(
        self,
        doc_id: int,
        pipeline_result: dict[str, Any],
        source_filename: str = "",
    ) -> None:
        from services.document_automation.document_grouper import (
            DocumentGrouper,
        )
        from services.document_automation.package_builder import (
            PackageBuilder,
        )
        from services.document_automation.trip_matcher import TripMatcher
        from services.operations.event_bus import (
            DOCUMENT_LINKED,
            EventBus,
        )

        extracted = pipeline_result.get("extracted", {})
        ocr_text = pipeline_result.get("ocr_text", "")

        if not extracted:
            return

        matcher = TripMatcher(self._ocr_db)
        match_result = matcher.match(
            extracted=extracted,
            ocr_text=ocr_text,
            source_filename=source_filename,
        )

        if (not match_result.best_match
                or match_result.confidence < matcher.auto_link_threshold):
            return

        trip_id = match_result.best_match["id"]

        grouper = DocumentGrouper(self._ocr_db)
        success = grouper.link_existing_document_to_trip(
            doc_id=doc_id,
            trip_id=trip_id,
            extracted=extracted,
            ocr_text=ocr_text,
        )

        if success:
            EventBus().publish(DOCUMENT_LINKED, {
                "document_id": doc_id,
                "entity_type": "trip",
                "entity_id": trip_id,
            })

            builder = PackageBuilder(self._ocr_db)
            related = builder.list_trip_documents(trip_id)
            if related:
                logger.info(
                    "Document %d linked to trip %d: "
                    "found %d related document(s)",
                    doc_id, trip_id, len(related),
                )

            self._retroactively_link_related_runs(trip_id, doc_id)

    def _retroactively_link_related_runs(
        self,
        trip_id: int,
        doc_id: int,
    ) -> None:
        from repositories.pipeline_repository import PipelineRepository

        pipeline = PipelineRepository(self._ocr_db)
        runs = pipeline.get_runs_by_trip_id(trip_id)
        if not runs:
            return

        updated = 0
        for run in runs:
            run_id = run["id"]
            try:
                pipeline.append_related_document(run_id, doc_id)
                updated += 1
            except Exception:
                logger.debug(
                    "Failed to update related docs for run %d "
                    "with doc %d",
                    run_id, doc_id,
                )

        if updated:
            logger.info(
                "Retroactively updated %d pipeline run(s) for trip %d "
                "with new document %d",
                updated, trip_id, doc_id,
            )

    # ── Basic OCR (fallback) ─────────────────────────────────────────

    def enqueue_ocr(self, doc_id: int, file_path: str, mime_type: str) -> None:
        if not os.path.isfile(file_path):
            return
        size = os.path.getsize(file_path)
        if size > MAX_PDF_SIZE_FOR_OCR:
            logger.debug("Skipping OCR for large file %s (%d bytes)", file_path, size)
            return
        try:
            self._ocr_queue.put_nowait((doc_id, file_path, mime_type))
        except queue.Full:
            logger.debug("OCR queue full, skipping doc %d", doc_id)

    def extract_text(self, file_path: str, mime_type: str) -> str:
        if not os.path.isfile(file_path):
            return ""
        try:
            if mime_type == "application/pdf":
                return self._extract_pdf_text(file_path)
            elif mime_type.startswith("image/"):
                return self._extract_image_text(file_path)
        except Exception as e:
            logger.debug("OCR extraction skipped for %s: %s", file_path, e)
        return ""

    def _extract_pdf_text(self, file_path: str) -> str:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            parts = []
            for page in reader.pages[:5]:
                txt = page.extract_text()
                if txt:
                    parts.append(txt)
            return "\n".join(parts)[:MAX_OCR_TEXT_LENGTH]
        except Exception:
            return ""

    def _extract_image_text(self, file_path: str) -> str:
        try:
            import pytesseract
            from PIL import Image
            with Image.open(file_path) as img:
                return pytesseract.image_to_string(img)[:MAX_OCR_TEXT_LENGTH]
        except (ImportError, Exception):
            return ""
