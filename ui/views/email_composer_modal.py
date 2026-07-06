"""Email composer modal — To / Subject / Body with auto-fill from
templates and the customer detected for the trip.

On send, the email is dispatched through
:func:`NotificationCenter.send_email` and the :class:`document_package`
row is updated to mark it as sent (or failed).
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import smtplib
import ssl
import time
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from repositories.pipeline_repository import PipelineRepository
from repositories.trip_repository import TripRepository
from services.document_automation import CustomerDetector, EmailTemplateService
from services.document_automation.package_builder import PackageBuilder
from services.i18n import t
from services.operations.notification_center import NotificationCenter
from ui.design_tokens import DANGER_TEXT, SP

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-']+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


class _EmailSendWorker(QThread):
    """Background worker that sends the email without blocking the UI.

    Signals:
        succeeded()         — email sent successfully.
        failed(str)         — error message to display.
    """

    succeeded = Signal()
    failed = Signal(str)

    def __init__(
        self,
        notifier: NotificationCenter,
        to: str,
        subject: str,
        body: str,
        attachments: list[str],
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self._notifier = notifier
        self._to = to
        self._subject = subject
        self._body = body
        self._attachments = list(attachments)

    def run(self) -> None:
        try:
            ok = self._notifier.send_email(
                to_address=self._to,
                subject=self._subject,
                body=self._body,
                attachments=self._attachments,
            )
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        if not ok:
            self.failed.emit("SMTP not configured or send returned False")
            return
        self.succeeded.emit()


class EmailComposerDialog(QDialog):
    """Modal that lets the user review the auto-filled email and send."""

    sent = Signal(int, str)  # package_id, email_message_id

    def __init__(
        self,
        parent,
        db,
        trip_id: int | None = None,
        prefs=None,
        ordered_doc_ids: list[int] | None = None,
        package_id: int | None = None,
        documents: list[dict[str, Any]] | None = None,
        trip_repo=None,
        pipeline_repo=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.trip_id = int(trip_id) if trip_id is not None else None
        self.prefs = prefs
        self.ordered_doc_ids = list(ordered_doc_ids or [])
        self._trip_repo = trip_repo if trip_repo is not None else TripRepository(db)
        self._pipeline_repo = pipeline_repo if pipeline_repo is not None else PipelineRepository(db)
        # If the caller already loaded the ordered documents (the
        # package preview does), reuse them.  Otherwise, fall back to
        # a PackageBuilder lookup.
        self._preloaded_documents: list[dict[str, Any]] = list(documents or [])
        self._package_id = package_id
        self._to_emails: list[str] = []
        self.setWindowTitle(
            t("automation.email_title", default="Send Customer Package")
        )
        self.setMinimumSize(720, 560)
        self._build_ui()
        self._prefill()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP["4"], SP["4"], SP["4"], SP["4"])
        layout.setSpacing(SP["3"])

        self._trip_label = QLabel()
        self._trip_label.setProperty("fontRole", "h3")
        if self.trip_id is not None:
            self._trip_label.setText(f"Trip #{self.trip_id}")
        else:
            self._trip_label.setText(
                t("automation.standalone_title", default="Standalone Package")
            )
        layout.addWidget(self._trip_label)

        # To:
        to_row = QHBoxLayout()
        to_label = QLabel(t("automation.to_label", default="To:"))
        to_label.setFixedWidth(60)
        to_row.addWidget(to_label)
        self._to_combo = QComboBox()
        self._to_combo.setEditable(True)
        self._to_combo.setInsertPolicy(QComboBox.NoInsert)
        self._to_combo.lineEdit().setPlaceholderText(
            t("automation.to_placeholder", default="Type email address...")
        )
        to_row.addWidget(self._to_combo, 1)
        layout.addLayout(to_row)

        # Subject
        sub_row = QHBoxLayout()
        sub_label = QLabel(t("automation.subject_label", default="Subject:"))
        sub_label.setFixedWidth(60)
        sub_row.addWidget(sub_label)
        self._subject_edit = QLineEdit()
        sub_row.addWidget(self._subject_edit, 1)
        layout.addLayout(sub_row)

        # Body
        body_label = QLabel(t("automation.body_label", default="Body:"))
        layout.addWidget(body_label)
        self._body_edit = QPlainTextEdit()
        # QPlainTextEdit is plain-text only; it has no
        # setAcceptRichText method.  We keep the comment for clarity.
        layout.addWidget(self._body_edit, 1)

        # Attachments list
        self._attach_label = QLabel()
        self._attach_label.setProperty("fontRole", "muted")
        self._attach_label.setWordWrap(True)
        layout.addWidget(self._attach_label)

        # Inline error
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {DANGER_TEXT};")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Buttons
        button_box = QDialogButtonBox()
        self._send_btn = button_box.addButton(
            t("automation.send", default="Send"), QDialogButtonBox.AcceptRole
        )
        self._send_btn.setDefault(True)
        self._save_draft_btn = button_box.addButton(
            t("automation.save_draft", default="Save Draft"),
            QDialogButtonBox.ActionRole,
        )
        self._cancel_btn = button_box.addButton(
            t("common.cancel", default="Cancel"), QDialogButtonBox.RejectRole
        )
        self._send_btn.clicked.connect(self._on_send)
        self._save_draft_btn.clicked.connect(self._on_save_draft)
        self._cancel_btn.clicked.connect(self.reject)
        layout.addWidget(button_box)

    def _prefill(self) -> None:
        documents: list[dict[str, Any]] = []
        customer = None

        if self.trip_id is not None:
            trip = self._trip_repo.get_by_id(self.trip_id)
            if not trip:
                self._error_label.setText(
                    t("automation.trip_not_found", default="Trip not found")
                )
                self._error_label.setVisible(True)
                self._send_btn.setEnabled(False)
                return

            # Resolve documents.  Reuse the list passed in by the package
            # preview if we got one, so we don't re-query the DB.
            if self._preloaded_documents:
                documents = list(self._preloaded_documents)
            else:
                try:
                    builder = PackageBuilder(self.db)
                    documents = builder.list_trip_documents(self.trip_id)
                except Exception:
                    documents = []
                    logger.exception("PackageBuilder failed")
            if self.ordered_doc_ids:
                order_index = {int(d): i for i, d in enumerate(self.ordered_doc_ids)}
                documents = sorted(
                    documents,
                    key=lambda d: order_index.get(int(d.get("id", -1)), 9999),
                )

            # Resolve customer.
            try:
                detector = CustomerDetector(self.db)
                customer = detector.detect_for_trip(trip)
            except Exception:
                customer = None
                logger.exception("CustomerDetector failed")

            # Subject + body with trip context.
            try:
                tpl = EmailTemplateService(self.prefs)
                subject = tpl.render_subject(trip, customer)
                body = tpl.render_body(trip, customer, documents)
            except Exception:
                subject = t("email.subject_trip", default="Documents for Trip #{}").format(self.trip_id)
                body = t("email.default_body", default="Please find attached the requested documents.")
                logger.exception("EmailTemplateService failed")
        else:
            # No trip — standalone package.  Use preloaded documents if
            # available; customer detection is not possible.
            if self._preloaded_documents:
                documents = list(self._preloaded_documents)
            if self.ordered_doc_ids:
                order_index = {int(d): i for i, d in enumerate(self.ordered_doc_ids)}
                documents = sorted(
                    documents,
                    key=lambda d: order_index.get(int(d.get("id", -1)), 9999),
                )
            # Derive the subject from the first document title so it
            # reflects the original file name (simple mode) or the
            # extracted invoice/CMR number (advanced mode).
            if documents and documents[0].get("title"):
                subject = documents[0]["title"]
            else:
                subject = t(
                    "automation.standalone_subject",
                    default="Documents Attached",
                )
            body = t(
                "automation.standalone_body",
                default="Please find attached the requested documents.",
            )

        self._documents = documents

        # To field — collect all candidate emails.
        self._to_emails = list(customer.all_emails) if customer else []
        self._to_combo.clear()
        for addr in self._to_emails:
            self._to_combo.addItem(addr)
        default = customer.default_email if customer else ""
        if default:
            idx = self._to_combo.findText(default)
            if idx >= 0:
                self._to_combo.setCurrentIndex(idx)
            else:
                self._to_combo.setEditText(default)

        self._subject_edit.setText(subject)
        self._body_edit.setPlainText(body)

        # Attachments.
        if documents:
            files = [d.get("file_name", f"doc_{d.get('id')}.pdf") for d in documents]
            self._attach_label.setText(
                t(
                    "automation.attachments_label",
                    default="Attachments ({n}): {files}",
                ).format(n=len(documents), files=", ".join(files))
            )
        else:
            self._attach_label.setText(
                t("automation.attachments_empty", default="(no attachments)")
            )

    def _validate_to(self) -> str | None:
        addr = self._to_combo.currentText().strip()
        if not addr:
            self._error_label.setText(
                t("automation.err_no_to", default="Please enter a recipient address.")
            )
            self._error_label.setVisible(True)
            return None
        if not _EMAIL_RE.match(addr):
            self._error_label.setText(
                t("automation.err_bad_to", default="Email address is not valid.")
            )
            self._error_label.setVisible(True)
            return None
        self._error_label.setVisible(False)
        return addr

    def _on_send(self) -> None:
        to = self._validate_to()
        if not to:
            return
        # Verify all attachment files exist on disk before sending —
        # SMTP would raise mid-stream otherwise.
        missing: list[str] = []
        for d in self._documents:
            path = d.get("file_path")
            if path and not os.path.isfile(path):
                missing.append(d.get("file_name") or str(path))
        if missing:
            self._error_label.setText(
                t(
                    "automation.err_missing_files",
                    default=(
                        "These attached files no longer exist on disk:\n{list}\n\n"
                        "Re-link the documents and try again."
                    ),
                ).format(list="\n".join(f"  - {m}" for m in missing))
            )
            self._error_label.setVisible(True)
            return
        attachments = [d["file_path"] for d in self._documents if d.get("file_path")]
        # Warn if attachments exceed the typical SMTP 25 MB cap.
        total_size = 0
        with contextlib.suppress(TypeError, ValueError):
            total_size = sum(int(d.get("file_size") or 0) for d in self._documents)
        if total_size > 25 * 1024 * 1024:
            self._error_label.setText(
                t(
                    "automation.err_size",
                    default=(
                        "Attachments are {mb:.1f} MB which exceeds the typical "
                        "25 MB SMTP limit. Remove some files or send fewer at a time."
                    ),
                ).format(mb=total_size / (1024 * 1024))
            )
            self._error_label.setVisible(True)
            return
        # Ensure package row exists.
        package_id = self._package_id
        pipeline = self._pipeline_repo
        if not package_id:
            try:
                package_id = pipeline.create_package(self.trip_id)
            except Exception:
                logger.exception("Failed to create package row")
                self._error_label.setText(t("automation.package_create_error", default="Internal error: package row creation failed"))
                self._error_label.setVisible(True)
                return
            self._package_id = package_id
        # Save email content.
        try:
            pipeline.update_package(
                package_id,
                status="sending",
                recipient_email=to,
                subject=self._subject_edit.text(),
                body=self._body_edit.toPlainText(),
            )
        except Exception:
            logger.exception("Failed to save package draft")

        # Configure SMTP via the existing NotificationCenter.
        notifier = NotificationCenter(self.db)
        if self.prefs is not None:
            try:
                cfg = self.prefs.get_smtp_config()
                port = int(cfg.get("smtp_port", 587))
                notifier.configure_smtp(
                    cfg.get("smtp_server", ""), port,
                    cfg.get("smtp_user", ""), cfg.get("smtp_password", ""),
                )
            except Exception:
                logger.exception("Failed to configure SMTP from preferences")
        # Send asynchronously so the UI stays responsive.
        self._send_btn.setEnabled(False)
        self._send_btn.setText(t("automation.sending", default="Sending…"))
        self._send_async_to = to
        worker = _EmailSendWorker(
            notifier, to,
            self._subject_edit.text(),
            self._body_edit.toPlainText(),
            attachments,
        )
        worker.succeeded.connect(lambda pid=package_id: self._on_send_succeeded(pid))
        worker.failed.connect(lambda err, pid=package_id: self._on_send_failed(pid, err))
        worker.finished.connect(lambda w=worker: self._cleanup_send_worker(w))
        worker.start()

    def _on_send_succeeded(self, package_id: int) -> None:
        """Mark the package as sent and close the dialog."""
        to = getattr(self, "_send_async_to", "")
        pipeline = self._pipeline_repo
        try:
            pipeline.update_package(
                package_id,
                status="sent",
                email_message_id=f"sent-{package_id}-{int(time.time())}",
            )
        except Exception:
            logger.exception("Failed to mark package as sent")

        self.sent.emit(int(package_id), to)
        self.accept()

    def _cleanup_send_worker(self, worker: QThread) -> None:
        """Safely clean up a send worker after it finishes."""
        with contextlib.suppress(RuntimeError):
            worker.deleteLater()

    def _on_send_failed(self, package_id: int, error: str) -> None:
        """Roll package back to draft and show the error."""
        logger.warning("Async email send failed for package %s: %s", package_id, error)
        try:
            self._pipeline_repo.update_package(
                package_id, status="draft", error_message=error,
            )
        except Exception:
            logger.exception("Failed to roll back package to draft")
        self._error_label.setText(error)
        self._error_label.setVisible(True)
        self._send_btn.setEnabled(True)
        self._send_btn.setText(t("automation.send", default="Send"))

    def _on_save_draft(self) -> None:
        to = self._to_combo.currentText().strip()
        pipeline = self._pipeline_repo
        package_id = self._package_id
        if not package_id:
            package_id = pipeline.create_package(self.trip_id)
            self._package_id = package_id
        pipeline.update_package(
            package_id,
            status="draft",
            recipient_email=to,
            subject=self._subject_edit.text(),
            body=self._body_edit.toPlainText(),
        )
        QMessageBox.information(
            self,
            t("automation.draft_saved_title", default="Draft saved"),
            t(
                "automation.draft_saved_msg",
                default="Email draft saved. You can return to this dialog to send it later.",
            ),
        )
