"""Human Handoff & De-escalation (§23.7).

Tracks conversation quality and hands off to manual UI when
the Co-Pilot is struggling (repeated low confidence, cancellations,
failed clarifications).

Blueprint: §23.7 — Human Handoff & De-escalation.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class HandoffState:
    """Tracks de-escalation state for a single conversation."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self.low_confidence_count: int = 0
        self.cancellation_count: int = 0
        self.failed_clarification_count: int = 0
        self.last_intent: Optional[str] = None
        self.handoff_triggered: bool = False
        self.reason: Optional[str] = None
        self.created_at: float = time.time()

    def record_low_confidence(self, intent_name: str) -> None:
        """Increment low confidence count. Resets if intent changes."""
        if not intent_name:
            return  # Ignore empty intent names
        if intent_name == self.last_intent:
            self.low_confidence_count += 1
        else:
            self.low_confidence_count = 1
        self.last_intent = intent_name

    def record_cancellation(self, intent_name: str) -> None:
        """Increment cancellation count."""
        if not intent_name:
            return
        if intent_name == self.last_intent:
            self.cancellation_count += 1
        else:
            self.cancellation_count = 1
        self.last_intent = intent_name

    def record_failed_clarification(self) -> None:
        """Increment failed clarification count."""
        self.failed_clarification_count += 1

    def should_handoff(self) -> bool:
        """Check if any threshold is crossed."""
        if self.handoff_triggered:
            return True  # Once triggered, stays triggered for this conversation
        if self.low_confidence_count >= 2:
            self._trigger("Two consecutive low-confidence plans for the same intent")
            return True
        if self.cancellation_count >= 2:
            self._trigger("Two consecutive user cancellations")
            return True
        if self.failed_clarification_count >= 1:
            self._trigger("Clarification round-trip did not resolve requirement")
            return True
        return False

    def _trigger(self, reason: str) -> None:
        self.handoff_triggered = True
        self.reason = reason
        logger.warning("Handoff triggered for %s: %s", self.conversation_id, reason)


# ── Global tracker (thread-safe, with auto-expiry) ─────────────────────────

_trackers: Dict[str, HandoffState] = {}
_trackers_lock = threading.Lock()
_TRACKER_TTL_SECONDS = 3600  # 1 hour


class HandoffTracker:
    """Thread-safe manager for per-conversation HandoffState."""

    @staticmethod
    def get(conversation_id: str) -> HandoffState:
        with _trackers_lock:
            if conversation_id not in _trackers:
                _trackers[conversation_id] = HandoffState(conversation_id)
            return _trackers[conversation_id]

    @staticmethod
    def record_low_confidence(conversation_id: str, intent_name: str) -> None:
        state = HandoffTracker.get(conversation_id)
        state.record_low_confidence(intent_name)

    @staticmethod
    def record_cancellation(conversation_id: str, intent_name: str) -> None:
        state = HandoffTracker.get(conversation_id)
        state.record_cancellation(intent_name)

    @staticmethod
    def record_failed_clarification(conversation_id: str) -> None:
        state = HandoffTracker.get(conversation_id)
        state.record_failed_clarification()

    @staticmethod
    def should_handoff(conversation_id: str, intent_name: str) -> bool:
        state = HandoffTracker.get(conversation_id)
        return state.should_handoff()

    @staticmethod
    def reset(conversation_id: str) -> None:
        with _trackers_lock:
            _trackers.pop(conversation_id, None)

    @staticmethod
    def cleanup_expired() -> int:
        """Remove expired trackers to prevent memory leaks."""
        now = time.time()
        expired = []
        with _trackers_lock:
            for cid, state in list(_trackers.items()):
                if now - state.created_at > _TRACKER_TTL_SECONDS:
                    expired.append(cid)
            for cid in expired:
                _trackers.pop(cid, None)
        return len(expired)


def should_handoff(state: HandoffState, current_intent: str) -> bool:
    """Check if handoff is needed for the current intent."""
    return state.should_handoff()
