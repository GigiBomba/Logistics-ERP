"""Tests for document_automation pipeline module."""
from unittest.mock import MagicMock, call, patch

import pytest

from services.document_automation.pipeline import run_for_existing_document, _temp_dir


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.conn = MagicMock()
    return db


class TestRunForExistingDocument:
    @patch("repositories.document_repository.DocumentRepository")
    @patch("services.document_automation.image_processor.ImageProcessor")
    @patch("services.document_automation.ocr_extractor.OcrExtractor")
    @patch("services.document_automation.pipeline.os.path.isfile", return_value=True)
    @patch("services.document_automation.pipeline.os.makedirs")
    @patch("services.document_automation.pipeline.shutil.rmtree")
    def test_run_for_existing_document_success(
        self, mock_rmtree, mock_makedirs, mock_isfile,
        mock_ocr_cls, mock_processor_cls, mock_repo_cls, mock_db,
    ):
        # Mock document retrieval
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "id": 42, "file_path": "/docs/test.pdf",
            "file_name": "test.pdf", "mime_type": "application/pdf",
        }
        mock_repo_cls.return_value = mock_repo

        # Mock image processor
        mock_processor = MagicMock()
        mock_processor.process.return_value = MagicMock(
            pdf_path="/tmp/output/final.pdf",
        )
        mock_processor_cls.return_value = mock_processor

        # Mock OCR extractor
        mock_ocr = MagicMock()
        mock_ocr.extract.return_value = MagicMock(
            full_text="OCR text result",
            extracted={"cmr_number": "CMR001"},
            confidence=85.0,
            engine="paddle",
            pages_processed=1,
        )
        mock_ocr_cls.return_value = mock_ocr

        result = run_for_existing_document(mock_db, 42)

        assert result["ocr_text"] == "OCR text result"
        assert result["extracted"]["cmr_number"] == "CMR001"
        assert result["engine"] == "paddle"
        assert result["confidence"] == 85.0

        mock_processor.process.assert_called_once()
        mock_ocr.extract.assert_called_once()
        mock_repo.update.assert_called_once()

    @patch("repositories.document_repository.DocumentRepository")
    @patch("services.document_automation.pipeline.os.path.isfile", return_value=False)
    def test_run_missing_file_raises(self, mock_isfile, mock_repo_cls, mock_db):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {"id": 42, "file_path": "/docs/missing.pdf"}
        mock_repo_cls.return_value = mock_repo

        with pytest.raises(FileNotFoundError):
            run_for_existing_document(mock_db, 42)

    @patch("repositories.document_repository.DocumentRepository")
    def test_run_missing_doc_raises(self, mock_repo_cls, mock_db):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_repo_cls.return_value = mock_repo

        with pytest.raises(ValueError, match="not found"):
            run_for_existing_document(mock_db, 42)

    @patch("repositories.document_repository.DocumentRepository")
    @patch("services.document_automation.image_processor.ImageProcessor")
    @patch("services.document_automation.ocr_extractor.OcrExtractor")
    @patch("services.document_automation.pipeline.os.path.isfile", return_value=True)
    @patch("services.document_automation.pipeline.os.makedirs")
    @patch("services.document_automation.pipeline.shutil.rmtree")
    def test_run_with_progress_callback(
        self, mock_rmtree, mock_makedirs, mock_isfile,
        mock_ocr_cls, mock_processor_cls, mock_repo_cls, mock_db,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "id": 42, "file_path": "/docs/test.pdf",
        }
        mock_repo_cls.return_value = mock_repo

        mock_processor = MagicMock()
        mock_processor.process.return_value = MagicMock(pdf_path="/tmp/out.pdf")
        mock_processor_cls.return_value = mock_processor

        mock_ocr = MagicMock()
        mock_ocr.extract.return_value = MagicMock(
            full_text="text", extracted={},
            confidence=0.0, engine="paddle", pages_processed=0,
        )
        mock_ocr_cls.return_value = mock_ocr

        progress_cb = MagicMock()
        run_for_existing_document(mock_db, 42, progress_callback=progress_cb)

        assert progress_cb.call_count >= 3  # processing, ocr, persisting, complete

    @patch("repositories.document_repository.DocumentRepository")
    @patch("services.document_automation.image_processor.ImageProcessor")
    @patch("services.document_automation.ocr_extractor.OcrExtractor")
    @patch("services.document_automation.pipeline.os.path.isfile", return_value=True)
    @patch("services.document_automation.pipeline.os.makedirs")
    @patch("services.document_automation.pipeline.shutil.rmtree")
    def test_run_with_stop_event(
        self, mock_rmtree, mock_makedirs, mock_isfile,
        mock_ocr_cls, mock_processor_cls, mock_repo_cls, mock_db,
    ):
        import threading

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "id": 42, "file_path": "/docs/test.pdf",
        }
        mock_repo_cls.return_value = mock_repo

        mock_processor = MagicMock()
        mock_processor.process.return_value = MagicMock(pdf_path="/tmp/out.pdf")
        mock_processor_cls.return_value = mock_processor

        mock_ocr = MagicMock()
        mock_ocr.extract.return_value = MagicMock(
            full_text="text", extracted={},
            confidence=0.0, engine="paddle", pages_processed=0,
        )
        mock_ocr_cls.return_value = mock_ocr

        stop_event = threading.Event()
        result = run_for_existing_document(mock_db, 42, stop_event=stop_event)
        assert result is not None

    @patch("repositories.document_repository.DocumentRepository")
    @patch("services.document_automation.image_processor.ImageProcessor")
    @patch("services.document_automation.ocr_extractor.OcrExtractor")
    @patch("services.document_automation.pipeline.os.path.isfile", return_value=True)
    @patch("services.document_automation.pipeline.os.makedirs")
    @patch("services.document_automation.pipeline.shutil.rmtree")
    def test_run_ai_init_called(
        self, mock_rmtree, mock_makedirs, mock_isfile,
        mock_ocr_cls, mock_processor_cls, mock_repo_cls, mock_db,
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "id": 42, "file_path": "/docs/test.pdf",
        }
        mock_repo_cls.return_value = mock_repo

        mock_processor = MagicMock()
        mock_processor.process.return_value = MagicMock(pdf_path="/tmp/out.pdf")
        mock_processor_cls.return_value = mock_processor

        mock_ocr = MagicMock()
        mock_ocr.extract.return_value = MagicMock(
            full_text="text", extracted={},
            confidence=0.0, engine="paddle", pages_processed=0,
        )
        mock_ocr_cls.return_value = mock_ocr

        with patch("services.document_automation.ai_fallback.init_from_db") as mock_ai_init:
            run_for_existing_document(mock_db, 42)
            mock_ai_init.assert_called_once_with(mock_db)


class TestTempDir:
    @patch("utils.resource_path.data_path")
    def test_temp_dir(self, mock_data_path):
        mock_data_path.return_value = "/data/documents/automation/on_demand_job123"
        result = _temp_dir("job123")
        assert result == "/data/documents/automation/on_demand_job123"
