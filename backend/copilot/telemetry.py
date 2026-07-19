"""Correlation ID propagation and per-phase latency tracking (§23.6).

Ties every log line, LLM provider call, tool execution, and WebSocket
message in a single conversation together via a shared conversation_id,
and emits per-phase timing metrics so pipeline bottlenecks can be
identified without timestamp-guessing.

Blueprint: §23.6 — Observability, §29 — Application Logging.
"""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger(__name__)

# ── Correlation ID context ──────────────────────────────────────────────────
# These ContextVars propagate across async boundaries automatically.
# Set once per request at the API entry point; read by every pipeline phase.

current_conversation_id: ContextVar[str] = ContextVar("conversation_id", default="")
current_company_id: ContextVar[int] = ContextVar("company_id", default=0)
current_user_id: ContextVar[int] = ContextVar("user_id", default=0)
current_phase: ContextVar[str] = ContextVar("phase", default="")


def set_correlation_context(
    conversation_id: str,
    company_id: int = 0,
    user_id: int = 0,
) -> None:
    """Set the correlation context for the current request."""
    current_conversation_id.set(conversation_id)
    current_company_id.set(company_id)
    current_user_id.set(user_id)


def set_phase(phase: str) -> None:
    """Set the current pipeline phase (Understand/Reasoning/Execute/Summarize)."""
    current_phase.set(phase)


# ── Per-phase latency tracking ──────────────────────────────────────────────

class PhaseTimer:
    """Context manager for timing a pipeline phase.
    
    Usage:
        with PhaseTimer("REASONING", conversation_id="conv-123") as timer:
            # do work
        # timer.elapsed_ms is now available
    """

    def __init__(
        self,
        phase_name: str,
        conversation_id: Optional[str] = None,
    ) -> None:
        self.phase_name = phase_name
        self.conversation_id = conversation_id or current_conversation_id.get()
        self.start: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> PhaseTimer:
        self.start = time.monotonic()
        self._previous_phase = current_phase.get()  # Save previous
        set_phase(self.phase_name)
        logger.debug("PHASE_START | phase=%s conv=%s", self.phase_name, self.conversation_id)
        return self

    def __exit__(self, *args) -> None:
        self.elapsed_ms = (time.monotonic() - self.start) * 1000
        current_phase.set(self._previous_phase)  # Restore previous
        logger.info(
            "PHASE_END | phase=%s conv=%s elapsed_ms=%.1f",
            self.phase_name, self.conversation_id, self.elapsed_ms,
        )


def get_structured_log_extras() -> dict:
    """Return the standard structured logging extras for the current context.
    
    Every log line from app/copilot/ should include these.
    """
    return {
        "conversation_id": current_conversation_id.get(),
        "company_id": current_company_id.get(),
        "user_id": current_user_id.get(),
        "phase": current_phase.get(),
    }
