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

def _record_phase_metric(phase_name: str, elapsed_ms: float) -> None:
    """Record a phase's latency into the shared metrics registry.

    Keyed ``copilot.phase.<PHASE>.count`` / ``copilot.phase.<PHASE>.last_ms``
    so the dev-toolkit observability panel can render per-phase timings.
    Guarded: telemetry must never break the pipeline if metrics is missing.
    """
    try:
        from utils.observability import metrics
        metrics.increment(f"copilot.phase.{phase_name}.count")
        metrics.gauge(f"copilot.phase.{phase_name}.last_ms", round(elapsed_ms, 2))
    except Exception:
        logger.debug("Copilot phase metric not recorded (metrics unavailable)", exc_info=True)
        pass


class PhaseTimer:
    """Context manager for timing a pipeline phase.

    Records the elapsed time both on the instance (``timer.elapsed_ms``) and
    into the shared metrics registry (``copilot.phase.<PHASE>.count`` and
    ``copilot.phase.<PHASE>.last_ms``) so the observability panel can render
    per-phase latency without parsing logs.

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
        _record_phase_metric(self.phase_name, self.elapsed_ms)
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


# ── Logging integration ─────────────────────────────────────────────────────
# Attach the correlation context to every record emitted through the copilot
# loggers, so §23.6 ("every copilot log line carries conversation_id") holds
# without a per-call-site sweep. The filter mutates the record in place; the
# structured formatter renders the extra attributes.
#
# WHY THIS IS NOT JUST A FILTER ON THE PARENT LOGGER:
# Logger-level filters are applied only to records logged *directly* on that
# logger — they are NOT inherited by child loggers via propagation. CPython's
# ``Logger.callHandlers`` walks the ancestor chain to run ancestor *handlers*,
# but never applies ancestor ``Logger.filters``; and a filter on the root
# logger does not apply to descendant records either. Empirically verified:
# a record from ``backend.copilot.tools.fake_tool`` carried no correlation
# fields when only ``backend.copilot`` was filtered (with propagate True *or*
# False). Every copilot module calls ``logging.getLogger(__name__)``, so each
# sub-logger needs its own filter.
#
# TWO-PART COVERAGE:
#   1. Existing loggers — attach the filter to the parents and to every
#      already-registered descendant under the ``backend.copilot`` namespace.
#   2. Future loggers — ``backend/copilot/__init__.py`` installs this at
#      import time, *before* submodules (executor, tools.*, …) are imported,
#      so their loggers do not exist yet. We therefore install a name-guarded
#      :class:`_CopilotCorrelationLogger` via ``logging.setLoggerClass`` so any
#      copilot-namespace logger created later is stamped automatically. The
#      guard keeps the behaviour bounded to ``backend.copilot``; non-copilot
#      loggers are unaffected (no filter attached).

# Parent loggers that anchor the copilot namespace.
_COPILOT_LOGGER_NAMES = (
    "backend.copilot",
    "backend.api.v1.copilot_router",
)
# Namespace prefix whose descendants also need the filter.
_COPILOT_CHILD_PREFIX = "backend.copilot"


class CorrelationLogFilter(logging.Filter):
    """Stamp every log record with the current correlation context."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.conversation_id = current_conversation_id.get()
        record.company_id = current_company_id.get()
        record.user_id = current_user_id.get()
        record.phase = current_phase.get()
        return True


def _attach_filter(target: logging.Logger) -> None:
    """Attach a :class:`CorrelationLogFilter` to ``target`` unless present."""
    if not any(isinstance(f, CorrelationLogFilter) for f in target.filters):
        target.addFilter(CorrelationLogFilter())


def _is_copilot_logger(name: str) -> bool:
    """True for the copilot parent loggers and their descendants."""
    return name in _COPILOT_LOGGER_NAMES or name.startswith(_COPILOT_CHILD_PREFIX + ".")


# Subclass whatever logger class is current so we compose with any existing
# customisation rather than clobbering it.
_BaseLoggerClass = logging.getLoggerClass()


class _CopilotCorrelationLogger(_BaseLoggerClass):
    """Logger that self-installs the correlation filter for copilot names.

    Used as the global logger class so loggers created after
    :func:`install_copilot_logging` (new modules imported later) are covered
    without touching non-copilot loggers.
    """

    def __init__(self, name: str, level: int = logging.NOTSET) -> None:
        super().__init__(name, level)
        if _is_copilot_logger(name):
            _attach_filter(self)


def install_copilot_logging() -> None:
    """Attach :class:`CorrelationLogFilter` to the copilot loggers (idempotent).

    Covers the parent loggers in :data:`_COPILOT_LOGGER_NAMES`, every
    already-created descendant under the ``backend.copilot`` namespace, and
    (via :class:`_CopilotCorrelationLogger`) copilot loggers created later.
    """
    # Future loggers: make the copilot namespace self-filtering. Idempotent —
    # skip once our class is already installed.
    if logging.getLoggerClass() is not _CopilotCorrelationLogger:
        logging.setLoggerClass(_CopilotCorrelationLogger)

    for name in _COPILOT_LOGGER_NAMES:
        _attach_filter(logging.getLogger(name))

    # Existing loggers: ``loggerDict`` holds all known loggers; entries may be
    # PlaceHolder objects for parents referenced only by name, so guard with
    # isinstance. Bounded to the copilot namespace.
    for name, candidate in list(logging.Logger.manager.loggerDict.items()):
        if not name.startswith(_COPILOT_CHILD_PREFIX + "."):
            continue
        if isinstance(candidate, logging.Logger):
            _attach_filter(candidate)
