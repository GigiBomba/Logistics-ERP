"""Synchronous orchestrator for the document-automation pipeline.

The :class:`PipelineWorker` in ``ui/views/automation_worker.py`` runs
the pipeline on a background ``QThread`` and is wired to the
Automation tab's UI.  This module is the equivalent entry point
for batch / one-shot callers (e.g. ``Re-run OCR`` from the Document
Center) that don't need a Qt worker thread.

Public surface:
    - :func:`run_for_existing_document` — run image enhancement,
      OCR, and field extraction on an existing ``documents`` row
      and persist the results back to the row.

Validation:
    - :func:`validate_document_before_ocr` — pre-OCR document checks.
    - :func:`validate_extraction` — post-OCR field validation.
    - :func:`validate_match` — trip match confidence checks.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
from datetime import datetime
from typing import Any, Callable, Optional

from models.common import ErrorDetail, ServiceResult
from models.ocr_models import MatchedTrip, OcrResult
from repositories.settings_repository import SettingsRepository

from .field_extractors import validate_extracted_fields
from .types import FieldValidationResult, ValidationResult

logger = logging.getLogger("document_automation.pipeline")

ProgressCallback = Optional[Callable[[str, int], None]]


def run_for_existing_document(
    db: Any,
    doc_id: int,
    *,
    progress_callback: ProgressCallback = None,
    stop_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Run image enhancement + OCR + field extraction on an existing
    ``documents`` row.

    Persists ``ocr_text``, ``extracted_data_json``, ``ocr_run_at``,
    and ``ocr_engine`` back onto the row.

    Returns a dict with the persisted fields so callers can show a
    "OCR complete" badge without re-querying the DB.

    ``progress_callback`` is an optional callable accepting a
    ``(stage_label, percent)`` tuple; used by the QThread-based
    worker to emit ``stage_changed`` signals.
    """
    from repositories.document_repository import DocumentRepository

    from .image_processor import ImageProcessor, ProcessingError
    from .ocr_extractor import (
        OcrExtractor,
        set_paddle_config,
        set_paddle_gpu,
    )
    try:
        from .ai_fallback import init_from_db as ai_init
        ai_init(db)
    except (ImportError, ValueError, OSError):
        logger.debug("AI fallback init failed — continuing without it")

    # Read PaddleOCR settings from the DB if not already configured
    # by the caller (e.g. ReRunOcrWorker).
    try:
        overrides = SettingsRepository(db).get_settings_by_keys(
            ["ocr_use_gpu", "ocr_det_limit_side_len", "ocr_rec_batch_num"]
        )
        gpu_val = overrides.get("ocr_use_gpu", "0")
        set_paddle_gpu(gpu_val in ("1", "true", "yes"))
        det_len = int(overrides.get("ocr_det_limit_side_len", "960"))
        rec_batch = int(overrides.get("ocr_rec_batch_num", "6"))
        set_paddle_config(det_limit_side_len=det_len, rec_batch_num=rec_batch)
    except (ValueError, TypeError, OSError):
        logger.debug("Failed to apply PaddleOCR settings from DB — using defaults")

    doc = DocumentRepository(db).get_by_id(doc_id)
    if not doc:
        raise ValueError(f"Document {doc_id} not found")
    file_path = doc.get("file_path")
    if not file_path or not os.path.isfile(file_path):
        raise FileNotFoundError(f"File missing: {file_path}")

    if progress_callback:
        progress_callback("processing", 10)

    job_id = f"doc_{doc_id}"
    temp_output_dir = _temp_dir(job_id)
    try:
        processor = ImageProcessor()
        result = processor.process(
            [file_path],
            output_dir=temp_output_dir,
            job_id=job_id,
        )
    except ProcessingError:
        logger.exception("ImageProcessor failed for document %d", doc_id)
        raise
    except (ValueError, TypeError, OSError, RuntimeError) as exc:
        logger.exception("Unexpected error in image processing for document %d", doc_id)
        raise RuntimeError(f"Image processing failed: {exc}") from exc

    if progress_callback:
        progress_callback("ocr", 50)

    ocr = OcrExtractor(db=db)
    extraction = ocr.extract(result.pdf_path, stop_event=stop_event)

    # Clean up temp dir after OCR has read the processed file.
    try:
        if os.path.isdir(temp_output_dir):
            shutil.rmtree(temp_output_dir, ignore_errors=True)
    except (OSError, PermissionError):
        logger.debug("Failed to clean up temp dir: %s", temp_output_dir)

    if progress_callback:
        progress_callback("persisting", 80)

    extracted_fields = extraction.extracted or {}

    # ── Cross-reference extracted company names against client DB ──
    from repositories.client_repository import ClientRepository

    from .field_extractors import match_clients_from_extracted
    matched_clients: list[str] = []
    try:
        client_repo = ClientRepository(db)
        matched_clients = match_clients_from_extracted(extracted_fields, client_repo)
    except (ValueError, KeyError, TypeError) as exc:
        logger.debug("Client cross-reference failed for doc %d: %s", doc_id, exc)

    # ── Persist OCR results to the documents row ──
    try:
        DocumentRepository(db).update(
            doc_id,
            ocr_text=extraction.full_text or "",
            extracted_data_json=json.dumps(extracted_fields, ensure_ascii=False, default=str),
            ocr_run_at=datetime.now().isoformat(timespec="seconds"),
            ocr_engine=extraction.engine or "",
        )
    except (ValueError, TypeError, OSError, RuntimeError) as exc:
        logger.exception("Failed to persist OCR result to document %d", doc_id)
        if progress_callback:
            progress_callback("persisting", 100)
        raise RuntimeError(f"OCR persistence failed: {exc}") from exc

    if progress_callback:
        progress_callback("rename", 90)

    # ── Rename document to DOCID-CLIENT-DATE.pdf ──
    try:
        _rename_document_after_ocr(db, doc_id, extracted_fields, matched_clients)
    except (OSError, ValueError, RuntimeError) as exc:
        logger.warning("Document rename failed for doc %d: %s", doc_id, exc)

    if progress_callback:
        progress_callback("complete", 100)

    return {
        "ocr_text": extraction.full_text,
        "extracted": extracted_fields,
        "engine": extraction.engine,
        "confidence": extraction.confidence,
        "pages": extraction.pages_processed,
        "matched_clients": matched_clients,
    }


def _rename_document_after_ocr(
    db: Any,
    doc_id: int,
    extracted: dict[str, str],
    matched_clients: list[str],
) -> None:
    """Rename the physical document file and update DB metadata after OCR.

    New filename format: ``{DOC_ID}-{CLIENT_NAMES}-{DATE}.pdf``

    - DOC_ID is the first of: doc_id, cmr_number, invoice_number, or
      the original file stem.
    - CLIENT_NAMES are the matched client names joined with ``-and-``.
    - DATE is the best date found in extracted fields.
    """
    from repositories.document_repository import DocumentRepository

    from .field_extractors import normalize_date

    repo = DocumentRepository(db)
    doc = repo.get_by_id(doc_id)
    if not doc:
        logger.warning("rename_after_ocr: doc %d not found", doc_id)
        return

    old_path = doc.get("file_path", "")
    if not old_path or not os.path.isfile(old_path):
        logger.warning("rename_after_ocr: file missing for doc %d: %s", doc_id, old_path)
        return

    ext = os.path.splitext(old_path)[1].lower() or ".pdf"

    # ── Build doc_id component ──
    doc_id_part = (
        extracted.get("doc_id")
        or extracted.get("cmr_number")
        or extracted.get("invoice_number")
        or os.path.splitext(doc.get("file_name", ""))[0]
    )
    doc_id_part = _sanitize_filename_part(doc_id_part)

    # ── Build client names component ──
    if matched_clients:
        client_part = _sanitize_filename_part(" and ".join(matched_clients))
    else:
        # Fall back to raw extracted names
        raw_name = (
            extracted.get("consignor_stamp")
            or extracted.get("consignee_stamp")
            or extracted.get("haulier_stamp")
            or extracted.get("consignor")
            or extracted.get("consignee")
            or ""
        )
        client_part = _sanitize_filename_part(raw_name) if raw_name else "Unknown"

    # ── Build date component ──
    raw_date = extracted.get("date", "")
    date_part = normalize_date(raw_date) if raw_date else ""
    if not date_part:
        # Fall back to upload date
        uploaded = doc.get("uploaded_at", "")
        date_part = uploaded[:10] if uploaded else "nodate"

    new_name = f"{doc_id_part}-{client_part}-{date_part}{ext}"
    new_path = os.path.join(os.path.dirname(old_path), new_name)

    if old_path == new_path:
        return

    try:
        os.rename(old_path, new_path)
    except OSError as exc:
        logger.warning("rename_after_ocr: os.rename failed for doc %d: %s", doc_id, exc)
        return

    try:
        repo.update(
            doc_id,
            file_path=new_path,
            file_name=new_name,
            title=os.path.splitext(new_name)[0],
        )
    except (ValueError, OSError, RuntimeError) as exc:
        logger.warning("rename_after_ocr: DB update failed for doc %d, rolling back rename: %s", doc_id, exc)
        try:
            os.rename(new_path, old_path)
        except OSError:
            pass
        return

    logger.info(
        "Renamed document %d: %s -> %s   (matched_clients=%s)",
        doc_id, os.path.basename(old_path), new_name, matched_clients,
    )


def _sanitize_filename_part(value: str) -> str:
    """Strip or replace characters that are unsafe in filenames."""
    # Replace path separators, null, control chars
    value = re.sub(r'[\0\n\r\t\\/:*?"<>|]', "_", value)
    # Collapse consecutive underscores/spaces
    value = re.sub(r"[_\s]+", "_", value)
    # Strip leading/trailing separators
    value = value.strip("._ ")
    return value if value else "Unknown"


def _temp_dir(job_id: str) -> str:
    """Build a per-job temp directory under the writable data dir."""
    from utils.resource_path import data_path
    return data_path(f"data/documents/automation/on_demand_{job_id}")


# ── Pipeline validation helpers ───────────────────────────────────────
# These functions implement the validation stages of the pipeline so
# that callers can verify each step before proceeding to the next.


def validate_document_before_ocr(db: Any, doc_id: int) -> ServiceResult[bool]:
    """Validate a document record before running OCR.

    Checks:
        1. The document row exists in the database.
        2. The associated file exists on disk.
        3. The file extension is supported.
        4. The file size is under 50 MB.

    Args:
        db: Database session / connection.
        doc_id: Primary key of the ``documents`` row.

    Returns:
        ``ServiceResult[bool]`` — ``data=True`` when the document passes
        all checks; errors are populated with details on failure.
    """
    from repositories.document_repository import DocumentRepository

    logger.info("Validating document %d before OCR", doc_id)

    doc = DocumentRepository(db).get_by_id(doc_id)
    if not doc:
        logger.error("Validation failed: document %d not found", doc_id)
        return ServiceResult(
            success=False,
            data=False,
            errors=[ErrorDetail(
                field="document_id",
                message=f"Document {doc_id} not found in database",
                code="DOC_NOT_FOUND",
            )],
        )

    file_path = doc.get("file_path", "")
    if not file_path:
        logger.error("Validation failed: document %d has no file_path", doc_id)
        return ServiceResult(
            success=False,
            data=False,
            errors=[ErrorDetail(
                field="file_path",
                message=f"Document {doc_id} has no file path",
                code="FILE_PATH_MISSING",
            )],
        )

    # Delegate file-level checks to the cloud_ocr validator (works for
    # local OCR too — the checks are format/size, not cloud-specific).
    from .cloud_ocr import validate_document_file

    file_check = validate_document_file(file_path)
    if not file_check.success:
        logger.error(
            "Validation failed for document %d: %s",
            doc_id,
            "; ".join(e.message for e in file_check.errors),
        )
        return file_check

    logger.info("Document %d passed pre-OCR validation", doc_id)
    return ServiceResult(success=True, data=True, errors=[])


def validate_extraction(
    result: OcrResult,
    *,
    client_names: list[str] | None = None,
    min_confidence: float = 0.7,
) -> ServiceResult[OcrResult]:
    """Validate the extracted fields from an OCR result.

    Checks:
        1. Overall OCR confidence meets the threshold.
        2. Extracted fields pass format validation.
        3. Client names are cross-referenced (when *client_names* given).

    Args:
        result: The ``OcrResult`` to validate.
        client_names: Optional list of known client names for fuzzy match.
        min_confidence: Minimum acceptable OCR confidence (0.0–1.0).

    Returns:
        ``ServiceResult[OcrResult]`` — the original result (with any
        validation metadata) on partial success, or errors on failure.
    """
    logger.info(
        "Validating extraction for document %d (confidence=%.2f)",
        result.document_id, result.extracted_fields.confidence,
    )

    errors: list[ErrorDetail] = []

    # 1. Overall OCR confidence
    if result.extracted_fields.confidence < min_confidence:
        errors.append(ErrorDetail(
            field="extracted_fields.confidence",
            message=(
                f"OCR confidence {result.extracted_fields.confidence:.2f} "
                f"below minimum {min_confidence:.2f}"
            ),
            code="LOW_CONFIDENCE",
        ))

    # 2. Per-field format validation
    fields_dict = result.extracted_fields.model_dump(exclude={"raw_text", "additional_fields"})
    non_empty = {k: v for k, v in fields_dict.items() if v is not None and v != ""}

    field_validation: FieldValidationResult = validate_extracted_fields(
        non_empty,
        client_names=client_names,
    )

    for err_msg in field_validation.errors:
        errors.append(ErrorDetail(
            field="extracted_fields",
            message=err_msg,
            code="FIELD_VALIDATION_ERROR",
        ))

    for warn_msg in field_validation.warnings:
        logger.warning(
            "Extraction warning for doc %d: %s",
            result.document_id, warn_msg,
        )

    # 3. Log per-field scores
    if field_validation.field_scores:
        low_fields = [f"{k}={v:.2f}" for k, v in field_validation.field_scores.items() if v < 0.6]
        if low_fields:
            logger.info(
                "Low-confidence fields for doc %d: %s",
                result.document_id, ", ".join(low_fields),
            )

    if errors:
        logger.error(
            "Extraction validation failed for doc %d: %s",
            result.document_id,
            "; ".join(e.message for e in errors),
        )
        return ServiceResult(success=False, data=result, errors=errors)

    logger.info(
        "Extraction validation passed for doc %d (field_score=%.3f)",
        result.document_id, field_validation.score,
    )
    return ServiceResult(success=True, data=result, errors=[])


def validate_match(
    matched_trip: MatchedTrip,
    min_confidence: float = 0.5,
) -> ServiceResult[MatchedTrip]:
    """Validate a trip match result meets the minimum confidence threshold.

    Args:
        matched_trip: The ``MatchedTrip`` to validate.
        min_confidence: Minimum acceptable match confidence (0.0–1.0).

    Returns:
        ``ServiceResult[MatchedTrip]`` — the original trip on success,
        or an error detailing why the match is rejected.
    """
    logger.info(
        "Validating trip match: trip_id=%s confidence=%.2f threshold=%.2f",
        matched_trip.trip_id, matched_trip.confidence, min_confidence,
    )

    if matched_trip.confidence < min_confidence:
        msg = (
            f"Match confidence {matched_trip.confidence:.2f} for trip "
            f"{matched_trip.trip_id} is below minimum {min_confidence:.2f}"
        )
        logger.warning("Match validation failed: %s", msg)
        return ServiceResult(
            success=False,
            data=matched_trip,
            errors=[ErrorDetail(
                field="matched_trip.confidence",
                message=msg,
                code="LOW_MATCH_CONFIDENCE",
            )],
        )

    logger.info(
        "Trip match validated: trip_id=%s confidence=%.2f reason='%s'",
        matched_trip.trip_id, matched_trip.confidence, matched_trip.match_reason,
    )
    return ServiceResult(success=True, data=matched_trip, errors=[])


# ── Pipeline service helpers ──────────────────────────────────────────
# These functions provide a service-layer API for pipeline operations,
# so that UI code (automation_worker.py) never touches repositories
# directly.

def get_pipeline_repo(db) -> Any:
    """Return a PipelineRepository bound to *db*."""
    from repositories.pipeline_repository import PipelineRepository
    return PipelineRepository(db)


def get_run(db, run_id: int) -> dict | None:
    """Fetch a pipeline run dict by id, or None if not found."""
    return get_pipeline_repo(db).get_run_by_id(run_id)


def get_extracted_data(db, run_id: int) -> dict:
    """Return the parsed extracted_data_json for a run."""
    return get_pipeline_repo(db).get_extracted_data(run_id)


def set_match_result(db, run_id: int, trip_id: int | None,
                     confidence: float,
                     signals: dict) -> None:
    """Persist the trip match result on a pipeline run."""
    get_pipeline_repo(db).set_match_result(run_id, trip_id, confidence, signals)


def update_stage(db, run_id: int, stage: str, status: str,
                 error_message: str = "") -> None:
    """Update the stage / status of a pipeline run."""
    get_pipeline_repo(db).update_stage(run_id, stage, status, error_message)


def set_related_documents(db, run_id: int, doc_ids: list[int]) -> None:
    """Store the list of related document ids on a pipeline run."""
    get_pipeline_repo(db).set_related_documents(run_id, doc_ids)


def set_document_id(db, run_id: int, doc_id: int) -> None:
    """Associate a document id with a pipeline run."""
    get_pipeline_repo(db).set_document_id(run_id, doc_id)


def init_pipeline(db, prefs=None) -> None:
    """Initialise AI Vision fallback and PaddleOCR settings.

    Called once at worker start-up (or before a batch pipeline run) so
    that the OCR engine and the AI fallback are ready before any work
    begins.  Safe to call multiple times — subsequent calls are no-ops
    for the AI init and just re-read the Paddle config from *prefs*.
    """
    from .ai_fallback import init_from_db as ai_init
    from .ocr_extractor import set_paddle_config, set_paddle_gpu
    # Initialise AI Vision credentials from DB settings.
    try:
        ai_init(db)
    except (ImportError, ValueError, OSError):
        logger.exception("ai_init failed — continuing without AI fallback")

    # Read GPU / OCR preferences and propagate to PaddleOCR.
    if prefs is not None:
        try:
            gpu_val = prefs.get_setting("ocr_use_gpu", "0")
            set_paddle_gpu(gpu_val in ("1", "true", "yes"))
            det_len = prefs.get_setting("ocr_det_limit_side_len", "960")
            rec_batch = prefs.get_setting("ocr_rec_batch_num", "6")
            set_paddle_config(
                det_limit_side_len=int(det_len),
                rec_batch_num=int(rec_batch),
            )
        except (ValueError, TypeError, OSError):
            logger.exception("Failed to apply PaddleOCR preferences")
