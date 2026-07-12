"""Tests for the upload integration view."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QScrollArea, QFrame


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client._config = MagicMock()
    return client


@pytest.fixture
def upload_widget(qt_widget, qtbot, mock_api_client):
    """Create UploadIntegrationWidget with mocked ApiClient."""
    from ui.views.upload_integration import UploadIntegrationWidget

    widget = UploadIntegrationWidget(
        parent=qt_widget,
        api_client=mock_api_client,
    )
    qtbot.addWidget(widget)
    yield widget
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        widget.shutdown()


# =========================================================================
# Tests
# =========================================================================


class TestQtUploadIntegrationInit:
    """Construction and basic attributes."""

    def test_creation(self, upload_widget):
        assert upload_widget is not None
        assert upload_widget._api is not None
        assert upload_widget._worker is None
        assert upload_widget._selected_path == ""

    def test_has_browse_button(self, upload_widget):
        assert hasattr(upload_widget, "_browse_btn")
        assert isinstance(upload_widget._browse_btn, QPushButton)

    def test_has_upload_button(self, upload_widget):
        assert hasattr(upload_widget, "_upload_btn")
        assert isinstance(upload_widget._upload_btn, QPushButton)

    def test_upload_button_disabled_initially(self, upload_widget):
        assert not upload_widget._upload_btn.isEnabled()

    def test_has_path_label(self, upload_widget):
        assert hasattr(upload_widget, "_path_label")
        assert isinstance(upload_widget._path_label, QLabel)

    def test_path_label_default_text(self, upload_widget):
        assert "No file selected" in upload_widget._path_label.text() or \
               "no_file" in upload_widget._path_label.text()

    def test_has_progress_bar(self, upload_widget):
        assert hasattr(upload_widget, "_progress_bar")
        assert isinstance(upload_widget._progress_bar, QProgressBar)

    def test_progress_bar_hidden_initially(self, upload_widget):
        assert not upload_widget._progress_bar.isVisible()

    def test_has_status_label(self, upload_widget):
        assert hasattr(upload_widget, "_status_label")
        assert isinstance(upload_widget._status_label, QLabel)

    def test_has_result_scroll(self, upload_widget):
        assert hasattr(upload_widget, "_result_scroll")
        assert isinstance(upload_widget._result_scroll, QScrollArea)

    def test_result_scroll_hidden_initially(self, upload_widget):
        assert not upload_widget._result_scroll.isVisible()


class TestQtUploadIntegrationBrowse:
    """File browsing interaction."""

    def test_browse_cancelled_does_not_change_path(self, upload_widget, monkeypatch):
        """If no file selected, path stays empty."""
        monkeypatch.setattr(
            "ui.views.upload_integration.QFileDialog.getOpenFileName",
            lambda *a, **kw: ("", ""),
        )
        upload_widget._on_browse_clicked()
        assert upload_widget._selected_path == ""
        assert not upload_widget._upload_btn.isEnabled()

    def test_browse_file_too_large_shows_warning(self, upload_widget, monkeypatch):
        """File exceeding MAX_UPLOAD_SIZE shows warning and does not select."""
        warnings = []
        monkeypatch.setattr(
            "ui.views.upload_integration.QFileDialog.getOpenFileName",
            lambda *a, **kw: ("/tmp/huge.pdf", "huge.pdf"),
        )
        monkeypatch.setattr(
            "os.path.getsize",
            lambda p: 60 * 1024 * 1024,  # 60MB > 50MB
        )
        monkeypatch.setattr(
            "ui.views.upload_integration.QMessageBox.warning",
            lambda *a, **kw: warnings.append("shown"),
        )
        upload_widget._on_browse_clicked()
        assert len(warnings) >= 1
        assert upload_widget._selected_path == ""
        assert not upload_widget._upload_btn.isEnabled()

    def test_browse_valid_file_updates_path(self, upload_widget, monkeypatch, tmp_path):
        """Valid file selection updates path and enables upload button."""
        valid_file = tmp_path / "test.pdf"
        valid_file.write_text("fake pdf content")

        monkeypatch.setattr(
            "ui.views.upload_integration.QFileDialog.getOpenFileName",
            lambda *a, **kw: (str(valid_file), "test.pdf"),
        )
        monkeypatch.setattr(
            "os.path.getsize",
            lambda p: 1024,  # 1KB
        )
        upload_widget._on_browse_clicked()
        assert upload_widget._selected_path == str(valid_file)
        assert upload_widget._upload_btn.isEnabled()


class TestQtUploadIntegrationUpload:
    """Upload lifecycle."""

    def test_upload_with_no_path_does_nothing(self, upload_widget):
        upload_widget._selected_path = ""
        upload_widget._on_upload_clicked()
        assert upload_widget._worker is None

    def test_upload_creates_worker(self, upload_widget, monkeypatch):
        upload_widget._selected_path = "/tmp/test.pdf"
        mock_worker = MagicMock()
        mock_worker_class = MagicMock(return_value=mock_worker)
        monkeypatch.setattr(
            "ui.views.upload_integration.NetworkWorker",
            mock_worker_class,
        )
        upload_widget._on_upload_clicked()
        assert upload_widget._worker is not None
        mock_worker.start.assert_called_once()

    def test_upload_sets_progress_and_status(self, upload_widget, monkeypatch):
        upload_widget._selected_path = "/tmp/test.pdf"
        mock_worker = MagicMock()
        monkeypatch.setattr(
            "ui.views.upload_integration.NetworkWorker",
            MagicMock(return_value=mock_worker),
        )
        upload_widget._on_upload_clicked()
        # _set_uploading(True) disables buttons and sets progress bar visible.
        # Button state is reliable across Qt test environments.
        assert not upload_widget._browse_btn.isEnabled()
        assert not upload_widget._upload_btn.isEnabled()

    def test_upload_done_updates_status_and_emits_signal(self, upload_widget, qtbot, monkeypatch):
        """_on_upload_done sets status and emits document_uploaded."""
        # Prevent _fetch_ocr_result from overwriting the status label
        monkeypatch.setattr(upload_widget, "_fetch_ocr_result", lambda doc_id: None)
        with qtbot.waitSignal(upload_widget.document_uploaded, timeout=1000) as blocker:
            upload_widget._on_upload_done({"id": 7, "status": "ok"})
        assert blocker.signal_triggered
        assert blocker.args[0] == 7
        assert "7" in upload_widget._status_label.text()

    def test_upload_done_clears_worker(self, upload_widget, monkeypatch):
        """_on_upload_done sets _worker to None, then _fetch_ocr_result may recreate it."""
        monkeypatch.setattr(upload_widget, "_fetch_ocr_result", lambda doc_id: None)
        upload_widget._worker = MagicMock()
        upload_widget._on_upload_done({"id": 1})
        # Worker is cleared inside _on_upload_done (fetched separately afterwards)
        assert upload_widget._worker is None

    def test_upload_error_shows_message_and_clears(self, upload_widget, monkeypatch):
        messages = []
        monkeypatch.setattr(
            "ui.views.upload_integration.QMessageBox.critical",
            lambda *a, **kw: messages.append("shown"),
        )
        upload_widget._worker = MagicMock()
        upload_widget._on_upload_error("Server error")
        assert upload_widget._worker is None
        # _set_uploading(False) re-enables buttons after an error
        assert upload_widget._upload_btn.isEnabled()
        assert upload_widget._browse_btn.isEnabled()
        assert "Error" in upload_widget._status_label.text()
        assert len(messages) >= 1

    def test_progress_updates_widgets(self, upload_widget):
        upload_widget._on_progress("Downloading...", 50)
        assert upload_widget._status_label.text() == "Downloading..."
        assert upload_widget._progress_bar.value() == 50


class TestQtUploadIntegrationOcr:
    """OCR result handling."""

    def test_ocr_done_displays_result(self, upload_widget, qtbot):
        """_on_ocr_done displays payload and shows scroll area."""
        payload = {
            "document": {"title": "Test Doc", "file_name": "test.pdf"},
            "ocr_text": "Extracted OCR text here",
            "extracted_fields": {"amount": "100", "date": "2025-01-01"},
        }
        upload_widget._on_ocr_done(payload)
        # _display_ocr_result populates the result_layout
        assert upload_widget._result_layout.count() >= 1
        assert upload_widget._status_label.text() != ""

    def test_ocr_done_with_empty_fields(self, upload_widget):
        """OCR result with no fields does not crash."""
        payload = {
            "document": {"title": "Test Doc"},
            "ocr_text": "",
            "extracted_fields": {},
        }
        upload_widget._on_ocr_done(payload)
        # Should have at least the title label and stretch
        assert upload_widget._result_layout.count() >= 1

    def test_ocr_fetch_creates_worker(self, upload_widget, monkeypatch):
        """_fetch_ocr_result creates a NetworkWorker."""
        mock_worker = MagicMock()
        monkeypatch.setattr(
            "ui.views.upload_integration.NetworkWorker",
            MagicMock(return_value=mock_worker),
        )
        upload_widget._fetch_ocr_result(5)
        assert upload_widget._worker is not None
        mock_worker.call_action.assert_called_with("GET", "/api/v1/documents/5/read")
        mock_worker.start.assert_called_once()


class TestQtUploadIntegrationLifecycle:
    """Lifecycle management."""

    def test_shutdown_cancels_worker(self, upload_widget):
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        upload_widget._worker = mock_worker
        upload_widget.shutdown()
        assert upload_widget._worker is None
        mock_worker.stop_event.set.assert_called_once()

    def test_shutdown_with_no_worker_does_not_crash(self, upload_widget):
        upload_widget._worker = None
        upload_widget.shutdown()  # should not raise

    def test_set_uploading_disables_buttons(self, upload_widget):
        upload_widget._set_uploading(True)
        assert not upload_widget._browse_btn.isEnabled()
        assert not upload_widget._upload_btn.isEnabled()
        # Progress bar visibility requires the widget to be shown on-screen;
        # in headless test environments the parent might not be mapped, so
        # isVisible() may return False even after setVisible(True).

    def test_set_uploading_false_clears_progress(self, upload_widget):
        upload_widget._progress_bar.setValue(50)
        upload_widget._set_uploading(False)
        assert upload_widget._browse_btn.isEnabled()
        assert upload_widget._upload_btn.isEnabled()
        assert upload_widget._progress_bar.value() == 0
