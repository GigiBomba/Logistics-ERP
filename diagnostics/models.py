"""Shared data models for the Runtime Diagnostics Framework.

Every measurement in the framework uses one of these canonical types.
All timestamps are ``time.perf_counter()`` floats for high-resolution
comparison.  Human-readable timestamps are added at export time.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ── Categories ────────────────────────────────────────────────────────


class DiagnosticCategory(str, Enum):
    """Every span/event belongs to exactly one category."""
    STARTUP = "startup"
    VIEW = "view"
    WIDGET = "widget"
    EVENT_LOOP = "event_loop"
    TIMER = "timer"
    SIGNAL = "signal"
    WORKER = "worker"
    DATABASE = "database"
    PAINT = "paint"
    MEMORY = "memory"
    EVENT_BUS = "event_bus"
    NAVIGATION = "navigation"
    FULLSCREEN = "fullscreen"
    FREEZE = "freeze"
    CUSTOM = "custom"


# ── Span: an operation with start + end time ────────────────────────


@dataclass
class Span:
    """A timed operation with a known start and end.

    ``start_time`` and ``end_time`` are ``time.perf_counter()`` values.
    Use ``elapsed_ms`` for the duration.
    """
    name: str
    category: DiagnosticCategory
    start_time: float = field(default_factory=time.perf_counter)
    end_time: float = 0.0
    thread_id: int = field(default_factory=lambda: threading.get_ident())
    thread_name: str = field(default_factory=lambda: threading.current_thread().name)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self) -> None:
        """Mark the span as finished (records end_time)."""
        self.end_time = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        if self.end_time > 0:
            return (self.end_time - self.start_time) * 1000.0
        return (time.perf_counter() - self.start_time) * 1000.0

    @property
    def elapsed_s(self) -> float:
        return self.elapsed_ms / 1000.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "category": self.category.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "thread_id": self.thread_id,
            "thread_name": self.thread_name,
            "metadata": self.metadata,
        }


# ── Event: a point-in-time occurrence ───────────────────────────────


@dataclass
class Event:
    """A point-in-time event with no duration."""
    name: str
    category: DiagnosticCategory
    timestamp: float = field(default_factory=time.perf_counter)
    thread_id: int = field(default_factory=lambda: threading.get_ident())
    thread_name: str = field(default_factory=lambda: threading.current_thread().name)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "category": self.category.value,
            "timestamp": self.timestamp,
            "thread_id": self.thread_id,
            "thread_name": self.thread_name,
            "metadata": self.metadata,
        }


# ── Gauge: a named numeric value sampled at a point in time ─────────


@dataclass
class Gauge:
    """A point-in-time numeric metric."""
    name: str
    value: float
    category: DiagnosticCategory = DiagnosticCategory.CUSTOM
    timestamp: float = field(default_factory=time.perf_counter)
    labels: dict[str, str] = field(default_factory=dict)


# ── Counter: a monotonically increasing count ───────────────────────


@dataclass
class Counter:
    """A monotonically increasing counter."""
    name: str
    value: int = 0
    category: DiagnosticCategory = DiagnosticCategory.CUSTOM


# ── FreezeReport: details of a detected UI freeze ───────────────────


@dataclass
class FreezeReport:
    """Captured when the UI thread blocks for longer than threshold."""
    duration_ms: float
    timestamp: float = field(default_factory=time.perf_counter)
    thread_id: int = field(default_factory=lambda: threading.get_ident())
    stack_trace: str = ""
    active_timers: list[dict[str, Any]] = field(default_factory=list)
    worker_queue: list[dict[str, Any]] = field(default_factory=list)
    event_queue_size: int = 0
    active_signals: list[str] = field(default_factory=list)
    memory_mb: float = 0.0
    current_operation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_ms": round(self.duration_ms, 1),
            "timestamp": self.timestamp,
            "thread_id": self.thread_id,
            "stack_trace": self.stack_trace,
            "active_timers": self.active_timers[:20],
            "worker_queue": self.worker_queue[:20],
            "event_queue_size": self.event_queue_size,
            "memory_mb": round(self.memory_mb, 1),
            "current_operation": self.current_operation,
        }
