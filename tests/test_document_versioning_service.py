"""Tests for VersioningService."""
from __future__ import annotations

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


def test_get_versions_empty(service):
    service._repo.get_versions.return_value = []
    assert service.get_versions(999) == []


def test_get_versions_multiple(service):
    service._repo.get_versions.return_value = [
        {"version_number": 1},
        {"version_number": 2},
    ]
    result = service.get_versions(1)
    assert len(result) == 2
    assert result[1]["version_number"] == 2


def test_upload_new_version_enforces_max_versions(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"new version content")
        tmp_path = f.name
    try:
        service._repo.get_by_id.return_value = {"id": 1, "title": "Test"}
        service._repo.get_version_count.return_value = 20
        # Return 20 existing versions for first call, then 19 after "delete"
        versions_20 = [
            {"id": v, "version_number": v, "file_path": f"/tmp/v{v}.pdf"}
            for v in range(1, 21)
        ]
        versions_19 = versions_20[1:]  # remove first (oldest)
        service._repo.get_versions.side_effect = [versions_20, versions_19]
        service._repo.add_version.return_value = 1

        with patch("os.path.isfile", return_value=True), \
             patch("os.remove") as mock_rm:
            result = service.upload_new_version(1, tmp_path, comment="v21")
            assert result is not None
            mock_rm.assert_called_once()
            service._repo._execute.assert_called()
    finally:
        os.unlink(tmp_path)


def test_upload_new_version_purges_multiple_oldest_when_over_limit(service):
    """When more than MAX_VERSIONS_PER_DOC exist, purge until under limit."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"overflow test")
        tmp_path = f.name
    try:
        service._repo.get_by_id.return_value = {"id": 1, "title": "Test"}
        service._repo.get_version_count.return_value = 22
        # Return 22 versions then 19 after purging 3
        versions_22 = [
            {"id": v, "version_number": v, "file_path": f"/tmp/v{v}.pdf"}
            for v in range(1, 23)
        ]
        # Need to get_versions called until < 20: 22->19 (remove 3)
        service._repo.get_versions.side_effect = [
            versions_22,      # first check: 22 >= 20, remove first
            versions_22[1:],  # 21 >= 20, remove second
            versions_22[2:],  # 20 >= 20, remove third
            versions_22[3:],  # 19 < 20, done
        ]
        service._repo.add_version.return_value = 1

        with patch("os.path.isfile", return_value=True), \
             patch("os.remove") as mock_rm:
            result = service.upload_new_version(1, tmp_path, comment="v23")
            assert result is not None
            assert mock_rm.call_count == 3
    finally:
        os.unlink(tmp_path)


def test_restore_version_not_found_on_disk(service):
    service._repo.get_versions.return_value = [
        {"version_number": 2, "file_path": "/tmp/deleted.pdf", "file_size": 100, "file_hash": "abc"},
    ]
    with patch("os.path.isfile", return_value=False):
        result = service.restore_version(1, 2)
        assert result is False
        service._repo.update.assert_not_called()


def test_restore_version_updates_document(service):
    service._repo.get_versions.return_value = [
        {"version_number": 1, "file_path": "/tmp/v1.pdf", "file_size": 100, "file_hash": "abc123"},
    ]
    with patch("os.path.isfile", return_value=True):
        result = service.restore_version(1, 1)
        assert result is True
        service._repo.update.assert_called_once_with(
            1, file_path="/tmp/v1.pdf", file_size=100,
            file_hash="abc123", updated_at=service._repo.update.call_args[1]["updated_at"],
        )


def test_sanitize_filename_edge_cases(service):
    assert service._sanitize_filename("") == "unnamed_file"
    assert service._sanitize_filename("...") == "unnamed_file"
    assert service._sanitize_filename("file") == "file"
    # Dots in the base name are stripped (only alnum, _, -, space allowed)
    assert service._sanitize_filename("hello.world.txt") == "helloworld.txt"
    assert service._sanitize_filename("  spaced  file  .PDF") == "spaced  file.pdf"


def test_validate_file_ok(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"valid")
        tmp_path = f.name
    try:
        # Should not raise
        service._validate_file(tmp_path)
    finally:
        os.unlink(tmp_path)


def test_upload_new_version_with_tags_and_metadata(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"meta test")
        tmp_path = f.name
    try:
        service._repo.get_by_id.return_value = {"id": 1, "title": "Test"}
        service._repo.get_version_count.return_value = 0
        service._repo.get_versions.return_value = []
        service._repo.add_version.return_value = 1

        result = service.upload_new_version(1, tmp_path, comment="Updated", uploaded_by="admin")
        assert result == 1
        # Verify add_version was called with correct comment and uploaded_by
        call_kwargs = service._repo.add_version.call_args
        assert call_kwargs is not None
        # add_version(doc_id, next_ver, version_path, file_size, file_hash, comment, uploaded_by, now)
        args = call_kwargs[0]
        assert args[5] == "Updated"  # comment at index 5
        assert args[6] == "admin"   # uploaded_by at index 6
    finally:
        os.unlink(tmp_path)


def test_compute_sha256_consistency(service):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"exact content for hash check")
        tmp_path = f.name
    try:
        h1 = service._compute_sha256(tmp_path)
        h2 = service._compute_sha256(tmp_path)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest
    finally:
        os.unlink(tmp_path)


def test_unique_path_multiple_collisions(service):
    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = service._unique_path(tmpdir, "doc.pdf")
        open(p1, "w").close()
        p2 = service._unique_path(tmpdir, "doc.pdf")
        open(p2, "w").close()
        p3 = service._unique_path(tmpdir, "doc.pdf")
        assert p1 != p2
        assert p2 != p3
        assert "doc_1.pdf" in p2
        assert "doc_2.pdf" in p3
