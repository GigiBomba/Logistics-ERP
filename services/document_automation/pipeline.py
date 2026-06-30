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
import shutil
import threading
from datetime import datetime
from typing import Any, Callable, Optional

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
        row = db.conn.execute(
            "SELECT key, value FROM settings WHERE key IN (?, ?, ?)",
            ("ocr_use_gpu", "ocr_det_limit_side_len", "ocr_rec_batch_num"),
        ).fetchall()
        overrides = {r["key"]: r["value"] for r in row}
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
    finally:
        try:
            if os.path.isdir(temp_output_dir):
                shutil.rmtree(temp_output_dir, ignore_errors=True)
        except Exception:
            logger.debug("Failed to clean up temp dir: %s", temp_output_dir)

    if progress_callback:
        progress_callback("ocr", 50)

    ocr = OcrExtractor(db=db)
    extraction = ocr.extract(result.pdf_path, stop_event=stop_event)

    if progress_callback:
        progress_callback("persisting", 80)

    try:
        DocumentRepository(db).update(
            doc_id,
            ocr_text=extraction.full_text or "",
            extracted_data_json=json.dumps(extraction.extracted or {}, ensure_ascii=False, default=str),
            ocr_run_at=datetime.now().isoformat(timespec="seconds"),
            ocr_engine=extraction.engine or "",
        )
    except Exception as exc:
        logger.exception("Failed to persist OCR result to document %d", doc_id)
        if progress_callback:
            progress_callback("persisting", 100)
        raise RuntimeError(f"OCR persistence failed: {exc}") from exc

    if progress_callback:
        progress_callback("complete", 100)

    return {
        "ocr_text": extraction.full_text,
        "extracted": extraction.extracted,
        "engine": extraction.engine,
        "confidence": extraction.confidence,
        "pages": extraction.pages_processed,
    }


def _temp_dir(job_id: str) -> str:
    """Build a per-job temp directory under the writable data dir."""
    from utils.resource_path import data_path
    return data_path(f"data/documents/automation/on_demand_{job_id}")
