"""PySide6 Physical Archive tab — upload → OCR → Review → Confirm workflow.

Supports drag-and-drop and browse-based file uploads for paper document
digitisation (PDF, JPG, PNG) with per-document progress and a review
panel for low-confidence OCR results.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import Qt, QEvent, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import Btn, Card, CardHeader, EmptyState, Label, StatusBadge
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_INFO_DEFAULT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    DANGER_TEXT,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    SP,
    SUCCESS_TEXT,
    WARNING_TEXT,
)

logger = logging.getLogger(__name__)

# ── Graceful service imports ──────────────────────────────────────────

try:
    from services.migration.physical_archive_service import PhysicalArchiveService
    from services.migration.progress_tracker import MigrationProgressTracker
except ImportError:
    PhysicalArchiveService = None
    MigrationProgressTracker = None

SUPPORTED_FORMATS = t("migration.physical_formats", "Supported: PDF, JPG, PNG")


class ImmigratePhysicalTab(QWidget):
    """Tab 2: Import from physical archive (paper documents)."""

    processing_complete = Signal(dict)

    def __init__(self, parent, db=None):
        super().__init__(parent)
        self.db = db
        self._archive_svc = (
            PhysicalArchiveService(db) if (db and PhysicalArchiveService) else None
        )

        # State
        self._selected_files: list[str] = []
        self._processing = False
        self._doc_results: list[dict] = []

        self.processing_complete.connect(self._on_batch_complete)

        self._build_ui()

    # ── UI build ──────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(SP["6"], SP["4"], SP["6"], SP["6"])
        main_layout.setSpacing(SP["5"])
        main_layout.setAlignment(Qt.AlignTop)

        # ── 1. Upload area card ──────────────────────────────────────
        self._upload_card = Card(None)
        upload_layout = self._upload_card.layout()
        CardHeader(
            upload_layout,
            t("migration.physical_title", "Upload Documents"),
            subtitle=t(
                "migration.physical_subtitle",
                "Drag & drop or browse to upload paper documents for OCR processing",
            ),
        )

        # Drop zone
        self._drop_zone = QFrame()
        self._drop_zone.setAcceptDrops(True)
        self._drop_zone.setMinimumHeight(140)
        self._drop_zone.setStyleSheet(
            f"QFrame{{"
            f"  background: {COLOR_BG_ELEVATED};"
            f"  border: 1px dashed {COLOR_BORDER_MEDIUM};"
            f"  border-radius: 8px;"
            f"}}"
            f"QFrame:hover{{"
            f"  border-color: {COLOR_INFO_DEFAULT};"
            f"}}"
        )
        drop_layout = QVBoxLayout(self._drop_zone)
        drop_layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        drop_layout.setSpacing(SP["2"])
        drop_layout.setAlignment(Qt.AlignCenter)

        drop_icon = QLabel("\u2B06")  # up arrow
        drop_icon.setAlignment(Qt.AlignCenter)
        drop_icon.setStyleSheet(
            f"font-size: 28px; color: {COLOR_TEXT_TERTIARY}; background: transparent; border: none;"
        )
        drop_layout.addWidget(drop_icon)

        drop_hint = QLabel(
            t(
                "migration.physical_drop_hint",
                "Drop files here or click to select",
            )
        )
        drop_hint.setAlignment(Qt.AlignCenter)
        drop_hint.setStyleSheet(
            f"font-size: {FONT_SIZE_BASE}px; font-weight: {FONT_WEIGHT_MEDIUM}; "
            f"color: {COLOR_TEXT_SECONDARY}; background: transparent; border: none;"
        )
        drop_layout.addWidget(drop_hint)

        drop_sub = QLabel(SUPPORTED_FORMATS)
        drop_sub.setAlignment(Qt.AlignCenter)
        drop_sub.setStyleSheet(
            f"font-size: {FONT_SIZE_SM}px; color: {COLOR_TEXT_TERTIARY}; background: transparent; border: none;"
        )
        drop_layout.addWidget(drop_sub)

        # Click to browse
        self._drop_zone.mousePressEvent = lambda e: self._browse_files()

        # Install event filter so the drop zone catches drag-drop events
        self._drop_zone.installEventFilter(self)

        upload_layout.addWidget(self._drop_zone)

        # File list label
        self._file_count_label = Label(
            None,
            t("migration.physical_no_files", "No files selected"),
            role="secondary",
        )
        upload_layout.addWidget(self._file_count_label)

        # Start / Cancel buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SP["2"])
        self._btn_start = Btn(
            None,
            t("migration.physical_start", "Start Processing"),
            variant="primary",
            command=self._start_processing,
        )
        self._btn_start.setEnabled(False)
        btn_row.addWidget(self._btn_start)

        self._btn_cancel = Btn(
            None,
            t("migration.physical_cancel", "Cancel"),
            variant="secondary",
            command=self._cancel_processing,
        )
        self._btn_cancel.setEnabled(False)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addStretch()
        upload_layout.addLayout(btn_row)

        main_layout.addWidget(self._upload_card)

        # ── 2. Processing progress card (hidden initially) ──────────
        self._progress_card = Card(None)
        self._progress_card.setVisible(False)
        progress_layout = self._progress_card.layout()
        CardHeader(
            progress_layout,
            t("migration.physical_progress_title", "Processing Progress"),
        )

        self._batch_progress = QProgressBar()
        self._batch_progress.setFixedHeight(6)
        self._batch_progress.setTextVisible(False)
        progress_layout.addWidget(self._batch_progress)

        self._progress_status = Label(None, "", role="muted")
        progress_layout.addWidget(self._progress_status)

        main_layout.addWidget(self._progress_card)

        # ── 3. Document status table ────────────────────────────────
        self._doc_table_card = Card(None)
        self._doc_table_card.setVisible(False)
        doc_table_layout = self._doc_table_card.layout()
        CardHeader(
            doc_table_layout,
            t("migration.physical_docs_title", "Documents"),
        )

        self._doc_table = QTableWidget()
        self._doc_table.setColumnCount(5)
        self._doc_table.setHorizontalHeaderLabels([
            t("migration.physical_col_file", "Filename"),
            t("migration.physical_col_status", "Status"),
            t("migration.physical_col_type", "Doc Type"),
            t("migration.physical_col_confidence", "Confidence"),
            t("migration.physical_col_actions", "Actions"),
        ])
        self._doc_table.horizontalHeader().setStretchLastSection(True)
        self._doc_table.setAlternatingRowColors(True)
        self._doc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._doc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._doc_table.verticalHeader().setVisible(False)
        self._doc_table.setMinimumHeight(120)
        doc_table_layout.addWidget(self._doc_table, 1)

        main_layout.addWidget(self._doc_table_card)

        # ── 4. Review card (for low-confidence docs, hidden) ────────
        self._review_card = Card(None)
        self._review_card.setVisible(False)
        review_layout = self._review_card.layout()
        CardHeader(
            review_layout,
            t("migration.physical_review_title", "Review Required"),
            subtitle=t(
                "migration.physical_review_subtitle",
                "Some documents need manual confirmation before saving",
            ),
        )

        self._review_container = QVBoxLayout()
        review_layout.addLayout(self._review_container)

        main_layout.addWidget(self._review_card)

        # ── Empty state (no service) ─────────────────────────────────
        self._empty_state = EmptyState(
            None,
            icon_name="fa5s.file-import",
            title=t("migration.physical_empty_title", "Physical Archive"),
            subtitle=t(
                "migration.physical_empty_subtitle",
                "Upload paper documents to digitise and import them into Operion.",
            ),
        )
        self._empty_state.setVisible(False)
        main_layout.addWidget(self._empty_state)

    # ── Drag & drop ──────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        """Forward drag-drop events from the drop zone to private handlers."""
        if obj is self._drop_zone:
            if event.type() == QEvent.DragEnter:
                self._handle_drag_enter(event)
                return True
            elif event.type() == QEvent.DragLeave:
                self._handle_drag_leave(event)
                return True
            elif event.type() == QEvent.Drop:
                self._handle_drop(event)
                return True
        return super().eventFilter(obj, event)

    def _handle_drag_enter(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._drop_zone.setStyleSheet(
                f"QFrame{{"
                f"  background: {COLOR_BG_ELEVATED};"
                f"  border: 1px dashed {COLOR_INFO_DEFAULT};"
                f"  border-radius: 8px;"
                f"}}"
            )

    def _handle_drag_leave(self, event):
        self._drop_zone.setStyleSheet(
            f"QFrame{{"
            f"  background: {COLOR_BG_ELEVATED};"
            f"  border: 1px dashed {COLOR_BORDER_MEDIUM};"
            f"  border-radius: 8px;"
            f"}}"
            f"QFrame:hover{{"
            f"  border-color: {COLOR_INFO_DEFAULT};"
            f"}}"
        )

    def _handle_drop(self, event: QDropEvent):
        self._drop_zone.setStyleSheet(
            f"QFrame{{"
            f"  background: {COLOR_BG_ELEVATED};"
            f"  border: 1px dashed {COLOR_BORDER_MEDIUM};"
            f"  border-radius: 8px;"
            f"}}"
            f"QFrame:hover{{"
            f"  border-color: {COLOR_INFO_DEFAULT};"
            f"}}"
        )
        accepted = False
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and self._is_supported(path):
                self._selected_files.append(path)
                accepted = True
        if accepted:
            self._update_file_count()
            self._btn_start.setEnabled(True)

    # ── Event handlers ───────────────────────────────────────────────

    def _browse_files(self):
        """Open a multi-file dialog for supported document types."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            t("migration.physical_select_files", "Select documents to upload"),
            "",
            "Documents (*.pdf *.PDF *.jpg *.JPG *.jpeg *.JPEG *.png *.PNG);;All files (*.*)",
        )
        if files:
            self._selected_files.extend(files)
            self._update_file_count()
            self._btn_start.setEnabled(True)

    def _is_supported(self, path: str) -> bool:
        """Check if the file extension is supported."""
        ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
        return ext in ("pdf", "jpg", "jpeg", "png")

    def _update_file_count(self):
        """Update the file count label."""
        count = len(self._selected_files)
        if count == 0:
            self._file_count_label.setText(
                t("migration.physical_no_files", "No files selected")
            )
        else:
            self._file_count_label.setText(
                t("migration.physical_files_selected", "{count} file(s) selected").format(
                    count=count
                )
            )

    def _start_processing(self):
        """Process all selected files in a background thread."""
        if not self._selected_files or not self._archive_svc:
            return

        self._processing = True
        self._btn_start.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._drop_zone.setAcceptDrops(False)

        # Reset state
        self._doc_results = []
        self._doc_table.setRowCount(len(self._selected_files))
        for i, fpath in enumerate(self._selected_files):
            fname = fpath.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            self._doc_table.setItem(i, 0, QTableWidgetItem(fname))
            badge = StatusBadge(None, "loading", t("migration.status_pending", "Pending"))
            self._doc_table.setCellWidget(i, 1, badge)
            self._doc_table.setItem(i, 2, QTableWidgetItem("\u2014"))
            self._doc_table.setItem(i, 3, QTableWidgetItem("\u2014"))
            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(SP["1"], 0, SP["1"], 0)
            action_widget.setStyleSheet("background: transparent;")
            action_layout.addStretch()
            self._doc_table.setCellWidget(i, 4, action_widget)

        self._doc_table_card.setVisible(True)
        self._progress_card.setVisible(True)
        self._progress_status.setText(
            t("migration.physical_processing", "Processing {count} document(s)\u2026").format(
                count=len(self._selected_files)
            )
        )
        self._batch_progress.setValue(0)
        self._batch_progress.setMaximum(len(self._selected_files))

        files_copy = list(self._selected_files)

        def process_batch():
            try:
                for idx, fpath in enumerate(files_copy):
                    if not self._processing:
                        break
                    try:
                        result = self._archive_svc.process_document(fpath)
                    except Exception as exc:
                        logger.exception("Document processing error")
                        result = {
                            "file_path": fpath,
                            "success": False,
                            "error": str(exc),
                        }
                    # Update table on GUI thread via signal
                    self.processing_complete.emit({"index": idx, "result": result})
            except Exception as exc:
                logger.exception("Batch processing error")
                self.processing_complete.emit(
                    {"error": str(exc), "batch_done": True}
                )

        threading.Thread(target=process_batch, daemon=True).start()

    def _cancel_processing(self):
        """Cancel the ongoing batch."""
        self._processing = False
        self._btn_cancel.setEnabled(False)
        self._btn_start.setEnabled(True)
        self._drop_zone.setAcceptDrops(True)
        self._progress_status.setText(
            t("migration.physical_cancelled", "Processing cancelled")
        )

    def _on_doc_processed(self, result: dict):
        """Update the document table row with processing results."""
        idx = result.get("index", 0)
        doc = result.get("result", {})
        status_key = "success" if doc.get("success") else "error"
        status_text = (
            t("migration.status_complete", "Complete")
            if doc.get("success")
            else t("migration.status_error", "Error")
        )

        if idx < self._doc_table.rowCount():
            badge = StatusBadge(
                None,
                status_key,
                status_text,
            )
            self._doc_table.setCellWidget(idx, 1, badge)

            doc_type = doc.get("doc_type", "\u2014")
            confidence = doc.get("confidence", "\u2014")
            self._doc_table.setItem(idx, 2, QTableWidgetItem(str(doc_type)))
            self._doc_table.setItem(idx, 3, QTableWidgetItem(str(confidence)))

            # Add review button for low confidence
            try:
                conf_val = float(confidence) if confidence != "\u2014" else 1.0
            except (ValueError, TypeError):
                conf_val = 1.0

            if doc.get("success") and conf_val < 0.7:
                review_btn = Btn(
                    None,
                    t("migration.physical_review", "Review"),
                    variant="primary",
                    command=lambda d=doc: self._show_review_panel(d),
                )
                self._doc_table.setCellWidget(idx, 4, review_btn)

    def _on_batch_complete(self, payload: dict):
        """Handle processing complete or error."""
        if "error" in payload and payload.get("batch_done"):
            self._progress_status.setText(
                t("migration.physical_batch_error", "Batch processing failed: {error}").format(
                    error=payload["error"]
                )
            )
            self._reset_after_processing()
            return

        # Single doc result
        self._on_doc_processed(payload)

        # Update progress
        done = sum(
            1 for r in range(self._doc_table.rowCount())
            if self._doc_table.cellWidget(r, 1) is not None
        )
        self._batch_progress.setValue(done)

        if done >= self._batch_progress.maximum():
            self._progress_status.setText(
                t("migration.physical_batch_done", "All documents processed")
            )
            self._reset_after_processing()

    def _reset_after_processing(self):
        """Reset UI state after processing ends."""
        self._processing = False
        self._btn_cancel.setEnabled(False)
        self._btn_start.setEnabled(True)
        self._drop_zone.setAcceptDrops(True)
        self._selected_files = []
        self._update_file_count()

    def _show_review_panel(self, doc_result: dict):
        """Show a review form for a low-confidence document."""
        self._review_card.setVisible(True)

        # Clear previous review widgets
        while self._review_container.count():
            item = self._review_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        review_label = Label(
            None,
            t(
                "migration.physical_review_doc",
                "Review: {file}".format(file=doc_result.get("file_path", "")),
            ),
            role="default",
        )
        self._review_container.addWidget(review_label)

        # Confirmation button
        confirm_btn = Btn(
            None,
            t("migration.physical_confirm", "Confirm && Save"),
            variant="primary",
            command=lambda: self._on_confirm_document(
                doc_result.get("doc_id"), None
            ),
        )
        self._review_container.addWidget(confirm_btn)

    def _on_confirm_document(self, doc_id, corrections):
        """Confirm and save a reviewed document."""
        if not self._archive_svc:
            return

        try:
            self._archive_svc.confirm_document(doc_id, corrections or {})
            logger.info("Document %s confirmed and saved", doc_id)
        except Exception as exc:
            logger.exception("Failed to confirm document %s", doc_id)

        self._review_card.setVisible(False)

    def _update_stats(self):
        """Refresh statistics (placeholder — called from main view)."""
        pass
