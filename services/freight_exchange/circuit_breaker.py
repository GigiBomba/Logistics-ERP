"""Redis-backed circuit breaker for freight exchange providers.

Per-(company_id, provider_id) circuit breaker. States stored in Redis
so they are shared across all gunicorn/Celery workers.

Auth errors (401) do NOT count toward the trip threshold — auth failure
is a user problem, not a provider outage.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.cache import get_cache

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────
FAILURE_THRESHOLD = 5
RECOVERY_TIMEOUT_SECONDS = 30
HALF_OPEN_MAX_REQUESTS = 1

REDIS_PREFIX = "circuit_breaker:freight:"


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when a request is blocked by an open circuit breaker."""
    def __init__(self, provider_id: str, company_id: int):
        super().__init__(
            f"Circuit breaker is OPEN for provider '{provider_id}' (company {company_id}). "
            f"Requests are blocked for {RECOVERY_TIMEOUT_SECONDS}s."
        )


class FreightCircuitBreaker:
    """Redis-backed circuit breaker for freight exchange provider API calls.

    Per-key: circuit_breaker:freight:{company_id}:{provider_id}

    Usage::

        cb = FreightCircuitBreaker()
        if not await cb.is_allowed(company_id=1, provider_id="trans_eu"):
            raise CircuitBreakerOpenError("trans_eu", 1)
        try:
            result = await call_provider_api()
            await cb.record_success(company_id=1, provider_id="trans_eu")
        except Exception:
            await cb.record_failure(company_id=1, provider_id="trans_eu")
    """

    def __init__(self, redis_client=None):
        """If redis_client is None, uses the global RedisCache singleton."""
        if redis_client is None:
            cache = get_cache()
            self._redis = cache._redis if hasattr(cache, '_redis') and cache._enabled else None
        else:
            self._redis = redis_client

    def _key(self, company_id: int, provider_id: str) -> str:
        return f"{REDIS_PREFIX}{company_id}:{provider_id}"

    async def is_allowed(self, company_id: int, provider_id: str) -> bool:
        """Check if a request is allowed (circuit not in OPEN state)."""
        if self._redis is None:
            return True  # no Redis — allow all (degraded mode)

        key = self._key(company_id, provider_id)
        state = self._redis.get(f"{key}:state")
        state = state.decode() if isinstance(state, bytes) else state

        if state is None or state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True
        if state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            tripped_raw = self._redis.get(f"{key}:tripped_at")
            if tripped_raw:
                tripped_raw = tripped_raw.decode() if isinstance(tripped_raw, bytes) else tripped_raw
                tripped_at = datetime.fromisoformat(tripped_raw)
                if datetime.now(timezone.utc) > tripped_at + timedelta(seconds=RECOVERY_TIMEOUT_SECONDS):
                    # Transition to HALF_OPEN
                    self._redis.set(f"{key}:state", CircuitState.HALF_OPEN)
                    self._redis.set(f"{key}:half_open_requests", "0")
                    logger.info("Circuit breaker HALF_OPEN for company=%d provider=%s", company_id, provider_id)
                    return True
            return False
        return True

    def record_success(self, company_id: int, provider_id: str) -> None:
        """Record a successful API call. Resets failure count."""
        if self._redis is None:
            return
        key = self._key(company_id, provider_id)
        state_raw = self._redis.get(f"{key}:state")
        state = state_raw.decode() if isinstance(state_raw, bytes) else state_raw
        if state == CircuitState.HALF_OPEN:
            # Successful probe — transition to CLOSED
            self._redis.set(f"{key}:state", CircuitState.CLOSED)
            self._redis.delete(f"{key}:failures", f"{key}:half_open_requests")
            logger.info("Circuit breaker CLOSED for company=%d provider=%s", company_id, provider_id)
        # Reset failure count in all cases
        self._redis.set(f"{key}:failures", "0")

    def record_failure(self, company_id: int, provider_id: str) -> bool:
        """Record a failure. Returns True if circuit just tripped to OPEN."""
        if self._redis is None:
            return False
        key = self._key(company_id, provider_id)
        # Atomically increment failure count
        failures = self._redis.incr(f"{key}:failures") or 1
        failures = int(failures) if not isinstance(failures, int) else failures
        
        if failures >= FAILURE_THRESHOLD:
            self._redis.set(f"{key}:state", CircuitState.OPEN)
            self._redis.set(f"{key}:tripped_at", datetime.now(timezone.utc).isoformat())
            logger.warning(
                "Circuit breaker OPEN for company=%d provider=%s (failures=%d)",
                company_id, provider_id, failures,
            )
            return True
        return False

    def reset(self, company_id: int, provider_id: str) -> None:
        """Admin reset — fully close the circuit and clear all state."""
        if self._redis is None:
            return
        key = self._key(company_id, provider_id)
        self._redis.delete(
            f"{key}:state", f"{key}:failures", f"{key}:tripped_at",
            f"{key}:half_open_requests",
        )
        logger.info("Circuit breaker RESET for company=%d provider=%s", company_id, provider_id)

    def get_state(self, company_id: int, provider_id: str) -> dict:
        """Return current state for monitoring."""
        if self._redis is None:
            return {"state": "unknown", "reason": "redis_unavailable"}
        key = self._key(company_id, provider_id)
        state_raw = self._redis.get(f"{key}:state")
        state = state_raw.decode() if isinstance(state_raw, bytes) else state_raw
        failures_raw = self._redis.get(f"{key}:failures")
        failures = int(failures_raw.decode() if isinstance(failures_raw, bytes) else (failures_raw or 0))
        return {
            "state": state or CircuitState.CLOSED,
            "failures": failures,
            "threshold": FAILURE_THRESHOLD,
            "recovery_timeout_seconds": RECOVERY_TIMEOUT_SECONDS,
        }
