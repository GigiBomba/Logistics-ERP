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


def test_upload_file_too_large(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"x" * (20 * 1024 * 1024 + 1))
        tmp_path = f.name
    try:
        with pytest.raises(ValueError, match="too large"):
            service.upload(tmp_path)
    finally:
        os.unlink(tmp_path)


def test_upload_auto_category_from_entity(service):
    service._repo.get_by_hash.return_value = None
    service._repo.get_next_doc_number.return_value = "DOC-003"
    service._repo.create.return_value = 101

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"auto category test")
        tmp_path = f.name
    try:
        result = service.upload(tmp_path, entity_type="truck", entity_id=10)
        assert result == 101
        # Category should be auto-detected from entity_type "truck" -> "vehicles"
        call_kwargs = service._repo.create.call_args[1]
        assert call_kwargs["category"] == "vehicles"
    finally:
        os.unlink(tmp_path)


def test_upload_uses_filename_as_title_when_empty(service):
    service._repo.get_by_hash.return_value = None
    service._repo.get_next_doc_number.return_value = "DOC-004"
    service._repo.create.return_value = 102

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"title test")
        tmp_path = f.name
        fname = os.path.basename(tmp_path)
    try:
        result = service.upload(tmp_path)
        assert result == 102
        call_kwargs = service._repo.create.call_args[1]
        assert call_kwargs["title"] == os.path.splitext(fname)[0]
    finally:
        os.unlink(tmp_path)


def test_upload_creates_link_for_entity(service):
    service._repo.get_by_hash.return_value = None
    service._repo.get_next_doc_number.return_value = "DOC-005"
    service._repo.create.return_value = 103
    service._repo.add_link.return_value = 1

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"link test")
        tmp_path = f.name
    try:
        result = service.upload(tmp_path, entity_type="trip", entity_id=99)
        assert result == 103
        service._repo.add_link.assert_called()
    finally:
        os.unlink(tmp_path)


def test_check_duplicate_invalid_file(service):
    with pytest.raises(FileNotFoundError):
        service.check_duplicate("/nonexistent/file.pdf")


def test_register_existing_is_migration_skips_duplicate(service):
    service._repo._fetchone.side_effect = [
        {"cnt": 1},  # existing_count query returns > 0
    ]
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"migration dup")
        tmp_path = f.name
    try:
        result = service.register_existing(tmp_path, category="invoices", is_migration=True)
        # Should skip because we already have a doc with same file_name + category
        assert result is None
    finally:
        os.unlink(tmp_path)


def test_register_existing_returns_zero_for_migration_when_path_exists(service):
    service._repo._fetchone.side_effect = [
        {"cnt": 0},           # no duplicate by name+category
        {"id": 5},            # existing by path
    ]
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"existing path")
        tmp_path = f.name
    try:
        result = service.register_existing(tmp_path, is_migration=True)
        # is_migration returns 0 for existing
        assert result == 0
    finally:
        os.unlink(tmp_path)


def test_batch_upload_mixed_results(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"valid1")
        good_path = f.name
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
        f.write(b"bad")
        bad_path = f.name
    try:
        service.validate_file = MagicMock()
        service.validate_file.side_effect = [
            (True, None),       # good file passes validation
            (False, "blocked"),  # bad file rejected
        ]
        service.check_duplicate = MagicMock(return_value=None)
        service.upload = MagicMock(return_value=200)

        results = service.batch_upload([good_path, bad_path])
        assert len(results["uploaded"]) == 1
        assert len(results["rejected"]) == 1
        assert results["uploaded"][0]["id"] == 200
    finally:
        os.unlink(good_path)
        os.unlink(bad_path)


def test_batch_upload_handles_exception(service):
    service.validate_file = MagicMock(side_effect=Exception("Unexpected error"))
    results = service.batch_upload(["/some/path.pdf"])
    assert len(results["failed"]) == 1
    assert "Unexpected error" in results["failed"][0]["reason"]


def test_sanitize_filename_edge_cases(service):
    assert service._sanitize_filename("") == "unnamed_file"
    assert service._sanitize_filename("...") == "unnamed_file"
    assert service._sanitize_filename("file") == "file"
    assert service._sanitize_filename("hello.world.txt") == "helloworld.txt"  # dots stripped in base
    assert service._sanitize_filename("  spaced  .PDF") == "spaced.pdf"  # leading/trailing spaces stripped
    assert service._sanitize_filename("no_extension") == "no_extension"


def test_ensure_category_dir_creates(service):
    import tempfile as tf
    with tf.TemporaryDirectory() as tmpdir:
        with patch("services.document.upload_service.DOCUMENTS_ROOT", tmpdir):
            path = service._ensure_category_dir("test_cat")
            assert os.path.isdir(path)
            assert path.endswith("test_cat")


def test_unique_path_no_collision(service):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = service._unique_path(tmpdir, "new_file.pdf")
        assert path.endswith("new_file.pdf")


def test_migrate_all_combines_both(service):
    with patch.object(service, "migrate_existing_attachments", return_value=3), \
         patch.object(service, "migrate_existing_invoices", return_value=2):
        assert service.migrate_all() == 5


def test_compute_sha256(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"hash test content")
        tmp_path = f.name
    try:
        h = service._compute_sha256(tmp_path)
        assert isinstance(h, str)
        assert len(h) == 64
    finally:
        os.unlink(tmp_path)


def test_upload_duplicate_returns_existing_id(service):
    service._repo.get_by_hash.return_value = {"id": 42, "entity_type": "trip", "entity_id": 0}
    service._repo.add_link.return_value = 1

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"duplicate content for return test")
        tmp_path = f.name
    try:
        result = service.upload(tmp_path)
        assert result == 42
        service._event_bus.publish.assert_called()
    finally:
        os.unlink(tmp_path)


def test_register_existing_with_link(service):
    service._repo._fetchone.return_value = None  # no existing by path
    service._repo.get_by_hash.return_value = None
    service._repo.get_next_doc_number.return_value = "DOC-010"
    service._repo.create.return_value = 110

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"link registration test")
        tmp_path = f.name
    try:
        result = service.register_existing(
            tmp_path, title="Linked", category="maintenance",
            entity_type="maintenance_record", entity_id=42,
        )
        assert result == 110
        # Should have created a link
        service._repo.add_link.assert_called()
    finally:
        os.unlink(tmp_path)


def test_register_existing_no_file(service):
    result = service.register_existing("/nonexistent/path.pdf")
    assert result is None
