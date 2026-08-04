"""Tests for OcrService."""
from __future__ import annotations

import os
import queue
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from services.document.ocr_service import OcrService, MAX_PDF_SIZE_FOR_OCR


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def repo_mock():
    return MagicMock()


def test_enqueue_ocr_file_not_found(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    service._ocr_queue = queue.Queue()
    service.enqueue_ocr(1, "/nonexistent.pdf", "application/pdf")
    assert service._ocr_queue.qsize() == 0


def test_enqueue_ocr_too_large(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    service._ocr_queue = queue.Queue()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"x" * (MAX_PDF_SIZE_FOR_OCR + 1))
        tmp_path = f.name
    try:
        service.enqueue_ocr(1, tmp_path, "application/pdf")
        assert service._ocr_queue.qsize() == 0
    finally:
        os.unlink(tmp_path)


def test_enqueue_ocr_success(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    service._ocr_queue = queue.Queue()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"small file")
        tmp_path = f.name
    try:
        service.enqueue_ocr(1, tmp_path, "application/pdf")
        assert service._ocr_queue.qsize() == 1
        item = service._ocr_queue.get_nowait()
        assert item[0] == 1
        assert item[1] == tmp_path
    finally:
        os.unlink(tmp_path)


def test_extract_text_not_found(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    result = service.extract_text("/nonexistent.pdf", "application/pdf")
    assert result == ""


def test_extract_pdf_text(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 fake pdf content")
        tmp_path = f.name
    try:
        # pypdf will fail on garbage, so we should get empty string
        result = service._extract_pdf_text(tmp_path)
        assert result == ""
    finally:
        os.unlink(tmp_path)


def test_extract_image_text(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"not a real image")
        tmp_path = f.name
    try:
        result = service._extract_image_text(tmp_path)
        assert result == ""
    finally:
        os.unlink(tmp_path)


@patch("services.document.ocr_service.OcrService.retry_pending_ocr")
def test_retry_pending_on_startup(mock_retry, db_mock, repo_mock):
    _ = OcrService(db_mock, repo_mock)
    mock_retry.assert_called_once()


def test_retry_pending_ocr(repo_mock):
    ocr_queue = queue.Queue()
    repo_mock._fetchall.return_value = [
        {"id": 1, "file_path": "/tmp/test.pdf", "mime_type": "application/pdf"},
    ]
    with patch("os.path.isfile", return_value=True), \
         patch("os.path.getsize", return_value=1000):
        count = OcrService.retry_pending_ocr(repo_mock, ocr_queue, max_docs=50)
        assert count == 1
        assert ocr_queue.qsize() == 1


def test_retry_pending_ocr_skips_deleted(repo_mock):
    ocr_queue = queue.Queue()
    repo_mock._fetchall.return_value = [
        {"id": 1, "file_path": "/tmp/deleted.pdf", "mime_type": "application/pdf"},
    ]
    with patch("os.path.isfile", return_value=False):
        count = OcrService.retry_pending_ocr(repo_mock, ocr_queue, max_docs=50)
        assert count == 0


def test_shutdown(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    service._ocr_workers = [MagicMock()]
    service.shutdown()
    assert service._ocr_running is False
    assert service._ocr_workers == []


@patch("services.document_automation.document_grouper.DocumentGrouper")
@patch("services.document_automation.trip_matcher.TripMatcher")
def test_match_and_link_after_ocr(mock_matcher, mock_grouper, db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    mock_matcher_instance = MagicMock()
    mock_matcher.return_value = mock_matcher_instance
    mock_match = MagicMock()
    mock_match.best_match = {"id": 42}
    mock_match.confidence = 90
    mock_matcher_instance.match.return_value = mock_match
    mock_matcher_instance.auto_link_threshold = 80

    mock_grouper_instance = MagicMock()
    mock_grouper.return_value = mock_grouper_instance
    mock_grouper_instance.link_existing_document_to_trip.return_value = True

    service._match_and_link_after_ocr(1, {"extracted": {"cmr_number": "123"},
                                           "ocr_text": "text"})

    mock_grouper_instance.link_existing_document_to_trip.assert_called_once_with(
        doc_id=1, trip_id=42, extracted={"cmr_number": "123"}, ocr_text="text",
    )


@patch("services.document_automation.document_grouper.DocumentGrouper")
@patch("services.document_automation.trip_matcher.TripMatcher")
def test_match_and_link_low_confidence(mock_matcher, mock_grouper, db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    mock_matcher_instance = MagicMock()
    mock_matcher.return_value = mock_matcher_instance
    mock_match = MagicMock()
    mock_match.best_match = {"id": 42}
    mock_match.confidence = 50
    mock_matcher_instance.match.return_value = mock_match
    mock_matcher_instance.auto_link_threshold = 80

    service._match_and_link_after_ocr(1, {"extracted": {}, "ocr_text": ""})
    mock_grouper_instance = mock_grouper.return_value
    mock_grouper_instance.link_existing_document_to_trip.assert_not_called()


def test_enqueue_ocr_for_image(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    service._ocr_queue = queue.Queue()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"fake image")
        tmp_path = f.name
    try:
        service.enqueue_ocr(2, tmp_path, "image/png")
        assert service._ocr_queue.qsize() == 1
    finally:
        os.unlink(tmp_path)


def test_extract_text_unsupported_mime(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"plain text")
        tmp_path = f.name
    try:
        result = service.extract_text(tmp_path, "text/plain")
        assert result == ""
    finally:
        os.unlink(tmp_path)


def test_extract_text_file_not_found(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    result = service.extract_text("/nonexistent/file.pdf", "application/pdf")
    assert result == ""


def test_extract_pdf_text_with_mock_pypdf2(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj")
        tmp_path = f.name
    try:
        with patch("pypdf.PdfReader") as mock_reader:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Hello from PDF"
            mock_instance = MagicMock()
            mock_instance.pages = [mock_page]
            mock_reader.return_value = mock_instance
            result = service._extract_pdf_text(tmp_path)
            assert result == "Hello from PDF"
    finally:
        os.unlink(tmp_path)


def test_extract_image_text_with_mock_tesseract(db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"fake image bytes")
        tmp_path = f.name
    try:
        # Mock pytesseract at sys.modules level and inject a fake module
        import sys
        fake_tesseract = MagicMock()
        fake_tesseract.image_to_string.return_value = "Extracted image text"
        with patch("PIL.Image.open") as mock_img_open, \
             patch.dict("sys.modules", {"pytesseract": fake_tesseract}):
            mock_img = MagicMock()
            mock_img_open.return_value.__enter__.return_value = mock_img
            result = service._extract_image_text(tmp_path)
            assert result == "Extracted image text"
            fake_tesseract.image_to_string.assert_called_once_with(mock_img)
    finally:
        os.unlink(tmp_path)


def test_extract_image_text_truncates_long_text(db_mock, repo_mock):
    """_extract_image_text truncates at MAX_OCR_TEXT_LENGTH."""
    service = OcrService(db_mock, repo_mock)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"fake image")
        tmp_path = f.name
    try:
        import sys
        fake_tesseract = MagicMock()
        with patch("PIL.Image.open") as mock_open, \
             patch.dict("sys.modules", {"pytesseract": fake_tesseract}):
            mock_img = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_img
            long_text = "x" * 10000
            fake_tesseract.image_to_string.return_value = long_text
            from services.document.ocr_service import MAX_OCR_TEXT_LENGTH
            result = service._extract_image_text(tmp_path)
            assert len(result) == MAX_OCR_TEXT_LENGTH
            assert result == "x" * MAX_OCR_TEXT_LENGTH
    finally:
        os.unlink(tmp_path)


@patch("services.document_automation.document_grouper.DocumentGrouper")
@patch("services.document_automation.trip_matcher.TripMatcher")
def test_match_and_link_after_ocr_no_extracted(mock_matcher, mock_grouper, db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    # No extracted data
    service._match_and_link_after_ocr(1, {"extracted": {}, "ocr_text": ""})
    mock_matcher.return_value.match.assert_not_called()
    mock_grouper.return_value.link_existing_document_to_trip.assert_not_called()


@patch("services.document_automation.document_grouper.DocumentGrouper")
@patch("services.document_automation.trip_matcher.TripMatcher")
def test_match_and_link_no_best_match(mock_matcher, mock_grouper, db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    mock_matcher_instance = MagicMock()
    mock_matcher.return_value = mock_matcher_instance
    mock_match = MagicMock()
    mock_match.best_match = None
    mock_match.confidence = 0
    mock_matcher_instance.match.return_value = mock_match
    mock_matcher_instance.auto_link_threshold = 80

    service._match_and_link_after_ocr(1, {"extracted": {"cmr_number": "123"}, "ocr_text": "text"})
    mock_grouper.return_value.link_existing_document_to_trip.assert_not_called()


@patch("repositories.pipeline_repository.PipelineRepository")
def test_retroactively_link_related_runs(mock_pipeline_repo, db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    mock_pipeline_instance = MagicMock()
    mock_pipeline_repo.return_value = mock_pipeline_instance
    mock_pipeline_instance.get_runs_by_trip_id.return_value = [
        {"id": 10}, {"id": 11},
    ]

    service._retroactively_link_related_runs(42, 100)
    mock_pipeline_repo.assert_called_once()
    mock_pipeline_instance.get_runs_by_trip_id.assert_called_once_with(42)
    assert mock_pipeline_instance.append_related_document.call_count == 2


@patch("repositories.pipeline_repository.PipelineRepository")
def test_retroactively_link_no_runs(mock_pipeline_repo, db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    mock_pipeline_instance = MagicMock()
    mock_pipeline_repo.return_value = mock_pipeline_instance
    mock_pipeline_instance.get_runs_by_trip_id.return_value = []

    service._retroactively_link_related_runs(42, 100)
    mock_pipeline_instance.append_related_document.assert_not_called()


def test_retry_pending_ocr_skips_large_files(repo_mock):
    ocr_queue = queue.Queue()
    repo_mock._fetchall.return_value = [
        {"id": 1, "file_path": "/tmp/large.pdf", "mime_type": "application/pdf"},
    ]
    with patch("os.path.isfile", return_value=True), \
         patch("os.path.getsize", return_value=100 * 1024 * 1024):  # 100MB > MAX_PDF_SIZE_FOR_OCR
        count = OcrService.retry_pending_ocr(repo_mock, ocr_queue, max_docs=50)
        assert count == 0
        assert ocr_queue.qsize() == 0


def test_retry_pending_ocr_queue_full(repo_mock):
    """When queue is full, retry stops early."""
    ocr_queue = queue.Queue(maxsize=1)
    repo_mock._fetchall.return_value = [
        {"id": 1, "file_path": "/tmp/doc1.pdf", "mime_type": "application/pdf"},
        {"id": 2, "file_path": "/tmp/doc2.pdf", "mime_type": "application/pdf"},
    ]
    with patch("os.path.isfile", return_value=True), \
         patch("os.path.getsize", return_value=1000):
        # First enqueue succeeds, second should raise queue.Full
        count = OcrService.retry_pending_ocr(repo_mock, ocr_queue, max_docs=50)
        assert count == 1
        assert ocr_queue.qsize() == 1


@patch("services.document.ocr_service.OcrService._start_ocr_workers")
def test_shutdown_multiple_workers(mock_start, db_mock, repo_mock):
    service = OcrService(db_mock, repo_mock)
    service._ocr_workers = [MagicMock(), MagicMock()]
    service.shutdown()
    assert service._ocr_running is False
    assert service._ocr_workers == []
    for t in service._ocr_workers:
        t.join.assert_not_called()  # already cleared


def test_retry_pending_ocr_query_failure(repo_mock):
    """If the query itself fails, retry_pending_ocr returns 0."""
    ocr_queue = queue.Queue()
    repo_mock._fetchall.side_effect = Exception("DB Error")
    count = OcrService.retry_pending_ocr(repo_mock, ocr_queue, max_docs=50)
    assert count == 0


def test_enqueue_ocr_queue_full(db_mock, repo_mock):
    """When queue is full, enqueue_ocr should not block."""
    service = OcrService(db_mock, repo_mock)
    # Set up a full queue
    service._ocr_queue = queue.Queue(maxsize=0)  # maxsize=0 means infinite, let me use maxsize=1 and fill it
    
    # Actually let's use a full queue
    q = queue.Queue(maxsize=1)
    q.put_nowait((0, "", ""))  # Fill it
    service._ocr_queue = q
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"test")
        tmp_path = f.name
    try:
        service.enqueue_ocr(1, tmp_path, "application/pdf")
        # Should not raise, just log and skip
        assert service._ocr_queue.qsize() == 1  # Still just the filler
    finally:
        os.unlink(tmp_path)
