"""Optional performance timing helpers (enable via ROUTE_PERF_LOG=1)."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from utils.logger import get_logger

_PERF_ENABLED = os.environ.get("ROUTE_PERF_LOG", "").strip().lower() in ("1", "true", "yes")
_logger = get_logger("route_perf")


def perf_enabled() -> bool:
    return _PERF_ENABLED


@contextmanager
def perf_timer(label: str, *, logger=None) -> Iterator[None]:
    """Log elapsed milliseconds when ROUTE_PERF_LOG is enabled."""
    if not _PERF_ENABLED:
        yield
        return
    log = logger or _logger
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        log.info(f"[perf] {label}: {elapsed_ms:.1f}ms")


def perf_log(label: str, elapsed_ms: float, detail: Optional[str] = None) -> None:
    if not _PERF_ENABLED:
        return
    msg = f"[perf] {label}: {elapsed_ms:.1f}ms"
    if detail:
        msg = f"{msg} ({detail})"
    _logger.info(msg)
