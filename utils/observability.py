"""Structured logging and observability utilities for Operion ERP.

Provides JSON-format structured logging, key metrics instrumentation,
and a performance timer context manager.

Usage:
    from utils.observability import log, metrics, perf_timer

    log.info("route_calculated", distance_km=1786, duration_s=67)
    metrics.increment("routes_calculated")
    metrics.gauge("active_trips", 42)

    with perf_timer("cmr_generation"):
        generate_cmr(trip_id)
"""

from __future__ import annotations

import functools
import json
import logging
import os
import time
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

# The correlation id comes from the FastAPI middleware.  The packaged desktop
# build ships NO backend package (see scripts/build_client.py EXCLUDE_MODULES),
# so the import must be guarded — an unguarded one kills every packaged boot.
try:
    from backend.middleware.correlation_middleware import get_correlation_id
except ImportError:  # packaged client: no backend package
    def get_correlation_id() -> str:
        """No FastAPI request context in the desktop client — no correlation id."""
        return ""


class _StructuredLogger:
    """Wraps a standard logger to emit JSON lines with structured fields."""

    def __init__(self, name: str = "operion"):
        self._logger = logging.getLogger(name)

    _LEVEL_MAP = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    def _emit(self, level: str, message: str, **fields) -> None:
        record = {
            "level": level,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "correlation_id": get_correlation_id(),
            **fields,
        }
        level_num = self._LEVEL_MAP.get(level, logging.INFO)
        # Guard against the logger that will actually receive the record.
        # Resolve it by name so the check stays correct even if
        # ``self._logger`` holds a stale/patched reference (e.g. the level
        # was configured on ``logging.getLogger(name)`` directly).
        target = logging.getLogger(self._logger.name)
        if target.isEnabledFor(level_num):
            self._logger.log(level_num, json.dumps(record, ensure_ascii=False, default=str))

    def info(self, message: str, **fields) -> None:
        self._emit("INFO", message, **fields)

    def warning(self, message: str, **fields) -> None:
        self._emit("WARNING", message, **fields)

    def error(self, message: str, **fields) -> None:
        self._emit("ERROR", message, **fields)

    def debug(self, message: str, **fields) -> None:
        self._emit("DEBUG", message, **fields)


class _Metrics:
    """Thread-safe in-memory metrics registry.

    Provides counters (monotonically increasing) and gauges (point-in-time).
    Metrics can be dumped as JSON for health checks or logging.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._start_time = time.time()

    def increment(self, name: str, delta: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + delta
        # Also push to Prometheus if available
        try:
            from backend.metrics import trips_created_total, invoices_generated_total, routes_calculated_total
            metric_map = {
                "trips_created": trips_created_total,
                "invoices_generated": invoices_generated_total,
                "routes_calculated": routes_calculated_total,
            }
            if name in metric_map:
                metric_map[name].inc(delta)
        except ImportError:
            pass

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def get_counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        with self._lock:
            return self._gauges.get(name, 0.0)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "uptime_seconds": time.time() - self._start_time,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._start_time = time.time()


@contextmanager
def perf_timer(name: str, log_result: bool = True, logger: Optional[_StructuredLogger] = None):
    """Context manager that times execution and logs + records latency metric.

    Usage:
        with perf_timer("route_calculation"):
            result = calculate_route(...)

    Only counts successful completions (no exception propagated out).

    ``logger`` may be supplied to override the module-level ``log`` singleton
    (useful for injecting/patching the instance that receives the timing log).
    """
    start = time.perf_counter()
    success = True
    try:
        yield
    except BaseException:
        success = False
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if success:
            metrics.increment(f"perf.{name}.count")
            metrics.gauge(f"perf.{name}.last_ms", elapsed_ms)
            if log_result:
                (logger or log).debug(f"perf_timer", operation=name, elapsed_ms=round(elapsed_ms, 2))


def timed(func: Callable) -> Callable:
    """Decorator that logs execution time for any function."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with perf_timer(func.__qualname__):
            return func(*args, **kwargs)
    return wrapper


# ── Module-level singletons ──────────────────────────────────────────
log = _StructuredLogger("operion")
metrics = _Metrics()
