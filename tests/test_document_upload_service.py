"""Tests for UploadService."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, call, patch

import pytest

from services.document.upload_service import UploadService


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def repo_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock, repo_mock):
    svc = UploadService(db_mock, repo_mock)
    svc._event_bus = MagicMock()
    return svc


def test_validate_file_not_found(service):
    valid, err = service.validate_file("/nonexistent")
    assert valid is False
    assert err == "File not found"


def test_validate_file_blocked(service):
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
        f.write(b"data")
        tmp_path = f.name
    try:
        valid, err = service.validate_file(tmp_path)
        assert valid is False
        assert "blocked" in err
    finally:
        os.unlink(tmp_path)


def test_validate_file_unsupported(service):
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"data")
        tmp_path = f.name
    try:
        valid, err = service.validate_file(tmp_path)
        assert valid is False
        assert "not supported" in err
    finally:
        os.unlink(tmp_path)


def test_validate_file_ok(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"data")
        tmp_path = f.name
    try:
        valid, err = service.validate_file(tmp_path)
        assert valid is True
        assert err is None
    finally:
        os.unlink(tmp_path)


def test_check_duplicate(service):
    service._repo.get_by_hash.return_value = {"id": 42}
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"test content")
        tmp_path = f.name
    try:
        result = service.check_duplicate(tmp_path)
        assert result == 42
    finally:
        os.unlink(tmp_path)


def test_check_duplicate_not_found(service):
    service._repo.get_by_hash.return_value = None
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"unique content")
        tmp_path = f.name
    try:
        result = service.check_duplicate(tmp_path)
        assert result is None
    finally:
        os.unlink(tmp_path)


def test_upload_file_not_found(service):
    with pytest.raises(FileNotFoundError):
        service.upload("/nonexistent.pdf")


def test_upload_blocked_extension(service):
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
        f.write(b"data")
        tmp_path = f.name
    try:
        with pytest.raises(ValueError):
            service.upload(tmp_path)
    finally:
        os.unlink(tmp_path)


def test_upload_duplicate(service):
    service._repo.get_by_hash.return_value = {"id": 42, "entity_type": "trip", "entity_id": 0}
    service._repo.add_link.return_value = 1

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"duplicate content")
        tmp_path = f.name
    try:
        result = service.upload(tmp_path, entity_type="trip", entity_id=5)
        assert result == 42
        service._event_bus.publish.assert_called()
    finally:
        os.unlink(tmp_path)


def test_upload_new(service):
    service._repo.get_by_hash.return_value = None
    service._repo.get_next_doc_number.return_value = "DOC-001"
    service._repo.create.return_value = 99
    service._repo.add_link.return_value = 1

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"new content")
        tmp_path = f.name
    try:
        result = service.upload(tmp_path, title="Test Doc", category="invoices",
                                entity_type="trip", entity_id=5, tags=["tag1"],
                                uploaded_by="user")
        assert result == 99
        service._repo.create.assert_called_once()
        service._event_bus.publish.assert_called()
    finally:
        os.unlink(tmp_path)


def test_register_existing(service):
    service._repo._fetchone.return_value = None
    service._repo.get_by_hash.return_value = None
    service._repo.get_next_doc_number.return_value = "DOC-002"
    service._repo.create.return_value = 100

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"existing content")
        tmp_path = f.name
    try:
        result = service.register_existing(tmp_path, title="Existing",
                                           category="maintenance", tags=["maint"])
        assert result == 100
    finally:
        os.unlink(tmp_path)


def test_register_existing_file_not_found(service):
    result = service.register_existing("/nonexistent.pdf")
    assert result is None


def test_batch_upload(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"test")
        tmp_path = f.name
    try:
        service.validate_file = MagicMock(return_value=(True, None))
        service.check_duplicate = MagicMock(return_value=None)
        service.upload = MagicMock(return_value=42)
        results = service.batch_upload([tmp_path], category="invoices")
        assert len(results["uploaded"]) == 1
        assert results["uploaded"][0]["id"] == 42
    finally:
        os.unlink(tmp_path)


def test_batch_upload_with_duplicates(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"test")
        tmp_path = f.name
    try:
        service.validate_file = MagicMock(return_value=(True, None))
        service.check_duplicate = MagicMock(return_value=10)
        service._repo.add_link.return_value = 1
        results = service.batch_upload([tmp_path], entity_type="trip", entity_id=5)
        assert len(results["duplicates"]) == 1
    finally:
        os.unlink(tmp_path)


def test_batch_upload_rejected(service):
    service.validate_file = MagicMock(return_value=(False, "File not found"))
    results = service.batch_upload(["/bad/path.exe"])
    assert len(results["rejected"]) == 1


def test_sanitize_filename(service):
    assert service._sanitize_filename("test file.pdf") == "test file.pdf"
    assert service._sanitize_filename("bad<>.txt") == "bad.txt"


def test_migrate_existing_attachments(service):
    service.db.rows_to_dicts.return_value = []
    assert service.migrate_existing_attachments() == 0


def test_migrate_existing_invoices(service):
    import tempfile as tf
    with patch("os.path.isdir", return_value=False):
        assert service.migrate_existing_invoices() == 0
