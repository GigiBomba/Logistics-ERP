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
        # PyPDF2 will fail on garbage, so we should get empty string
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
