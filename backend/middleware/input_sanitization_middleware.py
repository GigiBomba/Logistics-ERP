"""FastAPI middleware for request-body input sanitization.

Registered in ``backend/main.py`` alongside other middlewares.
Intercepts all write-method requests and sanitizes string fields.
"""

from __future__ import annotations

import json
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from backend.middleware.input_sanitizer import sanitize_free_text, sanitize_json_field

logger = logging.getLogger("api.input_sanitizer")


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Middleware that sanitizes string fields in JSON request bodies.

    Applies :func:`sanitize_free_text` to every string value in the
    request body for write operations (POST/PATCH/PUT).  Read operations
    (GET) are skipped — query parameters are validated by fastapi but
    not content-sanitized at this layer.

    Authentication paths are excluded because passwords/tokens are
    not natural-language text and should not be transformed.
    """

    SKIP_PATHS: frozenset[str] = frozenset({
        "/api/v1/auth/token",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/reset-password",
    })

    async def dispatch(self, request: Request, call_next):
        if (
            request.method in ("POST", "PATCH", "PUT")
            and request.url.path not in self.SKIP_PATHS
        ):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body_bytes = await request.body()
                    if body_bytes:
                        body = json.loads(body_bytes)
                        sanitized = sanitize_json_field(body)
                        sanitized_bytes = json.dumps(sanitized).encode("utf-8")
                        request._body = sanitized_bytes
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass  # Let the endpoint validate the body normally
                except Exception as exc:
                    logger.debug(
                        "Body sanitization failed for %s: %s",
                        request.url.path, exc,
                    )

        response = await call_next(request)
        return response
