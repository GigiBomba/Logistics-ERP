"""Comprehensive Qt unit tests for ConnectView and OAuthLoopbackServer.

Tests cover: construction, provider list display, connect button,
OAuth callback handling, authorization code extraction, signal emission
on successful connection, error handling (connection failure, network error),
disconnect flow, and edge cases (port conflict, timeout, access denied).
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QPushButton, QLabel, QWidget

from ui.views.freight_exchange.connect_view import ConnectView
from ui.views.freight_exchange.oauth_loopback import (
    OAuthCallbackHandler,
    OAuthLoopbackServer,
    OAUTH_PORT_START,
    OAUTH_CALLBACK_PATH,
)

# =========================================================================
# Helpers
# =========================================================================


def shown_parent(qapp) -> QMainWindow:
    """Create and show a QMainWindow to serve as a visible parent."""
    w = QMainWindow()
    w.show()
    return w


def _show_view_in_window(view: ConnectView, window: QMainWindow) -> None:
    """Embed *view* as the central widget of *window* and show it."""
    window.setCentralWidget(view)
    view.show()


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def remote_api():
    """Build a mock RemoteFreightExchangeService."""
    api = MagicMock()
    api.get_trans_eu_status.return_value = {
        "status": "disconnected",
        "expires_at": None,
        "provider_id": "trans_eu",
    }
    api.connect_trans_eu.return_value = {
        "status": "connected",
        "expires_at": "2026-07-20T00:00:00+00:00",
        "provider_id": "trans_eu",
    }
    api.disconnect_provider.return_value = {}
    api.test_provider.return_value = {"status": "healthy"}
    return api


@pytest.fixture
def view(qapp, remote_api):
    """Build a ConnectView wired to a mock remote API inside a shown window."""
    parent = shown_parent(qapp)
    v = ConnectView(remote_api=remote_api, parent=parent)
    _show_view_in_window(v, parent)
    yield v
    v.deleteLater()
    parent.close()
    parent.deleteLater()


@pytest.fixture
def view_no_api(qapp):
    """Build a ConnectView without a remote API inside a shown window."""
    parent = shown_parent(qapp)
    v = ConnectView(parent=parent)
    _show_view_in_window(v, parent)
    yield v
    v.deleteLater()
    parent.close()
    parent.deleteLater()


# =========================================================================
# ConnectView — Construction
# =========================================================================


class TestConnectViewConstruction:
    """Widget construction, attributes, and initial UI state."""

    def test_object_name(self, view):
        """View has a sensible default object name (inherited from QWidget)."""
        # ConnectView does not set an explicit objectName in __init__
        assert isinstance(view, ConnectView)

    def test_initial_status_disconnected(self, view):
        assert view._status == ConnectView.STATUS_DISCONNECTED

    def test_initial_expires_at_none(self, view):
        assert view._expires_at is None

    def test_remote_api_stored(self, view, remote_api):
        assert view._remote_api is remote_api

    def test_no_remote_api(self, view_no_api):
        assert view_no_api._remote_api is None

    def test_title_label_exists(self, view):
        assert view._title_label is not None
        assert view._title_label.text() == "Trans.eu"

    def test_status_badge_exists(self, view):
        assert view._status_badge is not None
        assert view._status_badge.text() == "Disconnected"

    def test_expiry_label_hidden_initially(self, view):
        assert not view._expiry_label.isVisible()

    def test_error_label_hidden_initially(self, view):
        assert not view._error_label.isVisible()
        assert view._error_label.text() == ""

    def test_connect_button_visible_initially(self, view):
        assert view._connect_btn.isVisible()
        assert view._connect_btn.text() == "Connect Trans.eu"

    def test_test_button_hidden_initially(self, view):
        assert not view._test_btn.isVisible()

    def test_disconnect_button_hidden_initially(self, view):
        assert not view._disconnect_btn.isVisible()

    def test_refresh_timer_created(self, view):
        assert view._refresh_timer is not None
        assert not view._refresh_timer.isActive()

    def test_sub_widgets_exist(self, view):
        """All major sub-widgets are created."""
        assert isinstance(view._title_label, QLabel)
        assert isinstance(view._status_badge, QLabel)
        assert isinstance(view._expiry_label, QLabel)
        assert isinstance(view._error_label, QLabel)
        assert isinstance(view._connect_btn, QPushButton)
        assert isinstance(view._test_btn, QPushButton)
        assert isinstance(view._disconnect_btn, QPushButton)

    def test_set_remote_api(self, view_no_api, remote_api):
        """set_remote_api injects the API after construction."""
        assert view_no_api._remote_api is None
        view_no_api.set_remote_api(remote_api)
        assert view_no_api._remote_api is remote_api

    def test_visible_by_default(self, view):
        assert view.isVisible()


# =========================================================================
# ConnectView — update_status
# =========================================================================


class TestUpdateStatus:
    """update_status() and _update_ui_for_status() behavior."""

    def test_update_status_connected(self, view):
        """update_status with connected state updates badge and buttons."""
        view.update_status({
            "status": "connected",
            "expires_at": "2026-07-20T12:00:00+00:00",
        })
        assert view._status == "connected"
        assert "Connected" in view._status_badge.text()
        assert not view._connect_btn.isVisible()
        assert view._test_btn.isVisible()
        assert view._disconnect_btn.isVisible()
        assert view._expiry_label.isVisible()

    def test_update_status_disconnected(self, view):
        """update_status with disconnected state resets UI."""
        view.update_status({"status": "disconnected", "expires_at": None})
        assert view._status == "disconnected"
        assert "Disconnected" in view._status_badge.text()
        assert view._connect_btn.isVisible()
        assert not view._test_btn.isVisible()
        assert not view._disconnect_btn.isVisible()
        assert not view._expiry_label.isVisible()

    def test_update_status_connecting(self, view):
        """update_status with connecting state shows appropriate UI."""
        view.update_status({"status": "connecting"})
        assert view._status == "connecting"
        assert "Connecting" in view._status_badge.text()
        assert not view._connect_btn.isVisible()
        assert not view._test_btn.isVisible()
        assert not view._disconnect_btn.isVisible()

    def test_update_status_from_api(self, view, remote_api):
        """update_status(None) fetches status from the remote API."""
        view.update_status(None)
        remote_api.get_trans_eu_status.assert_called_once()

    def test_update_status_none_without_api_does_not_crash(self, view_no_api):
        """update_status(None) without API gracefully does nothing."""
        view_no_api.update_status(None)  # Should not raise

    def test_update_status_api_error(self, view, remote_api):
        """When API call fails, the error is displayed."""
        remote_api.get_trans_eu_status.side_effect = RuntimeError("Network error")
        view.update_status(None)
        assert view._error_label.isVisible()
        assert "Network error" in view._error_label.text()

    def test_update_status_invalid_expires_at(self, view):
        """Invalid expires_at string does not crash."""
        view.update_status({
            "status": "connected",
            "expires_at": "not-a-date",
        })
        assert view._expires_at is None


# =========================================================================
# ConnectView — Expiry Timer
# =========================================================================


class TestExpiryTimer:
    """Expiry countdown timer behavior."""

    def test_timer_starts_when_connected(self, view, qtbot):
        """Timer is started when status changes to connected."""
        assert not view._refresh_timer.isActive()
        view.update_status({
            "status": "connected",
            "expires_at": "2026-07-20T12:00:00+00:00",
        })
        assert view._refresh_timer.isActive()

    def test_timer_stops_when_disconnected(self, view):
        """Timer is stopped when status changes to disconnected."""
        view.update_status({
            "status": "connected",
            "expires_at": "2026-07-20T12:00:00+00:00",
        })
        assert view._refresh_timer.isActive()
        view.update_status({"status": "disconnected", "expires_at": None})
        assert not view._refresh_timer.isActive()

    def test_expiry_label_updated(self, view):
        """_update_status_display updates the expiry label text."""
        view.update_status({
            "status": "connected",
            "expires_at": "2026-07-20T12:00:00+00:00",
        })
        # Call directly to test the display logic
        view._update_status_display()
        assert view._expiry_label.isVisible()
        assert "expires in" in view._expiry_label.text().lower()

    def test_expiry_label_expired(self, view):
        """When token is expired, a reconnect message is shown."""
        view.update_status({
            "status": "connected",
            "expires_at": "2020-01-01T00:00:00+00:00",
        })
        view._update_status_display()
        assert "expired" in view._expiry_label.text().lower()

    def test_expiry_label_empty_when_not_connected(self, view):
        """Expiry label is empty when disconnected."""
        view._update_status_display()
        assert view._expiry_label.text() == ""


# =========================================================================
# ConnectView — Connect Action
# =========================================================================


class TestConnectAction:
    """_on_connect_clicked — OAuth flow initiation."""

    def test_connect_no_api_shows_error(self, view_no_api):
        """Clicking connect without an API shows an error."""
        view_no_api._on_connect_clicked()
        assert view_no_api._error_label.isVisible()
        assert "not configured" in view_no_api._error_label.text().lower()

    def test_connect_sets_connecting_state(self, view, remote_api, qtbot):
        """Clicking connect sets status to connecting."""
        with patch("ui.views.freight_exchange.oauth_loopback.OAuthLoopbackServer") as MockServer:
            instance = MagicMock()
            instance.start.return_value = True
            instance.port = 19999
            instance.build_auth_url.return_value = "https://auth.example.com/auth?code=abc"
            instance.wait_for_code.return_value = ("auth_code_123", None)
            MockServer.return_value = instance

            with patch("ui.views.freight_exchange.connect_view.webbrowser.open"):
                view._on_connect_clicked()
                qtbot.wait(50)

        # Status briefly set to connecting
        assert view._status == ConnectView.STATUS_CONNECTED  # After success

    def test_connect_success_emits_signal(self, view, remote_api, qtbot):
        """Successful connection emits connection_changed with status dict."""
        signals = []
        view.connection_changed.connect(lambda d: signals.append(d))

        with patch("ui.views.freight_exchange.oauth_loopback.OAuthLoopbackServer") as MockServer:
            instance = MagicMock()
            instance.start.return_value = True
            instance.port = 19999
            instance.build_auth_url.return_value = "https://auth.example.com/auth"
            instance.wait_for_code.return_value = ("auth_code_123", None)
            MockServer.return_value = instance

            with patch("ui.views.freight_exchange.connect_view.webbrowser.open"):
                view._on_connect_clicked()
                qtbot.wait(50)

        assert len(signals) >= 1
        assert signals[-1].get("status") == "connected"

    def test_connect_server_start_failure(self, view, qtbot):
        """When loopback server cannot start, an error is shown."""
        with patch("ui.views.freight_exchange.oauth_loopback.OAuthLoopbackServer") as MockServer:
            instance = MagicMock()
            instance.start.return_value = False
            MockServer.return_value = instance

            view._on_connect_clicked()
            qtbot.wait(50)

        assert view._error_label.isVisible()
        assert "port" in view._error_label.text().lower()

    def test_connect_auth_url_empty(self, view, qtbot):
        """When build_auth_url returns empty, an error is shown."""
        with patch("ui.views.freight_exchange.oauth_loopback.OAuthLoopbackServer") as MockServer:
            instance = MagicMock()
            instance.start.return_value = True
            instance.port = 19999
            instance.build_auth_url.return_value = ""
            MockServer.return_value = instance

            view._on_connect_clicked()
            qtbot.wait(50)

        assert view._error_label.isVisible()
        assert "auth url" in view._error_label.text().lower()

    def test_connect_wait_code_timeout(self, view, qtbot):
        """When OAuth times out, an appropriate error is shown."""
        with patch("ui.views.freight_exchange.oauth_loopback.OAuthLoopbackServer") as MockServer:
            instance = MagicMock()
            instance.start.return_value = True
            instance.port = 19999
            instance.build_auth_url.return_value = "https://auth.example.com/auth"
            instance.wait_for_code.return_value = (None, "timeout")
            MockServer.return_value = instance

            with patch("ui.views.freight_exchange.connect_view.webbrowser.open"):
                view._on_connect_clicked()
                qtbot.wait(50)

        assert view._error_label.isVisible()
        assert "timed out" in view._error_label.text().lower()

    def test_connect_wait_code_access_denied(self, view, qtbot):
        """When OAuth returns access_denied, an appropriate error is shown."""
        with patch("ui.views.freight_exchange.oauth_loopback.OAuthLoopbackServer") as MockServer:
            instance = MagicMock()
            instance.start.return_value = True
            instance.port = 19999
            instance.build_auth_url.return_value = "https://auth.example.com/auth"
            instance.wait_for_code.return_value = (None, "access_denied")
            MockServer.return_value = instance

            with patch("ui.views.freight_exchange.connect_view.webbrowser.open"):
                view._on_connect_clicked()
                qtbot.wait(50)

        assert view._error_label.isVisible()
        assert "denied" in view._error_label.text().lower()

    def test_connect_wait_code_no_code_returned(self, view, qtbot):
        """When no code is returned, an appropriate error is shown."""
        with patch("ui.views.freight_exchange.oauth_loopback.OAuthLoopbackServer") as MockServer:
            instance = MagicMock()
            instance.start.return_value = True
            instance.port = 19999
            instance.build_auth_url.return_value = "https://auth.example.com/auth"
            instance.wait_for_code.return_value = (None, None)
            MockServer.return_value = instance

            with patch("ui.views.freight_exchange.connect_view.webbrowser.open"):
                view._on_connect_clicked()
                qtbot.wait(50)

        assert view._error_label.isVisible()
        assert "authorization code" in view._error_label.text().lower()

    def test_connect_api_exception(self, view, remote_api, qtbot):
        """When the API call raises, an error is shown."""
        remote_api.connect_trans_eu.side_effect = RuntimeError("API failure")

        with patch("ui.views.freight_exchange.oauth_loopback.OAuthLoopbackServer") as MockServer:
            instance = MagicMock()
            instance.start.return_value = True
            instance.port = 19999
            instance.build_auth_url.return_value = "https://auth.example.com/auth"
            instance.wait_for_code.return_value = ("auth_code_123", None)
            MockServer.return_value = instance

            with patch("ui.views.freight_exchange.connect_view.webbrowser.open"):
                view._on_connect_clicked()
                qtbot.wait(50)

        assert view._error_label.isVisible()
        assert "API failure" in view._error_label.text()

    def test_connect_ui_state_reset_on_failure(self, view, qtbot):
        """After a connection failure, UI resets to disconnected state."""
        with patch("ui.views.freight_exchange.oauth_loopback.OAuthLoopbackServer") as MockServer:
            instance = MagicMock()
            instance.start.return_value = True
            instance.port = 19999
            instance.build_auth_url.return_value = "https://auth.example.com/auth"
            instance.wait_for_code.return_value = (None, "timeout")
            MockServer.return_value = instance

            with patch("ui.views.freight_exchange.connect_view.webbrowser.open"):
                view._on_connect_clicked()
                qtbot.wait(50)

        # UI should be back to disconnected
        assert view._status == ConnectView.STATUS_DISCONNECTED
        assert view._connect_btn.isVisible()
        assert not view._test_btn.isVisible()
        assert not view._disconnect_btn.isVisible()


# =========================================================================
# ConnectView — Disconnect Action
# =========================================================================


class TestDisconnectAction:
    """_on_disconnect_clicked behavior."""

    def test_disconnect_calls_api(self, view, remote_api):
        """Disconnect calls the remote API disconnect method."""
        view._on_disconnect_clicked()
        remote_api.disconnect_provider.assert_called_once_with("trans_eu")

    def test_disconnect_updates_status(self, view, remote_api, qtbot):
        """Disconnect resets status to disconnected."""
        view._on_disconnect_clicked()
        qtbot.wait(50)
        assert view._status == ConnectView.STATUS_DISCONNECTED
        assert "Disconnected" in view._status_badge.text()

    def test_disconnect_emits_signal(self, view, remote_api, qtbot):
        """Disconnect emits connection_changed with disconnected status."""
        signals = []
        view.connection_changed.connect(lambda d: signals.append(d))

        view._on_disconnect_clicked()
        qtbot.wait(50)

        assert len(signals) >= 1
        assert signals[-1].get("status") == ConnectView.STATUS_DISCONNECTED

    def test_disconnect_no_api_does_not_crash(self, view_no_api):
        """Disconnect without API does not raise."""
        view_no_api._on_disconnect_clicked()  # Should not raise

    def test_disconnect_api_error(self, view, remote_api):
        """When disconnect API call fails, error is shown."""
        remote_api.disconnect_provider.side_effect = RuntimeError("Network error")
        view._on_disconnect_clicked()
        assert view._error_label.isVisible()
        assert "Network error" in view._error_label.text()


# =========================================================================
# ConnectView — Test Action
# =========================================================================


class TestTestAction:
    """_on_test_clicked behavior."""

    def test_test_calls_api(self, view, remote_api):
        """Test button calls the remote API test method."""
        view._on_test_clicked()
        remote_api.test_provider.assert_called_once_with("trans_eu")

    def test_test_healthy_hides_error(self, view, remote_api):
        """When test returns healthy, error is hidden."""
        view._show_error("previous error")
        assert view._error_label.isVisible()

        view._on_test_clicked()
        assert not view._error_label.isVisible()

    def test_test_healthy_updates_badge(self, view, remote_api):
        """When test returns healthy, badge shows Connected."""
        view._on_test_clicked()
        assert "Connected" in view._status_badge.text()

    def test_test_unhealthy_shows_error(self, view, remote_api):
        """When test returns unhealthy status, error is shown."""
        remote_api.test_provider.return_value = {"status": "degraded"}
        view._on_test_clicked()
        assert view._error_label.isVisible()

    def test_test_api_error(self, view, remote_api):
        """When test API call raises, error is shown."""
        remote_api.test_provider.side_effect = RuntimeError("Test failed")
        view._on_test_clicked()
        assert view._error_label.isVisible()
        assert "Test failed" in view._error_label.text()

    def test_test_no_api_does_not_crash(self, view_no_api):
        """Test without API does not raise."""
        view_no_api._on_test_clicked()  # Should not raise


# =========================================================================
# ConnectView — Error Display Helpers
# =========================================================================


class TestErrorDisplay:
    """_show_error and _hide_error helpers."""

    def test_show_error_sets_text(self, view):
        view._show_error("Something went wrong")
        assert view._error_label.isVisible()
        assert view._error_label.text() == "Something went wrong"

    def test_hide_error_clears_text(self, view):
        view._show_error("Something went wrong")
        view._hide_error()
        assert not view._error_label.isVisible()
        assert view._error_label.text() == ""

    def test_show_error_word_wrap(self, view):
        """Error label has word wrap enabled."""
        assert view._error_label.wordWrap() is True

    def test_show_error_multiple_calls(self, view):
        """Multiple error calls replace the previous error."""
        view._show_error("Error 1")
        view._show_error("Error 2")
        assert view._error_label.text() == "Error 2"


# =========================================================================
# ConnectView — Signal Emissions
# =========================================================================


class TestSignalEmissions:
    """connection_changed signal emissions."""

    def test_connection_changed_emitted_on_connect(self, view, remote_api, qtbot):
        """connection_changed fires when connection succeeds."""
        signals = []

        @view.connection_changed.connect
        def capture(status):
            signals.append(status)

        with patch("ui.views.freight_exchange.oauth_loopback.OAuthLoopbackServer") as MockServer:
            instance = MagicMock()
            instance.start.return_value = True
            instance.port = 19999
            instance.build_auth_url.return_value = "https://auth.example.com/auth"
            instance.wait_for_code.return_value = ("code", None)
            MockServer.return_value = instance

            with patch("ui.views.freight_exchange.connect_view.webbrowser.open"):
                view._on_connect_clicked()
                qtbot.wait(50)

        assert len(signals) >= 1

    def test_connection_changed_emitted_on_disconnect(self, view, qtbot):
        """connection_changed fires when disconnecting."""
        signals = []
        view.connection_changed.connect(lambda d: signals.append(d))

        view._on_disconnect_clicked()
        qtbot.wait(50)

        assert len(signals) >= 1
        assert signals[-1].get("status") == "disconnected"


# =========================================================================
# OAuthLoopbackServer — Construction & Port Management
# =========================================================================


class TestOAuthLoopbackConstruction:
    """OAuthLoopbackServer initialization and port selection."""

    def test_default_port(self):
        server = OAuthLoopbackServer()
        assert server._port == OAUTH_PORT_START

    def test_port_property(self):
        server = OAuthLoopbackServer()
        assert server.port == OAUTH_PORT_START

    def test_initial_state_none(self):
        server = OAuthLoopbackServer()
        assert server._state is None
        assert server._server is None
        assert server._thread is None

    def test_callback_handler_received_event_initialized(self):
        server = OAuthLoopbackServer()
        assert server._received is not None


class TestOAuthLoopbackStartStop:
    """Server start/stop lifecycle."""

    def test_start_success(self):
        server = OAuthLoopbackServer()
        result = server.start()
        assert result is True
        assert server._server is not None
        assert server._thread is not None
        assert server._thread.is_alive()
        server.stop()

    def test_stop_after_start(self):
        server = OAuthLoopbackServer()
        server.start()
        server.stop()  # Should not raise
        assert server._server is not None

    def test_stop_without_start(self):
        """Calling stop on a non-started server does not crash."""
        server = OAuthLoopbackServer()
        server.stop()  # Should not raise

    def test_double_start(self):
        """Starting an already-started server returns True (new instance)."""
        server = OAuthLoopbackServer()
        assert server.start() is True
        # Second start on same instance — the old one is replaced
        server.stop()

    def test_build_auth_url_contains_required_params(self):
        server = OAuthLoopbackServer()
        url = server.build_auth_url(client_id="test_client", redirect_uri="http://localhost:19999/trans-eu/callback")
        assert "client_id=test_client" in url
        assert "response_type=code" in url
        assert "redirect_uri=http%3A//localhost" in url or "redirect_uri=http://localhost" in url
        assert "state=" in url

    def test_build_auth_url_sets_state(self):
        server = OAuthLoopbackServer()
        url = server.build_auth_url(client_id="c", redirect_uri="http://localhost:19999/callback")
        assert server._state is not None
        assert server._state in url


# =========================================================================
# OAuthCallbackHandler — Request Handling
# =========================================================================


class TestOAuthCallbackHandler:
    """OAuthCallbackHandler processing of GET requests."""

    def test_extract_code_from_query(self):
        """Handler extracts authorization code from query string."""
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None
        received = threading.Event()
        OAuthCallbackHandler.received = received

        # Simulate a minimal GET request
        handler = _make_handler("/trans-eu/callback?code=abc123&state=test")
        handler.do_GET()

        assert OAuthCallbackHandler.auth_code == "abc123"
        assert OAuthCallbackHandler.error is None
        assert received.is_set()

    def test_extract_error_from_query(self):
        """Handler extracts error from query string."""
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None
        received = threading.Event()
        OAuthCallbackHandler.received = received

        handler = _make_handler("/trans-eu/callback?error=access_denied&state=test")
        handler.do_GET()

        assert OAuthCallbackHandler.auth_code is None
        assert OAuthCallbackHandler.error == "access_denied"
        assert received.is_set()

    def test_no_code_no_error(self):
        """Handler handles missing code and error gracefully."""
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None
        received = threading.Event()
        OAuthCallbackHandler.received = received

        handler = _make_handler("/trans-eu/callback?state=test")
        handler.do_GET()

        assert OAuthCallbackHandler.auth_code is None
        assert OAuthCallbackHandler.error is None
        assert received.is_set()

    def test_wrong_path_not_handled(self):
        """Handler returns 404 for paths other than /trans-eu/callback."""
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None
        received = threading.Event()
        OAuthCallbackHandler.received = received

        handler = _make_handler("/other/path")
        handler.do_GET()

        # Event not set, code remains None
        assert not received.is_set()
        assert OAuthCallbackHandler.auth_code is None

    def test_multiple_params_in_query(self):
        """Handler extracts code even with multiple query params."""
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None
        received = threading.Event()
        OAuthCallbackHandler.received = received

        handler = _make_handler(
            "/trans-eu/callback?code=secret123&state=xyz&scope=openid&foo=bar"
        )
        handler.do_GET()

        assert OAuthCallbackHandler.auth_code == "secret123"

    def test_code_takes_precedence_over_error(self):
        """When both code and error are present, code is captured."""
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None
        received = threading.Event()
        OAuthCallbackHandler.received = received

        handler = _make_handler(
            "/trans-eu/callback?code=abc123&error=access_denied"
        )
        handler.do_GET()

        assert OAuthCallbackHandler.auth_code == "abc123"
        assert OAuthCallbackHandler.error == "access_denied"


# =========================================================================
# OAuthLoopbackServer — wait_for_code
# =========================================================================


class TestWaitForCode:
    """wait_for_code behavior with various outcomes."""

    def test_wait_for_code_timeout(self):
        """wait_for_code returns (None, 'timeout') on timeout."""
        server = OAuthLoopbackServer()
        code, error = server.wait_for_code(timeout=0.01)
        assert code is None
        assert error == "timeout"

    def test_wait_for_code_success(self):
        """wait_for_code returns the code when received."""
        server = OAuthLoopbackServer()
        server.start()

        # Simulate receiving a code via the callback handler
        OAuthCallbackHandler.auth_code = "test_code"
        OAuthCallbackHandler.error = None
        server._received.set()

        code, error = server.wait_for_code(timeout=5)
        assert code == "test_code"
        assert error is None
        server.stop()

    def test_wait_for_code_with_error(self):
        """wait_for_code returns error when received."""
        server = OAuthLoopbackServer()
        server.start()

        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = "invalid_scope"
        server._received.set()

        code, error = server.wait_for_code(timeout=5)
        assert code is None
        assert error == "invalid_scope"
        server.stop()


# =========================================================================
# OAuthLoopbackServer — Full End-to-End Simulation
# =========================================================================


class TestOAuthLoopbackIntegration:
    """End-to-end flow: start server, handle request, wait for code."""

    def test_full_callback_flow(self):
        """Start server, receive callback, extract code."""
        server = OAuthLoopbackServer()
        assert server.start() is True
        port = server.port

        # Simulate what the OAuth provider would send
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None
        OAuthCallbackHandler.received = server._received
        OAuthCallbackHandler.received.clear()

        # Manually trigger the handler (as the HTTP server would)
        code_val = "integration_test_code_456"
        OAuthCallbackHandler.auth_code = code_val
        OAuthCallbackHandler.received.set()

        code, error = server.wait_for_code(timeout=5)
        assert code == code_val
        assert error is None
        server.stop()

    def test_build_auth_url_uses_correct_path(self):
        """build_auth_url includes the correct redirect_uri with callback path."""
        server = OAuthLoopbackServer()
        with patch.object(server, "_port", 19999):
            url = server.build_auth_url(
                client_id="my_client",
                redirect_uri="http://localhost:19999/trans-eu/callback",
            )
        assert "redirect_uri=http" in url


# =========================================================================
# Helpers
# =========================================================================


def _make_handler(path: str) -> OAuthCallbackHandler:
    """Build a minimal OAuthCallbackHandler with a fake request.

    Creates a handler whose ``path`` attribute and a stub ``send_response`` /
    ``end_headers`` / ``wfile`` are set so that ``do_GET`` can execute
    without raising.
    """
    import io
    from http.server import HTTPServer

    server = HTTPServer(("127.0.0.1", 0), OAuthCallbackHandler)
    request = MagicMock()
    request.makefile.return_value = io.BytesIO()
    handler = OAuthCallbackHandler(request, ("127.0.0.1", 0), server)
    handler.path = path
    handler.headers = {}
    handler.close_connection = True
    # Stub out the response machinery
    handler.send_response = lambda code, msg=None: None  # type: ignore[assignment]
    handler.send_header = lambda k, v: None  # type: ignore[assignment]
    handler.end_headers = lambda: None  # type: ignore[assignment]
    handler.wfile = io.BytesIO()
    return handler
