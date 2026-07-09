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

from repositories.settings_repository import SettingsRepository

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
    except Exception:
        pass

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
    except Exception:
        pass

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
    except Exception as exc:
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
    except Exception:
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
    except Exception as exc:
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
    except Exception as exc:
        logger.exception("Failed to persist OCR result to document %d", doc_id)
        if progress_callback:
            progress_callback("persisting", 100)
        raise RuntimeError(f"OCR persistence failed: {exc}") from exc

    if progress_callback:
        progress_callback("rename", 90)

    # ── Rename document to DOCID-CLIENT-DATE.pdf ──
    try:
        _rename_document_after_ocr(db, doc_id, extracted_fields, matched_clients)
    except Exception as exc:
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
    except Exception as exc:
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
