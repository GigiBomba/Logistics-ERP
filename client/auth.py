"""Client-side authentication state and JWT token management.

The ``Auth`` class stores access tokens in memory and provides
convenience properties for role gating in the UI layer.
"""

import json
import logging
import threading
import time
from typing import Any, Dict, Optional

import httpx

from client.config import get_client_config

logger = logging.getLogger(__name__)


def _decode_jwt_payload(token: str) -> Dict[str, Any]:
    """Safely decode the claims portion of a JWT *without* signature verification.

    ⚠ This is a client-side convenience — the server always verifies the
    signature.  Only use the returned claims for UI gating (show/hide), never
    for actual authorization decisions.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        decoded = json.loads(
            __import__("base64").urlsafe_b64decode(payload_b64)
        )
        return decoded if isinstance(decoded, dict) else {}
    except Exception as exc:
        logger.debug("Failed to decode JWT payload: %s", exc)
        return {}


class Auth:
    """Holds access + refresh tokens and provides role/expiry helpers."""

    def __init__(
        self,
        token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ) -> None:
        self._token: Optional[str] = token
        self._refresh_token: Optional[str] = refresh_token
        self._refresh_lock = threading.Lock()

    # ── Token accessors ─────────────────────────────────────────────────

    @property
    def token(self) -> Optional[str]:
        return self._token

    @property
    def refresh_token(self) -> Optional[str]:
        return self._refresh_token

    def set_token(self, token: str) -> None:
        self._token = token

    def set_refresh_token(self, refresh_token: Optional[str]) -> None:
        self._refresh_token = refresh_token

    def clear_token(self) -> None:
        self._token = None
        self._refresh_token = None

    # ── HTTP header helper ──────────────────────────────────────────────

    @property
    def headers(self) -> Dict[str, str]:
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    # ── Authentication & session management ─────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    @property
    def is_admin(self) -> bool:
        """Decode the JWT payload and check for the ``admin`` role.

        Returns ``False`` if the token is missing, malformed, or the
        ``role`` claim is not ``"admin"``.
        """
        if not self._token:
            return False
        claims: Dict[str, Any] = _decode_jwt_payload(self._token)
        return claims.get("role") == "admin"

    @property
    def role(self) -> str:
        """Return the role claim from the JWT payload."""
        if not self._token:
            return ""
        try:
            claims: Dict[str, Any] = _decode_jwt_payload(self._token)
            return claims.get("role", "")
        except Exception:
            return ""

    @property
    def is_manager(self) -> bool:
        """True if the JWT role is 'admin' or 'manager'."""
        return self.is_admin or self.role == "manager"

    @property
    def token_expired(self) -> bool:
        """Check the ``exp`` claim (Unix epoch) against the current time.

        Returns ``True`` if the token is missing, has no ``exp`` claim,
        or the expiry is in the past.
        """
        if not self._token:
            return True
        claims: Dict[str, Any] = _decode_jwt_payload(self._token)
        exp: Optional[float] = claims.get("exp")
        if exp is None:
            return True
        return time.time() >= exp

    # ── Login / logout ──────────────────────────────────────────────────

    def login(self, email: str, password: str) -> bool:
        """Authenticate with the backend and store access + refresh tokens.

        On success both tokens are persisted to machine-local storage
        via :meth:`_save_tokens` so the session survives app restarts.

        Args:
            email:    Admin or user email address.
            password: Plain-text password.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        config = get_client_config()
        url = f"{config.api_url}/api/v1/auth/token"

        try:
            resp = httpx.post(
                url,
                data={"username": email, "password": password},
                timeout=30.0,
                verify=config.verify_ssl,
            )
            if resp.status_code != 200:
                logger.warning("Login failed with status %s", resp.status_code)
                return False

            data: Dict[str, Any] = resp.json()
            token: str = data.get("access_token", "")
            if not token:
                return False

            self._token = token
            self._refresh_token = data.get("refresh_token")

            # Persist to machine-local storage (QSettings)
            self._save_tokens()

            return True

        except httpx.RequestError as exc:
            logger.debug("Login request failed: %s", exc)
            return False

    def refresh(self) -> bool:
        """Exchange the refresh token for a new access token.

        Uses the stored ``_refresh_token`` to call ``POST /auth/refresh``.
        On success, updates the in-memory access token and persists both.

        Protected by ``_refresh_lock`` to prevent concurrent refresh calls
        from racing (both would use the same old refresh token; the second
        would fail if the server rotates refresh tokens).

        Returns:
            ``True`` if the access token was refreshed, ``False`` otherwise.
        """
        if not self._refresh_token:
            return False

        with self._refresh_lock:
            return self._do_refresh()

    def _do_refresh(self) -> bool:
        """Core refresh logic — must be called with ``_refresh_lock`` held."""
        config = get_client_config()
        url = f"{config.api_url}/api/v1/auth/refresh"

        try:
            resp = httpx.post(
                url,
                json={"refresh_token": self._refresh_token},
                timeout=30.0,
                verify=config.verify_ssl,
            )
            if resp.status_code != 200:
                logger.warning("Token refresh failed with status %s", resp.status_code)
                return False

            data: Dict[str, Any] = resp.json()
            new_token: str = data.get("access_token", "")
            if not new_token:
                return False

            self._token = new_token
            # Update the refresh token if the server issued a new one
            # (common with refresh-token rotation security policies).
            new_refresh: Optional[str] = data.get("refresh_token")
            if new_refresh:
                self._refresh_token = new_refresh
            self._save_tokens()
            return True

        except httpx.RequestError as exc:
            logger.error("Token refresh request failed: %s", exc)
            return False

    def logout(self) -> None:
        """Clear the stored token and wipe persisted credentials."""
        self.clear_token()
        self._clear_stored_tokens()

    # ── Persistent storage (QSettings) ───────────────────────────────────

    def _settings(self) -> Any:
        """Return a ``QSettings`` instance (lazy — requires running QApp)."""
        from PySide6.QtCore import QSettings
        return QSettings("Operion", "Operion ERP")

    def _save_tokens(self) -> None:
        """Write the current access + refresh tokens to machine-local storage."""
        if not self._token:
            return
        try:
            s = self._settings()
            s.setValue("auth/access_token", self._token)
            if self._refresh_token:
                s.setValue("auth/refresh_token", self._refresh_token)
            s.sync()
            logger.debug("Tokens persisted to machine-local storage.")
        except Exception as exc:
            logger.warning("Failed to persist tokens: %s", exc)

    def _clear_stored_tokens(self) -> None:
        """Remove any persisted credentials from machine-local storage."""
        try:
            s = self._settings()
            s.remove("auth/access_token")
            s.remove("auth/refresh_token")
            s.sync()
            logger.debug("Stored credentials wiped.")
        except Exception as exc:
            logger.warning("Failed to clear stored credentials: %s", exc)

    @classmethod
    def load_from_storage(cls) -> "Auth":
        """Create an ``Auth`` instance hydrated from persisted storage.

        Returns an empty ``Auth()`` (no token) if no stored credentials
        are found.
        """
        try:
            from PySide6.QtCore import QSettings
            s = QSettings("Operion", "Operion ERP")
            token: Optional[str] = s.value("auth/access_token", None)
            ref_token: Optional[str] = s.value("auth/refresh_token", None)
            if token:
                logger.debug("Loaded tokens from persistent storage.")
                return cls(token=token, refresh_token=ref_token)
        except Exception as exc:
            logger.debug("No stored credentials found: %s", exc)
        return cls()
