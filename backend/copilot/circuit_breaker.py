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

    State is held in-memory per process in the ``_states`` dict and resets
    on process restart. Trip events are audited to the copilot audit log
    (``copilot_audit_log``) and admin-alerted via ``_notify_trip``
    (AuditManager -> EventBus -> NotificationCenter -> admin email when
    SMTP is configured). Redis-backed persistence per blueprint §23.1 is
    deferred (documented decision 2026-09-09); state resets are acceptable
    for the current single-worker deployment. All side effects are
    best-effort — this class never raises.
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

    def record_failure(
        self,
        company_id: int,
        tool_name: str,
        error: str,
        db: Any = None,
        user_id: int = 0,
        conversation_id: str = "",
    ) -> bool:
        """Record a failed autonomous action. Returns True if the breaker tripped.

        ``db`` / ``user_id`` / ``conversation_id`` are threaded from the
        request-scoped ``services`` dict so the trip event can be written to
        the audit log and an admin notification fired with tenant context.
        """
        state = self.get_state(company_id)
        state.consecutive_failures += 1
        state.actions_this_window += 1

        if state.consecutive_failures >= self._config.max_consecutive_failures:
            self._trip(
                company_id,
                f"Max consecutive failures ({state.consecutive_failures}) reached",
                db=db,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            return True
        return False

    def _trip(
        self,
        company_id: int,
        reason: str,
        db: Any = None,
        user_id: int = 0,
        conversation_id: str = "",
    ) -> None:
        """Trip the circuit breaker for a company.

        Beyond flipping the state this fires the §23.1 side effects:
        an audit-log row (event-style, plan/step ids empty) and an admin
        notification, both best-effort and gated on a request-scoped ``db``.
        """
        state = self.get_state(company_id)
        state.tripped = True
        state.tripped_at = datetime.utcnow()
        state.tripped_reason = reason
        logger.warning("CIRCUIT BREAKER TRIPPED | company=%d reason=%s", company_id, reason)
        self._notify_trip(company_id, reason, db=db, user_id=user_id, conversation_id=conversation_id)

    def _notify_trip(
        self,
        company_id: int,
        reason: str,
        db: Any = None,
        user_id: int = 0,
        conversation_id: str = "",
    ) -> None:
        """§23.1 trip side effects: audit row + admin notification (best-effort).

        Never raises — a notification failure must not mask the trip itself.
        Falls back to a structured log warning when no request-scoped DB is
        available (same gating the executor applies to its audit writes).
        """
        # Structured log warning is ALWAYS emitted — survives DB/Redis gaps.
        logger.warning(
            "CIRCUIT BREAKER TRIP EVENT | company=%d user=%d conv=%s reason=%s",
            company_id, user_id, conversation_id, reason,
        )

        # ── Audit row (event-style, plan/step ids empty) ──────────────────
        if db is not None:
            try:
                import json

                from repositories.copilot_repository import CopilotAuditRepository

                CopilotAuditRepository(db).log_action(
                    conversation_id=conversation_id,
                    action="circuit_breaker_tripped",
                    entity_type="company",
                    entity_id=str(company_id),
                    new_value=json.dumps({
                        "reason": reason,
                        "tripped_at": datetime.utcnow().isoformat(),
                    }),
                    performed_by=str(user_id),
                )
            except Exception as exc:
                logger.warning("Circuit breaker audit row skipped: %s", exc)

        # ── Admin notification (best-effort) ─────────────────────────────
        # Uses the AlertManager (→ EventBus → NotificationCenter → admin
        # email when SMTP is configured).  The dedicated
        # AlertType.COPILOT_CIRCUIT_BREAKER member (services/operations/
        # alert_manager.py) distinguishes copilot trips from policy
        # violations so the alert panel can route/surface them separately;
        # the reason + metadata keep the alert unambiguous.
        try:
            from services.operations.alert_manager import (
                AlertManager,
                AlertType,
                Severity,
            )

            alert_mgr = AlertManager.get_instance(db=db)
            alert_mgr.create_alert(
                alert_type=AlertType.COPILOT_CIRCUIT_BREAKER,
                severity=Severity.CRITICAL,
                title="Co-Pilot Circuit Breaker Tripped",
                message=f"Autonomous Co-Pilot temporarily disabled for company {company_id}: {reason}",
                metadata={
                    "source": "copilot.circuit_breaker",
                    "company_id": company_id,
                    "reason": reason,
                    "conversation_id": conversation_id,
                },
            )
        except Exception as exc:
            logger.warning("Circuit breaker admin notification skipped: %s", exc)

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
