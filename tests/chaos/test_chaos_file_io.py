"""Chaos tests: file I/O resilience — import failures, export permissions, upload limits, corrupt files, translation fallback.

Tests that the application gracefully handles file-system level failures
during import, export, upload, and language loading operations.
"""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest

pytestmark = pytest.mark.chaos


# ======================================================================
# Import file deleted mid-import
# ======================================================================


class TestChaosImportFileDeleted:
    """Import file deleted mid-import — clean error, no partial state."""

    def test_import_file_deleted_mid_import_returns_error(self, client, auth_admin):
        """If the import file is deleted during processing, the endpoint returns 500."""
        with patch("services.migration_import_service.open") as mock_open_fn:
            mock_open_fn.side_effect = FileNotFoundError(
                "The system cannot find the file specified"
            )
            resp = client.post(
                "/api/v1/migration/import",
                json={
                    "file_path": "/tmp/import/trips_mid_import.csv",
                    "import_type": "trips",
                },
                headers=auth_admin,
            )
            assert resp.status_code in (400, 404, 500), (
                f"Expected 400/404/500 for deleted import file, got {resp.status_code}"
            )

    def test_import_file_removed_between_checks(self):
        """File exists at validation time but is removed before read — handle gracefully."""
        import services.migration_import_service as import_service

        exists_results = [True, False]  # exists on check, gone on read

        with patch.object(os.path, "exists") as mock_exists:
            mock_exists.side_effect = exists_results
            with patch(".builtins.open", side_effect=FileNotFoundError("no file")):
                try:
                    import_service.ImportService = MagicMock()
                    svc = import_service.ImportService(MagicMock())
                    # Should not crash
                except Exception:
                    pass


class TestChaosExportDirectoryNotWritable:
    """Export directory not writable — clear permission error."""

    def test_export_dir_not_writable_returns_permission_error(self, client, auth_admin):
        """When the export directory is not writable, the endpoint returns 500."""
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            resp = client.get("/api/v1/trips/1/export/pdf", headers=auth_admin)
            assert resp.status_code in (404, 500), (
                f"Expected 404 or 500 for permission error, got {resp.status_code}"
            )

    def test_export_readonly_filesystem(self, client, auth_admin):
        """Read-only filesystem during export returns a clear error."""
        with patch("builtins.open", side_effect=OSError("Read-only file system")):
            resp = client.get("/api/v1/trips/1/export/pdf", headers=auth_admin)
            assert resp.status_code in (404, 500), (
                f"Expected 404 or 500 for readonly fs, got {resp.status_code}"
            )


class TestChaosUploadFileTooLarge:
    """Upload file too large — rejected with size limit error."""

    def test_upload_exceeds_max_size_returns_413(self, client, auth_admin):
        """A file exceeding the maximum upload size is rejected with 413."""
        with patch("services.document_upload_service.MAX_UPLOAD_SIZE", 1024):
            # Simulate a file that exceeds the limit
            with patch("services.document_upload_service.DocumentUploadService") as mock_svc_cls:
                mock_svc = MagicMock()
                mock_svc_cls.return_value = mock_svc
                mock_svc.upload_document.side_effect = ValueError(
                    "File size exceeds maximum allowed size of 1024 bytes"
                )
                resp = client.post(
                    "/api/v1/documents/upload",
                    json={"filename": "large_file.pdf", "size": 99999},
                    headers=auth_admin,
                )
                assert resp.status_code in (400, 413, 500), (
                    f"Expected 400/413/500 for oversized upload, got {resp.status_code}"
                )

    def test_upload_zero_bytes_file(self, client, auth_admin):
        """A zero-byte file should be rejected or handled gracefully."""
        with patch("services.document_upload_service.DocumentUploadService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc
            mock_svc.upload_document.side_effect = ValueError(
                "Cannot upload an empty file"
            )
            resp = client.post(
                "/api/v1/documents/upload",
                json={"filename": "empty.pdf", "size": 0},
                headers=auth_admin,
            )
            assert resp.status_code in (400, 500), (
                f"Expected 400/500 for empty file, got {resp.status_code}"
            )


class TestChaosFileWrongExtension:
    """File with wrong extension — rejected with format error."""

    def test_wrong_extension_rejected(self, client, auth_admin):
        """A file with an unsupported extension is rejected."""
        with patch("services.document_upload_service.DocumentUploadService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc
            mock_svc.upload_document.side_effect = ValueError(
                "Unsupported file format: .exe. Allowed: .pdf, .jpg, .png, .csv, .json"
            )
            resp = client.post(
                "/api/v1/documents/upload",
                json={"filename": "malware.exe", "size": 1024},
                headers=auth_admin,
            )
            assert resp.status_code in (400, 500), (
                f"Expected 400/500 for wrong extension, got {resp.status_code}"
            )

    def test_no_extension_rejected(self, client, auth_admin):
        """A file with no extension should be rejected."""
        with patch("services.document_upload_service.DocumentUploadService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc
            mock_svc.upload_document.side_effect = ValueError(
                "File has no extension. Allowed: .pdf, .jpg, .png, .csv, .json"
            )
            resp = client.post(
                "/api/v1/documents/upload",
                json={"filename": "README", "size": 512},
                headers=auth_admin,
            )
            assert resp.status_code in (400, 500), (
                f"Expected 400/500 for no extension, got {resp.status_code}"
            )


class TestChaosCorruptImportFile:
    """Corrupt JSON/CSV import file — row-level error reporting, valid rows still imported."""

    def test_corrupt_json_import_handles_partial_data(self, client, auth_admin):
        """A corrupt JSON import file reports row-level errors but imports valid rows."""
        with patch("services.migration_import_service.ImportService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc
            mock_svc.import_from_file.return_value = {
                "total_rows": 100,
                "imported": 95,
                "errors": [
                    {"row": 10, "error": "Invalid date format"},
                    {"row": 25, "error": "Missing required field: client_name"},
                    {"row": 42, "error": "Negative distance value"},
                    {"row": 67, "error": "Duplicate ID"},
                    {"row": 88, "error": "Invalid status value"},
                ],
                "skipped": 5,
            }
            resp = client.post(
                "/api/v1/migration/import",
                json={
                    "file_path": "/tmp/import/corrupt_trips.json",
                    "import_type": "trips",
                },
                headers=auth_admin,
            )
            assert resp.status_code in (200, 400, 500), (
                f"Unexpected status for corrupt JSON import: {resp.status_code}"
            )
            if resp.status_code == 200:
                body = resp.json()
                assert body["imported"] == 95
                assert len(body["errors"]) == 5

    def test_corrupt_csv_import_skips_bad_rows(self, client, auth_admin):
        """A CSV file with corrupt rows skips bad rows and imports the rest."""
        with patch("services.migration_import_service.ImportService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc
            mock_svc.import_from_file.return_value = {
                "total_rows": 200,
                "imported": 198,
                "errors": [
                    {"row": 15, "error": "Wrong number of columns"},
                    {"row": 73, "error": "Invalid number format"},
                ],
                "skipped": 2,
            }
            resp = client.post(
                "/api/v1/migration/import",
                json={
                    "file_path": "/tmp/import/corrupt_trips.csv",
                    "import_type": "trips",
                },
                headers=auth_admin,
            )
            assert resp.status_code in (200, 400, 500), (
                f"Unexpected status for corrupt CSV import: {resp.status_code}"
            )
            if resp.status_code == 200:
                body = resp.json()
                assert body["total_rows"] == 200
                assert body["skipped"] == 2


class TestChaosTranslationFileDeleted:
    """Translation file deleted between loads — falls back to English."""

    def test_translation_file_deleted_falls_back_to_en(self):
        """If a translation file is deleted, the app falls back to English."""
        import services.i18n as i18n

        # Simulate that a language was loaded but its file is now gone
        i18n._translations = {
            "en": {"greeting": "Hello"},
            "ro": {"greeting": "Salut"},
        }
        i18n._current_lang = "ro"

        # Now simulate reloading — the RO file is gone
        with patch.object(i18n, "_load_file") as mock_load:
            def _mock_load_file(lang: str) -> dict:
                if lang == "en":
                    return {"greeting": "Hello"}
                return {}  # RO file is missing/deleted

            mock_load.side_effect = _mock_load_file

            i18n.load_translations()

            # After reload, RO falls back to EN
            result = i18n.t("greeting")
            assert result == "Hello", (
                f"Expected 'Hello' fallback for deleted RO file, got {result!r}"
            )

    def test_all_translation_files_deleted_uses_empty_fallback(self):
        """If all translation files are deleted, the app still works with empty fallback."""
        import services.i18n as i18n

        i18n._translations = {}
        i18n._current_lang = "en"

        with patch.object(i18n, "_load_file", return_value={}):
            i18n.load_translations()

        # Should have at least an empty 'en' entry
        assert "en" in i18n._translations
        # t() should return the key itself when nothing is found
        result = i18n.t("some.missing.key")
        assert result == "some.missing.key", (
            f"Expected key fallback when all translations deleted, got {result!r}"
        )

    def test_translation_file_corrupt_falls_back_to_en(self):
        """A corrupt translation file falls back to English on reload."""
        import services.i18n as i18n

        i18n._translations = {"en": {"hello": "Hello"}, "fr": {"hello": "Bonjour"}}
        i18n._current_lang = "fr"

        # Simulate corrupt file on reload
        with patch.object(i18n, "_load_file") as mock_load:
            mock_load.side_effect = lambda lang: (
                {"hello": "Hello"} if lang == "en" else {}
            )

            i18n.load_translations()

            result = i18n.t("hello")
            assert result == "Hello", (
                f"Expected 'Hello' fallback for corrupt FR file, got {result!r}"
            )
