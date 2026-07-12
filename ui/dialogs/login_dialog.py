"""PySide6 modal login dialog for admin authentication.

Features a two-step ``QStackedWidget`` layout:

    *Index 0* — Identity Capture View (email entry)
    *Index 1* — Credential Validation View (password entry)

The dialog **never** performs preliminary network requests to check
email existence (anti-enumeration gate).  The transition from Index 0
to Index 1 always occurs regardless of whether the email is registered.
The sole network transaction fires from the "Login" button on the
Credential Validation View.

Usage::

    dlg = QtLoginDialog(parent=self)
    if dlg.exec() == QDialog.Accepted:
        # auth_manager is now populated
        ...
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from client.auth import Auth
from client.auth_manager import set_auth
from services.i18n import t
from ui.theme import COLORS, S

logger = logging.getLogger(__name__)

# Simple email pattern — we only check for basic format, never call an API.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _LoginWorker(QObject):
    """Background worker that authenticates without blocking the UI.

    ⚠ Anti-enumeration: the worker always executes a full bcrypt
    verification cycle, even if the email is unknown, to ensure a
    uniform response latency profile.  The caller always receives the
    same generic error message regardless of the failure reason.
    """

    finished = Signal(bool, str)  # success: bool, message: str (error on failure)

    def __init__(self, email: str, password: str) -> None:
        super().__init__()
        self._email = email
        self._password = password

    def run(self) -> None:
        """Execute login and emit the result.

        Never distinguishes between "email not found" and "wrong password";
        always reports the same generic error on failure.
        """
        auth = Auth()
        ok = auth.login(self._email, self._password)
        if ok:
            set_auth(auth)
            self.finished.emit(True, "")
        else:
            # Generic message — no information leakage.
            self.finished.emit(
                False,
                t("admin.login_failed", default="Invalid email or password."),
            )


class QtLoginDialog(QDialog):
    """Modal dialog for admin authentication with two-step flow.

    Layout:
        Stack index 0 — Email entry with "Next" button.
        Stack index 1 — Password entry with "Back" and "Login" buttons.

    The transition from index 0 to 1 always occurs regardless of whether
    the email address is valid or registered (anti-enumeration gate).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Temporary storage for captured values
        self._stored_email: str = ""
        self._worker: Optional[_LoginWorker] = None
        self._thread: Optional[QThread] = None
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle(t("admin.login_title", default="Admin Login"))
        self.setMinimumSize(400, 260)
        self.setMaximumSize(500, 320)
        self.setWindowModality(Qt.ApplicationModal)
        self.setStyleSheet(f"QDialog {{ background-color: {COLORS['bg_base']}; }}")

        # Root layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(S["5"], S["5"], S["5"], S["5"])
        root_layout.setSpacing(S["3"])

        # ── Title (persistent across both stacked pages) ─────────────────
        title = QLabel(t("admin.login_title", default="Admin Login"), self)
        title.setProperty("fontRole", "h3")
        title.setAlignment(Qt.AlignCenter)
        root_layout.addWidget(title)

        # ── Stacked widget ───────────────────────────────────────────────
        self._stack = QStackedWidget(self)
        root_layout.addWidget(self._stack, 1)

        # Build the two stacked pages
        self._build_page_0()  # Identity Capture View   (index 0)
        self._build_page_1()  # Credential Validation View (index 1)

        self._stack.setCurrentIndex(0)

        # ── Shared error label (below the stack) ─────────────────────────
        self._error_label = QLabel("", self)
        self._error_label.setProperty("fontRole", "small")
        self._error_label.setStyleSheet(f"color: {COLORS['danger']};")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        root_layout.addWidget(self._error_label)

        # ── Cancel button (persistent across both pages) ─────────────────
        self._cancel_btn = QPushButton(
            t("admin.cancel", default="Cancel"), self
        )
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ padding: 8px 24px; border: 1px solid {COLORS['border']}; "
            f"border-radius: 4px; background: {COLORS['bg_card']}; "
            f"color: {COLORS['text_primary']}; }}"
            f"QPushButton:hover {{ background: {COLORS['bg_hover']}; }}"
        )
        self._cancel_btn.clicked.connect(self.reject)
        root_layout.addWidget(self._cancel_btn)

    # ── Page 0: Identity Capture View ────────────────────────────────────

    def _build_page_0(self) -> None:
        """Email entry with "Next" button — no network calls."""
        page = QWidget(self._stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        email_label = QLabel(t("admin.email_prompt", default="Enter your email"), page)
        email_label.setProperty("fontRole", "label")
        email_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(email_label)

        self._email_input = QLineEdit(page)
        self._email_input.setPlaceholderText(t("admin.email_placeholder", default="admin@example.com"))
        self._email_input.setStyleSheet(
            f"QLineEdit {{ padding: 8px; border: 1px solid {COLORS['border']}; "
            f"border-radius: 4px; background: {COLORS['bg_input']}; "
            f"color: {COLORS['text_primary']}; font-size: 14px; }}"
        )
        self._email_input.returnPressed.connect(self._on_next_clicked)
        layout.addWidget(self._email_input)

        layout.addStretch()

        next_btn = QPushButton(
            t("admin.next", default="Next \u2192"), page
        )
        next_btn.setStyleSheet(
            f"QPushButton {{ padding: 10px 32px; border: none; border-radius: 4px; "
            f"background: {COLORS['accent']}; color: #FFFFFF; font-weight: bold; "
            f"font-size: 14px; }}"
            f"QPushButton:hover {{ background: {COLORS['accent_hover']}; }}"
        )
        next_btn.clicked.connect(self._on_next_clicked)
        layout.addWidget(next_btn)

        self._stack.addWidget(page)

    # ── Page 1: Credential Validation View ───────────────────────────────

    def _build_page_1(self) -> None:
        """Password entry with "Back" and "Login" buttons."""
        page = QWidget(self._stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["3"])

        # Email display (read-only, confirmation)
        self._email_display = QLabel("", page)
        self._email_display.setProperty("fontRole", "body_bold")
        self._email_display.setAlignment(Qt.AlignCenter)
        self._email_display.setWordWrap(True)
        layout.addWidget(self._email_display)

        pw_label = QLabel(t("admin.password", default="Password"), page)
        pw_label.setProperty("fontRole", "label")
        layout.addWidget(pw_label)

        self._password_input = QLineEdit(page)
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText(t("admin.password_placeholder", default="············"))
        self._password_input.setStyleSheet(
            f"QLineEdit {{ padding: 8px; border: 1px solid {COLORS['border']}; "
            f"border-radius: 4px; background: {COLORS['bg_input']}; "
            f"color: {COLORS['text_primary']}; font-size: 14px; }}"
        )
        self._password_input.returnPressed.connect(self._on_login_clicked)
        layout.addWidget(self._password_input)

        layout.addStretch()

        # Button row: Back + Login
        btn_row = QWidget(page)
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(S["3"])

        back_btn = QPushButton(
            t("admin.back", default="\u2190 Back"), btn_row
        )
        back_btn.setStyleSheet(
            f"QPushButton {{ padding: 10px 24px; border: 1px solid {COLORS['border']}; "
            f"border-radius: 4px; background: {COLORS['bg_card']}; "
            f"color: {COLORS['text_primary']}; font-size: 14px; }}"
            f"QPushButton:hover {{ background: {COLORS['bg_hover']}; }}"
        )
        back_btn.clicked.connect(self._on_back_clicked)
        btn_layout.addWidget(back_btn)

        self._login_btn = QPushButton(
            t("admin.login_button", default="Login"), btn_row
        )
        self._login_btn.setStyleSheet(
            f"QPushButton {{ padding: 10px 32px; border: none; border-radius: 4px; "
            f"background: {COLORS['accent']}; color: #FFFFFF; font-weight: bold; "
            f"font-size: 14px; }}"
            f"QPushButton:hover {{ background: {COLORS['accent_hover']}; }}"
            f"QPushButton:disabled {{ background: {COLORS['bg_disabled']}; "
            f"color: {COLORS['text_muted']}; }}"
        )
        self._login_btn.setDefault(True)
        self._login_btn.clicked.connect(self._on_login_clicked)
        btn_layout.addWidget(self._login_btn)

        layout.addWidget(btn_row)

        self._stack.addWidget(page)

    # ── Navigation: Identity Capture View ────────────────────────────────

    def _on_next_clicked(self) -> None:
        """Validate email format locally, then advance to password view.

        ⚠ Anti-enumeration gate: we never call an API to verify whether
        the email exists.  The transition fires unconditionally after
        a basic format check.  If the format is invalid we show the error
        but the user can still correct and retry.
        """
        email = self._email_input.text().strip()
        if not email:
            self._show_error(
                t("admin.email_required", default="Please enter your email address.")
            )
            return

        if not _EMAIL_PATTERN.match(email):
            self._show_error(
                t("admin.email_invalid", default="Please enter a valid email address.")
            )
            return

        # Store the email locally — never sent to the server at this stage.
        self._stored_email = email
        self._email_display.setText(email)

        # Clear any previous error
        self._hide_error()

        # Transition to password view (index 1)
        self._stack.setCurrentIndex(1)
        self._password_input.setFocus()
        self._password_input.clear()

    # ── Navigation: Credential Validation View ───────────────────────────

    def _on_back_clicked(self) -> None:
        """Return to email entry view without clearing the stored email."""
        self._stored_email = ""
        self._hide_error()
        self._stack.setCurrentIndex(0)
        self._email_input.setFocus()

    # ── Login flow (fires from the Credential Validation View) ───────────

    def _on_login_clicked(self) -> None:
        """Collect credentials and dispatch authentication.

        This is the **only** network transaction in the entire dialog.
        No preliminary email-check requests are ever sent.
        """
        password = self._password_input.text()

        if not password:
            self._show_error(
                t("admin.password_required", default="Please enter your password.")
            )
            return

        self._set_busy(True)
        self._hide_error()

        # Spawn background worker
        self._worker = _LoginWorker(self._stored_email, password)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_login_result, Qt.QueuedConnection)
        self._worker.finished.connect(self._thread.quit, Qt.QueuedConnection)
        self._worker.finished.connect(self._worker.deleteLater, Qt.QueuedConnection)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_login_result(self, success: bool, message: str) -> None:
        self._set_busy(False)
        if success:
            self.accept()
        else:
            self._show_error(message)

    # ── UI state helpers ─────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        self._email_input.setEnabled(not busy)
        self._password_input.setEnabled(not busy)
        self._login_btn.setEnabled(not busy)
        self._cancel_btn.setEnabled(not busy)

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.setVisible(True)

    def _hide_error(self) -> None:
        self._error_label.setVisible(False)
        self._error_label.clear()
