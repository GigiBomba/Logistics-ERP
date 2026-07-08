import os
import time
from collections import defaultdict
from typing import Dict, List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = None, window_seconds: int = 60):
        super().__init__(app)
        # Allow env var override for testing
        self.max_requests = max_requests or int(os.environ.get("OPERION_RATE_LIMIT", "100"))
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = self.requests[client_ip]
        window[:] = [t for t in window if now - t < self.window_seconds]

        if len(window) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests", "retry_after": self.window_seconds},
            )

        window.append(now)
        return await call_next(request)
