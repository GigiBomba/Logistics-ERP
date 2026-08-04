"""PySide6 modal dialog for submitting a support / bug report.

Allows the user to submit a support ticket with subject, description,
severity level, and an optional screenshot attachment.

Usage::

    dlg = QtReportIssueDialog(parent=self)
    if dlg.exec() == QDialog.Accepted:
        # report was submitted
        ...
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, Qt, QThread, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from client.api_client import ApiClient
from services.i18n import t
from ui.design_tokens import (
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_BASE,
    COLOR_BG_CARD,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_ERROR_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_TERTIARY,
    COLOR_TEXT_WHITE,
    FADE_MS,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_WEIGHT_BOLD,
    RADIUS_SM,
    SPACE_2,
    SPACE_3,
    SPACE_6,
    SPACE_8,
)
from ui.design_tokens import SP as S

logger = logging.getLogger(__name__)

_MAX_SCREENSHOT_BYTES = 10 * 1024 * 1024  # 10 MiB


class _ReportIssueWorker(QObject):
    """Background worker that submits a support ticket without blocking the UI."""

    finished = Signal(bool, str)  # success: bool, message: str (error on failure)

    def __init__(
        self,
        subject: str,
        description: str,
        severity: str,
        screenshot_bytes: bytes | None,
        screenshot_filename: str,
        api_client: ApiClient | None = None,
    ) -> None:
        super().__init__()
        self._subject = subject
        self._description = description
        self._severity = severity
        self._screenshot_bytes = screenshot_bytes
        self._screenshot_filename = screenshot_filename
        self._api_client = api_client

    def run(self) -> None:
        """Execute report submission and emit the result."""
        try:
            api = self._api_client or ApiClient()
            api.report_issue(
                subject=self._subject,
                description=self._description,
                severity=self._severity,
                screenshot_bytes=self._screenshot_bytes,
                screenshot_filename=self._screenshot_filename,
            )
            self.finished.emit(True, "")
        except Exception as exc:
            logger.exception("Failed to submit issue report")
            self.finished.emit(False, str(exc))


class QtReportIssueDialog(QDialog):
    """Modal dialog for submitting a support / bug report.

    Layout (top-to-bottom):
        Title
        Subject      (QLineEdit)
        Description  (QPlainTextEdit, min 100 px)
        Severity     (QComboBox — Low / Medium / High / Critical)
        Screenshot   (QPushButton + filename QLabel)
        Error label  (hidden until a validation or submit error occurs)
        Cancel / Submit buttons
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        api_client: Optional[ApiClient] = None,
    ) -> None:
        super().__init__(parent)
        self._api_client = api_client
        self._screenshot_bytes: bytes | None = None
        self._screenshot_filename: str = ""
        self._worker: Optional[_ReportIssueWorker] = None
        self._thread: Optional[QThread] = None
        self._build_ui()

        # ── Fade-in effect ─────────────────────────────────────────────
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

    def showEvent(self, event: QShowEvent) -> None:
        """Fade in the dialog on show."""
        super().showEvent(event)
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(FADE_MS)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.start()
        self._fade_anim.finished.connect(self._fade_anim.deleteLater)

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle(t("report_issue.window_title", default="Report Issue"))
        self.setAccessibleName("Report Issue")
        self.setAccessibleDescription(
            "Dialog for submitting a support or bug report"
        )
        self.setMinimumSize(480, 420)
        self.setMaximumSize(560, 520)
        self.setWindowModality(Qt.ApplicationModal)
        self.setStyleSheet(f"QDialog {{ background-color: {COLOR_BG_BASE}; }}")

        # Root layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(S["5"], S["5"], S["5"], S["5"])
        root_layout.setSpacing(S["3"])

        # ── Title ───────────────────────────────────────────────────────
        title = QLabel(
            t("report_issue.title", default="Submit a Report"), self
        )
        title.setProperty("fontRole", "h3")
        title.setAlignment(Qt.AlignCenter)
        root_layout.addWidget(title)

        # ── Subject ─────────────────────────────────────────────────────
        subject_label = QLabel(
            t("report_issue.subject_label", default="Subject"), self
        )
        subject_label.setProperty("fontRole", "label")
        root_layout.addWidget(subject_label)

        self._subject_input = QLineEdit(self)
        self._subject_input.setAccessibleName("Subject")
        self._subject_input.setPlaceholderText(
            t(
                "report_issue.subject_placeholder",
                default="Brief summary of the issue",
            )
        )
        self._subject_input.setStyleSheet(
            f"QLineEdit {{ padding: {SPACE_2}px; border: 1px solid {COLOR_BORDER_MEDIUM}; "
            f"border-radius: {RADIUS_SM}px; background: {COLOR_BG_OVERLAY}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_MD}px; }}"
        )
        root_layout.addWidget(self._subject_input)

        # ── Description ─────────────────────────────────────────────────
        desc_label = QLabel(
            t("report_issue.description_label", default="Description"), self
        )
        desc_label.setProperty("fontRole", "label")
        root_layout.addWidget(desc_label)

        self._description_input = QPlainTextEdit(self)
        self._description_input.setAccessibleName("Description")
        self._description_input.setPlaceholderText(
            t(
                "report_issue.description_placeholder",
                default="Detailed description of the issue",
            )
        )
        self._description_input.setMinimumHeight(100)
        self._description_input.setStyleSheet(
            f"QPlainTextEdit {{ padding: {SPACE_2}px; border: 1px solid {COLOR_BORDER_MEDIUM}; "
            f"border-radius: {RADIUS_SM}px; background: {COLOR_BG_OVERLAY}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_MD}px; }}"
        )
        root_layout.addWidget(self._description_input)

        # ── Severity ────────────────────────────────────────────────────
        severity_label = QLabel(
            t("report_issue.severity_label", default="Severity"), self
        )
        severity_label.setProperty("fontRole", "label")
        root_layout.addWidget(severity_label)

        self._severity_combo = QComboBox(self)
        self._severity_combo.setAccessibleName("Severity")
        self._severity_combo.addItem(
            t("report_issue.severity.low", default="Low"), "low"
        )
        self._severity_combo.addItem(
            t("report_issue.severity.medium", default="Medium"), "medium"
        )
        self._severity_combo.addItem(
            t("report_issue.severity.high", default="High"), "high"
        )
        self._severity_combo.addItem(
            t("report_issue.severity.critical", default="Critical"), "critical"
        )
        self._severity_combo.setStyleSheet(
            f"QComboBox {{ padding: {SPACE_2}px; border: 1px solid {COLOR_BORDER_MEDIUM}; "
            f"border-radius: {RADIUS_SM}px; background: {COLOR_BG_OVERLAY}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_MD}px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox::down-arrow {{ image: none; }}"
        )
        root_layout.addWidget(self._severity_combo)

        # ── Screenshot row ──────────────────────────────────────────────
        screenshot_row = QWidget(self)
        screenshot_layout = QHBoxLayout(screenshot_row)
        screenshot_layout.setContentsMargins(0, 0, 0, 0)
        screenshot_layout.setSpacing(S["3"])

        self._screenshot_btn = QPushButton(
            t("report_issue.attach_screenshot", default="Attach Screenshot"),
            screenshot_row,
        )
        self._screenshot_btn.setAccessibleName("Attach screenshot")
        self._screenshot_btn.setToolTip(
            t(
                "report_issue.button_tooltip",
                default="Attach a screenshot to the report",
            )
        )
        self._screenshot_btn.setStyleSheet(
            f"QPushButton {{ padding: {SPACE_2}px {SPACE_6}px; "
            f"border: 1px solid {COLOR_BORDER_MEDIUM}; "
            f"border-radius: {RADIUS_SM}px; background: {COLOR_BG_CARD}; "
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_MD}px; }}"
            f"QPushButton:hover {{ background: {COLOR_BG_HOVER}; }}"
        )
        self._screenshot_btn.clicked.connect(self._on_attach_screenshot)
        screenshot_layout.addWidget(self._screenshot_btn)

        self._screenshot_label = QLabel("", screenshot_row)
        self._screenshot_label.setProperty("fontRole", "small")
        self._screenshot_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
        self._screenshot_label.setVisible(False)
        screenshot_layout.addWidget(self._screenshot_label, 1)

        root_layout.addWidget(screenshot_row)

        # ── Error label ─────────────────────────────────────────────────
        self._error_label = QLabel("", self)
        self._error_label.setProperty("fontRole", "small")
        self._error_label.setStyleSheet(f"color: {COLOR_ERROR_DEFAULT};")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root_layout.addWidget(self._error_label)

        # ── Button row: Cancel + Submit ─────────────────────────────────
        btn_row = QWidget(self)
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(S["3"])

        self._cancel_btn = QPushButton(
            t("report_issue.cancel", default="Cancel"), btn_row
        )
        self._cancel_btn.setAccessibleName("Cancel")
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ padding: {SPACE_2}px {SPACE_6}px; "
            f"border: 1px solid {COLOR_BORDER_MEDIUM}; "
            f"border-radius: {RADIUS_SM}px; background: {COLOR_BG_CARD}; "
            f"color: {COLOR_TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {COLOR_BG_HOVER}; }}"
            f"QPushButton:disabled {{ color: {COLOR_TEXT_TERTIARY}; }}"
        )
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        btn_layout.addStretch()

        self._submit_btn = QPushButton(
            t("report_issue.submit", default="Submit"), btn_row
        )
        self._submit_btn.setAccessibleName("Submit")
        self._submit_btn.setDefault(True)
        self._submit_btn.setStyleSheet(
            f"QPushButton {{ padding: {SPACE_3}px {SPACE_8}px; border: none; "
            f"border-radius: {RADIUS_SM}px; "
            f"background: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_WHITE}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; font-size: {FONT_SIZE_LG}px; }}"
            f"QPushButton:hover {{ background: {COLOR_ACCENT_HOVER}; }}"
            f"QPushButton:disabled {{ background: {COLOR_BG_OVERLAY}; "
            f"color: {COLOR_TEXT_TERTIARY}; }}"
        )
        self._submit_btn.clicked.connect(self._on_submit_clicked)
        btn_layout.addWidget(self._submit_btn)

        root_layout.addWidget(btn_row)

    # ── Actions ─────────────────────────────────────────────────────────

    def _on_attach_screenshot(self) -> None:
        """Open file picker for a screenshot or remove the current attachment."""
        # Toggle: if a screenshot is already attached, remove it.
        if self._screenshot_bytes is not None:
            self._screenshot_bytes = None
            self._screenshot_filename = ""
            self._screenshot_btn.setText(
                t("report_issue.attach_screenshot", default="Attach Screenshot")
            )
            self._screenshot_label.clear()
            self._screenshot_label.setVisible(False)
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            t("report_issue.attach_screenshot", default="Attach Screenshot"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if not path:
            return

        file_size = os.path.getsize(path)
        if file_size > _MAX_SCREENSHOT_BYTES:
            self._show_error(
                t(
                    "report_issue.screenshot_too_large",
                    default="Screenshot exceeds the 10 MB size limit.",
                )
            )
            return

        with open(path, "rb") as f:
            self._screenshot_bytes = f.read()
        self._screenshot_filename = os.path.basename(path)
        self._screenshot_btn.setText(
            t("report_issue.remove_screenshot", default="Remove Screenshot")
        )
        self._screenshot_label.setText(self._screenshot_filename)
        self._screenshot_label.setVisible(True)
        self._hide_error()

    def _on_submit_clicked(self) -> None:
        """Validate inputs and dispatch the report submission."""
        subject = self._subject_input.text().strip()
        if not subject:
            self._show_error(
                t(
                    "report_issue.subject_required",
                    default="Please enter a subject.",
                )
            )
            self._subject_input.setFocus()
            return

        description = self._description_input.toPlainText().strip()
        if not description:
            self._show_error(
                t(
                    "report_issue.description_required",
                    default="Please enter a description.",
                )
            )
            self._description_input.setFocus()
            return

        severity = self._severity_combo.currentData()

        self._set_busy(True)
        self._hide_error()

        # Spawn background worker
        self._worker = _ReportIssueWorker(
            subject=subject,
            description=description,
            severity=severity,
            screenshot_bytes=self._screenshot_bytes,
            screenshot_filename=self._screenshot_filename or "screenshot.png",
            api_client=self._api_client,
        )
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(
            self._on_submit_result, Qt.QueuedConnection
        )
        self._worker.finished.connect(
            self._thread.quit, Qt.QueuedConnection
        )
        self._worker.finished.connect(
            self._worker.deleteLater, Qt.QueuedConnection
        )
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_submit_result(self, success: bool, message: str) -> None:
        """Handle the worker result."""
        self._set_busy(False)
        if success:
            QMessageBox.information(
                self,
                t(
                    "report_issue.success_title",
                    default="Report Submitted",
                ),
                t(
                    "report_issue.success_message",
                    default="Your report has been submitted successfully. "
                    "We will review it shortly.",
                ),
            )
            self.accept()
        else:
            # Detect connectivity-related errors for a friendlier message.
            lower_msg = message.lower()
            is_offline = any(
                kw in lower_msg
                for kw in (
                    "unreachable",
                    "connection",
                    "connecterror",
                    "circuit breaker",
                    "timeout",
                )
            )
            if is_offline:
                QMessageBox.warning(
                    self,
                    t("report_issue.offline_title", default="Offline"),
                    t(
                        "report_issue.offline_message",
                        default="You appear to be offline. "
                        "Please check your connection and try again.",
                    ),
                )
            else:
                error_msg = t(
                    "report_issue.submit_error",
                    default="Failed to submit report.",
                )
                if message:
                    error_msg = f"{error_msg} {message}"
                self._show_error(error_msg)

    # ── UI state helpers ───────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        enabled = not busy
        self._subject_input.setEnabled(enabled)
        self._description_input.setEnabled(enabled)
        self._severity_combo.setEnabled(enabled)
        self._screenshot_btn.setEnabled(enabled)
        self._submit_btn.setEnabled(enabled)
        self._cancel_btn.setEnabled(enabled)

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.setVisible(True)

    def _hide_error(self) -> None:
        self._error_label.setVisible(False)
        self._error_label.clear()
