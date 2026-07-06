"""Tests for pipeline rename functions (_rename_document_after_ocr, _sanitize_filename_part)."""
import os.path
from unittest.mock import MagicMock, call, patch

import pytest

from services.document_automation.pipeline import (
    _rename_document_after_ocr,
    _sanitize_filename_part,
)


class TestSanitizeFilenamePart:
    def test_keeps_alphanumeric_and_hyphens(self):
        assert _sanitize_filename_part("CRG-0148") == "CRG-0148"

    def test_replaces_path_separators(self):
        result = _sanitize_filename_part("ACME/Corp GmbH")
        assert "/" not in result
        assert "Corp" in result

    def test_replaces_backslash(self):
        result = _sanitize_filename_part("Bad\\Name")
        assert "\\" not in result

    def test_collapses_consecutive_underscores(self):
        result = _sanitize_filename_part("ACME___Corp")
        assert "___" not in result
        assert result == "ACME_Corp"

    def test_strips_leading_trailing_dots(self):
        assert _sanitize_filename_part(".ACME Corp.") == "ACME_Corp"

    def test_strips_trailing_whitespace(self):
        assert _sanitize_filename_part("ACME Corp  ") == "ACME_Corp"

    def test_returns_unknown_for_empty(self):
        assert _sanitize_filename_part("") == "Unknown"

    def test_replaces_control_chars(self):
        result = _sanitize_filename_part("ACME\x00Corp")
        assert "\x00" not in result

    def test_replaces_wildcards(self):
        result = _sanitize_filename_part("ACME*Corp?.pdf")
        assert "*" not in result
        assert "?" not in result

    def test_preserves_hyphens_in_client_name(self):
        result = _sanitize_filename_part("Smith & Wesson GmbH")
        assert "Smith" in result
        assert "Wesson" in result


class TestRenameDocumentAfterOcr:
    def test_renames_with_doc_id_client_and_date(self):
        mock_db = MagicMock()
        mock_db.conn = MagicMock()

        with patch("repositories.document_repository.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = {
                "id": 42,
                "file_path": "/docs/uploaded_file.pdf",
                "file_name": "uploaded_file.pdf",
                "title": "uploaded_file",
                "uploaded_at": "2025-06-15T10:00:00",
            }

            extracted = {
                "doc_id": "CRG-0148",
                "date": "2025-06-15",
            }
            matched_clients = ["ACME Corp GmbH"]

            with patch("os.path.isfile", return_value=True), \
                 patch("os.rename") as mock_rename:
                _rename_document_after_ocr(mock_db, 42, extracted, matched_clients)
                expected_new_name = f"CRG-0148-ACME_Corp_GmbH-2025-06-15.pdf"
                expected_new_path = os.path.join("/docs", expected_new_name)
                mock_rename.assert_called_once_with(
                    "/docs/uploaded_file.pdf", expected_new_path
                )

    def test_uses_cmr_number_fallback_when_no_doc_id(self):
        mock_db = MagicMock()
        with patch("repositories.document_repository.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = {
                "id": 42,
                "file_path": "/docs/uploaded.pdf",
                "file_name": "uploaded.pdf",
                "title": "uploaded",
                "uploaded_at": "2025-06-15T10:00:00",
            }

            extracted = {
                "cmr_number": "CMR-999",
                "date": "2025-06-15",
            }
            matched_clients = ["Client SRL"]

            with patch("os.path.isfile", return_value=True), \
                 patch("os.rename") as mock_rename:
                _rename_document_after_ocr(mock_db, 42, extracted, matched_clients)
                args, _ = mock_rename.call_args
                assert "CMR-999" in args[1]

    def test_uses_invoice_number_fallback(self):
        mock_db = MagicMock()
        with patch("repositories.document_repository.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = {
                "id": 42,
                "file_path": "/docs/uploaded.pdf",
                "file_name": "uploaded.pdf",
                "title": "uploaded",
                "uploaded_at": "2025-06-15T10:00:00",
            }

            extracted = {
                "invoice_number": "INV-2025-001",
                "date": "2025-06-15",
            }
            matched_clients = ["Client SRL"]

            with patch("os.path.isfile", return_value=True), \
                 patch("os.rename") as mock_rename:
                _rename_document_after_ocr(mock_db, 42, extracted, matched_clients)
                args, _ = mock_rename.call_args
                assert "INV-2025-001" in args[1]

    def test_uses_upload_date_when_no_date_extracted(self):
        mock_db = MagicMock()
        with patch("repositories.document_repository.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = {
                "id": 42,
                "file_path": "/docs/uploaded.pdf",
                "file_name": "uploaded.pdf",
                "title": "uploaded",
                "uploaded_at": "2025-06-15T10:00:00",
            }

            extracted = {"doc_id": "DOC-001"}
            matched_clients = ["Client SRL"]

            with patch("os.path.isfile", return_value=True), \
                 patch("os.rename") as mock_rename:
                _rename_document_after_ocr(mock_db, 42, extracted, matched_clients)
                args, _ = mock_rename.call_args
                assert "DOC-001" in args[1]
                assert "Client_SRL" in args[1]
                assert "2025-06-15" in args[1]

    def test_multiple_clients_joined_with_and(self):
        mock_db = MagicMock()
        with patch("repositories.document_repository.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = {
                "id": 42,
                "file_path": "/docs/uploaded.pdf",
                "file_name": "uploaded.pdf",
                "title": "uploaded",
                "uploaded_at": "2025-06-15T10:00:00",
            }

            extracted = {"doc_id": "DOC-001", "date": "2025-06-15"}
            matched_clients = ["ACME Corp", "Beta SRL"]

            with patch("os.path.isfile", return_value=True), \
                 patch("os.rename") as mock_rename:
                _rename_document_after_ocr(mock_db, 42, extracted, matched_clients)
                args, _ = mock_rename.call_args
                assert "ACME_Corp" in args[1]
                assert "and" in args[1] or "Beta_SRL" in args[1]
                assert "Beta_SRL" in args[1]

    def test_rolls_back_rename_on_db_failure(self):
        mock_db = MagicMock()
        with patch("repositories.document_repository.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = {
                "id": 42,
                "file_path": "/docs/test.pdf",
                "file_name": "test.pdf",
                "title": "test",
                "uploaded_at": "2025-06-15T10:00:00",
            }
            mock_repo.update.side_effect = Exception("DB error")

            extracted = {"doc_id": "DOC-001", "date": "2025-06-15"}
            matched_clients = ["Client SRL"]

            with patch("os.path.isfile", return_value=True), \
                 patch("os.rename") as mock_rename:
                _rename_document_after_ocr(mock_db, 42, extracted, matched_clients)
                # Should have called rename twice: forward, then rollback
                assert mock_rename.call_count == 2

    def test_skips_rename_when_file_missing(self):
        mock_db = MagicMock()
        with patch("repositories.document_repository.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = {
                "id": 42,
                "file_path": "/docs/missing.pdf",
                "file_name": "missing.pdf",
                "title": "missing",
                "uploaded_at": "2025-06-15",
            }

            with patch("os.path.isfile", return_value=False), \
                 patch("os.rename") as mock_rename:
                _rename_document_after_ocr(mock_db, 42, {}, [])
                mock_rename.assert_not_called()

    def test_skips_rename_when_doc_not_found(self):
        mock_db = MagicMock()
        with patch("repositories.document_repository.DocumentRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = None

            with patch("os.rename") as mock_rename:
                _rename_document_after_ocr(mock_db, 999, {}, [])
                mock_rename.assert_not_called()
