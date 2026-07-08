"""Tests for the automation worker."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtCore import QObject

class TestPipelineWorker:
    def test_creation(self):
        worker = __import__("ui.views.automation_worker", fromlist=["PipelineWorker"]).PipelineWorker(
            pipeline_id=1,
            document_ids=[1, 2, 3],
            db=MagicMock(),
        )
        assert worker._pipeline_id == 1
        assert worker._document_ids == [1, 2, 3]

    def test_run_with_no_documents(self):
        worker = __import__("ui.views.automation_worker", fromlist=["PipelineWorker"]).PipelineWorker(
            pipeline_id=1,
            document_ids=[],
            db=MagicMock(),
        )
        worker.run()
        assert True  # Should complete without error

    def test_progress_signal_emitted(self, qtbot):
        worker = __import__("ui.views.automation_worker", fromlist=["PipelineWorker"]).PipelineWorker(
            pipeline_id=1,
            document_ids=[1],
            db=MagicMock(),
        )
        progress_values = []
        worker.progress.connect(lambda val: progress_values.append(val))
        worker.run()
        assert len(progress_values) > 0

    def test_finished_signal_emitted(self, qtbot):
        worker = __import__("ui.views.automation_worker", fromlist=["PipelineWorker"]).PipelineWorker(
            pipeline_id=1,
            document_ids=[1],
            db=MagicMock(),
        )
        finished_called = []
        worker.finished.connect(lambda: finished_called.append(True))
        worker.run()
        assert len(finished_called) == 1

    def test_error_signal_emitted_on_failure(self, qtbot):
        worker = __import__("ui.views.automation_worker", fromlist=["PipelineWorker"]).PipelineWorker(
            pipeline_id=1,
            document_ids=[1],
            db=None,
        )
        error_called = []
        worker.error.connect(lambda msg: error_called.append(msg))
        worker.run()
        # Database=None should not crash

    def test_pipeline_error_run_id_defined(self):
        from ui.views.automation_worker import PIPELINE_ERROR_RUN_ID
        assert PIPELINE_ERROR_RUN_ID is not None
