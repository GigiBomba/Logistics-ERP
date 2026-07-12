"""Tests for DocumentActionsMixin — bulk document actions.

This tests the mixin methods defined in
``ui/views/document_center/document_actions.py``.
"""
from __future__ import annotations

import contextlib
import os
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox, QWidget

from ui.views.document_center.document_actions import DocumentActionsMixin


# =========================================================================
# Mock host — a minimal QWidget that uses the mixin
# =========================================================================


class MockDocumentHost(QWidget, DocumentActionsMixin):
    """A QWidget host that mixes in DocumentActionsMixin for testing.

    Provides the minimum attributes that the mixin expects on ``self``.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._service = MagicMock()
        self._selected_ids: set = set()
        self._active_category: str = ""
        self.db = MagicMock()
        self.prefs = MagicMock()
        self._ocr_busy: bool = False
        self._current_detail_doc: dict | None = None
        self._ocr_worker = None

    def refresh(self) -> None:
        pass

    def _show_toast(self, msg: str) -> None:
        pass

    def _show_detail(self, doc: dict | None) -> None:
        self._current_detail_doc = doc

    def _refresh_detail(self, doc_id: int) -> None:
        if self._service:
            doc = self._service.get_by_id(doc_id)
            if doc:
                self._show_detail(doc)

    def _stop_ocr_worker(self) -> None:
        self._ocr_worker = None


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_host(qtbot):
    """Create a MockDocumentHost with DocumentActionsMixin mixed in."""
    host = MockDocumentHost()
    qtbot.addWidget(host)
    yield host


@pytest.fixture
def sample_doc():
    """A minimal document dict for testing action methods."""
    return {
        "id": 1,
        "title": "Test Invoice",
        "file_name": "invoice.pdf",
        "file_path": "/tmp/invoice.pdf",
        "file_size": 2048,
        "mime_type": "application/pdf",
        "uploaded_at": "2025-01-15T10:00:00",
        "doc_number": "INV-001",
    }


# =========================================================================
# Tests
# =========================================================================


class TestDocumentActionsMixin:
    """Suite of tests for DocumentActionsMixin methods."""

    # ── Open / View ───────────────────────────────────────────────────

    @patch("ui.views.document_center.document_actions.QDesktopServices.openUrl")
    def test_open_document_calls_service(self, mock_open_url, mock_host, sample_doc):
        """_open_document gets the file path from the service and opens it."""
        mock_host._service.get_file_path.return_value = "/path/to/invoice.pdf"
        mock_host._open_document(sample_doc)
        mock_host._service.get_file_path.assert_called_once_with(1)
        mock_open_url.assert_called_once()

    @patch("ui.views.document_center.document_actions.QDesktopServices.openUrl")
    def test_open_document_no_path(self, mock_open_url, mock_host, sample_doc):
        """_open_document does nothing when service returns no path."""
        mock_host._service.get_file_path.return_value = None
        mock_host._open_document(sample_doc)
        mock_open_url.assert_not_called()

    @patch("ui.views.document_center.document_actions.QDesktopServices.openUrl")
    def test_open_document_no_service(self, mock_open_url, mock_host, sample_doc):
        """_open_document does nothing when _service is None."""
        mock_host._service = None
        mock_host._open_document(sample_doc)
        mock_open_url.assert_not_called()

    # ── Upload ────────────────────────────────────────────────────────

    @patch("ui.views.document_center.document_actions.QFileDialog.getOpenFileNames",
           return_value=(["file1.pdf", "file2.pdf"], ""))
    @patch.object(MockDocumentHost, "_process_batch_upload")
    def test_upload_dialog_opens_and_processes(self, mock_process, mock_get_files,
                                                mock_host):
        """_upload_dialog opens file picker and delegates to batch upload."""
        mock_host._upload_dialog()
        mock_get_files.assert_called_once()
        mock_process.assert_called_once_with(["file1.pdf", "file2.pdf"])

    @patch("ui.views.document_center.document_actions.QFileDialog.getOpenFileNames",
           return_value=([], ""))
    @patch.object(MockDocumentHost, "_process_batch_upload")
    def test_upload_dialog_cancelled(self, mock_process, mock_get_files,
                                      mock_host):
        """_upload_dialog does nothing when no files are selected."""
        mock_host._upload_dialog()
        mock_process.assert_not_called()

    # ── Batch upload ──────────────────────────────────────────────────

    @patch("ui.views.document_center.document_actions.QMessageBox.warning")
    def test_process_batch_upload_success(self, mock_warning, mock_host):
        """_process_batch_upload handles successful uploads."""
        mock_host._service.batch_upload.return_value = {
            "uploaded": ["file1.pdf"],
            "duplicates": [],
            "rejected": [],
            "failed": [],
        }
        with patch.object(mock_host, "_show_toast") as mock_toast:
            mock_host._process_batch_upload(["/path/file1.pdf"])
            mock_host._service.batch_upload.assert_called_once()
            mock_toast.assert_called_once()
            assert "Uploaded: 1" in mock_toast.call_args[0][0]
        mock_warning.assert_not_called()

    @patch("ui.views.document_center.document_actions.QMessageBox.warning")
    def test_process_batch_upload_with_rejected(self, mock_warning, mock_host):
        """_process_batch_upload shows warning when files are rejected."""
        mock_host._service.batch_upload.return_value = {
            "uploaded": [],
            "duplicates": [],
            "rejected": [{"file": "bad.pdf", "reason": "Invalid format"}],
            "failed": [],
        }
        with patch.object(mock_host, "_show_toast"):
            mock_host._process_batch_upload(["/path/bad.pdf"])
        mock_warning.assert_called_once()

    def test_process_batch_upload_no_service(self, mock_host):
        """_process_batch_upload does nothing when _service is None."""
        mock_host._service = None
        # Should not raise
        mock_host._process_batch_upload(["/path/file.pdf"])

    # ── Email ─────────────────────────────────────────────────────────

    @patch("ui.views.document_center.document_actions.QInputDialog.getText",
           return_value=("test@example.com", True))
    @patch("ui.views.document_center.document_actions.QMessageBox.information")
    def test_email_document_success(self, mock_info, mock_input, mock_host,
                                    sample_doc):
        """_email_document sends via service and shows info on success."""
        mock_host._service.email_document.return_value = True
        mock_host._email_document(sample_doc)
        mock_host._service.email_document.assert_called_once_with(
            1, "test@example.com", prefs=mock_host.prefs,
        )
        mock_info.assert_called_once()

    @patch("ui.views.document_center.document_actions.QInputDialog.getText",
           return_value=("test@example.com", True))
    @patch("ui.views.document_center.document_actions.QMessageBox.critical")
    def test_email_document_smtp_not_configured(self, mock_critical, mock_input,
                                                 mock_host, sample_doc):
        """_email_document shows critical when SMTP is not configured."""
        mock_host._service.email_document.return_value = False
        mock_host._email_document(sample_doc)
        mock_critical.assert_called_once()

    @patch("ui.views.document_center.document_actions.QInputDialog.getText",
           return_value=("", True))
    def test_email_document_empty_recipient(self, mock_input, mock_host, sample_doc):
        """_email_document aborts when no recipient is entered."""
        mock_host._email_document(sample_doc)
        mock_host._service.email_document.assert_not_called()

    @patch("ui.views.document_center.document_actions.QInputDialog.getText",
           return_value=("test@example.com", True))
    @patch("ui.views.document_center.document_actions.QMessageBox.critical")
    def test_email_document_service_exception(self, mock_critical, mock_input,
                                               mock_host, sample_doc):
        """_email_document catches service exceptions and shows error."""
        mock_host._service.email_document.side_effect = Exception("Email failed")
        mock_host._email_document(sample_doc)
        mock_critical.assert_called_once()

    # ── Download ZIP ──────────────────────────────────────────────────

    @patch("ui.views.document_center.document_actions.QFileDialog.getSaveFileName",
           return_value=("/tmp/docs.zip", ""))
    @patch("ui.views.document_center.document_actions.QMessageBox.information")
    def test_download_zip_selected(self, mock_info, mock_save, mock_host):
        """_download_zip_selected calls service and shows info."""
        mock_host._selected_ids = {1, 2}
        mock_host._download_zip_selected()
        mock_host._service.download_zip.assert_called_once_with(
            [1, 2], "/tmp/docs.zip",
        )
        mock_info.assert_called_once()

    @patch("ui.views.document_center.document_actions.QFileDialog.getSaveFileName",
           return_value=("", ""))
    def test_download_zip_cancelled(self, mock_save, mock_host):
        """_download_zip_selected does nothing when save dialog is cancelled."""
        mock_host._selected_ids = {1}
        mock_host._download_zip_selected()
        mock_host._service.download_zip.assert_not_called()

    def test_download_zip_no_selection(self, mock_host):
        """_download_zip_selected does nothing when nothing is selected."""
        mock_host._selected_ids.clear()
        mock_host._download_zip_selected()
        mock_host._service.download_zip.assert_not_called()

    @patch("ui.views.document_center.document_actions.QFileDialog.getSaveFileName",
           return_value=("/tmp/doc.zip", ""))
    @patch("ui.views.document_center.document_actions.QMessageBox.critical")
    def test_download_zip_service_exception(self, mock_critical, mock_save,
                                             mock_host):
        """_download_zip_selected catches service exceptions."""
        mock_host._selected_ids = {1}
        mock_host._service.download_zip.side_effect = Exception("ZIP error")
        mock_host._download_zip_selected()
        mock_critical.assert_called_once()

    @patch("ui.views.document_center.document_actions.QFileDialog.getSaveFileName",
           return_value=("/tmp/doc.zip", ""))
    @patch("ui.views.document_center.document_actions.QMessageBox.information")
    def test_download_single_zip(self, mock_info, mock_save, mock_host,
                                  sample_doc):
        """_download_single_zip downloads a single document as ZIP."""
        mock_host._download_single_zip(sample_doc)
        mock_host._service.download_zip.assert_called_once_with(
            [1], "/tmp/doc.zip",
        )
        mock_info.assert_called_once()

    # ── Delete ────────────────────────────────────────────────────────

    @patch("ui.views.document_center.document_actions.QMessageBox.question",
           return_value=QMessageBox.Yes)
    def test_delete_document_confirmed(self, mock_question, mock_host, sample_doc):
        """_delete_document removes document after user confirms."""
        mock_host._selected_ids = {1}
        mock_host._delete_document(sample_doc)
        mock_host._service.delete.assert_called_once_with(1)
        assert 1 not in mock_host._selected_ids

    @patch("ui.views.document_center.document_actions.QMessageBox.question",
           return_value=QMessageBox.No)
    def test_delete_document_cancelled(self, mock_question, mock_host, sample_doc):
        """_delete_document does nothing when user cancels."""
        mock_host._delete_document(sample_doc)
        mock_host._service.delete.assert_not_called()

    @patch("ui.views.document_center.document_actions.QMessageBox.question",
           return_value=QMessageBox.Yes)
    def test_delete_document_no_service(self, mock_question, mock_host, sample_doc):
        """_delete_document does nothing when _service is None."""
        mock_host._service = None
        mock_host._delete_document(sample_doc)

    # ── Archive ───────────────────────────────────────────────────────

    def test_archive_document(self, mock_host, sample_doc):
        """_archive_document calls service.archive and discards selection."""
        mock_host._selected_ids = {1}
        mock_host._archive_document(sample_doc)
        mock_host._service.archive.assert_called_once_with(1)
        assert 1 not in mock_host._selected_ids

    def test_archive_document_no_service(self, mock_host, sample_doc):
        """_archive_document does nothing when _service is None."""
        mock_host._service = None
        mock_host._archive_document(sample_doc)

    # ── Batch delete ──────────────────────────────────────────────────

    @patch("ui.views.document_center.document_actions.QMessageBox.question",
           return_value=QMessageBox.Yes)
    def test_batch_delete_selected_confirmed(self, mock_question, mock_host):
        """_batch_delete_selected deletes all selected documents."""
        mock_host._selected_ids = {1, 2, 3}
        mock_host._batch_delete_selected()
        mock_host._service.delete_batch.assert_called_once_with([1, 2, 3])
        assert len(mock_host._selected_ids) == 0

    @patch("ui.views.document_center.document_actions.QMessageBox.question",
           return_value=QMessageBox.No)
    def test_batch_delete_selected_cancelled(self, mock_question, mock_host):
        """_batch_delete_selected does nothing when user cancels."""
        mock_host._selected_ids = {1, 2}
        mock_host._batch_delete_selected()
        mock_host._service.delete_batch.assert_not_called()

    def test_batch_delete_selected_no_selection(self, mock_host):
        """_batch_delete_selected does nothing when nothing is selected."""
        mock_host._selected_ids.clear()
        mock_host._batch_delete_selected()
        mock_host._service.delete_batch.assert_not_called()

    @patch("ui.views.document_center.document_actions.QMessageBox.question",
           return_value=QMessageBox.Yes)
    @patch("ui.views.document_center.document_actions.QMessageBox.critical")
    def test_batch_delete_service_exception(self, mock_critical, mock_question,
                                             mock_host):
        """_batch_delete_selected catches service exceptions."""
        mock_host._selected_ids = {1}
        mock_host._service.delete_batch.side_effect = Exception("DB error")
        mock_host._batch_delete_selected()
        mock_critical.assert_called_once()

    # ── On-demand OCR ─────────────────────────────────────────────────

    @patch("ui.views.document_center.document_actions.os.path.isfile",
           return_value=True)
    @patch("ui.views.document_center.document_actions.QMessageBox.warning")
    def test_rerun_ocr_file_not_found(self, mock_warning, mock_isfile,
                                       mock_host, sample_doc):
        """_on_rerun_ocr_clicked warns when the file is missing."""
        mock_isfile.return_value = False
        mock_host._on_rerun_ocr_clicked(sample_doc)
        mock_warning.assert_called_once()

    def test_rerun_ocr_already_busy(self, mock_host, sample_doc):
        """_on_rerun_ocr_clicked returns early if OCR is already running."""
        mock_host._ocr_busy = True
        # Should not raise
        mock_host._on_rerun_ocr_clicked(sample_doc)

    def test_rerun_ocr_no_service(self, mock_host, sample_doc):
        """_on_rerun_ocr_clicked returns early if _service is None."""
        mock_host._service = None
        mock_host._on_rerun_ocr_clicked(sample_doc)

    def test_rerun_ocr_non_dict_doc(self, mock_host):
        """_on_rerun_ocr_clicked handles non-dict doc gracefully."""
        # Should not raise
        mock_host._on_rerun_ocr_clicked("not_a_dict")

    # ── Trip linking ──────────────────────────────────────────────────

    @patch("ui.views.document_center.document_actions.QMessageBox.warning")
    def test_link_to_trip_non_dict_doc(self, mock_warning, mock_host):
        """_on_link_to_trip_clicked warns on non-dict document."""
        mock_host._on_link_to_trip_clicked("bad_doc")
        mock_warning.assert_called_once()

    def test_link_to_trip_no_db(self, mock_host, sample_doc):
        """_on_link_to_trip_clicked returns early if db is None."""
        mock_host.db = None
        mock_host._on_link_to_trip_clicked(sample_doc)

    @patch("ui.dialogs.trip_picker_dialog.QtTripPickerDialog")
    def test_link_to_trip_dialog_rejected(self, mock_dialog_class, mock_host,
                                           sample_doc):
        """_on_link_to_trip_clicked returns early when dialog is rejected."""
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Rejected
        mock_dialog_class.return_value = mock_dialog
        mock_host._on_link_to_trip_clicked(sample_doc)
        mock_host._service.link_document.assert_not_called()

    @patch("ui.dialogs.trip_picker_dialog.QtTripPickerDialog")
    def test_link_to_trip_linked(self, mock_dialog_class, mock_host, sample_doc):
        """_on_link_to_trip_clicked links document when dialog is accepted."""
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Accepted
        mock_dialog.selected_trip_id.return_value = 42
        mock_dialog_class.return_value = mock_dialog
        mock_host._service.link_document.return_value = True

        with patch.object(mock_host, "_show_toast") as mock_toast:
            mock_host._on_link_to_trip_clicked(sample_doc)
            mock_host._service.link_document.assert_called_once_with(
                1, "trip", 42, relation_type="ocr_linked",
            )
            mock_toast.assert_called_once()

    @patch("ui.dialogs.trip_picker_dialog.QtTripPickerDialog")
    def test_link_to_trip_no_service(self, mock_dialog_class, mock_host,
                                      sample_doc):
        """_on_link_to_trip_clicked returns early if _service is None."""
        mock_host._service = None
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.Accepted
        mock_dialog.selected_trip_id.return_value = 42
        mock_dialog_class.return_value = mock_dialog
        # Should not raise
        mock_host._on_link_to_trip_clicked(sample_doc)
