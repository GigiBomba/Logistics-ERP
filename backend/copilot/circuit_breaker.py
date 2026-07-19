"""Circuit Breaker — prevents autonomous mode from running away.

When tripped: Autonomous Mode reverts to manual confirmation for every action,
a notification fires to the company admin, and the trip event is written to the audit log.

Blueprint: §23.1
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class CircuitBreakerConfig(BaseModel):
    """Configuration for a per-company circuit breaker."""
    model_config = ConfigDict(extra="forbid")

    max_level2_actions_per_hour: int = 20         # per company, tunable in settings
    max_consecutive_failures: int = 3               # trips the breaker regardless of hourly count
    max_identical_action_repeats: int = 5            # e.g. 5x dispatch.cancel in a row is almost certainly wrong
    cooldown_minutes_after_trip: int = 60


class CircuitBreakerState(BaseModel):
    """Current state of a per-company circuit breaker. Stored in Redis."""
    model_config = ConfigDict(extra="forbid")

    company_id: int
    tripped: bool = False
    tripped_at: Optional[datetime] = None
    tripped_reason: Optional[str] = None
    actions_this_window: int = 0
    consecutive_failures: int = 0

    def is_cooled_down(self, config: CircuitBreakerConfig) -> bool:
        """Check whether the cooldown period has elapsed."""
        if not self.tripped or not self.tripped_at:
            return True
        cooldown = timedelta(minutes=config.cooldown_minutes_after_trip)
        return datetime.utcnow() > self.tripped_at + cooldown


class CircuitBreaker:
    """Manages per-company circuit breakers for Autonomous Mode.

    PHASE 0 STUB — full implementation in Phase 4.
    """

    _states: Dict[int, CircuitBreakerState] = {}
    _states_lock = threading.Lock()
    _config: CircuitBreakerConfig = CircuitBreakerConfig()

    def get_state(self, company_id: int) -> CircuitBreakerState:
        """Get or create the circuit breaker state for a company."""
        with self._states_lock:
            if company_id not in self._states:
                self._states[company_id] = CircuitBreakerState(company_id=company_id)
            return self._states[company_id]

    def record_success(self, company_id: int, tool_name: str) -> None:
        """Record a successful autonomous action."""
        state = self.get_state(company_id)
        state.consecutive_failures = 0
        state.actions_this_window += 1
        logger.debug("Circuit breaker: company=%d action=%s succeeded", company_id, tool_name)

    def record_failure(self, company_id: int, tool_name: str, error: str) -> bool:
        """Record a failed autonomous action. Returns True if the breaker tripped."""
        state = self.get_state(company_id)
        state.consecutive_failures += 1
        state.actions_this_window += 1

        if state.consecutive_failures >= self._config.max_consecutive_failures:
            self._trip(company_id, f"Max consecutive failures ({state.consecutive_failures}) reached")
            return True
        return False

    def _trip(self, company_id: int, reason: str) -> None:
        """Trip the circuit breaker for a company."""
        state = self.get_state(company_id)
        state.tripped = True
        state.tripped_at = datetime.utcnow()
        state.tripped_reason = reason
        logger.warning("CIRCUIT BREAKER TRIPPED | company=%d reason=%s", company_id, reason)

    def reset(self, company_id: int) -> None:
        """Admin-initiated reset — only allowed after cooldown or explicit override."""
        state = self.get_state(company_id)
        state.tripped = False
        state.tripped_at = None
        state.tripped_reason = None
        state.consecutive_failures = 0
        state.actions_this_window = 0
        logger.info("Circuit breaker reset for company=%d", company_id)

    def is_allowed(self, company_id: int) -> bool:
        """Check whether an autonomous action is currently allowed."""
        state = self.get_state(company_id)
        if not state.tripped:
            return True
        if self._config.cooldown_minutes_after_trip == 0:
            return False
        return state.is_cooled_down(self._config)


# Global singleton
_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get the global CircuitBreaker singleton."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker


async def check_circuit_breaker_and_block(
    company_id: int,
    conversation_id: str,
) -> Optional[str]:
    """Check circuit breaker and return an i18n message_key if blocked.

    Returns None if allowed, a message_key string if blocked.

    Blueprint: §23.1, §23.5.
    """
    cb = get_circuit_breaker()
    if not cb.is_allowed(company_id):
        logger.warning("Circuit breaker tripped: company=%d conv=%s", company_id, conversation_id)
        return "copilot.error.circuit_breaker_tripped"
    return None
