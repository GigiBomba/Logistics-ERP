"""Main QtAutomationView class — UI, lifecycle, pipeline listing.

Contains the drop zone, run cards, detail panel, and the top-level
:class:`QtAutomationView` widget that ties everything together.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from repositories.pipeline_repository import PipelineRepository
from services.i18n import t
from ui.components import Btn, PageTitle
from ui.design_tokens import (
    ACCENT,
    ACCENT_DIM,
    ACCENT_HOVER,
    ACCENT_TEXT,
    BG_SURFACE,
    BORDER_DEFAULT,
    BORDER_FAINT,
    DANGER_TEXT,
    INFO,
    SP,
    SUCCESS_TEXT,
    TEXT_MUTED,
)
from ui.views.automation_view.automation_queue import QueueManagementMixin
from ui.views.automation_worker import PipelineWorker, register_standalone_document
from ui.widgets import StyledRadioButton

logger = logging.getLogger(__name__)


# ======================================================================
# Module-level helpers
# ======================================================================

_RUN_STATUS_COLORS = {
    "imported":     TEXT_MUTED,
    "import":       TEXT_MUTED,
    "processing":   INFO,
    "ocr":          ACCENT,
    "matched":      ACCENT_TEXT,
    "complete":     SUCCESS_TEXT,
    "failed":       DANGER_TEXT,
}


def _progress_from_status(status: str) -> int:
    return {
        "imported": 5,
        "import": 5,
        "processing": 25,
        "processed": 50,
        "ocr": 50,
        "matched": 75,
        "complete": 100,
        "failed": 100,
    }.get(status, 5)


def _subtitle_for_run(run: dict[str, Any]) -> str:
    status = run.get("status", "")
    if status == "failed":
        msg = (run.get("error_message") or "").strip()
        return f"\u274c {msg[:100]}" if msg else "\u274c Failed"
    if status == "complete":
        trip_id = run.get("matched_trip_id")
        return f"\u2705 Linked to trip #{trip_id}" if trip_id else "\u2705 Complete"
    if status == "processed":
        return "\U0001F4C4 Processed \u2014 awaiting action"
    return run.get("stage", "\u2014")


# ======================================================================
# Drop zone
# ======================================================================


class DropZone(QFrame):
    """A large framed area that accepts file drops or a click."""

    files_dropped = Signal(list)   # list of file paths

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("automationDropZone")
        self.setMinimumHeight(120)
        self.setStyleSheet(
            f"QFrame#automationDropZone {{ border: 2px dashed {BORDER_DEFAULT}; "
            f"border-radius: 8px; background: {BG_SURFACE}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setAlignment(Qt.AlignCenter)
        title = QLabel(t("automation.drop_title", default="Drop images or PDFs here"))
        title.setProperty("fontRole", "h3")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel(t(
            "automation.drop_subtitle",
            default="\u2026or click to browse. Supported: JPG, PNG, PDF, TIFF, HEIC.",
        ))
        sub.setProperty("fontRole", "muted")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(sub)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                t("automation.browse_title", default="Select document(s) to import"),
                "",
                "Documents (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp *.heic)",
            )
            if files:
                self.files_dropped.emit(files)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(
                f"QFrame#automationDropZone {{ border: 2px solid {ACCENT}; "
                f"border-radius: 8px; background: {BG_SURFACE}; }}"
            )

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(
            f"QFrame#automationDropZone {{ border: 2px dashed {BORDER_DEFAULT}; "
            f"border-radius: 8px; background: {BG_SURFACE}; }}"
        )

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet(
            f"QFrame#automationDropZone {{ border: 2px dashed {BORDER_DEFAULT}; "
            f"border-radius: 8px; background: {BG_SURFACE}; }}"
        )
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)


# ======================================================================
# Run card
# ======================================================================


class _RunCard(QFrame):
    """One pipeline run shown as a card in the run list."""

    clicked = Signal(int)              # run_id

    def __init__(self, run: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.run_id = int(run["id"])
        self.setObjectName("automationRunCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            f"QFrame#automationRunCard {{ background: {BG_SURFACE}; "
            f"border: 1px solid {BORDER_FAINT}; border-radius: 6px; }}"
        )
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["3"], SP["2"], SP["3"], SP["2"])
        layout.setSpacing(SP["1"])

        self._title = QLabel(run.get("source_file_name") or f"Run #{self.run_id}")
        self._title.setProperty("fontRole", "body_bold")
        layout.addWidget(self._title)

        status_row = QHBoxLayout()
        self._status_dot = QLabel("\u25cf")
        self._status_dot.setStyleSheet(f"color: {_RUN_STATUS_COLORS.get(run.get('status', 'imported'), TEXT_MUTED)};")
        status_row.addWidget(self._status_dot)
        self._stage_lbl = QLabel(run.get("stage") or "\u2014")
        self._stage_lbl.setProperty("fontRole", "small")
        status_row.addWidget(self._stage_lbl)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(_progress_from_status(run.get("status", "")))
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        layout.addWidget(self._progress)

        self._subtitle = QLabel()
        self._subtitle.setProperty("fontRole", "muted")
        self._subtitle.setWordWrap(True)
        self._subtitle.setText(_subtitle_for_run(run))
        layout.addWidget(self._subtitle)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.run_id)

    def update(self, run: dict[str, Any]) -> None:
        """Refresh all visible fields without re-creating the widget."""
        new_title = run.get("source_file_name") or f"Run #{run.get('id', self.run_id)}"
        if self._title.text() != new_title:
            self._title.setText(new_title)
        self._stage_lbl.setText(run.get("stage") or "\u2014")
        self._status_dot.setStyleSheet(
            f"color: {_RUN_STATUS_COLORS.get(run.get('status', ''), TEXT_MUTED)};"
        )
        self._progress.setValue(_progress_from_status(run.get("status", "")))
        new_subtitle = _subtitle_for_run(run)
        if self._subtitle.text() != new_subtitle:
            self._subtitle.setText(new_subtitle)


# ======================================================================
# Run detail panel
# ======================================================================


class _RunDetailPanel(QFrame):
    """Right-side panel \u2014 preview + OCR fields + match + actions."""

    prepare_clicked = Signal(int)       # trip_id
    send_clicked = Signal(int)          # trip_id
    link_requested = Signal(int, int)   # run_id, trip_id
    skip_and_package_clicked = Signal(int)  # run_id
    delete_requested = Signal(int)      # run_id

    def __init__(self, parent: QWidget | None = None, db=None, pipeline_repo=None, document_repo=None) -> None:
        super().__init__(parent)
        self.setObjectName("automationDetailPanel")
        self._db = db
        self._pipeline_repo = pipeline_repo
        self._document_repo = document_repo
        self._current_trip_id: int | None = None
        self._current_run_id: int | None = None
        self._current_mode: str = "advanced"
        self._candidate_links: list[QPushButton] = []
        self._build_ui()
        self.clear()
        self._prepare_btn.clicked.connect(self._on_prepare_clicked)
        self._send_btn.clicked.connect(self._on_send_clicked)
        self._skip_btn.clicked.connect(self._on_skip_clicked)

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _style_primary_btn(btn: QPushButton) -> None:
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {ACCENT};"
            f"  color: {ACCENT_TEXT};"
            f"  border: none;"
            f"  border-radius: 6px;"
            f"  padding: 8px 16px;"
            f"  font-size: 13px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {ACCENT_HOVER};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background: {ACCENT};"
            f"}}"
            f"QPushButton:disabled {{"
            f"  background: {BORDER_FAINT};"
            f"  color: {TEXT_MUTED};"
            f"}}"
        )

    @staticmethod
    def _style_secondary_btn(btn: QPushButton) -> None:
        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {BG_SURFACE};"
            f"  color: {ACCENT_TEXT};"
            f"  border: 1px solid {BORDER_DEFAULT};"
            f"  border-radius: 6px;"
            f"  padding: 8px 16px;"
            f"  font-size: 13px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  border: 1px solid {ACCENT};"
            f"  background: {ACCENT_DIM};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background: {ACCENT};"
            f"  color: {ACCENT_TEXT};"
            f"}}"
            f"QPushButton:disabled {{"
            f"  background: {BORDER_FAINT};"
            f"  color: {TEXT_MUTED};"
            f"  border: 1px solid transparent;"
            f"}}"
        )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["3"])
        self._title = QLabel(t("automation.detail_title", default="Select a run to view details"))
        self._title.setProperty("fontRole", "h3")
        layout.addWidget(self._title)

        self._fields_box = QLabel()
        self._fields_box.setWordWrap(True)
        self._fields_box.setProperty("fontRole", "body")
        self._fields_box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._fields_box.setStyleSheet(f"color: {TEXT_MUTED};")
        layout.addWidget(self._fields_box)

        # Simple-mode status label (hidden by default)
        self._simple_status = QLabel()
        self._simple_status.setWordWrap(True)
        self._simple_status.setProperty("fontRole", "body_bold")
        self._simple_status.setStyleSheet(f"color: {ACCENT_TEXT};")
        self._simple_status.hide()
        layout.addWidget(self._simple_status)

        # Candidate manual selection area (hidden by default)
        self._candidates_box = QLabel()
        self._candidates_box.setProperty("fontRole", "small")
        self._candidates_box.setStyleSheet(f"color: {ACCENT};")
        self._candidates_box.setWordWrap(True)
        self._candidates_box.hide()
        layout.addWidget(self._candidates_box)

        self._candidate_links_container = QWidget()
        self._candidate_links_layout = QVBoxLayout(self._candidate_links_container)
        self._candidate_links_layout.setContentsMargins(0, 0, 0, 0)
        self._candidate_links_layout.setSpacing(SP["1"])
        self._candidate_links_container.hide()
        layout.addWidget(self._candidate_links_container)

        # Search-all-trips button (hidden by default)
        self._search_all_btn = QPushButton(
            "\U0001F50D  " + t("automation.search_trips", default="Search all trips\u2026")
        )
        self._style_secondary_btn(self._search_all_btn)
        self._search_all_btn.setCursor(Qt.PointingHandCursor)
        self._search_all_btn.clicked.connect(self._on_search_all_clicked)
        self._search_all_btn.hide()
        layout.addWidget(self._search_all_btn)

        # Related documents (hidden by default)
        self._related_label = QLabel()
        self._related_label.setProperty("fontRole", "small")
        self._related_label.setWordWrap(True)
        self._related_label.setStyleSheet(f"color: {TEXT_MUTED};")
        self._related_label.hide()
        layout.addWidget(self._related_label)

        # Action buttons
        action_row = QHBoxLayout()
        self._prepare_btn = QPushButton(
            t("automation.prepare_package", default="Prepare Customer Package")
        )
        self._send_btn = QPushButton(
            t("automation.send_documents", default="Send Documents")
        )
        self._skip_btn = QPushButton(
            t("automation.skip_package", default="Skip \u2014 Create Package")
        )
        for btn in (self._prepare_btn, self._send_btn):
            self._style_primary_btn(btn)
            btn.setEnabled(False)
        self._style_secondary_btn(self._skip_btn)
        self._skip_btn.hide()
        action_row.addWidget(self._prepare_btn)
        action_row.addWidget(self._send_btn)
        action_row.addWidget(self._skip_btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        # File action buttons (Delete / Copy / Download) \u2014 hidden by default
        file_actions = QHBoxLayout()
        self._delete_btn = QPushButton(
            t("automation.delete_run", default="\U0001F5D1 Delete")
        )
        self._copy_btn = QPushButton(
            t("automation.copy_run", default="\U0001F4CB Copy path")
        )
        self._download_btn = QPushButton(
            t("automation.download_run", default="\U0001F4E5 Download")
        )
        for btn in (self._delete_btn, self._copy_btn, self._download_btn):
            self._style_secondary_btn(btn)
            btn.hide()
        self._delete_btn.clicked.connect(self._on_delete_run)
        self._copy_btn.clicked.connect(self._on_copy_run)
        self._download_btn.clicked.connect(self._on_download_run)
        file_actions.addWidget(self._delete_btn)
        file_actions.addWidget(self._copy_btn)
        file_actions.addWidget(self._download_btn)
        file_actions.addStretch(1)
        layout.addLayout(file_actions)

        layout.addStretch(1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self._title.setText(t("automation.detail_title", default="Select a run to view details"))
        self._fields_box.setText("")
        self._fields_box.setStyleSheet(f"color: {TEXT_MUTED};")
        self._simple_status.hide()
        self._current_trip_id = None
        self._current_run_id = None
        self._prepare_btn.setEnabled(False)
        self._send_btn.setEnabled(False)
        self._skip_btn.hide()
        self._candidates_box.hide()
        self._candidate_links_container.hide()
        self._related_label.hide()
        self._delete_btn.hide()
        self._copy_btn.hide()
        self._download_btn.hide()
        for link in self._candidate_links:
            link.deleteLater()
        self._candidate_links.clear()

    def show_run(
        self,
        run: dict[str, Any],
        extracted: dict[str, Any],
        candidates: list[dict[str, Any]],
        mode: str = "advanced",
    ) -> None:
        self._current_mode = mode
        self._title.setText(run.get("source_file_name") or t("automation.run_label", default="Run #{}").format(run.get('id')))
        body = []
        body.append(
            f"<b>{t('automation.label_status', default='Status:')}</b> "
            f"{run.get('status')}  \u00b7  "
            f"<b>{t('automation.label_stage', default='Stage:')}</b> "
            f"{run.get('stage')}"
        )
        trip_id = run.get("matched_trip_id")
        if trip_id:
            body.append(
                f"<b>{t('automation.label_matched_trip', default='Matched trip:')}</b> "
                f"#{trip_id} (confidence {float(run.get('match_confidence') or 0):.0%})"
            )
        body.append(
            f"<br><b>{t('automation.label_extracted_fields', default='Extracted fields:')}</b>"
        )
        for key, value in extracted.items():
            if key == "raw_text":
                continue
            body.append(f"&nbsp;&nbsp;<b>{key}:</b> {value}")
        if candidates:
            body.append(
                f"<br><b>{t('automation.label_top_candidates', default='Top candidates:')}</b>"
            )
            for idx, c in enumerate(candidates[:5], 1):
                trip = c.get("trip") or {}
                body.append(
                    f"&nbsp;&nbsp;{idx}. Trip #{trip.get('id')} "
                    f"({trip.get('client_name')}, {trip.get('start_date')}) "
                    f"\u00b7 {float(c.get('confidence', 0)):.0%}"
                )
        if run.get("error_message"):
            body.append(f"<br><b>Error:</b> {run['error_message']}")
        self._fields_box.setText("<br>".join(body))
        self._fields_box.setStyleSheet(f"color: {TEXT_MUTED};")

        self._current_trip_id = int(trip_id) if trip_id else None
        self._current_run_id = int(run.get("id", 0)) if run.get("id") else None

        # Hide simple-mode UI elements by default.
        self._simple_status.hide()
        self._skip_btn.hide()
        self._candidates_box.hide()
        self._candidate_links_container.hide()
        self._search_all_btn.hide()
        for link in self._candidate_links:
            link.deleteLater()
        self._candidate_links.clear()

        # ------------------------------------------------------------------
        # Simple mode \u2014 show action panel when run has a processed
        # file and hasn't been matched to a trip yet.
        # ------------------------------------------------------------------
        has_file = bool(run.get("processed_pdf_path") or run.get("processed_file_path"))
        is_complete = run.get("status") == "complete"
        is_simple_awaiting = (
            mode == "simple"
            and has_file
            and not is_complete
            and not trip_id
        )
        if is_simple_awaiting:
            self._simple_status.setText(
                t(
                    "automation.simple_awaiting",
                    default="Document processed \u2014 choose an action below.",
                )
            )
            self._simple_status.show()

            if trip_id:
                self._fields_box.setText(
                    f"<b>Status:</b> processed  \u00b7  Linked to trip #{trip_id}"
                )
                self._fields_box.setStyleSheet(f"color: {TEXT_MUTED};")
            else:
                self._candidates_box.setText(
                    t(
                        "automation.simple_select_trip",
                        default="Optionally select a trip to associate this document with:",
                    )
                )
                self._candidates_box.show()

                if candidates:
                    for c in candidates:
                        self._add_candidate_button(c)
                    self._candidate_links_container.show()

                self._search_all_btn.show()
                self._skip_btn.show()
                self._skip_btn.setEnabled(True)
            return

        # ------------------------------------------------------------------
        # Advanced mode: buttons enabled only when complete + matched
        # ------------------------------------------------------------------
        complete = run.get("status") == "complete" and self._current_trip_id
        self._prepare_btn.setEnabled(bool(complete))
        self._send_btn.setEnabled(bool(complete))

        need_manual = run.get("stage") == "matching" and not trip_id and run.get("status") != "failed"
        if need_manual and candidates:
            self._candidates_box.setText(
                t("automation.select_trip", default="Select a trip to link this document to:")
            )
            self._candidates_box.show()
            for c in candidates:
                self._add_candidate_button(c)
            self._candidate_links_container.show()
            self._search_all_btn.show()
        else:
            self._search_all_btn.hide()

        # Show related documents (stored inside match_signals_json).
        related_ids = None
        raw_signals = run.get("match_signals_json")
        if raw_signals:
            try:
                signals = json.loads(raw_signals) if isinstance(raw_signals, str) else raw_signals
                related_ids = signals.get("related_document_ids") if isinstance(signals, dict) else None
            except (ValueError, TypeError):
                related_ids = None
        if related_ids:
            self._related_label.setText(
                f"\U0001F4C4 {t('automation.related_docs', default='Related documents:')} "
                f"{t('automation.label_document', default='Doc #{}').format('#'.join(str(i) for i in related_ids))}"
            )
            self._related_label.show()
        else:
            self._related_label.hide()

        # File action buttons (Delete / Copy / Download)
        has_file = bool(run.get("processed_pdf_path") or run.get("processed_file_path"))
        if self._current_run_id is not None and has_file:
            self._delete_btn.show()
            self._copy_btn.show()
            self._download_btn.show()
        else:
            self._delete_btn.hide()
            self._copy_btn.hide()
            self._download_btn.hide()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_search_all_clicked(self, event=None) -> None:
        """Open the trip search dialog so the user can manually pick a trip."""
        if self._current_run_id is None or self._db is None:
            return
        from ui.dialogs.trip_search_dialog import QtTripSearchDialog

        dlg = QtTripSearchDialog(
            self._db,
            parent=self.window() if self.window() else self,
        )
        if dlg.exec() == QDialog.Accepted:
            tid = dlg.selected_trip_id()
            if tid is not None:
                self.link_requested.emit(self._current_run_id, int(tid))

    def _add_candidate_button(self, candidate: dict[str, Any]) -> None:
        """Add a styled button for a trip candidate to the candidate list."""
        trip = candidate.get("trip") or {}
        tid = trip.get("id")
        if tid is None:
            return
        label = (
            f"Trip #{tid}  \u2014  {trip.get('client_name') or '?'}  "
            f"({trip.get('start_date') or '?'})"
        )
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        self._style_secondary_btn(btn)
        rid = self._current_run_id
        if rid is not None:
            btn.clicked.connect(
                lambda checked=False, t=tid, r=rid: self.link_requested.emit(r, int(t))
            )
        self._candidate_links_layout.addWidget(btn)
        self._candidate_links.append(btn)

    def _on_skip_clicked(self) -> None:
        """Simple mode: skip trip association and create a standalone package."""
        if self._current_run_id is not None:
            self.skip_and_package_clicked.emit(self._current_run_id)

    def _on_prepare_clicked(self) -> None:
        if self._current_trip_id is not None:
            self.prepare_clicked.emit(self._current_trip_id)

    def _on_send_clicked(self) -> None:
        if self._current_trip_id is not None:
            self.send_clicked.emit(self._current_trip_id)

    def _on_delete_run(self) -> None:
        """Delete the current pipeline run and its processed files."""
        if self._current_run_id is not None and self._db is not None:
            confirm = QMessageBox.question(
                self,
                t("automation.confirm_delete_title", default="Delete run"),
                t(
                    "automation.confirm_delete_msg",
                    default="Delete this pipeline run and its processed file?",
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return
            from repositories.pipeline_repository import PipelineRepository

            repo = self._pipeline_repo if self._pipeline_repo is not None else PipelineRepository(self._db)
            run = repo.get_run_by_id(self._current_run_id)
            if run:
                pdf = run.get("processed_pdf_path") or run.get("processed_file_path") or ""
                output_dir = os.path.dirname(pdf) if pdf and os.path.isfile(pdf) else ""
                repo.delete_run(self._current_run_id)
                if output_dir:
                    import shutil
                    with contextlib.suppress(Exception):
                        shutil.rmtree(output_dir, ignore_errors=True)
                doc_id = run.get("document_id")
                if doc_id:
                    try:
                        from repositories.document_repository import DocumentRepository
                        (self._document_repo if self._document_repo is not None else DocumentRepository(self._db)).delete(doc_id)
                    except Exception:
                        pass
            self.delete_requested.emit(self._current_run_id)

    def _on_copy_run(self) -> None:
        """Copy the processed file path to the clipboard."""
        if self._current_run_id is None or self._db is None:
            return
        from repositories.pipeline_repository import PipelineRepository

        run = (self._pipeline_repo if self._pipeline_repo is not None else PipelineRepository(self._db)).get_run_by_id(self._current_run_id)
        if run:
            pdf = run.get("processed_pdf_path") or run.get("processed_file_path") or ""
            if pdf and os.path.isfile(pdf):
                from PySide6.QtWidgets import QApplication

                cb = QApplication.clipboard()
                cb.setText(os.path.abspath(pdf))

    def _on_download_run(self) -> None:
        """Save the processed PDF to a user-chosen location."""
        if self._current_run_id is None or self._db is None:
            return
        from repositories.pipeline_repository import PipelineRepository

        run = (self._pipeline_repo if self._pipeline_repo is not None else PipelineRepository(self._db)).get_run_by_id(self._current_run_id)
        if run:
            pdf = run.get("processed_pdf_path") or run.get("processed_file_path") or ""
            if pdf and os.path.isfile(pdf):
                save_path, _ = QFileDialog.getSaveFileName(
                    self,
                    t("automation.save_pdf", default="Save document as\u2026"),
                    run.get("source_file_name", "document.pdf"),
                    "PDF (*.pdf)",
                )
                if save_path:
                    import shutil
                    try:
                        shutil.copy2(pdf, save_path)
                    except OSError as exc:
                        logger.error("Failed to copy PDF: %s", exc)


# ======================================================================
# Main automation view
# ======================================================================


class QtAutomationView(QueueManagementMixin, QWidget):
    """The 'Automation' tab inside the Document Center."""

    package_requested = Signal(int)         # trip_id
    send_requested = Signal(int)            # trip_id

    # Hard upper bound on concurrent pipeline workers.
    HARD_MAX_CONCURRENT_WORKERS = 8
    DEFAULT_MAX_CONCURRENT_WORKERS = 2
    MAX_WORKERS_SETTING_KEY = "automation_max_concurrent_workers"

    def _load_max_concurrent_workers(self) -> int:
        """Resolve the cap from settings, clamped to sane bounds."""
        configured = self.DEFAULT_MAX_CONCURRENT_WORKERS
        if self.prefs is not None:
            try:
                raw = self.prefs.get_setting(self.MAX_WORKERS_SETTING_KEY)
                if raw:
                    configured = int(raw)
            except (TypeError, ValueError):
                configured = self.DEFAULT_MAX_CONCURRENT_WORKERS
        return max(1, min(self.HARD_MAX_CONCURRENT_WORKERS, configured))

    @property
    def MAX_CONCURRENT_WORKERS(self) -> int:
        return self._max_concurrent_workers

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        prefs=None,
        ops=None,
        api_client=None,
        pipeline_repo=None,
        doc_repo=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.prefs = prefs
        self.ops = ops
        self._api_client = api_client
        self._pipeline_repo = pipeline_repo if pipeline_repo is not None else PipelineRepository(db)
        from repositories.document_repository import DocumentRepository

        self._doc_repo = doc_repo if doc_repo is not None else DocumentRepository(db)

        # Queue management state (initialised by the mixin)
        self._init_queue_management()

        self._max_concurrent_workers = self._load_max_concurrent_workers()
        self._mode: str = "advanced"

        from services.email_importer import EmailImporter
        self._email_importer = EmailImporter(self._on_files_dropped)

        from services.folder_watcher import FolderWatcher
        self._folder_watcher = FolderWatcher(self._on_files_dropped)

        self._build_ui()
        self._refresh_from_db()
        QTimer.singleShot(200, self._recover_stuck_runs)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SP["3"])

        header = QFrame()
        header.setStyleSheet(f"background: {BG_SURFACE}; border-bottom: 1px solid {BORDER_FAINT};")
        h = QHBoxLayout(header)
        h.setContentsMargins(SP["5"], SP["3"], SP["5"], SP["3"])
        h.addWidget(PageTitle(header, t("automation.title", default="Document Automation")))
        h.addStretch(1)
        refresh_btn = Btn(header, t("automation.refresh", default="Refresh"), variant="secondary",
                          command=self._refresh_from_db)
        h.addWidget(refresh_btn)
        root.addWidget(header)

        # Mode switch
        mode_row = QFrame()
        mode_row.setStyleSheet(f"background: {BG_SURFACE}; border-bottom: 1px solid {BORDER_FAINT};")
        mode_layout = QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(SP["5"], SP["2"], SP["5"], SP["2"])
        mode_layout.setSpacing(SP["2"])
        mode_label = QLabel(t("automation.mode_label", default="Mode:"))
        mode_label.setProperty("fontRole", "body_bold")
        mode_layout.addWidget(mode_label)
        self._radio_simple = StyledRadioButton(
            mode_row, t("automation.mode_simple", default="Simple"),
        )
        self._radio_advanced = StyledRadioButton(
            mode_row, t("automation.mode_advanced", default="Advanced"),
        )
        self._radio_advanced.setChecked(True)
        self._mode = "advanced"
        self._radio_simple.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self._radio_simple)
        mode_layout.addWidget(self._radio_advanced)
        mode_layout.addStretch(1)
        root.addWidget(mode_row)

        body = QHBoxLayout()
        body.setContentsMargins(SP["3"], 0, SP["3"], SP["3"])
        body.setSpacing(SP["3"])

        # Left: drop zone + run list
        left = QVBoxLayout()
        left.setSpacing(SP["3"])
        self._drop_zone = DropZone()
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        left.addWidget(self._drop_zone)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._run_list_holder = QWidget()
        self._run_list_layout = QVBoxLayout(self._run_list_holder)
        self._run_list_layout.setContentsMargins(0, 0, 0, 0)
        self._run_list_layout.setSpacing(SP["2"])
        self._run_list_layout.addStretch(1)
        scroll.setWidget(self._run_list_holder)
        left.addWidget(scroll, 1)
        body.addLayout(left, 4)

        # Right: detail panel
        self._detail = _RunDetailPanel(db=self.db)
        self._detail.prepare_clicked.connect(self._on_prepare_package)
        self._detail.send_clicked.connect(self._on_send_documents)
        self._detail.skip_and_package_clicked.connect(self._on_skip_and_package)
        self._detail.delete_requested.connect(self._on_detail_delete_run)
        body.addWidget(self._detail, 5)
        root.addLayout(body, 1)

    # ------------------------------------------------------------------
    # Mode switch
    # ------------------------------------------------------------------

    def _on_mode_changed(self) -> None:
        self._mode = "simple" if self._radio_simple.isChecked() else "advanced"
        logger.info("Automation mode switched to: %s", self._mode)

    # ------------------------------------------------------------------
    # Pipeline listing / refresh
    # ------------------------------------------------------------------

    def _refresh_from_db(self) -> None:
        """Refresh the run list from the database, coalescing rapid calls."""
        if self._refresh_pending:
            return
        self._refresh_pending = True
        self._do_refresh()

    def _do_refresh(self) -> None:
        """Actual refresh \u2014 runs synchronously, coalesces subsequent calls."""
        if not self.db:
            self._refresh_pending = False
            return
        try:
            pipeline = self._pipeline_repo
            runs = pipeline.list_runs(limit=30)
        except Exception:
            logger.exception("Failed to load pipeline runs")
            runs = []
        runs_by_id: dict[int, dict[str, Any]] = {int(r["id"]): r for r in runs}
        seen: set = set()
        current_order = list(self._cards.keys())
        new_order_top_down = list(runs_by_id.keys())
        if current_order != new_order_top_down:
            for i in reversed(range(self._run_list_layout.count() - 1)):
                item = self._run_list_layout.itemAt(i)
                widget = item.widget() if item else None
                if isinstance(widget, _RunCard):
                    self._run_list_layout.removeWidget(widget)
                    widget.deleteLater()
            self._cards.clear()
            for run in runs:
                card = _RunCard(run)
                card.clicked.connect(self._select_run)
                self._run_list_layout.insertWidget(self._run_list_layout.count() - 1, card)
                self._cards[int(run["id"])] = card
                seen.add(int(run["id"]))
        else:
            for run in runs:
                run_id = int(run["id"])
                card = self._cards.get(run_id)
                if card is None:
                    card = _RunCard(run)
                    card.clicked.connect(self._select_run)
                    self._run_list_layout.insertWidget(self._run_list_layout.count() - 1, card)
                    self._cards[run_id] = card
                else:
                    card.update(run)
                seen.add(run_id)
        existing = getattr(self, "_placeholder_label", None)
        if existing is not None and existing.parent() is not None:
            self._run_list_layout.removeWidget(existing)
            existing.setParent(None)
        if not runs:
            if existing is None:
                existing = QLabel(t(
                    "automation.empty",
                    default="No imports yet \u2014 drop a file above to start.",
                ))
                existing.setProperty("fontRole", "muted")
                existing.setAlignment(Qt.AlignCenter)
                existing.setContentsMargins(0, SP["6"], 0, 0)
            self._placeholder_label = existing
            self._run_list_layout.insertWidget(0, existing)
        else:
            self._placeholder_label = None
        for stale in list(self._cards):
            if stale not in seen:
                card = self._cards.pop(stale)
                self._run_list_layout.removeWidget(card)
                card.deleteLater()
                if self._selected_run_id == stale:
                    self._selected_run_id = None
                    self._detail.clear()
        self._refresh_pending = False

    def _select_run(self, run_id: int) -> None:
        self._selected_run_id = int(run_id)
        for rid, card in self._cards.items():
            card.setStyleSheet(
                f"QFrame#automationRunCard {{ background: {BG_SURFACE}; "
                f"border: 2px solid {ACCENT if rid == self._selected_run_id else BORDER_FAINT}; "
                f"border-radius: 6px; }}"
            )
        self._update_selected_run()

    def _update_selected_run(self) -> None:
        if not self.db or self._selected_run_id is None:
            return
        try:
            pipeline = self._pipeline_repo
            run = pipeline.get_run_by_id(self._selected_run_id)
        except Exception:
            run = None
            logger.exception("Failed to load selected run")
        if not run:
            self._detail.clear()
            return
        extracted = {}
        with contextlib.suppress(ValueError, TypeError):
            extracted = json.loads(run.get("extracted_data_json") or "{}")
        candidates = self._candidate_cache.get(self._selected_run_id, [])
        self._detail.show_run(run, extracted, candidates, mode=self._mode)

    # ------------------------------------------------------------------
    # Public API  (used by the package / email flow)
    # ------------------------------------------------------------------

    def selected_trip_id(self) -> int | None:
        if not self.db or self._selected_run_id is None:
            return None
        run = self._pipeline_repo.get_run_by_id(self._selected_run_id)
        if not run:
            return None
        return int(run["matched_trip_id"]) if run.get("matched_trip_id") else None

    def prepare_package_for_selected_trip(self) -> int | None:
        trip_id = self.selected_trip_id()
        if not trip_id:
            return None
        self.package_requested.emit(trip_id)
        return trip_id

    def send_documents_for_selected_trip(self) -> int | None:
        trip_id = self.selected_trip_id()
        if not trip_id:
            return None
        self.send_requested.emit(trip_id)
        return trip_id

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _on_prepare_package(self, trip_id: int) -> None:
        """Open the package preview modal and chain into the email composer."""
        if not self.db or not trip_id:
            return
        from ui.views.package_preview_modal import PackagePreviewDialog

        preview = PackagePreviewDialog(self, self.db, trip_id, prefs=self.prefs)
        preview.continue_to_email.connect(self._open_email_composer)
        preview.exec()

    def _on_send_documents(self, trip_id: int) -> None:
        """Skip the preview and go straight to the email composer."""
        self._open_email_composer(trip_id, None)

    def _on_skip_and_package(self, run_id: int) -> None:
        """Simple mode: skip trip association, create a standalone package."""
        if not self.db:
            return
        from repositories.document_repository import DocumentRepository
        from services.document_automation.package_builder import PackageBuilder

        batch_id = self._batch_for_run.get(run_id, 0)
        batch_run_ids = [
            rid for rid, bid in self._batch_for_run.items()
            if bid == batch_id and rid > 0
        ] if batch_id else [run_id]
        seen: set = set()
        ordered_run_ids: list[int] = []
        for rid in batch_run_ids:
            if rid not in seen:
                seen.add(rid)
                ordered_run_ids.append(rid)

        docs: list[dict[str, Any]] = []
        for rid in ordered_run_ids:
            did = register_standalone_document(self.db, rid)
            if did:
                doc = self._doc_repo.get_by_id(did)
                if doc:
                    docs.append(doc)

        if not docs:
            logger.error(
                "_on_skip_and_package: no documents could be "
                "registered for run %d (batch %d)", run_id, batch_id,
            )
            QMessageBox.warning(
                self,
                t("automation.no_docs_title", default="Error"),
                t(
                    "automation.err_standalone_failed",
                    default="Failed to create standalone document. "
                    "Check that the processed PDF exists on disk.",
                ),
            )
            return

        builder = PackageBuilder(self.db)
        pkg = builder.build_standalone(documents=docs)
        if not pkg:
            logger.error(
                "_on_skip_and_package: failed to build standalone "
                "package for run %d (batch %d)", run_id, batch_id,
            )
            QMessageBox.warning(
                self,
                t("automation.no_docs_title", default="Error"),
                t(
                    "automation.err_package_failed",
                    default="Failed to build the package. Try again.",
                ),
            )
            return
        self._open_email_composer(
            trip_id=None,
            ordered_doc_ids=None,
            documents=pkg.documents,
        )
        self._refresh_from_db()

    def _open_email_composer(
        self,
        trip_id: int | None = None,
        ordered_doc_ids=None,
        documents=None,
    ) -> None:
        """Open the email composer modal pre-populated with package docs."""
        if not self.db:
            return
        from ui.views.email_composer_modal import EmailComposerDialog

        composer = EmailComposerDialog(
            self, self.db, trip_id,
            prefs=self.prefs,
            ordered_doc_ids=ordered_doc_ids or None,
            documents=documents,
        )
        composer.sent.connect(self._on_email_sent)
        composer.exec()

    def _on_email_sent(self, package_id: int, recipient: str) -> None:
        logger.info("Email sent for package %s to %s", package_id, recipient)

    def _on_detail_delete_run(self, run_id: int) -> None:
        """Remove a pipeline run and its card from the UI."""
        self._refresh_from_db()

    # ------------------------------------------------------------------
    # Lifecycle  (used by main_window)
    # ------------------------------------------------------------------

    def _configure_email_importer(self) -> None:
        """Read settings and start/stop the email importer accordingly."""
        if not self.prefs:
            return
        enabled = self.prefs.get_setting("email_importer_enabled", "0") in ("1", "true")
        if enabled:
            host = self.prefs.get_setting("email_importer_host", "")
            port = int(self.prefs.get_setting("email_importer_port", "993"))
            user = self.prefs.get_setting("email_importer_user", "")
            pw = self.prefs.get_setting("email_importer_password", "")
            interval = int(self.prefs.get_setting("email_importer_interval", "60"))
            raw_whitelist = self.prefs.get_setting("email_importer_whitelist", "")
            whitelist = {s.strip() for s in raw_whitelist.split(",") if s.strip()}
            delete = self.prefs.get_setting("email_importer_delete", "0") in ("1", "true")
            self._email_importer.configure(
                host=host, port=port, user=user, password=pw,
                interval_s=interval, whitelist=whitelist, delete_after=delete,
            )
            self._email_importer.start()
        else:
            self._email_importer.stop()

    def _configure_folder_watcher(self) -> None:
        """Read settings and start/stop the folder watcher accordingly."""
        if not self.prefs:
            return
        enabled = self.prefs.get_setting("folder_watcher_enabled", "0") in ("1", "true")
        if enabled:
            path = self.prefs.get_setting("folder_watcher_path", "")
            interval = int(self.prefs.get_setting("folder_watcher_interval", "10"))
            recursive = self.prefs.get_setting("folder_watcher_recursive", "0") in ("1", "true")
            delete = self.prefs.get_setting("folder_watcher_delete", "0") in ("1", "true")
            self._folder_watcher.configure(
                watch_path=path, recursive=recursive, delete_after=delete, interval_s=interval,
            )
            self._folder_watcher.start()
        else:
            self._folder_watcher.stop()

    def wakeup(self) -> None:
        self._refresh_from_db()
        self._configure_email_importer()
        self._configure_folder_watcher()

    def shutdown(self) -> None:
        self._email_importer.stop()
        self._folder_watcher.stop()
        for worker in list(self._workers.values()):
            try:
                worker.stop_event.set()
                worker.requestInterruption()
                if worker.isRunning():
                    worker.wait(2000)
            except Exception:
                pass
        queue = getattr(self, "_queue", [])
        if queue:
            logger.warning("Shutdown with %d pending files in queue \u2014 discarding: %s",
                           len(queue), queue[:5])
        self._workers.clear()
        self._pending_workers.clear()
        self._queue = []
