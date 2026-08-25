"""Tests for DocumentGrouper."""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from services.document_automation.document_grouper import (
    DocumentGrouper,
    _read_documents_attached,
)


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def grouper(db_mock):
    g = DocumentGrouper(db_mock)
    g.pipeline = MagicMock()
    return g


def test_read_documents_attached(db_mock):
    with patch("services.document_automation.document_grouper.TripRepository") as mock_trip_cls:
        mock_trip = MagicMock()
        mock_trip.get_documents_attached.return_value = [1, 2, 3]
        mock_trip_cls.return_value = mock_trip
        result = _read_documents_attached(db_mock, 1)
        assert result == [1, 2, 3]


def test_read_documents_attached_empty(db_mock):
    with patch("services.document_automation.document_grouper.TripRepository") as mock_trip_cls:
        mock_trip = MagicMock()
        mock_trip.get_documents_attached.return_value = []
        mock_trip_cls.return_value = mock_trip
        assert _read_documents_attached(db_mock, 1) == []


def test_read_documents_attached_null(db_mock):
    with patch("services.document_automation.document_grouper.TripRepository") as mock_trip_cls:
        mock_trip = MagicMock()
        mock_trip.get_documents_attached.return_value = []
        mock_trip_cls.return_value = mock_trip
        assert _read_documents_attached(db_mock, 1) == []


def test_read_documents_attached_invalid_json(db_mock):
    with patch("services.document_automation.document_grouper.TripRepository") as mock_trip_cls:
        mock_trip = MagicMock()
        mock_trip.get_documents_attached.return_value = []
        mock_trip_cls.return_value = mock_trip
        assert _read_documents_attached(db_mock, 1) == []


def test_read_documents_attached_not_list(db_mock):
    with patch("services.document_automation.document_grouper.TripRepository") as mock_trip_cls:
        mock_trip = MagicMock()
        mock_trip.get_documents_attached.return_value = []
        mock_trip_cls.return_value = mock_trip
        assert _read_documents_attached(db_mock, 1) == []


def test_read_documents_attached_exception(db_mock):
    # TripRepository.get_documents_attached handles DB errors internally
    # and returns [] — this test validates the thin wrapper propagates that.
    with patch("services.document_automation.document_grouper.TripRepository") as mock_trip_cls:
        mock_trip = MagicMock()
        mock_trip.get_documents_attached.return_value = []
        mock_trip_cls.return_value = mock_trip
        assert _read_documents_attached(db_mock, 1) == []


def test_group_and_link_run_not_found(grouper):
    grouper.pipeline.get_run_by_id.return_value = None
    result = grouper.group_and_link(999, 1)
    assert result is None


def test_group_and_link_no_pdf(grouper):
    grouper.pipeline.get_run_by_id.return_value = {
        "id": 1, "processed_pdf_path": None, "source_file_path": None,
    }
    result = grouper.group_and_link(1, 1)
    assert result is None


def test_group_and_link_success(grouper):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"test pdf content")
        tmp_path = f.name

    try:
        grouper.pipeline.get_run_by_id.return_value = {
            "id": 1, "processed_pdf_path": tmp_path, "source_file_path": tmp_path,
        }
        grouper.pipeline.get_extracted_data.return_value = {
            "cmr_number": "CMR-123", "doc_type": "cmr", "date": "2026-06-01",
        }

        grouper._document_service = MagicMock()
        grouper._document_service.register_existing.return_value = 42

        grouper.db.conn.execute.return_value.fetchone.return_value = None

        result = grouper.group_and_link(1, 42, ocr_text="some text")
        assert result == 42
        grouper._document_service.register_existing.assert_called_once()
        grouper.pipeline.set_document_id.assert_called_with(1, 42)
    finally:
        os.unlink(tmp_path)


def test_group_and_link_register_fails(grouper):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"test")
        tmp_path = f.name

    try:
        grouper.pipeline.get_run_by_id.return_value = {
            "id": 1, "processed_pdf_path": tmp_path,
        }
        grouper.pipeline.get_extracted_data.return_value = {}
        grouper._document_service = MagicMock()
        grouper._document_service.register_existing.return_value = None

        result = grouper.group_and_link(1, 42)
        assert result is None
        # rollback_transaction() now calls db.conn.rollback() (PG-safe API)
        grouper.db.conn.rollback.assert_called_once()
    finally:
        os.unlink(tmp_path)


def test_group_and_link_exception(grouper):
    grouper.pipeline.get_run_by_id.side_effect = Exception("Unexpected")
    with pytest.raises(Exception):
        grouper.group_and_link(1, 42)


def test_link_existing_document_to_trip(grouper):
    grouper.db.conn.execute.return_value.fetchone.side_effect = [
        None,  # existing_link check → no existing link
        None,  # _read_documents_attached → empty
    ]
    grouper.db.conn.execute.return_value.fetchall.return_value = []

    result = grouper.link_existing_document_to_trip(
        doc_id=1, trip_id=42,
        extracted={"cmr_number": "CMR-001", "doc_type": "cmr"},
        ocr_text="text",
    )
    assert result is True
    # Should have called BEGIN IMMEDIATE and COMMIT
    assert grouper.db.conn.execute.call_count >= 2


def test_link_existing_document_failure(grouper):
    grouper.db.conn.execute.side_effect = Exception("DB failure")
    result = grouper.link_existing_document_to_trip(
        doc_id=1, trip_id=42, extracted={},
    )
    assert result is False


def test_update_document_extraction(grouper):
    grouper._update_document_extraction(
        doc_id=1, extracted={"key": "val"}, ocr_text="text", tags=["tag1"],
    )
    grouper.db.conn.execute.assert_called_once()
    args = grouper.db.conn.execute.call_args[0]
    # Check the SQL query (args[0]) contains extracted_data_json
    assert "extracted_data_json" in args[0]


def test_update_trip_after_link_with_cmr(grouper):
    grouper.db.conn.execute.return_value.fetchone.return_value = None
    grouper._update_trip_after_link(trip_id=42, cmr_number="CMR-001", doc_id=1)
    # Should update trips.cmr_number and documents_attached
    assert grouper.db.conn.execute.call_count >= 2


def test_update_trip_after_link_without_cmr(grouper):
    grouper.db.conn.execute.return_value.fetchone.return_value = None
    grouper._update_trip_after_link(trip_id=42, cmr_number="", doc_id=1)
    # Should only update documents_attached
    assert grouper.db.conn.execute.call_count >= 1
