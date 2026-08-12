"""Double-submit cookie CSRF protection middleware.

Strategy
--------
* **Cookie issuance** — every response that did not carry a ``csrf_token``
  cookie gets a fresh random 32-hex token. The cookie is deliberately
  **NOT** ``HttpOnly`` (the SPA reads it to echo it back in the
  ``X-CSRF-Token`` header) and uses ``SameSite=Lax`` + ``Secure`` in
  production.
* **Enforcement** — on mutating requests (POST/PUT/PATCH/DELETE) from a
  browser context (an ``Origin`` header is present), the ``X-CSRF-Token``
  header must equal the ``csrf_token`` cookie value. Mismatch → 403
  ProblemDetail.
* **Exemptions**
    - ``POST /api/v1/auth/token``      — login happens before CSRF exists.
    - ``/api/v1/webhooks/*``           — HMAC-signed, no browser context.
    - ``POST /api/v1/auth/mfa/verify`` and ``POST /api/v1/auth/mfa/backup-code``
      — mid-login challenge (no browser session yet).
    - requests with **no** ``Origin`` header — desktop/native ERP clients
      send no Origin and are not subject to browser CSRF.

Wire order (main.py): after RateLimitMiddleware (throttle floods before CSRF
work) and before WebhookBodyMiddleware (CSRF only reads headers, so the
request body is untouched; WebhookBody runs later and can still parse the
raw body for signature checks).
"""

import hmac
import logging
import secrets
from typing import Optional, Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.config import BackendSettings
from backend.errors import ErrorCode

logger = logging.getLogger(__name__)

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

_DEFAULT_EXEMPT_PATHS = {
    "/api/v1/auth/token",
    "/api/v1/auth/mfa/verify",
    "/api/v1/auth/mfa/backup-code",
}


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF protection for browser requests."""

    def __init__(
        self,
        app,
        *,
        is_production: bool = False,
        exempt_paths: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(app)
        settings = BackendSettings()
        self._cookie_name = settings.csrf_cookie_name or "csrf_token"
        self._header_name = settings.csrf_header_name or "X-CSRF-Token"
        self._max_age = settings.csrf_cookie_max_age
        self._is_production = is_production
        self._exempt_paths = set(_DEFAULT_EXEMPT_PATHS) | {
            p for p in (exempt_paths or []) if p
        }

    # ── Helpers ────────────────────────────────────────────────────────

    def _is_exempt(self, path: str) -> bool:
        if path in self._exempt_paths:
            return True
        # Any /webhooks/* path — HMAC-signed, never a browser form target.
        if path.startswith("/api/v1/webhooks/"):
            return True
        return False

    def _is_mutating(self, method: str) -> bool:
        return method in _MUTATING_METHODS

    def _csrf_enforced(self, request: Request) -> bool:
        """True when this request must carry a valid CSRF token.

        A request is enforced only when it is mutating, not exempt, and
        carries a browser ``Origin`` header. Desktop/native ERP clients do
        not send Origin and therefore never hit the double-submit check.
        """
        if not self._is_mutating(request.method):
            return False
        if self._is_exempt(request.url.path):
            return False
        return bool(request.headers.get("Origin"))

    def _build_403(self, request: Request) -> JSONResponse:
        logger.warning(
            "CSRF check failed: method=%s path=%s (Origin present, token mismatch/missing)",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=403,
            content={
                "type": f"https://api.operionerp.xyz/errors/{ErrorCode.FORBIDDEN.value}",
                "title": "Forbidden",
                "status": 403,
                "detail": "CSRF token validation failed.",
                "instance": str(request.url),
                "error_code": ErrorCode.FORBIDDEN.value,
            },
        )

    def _maybe_set_cookie(self, request: Request, response: Response) -> None:
        """Set a csrf_token cookie on responses that don't already have one."""
        if self._cookie_name in request.cookies:
            return
        response.set_cookie(
            key=self._cookie_name,
            value=secrets.token_hex(16),  # 32 hex chars, readable by JS
            max_age=self._max_age,
            path="/",
            secure=self._is_production,
            httponly=False,  # the SPA must read it to echo it back
            samesite="lax",
        )

    async def dispatch(self, request: Request, call_next):
        # ── Enforce before the handler runs ──────────────────────────────
        if self._csrf_enforced(request):
            cookie_token = request.cookies.get(self._cookie_name, "")
            header_token = request.headers.get(self._header_name, "")
            if not cookie_token or not header_token or not hmac.compare_digest(
                cookie_token, header_token
            ):
                return self._build_403(request)

        response: Response = await call_next(request)

        # ── Issue the cookie on the way out (only if not already present) ──
        self._maybe_set_cookie(request, response)
        return response
