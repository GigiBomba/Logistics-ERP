"""Security headers middleware for FastAPI backend."""
from __future__ import annotations

from collections.abc import Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

API_DOMAIN = "https://api.operionerp.xyz"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security-related HTTP headers to all responses.

    Parameters
    ----------
    is_production :
        When ``False``, cross-orinity policies are relaxed so that Flutter
        web (running on a random localhost port) can reach the API.
    cors_origins :
        Explicit list of CORS origins.  Used to populate the CSP
        ``connect-src`` directive so that permitted cross-origin fetch/XHR
        requests are not also blocked by the Content Security Policy.
    """

    def __init__(
        self,
        app,
        *,
        is_production: bool = True,
        cors_origins: Sequence[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._is_production = is_production

        # Build connect-src: self + API domain + all explicit CORS origins
        connect_src = ["'self'", API_DOMAIN]
        if cors_origins:
            for origin in cors_origins:
                o = origin.strip()
                if o and o not in connect_src:
                    connect_src.append(o)

        # In development, also allow any localhost origin (Flutter web
        # picks a random port each run).
        if not is_production:
            connect_src.append("http://localhost:*")
            connect_src.append("http://127.0.0.1:*")

        self._connect_src = " ".join(connect_src)

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # HSTS: force HTTPS for 1 year, include subdomains
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Restrict referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        # Scoped to only domains Operion actually needs:
        # - Self (API origin)
        # - Leaflet tile providers for route planner maps
        # - Data: URIs for inline images
        # - Google Fonts if used (check ui/ for font sources)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https://*.tile.openstreetmap.org data:; "
            "font-src 'self'; "
            f"connect-src {self._connect_src}; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        # Permissions policy: restrict browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(self), "
            "interest-cohort=()"
        )

        # Cross-origin policies — relax in dev so Flutter web can reach the
        # API from its random localhost port.
        if self._is_production:
            response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        return response
