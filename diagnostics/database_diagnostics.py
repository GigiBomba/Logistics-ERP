"""Database Diagnostics Probe — monitor SQL query execution.

Monkey-patches ``database.db_manager.DatabaseManager.execute`` to record
timing, normalise SQL, and detect slow queries, N+1 query patterns, and
overall query rates.

Detection events
----------------
- ``db.slow_query`` — a query took >100 ms
- ``db.n_plus_1`` — same normalised SQL appears >5 times in a 500 ms window

Metrics
-------
- ``db.queries_total`` — counter
- ``db.queries.{normalized_sql}`` — per-query counter
- ``db.queries_per_sec`` — gauge (queries since last sample / interval)
- ``db.slow_query_count`` — gauge (number of slow queries since last sample)
- Spans ``db.query.{normalized_sql}`` for every query
"""

from __future__ import annotations

import functools
import logging
import re
import time
from collections import deque
from typing import Any

from diagnostics.models import DiagnosticCategory, Span, Event
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.database")

# ── Thresholds ──────────────────────────────────────────────────────────
SLOW_QUERY_THRESHOLD_MS = 100.0
N_PLUS_1_WINDOW_S = 0.5         # lookback window for N+1 detection
N_PLUS_1_COUNT = 5              # same SQL in window → N+1 event
N_PLUS_1_DEBOUNCE_S = 10.0     # don't fire same N+1 event more than once per 10 s
QUERY_WINDOW_MAXLEN = 500       # max entries in rolling query window


class DatabaseProbe:
    """Monitors DatabaseManager.execute timing and patterns.

    Usage::

        probe = DatabaseProbe(store)
        probe.install()     # patches DatabaseManager.execute
        probe.sample()      # periodic check (called by engine)
    """

    sample_interval_s: float = 2.0

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._installed = False
        self._original_execute: Any = None

        # Rolling query window for N+1 detection (thread-safe via store lock)
        self._query_window: deque[tuple[float, str]] = deque(
            maxlen=QUERY_WINDOW_MAXLEN
        )
        self._n_plus_1_debounce: dict[str, float] = {}

        # Sample tracking
        self._last_sample_queries: int = 0
        self._last_sample_time: float = time.perf_counter()
        self._slow_query_count: int = 0

    # ── Static helpers ───────────────────────────────────────────────

    @staticmethod
    def _normalize_sql(query: Any) -> str:
        """Normalise a SQL query for metric naming and grouping.

        Strips string literals, collapses whitespace, and truncates
        to 80 characters.
        """
        try:
            normalized = re.sub(r"'[^']*'", "'?'", str(query))
            normalized = re.sub(r"\s+", " ", normalized).strip()
            return normalized[:80]
        except Exception:
            return str(query)[:80]

    # ── Install / Uninstall ──────────────────────────────────────────

    def install(self) -> None:
        """Monkey-patch ``DatabaseManager.execute``."""
        if self._installed:
            return

        from database.db_manager import DatabaseManager

        self._original_execute = DatabaseManager.execute
        probe = self
        store = self.store

        @functools.wraps(self._original_execute)
        def _patched_execute(
            self: Any, query: str, params: tuple = ()
        ) -> Any:
            """Patched execute — wraps original with diagnostics."""
            start = time.perf_counter()
            try:
                result = self._original_execute(self, query, params)
                return result
            finally:
                elapsed = (time.perf_counter() - start) * 1000.0
                normalized = DatabaseProbe._normalize_sql(query)

                # Counters
                store.increment("db.queries_total")
                store.increment(f"db.queries.{normalized}")

                # Span
                store.record_span(Span(
                    name=f"db.query.{normalized[:60]}",
                    category=DiagnosticCategory.DATABASE,
                    start_time=start,
                    end_time=time.perf_counter(),
                    metadata={
                        "elapsed_ms": round(elapsed, 2),
                        "normalized_sql": normalized[:80],
                    },
                ))

                # Slow query detection
                if elapsed > SLOW_QUERY_THRESHOLD_MS:
                    probe._slow_query_count += 1
                    store.record_event(Event(
                        name="db.slow_query",
                        category=DiagnosticCategory.DATABASE,
                        metadata={
                            "elapsed_ms": round(elapsed, 1),
                            "sql": normalized[:120],
                        },
                    ))

                # N+1 detection
                now = time.perf_counter()
                probe._query_window.append((now, normalized))
                probe._detect_n_plus_1(normalized, now)

        DatabaseManager.execute = _patched_execute
        self._installed = True
        logger.info("[DIAG] DatabaseProbe installed")

    def uninstall(self) -> None:
        """Restore original ``DatabaseManager.execute``."""
        if self._installed and self._original_execute is not None:
            from database.db_manager import DatabaseManager
            DatabaseManager.execute = self._original_execute
            self._installed = False
            self._query_window.clear()
            self._n_plus_1_debounce.clear()
            logger.info("[DIAG] DatabaseProbe uninstalled")

    # ── N+1 Detection ────────────────────────────────────────────────

    def _detect_n_plus_1(self, normalized_sql: str, now: float) -> None:
        """Check if the same normalised SQL appears suspiciously often.

        Fires ``db.n_plus_1`` event (debounced per SQL to 10 s).
        """
        try:
            # Count how many times the same SQL appears in the window
            cutoff = now - N_PLUS_1_WINDOW_S
            count = sum(
                1
                for ts, sql in self._query_window
                if sql == normalized_sql and ts >= cutoff
            )

            if count > N_PLUS_1_COUNT:
                # Debounce: only fire once per SQL per debounce window
                last_fire = self._n_plus_1_debounce.get(normalized_sql, 0.0)
                if now - last_fire >= N_PLUS_1_DEBOUNCE_S:
                    self._n_plus_1_debounce[normalized_sql] = now
                    self.store.record_event(Event(
                        name="db.n_plus_1",
                        category=DiagnosticCategory.DATABASE,
                        metadata={
                            "sql": normalized_sql[:120],
                            "count": count,
                            "window_s": N_PLUS_1_WINDOW_S,
                            "threshold": N_PLUS_1_COUNT,
                        },
                    ))

        except Exception:
            logger.exception(
                "[DIAG] DatabaseProbe N+1 detection failed — suppressed"
            )

    # ── Sampling ─────────────────────────────────────────────────────

    def sample(self) -> None:
        """Periodic query-rate reporting and gauge updates.

        Called by ``DiagnosticsEngine._sampler_loop`` every ~2 s.
        """
        try:
            now = time.perf_counter()
            total_queries = self.store.get_counter("db.queries_total")
            elapsed_s = now - self._last_sample_time

            if elapsed_s > 0:
                queries_this_interval = (
                    total_queries - self._last_sample_queries
                )
                rate = queries_this_interval / elapsed_s
                self.store.set_gauge("db.queries_per_sec", rate)

            self.store.set_gauge(
                "db.slow_query_count", float(self._slow_query_count)
            )

            # Reset per-sample counters
            self._last_sample_queries = total_queries
            self._last_sample_time = now
            self._slow_query_count = 0

        except Exception:
            logger.exception(
                "[DIAG] DatabaseProbe.sample failed — suppressed"
            )
