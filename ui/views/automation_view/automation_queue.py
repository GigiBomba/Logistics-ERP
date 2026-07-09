"""Queue management, run execution, and recovery for QtAutomationView.

Provides the :class:`QueueManagementMixin` that handles concurrent file
processing, pipeline-worker lifecycle, and stuck-run recovery.
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any

from PySide6.QtCore import QTimer

from ui.views.automation_worker import PipelineWorker

logger = logging.getLogger(__name__)


class QueueManagementMixin:
    """Mixin providing queue management, worker lifecycle, and recovery.

    Expected attributes / methods on ``self`` (provided by the concrete
    :class:`~ui.views.automation_view.automation_view.QtAutomationView`):

    *Attributes*
      ``db``, ``prefs``, ``_pipeline_repo``, ``_doc_repo``, ``_mode``,
      ``_api_client``, ``_max_concurrent_workers``
      ``_cards`` — ``dict[int, _RunCard]``
      ``_selected_run_id`` — ``int | None``
      ``_candidate_cache`` — ``dict[int, list[dict]]``
      ``_detail`` — ``_RunDetailPanel``

    *Methods*
      ``_refresh_from_db()``, ``_update_selected_run()``,
      ``MAX_CONCURRENT_WORKERS``
    """

    # ------------------------------------------------------------------
    # Initialisation  (called from QtAutomationView.__init__)
    # ------------------------------------------------------------------

    def _init_queue_management(self) -> None:
        """Initialise all attributes used by the queue / worker machinery."""
        self._workers: dict[int, PipelineWorker] = {}
        self._pending_workers: list[PipelineWorker] = []
        self._queue: list[str] = []
        self._cards: dict[int, Any] = {}  # run_id -> _RunCard
        self._selected_run_id: int | None = None
        self._candidate_cache: dict[int, list[dict[str, Any]]] = {}
        self._batch_counter: int = 0
        self._batch_for_run: dict[int, int] = {}  # run_id -> batch_id
        self._current_batch_id: int = 0

    # ------------------------------------------------------------------
    # File drop handling  (queue management)
    # ------------------------------------------------------------------

    def _on_files_dropped(self, file_paths: list[str]) -> None:
        """Accept a list of file paths, expand directories once, filter to
        supported extensions, and queue them for processing."""
        # Expand directories one level deep.
        expanded: list[str] = []
        for p in file_paths:
            if os.path.isdir(p):
                try:
                    for entry in sorted(os.listdir(p)):
                        full = os.path.join(p, entry)
                        if os.path.isfile(full):
                            expanded.append(full)
                except OSError:
                    pass
            elif os.path.isfile(p):
                expanded.append(p)

        # Filter to supported extensions.
        from services.document_automation.image_processor import (
            _IMAGE_EXTENSIONS,
            _PDF_EXTENSIONS,
        )

        supported = []
        for p in expanded:
            ext = os.path.splitext(p)[1].lower()
            if ext in _IMAGE_EXTENSIONS or ext in _PDF_EXTENSIONS:
                supported.append(p)
            else:
                logger.debug("Drop rejected (unsupported): %s", p)

        if not supported:
            return

        # Each drop starts a new batch so simple-mode skip-package
        # groups all files from this drop into a single package.
        self._batch_counter += 1
        self._current_batch_id = self._batch_counter

        # Queue the files (start as many as the cap allows, defer the
        # rest to be picked up by ``_on_worker_finished``).
        self._queue = self._queue + supported
        self._drain_pending_files()

    def _drain_pending_files(self) -> None:
        """Start workers for queued files up to the concurrency cap."""
        if not self._queue:
            return
        active = sum(
            1 for w in self._workers.values()
            if w.isRunning() and not w.isFinished()
        )
        while self._queue and active < self.MAX_CONCURRENT_WORKERS:
            path = self._queue.pop(0)
            self._start_worker_for_file(path)
            active += 1

    def _start_worker_for_file(self, path: str) -> None:
        """Create a :class:`PipelineWorker` for *path* and start it."""
        worker = PipelineWorker(
            self.db, [path], prefs=self.prefs, mode=self._mode,
        )
        worker.stage_changed.connect(self._on_stage_changed)
        worker.ocr_extracted.connect(self._on_ocr_extracted)
        worker.match_ready.connect(self._on_match_ready)
        worker.manual_needed.connect(self._on_manual_needed)
        worker.processing_done.connect(self._on_processing_done)
        worker.finished.connect(self._on_worker_finished)
        worker.log.connect(self._on_worker_log)
        worker.finished.connect(worker.deleteLater)
        # Wire the detail panel's manual selection to the standalone linker.
        self._detail.link_requested.connect(self._on_link_requested)
        # Hold a reference so the worker is not GC'd before ``worker_ready`` fires.
        self._pending_workers.append(worker)
        worker.worker_ready.connect(self._on_worker_ready)
        worker.start()
        self._refresh_from_db()

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    def _on_stage_changed(self, run_id: int, stage: str, status: str) -> None:
        """Update the in-memory card for the run, if we already have it."""
        card = self._cards.get(int(run_id))
        if card is not None:
            try:
                card.update({"id": int(run_id), "stage": stage, "status": status})
            except Exception:
                logger.exception("Failed to update run card in place")
                self._refresh_from_db()
        else:
            self._refresh_from_db()

    def _on_ocr_extracted(self, run_id: int, extracted: dict, ocr_text: str) -> None:
        """OCR done — refresh to show latest status."""
        self._refresh_from_db()

    def _on_match_ready(
        self,
        run_id: int,
        best_match: Any,
        confidence: float,
        candidates: Any,
    ) -> None:
        """Trip match found — refresh list and update detail if selected."""
        if candidates:
            self._candidate_cache[int(run_id)] = list(candidates)
        self._refresh_from_db()
        if self._selected_run_id == int(run_id):
            self._update_selected_run()

    def _on_manual_needed(self, run_id: int, candidates: Any) -> None:
        """Worker needs manual trip selection — store candidates and refresh."""
        if candidates:
            self._candidate_cache[int(run_id)] = list(candidates)
        self._refresh_from_db()
        if self._selected_run_id == int(run_id):
            self._update_selected_run()

    def _on_processing_done(self, run_id: int, processed_pdf_path: str) -> None:
        """Simple-mode processing complete — refresh list and detail."""
        self._refresh_from_db()
        if self._selected_run_id == int(run_id):
            self._update_selected_run()

    def _on_worker_ready(self, run_id: int) -> None:
        """Worker created its DB row — add to the tracking dict."""
        if run_id in self._workers:
            return
        worker = self.sender()
        if worker is not None:
            self._workers[run_id] = worker
            with contextlib.suppress(ValueError):
                self._pending_workers.remove(worker)
        self._batch_for_run[run_id] = getattr(self, "_current_batch_id", 0)
        self._refresh_from_db()

    def _on_link_requested(self, run_id: int, trip_id: int) -> None:
        """User clicked a candidate — manually link the document to the trip."""
        from ui.views.automation_worker import link_document_to_trip

        doc_id = link_document_to_trip(self.db, run_id, trip_id)
        if doc_id:
            logger.info("Manual link: run %s -> trip %s -> doc %s", run_id, trip_id, doc_id)
        else:
            logger.warning("Manual link failed: run %s -> trip %s", run_id, trip_id)
        self._refresh_from_db()
        if self._selected_run_id == run_id:
            self._update_selected_run()

    def _on_worker_finished(
        self, run_id: int, document_id: Any, error: Any
    ) -> None:
        """Worker thread finished — remove worker, drain queue, and refresh."""
        try:
            rid = int(run_id) if run_id is not None else None
        except (TypeError, ValueError):
            rid = None
        if rid is not None and rid in self._workers:
            del self._workers[rid]
        # Clean up pending list in case worker_ready never fired.
        self._pending_workers[:] = [
            w for w in self._pending_workers
            if w.isRunning() and not w.isFinished()
        ]
        if error:
            logger.warning(
                "Pipeline run %s finished with error: %s", run_id, error,
            )
        self._drain_pending_files()
        self._refresh_from_db()

    def _on_worker_log(self, run_id: int, message: str) -> None:
        """Forward worker log lines to the application logger."""
        logger.info("[run %s] %s", run_id, message)

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    def _recover_stuck_runs(self) -> None:
        """Recover pipeline runs that were left in a transitional state."""
        if not self.db:
            return
        try:
            recovered = self._pipeline_repo.recover_stuck_runs()
        except Exception:
            recovered = 0
            logger.exception("recover_stuck_runs failed")
        if recovered:
            logger.info("Recovered %d stuck pipeline runs on startup", recovered)
            self._refresh_from_db()
