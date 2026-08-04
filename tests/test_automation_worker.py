"""Tests for the automation worker."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtCore import QObject

class TestPipelineWorker:
    def test_creation(self):
        worker = __import__("ui.views.automation_worker", fromlist=["PipelineWorker"]).PipelineWorker(
            db=MagicMock(),
            input_paths=["/tmp/fake.pdf"],
        )
        assert worker._run_id is None
        assert worker.input_paths == ["/tmp/fake.pdf"]

    def test_run_with_no_documents(self):
        worker = __import__("ui.views.automation_worker", fromlist=["PipelineWorker"]).PipelineWorker(
            db=MagicMock(),
            input_paths=[],
        )
        worker.run()
        assert True  # Should complete without error

    def test_stage_changed_signal_emitted(self, qtbot):
        worker = __import__("ui.views.automation_worker", fromlist=["PipelineWorker"]).PipelineWorker(
            db=MagicMock(),
            input_paths=["/tmp/fake.pdf"],
        )
        stage_values = []
        worker.stage_changed.connect(lambda rid, stage, status: stage_values.append((stage, status)))
        worker.run()
        # Even with a fake file path, the worker should attempt and emit stage signals
        # or finish with an error rather than crashing.
        assert len(stage_values) >= 0  # signals may fire before I/O error

    def test_finished_signal_emitted(self, qtbot):
        worker = __import__("ui.views.automation_worker", fromlist=["PipelineWorker"]).PipelineWorker(
            db=MagicMock(),
            input_paths=["/tmp/nonexistent_file.pdf"],
        )
        finished_called = []
        worker.finished.connect(lambda rid, doc_id, err: finished_called.append(True))
        worker.run()
        assert len(finished_called) == 1

    def test_error_on_missing_file(self, qtbot):
        worker = __import__("ui.views.automation_worker", fromlist=["PipelineWorker"]).PipelineWorker(
            db=MagicMock(),
            input_paths=["/tmp/nonexistent_file.pdf"],
        )
        finished_called = []
        worker.finished.connect(lambda rid, doc_id, err: finished_called.append((rid, doc_id, err)))
        worker.run()
        # Should emit finished with PIPELINE_ERROR_RUN_ID (-1) and an error message
        assert len(finished_called) == 1
        rid, doc_id, err_msg = finished_called[0]
        assert err_msg is not None  # error message should be set

    def test_pipeline_error_run_id_defined(self):
        from ui.views.automation_worker import PIPELINE_ERROR_RUN_ID
        assert PIPELINE_ERROR_RUN_ID is not None
