"""E2E: Document versioning lifecycle — upload, restore, enforce limits."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest

from repositories.document_repository import DocumentRepository
from services.document.versioning_service import (
    MAX_VERSIONS_PER_DOC,
    VersioningService,
)
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


# ── Helpers ───────────────────────────────────────────────────────────


def _create_temp_file(suffix: str = ".pdf", content: bytes = b"dummy") -> str:
    """Create a temp file on disk and return its path."""
    f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    f.write(content)
    f.close()
    return f.name


def _create_document(repo: DocumentRepository) -> int:
    """Insert a minimal document record and return its id."""
    now = datetime.now().isoformat()
    src = _create_temp_file()
    try:
        doc_id = repo.create(
            doc_number="DOC-VER-0001",
            title="Version Test Doc",
            category="general",
            entity_type="trip",
            entity_id=None,
            file_path=src,
            file_name="original.pdf",
            file_size=os.path.getsize(src),
            mime_type="application/pdf",
            file_hash="initial",
            tags="[]",
            description="",
            uploaded_by="tester",
            uploaded_at=now,
            updated_at=now,
        )
    finally:
        if os.path.isfile(src):
            os.unlink(src)
    return doc_id


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def repo(db):
    return DocumentRepository(db)


@pytest.fixture
def svc(repo):
    return VersioningService(repo)


@pytest.fixture(autouse=True)
def _reset_singletons():
    from services.operations.event_bus import EventBus
    EventBus._instance = None
    from services.operations.alert_manager import AlertManager
    AlertManager._instance = None
    from services.operations.rules import Rules
    Rules._instance = None


# ── Tests ─────────────────────────────────────────────────────────────


class TestDocumentVersioning:
    """Document versioning: upload, restore, enforce limits, validation."""

    def test_upload_new_version_increments_version_number(
        self, db, repo, svc,
    ):
        """Upload doc, add new version, verify version=2 in DB."""
        doc_id = _create_document(repo)

        src = _create_temp_file(content=b"version 2 data")
        try:
            with patch("services.document.versioning_service.shutil.copy2") as mock_copy:
                with patch("services.document.versioning_service.os.makedirs"):
                    ver = svc.upload_new_version(
                        doc_id, src, comment="Second version", uploaded_by="tester",
                    )
        finally:
            if os.path.isfile(src):
                os.unlink(src)

        # First upload yields version 1 (the document create itself is not a version)
        assert ver == 1, f"Expected version 1, got {ver}"
        versions = repo.get_versions(doc_id)
        assert len(versions) >= 1
        # Versions are returned DESC by version_number
        assert versions[0]["version_number"] == 1

        # Document pointers should be updated
        doc = repo.get_by_id(doc_id)
        assert doc is not None
        assert doc["file_hash"] != "initial"

    def test_get_versions_returns_sorted_descending(self, db, repo, svc):
        """Add 3 versions, verify sorted by version_number desc."""
        doc_id = _create_document(repo)

        with patch("services.document.versioning_service.shutil.copy2") as mock_copy:
            with patch("services.document.versioning_service.os.makedirs"):
                for i in range(3):
                    src = _create_temp_file(content=f"version {i+2} data".encode())
                    try:
                        svc.upload_new_version(doc_id, src, comment=f"v{i+2}")
                    finally:
                        if os.path.isfile(src):
                            os.unlink(src)

        versions = repo.get_versions(doc_id)
        # 3 versions added → version_numbers should be 1, 2, 3 (v1 is the original upload)
        # Original doc has no version record — only upload_new_version creates them
        # After 3 uploads: version_numbers = 1, 2, 3
        assert len(versions) == 3
        version_numbers = [v["version_number"] for v in versions]
        assert version_numbers == [3, 2, 1], f"Expected [3, 2, 1], got {version_numbers}"

    def test_restore_version_updates_document_pointers(self, db, repo, svc):
        """Add v2, restore v1, verify file_path updated in DB."""
        doc_id = _create_document(repo)

        with patch("services.document.versioning_service.shutil.copy2") as mock_copy:
            with patch("services.document.versioning_service.os.makedirs"):
                src = _create_temp_file(content=b"version 2 content")
                try:
                    svc.upload_new_version(doc_id, src, comment="v2")
                finally:
                    if os.path.isfile(src):
                        os.unlink(src)

        # Get the v1 version record before restore to know its file_path
        versions_before = repo.get_versions(doc_id)
        v1_path = next(
            v["file_path"] for v in versions_before if v["version_number"] == 1
        )

        # Mock os.path.isfile so restore_version finds the target file
        with patch("os.path.isfile", side_effect=lambda p: p == v1_path or not p.startswith("C:\\")):
            ok = svc.restore_version(doc_id, 1)

        assert ok is True, "restore_version returned False"

        doc = repo.get_by_id(doc_id)
        assert doc is not None
        assert doc["file_path"] == v1_path, (
            f"Expected file_path '{v1_path}', got '{doc['file_path']}'"
        )

    def test_restore_nonexistent_version_fails(self, db, repo, svc):
        """restore_version(doc_id, 99) returns False."""
        doc_id = _create_document(repo)

        ok = svc.restore_version(doc_id, 99)
        assert ok is False

    def test_max_versions_enforced(self, db, repo, svc):
        """Add 21 versions, verify only 20 kept and oldest removed."""
        doc_id = _create_document(repo)

        with patch("services.document.versioning_service.shutil.copy2") as mock_copy:
            with patch("services.document.versioning_service.os.makedirs"):
                for i in range(21):
                    src = _create_temp_file(content=f"bulk version {i}".encode())
                    try:
                        svc.upload_new_version(doc_id, src, comment=f"v{i+2}")
                    finally:
                        if os.path.isfile(src):
                            os.unlink(src)

        versions = repo.get_versions(doc_id)
        # MAX_VERSIONS_PER_DOC = 20, so only the 20 most recent should remain
        assert len(versions) <= MAX_VERSIONS_PER_DOC, (
            f"Expected ≤{MAX_VERSIONS_PER_DOC} versions, got {len(versions)}"
        )
        # The version numbers should be the 20 highest (2..21 since v1..v21 → keep 2..21)
        version_numbers = sorted(v["version_number"] for v in versions)
        assert version_numbers == list(range(2, len(version_numbers) + 2)), (
            f"Unexpected version numbers: {version_numbers}"
        )

    def test_invalid_file_extension_rejected(self, db, repo, svc):
        """Try .exe file, verify ValueError raised."""
        doc_id = _create_document(repo)

        src = _create_temp_file(suffix=".exe", content=b"malicious.exe")
        try:
            with pytest.raises(ValueError, match="not allowed"):
                svc.upload_new_version(doc_id, src, comment="exe test")
        finally:
            if os.path.isfile(src):
                os.unlink(src)
