"""Localhost OAuth callback server for Trans.eu desktop authentication.

Starts a temporary HTTP server on localhost:19999 (falls back to
19998, 19997) to receive the authorization code redirect from
Trans.eu's OAuth Authorization Code flow.

Usage::

    server = OAuthLoopbackServer()
    server.start()
    auth_url = server.build_auth_url(client_id="...", redirect_uri="...")
    webbrowser.open(auth_url)
    code, error = server.wait_for_code(timeout=120)
    server.stop()
    if code:
        # exchange code for tokens via backend API
"""

from __future__ import annotations

import logging
import threading
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

OAUTH_PORT_START = 19999
OAUTH_PORT_MAX = 19997
OAUTH_CALLBACK_PATH = "/trans-eu/callback"

_SUCCESS_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Authentication Successful</title>
<style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f0fdf4;color:#166534;text-align:center} h2{font-size:1.5rem} p{color:#4b5563}</style>
</head><body><div><h2>Authentication successful</h2><p>You may close this window and return to Operion.</p></div>
</body></html>"""

_ERROR_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Authentication Failed</title>
<style>body{{font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#fef2f2;color:#991b1b;text-align:center}} h2{{font-size:1.5rem}} p{{color:#4b5563}}</style>
</head><body><div><h2>Authentication failed</h2><p>{error_message}</p><p>You may close this window and return to Operion.</p></div>
</body></html>"""


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth redirect from Trans.eu's auth server.

    Class-level attributes store the result for the waiting thread.
    """

    # Shared state across all handler instances
    auth_code: str | None = None
    error: str | None = None
    received: threading.Event | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == OAUTH_CALLBACK_PATH:
            params = parse_qs(parsed.query)
            cls = self.__class__
            cls.auth_code = params.get("code", [None])[0]
            cls.error = params.get("error", [None])[0]

            if cls.received:
                cls.received.set()

            if cls.auth_code:
                self._respond(200, _SUCCESS_HTML)
            else:
                error_msg = cls.error or "No authorization code received"
                self._respond(400, _ERROR_HTML.format(error_message=error_msg))
        else:
            self.send_response(404)
            self.end_headers()

    def _respond(self, status: int, body: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress default HTTP server request logging."""
        pass


class OAuthLoopbackServer:
    """Temporary HTTP server for OAuth callback capture.

    Starts on OAUTH_PORT_START (19999), falls back to lower ports
    if occupied. Runs in a daemon thread. Captures one OAuth
    response and signals completion.
    """

    def __init__(self):
        self._port: int = OAUTH_PORT_START
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._received = threading.Event()
        self._state: str | None = None

    @property
    def port(self) -> int:
        return self._port

    def start(self) -> bool:
        """Start the server. Returns True if successful."""
        OAuthCallbackHandler.received = self._received
        OAuthCallbackHandler.auth_code = None
        OAuthCallbackHandler.error = None

        # Try ports from OAUTH_PORT_START down to OAUTH_PORT_MAX
        for port in range(OAUTH_PORT_START, OAUTH_PORT_MAX - 1, -1):
            try:
                self._server = HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
                self._port = port
                break
            except OSError:
                continue
        else:
            logger.error("OAuth loopback server: all ports %d-%d occupied",
                         OAUTH_PORT_MAX, OAUTH_PORT_START)
            return False

        self._received.clear()
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("OAuth loopback server started on port %d", self._port)
        return True

    def stop(self) -> None:
        """Shut down the server."""
        if self._server:
            self._server.shutdown()
            if self._thread:
                self._thread.join(timeout=2)
            self._server.server_close()
            logger.info("OAuth loopback server stopped")

    def wait_for_code(self, timeout: float = 120.0) -> tuple[str | None, str | None]:
        """Wait for the OAuth callback. Returns (code, error)."""
        if self._received.wait(timeout=timeout):
            code = OAuthCallbackHandler.auth_code
            error = OAuthCallbackHandler.error
            return code, error
        return None, "timeout"

    def build_auth_url(self, client_id: str, redirect_uri: str) -> str:
        """Build the Trans.eu OAuth authorization URL with random state."""
        state = uuid.uuid4().hex[:16]
        self._state = state
        return (
            "https://auth.platform.trans.eu/oauth2/auth?"
            f"client_id={client_id}&"
            "response_type=code&"
            f"redirect_uri={redirect_uri}&"
            f"state={state}"
        )
