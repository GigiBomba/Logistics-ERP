"""Regression tests for Phase 4b — missing worker slot methods.

Issue 5: ``_start_worker_for_file`` connected the worker's signals
to ``_on_stage_changed`` / ``_on_ocr_extracted`` / ``_on_match_ready``
/ ``_on_worker_finished`` / ``_on_worker_log`` — none of which
existed on the view.  The first ``AttributeError`` from
``connect()`` aborted the drop handler so dropping a file did
nothing.

These tests confirm the methods exist, are callable, and behave
sanely on inputs from the worker.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication


def _ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _new_db():
    from database.db_manager import DatabaseManager
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    db = DatabaseManager(tmp.name)
    return db, tmp.name


def _make_view():
    _ensure_qapp()
    db, path = _new_db()
    from ui.views.automation_view import QtAutomationView
    view = QtAutomationView(None, db=db, prefs=None, ops=None)
    return view, db, path


class TestWorkerSlotsExist(unittest.TestCase):
    """The view must define the slot methods that ``_start_worker_for_file`` connects to."""

    def setUp(self) -> None:
        self.view, self.db, self.path = _make_view()

    def tearDown(self) -> None:
        try:
            self.db.close()
        finally:
            os.unlink(self.path)
        self.view.deleteLater()

    def test_on_stage_changed_method_exists(self) -> None:
        self.assertTrue(callable(getattr(self.view, "_on_stage_changed", None)))

    def test_on_ocr_extracted_method_exists(self) -> None:
        self.assertTrue(callable(getattr(self.view, "_on_ocr_extracted", None)))

    def test_on_match_ready_method_exists(self) -> None:
        self.assertTrue(callable(getattr(self.view, "_on_match_ready", None)))

    def test_on_worker_finished_method_exists(self) -> None:
        self.assertTrue(callable(getattr(self.view, "_on_worker_finished", None)))

    def test_on_worker_log_method_exists(self) -> None:
        self.assertTrue(callable(getattr(self.view, "_on_worker_log", None)))


class TestWorkerSlotsBehave(unittest.TestCase):
    """The slot methods should be tolerant of partial / odd inputs and
    should never raise on a happy-path call."""

    def setUp(self) -> None:
        self.view, self.db, self.path = _make_view()

    def tearDown(self) -> None:
        try:
            self.db.close()
        finally:
            os.unlink(self.path)
        self.view.deleteLater()

    def test_on_stage_changed_with_unknown_run_id_refreshes(self) -> None:
        """If the card isn't in the cache yet, fall back to a DB
        refresh rather than crashing."""
        # No card for run_id=999; should just call _refresh_from_db
        # and not raise.
        self.view._refresh_from_db = MagicMock()
        self.view._on_stage_changed(999, "import", "imported")
        self.view._refresh_from_db.assert_called_once()

    def test_on_stage_changed_with_known_run_id_updates_in_place(self) -> None:
        # Insert a run so a card is created.
        from repositories.pipeline_repository import PipelineRepository
        rid = PipelineRepository(self.db).create_run(
            source_file_path="/tmp/fake.jpg",
            source_file_name="fake.jpg",
            source_mime_type="image/jpeg",
            source_file_size=123,
        )
        self.view._refresh_from_db()
        # Now the card should exist.
        self.assertIn(rid, self.view._cards)
        card = self.view._cards[rid]
        # Mock the card's update so we can verify it gets called.
        card.update = MagicMock()
        self.view._refresh_from_db = MagicMock()
        self.view._on_stage_changed(rid, "processing", "processing")
        card.update.assert_called_once()
        # And we should NOT have triggered a full refresh.
        self.view._refresh_from_db.assert_not_called()

    def test_on_worker_finished_removes_worker_from_cache(self) -> None:
        from ui.views.automation_worker import PipelineWorker
        from PySide6.QtCore import QThread
        # Don't actually start a thread; just stuff a fake entry.
        self.view._workers[42] = MagicMock(spec=QThread)
        # Also make sure drain + refresh don't crash.
        self.view._drain_pending_files = MagicMock()
        self.view._refresh_from_db = MagicMock()
        self.view._on_worker_finished(42, None, None)
        self.assertNotIn(42, self.view._workers)
        self.view._drain_pending_files.assert_called_once()
        self.view._refresh_from_db.assert_called_once()

    def test_on_worker_finished_handles_error_run_id(self) -> None:
        """``PIPELINE_ERROR_RUN_ID = -1`` is the sentinel emitted when
        the worker aborts before the DB row is created."""
        from ui.views.automation_worker import PIPELINE_ERROR_RUN_ID
        self.view._drain_pending_files = MagicMock()
        self.view._refresh_from_db = MagicMock()
        # Should not raise even when -1 is the run_id and there's no
        # corresponding worker in the cache.
        self.view._on_worker_finished(PIPELINE_ERROR_RUN_ID, None, "boom")
        self.view._drain_pending_files.assert_called_once()
        self.view._refresh_from_db.assert_called_once()

    def test_on_worker_log_does_not_raise(self) -> None:
        # Should just forward to logger; no side effects we can
        # assert, but it must not raise.
        try:
            self.view._on_worker_log(1, "imported fake.jpg")
        except Exception as exc:
            self.fail(f"_on_worker_log raised: {exc}")

    def test_start_worker_for_file_connects_without_error(self) -> None:
        """Connecting a real (not started) PipelineWorker to the view
        must not raise.  We don't call ``worker.start()`` to avoid
        actually running the pipeline in tests."""
        from ui.views.automation_worker import PipelineWorker
        worker = PipelineWorker(self.db, ["x"])
        try:
            # This is the exact set of connects used in
            # ``_start_worker_for_file``.  Each must succeed now
            # that the slot methods exist.
            worker.stage_changed.connect(self.view._on_stage_changed)
            worker.ocr_extracted.connect(self.view._on_ocr_extracted)
            worker.match_ready.connect(self.view._on_match_ready)
            worker.finished.connect(self.view._on_worker_finished)
            worker.log.connect(self.view._on_worker_log)
        except Exception as exc:
            self.fail(f"Connecting worker signals raised: {exc}")


if __name__ == "__main__":
    unittest.main()
