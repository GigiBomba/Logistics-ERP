"""pytest-qt tests for PipelineWorker — worker lifecycle, signals, and
standalone helper functions.

Expands on the legacy tests in ``test_automation_worker.py`` (which covered an
older constructor API) with modern pytest-qt fixtures and coverage for the
current ``PipelineWorker(db, input_paths, …)`` constructor.

Tests
-----
- Module-level constants and helpers (PIPELINE_ERROR_RUN_ID, _file_hash,
  _automation_output_dir)
- ``PipelineWorker`` creation with the current constructor signature
- ``stop_event`` property
- ``override_match`` behaviour
- ``run_id`` property
- Signal instantiation (signals are correctly defined on the class)
- ``link_document_to_trip`` and ``register_standalone_document`` function
  signatures and basic call paths
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QObject

from ui.views.automation_worker import (
    PIPELINE_ERROR_RUN_ID,
    PipelineWorker,
    _automation_output_dir,
    _file_hash,
    link_document_to_trip,
    register_standalone_document,
)


# =========================================================================
# Module-level constants & helpers
# =========================================================================


class TestConstants:
    """Module-level constants are defined and sane."""

    def test_pipeline_error_run_id_is_negative(self):
        assert PIPELINE_ERROR_RUN_ID == -1

    def test_pipeline_error_run_id_is_int(self):
        assert isinstance(PIPELINE_ERROR_RUN_ID, int)


class TestAutomationOutputDir:
    """_automation_output_dir returns expected paths."""

    def test_returns_string(self):
        path = _automation_output_dir(1)
        assert isinstance(path, str)
        assert "run_1" in path

    def test_includes_run_id(self):
        path = _automation_output_dir(42)
        assert "run_42" in path

    def test_uses_data_path(self):
        path = _automation_output_dir(7)
        assert "documents" in path
        assert "automation" in path


class TestFileHash:
    """_file_hash computes SHA-256 of file contents."""

    def test_returns_hash_for_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello world")
            path = f.name
        try:
            h = _file_hash(path)
            assert isinstance(h, str)
            assert len(h) == 64  # SHA-256 hex
            assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        finally:
            os.unlink(path)

    def test_returns_empty_for_missing_file(self):
        h = _file_hash("/nonexistent/file.txt")
        assert h == ""

    def test_returns_empty_for_directory(self):
        with tempfile.TemporaryDirectory() as d:
            h = _file_hash(d)
            assert h == ""


# =========================================================================
# PipelineWorker — init
# =========================================================================


class TestPipelineWorkerInit:
    """PipelineWorker creates with the current constructor."""

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_creation_with_db_and_paths(self, mock_repo, mock_init):
        worker = PipelineWorker(
            db=MagicMock(),
            input_paths=["/tmp/doc.pdf"],
            prefs=MagicMock(),
            mode="advanced",
        )
        assert worker is not None
        assert worker.input_paths == ["/tmp/doc.pdf"]
        assert worker._mode == "advanced"

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_creation_default_mode(self, mock_repo, mock_init):
        worker = PipelineWorker(MagicMock(), ["/tmp/doc.pdf"])
        assert worker._mode == "advanced"

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_creation_simple_mode(self, mock_repo, mock_init):
        worker = PipelineWorker(
            MagicMock(), ["/tmp/doc.pdf"], mode="simple",
        )
        assert worker._mode == "simple"

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_creation_stores_db(self, mock_repo, mock_init):
        db = MagicMock()
        worker = PipelineWorker(db, ["/tmp/doc.pdf"])
        assert worker.db is db

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_creation_with_pipeline_repo(self, mock_repo, mock_init):
        custom_repo = MagicMock()
        worker = PipelineWorker(
            MagicMock(), ["/tmp/doc.pdf"],
            pipeline_repo=custom_repo,
        )
        assert worker._pipeline_repo is custom_repo
        # get_pipeline_repo should NOT be called when pipeline_repo is given
        mock_repo.assert_not_called()

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_creation_with_parent(self, mock_repo, mock_init):
        parent = QObject()
        worker = PipelineWorker(
            MagicMock(), ["/tmp/doc.pdf"], parent=parent,
        )
        assert worker.parent() is parent

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_stop_event_is_threading_event(self, mock_repo, mock_init):
        worker = PipelineWorker(MagicMock(), ["/tmp/doc.pdf"])
        assert worker.stop_event is not None
        assert hasattr(worker.stop_event, "set")
        assert hasattr(worker.stop_event, "is_set")

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_initial_run_id_is_none(self, mock_repo, mock_init):
        worker = PipelineWorker(MagicMock(), ["/tmp/doc.pdf"])
        assert worker.run_id is None

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_initial_overridden_trip_id_none(self, mock_repo, mock_init):
        worker = PipelineWorker(MagicMock(), ["/tmp/doc.pdf"])
        assert worker._overridden_trip_id is None


# =========================================================================
# PipelineWorker — override_match
# =========================================================================


class TestPipelineWorkerOverrideMatch:
    """override_match sets the manual trip override."""

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_sets_overridden_trip_id(self, mock_repo, mock_init):
        worker = PipelineWorker(MagicMock(), ["/tmp/doc.pdf"])
        worker.override_match(42, {"signal1": 0.8})
        assert worker._overridden_trip_id == 42

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_sets_overridden_signals(self, mock_repo, mock_init):
        worker = PipelineWorker(MagicMock(), ["/tmp/doc.pdf"])
        signals = {"manual_selection": 1.0}
        worker.override_match(42, signals)
        assert worker._overridden_signals == signals

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_override_idempotent(self, mock_repo, mock_init):
        worker = PipelineWorker(MagicMock(), ["/tmp/doc.pdf"])
        worker.override_match(1, {})
        worker.override_match(2, {"x": 0.5})
        assert worker._overridden_trip_id == 2

    @patch("services.document_automation.pipeline.init_pipeline")
    @patch("services.document_automation.pipeline.get_pipeline_repo")
    def test_override_handles_empty_signals(self, mock_repo, mock_init):
        worker = PipelineWorker(MagicMock(), ["/tmp/doc.pdf"])
        worker.override_match(5, {})
        assert worker._overridden_trip_id == 5
        assert worker._overridden_signals == {}


# =========================================================================
# PipelineWorker — signals
# =========================================================================


class TestPipelineWorkerSignals:
    """All expected signals are defined on the class."""

    def test_stage_changed_signal_exists(self):
        assert hasattr(PipelineWorker, "stage_changed")

    def test_worker_ready_signal_exists(self):
        assert hasattr(PipelineWorker, "worker_ready")

    def test_ocr_extracted_signal_exists(self):
        assert hasattr(PipelineWorker, "ocr_extracted")

    def test_match_ready_signal_exists(self):
        assert hasattr(PipelineWorker, "match_ready")

    def test_manual_needed_signal_exists(self):
        assert hasattr(PipelineWorker, "manual_needed")

    def test_processing_done_signal_exists(self):
        assert hasattr(PipelineWorker, "processing_done")

    def test_finished_signal_exists(self):
        assert hasattr(PipelineWorker, "finished")

    def test_log_signal_exists(self):
        assert hasattr(PipelineWorker, "log")


# =========================================================================
# link_document_to_trip
# =========================================================================


class TestLinkDocumentToTrip:
    """link_document_to_trip standalone function."""

    @patch("services.document_automation.pipeline.get_run")
    @patch("services.document_automation.DocumentGrouper")
    @patch("services.document_service.DocumentService")
    def test_calls_get_run(self, mock_ds, mock_grouper, mock_get_run):
        db = MagicMock()
        mock_get_run.return_value = {"id": 1, "ocr_text": "hello"}
        mock_grouper_instance = MagicMock()
        mock_grouper_instance.group_and_link.return_value = 100
        mock_grouper.return_value = mock_grouper_instance
        mock_ds_instance = MagicMock()
        mock_ds_instance.link_to_entity.return_value.success = True
        mock_ds.return_value = mock_ds_instance

        result = link_document_to_trip(db, 1, 42)
        mock_get_run.assert_called_once_with(db, 1)
        assert result == 100

    @patch("services.document_automation.pipeline.get_run")
    def test_returns_none_when_run_not_found(self, mock_get_run):
        db = MagicMock()
        mock_get_run.return_value = None
        result = link_document_to_trip(db, 999, 42)
        assert result is None

    @patch("services.document_automation.pipeline.get_run")
    @patch("services.document_automation.DocumentGrouper")
    def test_returns_none_when_group_fails(
        self, mock_grouper, mock_get_run,
    ):
        db = MagicMock()
        mock_get_run.return_value = {"id": 1, "ocr_text": ""}
        mock_grouper_instance = MagicMock()
        mock_grouper_instance.group_and_link.return_value = None
        mock_grouper.return_value = mock_grouper_instance

        result = link_document_to_trip(db, 1, 42)
        assert result is None


# =========================================================================
# register_standalone_document
# =========================================================================


class TestRegisterStandaloneDocument:
    """register_standalone_document standalone function."""

    @patch("services.document_automation.pipeline.get_run")
    @patch("services.document_service.DocumentService")
    def test_calls_get_run(self, mock_ds, mock_get_run, tmp_path):
        db = MagicMock()
        pdf = tmp_path / "out.pdf"
        pdf.write_text("fake pdf content")
        mock_get_run.return_value = {
            "id": 1, "processed_pdf_path": str(pdf),
            "source_file_name": "in.pdf",
        }
        mock_ds_instance = MagicMock()
        mock_ds_instance.upload_legacy.return_value = 200
        mock_ds.return_value = mock_ds_instance

        result = register_standalone_document(db, 1)
        mock_get_run.assert_called_once_with(db, 1)
        assert result == 200

    @patch("services.document_automation.pipeline.get_run")
    def test_returns_none_when_run_not_found(self, mock_get_run):
        db = MagicMock()
        mock_get_run.return_value = None
        result = register_standalone_document(db, 999)
        assert result is None

    @patch("services.document_automation.pipeline.get_run")
    def test_returns_none_when_pdf_missing(self, mock_get_run):
        db = MagicMock()
        mock_get_run.return_value = {
            "id": 1, "processed_pdf_path": "/nonexistent.pdf",
            "source_file_name": "in.pdf",
        }
        result = register_standalone_document(db, 1)
        assert result is None
