"""Mixin providing bulk document actions: upload, download, delete,
link/unlink, and on-demand OCR for QtDocumentCenterView."""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

from services.i18n import t
from services.operations.event_bus import DOCUMENT_OCR_RAN, EventBus
from ui.components import Btn

logger = logging.getLogger(__name__)


class DocumentActionsMixin:
    """Mixin that provides document action methods.

    Intended to be used together with ``QtDocumentCenterView`` (which
    provides the UI, service instance, and helper methods such as
    ``refresh``, ``_show_toast``, ``_show_detail``, ``_refresh_detail``,
    and ``_stop_ocr_worker``).
    """

    # ------------------------------------------------------------------
    # Open / View
    # ------------------------------------------------------------------

    def _open_document(self, doc: dict[str, Any]) -> None:
        if self._service:
            path = self._service.get_file_path(doc["id"])
            if path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def _upload_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            t("docs.upload_title"),
            "",
            "All Supported (*.pdf *.png *.jpg *.jpeg *.docx *.xlsx *.csv *.txt *.zip *.gif);;"
            "PDF (*.pdf);;"
            "Images (*.png *.jpg *.jpeg *.gif);;"
            "Documents (*.docx *.xlsx *.csv *.txt);;"
            "All Files (*.*)",
        )
        if not paths:
            return
        self._process_batch_upload(paths)

    def _process_batch_upload(self, paths: list[str]) -> None:
        if self._service is None:
            return
        result = self._service.batch_upload(
            paths=paths,
            category=self._active_category or "",
            uploaded_by="user",
        )
        self.refresh()
        uploaded = len(result["uploaded"])
        dups = len(result["duplicates"])
        failed = len(result["rejected"]) + len(result["failed"])

        msg_parts: list[str] = []
        if uploaded:
            msg_parts.append(f"Uploaded: {uploaded}")
        if dups:
            msg_parts.append(f"Duplicates skipped: {dups}")
        if failed:
            msg_parts.append(f"Failed: {failed}")

        if uploaded > 0:
            self._show_toast(" | ".join(msg_parts))
        if failed > 0:
            details = "\n".join(
                [
                    f"  {r['file']}: {r.get('reason', 'Unknown')}"
                    for r in (result["rejected"] + result["failed"])
                ][:10]
            )
            QMessageBox.warning(
                self,
                t("docs.upload_title"),
                f"Some files were rejected:\n{details}",
            )

    # ------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------

    def _email_document(self, doc: dict[str, Any]) -> None:
        recipient, ok = QInputDialog.getText(
            self,
            t("docs.email_title"),
            t("docs.email_prompt"),
        )
        if not ok or not recipient:
            return
        try:
            if self._service:
                ok_sent = self._service.email_document(
                    doc["id"], recipient, prefs=self.prefs,
                )
                if ok_sent:
                    QMessageBox.information(
                        self, t("docs.email_title"), t("docs.email_sent"),
                    )
                else:
                    QMessageBox.critical(
                        self, t("docs.email_title"),
                        "SMTP not configured. Check settings.",
                    )
        except Exception as e:
            QMessageBox.critical(self, t("docs.email_title"), str(e))

    # ------------------------------------------------------------------
    # Download (ZIP)
    # ------------------------------------------------------------------

    def _download_zip_selected(self) -> None:
        if not self._selected_ids:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("docs.download_zip"),
            "",
            "ZIP archive (*.zip)",
        )
        if not path:
            return
        try:
            if self._service:
                self._service.download_zip(list(self._selected_ids), path)
                QMessageBox.information(
                    self, t("docs.download_zip"), f"Saved: {path}",
                )
        except Exception as e:
            QMessageBox.critical(self, t("docs.download_zip"), str(e))

    def _download_single_zip(self, doc: dict[str, Any]) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("docs.download_zip"),
            "",
            "ZIP archive (*.zip)",
        )
        if not path:
            return
        try:
            if self._service:
                self._service.download_zip([doc["id"]], path)
                QMessageBox.information(
                    self, t("docs.download_zip"), f"Saved: {path}",
                )
        except Exception as e:
            QMessageBox.critical(self, t("docs.download_zip"), str(e))

    # ------------------------------------------------------------------
    # Delete & Archive
    # ------------------------------------------------------------------

    def _delete_document(self, doc: dict[str, Any]) -> None:
        name = doc.get("title", doc.get("file_name", ""))
        reply = QMessageBox.question(
            self,
            t("docs.confirm_delete_title"),
            t("docs.confirm_delete_msg").format(name=name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            if self._service:
                self._service.delete(doc["id"])
                self._selected_ids.discard(doc["id"])
        except Exception as e:
            logger.error("Failed to delete document %d: %s", doc["id"], e)
            QMessageBox.critical(self, t("docs.confirm_delete_title"), str(e))
        self.refresh()

    def _archive_document(self, doc: dict[str, Any]) -> None:
        if self._service:
            self._service.archive(doc["id"])
            self._selected_ids.discard(doc["id"])
            self.refresh()

    def _batch_delete_selected(self) -> None:
        if not self._selected_ids:
            return
        n = len(self._selected_ids)
        reply = QMessageBox.question(
            self,
            t("docs.confirm_delete_title"),
            f"Delete {n} selected document(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            if self._service:
                self._service.delete_batch(list(self._selected_ids))
                self._selected_ids.clear()
        except Exception as e:
            QMessageBox.critical(self, t("docs.confirm_delete_title"), str(e))
        self.refresh()

    # ------------------------------------------------------------------
    # On-demand OCR
    # ------------------------------------------------------------------

    def _on_rerun_ocr_clicked(self, doc: dict[str, Any]) -> None:
        """Re-run image enhancement + OCR + field extraction on this doc.

        Strictly click-driven; we never auto-attach. The user can
        then press "Link to trip…" separately to wire the freshly
        extracted fields to a trip.
        """
        if not isinstance(doc, dict):
            logger.warning("_on_rerun_ocr_clicked called with non-dict doc: %s", doc)
            return
        if self._ocr_busy:
            return
        if self._service is None or self.db is None:
            return
        file_path = doc.get("file_path") or ""
        if not file_path or not os.path.isfile(file_path):
            QMessageBox.warning(
                self,
                t("docs.rerun_ocr", default="Re-run OCR"),
                t(
                    "docs.rerun_ocr_missing_file",
                    default="The file is no longer on disk; OCR cannot be re-run.",
                ),
            )
            return

        self._ocr_busy = True
        try:
            from ui.views.re_run_ocr_worker import ReRunOcrWorker
        except Exception as exc:
            logger.exception("Could not import ReRunOcrWorker")
            self._ocr_busy = False
            QMessageBox.critical(self, t("docs.rerun_ocr", default="Re-run OCR"), str(exc))
            return

        self._stop_ocr_worker()
        worker = ReRunOcrWorker(self.db, int(doc["id"]), parent=self)
        worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker = worker
        worker.start()
        self._show_toast(
            t("docs.rerun_ocr_started", default="OCR started…")
        )
        # Re-render detail so the button is disabled while running.
        self._show_detail(doc)

    def _on_ocr_finished(self, doc_id: int, error: object) -> None:
        """Worker callback: refresh the detail panel and publish event."""
        self._ocr_busy = False
        self._ocr_worker = None
        if error is not None:
            QMessageBox.critical(
                self,
                t("docs.rerun_ocr", default="Re-run OCR"),
                str(error),
            )
        else:
            self._show_toast(
                t("docs.rerun_ocr_done", default="OCR complete")
            )
            try:
                EventBus().publish(DOCUMENT_OCR_RAN, {"document_id": doc_id})
            except Exception:
                logger.exception("Failed to publish DOCUMENT_OCR_RAN")
        # Refresh detail panel (re-enables the button).
        if self._current_detail_doc and self._current_detail_doc.get("id") == doc_id:
            self._refresh_detail(doc_id)
        elif self._service is not None:
            doc = self._service.get_by_id(doc_id)
            if doc:
                self._show_detail(doc)

    # ------------------------------------------------------------------
    # Trip linking
    # ------------------------------------------------------------------

    def _on_link_to_trip_clicked(self, doc: Any) -> None:
        """Open a dialog that lets the user pick a trip to link to.

        Strictly click-driven: we never auto-attach a document to
        a trip. The dialog shows recent trips + a free-text
        filter and the user must press "Link" to confirm.
        """
        if self.db is None:
            return
        if not isinstance(doc, dict):
            logger.warning("_on_link_to_trip_clicked called with non-dict doc: %r", doc)
            QMessageBox.warning(
                self, t("docs.link_to_trip", default="Link to trip…"),
                t("docs.invalid_document_data", default="Invalid document data."),
            )
            return
        try:
            from ui.dialogs.trip_picker_dialog import QtTripPickerDialog
        except Exception as exc:
            logger.exception("Could not import QtTripPickerDialog")
            QMessageBox.critical(self, t("docs.link_to_trip", default="Link to trip…"), str(exc))
            return
        dlg = QtTripPickerDialog(self.db, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        trip_id = dlg.selected_trip_id()
        if trip_id is None:
            return
        if self._service is None:
            return
        try:
            ok = self._service.link_document(
                int(doc["id"]), "trip", int(trip_id), relation_type="ocr_linked"
            )
        except Exception as exc:
            logger.exception("link_document failed")
            QMessageBox.critical(self, t("docs.link_to_trip", default="Link to trip…"), str(exc))
            return
        if ok:
            self._show_toast(
                t("docs.link_to_trip_done", default="Document linked to trip.")
            )
        else:
            self._show_toast(
                t("docs.link_to_trip_exists", default="Already linked.")
            )
        self._refresh_detail(doc["id"])
