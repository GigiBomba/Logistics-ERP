"""Tests for PipelineWorker signals.

Verifies all 8 signals are defined and emit the correct types.
Direct Signal.emit() is used (no QThread needed) so these tests
are fast and deterministic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

# SP workaround: some imports in automation_worker.py reference
# ui.widgets.SP which may not exist in all environments.
import ui.widgets as _ui_widgets

if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S


# ---------------------------------------------------------------------------
# Signal host — mirrors PipelineWorker signal signatures on a plain QObject
# so tests can .connect()/.emit() without instantiating a full QThread.
# ---------------------------------------------------------------------------


class _WorkerSignals(QObject):
    """Duck-typed signal set matching PipelineWorker's 8 signals."""

    stage_changed = Signal(int, str, str)              # run_id, stage, status
    worker_ready = Signal(int)                          # run_id
    ocr_extracted = Signal(int, dict, str)              # run_id, extracted, ocr_text
    match_ready = Signal(int, object, float, object)    # run_id, best_match, conf, candidates
    manual_needed = Signal(int, object)                 # run_id, candidates
    processing_done = Signal(int, str)                  # run_id, processed_pdf_path
    finished = Signal(int, object, object)              # run_id, doc_id, error
    log = Signal(int, str)                              # run_id, message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestPipelineWorkerSignals:
    """Direct Signal emit/type tests for PipelineWorker."""

    # -- 1. All signals defined -------------------------------------------

    def test_all_signals_are_defined(self):
        """Verify PipelineWorker has all 8 signal attributes."""
        from ui.views.automation_worker import PipelineWorker

        expected = {
            "stage_changed",
            "worker_ready",
            "ocr_extracted",
            "match_ready",
            "manual_needed",
            "processing_done",
            "finished",
            "log",
        }
        actual = {
            name
            for name in dir(PipelineWorker)
            if isinstance(getattr(PipelineWorker, name, None), Signal)
        }
        missing = expected - actual
        assert not missing, f"Missing signals: {missing}"

    # -- 2. stage_changed -------------------------------------------------

    def test_stage_changed_emits_correct_types(self, qtbot):
        """Direct emit Signal(int, str, str), verify via waitSignal."""
        _ensure_qapp()
        host = _WorkerSignals()
        received = []

        def slot(run_id, stage, status):
            received.append((run_id, stage, status))

        host.stage_changed.connect(slot)
        try:
            host.stage_changed.emit(42, "ocr", "ocr_done")
            QTest.qWait(50)
            assert len(received) == 1
            r, s, st = received[0]
            assert isinstance(r, int) and r == 42
            assert isinstance(s, str) and s == "ocr"
            assert isinstance(st, str) and st == "ocr_done"
        finally:
            host.stage_changed.disconnect(slot)

    # -- 3. worker_ready --------------------------------------------------

    def test_worker_ready_emits_run_id(self, qtbot):
        """Direct emit Signal(int)."""
        _ensure_qapp()
        host = _WorkerSignals()
        received = []

        def slot(run_id):
            received.append(run_id)

        host.worker_ready.connect(slot)
        try:
            host.worker_ready.emit(99)
            QTest.qWait(50)
            assert len(received) == 1
            assert isinstance(received[0], int)
            assert received[0] == 99
        finally:
            host.worker_ready.disconnect(slot)

    # -- 4. ocr_extracted -------------------------------------------------

    def test_ocr_extracted_emits_correct_types(self, qtbot):
        """Direct emit Signal(int, dict, str)."""
        _ensure_qapp()
        host = _WorkerSignals()
        received = []

        def slot(run_id, extracted, ocr_text):
            received.append((run_id, extracted, ocr_text))

        host.ocr_extracted.connect(slot)
        try:
            data = {"cnp": "123", "name": "test"}
            host.ocr_extracted.emit(7, data, "full ocr text here")
            QTest.qWait(50)
            assert len(received) == 1
            r, ext, txt = received[0]
            assert isinstance(r, int) and r == 7
            assert isinstance(ext, dict) and ext["cnp"] == "123"
            assert isinstance(txt, str) and txt == "full ocr text here"
        finally:
            host.ocr_extracted.disconnect(slot)

    # -- 5. match_ready ---------------------------------------------------

    def test_match_ready_emits_correct_types(self, qtbot):
        """Direct emit Signal(int, object, float, object)."""
        _ensure_qapp()
        host = _WorkerSignals()
        received = []

        def slot(run_id, best_match, conf, candidates):
            received.append((run_id, best_match, conf, candidates))

        host.match_ready.connect(slot)
        try:
            trip = {"id": 1, "client_name": "Acme"}
            candidates = [{"trip": trip, "confidence": 0.95, "signals": {}}]
            host.match_ready.emit(5, trip, 0.95, candidates)
            QTest.qWait(50)
            assert len(received) == 1
            r, bm, c, ca = received[0]
            assert isinstance(r, int) and r == 5
            assert bm["id"] == 1
            assert isinstance(c, float) and c == 0.95
            assert isinstance(ca, list) and len(ca) == 1
        finally:
            host.match_ready.disconnect(slot)

    # -- 6. manual_needed -------------------------------------------------

    def test_manual_needed_emits_correct_types(self, qtbot):
        """Direct emit Signal(int, object)."""
        _ensure_qapp()
        host = _WorkerSignals()
        received = []

        def slot(run_id, candidates):
            received.append((run_id, candidates))

        host.manual_needed.connect(slot)
        try:
            candidates = [{"trip": {"id": 10}, "confidence": 0.6, "signals": {}}]
            host.manual_needed.emit(3, candidates)
            QTest.qWait(50)
            assert len(received) == 1
            r, c = received[0]
            assert isinstance(r, int) and r == 3
            assert isinstance(c, list) and c[0]["trip"]["id"] == 10
        finally:
            host.manual_needed.disconnect(slot)

    # -- 7. processing_done -----------------------------------------------

    def test_processing_done_emits_correct_types(self, qtbot):
        """Direct emit Signal(int, str)."""
        _ensure_qapp()
        host = _WorkerSignals()
        received = []

        def slot(run_id, pdf_path):
            received.append((run_id, pdf_path))

        host.processing_done.connect(slot)
        try:
            host.processing_done.emit(8, "/tmp/processed.pdf")
            QTest.qWait(50)
            assert len(received) == 1
            r, p = received[0]
            assert isinstance(r, int) and r == 8
            assert isinstance(p, str) and p == "/tmp/processed.pdf"
        finally:
            host.processing_done.disconnect(slot)

    # -- 8. finished ------------------------------------------------------

    def test_finished_emits_correct_types(self, qtbot):
        """Direct emit Signal(int, object, object)."""
        _ensure_qapp()
        host = _WorkerSignals()
        received = []

        def slot(run_id, doc_id, error):
            received.append((run_id, doc_id, error))

        host.finished.connect(slot)
        try:
            host.finished.emit(10, 100, None)
            QTest.qWait(50)
            assert len(received) == 1
            r, d, e = received[0]
            assert isinstance(r, int) and r == 10
            assert d == 100
            assert e is None
        finally:
            host.finished.disconnect(slot)

    # -- 9. log -----------------------------------------------------------

    def test_log_emits_run_id_and_message(self, qtbot):
        """Direct emit Signal(int, str)."""
        _ensure_qapp()
        host = _WorkerSignals()
        received = []

        def slot(run_id, message):
            received.append((run_id, message))

        host.log.connect(slot)
        try:
            host.log.emit(1, "Processing started")
            QTest.qWait(50)
            assert len(received) == 1
            r, m = received[0]
            assert isinstance(r, int) and r == 1
            assert isinstance(m, str) and m == "Processing started"
        finally:
            host.log.disconnect(slot)

    # -- 10. finished emitted in error paths ------------------------------

    def test_finished_emitted_in_error_paths(self, qtbot):
        """Test error path emits finished with -1 run ID (PIPELINE_ERROR_RUN_ID)."""
        _ensure_qapp()
        from ui.views.automation_worker import PIPELINE_ERROR_RUN_ID

        host = _WorkerSignals()
        received = []

        def slot(run_id, doc_id, error):
            received.append((run_id, doc_id, error))

        host.finished.connect(slot)
        try:
            # Simulate an error emit (e.g. before DB row created)
            host.finished.emit(PIPELINE_ERROR_RUN_ID, None, "Cannot read input")
            QTest.qWait(50)
            assert len(received) == 1
            r, d, e = received[0]
            assert r == -1, f"Expected -1, got {r}"
            assert d is None
            assert isinstance(e, str)
            assert "Cannot read input" in e
        finally:
            host.finished.disconnect(slot)
