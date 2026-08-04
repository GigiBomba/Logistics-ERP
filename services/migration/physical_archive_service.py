"""Orchestrates physical document processing (Tab 2).

Handles the end-to-end pipeline for physical documents: upload, OCR,
classification, trip matching, and confirmation.  Reuses the existing
document automation pipeline heavily.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from database.db_manager import DatabaseManager
from services.document_automation.pipeline import run_for_existing_document
from services.document_automation.trip_matcher import TripMatcher
from services.document_service import DocumentService
from services.migration.types import ArchiveStage, ProgressCallback

logger = logging.getLogger(__name__)

# ── Classification patterns ───────────────────────────────────────────────

TYPE_PATTERNS: dict[str, list[re.Pattern]] = {
    "cmr": [
        re.compile(r"\bcmr\b", re.IGNORECASE),
        re.compile(r"\bcarta\s*verde\b", re.IGNORECASE),
        re.compile(r"\bconsignment\s*note\b", re.IGNORECASE),
        re.compile(r"\bletter\s*of\s*carriage\b", re.IGNORECASE),
    ],
    "invoice": [
        re.compile(r"\binvoice\b", re.IGNORECASE),
        re.compile(r"\bfactura?\b", re.IGNORECASE),
        re.compile(r"\brechnung\b", re.IGNORECASE),
        re.compile(r"\bfacture\b", re.IGNORECASE),
    ],
    "delivery_note": [
        re.compile(r"\bdelivery\s*note\b", re.IGNORECASE),
        re.compile(r"\baviz\s*de\s*expeditie\b", re.IGNORECASE),
        re.compile(r"\blieferschein\b", re.IGNORECASE),
        re.compile(r"\bbon\s*livraison\b", re.IGNORECASE),
        re.compile(r"\bpod\b", re.IGNORECASE),
    ],
    "contract": [
        re.compile(r"\bcontract\b", re.IGNORECASE),
        re.compile(r"\bagreement\b", re.IGNORECASE),
        re.compile(r"\bvertrag\b", re.IGNORECASE),
    ],
}


class PhysicalArchiveService:
    """Orchestrates the physical document processing pipeline.

    Typical flow::

        svc = PhysicalArchiveService(db)
        results = svc.process_batch(["/path/to/doc1.pdf", "/path/to/doc2.jpg"])
        # Review results and confirm
        svc.confirm_document(doc_id=42, corrections={"date": "2026-01-15"}, trip_id=7)
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self._doc_svc: Any = None

    @property
    def doc_svc(self) -> Any:
        """Lazy-initialised DocumentService."""
        if self._doc_svc is None:
            self._doc_svc = DocumentService(self.db)
        return self._doc_svc

    # ── Single document processing ─────────────────────────────────────

    def process_document(self, file_path: str, progress_cb=None) -> dict:
        """Process a single document through the OCR pipeline."""
        results = self.process_batch([file_path], progress_cb)
        return results.get(os.path.basename(file_path), {"status": "error", "error": "Unknown"})

    # ── Batch processing ───────────────────────────────────────────────

    def process_batch(
        self,
        file_paths: list[str],
        progress_cb: ProgressCallback = None,
    ) -> dict[str, Any]:
        """Process a batch of physical document files through the full pipeline.

        For each file:
        1. Upload via DocumentService
        2. Run OCR pipeline
        3. Classify document type
        4. Check confidence; flag for confirmation if < 0.75
        5. Attempt trip matching for CMR / invoice docs

        Returns:
            A dict mapping each file path to its processing result::

                {
                    "path/to/doc.pdf": {
                        "doc_id": 42,
                        "doc_type": "cmr",
                        "confidence": 0.82,
                        "needs_confirmation": False,
                        "extracted": {...},
                        "match_result": {...} | None,
                        "error": None,
                    },
                    ...
                }
        """
        results: dict[str, Any] = {}

        for idx, file_path in enumerate(file_paths):
            file_result: dict[str, Any] = {
                "doc_id": None,
                "doc_type": "unknown",
                "confidence": 0.0,
                "needs_confirmation": True,
                "extracted": {},
                "match_result": None,
                "error": None,
            }

            try:
                if not os.path.isfile(file_path):
                    raise FileNotFoundError(f"File not found: {file_path}")

                filename = os.path.basename(file_path)

                if progress_cb:
                    pct = int((idx + 1) / len(file_paths) * 25) if file_paths else 0
                    progress_cb(
                        ArchiveStage.UPLOADING.value,
                        pct,
                        f"Uploading {filename}...",
                    )

                # ── Step 1: Upload ────────────────────────────────────
                from models.document_models import DocumentUpload
                upload_result = self.doc_svc.upload_document(
                    DocumentUpload(
                        source_path=file_path,
                        title=os.path.splitext(filename)[0],
                        category="migration",
                    ),
                    user_id=0,
                )
                if not upload_result.success:
                    raise RuntimeError(f"DocumentService.upload_document failed for {file_path}")
                doc_id = upload_result.data.id
                file_result["doc_id"] = doc_id

                if progress_cb:
                    pct = int((idx + 1) / len(file_paths) * 50) if file_paths else 0
                    progress_cb(
                        ArchiveStage.IMAGE_PROCESSING.value,
                        pct,
                        f"Processing {filename} (doc #{doc_id})...",
                    )

                # ── Step 2: Run OCR pipeline ──────────────────────────
                try:
                    pipeline_result = run_for_existing_document(
                        self.db,
                        doc_id,
                        progress_callback=lambda stage, pct: None,
                    )
                    file_result["extracted"] = pipeline_result.get("extracted", {})
                    file_result["confidence"] = pipeline_result.get("confidence", 0.0)
                except Exception as exc:
                    logger.exception("OCR pipeline failed for doc %d", doc_id)
                    file_result["error"] = f"OCR failed: {exc}"
                    results[file_path] = file_result
                    continue

                if progress_cb:
                    pct = int((idx + 1) / len(file_paths) * 75) if file_paths else 0
                    progress_cb(
                        ArchiveStage.CLASSIFYING.value,
                        pct,
                        f"Classifying {filename}...",
                    )

                # ── Step 3: Classify document type ────────────────────
                doc_type = self._classify(pipeline_result)
                file_result["doc_type"] = doc_type

                # ── Step 4: Confidence check ──────────────────────────
                confidence = pipeline_result.get("confidence", 0.0)
                file_result["needs_confirmation"] = confidence < 0.75

                if progress_cb:
                    pct = int((idx + 1) / len(file_paths) * 90) if file_paths else 0
                    progress_cb(
                        ArchiveStage.MATCHING.value,
                        pct,
                        f"Matching {filename} ({doc_type}, conf={confidence:.2f})...",
                    )

                # ── Step 5: Trip matching (CMR / invoice only) ────────
                if doc_type in ("cmr", "invoice"):
                    try:
                        matcher = TripMatcher(self.db)
                        match_result = matcher.match(
                            extracted=pipeline_result.get("extracted", {}),
                            ocr_text=pipeline_result.get("ocr_text", ""),
                            source_filename=filename,
                        )
                        file_result["match_result"] = {
                            "confidence": match_result.confidence,
                            "best_match": match_result.best_match,
                            "candidates": [
                                {
                                    "trip_id": c.trip.get("id"),
                                    "confidence": c.confidence,
                                }
                                for c in match_result.candidates
                            ],
                        }
                    except Exception as exc:
                        logger.debug("Trip matching failed for doc %d: %s", doc_id, exc)
                        file_result["match_result"] = {"error": str(exc)}

                if progress_cb:
                    pct = int((idx + 1) / len(file_paths) * 100) if file_paths else 0
                    stage = (
                        ArchiveStage.AWAITING_CONFIRMATION.value
                        if file_result["needs_confirmation"]
                        else ArchiveStage.COMPLETE.value
                    )
                    progress_cb(stage, pct, f"Processed {filename}")

            except Exception as exc:
                logger.exception("Failed to process file: %s", file_path)
                file_result["error"] = str(exc)

            results[file_path] = file_result

        return results

    # ── Document confirmation ──────────────────────────────────────────

    def confirm_document(
        self,
        doc_id: int,
        corrections: dict[str, Any] | None = None,
        trip_id: int | None = None,
    ) -> bool:
        """Apply user corrections and optionally link to a trip.

        Args:
            doc_id: The document ID to update.
            corrections: User-provided field corrections (``{field: value}``).
            trip_id: Optional trip ID to link the document to.

        Returns:
            ``True`` if the update succeeded.
        """
        try:
            import json

            from repositories.document_repository import DocumentRepository

            repo = DocumentRepository(self.db)
            doc = repo.get_by_id(doc_id)
            if not doc:
                logger.warning("confirm_document: document %d not found", doc_id)
                return False

            # Merge corrections into extracted data
            existing_raw = doc.get("extracted_data_json", "{}")
            try:
                existing = json.loads(existing_raw) if existing_raw else {}
            except (json.JSONDecodeError, TypeError):
                existing = {}

            if corrections:
                existing.update(corrections)

            repo.update(
                doc_id,
                extracted_data_json=json.dumps(existing, ensure_ascii=False, default=str),
            )

            # Link to trip if provided
            if trip_id is not None:
                self.doc_svc.link_document(
                    doc_id=doc_id,
                    entity_type="trip",
                    entity_id=trip_id,
                    relation_type="attached",
                )

            logger.info("Document %d confirmed with corrections: %s", doc_id, corrections)
            return True

        except Exception as exc:
            logger.exception("Failed to confirm document %d: %s", doc_id, exc)
            return False

    # ── Classification ─────────────────────────────────────────────────

    @staticmethod
    def _classify(pipeline_result: dict[str, Any]) -> str:
        """Determine the document type from OCR extraction results.

        Priority order:
        1. Extracted fields (cmr_number, invoice_number, etc.)
        2. Pattern matching against OCR text
        3. Default: "unknown"
        """
        extracted = pipeline_result.get("extracted", {}) or {}

        # ── Check extracted fields first ───────────────────────────────
        if extracted.get("cmr_number"):
            return "cmr"
        if extracted.get("invoice_number"):
            return "invoice"
        if extracted.get("doc_type"):
            return extracted["doc_type"].lower()

        # ── Fallback: pattern matching on OCR text ────────────────────
        ocr_text = pipeline_result.get("ocr_text", "") or ""

        # Score each type by pattern hits
        scores: dict[str, int] = {}
        for doc_type, patterns in TYPE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = pattern.findall(ocr_text)
                score += len(matches)
            if score > 0:
                scores[doc_type] = score

        if scores:
            best: str = max(scores, key=lambda k: scores[k])  # type: ignore[arg-type]
            logger.debug("Classified as '%s' via text patterns (scores: %s)", best, scores)
            return best

        return "unknown"
