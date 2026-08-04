"""Complete upload integration example: file pick → upload → OCR → display.

Demonstrates the reference implementation required by the production
cutover plan (§139-142).  A user selects a PDF, the file is streamed
via a background ``NetworkWorker`` to ``/api/v1/documents/upload``, the
OCR result is fetched, and the extracted fields are displayed in a
scrollable panel with a progress bar.

Usage as a reusable widget::

    upload_widget = UploadIntegrationWidget(parent, api_client=my_api_client)
    layout.addWidget(upload_widget)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from client.api_client import ApiClient
from client.config import ClientConfig, get_client_config
from client.network.network_worker import NetworkWorker
from services.i18n import t
from ui.components import Btn
from ui.design_tokens import SP
from ui.widgets import SectionHeader

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 50 * 1024 * 1024


class UploadIntegrationWidget(QWidget):
    """Self-contained document upload + OCR viewer.

    Signals
    -------
    document_uploaded : Signal(int)
        Emitted with the *document_id* after a successful upload+OCR cycle.
    """

    document_uploaded = Signal(int)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        api_client: Optional[ApiClient] = None,
        config: Optional[ClientConfig] = None,
    ) -> None:
        super().__init__(parent)
        self._api = api_client or ApiClient(config=config or get_client_config())
        self._worker: Optional[NetworkWorker] = None
        self._selected_path: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["3"])

        header = SectionHeader(self, t("upload.title", default="Upload & OCR"))
        layout.addWidget(header)

        pick_row = QWidget(self)
        pick_layout = QHBoxLayout(pick_row)
        pick_layout.setContentsMargins(0, 0, 0, 0)
        pick_layout.setSpacing(SP["2"])

        self._path_label = QLabel(t("upload.no_file", default="No file selected"), pick_row)
        self._path_label.setProperty("fontRole", "small")
        self._path_label.setWordWrap(True)
        pick_layout.addWidget(self._path_label, 1)

        self._browse_btn = Btn(
            pick_row, text=t("upload.browse", default="Browse..."),
            command=self._on_browse_clicked, variant="secondary",
        )
        pick_layout.addWidget(self._browse_btn)

        layout.addWidget(pick_row)

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("", self)
        self._status_label.setProperty("fontRole", "small")
        self._status_label.setProperty("role", "status-label")
        layout.addWidget(self._status_label)

        self._upload_btn = Btn(
            self, text=t("upload.start", default="Upload & Run OCR"),
            command=self._on_upload_clicked, variant="primary",
        )
        self._upload_btn.setEnabled(False)
        layout.addWidget(self._upload_btn)

        self._result_scroll = QScrollArea(self)
        self._result_scroll.setWidgetResizable(True)
        self._result_scroll.setFrameShape(QFrame.NoFrame)
        self._result_content = QWidget(self._result_scroll)
        self._result_layout = QVBoxLayout(self._result_content)
        self._result_layout.setContentsMargins(0, 0, 0, 0)
        self._result_layout.setSpacing(SP["1"])
        self._result_layout.setAlignment(Qt.AlignTop)
        self._result_scroll.setWidget(self._result_content)
        self._result_scroll.setVisible(False)
        layout.addWidget(self._result_scroll, 1)

    def shutdown(self) -> None:
        self._cancel_worker()

    def _cancel_worker(self) -> None:
        worker = self._worker
        if worker is None:
            return
        try:
            worker.stop_event.set()
            worker.requestInterruption()
            if worker.isRunning():
                worker.wait(3000)
        except Exception:
            pass
        self._worker = None

    def _on_browse_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("upload.title", default="Select Document"),
            "",
            "PDF (*.pdf);;Images (*.png *.jpg *.jpeg);;All Files (*.*)",
        )
        if not path:
            return
        import os
        size = os.path.getsize(path)
        if size > MAX_UPLOAD_SIZE:
            QMessageBox.warning(
                self,
                t("upload.too_large_title", default="File too large"),
                t("upload.too_large_msg", default="Maximum upload size is 50 MB."),
            )
            return
        self._selected_path = path
        self._path_label.setText(os.path.basename(path))
        self._upload_btn.setEnabled(True)

    def _on_upload_clicked(self) -> None:
        if not self._selected_path:
            return
        self._cancel_worker()
        self._set_uploading(True)
        worker = NetworkWorker(config=self._api._config if hasattr(self._api, '_config') else None)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_upload_done)
        worker.error.connect(self._on_upload_error)
        worker.upload(
            path="/api/v1/documents/upload",
            file_path=self._selected_path,
            form_data={"uploaded_by": "user", "category": ""},
        )
        self._worker = worker
        self._status_label.setText(t("upload.uploading", default="Uploading..."))
        worker.start()

    def _set_uploading(self, uploading: bool) -> None:
        self._browse_btn.setEnabled(not uploading)
        self._upload_btn.setEnabled(not uploading)
        self._progress_bar.setVisible(uploading)
        if not uploading:
            self._progress_bar.setValue(0)

    def _on_progress(self, label: str, percent: int) -> None:
        self._status_label.setText(label)
        self._progress_bar.setValue(percent)

    def _on_upload_done(self, payload: Dict[str, Any]) -> None:
        self._set_uploading(False)
        self._worker = None
        doc_id = payload.get("id", 0)
        self._status_label.setText(
            t("upload.done", default="Upload complete. Document #{id}").format(id=doc_id)
        )
        self.document_uploaded.emit(doc_id)
        self._fetch_ocr_result(doc_id)

    def _fetch_ocr_result(self, doc_id: int) -> None:
        self._cancel_worker()
        worker = NetworkWorker(config=self._api._config if hasattr(self._api, '_config') else None)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_ocr_done)
        worker.error.connect(self._on_upload_error)
        worker.call_action("GET", f"/api/v1/documents/{doc_id}/read")
        self._worker = worker
        self._status_label.setText(
            t("upload.fetching_ocr", default="Fetching OCR results...")
        )
        worker.start()

    def _on_ocr_done(self, payload: Dict[str, Any]) -> None:
        self._worker = None
        self._status_label.setText(
            t("upload.ocr_done", default="OCR complete.")
        )
        self._display_ocr_result(payload)

    def _on_upload_error(self, msg: str) -> None:
        self._set_uploading(False)
        self._worker = None
        self._status_label.setText(t("upload.error", default="Error") + f": {msg}")
        QMessageBox.critical(
            self,
            t("upload.error_title", default="Upload Error"),
            str(msg),
        )

    def _display_ocr_result(self, payload: Dict[str, Any]) -> None:
        while self._result_layout.count():
            item = self._result_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        self._result_scroll.setVisible(True)

        doc = payload.get("document", {})
        ocr_text = payload.get("ocr_text", "")
        fields = payload.get("extracted_fields", {})

        title = doc.get("title", doc.get("file_name", ""))
        title_lbl = QLabel(title, self._result_content)
        title_lbl.setProperty("fontRole", "body_bold")
        self._result_layout.addWidget(title_lbl)

        if ocr_text:
            ocr_lbl = QLabel(ocr_text[:500], self._result_content)
            ocr_lbl.setProperty("fontRole", "small")
            ocr_lbl.setWordWrap(True)
            self._result_layout.addWidget(ocr_lbl)

        if fields:
            fields_header = QLabel(t("upload.extracted_fields", default="Extracted Fields"), self._result_content)
            fields_header.setProperty("fontRole", "label")
            self._result_layout.addWidget(fields_header)
            for key, value in sorted(fields.items()):
                entry = QLabel(f"  {key}: {value}", self._result_content)
                entry.setProperty("fontRole", "mono")
                entry.setWordWrap(True)
                self._result_layout.addWidget(entry)

        self._result_layout.addStretch(1)
