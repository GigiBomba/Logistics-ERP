import os
import time
from collections import defaultdict
from typing import Dict, List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class RateLimitMiddleware(BaseHTTPMiddleware):
    _PURGE_INTERVAL = 100  # Purge stale entries every N requests

    def __init__(self, app, max_requests: int = None, window_seconds: int = 60):
        super().__init__(app)
        # Allow env var override for testing
        self.max_requests = max_requests or int(os.environ.get("OPERION_RATE_LIMIT", "100"))
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self._request_count = 0

    def _purge_stale(self, now: float) -> None:
        """Remove entries for IPs whose last request is outside the window."""
        cutoff = now - self.window_seconds
        stale_ips = [ip for ip, times in self.requests.items()
                     if not times or max(times) < cutoff]
        for ip in stale_ips:
            del self.requests[ip]

    async def dispatch(self, request: Request, call_next):
        # Respect X-Forwarded-For when behind a reverse proxy
        forwarded = request.headers.get("X-Forwarded-For", "")
        client_ip = forwarded.split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        now = time.time()
        window = self.requests[client_ip]
        window[:] = [t for t in window if now - t < self.window_seconds]

        if len(window) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests", "retry_after": self.window_seconds},
            )

        window.append(now)

        # Periodic stale-entry purge to prevent memory leak
        self._request_count += 1
        if self._request_count % self._PURGE_INTERVAL == 0:
            self._purge_stale(now)

        return await call_next(request)
