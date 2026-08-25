from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Dict, List, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.errors import ErrorCode

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiting backed by Redis (preferred) or in-memory dict.

    Redis backend provides accurate distributed rate limiting across
    gunicorn workers.  Falls back to in-memory if Redis is unavailable
    (with a warning in production).
    """

    _PURGE_INTERVAL = 100  # Purge stale in-memory entries every N requests
    _redis_client: Optional[object] = None
    _redis_warned: bool = False

    def __init__(self, app, max_requests: int = None, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests or int(os.environ.get("OPERION_RATE_LIMIT", "100"))
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self._request_count = 0
        self._env = os.environ.get("OPERION_ENV", "development")

        # Try to connect to Redis once at startup
        redis_url = os.environ.get("OPERION_REDIS_URL", "")
        redis_password = os.environ.get("OPERION_REDIS_PASSWORD", "")
        if redis_url:
            try:
                import redis as _redis
                client = _redis.Redis.from_url(redis_url, socket_timeout=2, password=redis_password or None)
                client.ping()
                self._redis_client = client
                logger.info("RateLimitMiddleware using Redis backend at %s", redis_url)
            except Exception:
                if self._env == "production":
                    logger.error(
                        "RateLimitMiddleware: OPERION_REDIS_URL=%s but Redis is "
                        "unreachable. Falling back to in-memory — rate limits "
                        "will NOT be shared across gunicorn workers.",
                        redis_url,
                    )
                else:
                    logger.debug("RateLimitMiddleware: Redis unavailable, using in-memory.")

    def _redis_key(self, client_ip: str) -> str:
        return f"ratelimit:{client_ip}"

    def _check_redis(self, client_ip: str) -> bool:
        """Check rate limit via Redis sorted set. Returns True if allowed."""
        client = self._redis_client
        if client is None:
            return False  # caller falls through to in-memory

        now = time.time()
        key = self._redis_key(client_ip)
        window_start = now - self.window_seconds

        try:
            # Remove entries outside the window
            client.zremrangebyscore(key, 0, window_start)
            # Count remaining entries
            count = client.zcard(key)
            if count is not None and count >= self.max_requests:
                return True  # blocked
            # Record this request
            client.zadd(key, {str(now): now})
            client.expire(key, self.window_seconds)
            return False  # allowed
        except Exception:
            if self._env == "production" and not self._redis_warned:
                logger.error("RateLimitMiddleware: Redis operation failed, falling back to in-memory.")
                self._redis_warned = True
            return False  # fall through to in-memory

    def _purge_stale(self, now: float) -> None:
        """Remove entries for IPs whose last request is outside the window."""
        cutoff = now - self.window_seconds
        stale_ips = [ip for ip, times in self.requests.items()
                     if not times or max(times) < cutoff]
        for ip in stale_ips:
            del self.requests[ip]

    async def dispatch(self, request: Request, call_next):
        forwarded = request.headers.get("X-Forwarded-For", "")
        client_ip = forwarded.split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )

        # Try Redis first
        if self._redis_client is not None:
            blocked = self._check_redis(client_ip)
            if blocked:
                logger.warning(
                    "Rate limit exceeded: client=%s path=%s limit=%d per %ds",
                    client_ip,
                    request.url.path,
                    self.max_requests,
                    self.window_seconds,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests",
                        "error_code": ErrorCode.RATE_LIMITED.value,
                        "retry_after": self.window_seconds,
                    },
                )
            return await call_next(request)

        # Fallback: in-memory
        now = time.time()
        window = self.requests[client_ip]
        window[:] = [t for t in window if now - t < self.window_seconds]

        if len(window) >= self.max_requests:
            logger.warning(
                "Rate limit exceeded: client=%s path=%s limit=%d per %ds",
                client_ip,
                request.url.path,
                self.max_requests,
                self.window_seconds,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests",
                    "error_code": ErrorCode.RATE_LIMITED.value,
                    "retry_after": self.window_seconds,
                },
            )

        window.append(now)

        self._request_count += 1
        if self._request_count % self._PURGE_INTERVAL == 0:
            self._purge_stale(now)

        return await call_next(request)
