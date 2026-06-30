"""QThread worker for re-running OCR on a single document.

The Document Center exposes a "Re-run OCR" button that triggers
this worker.  It reuses :func:`services.document_automation.pipeline.run_for_existing_document`
so the heavy lifting (image enhancement, OCR, field extraction)
runs in the same way the Automation tab does, but on a single
existing row instead of a freshly-imported file.

Unlike :class:`PipelineWorker`, this worker does not need a
``run_id`` (it operates on a ``document_id`` directly) and does
not emit match/package signals.  It does emit the same
``finished(int, object)`` shape as the worker in
:mod:`ui.views.automation_worker` so callers can ``connect`` to
either uniformly.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class ReRunOcrWorker(QThread):
    """Run image enhancement + OCR + extraction on one document.

    Signals:
        stage_changed(str, int)  — (stage_label, percent)
        finished(int, object)    — (document_id, error_or_None)
    """

    stage_changed = Signal(str, int)
    finished = Signal(int, object)

    def __init__(self, db: Any, doc_id: int, *, prefs=None,
                 parent: Any | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.doc_id = int(doc_id)
        self.prefs = prefs
        self._stop_event = threading.Event()
        from services.document_automation.ocr_extractor import (
            set_paddle_config,
            set_paddle_gpu,
        )
        try:
            from services.document_automation.ai_fallback import init_from_db as ai_init
            ai_init(self.db)
        except Exception:
            pass
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
            except Exception:
                pass

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    def run(self) -> None:
        try:
            from services.document_automation.pipeline import (
                run_for_existing_document,
            )
            run_for_existing_document(
                self.db,
                self.doc_id,
                progress_callback=self._on_progress,
                stop_event=self._stop_event,
            )
            self.finished.emit(self.doc_id, None)
        except Exception as exc:  # pragma: no cover - thread safety
            logger.exception("Re-run OCR failed for document %d", self.doc_id)
            self.finished.emit(self.doc_id, exc)

    def _on_progress(self, stage_label: str, percent: int) -> None:
        try:
            self.stage_changed.emit(stage_label, int(percent))
        except RuntimeError as exc:
            if "wrapped C/C++ object" in str(exc):
                pass
            else:
                raise
