"""Reusable HTTP client for external API integrations.

Provides: retry with exponential backoff, rate limiting, timeout handling,
error mapping, request/response logging, and correlation ID propagation.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from services.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


@dataclass
class HttpClientConfig:
    """Configuration for ExternalHttpClient."""

    base_url: str
    timeout: float = 30.0
    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 30.0
    rate_limit_rps: float = 0.0  # 0 = no rate limiting
    default_headers: dict[str, str] = field(default_factory=dict)


# Transient HTTP status codes that are safe to retry
TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504}

# Retryable request exception types
RETRYABLE_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


class ExternalHttpClient:
    """Reusable HTTP client for external API integrations.

    Features:
    - Exponential backoff retry on transient errors
    - Rate limiting (configurable requests/second)
    - Request/response logging with correlation IDs
    - Timeout handling
    - Error mapping
    """

    def __init__(self, config: HttpClientConfig) -> None:
        self.config = config
        self._session = requests.Session()
        self._session.headers.update(config.default_headers)
        self._last_request_time = 0.0
        self._rate_lock = threading.Lock()

        # Configure connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=Retry(total=0),  # We handle retries at app level
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    # ── Rate limiting ─────────────────────────────────────────────────

    def _apply_rate_limit(self) -> None:
        """Enforce rate limiting if configured."""
        if self.config.rate_limit_rps <= 0:
            return
        with self._rate_lock:
            elapsed = time.time() - self._last_request_time
            min_interval = 1.0 / self.config.rate_limit_rps
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            self._last_request_time = time.time()

    # ── Retry / backoff ───────────────────────────────────────────────

    def _should_retry(
        self,
        attempt: int,
        response: Optional[requests.Response] = None,
        exception: Optional[BaseException] = None,
    ) -> bool:
        """Determine if a request should be retried."""
        if attempt >= self.config.max_retries:
            return False
        if exception is not None and isinstance(exception, RETRYABLE_EXCEPTIONS):
            return True
        if response is not None and response.status_code in TRANSIENT_STATUSES:
            return True
        return False

    def _backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = self.config.backoff_base * (2.0**attempt)
        return min(delay, self.config.backoff_max)

    # ── Correlation ID ────────────────────────────────────────────────

    @staticmethod
    def _get_correlation_id() -> str:
        """Try to get correlation ID from request context."""
        try:
            from backend.middleware.correlation_middleware import get_correlation_id  # type: ignore[import-untyped]

            return get_correlation_id()
        except (ImportError, LookupError):
            return "no-context"

    # ── Logging ───────────────────────────────────────────────────────

    def _log_request(self, method: str, url: str) -> None:
        cid = self._get_correlation_id()
        logger.debug("[%s] External API request: %s %s", cid, method, url)

    def _log_response(
        self, method: str, url: str, status: int, duration_ms: float
    ) -> None:
        cid = self._get_correlation_id()
        logger.info(
            "[%s] External API response: %s %s \u2192 %d (%.0fms)",
            cid,
            method,
            url,
            status,
            duration_ms,
        )

    # ── Core request method ──────────────────────────────────────────

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Make an HTTP request with retry, rate limiting, and logging.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: URL path (appended to base_url)
            **kwargs: Passed to requests.Session.request()

        Returns:
            requests.Response

        Raises:
            ExternalServiceError: After all retries exhausted
        """
        url = self.config.base_url.rstrip("/") + "/" + path.lstrip("/")
        kwargs.setdefault("timeout", self.config.timeout)

        for attempt in range(self.config.max_retries + 1):
            self._apply_rate_limit()
            self._log_request(method, url)

            start = time.time()
            try:
                response = self._session.request(method, url, **kwargs)
                duration_ms = (time.time() - start) * 1000
                self._log_response(method, url, response.status_code, duration_ms)

                # Client errors (4xx) are not retried except 408/429
                if response.status_code < 500 and response.status_code not in (408, 429):
                    return response

                if self._should_retry(attempt, response=response):
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Retrying %s %s (attempt %d/%d, status %d) after %.1fs",
                        method,
                        url,
                        attempt + 1,
                        self.config.max_retries,
                        response.status_code,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                return response

            except RETRYABLE_EXCEPTIONS as e:
                duration_ms = (time.time() - start) * 1000
                self._log_response(method, url, 0, duration_ms)

                if self._should_retry(attempt, exception=e):
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Retrying %s %s (attempt %d/%d, error: %s) after %.1fs",
                        method,
                        url,
                        attempt + 1,
                        self.config.max_retries,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                raise ExternalServiceError(
                    f"External API call failed after {self.config.max_retries} "
                    f"retries: {method} {url}"
                ) from e

        # Last-attempt response (may be an error status)
        return response  # type: ignore[return-value, unused-ignore]

    # ── Convenience HTTP method wrappers ─────────────────────────────

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

    # ── Lifecycle ────────────────────────────────────────────────────

    def close(self) -> None:
        self._session.close()
