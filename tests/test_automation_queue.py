"""pytest-qt tests for QueueManagementMixin — queue logic, worker lifecycle,
and stuck-run recovery.

Tests
-----
- ``_init_queue_management`` initialises all attributes
- ``_on_files_dropped`` filters to supported extensions, expands directories,
  assigns batch ids, and enqueues files
- ``_drain_pending_files`` respects the concurrency cap
- Worker signal handlers update cards and refresh appropriately
- ``_recover_stuck_runs`` delegates to pipeline_repo
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject

from ui.views.automation_view.automation_queue import QueueManagementMixin


# =========================================================================
# Fake concrete class for testing the mixin in isolation
# =========================================================================


class _FakeQueueView(QObject, QueueManagementMixin):
    """Minimal concrete class that inherits QueueManagementMixin.

    Provides the attributes / methods the mixin expects on ``self``.
    Simulates worker startup so the queue drain behaves correctly.
    """

    def __init__(self, db=None, prefs=None, pipeline_repo=None):
        super().__init__()
        self.db = db
        self.prefs = prefs
        self._pipeline_repo = pipeline_repo
        self._doc_repo = MagicMock()
        self._mode = "advanced"
        self._api_client = MagicMock()
        self._max_concurrent_workers = 2

        # Detail panel mock with a ``link_requested`` signal-compatible mock.
        detail = MagicMock()
        detail.link_requested = MagicMock()
        self._detail = detail

        self._init_queue_management()

        # Tracking for test assertions
        self._started_files: list[str] = []

    @property
    def MAX_CONCURRENT_WORKERS(self):
        return self._max_concurrent_workers

    # Stub methods the mixin calls; spy-wrapped so tests can assert.
    def _refresh_from_db(self) -> None:
        pass

    def _update_selected_run(self) -> None:
        pass

    def _start_worker_for_file(self, path: str) -> None:
        """Simulate starting a worker so _drain_pending_files makes progress."""
        self._started_files.append(path)
        # Add a fake worker so the concurrency cap is tracked correctly.
        w = MagicMock()
        w.isRunning.return_value = True
        w.isFinished.return_value = False
        self._workers[id(w)] = w


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def fake_view():
    return _FakeQueueView(db=MagicMock(), prefs=MagicMock(), pipeline_repo=MagicMock())


@pytest.fixture
def image_extensions():
    """Patch image_processor extensions to known values for filter tests."""
    exts = {".jpg", ".jpeg", ".png", ".pdf", ".tif", ".tiff", ".heic", ".webp", ".bmp"}
    with patch(
        "services.document_automation.image_processor._IMAGE_EXTENSIONS",
        {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".heic"},
    ):
        with patch(
            "services.document_automation.image_processor._PDF_EXTENSIONS",
            {".pdf"},
        ):
            yield exts


# =========================================================================
# _init_queue_management
# =========================================================================


class TestInitQueueManagement:
    """_init_queue_management sets up all required attributes."""

    def test_workers_dict(self, fake_view):
        assert isinstance(fake_view._workers, dict)
        assert fake_view._workers == {}

    def test_pending_workers_list(self, fake_view):
        assert isinstance(fake_view._pending_workers, list)
        assert fake_view._pending_workers == []

    def test_queue_list(self, fake_view):
        assert isinstance(fake_view._queue, list)
        assert fake_view._queue == []

    def test_cards_dict(self, fake_view):
        assert isinstance(fake_view._cards, dict)
        assert fake_view._cards == {}

    def test_selected_run_id_none(self, fake_view):
        assert fake_view._selected_run_id is None

    def test_candidate_cache_dict(self, fake_view):
        assert isinstance(fake_view._candidate_cache, dict)
        assert fake_view._candidate_cache == {}

    def test_batch_counter(self, fake_view):
        assert fake_view._batch_counter == 0

    def test_batch_for_run_dict(self, fake_view):
        assert isinstance(fake_view._batch_for_run, dict)
        assert fake_view._batch_for_run == {}

    def test_current_batch_id(self, fake_view):
        assert fake_view._current_batch_id == 0


# =========================================================================
# _on_files_dropped
# =========================================================================


class TestOnFilesDropped:
    """File drop handling — expansion, filtering, batching."""

    def test_accepts_single_file(self, fake_view, image_extensions, tmp_path):
        p = tmp_path / "doc.pdf"
        p.write_text("dummy content")
        fake_view._on_files_dropped([str(p)])
        # File was consumed from the queue and a worker was started for it
        assert fake_view._started_files == [str(p)]
        assert fake_view._current_batch_id > 0

    def test_rejects_unsupported_extension(self, fake_view, image_extensions, tmp_path):
        p = tmp_path / "doc.txt"
        p.write_text("hello")
        fake_view._on_files_dropped([str(p)])
        # No started files, queue remains empty
        assert fake_view._started_files == []
        assert fake_view._queue == []

    def test_mixed_supported_and_unsupported(self, fake_view, image_extensions, tmp_path):
        ok = tmp_path / "img.jpg"
        bad = tmp_path / "readme.txt"
        ok.write_text("img")
        bad.write_text("text")
        fake_view._on_files_dropped([str(ok), str(bad)])
        # Only the supported file gets started
        assert fake_view._started_files == [str(ok)]

    def test_expands_directory(self, fake_view, image_extensions, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "a.jpg").write_text("a")
        (sub / "b.pdf").write_text("b")
        (sub / "c.txt").write_text("c")  # filtered out
        fake_view._on_files_dropped([str(sub)])
        started_names = {os.path.basename(p) for p in fake_view._started_files}
        assert "a.jpg" in started_names
        assert "b.pdf" in started_names
        assert "c.txt" not in started_names

    def test_empty_directory_produces_no_files(self, fake_view, image_extensions, tmp_path):
        empty = tmp_path / "empty_dir"
        empty.mkdir()
        fake_view._on_files_dropped([str(empty)])
        assert fake_view._started_files == []

    def test_nonexistent_path_ignored(self, fake_view, image_extensions):
        fake_view._on_files_dropped(["/nonexistent/file.pdf"])
        assert fake_view._started_files == []

    def test_empty_file_list_does_nothing(self, fake_view):
        fake_view._on_files_dropped([])
        assert fake_view._started_files == []

    def test_batch_id_increments(self, fake_view, image_extensions, tmp_path):
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.pdf"
        a.write_text("a"); b.write_text("b")
        fake_view._on_files_dropped([str(a)])
        batch1 = fake_view._current_batch_id
        fake_view._on_files_dropped([str(b)])
        assert fake_view._current_batch_id > batch1

    def test_queue_appended_not_replaced(self, fake_view, image_extensions, tmp_path):
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.pdf"
        a.write_text("a"); b.write_text("b")
        fake_view._on_files_dropped([str(a)])
        started_after_first = len(fake_view._started_files)
        fake_view._on_files_dropped([str(b)])
        # Second drop adds another file to the started list (total 2)
        assert len(fake_view._started_files) > started_after_first


# =========================================================================
# _drain_pending_files
# =========================================================================


class TestDrainPendingFiles:
    """Concurrency-aware queue draining."""

    def test_starts_worker_for_each_file(self, fake_view, tmp_path):
        files = []
        for name in ["a.pdf", "b.pdf"]:
            p = tmp_path / name
            p.write_text("x")
            files.append(str(p))
        fake_view._queue = list(files)
        fake_view._max_concurrent_workers = 10  # let both through
        # Stub _start_worker_for_file so we can count calls
        calls = []
        original = fake_view._start_worker_for_file

        def tracking_start(path):
            calls.append(path)
            original(path)

        fake_view._start_worker_for_file = tracking_start
        fake_view._drain_pending_files()
        assert len(calls) == 2
        assert fake_view._queue == []

    def test_respects_concurrency_cap(self, fake_view, tmp_path):
        """When cap is 1, only one file is started per drain call."""
        fake_view._max_concurrent_workers = 1
        files = []
        for name in ["a.pdf", "b.pdf"]:
            p = tmp_path / name
            p.write_text("x")
            files.append(str(p))
        fake_view._queue = list(files)
        calls = []
        original = fake_view._start_worker_for_file

        def tracking_start(path):
            calls.append(path)

        fake_view._start_worker_for_file = tracking_start
        fake_view._drain_pending_files()
        assert len(calls) == 1
        assert len(fake_view._queue) == 1  # one remains

    def test_no_files_does_nothing(self, fake_view):
        fake_view._queue = []
        fake_view._drain_pending_files()  # must not crash
        assert fake_view._queue == []


# =========================================================================
# Worker signal handlers
# =========================================================================


class TestWorkerSignalHandlers:
    """Signal handlers update state and trigger refreshes."""

    def test_on_stage_changed_unknown_run_refreshes(self, fake_view):
        fake_view._refresh_from_db = MagicMock()
        fake_view._on_stage_changed(999, "import", "imported")
        fake_view._refresh_from_db.assert_called_once()

    def test_on_stage_changed_known_run_updates_card(self, fake_view):
        card = MagicMock()
        fake_view._cards[1] = card
        fake_view._refresh_from_db = MagicMock()
        fake_view._on_stage_changed(1, "processing", "processing")
        card.update.assert_called_once()
        fake_view._refresh_from_db.assert_not_called()

    def test_on_ocr_extracted_refreshes(self, fake_view):
        fake_view._refresh_from_db = MagicMock()
        fake_view._on_ocr_extracted(1, {"field": "val"}, "text")
        fake_view._refresh_from_db.assert_called_once()

    def test_on_match_ready_stores_candidates(self, fake_view):
        candidates = [{"trip": {"id": 1}, "confidence": 0.9}]
        fake_view._on_match_ready(1, None, 0.9, candidates)
        assert fake_view._candidate_cache[1] == candidates

    def test_on_match_ready_updates_selected_run(self, fake_view):
        fake_view._selected_run_id = 1
        fake_view._update_selected_run = MagicMock()
        fake_view._on_match_ready(1, None, 0.9, [])
        fake_view._update_selected_run.assert_called_once()

    def test_on_manual_needed_stores_candidates(self, fake_view):
        cands = [{"trip": {"id": 2}, "confidence": 0.7}]
        fake_view._on_manual_needed(1, cands)
        assert fake_view._candidate_cache[1] == cands

    def test_on_processing_done_refreshes(self, fake_view):
        fake_view._refresh_from_db = MagicMock()
        fake_view._update_selected_run = MagicMock()
        fake_view._on_processing_done(1, "/tmp/out.pdf")
        fake_view._refresh_from_db.assert_called_once()

    def test_on_worker_ready_adds_to_workers(self, fake_view):
        worker = MagicMock()
        fake_view.sender = MagicMock(return_value=worker)
        fake_view._on_worker_ready(42)
        assert fake_view._workers[42] is worker
        assert 42 not in fake_view._pending_workers

    def test_on_worker_ready_sets_batch_for_run(self, fake_view):
        fake_view._current_batch_id = 7
        fake_view.sender = MagicMock(return_value=MagicMock())
        fake_view._on_worker_ready(1)
        assert fake_view._batch_for_run[1] == 7

    def test_on_worker_finished_removes_worker(self, fake_view):
        fake_view._workers[1] = MagicMock()
        fake_view._drain_pending_files = MagicMock()
        fake_view._refresh_from_db = MagicMock()
        fake_view._on_worker_finished(1, None, None)
        assert 1 not in fake_view._workers

    def test_on_worker_finished_drains_and_refreshes(self, fake_view):
        fake_view._workers[1] = MagicMock()
        fake_view._drain_pending_files = MagicMock()
        fake_view._refresh_from_db = MagicMock()
        fake_view._on_worker_finished(1, None, None)
        fake_view._drain_pending_files.assert_called_once()
        fake_view._refresh_from_db.assert_called_once()

    def test_on_worker_finished_handles_none_run_id(self, fake_view):
        fake_view._drain_pending_files = MagicMock()
        fake_view._refresh_from_db = MagicMock()
        # Must not crash when run_id is None
        fake_view._on_worker_finished(None, None, None)
        fake_view._drain_pending_files.assert_called_once()
        fake_view._refresh_from_db.assert_called_once()

    def test_on_worker_log_does_not_raise(self, fake_view):
        fake_view._on_worker_log(1, "some message")  # must not crash

    def test_on_worker_log_different_run_ids(self, fake_view):
        fake_view._on_worker_log(42, "stage 1")
        fake_view._on_worker_log(-1, "error before db row")
        fake_view._on_worker_log(0, "edge case")


# =========================================================================
# _on_link_requested
# =========================================================================


class TestOnLinkRequested:
    """Manual trip linking delegates to link_document_to_trip."""

    @patch("ui.views.automation_worker.link_document_to_trip")
    def test_calls_link_function(self, mock_link, fake_view):
        mock_link.return_value = 100
        fake_view._refresh_from_db = MagicMock()
        fake_view._on_link_requested(1, 42)
        mock_link.assert_called_once_with(fake_view.db, 1, 42)

    @patch("ui.views.automation_worker.link_document_to_trip")
    def test_updates_selected_run(self, mock_link, fake_view):
        mock_link.return_value = 100
        fake_view._selected_run_id = 1
        fake_view._update_selected_run = MagicMock()
        fake_view._on_link_requested(1, 42)
        fake_view._update_selected_run.assert_called_once()


# =========================================================================
# _recover_stuck_runs
# =========================================================================


class TestRecoverStuckRuns:
    """Stuck-run recovery delegates to pipeline_repo."""

    def test_calls_recover_on_repo(self, fake_view):
        fake_view._pipeline_repo.recover_stuck_runs = MagicMock(return_value=2)
        fake_view._refresh_from_db = MagicMock()
        fake_view._recover_stuck_runs()
        fake_view._pipeline_repo.recover_stuck_runs.assert_called_once()
        assert fake_view._refresh_from_db.called

    def test_no_db_skips_gracefully(self, fake_view):
        fake_view.db = None
        fake_view._pipeline_repo.recover_stuck_runs = MagicMock()
        fake_view._recover_stuck_runs()
        fake_view._pipeline_repo.recover_stuck_runs.assert_not_called()

    def test_recover_exception_handled(self, fake_view):
        fake_view._pipeline_repo.recover_stuck_runs = MagicMock(
            side_effect=Exception("DB error"),
        )
        fake_view._recover_stuck_runs()  # must not crash

    def test_recover_returns_zero(self, fake_view):
        fake_view._pipeline_repo.recover_stuck_runs = MagicMock(return_value=0)
        fake_view._refresh_from_db = MagicMock()
        fake_view._recover_stuck_runs()
        # No recovered runs → _refresh_from_db is skipped (not called)
        fake_view._refresh_from_db.assert_not_called()
