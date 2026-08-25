"""Trans.eu provider connection widget.

Manages OAuth connection flow: connect via browser, view status,
test connection, and disconnect. Uses OAuthLoopbackServer for
capturing the authorization code redirect.
"""

from __future__ import annotations

import logging
import webbrowser
from datetime import datetime, timezone

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_TEXT,
    COLOR_NEUTRAL_SUBTLE,
    COLOR_NEUTRAL_TEXT,
    COLOR_SUCCESS_SUBTLE,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_WHITE,
    COLOR_WARNING_SUBTLE,
    COLOR_WARNING_TEXT,
    FONT_SIZE_BASE,
    FONT_SIZE_LG,
    FONT_WEIGHT_BOLD,
    RADIUS_MD,
    RADIUS_PILL,
)

logger = logging.getLogger(__name__)


class ConnectView(QWidget):
    """Widget for managing a Trans.eu provider connection.

    Signals:
        connection_changed: emitted after connect/disconnect completes
            with the new status dict.
    """

    connection_changed = Signal(dict)

    # ── Status constants ───────────────────────────────────────────

    STATUS_DISCONNECTED = "disconnected"
    STATUS_CONNECTING = "connecting"
    STATUS_CONNECTED = "connected"
    STATUS_ERROR = "error"

    def __init__(self, remote_api=None, parent=None):
        super().__init__(parent)
        self._remote_api = remote_api
        self._status = self.STATUS_DISCONNECTED
        self._expires_at: datetime | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._update_status_display)

        self._setup_ui()
        self._update_ui_for_status()

    # ── UI Setup ──────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header row
        header_layout = QHBoxLayout()
        self._title_label = QLabel(t("freight.connection.provider_trans_eu", default="Trans.eu"))
        self._title_label.setStyleSheet(f"font-weight: {FONT_WEIGHT_BOLD}; font-size: {FONT_SIZE_LG}px;")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        # Status badge
        self._status_badge = QLabel(t("freight.connection.status_disconnected", default="Disconnected"))
        self._status_badge.setStyleSheet(
            f"padding: 4px 12px; border-radius: {RADIUS_PILL}px; background: {COLOR_NEUTRAL_SUBTLE}; color: {COLOR_NEUTRAL_TEXT};"
        )
        header_layout.addWidget(self._status_badge)
        layout.addLayout(header_layout)

        # Expiry info
        self._expiry_label = QLabel("")
        self._expiry_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_BASE}px;")
        self._expiry_label.setVisible(False)
        layout.addWidget(self._expiry_label)

        # Error label
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {COLOR_ERROR_TEXT}; font-size: {FONT_SIZE_BASE}px;")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)

        self._connect_btn = QPushButton(t("freight.connection.connect_trans_eu", default="Connect Trans.eu"))
        self._connect_btn.setStyleSheet(
            f"background: {COLOR_ACCENT_PRIMARY}; color: {COLOR_TEXT_WHITE}; padding: 6px 16px; border-radius: {RADIUS_MD}px; border: none;"
        )
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        button_layout.addWidget(self._connect_btn)

        self._test_btn = QPushButton(t("freight.connection.test_button", default="Test"))
        self._test_btn.setStyleSheet(
            f"padding: 6px 12px; border-radius: {RADIUS_MD}px; border: 1px solid {COLOR_BORDER_MEDIUM};"
        )
        self._test_btn.clicked.connect(self._on_test_clicked)
        self._test_btn.setVisible(False)
        button_layout.addWidget(self._test_btn)

        self._disconnect_btn = QPushButton(t("freight.connection.disconnect", default="Disconnect"))
        self._disconnect_btn.setStyleSheet(
            f"padding: 6px 12px; border-radius: {RADIUS_MD}px; border: 1px solid {COLOR_ERROR_DEFAULT}; color: {COLOR_ERROR_TEXT};"
        )
        self._disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        self._disconnect_btn.setVisible(False)
        button_layout.addWidget(self._disconnect_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Bottom separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"background: {COLOR_BORDER_SUBTLE};")
        layout.addWidget(separator)

    # ── Public API ─────────────────────────────────────────────────

    def set_remote_api(self, remote_api):
        """Inject the RemoteFreightExchangeService for API calls."""
        self._remote_api = remote_api

    def update_status(self, status_data: dict | None = None):
        """Update the displayed connection status.

        If status_data is None, fetches from the API.
        """
        if status_data is None and self._remote_api:
            try:
                status_data = self._remote_api.get_trans_eu_status()
            except Exception as e:
                logger.warning("Failed to get Trans.eu status: %s", e)
                self._show_error(str(e))
                return

        if status_data:
            self._status = status_data.get("status", self.STATUS_DISCONNECTED)
            expires_str = status_data.get("expires_at")
            if expires_str:
                try:
                    self._expires_at = datetime.fromisoformat(expires_str)
                except (ValueError, TypeError):
                    self._expires_at = None
            else:
                self._expires_at = None
        else:
            self._status = self.STATUS_DISCONNECTED
            self._expires_at = None

        self._update_ui_for_status()

    # ── UI State ───────────────────────────────────────────────────

    def _update_ui_for_status(self):
        """Update visibility and text based on current status."""
        if self._status == self.STATUS_CONNECTED:
            self._status_badge.setText(t("freight.connection.status_connected", default="Connected"))
            self._status_badge.setStyleSheet(
                f"padding: 4px 12px; border-radius: {RADIUS_PILL}px; background: {COLOR_SUCCESS_SUBTLE}; color: {COLOR_SUCCESS_TEXT};"
            )
            self._connect_btn.setVisible(False)
            self._test_btn.setVisible(True)
            self._disconnect_btn.setVisible(True)
            self._expiry_label.setVisible(True)
            self._start_expiry_timer()
        elif self._status == self.STATUS_CONNECTING:
            self._status_badge.setText(t("freight.connection.status_connecting", default="Connecting..."))
            self._status_badge.setStyleSheet(
                f"padding: 4px 12px; border-radius: {RADIUS_PILL}px; background: {COLOR_WARNING_SUBTLE}; color: {COLOR_WARNING_TEXT};"
            )
            self._connect_btn.setVisible(False)
            self._test_btn.setVisible(False)
            self._disconnect_btn.setVisible(False)
        else:
            self._status_badge.setText(t("freight.connection.status_disconnected", default="Disconnected"))
            self._status_badge.setStyleSheet(
                f"padding: 4px 12px; border-radius: {RADIUS_PILL}px; background: {COLOR_NEUTRAL_SUBTLE}; color: {COLOR_NEUTRAL_TEXT};"
            )
            self._connect_btn.setVisible(True)
            self._test_btn.setVisible(False)
            self._disconnect_btn.setVisible(False)
            self._expiry_label.setVisible(False)
            self._stop_expiry_timer()

    def _start_expiry_timer(self):
        """Start a 30-second timer to update the expiry display."""
        self._update_status_display()
        self._refresh_timer.start(30000)

    def _stop_expiry_timer(self):
        self._refresh_timer.stop()

    def _update_status_display(self):
        """Refresh the expiry label text."""
        if self._expires_at and self._status == self.STATUS_CONNECTED:
            now = datetime.now(timezone.utc)
            if self._expires_at > now:
                ttl = (self._expires_at - now).total_seconds()
                hours = int(ttl // 3600)
                minutes = int((ttl % 3600) // 60)
                self._expiry_label.setText(
                    t(
                        "freight.connection.token_expires_in",
                        default="Token expires in {hours}h {minutes}m",
                        hours=hours,
                        minutes=minutes,
                    )
                )
                if ttl < 600:
                    self._expiry_label.setStyleSheet(f"color: {COLOR_ERROR_TEXT}; font-size: {FONT_SIZE_BASE}px;")
                elif ttl < 1800:
                    self._expiry_label.setStyleSheet(f"color: {COLOR_WARNING_TEXT}; font-size: {FONT_SIZE_BASE}px;")
                else:
                    self._expiry_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_BASE}px;")
            else:
                self._expiry_label.setText(t("freight.connection.token_expired", default="Token expired — reconnect required"))
                self._expiry_label.setStyleSheet(f"color: {COLOR_ERROR_TEXT}; font-size: {FONT_SIZE_BASE}px; font-weight: {FONT_WEIGHT_BOLD};")
        else:
            self._expiry_label.setText("")

    # ── Actions ────────────────────────────────────────────────────

    def _on_connect_clicked(self):
        """Start the OAuth connection flow."""
        if not self._remote_api:
            self._show_error(t("freight.connection.api_not_configured", default="API client not configured"))
            return

        self._set_status(self.STATUS_CONNECTING)
        self._hide_error()

        try:
            from ui.views.freight_exchange.oauth_loopback import OAuthLoopbackServer

            server = OAuthLoopbackServer()
            if not server.start():
                self._show_error(t(
                    "freight.connection.server_start_failed",
                    default="Could not start local server for OAuth callback. All ports in use.",
                ))
                self._set_status(self.STATUS_DISCONNECTED)
                return

            # Build auth URL (client_id and redirect_uri must match registered app)
            redirect_uri = f"http://localhost:{server.port}/trans-eu/callback"
            auth_url = server.build_auth_url(
                client_id="",  # Will be resolved from backend config
                redirect_uri=redirect_uri,
            )

            # The client_id needs to come from the API
            # For now, we'll use a placeholder — the backend uses its own config
            # to exchange the code. The loopback server just captures the code.

            # Override auth URL with the actual Trans.eu auth URL
            # The backend knows client_id; we just need to redirect to the
            # correct auth server. For now, open the URL as-is.
            if not auth_url:
                self._show_error(t("freight.connection.auth_url_failed", default="Could not build auth URL"))
                self._set_status(self.STATUS_DISCONNECTED)
                server.stop()
                return

            webbrowser.open(auth_url)

            # Wait for the callback
            code, error = server.wait_for_code(timeout=120)
            server.stop()

            if error:
                if error == "timeout":
                    self._show_error(t("freight.connection.auth_timeout", default="Authentication timed out. Please try again."))
                elif error == "access_denied":
                    self._show_error(t("freight.connection.access_denied", default="Access was denied. You must grant access to connect."))
                else:
                    self._show_error(t("freight.connection.auth_error", default="Authentication error: {error}", error=error))
                self._set_status(self.STATUS_DISCONNECTED)
                return

            if not code:
                self._show_error(t("freight.connection.no_auth_code", default="No authorization code received."))
                self._set_status(self.STATUS_DISCONNECTED)
                return

            # Exchange the code for tokens via the backend
            result = self._remote_api.connect_trans_eu(
                authorization_code=code,
                redirect_uri=redirect_uri,
            )

            self.update_status(result)
            self._hide_error()
            self.connection_changed.emit(result)

        except Exception as e:
            logger.exception("Failed to connect Trans.eu")
            self._show_error(t("freight.connection.connect_failed", default="Connection failed: {error}", error=e))
            self._set_status(self.STATUS_DISCONNECTED)

    def _on_disconnect_clicked(self):
        """Disconnect from Trans.eu."""
        if not self._remote_api:
            return
        try:
            self._remote_api.disconnect_provider("trans_eu")
            self.update_status({"status": self.STATUS_DISCONNECTED})
            self.connection_changed.emit({"status": self.STATUS_DISCONNECTED})
        except Exception as e:
            self._show_error(t("freight.connection.disconnect_failed", default="Disconnect failed: {error}", error=e))

    def _on_test_clicked(self):
        """Test the Trans.eu connection."""
        if not self._remote_api:
            return
        try:
            result = self._remote_api.test_provider("trans_eu")
            if result.get("status") == "healthy":
                self._hide_error()
                self._status_badge.setText(t("freight.connection.status_connected", default="Connected"))
                self._status_badge.setStyleSheet(
                    f"padding: 4px 12px; border-radius: {RADIUS_PILL}px; background: {COLOR_SUCCESS_SUBTLE}; color: {COLOR_SUCCESS_TEXT};"
                )
            else:
                self._show_error(t(
                    "freight.connection.test_status",
                    default="Connection test: {status}",
                    status=result.get("status", "unknown"),
                ))
        except Exception as e:
            self._show_error(t("freight.connection.test_failed_msg", default="Connection test failed: {error}", error=e))

    # ── Helpers ────────────────────────────────────────────────────

    def _set_status(self, status: str):
        self._status = status
        self._update_ui_for_status()

    def _show_error(self, message: str):
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _hide_error(self):
        self._error_label.setText("")
        self._error_label.setVisible(False)
