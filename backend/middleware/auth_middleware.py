"""API Key authentication middleware.

If ``OPERION_API_KEY`` environment variable is set, all requests
must include the ``X-API-Key`` header matching that value.
If no key is configured, authentication is skipped (open API).

Used as an ASGI middleware in ``backend/main.py``.

Usage::

    export OPERION_API_KEY=my-secret-key-123
    python -m uvicorn backend.main:app
"""

import hmac
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import Config

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """Validate ``X-API-Key`` header against ``Config.API_KEY``."""

    def __init__(self, app):
        super().__init__(app)
        self._api_key = Config.API_KEY
        self._enabled = bool(self._api_key)
        if not self._api_key:
            logger.critical(
                "OPERION_API_KEY is not set — API key middleware is DISABLED. "
                "All requests are accepted without API key validation."
            )

    async def dispatch(self, request: Request, call_next):
        if not self._enabled:
            return await call_next(request)

        # Skip auth for Swagger docs (use startswith for sub-resources)
        skip_prefixes = ("/docs", "/redoc", "/openapi.json")
        if request.url.path.startswith(skip_prefixes):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(api_key, self._api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid API key"},
            )

        return await call_next(request)
