"""Tests for VersioningService."""
import os
import tempfile
from unittest.mock import MagicMock, call, patch

import pytest

from services.document.versioning_service import VersioningService, MAX_VERSIONS_PER_DOC


@pytest.fixture
def repo_mock():
    return MagicMock()


@pytest.fixture
def service(repo_mock):
    return VersioningService(repo_mock)


def test_get_versions(service):
    service._repo.get_versions.return_value = [{"version_number": 1}]
    result = service.get_versions(1)
    assert result == [{"version_number": 1}]


def test_upload_new_version_doc_not_found(service):
    service._repo.get_by_id.return_value = None
    result = service.upload_new_version(999, "/tmp/test.pdf")
    assert result is None


def test_upload_new_version(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"test content")
        tmp_path = f.name

    try:
        service._repo.get_by_id.return_value = {"id": 1, "title": "Test"}
        service._repo.get_version_count.return_value = 0
        service._repo.get_versions.return_value = []
        service._repo.add_version.return_value = 1

        result = service.upload_new_version(1, tmp_path, comment="v1", uploaded_by="user")
        assert result == 1
        service._repo.add_version.assert_called_once()
        service._repo.update.assert_called_once()
        # Check that file was copied
        assert service._repo.update.call_args[1].get("file_path") is not None
    finally:
        os.unlink(tmp_path)


def test_upload_new_version_invalid_extension(service):
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
        f.write(b"bad")
        tmp_path = f.name
    try:
        service._repo.get_by_id.return_value = {"id": 1}
        with pytest.raises(ValueError):
            service.upload_new_version(1, tmp_path)
    finally:
        os.unlink(tmp_path)


def test_upload_new_version_file_not_found(service):
    service._repo.get_by_id.return_value = {"id": 1}
    with pytest.raises(FileNotFoundError):
        service.upload_new_version(1, "/nonexistent/file.pdf")


def test_restore_version(service):
    service._repo.get_versions.return_value = [
        {"version_number": 1, "file_path": "/tmp/v1.pdf", "file_size": 100, "file_hash": "abc"},
    ]
    with patch("os.path.isfile", return_value=True):
        result = service.restore_version(1, 1)
        assert result is True
        service._repo.update.assert_called_once()


def test_restore_version_not_found(service):
    service._repo.get_versions.return_value = []
    result = service.restore_version(1, 99)
    assert result is False


def test_validate_file_not_found(service):
    with pytest.raises(FileNotFoundError):
        service._validate_file("/nonexistent")


def test_validate_blocked_extension(service):
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
        f.write(b"data")
        tmp_path = f.name
    try:
        with pytest.raises(ValueError):
            service._validate_file(tmp_path)
    finally:
        os.unlink(tmp_path)


def test_validate_unsupported_extension(service):
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"data")
        tmp_path = f.name
    try:
        with pytest.raises(ValueError):
            service._validate_file(tmp_path)
    finally:
        os.unlink(tmp_path)


def test_validate_file_too_large(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"x" * (20 * 1024 * 1024 + 1))
        tmp_path = f.name
    try:
        with pytest.raises(ValueError):
            service._validate_file(tmp_path)
    finally:
        os.unlink(tmp_path)


def test_sanitize_filename(service):
    assert service._sanitize_filename("hello world.pdf") == "hello world.pdf"
    assert service._sanitize_filename("bad<file>.PDF") == "badfile.pdf"
    # .gitignore → rsplit('.', 1) gives ['', 'gitignore'], base='', ext='gitignore' → ".gitignore"
    assert service._sanitize_filename(".gitignore") == ".gitignore"


def test_unique_path(service):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create first file
        p1 = service._unique_path(tmpdir, "test.pdf")
        open(p1, "w").close()
        # Second should be different
        p2 = service._unique_path(tmpdir, "test.pdf")
        assert p1 != p2
        assert "_1" in p2
