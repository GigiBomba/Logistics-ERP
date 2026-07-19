"""Package preview modal — show the trip's documents in a reorderable
list, then either go back to the automation view or open the email
composer.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from services.document_automation import PackageBuilder
from services.i18n import t
from ui.design_tokens import SP

logger = logging.getLogger(__name__)


def _human_size(size: int) -> str:
    if not size:
        return "?"
    if size > 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size > 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} B"


class PackagePreviewDialog(QDialog):
    """Lists the trip's documents in an InternalMove QListWidget."""

    continue_to_email = Signal(int, list, object)   # trip_id, ordered doc_ids, docs

    def __init__(
        self,
        parent,
        db,
        trip_id: int | None = None,
        prefs=None,
        trip_repo=None,
        doc_repo=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.trip_id = int(trip_id) if trip_id is not None else None
        self.prefs = prefs
        self._doc_ids: list[int] = []
        if trip_repo is not None:
            self._trip_repo = trip_repo
        elif db is not None:
            from repositories.trip_repository import TripRepository
            self._trip_repo = TripRepository(db)
        else:
            logger.warning("PackagePreview: no local database - TripRepository disabled in remote mode")
            self._trip_repo = None

        if doc_repo is not None:
            self._doc_repo = doc_repo
        elif db is not None:
            from repositories.document_repository import DocumentRepository
            self._doc_repo = DocumentRepository(db)
        else:
            logger.warning("PackagePreview: no local database - DocumentRepository disabled in remote mode")
            self._doc_repo = None
        # The already-loaded documents (one per list item) so the
        # downstream email composer doesn't have to re-query the DB.
        self._documents_by_id: dict[int, dict[str, Any]] = {}
        self.setWindowTitle(
            t("automation.package_title", default="Prepare Customer Package")
        )
        self.setMinimumSize(640, 480)
        self._build_ui()
        self._load_documents()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["3"])

        if self.trip_id is not None:
            trip = self._trip_repo.get_by_id(self.trip_id)
            if trip:
                trip_label = t(
                    "automation.preview_trip_format",
                    default="Trip #{} — {} ({} → {})",
                ).format(self.trip_id, trip.get('client_name', ''), trip.get('start_date', ''), trip.get('end_date', ''))
            else:
                trip_label = t("route_history.trip_title", default="Trip #{}").format(self.trip_id)
        else:
            trip_label = t("automation.standalone_title", default="Standalone Package")

        self._header = QLabel(
            t("automation.package_subtitle", default="Package for {trip}").format(
                trip=trip_label
            )
        )
        self._header.setProperty("fontRole", "h3")
        layout.addWidget(self._header)

        info = QLabel(
            t(
                "automation.package_help",
                default="Drag to reorder. Use ↑/↓ buttons if you prefer. "
                       "Click 'Continue to Email' when ready.",
            )
        )
        info.setProperty("fontRole", "muted")
        info.setWordWrap(True)
        layout.addWidget(info)

        self._list = QListWidget()
        self._list.setDragDropMode(QAbstractItemView.InternalMove)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setAlternatingRowColors(True)
        layout.addWidget(self._list, 1)

        # Up / Down buttons.
        row = QHBoxLayout()
        self._up_btn = QPushButton(t("common.up", default="↑ Up"))
        self._up_btn.clicked.connect(self._on_move_up)
        self._down_btn = QPushButton(t("common.down", default="↓ Down"))
        self._down_btn.clicked.connect(self._on_move_down)
        row.addWidget(self._up_btn)
        row.addWidget(self._down_btn)
        row.addStretch(1)
        layout.addLayout(row)

        # Download buttons.
        download_row = QHBoxLayout()
        self._download_zip_btn = QPushButton(
            t("automation.download_zip", default="\U0001F4E6 Download ZIP"),
        )
        self._download_zip_btn.clicked.connect(self._on_download_zip)
        download_row.addWidget(self._download_zip_btn)

        self._download_pdf_btn = QPushButton(
            t("automation.download_pdf", default="\U0001F4C4 Download Combined PDF"),
        )
        self._download_pdf_btn.clicked.connect(self._on_download_pdf)
        download_row.addWidget(self._download_pdf_btn)

        download_row.addStretch(1)
        layout.addLayout(download_row)

        # Dialog buttons.
        button_box = QDialogButtonBox()
        self._cancel_btn = button_box.addButton(QDialogButtonBox.Cancel)
        self._cancel_btn.setText(t("common.cancel", default="Cancel"))
        self._continue_btn = button_box.addButton(
            t("automation.continue_to_email", default="Continue to Email"),
            QDialogButtonBox.AcceptRole,
        )
        self._continue_btn.setDefault(True)
        button_box.accepted.connect(self._on_continue)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_documents(self) -> None:
        self._list.clear()
        if self.trip_id is None:
            documents = []
        else:
            try:
                builder = PackageBuilder(self.db)
                documents = builder.list_trip_documents(self.trip_id)
            except Exception:
                documents = []
                logger.exception("Failed to list trip documents")
        if not documents:
            placeholder = QListWidgetItem(
                t("automation.package_empty",
                  default="(No documents linked to this trip yet)")
            )
            placeholder.setFlags(Qt.NoItemFlags)
            self._list.addItem(placeholder)
            self._continue_btn.setEnabled(False)
            return
        for doc in documents:
            try:
                doc_id_int = int(doc.get("id"))
            except (TypeError, ValueError):
                continue
            label = f"{doc.get('title') or doc.get('file_name')}    [{_human_size(int(doc.get('file_size') or 0))}]"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, doc_id_int)
            tip = doc.get("file_name") or ""
            if tip:
                item.setToolTip(tip)
            self._list.addItem(item)
            self._doc_ids.append(doc_id_int)
            self._documents_by_id[doc_id_int] = doc
        self._continue_btn.setEnabled(True)

    def _on_move_up(self) -> None:
        row = self._list.currentRow()
        if row <= 0:
            return
        item = self._list.takeItem(row)
        self._list.insertItem(row - 1, item)
        self._list.setCurrentRow(row - 1)
        self._refresh_id_order()

    def _on_move_down(self) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= self._list.count() - 1:
            return
        item = self._list.takeItem(row)
        self._list.insertItem(row + 1, item)
        self._list.setCurrentRow(row + 1)
        self._refresh_id_order()

    def _refresh_id_order(self) -> None:
        ids: list[int] = []
        for i in range(self._list.count()):
            data = self._list.item(i).data(Qt.UserRole)
            try:
                ids.append(int(data))
            except (TypeError, ValueError):
                logger.warning("_refresh_id_order: skipping item %d with non-integer data: %r", i, data)
                continue
        self._doc_ids = ids

    def get_ordered_documents(self) -> list[dict[str, Any]]:
        """Return the documents in the user-selected order.

        Documents that were loaded into the list are returned.  If a
        document ID was added between the package preview and the
        email composer, a fresh DB lookup fills the gap.
        """
        out: list[dict[str, Any]] = []
        for doc_id in self._doc_ids:
            doc = self._documents_by_id.get(doc_id)
            if doc is None:
                try:
                    row = self._doc_repo.get_by_id(doc_id)
                except Exception:
                    row = None
                if row is None:
                    continue
                doc = {
                    "id": row.get("id"),
                    "doc_number": row.get("doc_number", ""),
                    "title": row.get("title", ""),
                    "file_path": row.get("file_path", ""),
                    "file_name": row.get("file_name", ""),
                    "file_size": row.get("file_size", 0) or 0,
                    "mime_type": row.get("mime_type", ""),
                    "category": row.get("category", ""),
                    "cmr_number": row.get("cmr_number", ""),
                    "is_signed": row.get("is_signed", 0) or 0,
                }
                self._documents_by_id[doc_id] = doc
            out.append(doc)
        return out

    def _on_download_zip(self) -> None:
        """Download all trip documents as a ZIP archive."""
        from services.document_automation.package_builder import PackageBuilder
        builder = PackageBuilder(self.db)
        output_dir = os.path.join(tempfile.gettempdir(), "operion_packages")
        path = builder.build_zip(self.trip_id, output_dir)
        if path:
            QMessageBox.information(
                self,
                t("automation.download_zip", default="Download ZIP"),
                t("automation.download_done",
                  default="Package saved to:\n{path}").format(path=path),
            )
        else:
            QMessageBox.warning(
                self,
                t("automation.download_zip", default="Download ZIP"),
                t("automation.download_empty",
                  default="No documents to package."),
            )

    def _on_download_pdf(self) -> None:
        """Download all documents merged into a single PDF with cover page."""
        from services.document_automation.package_builder import PackageBuilder
        builder = PackageBuilder(self.db)
        output_dir = os.path.join(tempfile.gettempdir(), "operion_packages")
        path = builder.build_combined_pdf(self.trip_id, output_dir)
        if path:
            QMessageBox.information(
                self,
                t("automation.download_pdf", default="Download Combined PDF"),
                t("automation.download_done",
                  default="Package saved to:\n{path}").format(path=path),
            )
        else:
            QMessageBox.warning(
                self,
                t("automation.download_pdf", default="Download Combined PDF"),
                t("automation.download_empty",
                  default="No PDF documents to merge."),
            )

    def _on_continue(self) -> None:
        if not self._doc_ids:
            QMessageBox.information(
                self,
                t("automation.no_docs_title", default="No documents"),
                t("automation.no_docs_msg",
                  default="There are no documents to send. Cancel and run the automation first."),
            )
            return
        self.continue_to_email.emit(
            self.trip_id, list(self._doc_ids), self.get_ordered_documents(),
        )
        self.accept()

    def get_ordered_document_ids(self) -> list[int]:
        return list(self._doc_ids)
