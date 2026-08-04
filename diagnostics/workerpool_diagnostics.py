"""Worker Pool Diagnostics Probe — monitor QThreadPool task execution.

Monkey-patches ``ui.worker_pool.WorkerPool.run`` and
``ui.worker_pool.WorkerPool.map`` to record timing, track queue depth,
and detect task starvation and slow tasks.

Detection events
----------------
- ``workerpool.task_slow`` — a single task took >2 s to execute
- ``workerpool.starvation`` — queue depth >50 at sample time

Metrics
-------
- ``workerpool.tasks_submitted`` — counter
- ``workerpool.tasks_completed`` — counter
- ``workerpool.queue_depth`` — gauge (submitted - completed)
- ``workerpool.queue_time_ms`` — gauge (time from submit to execution start)
- ``workerpool.last_exec_ms`` — gauge (last task execution time)
- ``workerpool.active_threads`` — gauge (QThreadPool.activeThreadCount)
- Spans ``workerpool.task.{fn_name}`` for each task
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable

from PySide6.QtCore import QThreadPool

from diagnostics.models import DiagnosticCategory, Span, Event
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.workerpool")

# ── Thresholds ──────────────────────────────────────────────────────────
SLOW_TASK_THRESHOLD_MS = 2000.0
STARVATION_QUEUE_DEPTH = 50


class WorkerPoolProbe:
    """Monitors WorkerPool task execution timing and queue health.

    Usage::

        probe = WorkerPoolProbe(store)
        probe.install()     # patches WorkerPool.run and WorkerPool.map
        probe.sample()      # periodic check (called by engine)
    """

    sample_interval_s: float = 2.0

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._installed = False
        self._original_run: Any = None
        self._original_map: Any = None

    # ── Install / Uninstall ──────────────────────────────────────────

    def install(self) -> None:
        """Monkey-patch ``WorkerPool.run`` and ``WorkerPool.map``."""
        if self._installed:
            return

        from ui.worker_pool import WorkerPool

        store = self.store

        # ── Patch WorkerPool.run ─────────────────────────────────────
        self._original_run = WorkerPool.run.__func__  # unwrap classmethod

        @classmethod
        @functools.wraps(self._original_run)
        def _patched_run(
            cls,
            fn: Callable[[], Any],
            on_result: Callable[[Any], None] | None = None,
            on_error: Callable[[str], None] | None = None,
            priority: int = 0,
        ) -> None:
            submit_ts = time.perf_counter()
            fn_name = getattr(fn, "__name__", repr(fn)[:50])
            store.increment("workerpool.tasks_submitted")
            store.set_gauge(
                "workerpool.queue_depth",
                float(
                    store.get_counter("workerpool.tasks_submitted")
                    - store.get_counter("workerpool.tasks_completed")
                ),
            )

            def _wrapped_fn() -> Any:
                start_ts = time.perf_counter()
                queue_ms = (start_ts - submit_ts) * 1000.0
                store.set_gauge("workerpool.queue_time_ms", queue_ms)
                try:
                    return fn()
                finally:
                    exec_ms = (time.perf_counter() - start_ts) * 1000.0
                    store.record_span(Span(
                        name=f"workerpool.task.{fn_name}",
                        category=DiagnosticCategory.WORKER,
                        start_time=start_ts,
                        end_time=time.perf_counter(),
                        metadata={
                            "queue_ms": round(queue_ms, 2),
                            "exec_ms": round(exec_ms, 2),
                            "task": fn_name,
                        },
                    ))
                    store.increment("workerpool.tasks_completed")
                    store.set_gauge("workerpool.last_exec_ms", exec_ms)
                    if exec_ms > SLOW_TASK_THRESHOLD_MS:
                        store.record_event(Event(
                            name="workerpool.task_slow",
                            category=DiagnosticCategory.WORKER,
                            metadata={
                                "task": fn_name,
                                "exec_ms": round(exec_ms, 1),
                                "queue_ms": round(queue_ms, 1),
                            },
                        ))

            # Forward to original with wrapped function
            return self._original_run(
                cls, _wrapped_fn,
                on_result=on_result,
                on_error=on_error,
                priority=priority,
            )

        # ── Patch WorkerPool.map ─────────────────────────────────────
        self._original_map = WorkerPool.map.__func__  # unwrap classmethod

        @classmethod
        @functools.wraps(self._original_map)
        def _patched_map(
            cls,
            fn: Callable[[Any], Any],
            items: list[Any],
            on_each: Callable[[Any], None] | None = None,
            on_done: Callable[[], None] | None = None,
            on_error: Callable[[str], None] | None = None,
        ) -> list[Any]:
            # Wrap each per-item function with timing instrumentation
            def _make_wrapped_fn(item: Any) -> Callable[[], Any]:
                submit_ts = time.perf_counter()
                item_repr = repr(item)[:30]

                def _inner() -> Any:
                    start_ts = time.perf_counter()
                    queue_ms = (start_ts - submit_ts) * 1000.0
                    store.set_gauge("workerpool.queue_time_ms", queue_ms)
                    try:
                        result = fn(item)
                        return result
                    finally:
                        exec_ms = (time.perf_counter() - start_ts) * 1000.0
                        fn_name = getattr(fn, "__name__", repr(fn)[:40])
                        task_name = f"{fn_name}({item_repr})"
                        store.increment("workerpool.tasks_completed")
                        store.record_span(Span(
                            name=f"workerpool.task.{task_name}",
                            category=DiagnosticCategory.WORKER,
                            start_time=start_ts,
                            end_time=time.perf_counter(),
                            metadata={
                                "queue_ms": round(queue_ms, 2),
                                "exec_ms": round(exec_ms, 2),
                            },
                        ))
                        if exec_ms > SLOW_TASK_THRESHOLD_MS:
                            store.record_event(Event(
                                name="workerpool.task_slow",
                                category=DiagnosticCategory.WORKER,
                                metadata={
                                    "task": task_name,
                                    "exec_ms": round(exec_ms, 1),
                                },
                            ))

                return _inner

            # Submit each wrapped item via the original run method
            def _wrapped_on_each(result: Any) -> None:
                if on_each:
                    on_each(result)

            def _wrapped_on_done() -> None:
                if on_done:
                    on_done()

            def _wrapped_on_error(msg: str) -> None:
                if on_error:
                    on_error(msg)

            for item in items:
                store.increment("workerpool.tasks_submitted")
                store.set_gauge(
                    "workerpool.queue_depth",
                    float(
                        store.get_counter("workerpool.tasks_submitted")
                        - store.get_counter("workerpool.tasks_completed")
                    ),
                )
                wrapped = _make_wrapped_fn(item)
                self._original_run(
                    cls, wrapped,
                    on_result=_wrapped_on_each,
                    on_error=_wrapped_on_error,
                    priority=0,
                )

            # Return empty list immediately (results arrive via callbacks)
            return []

        # Apply patches
        WorkerPool.run = _patched_run
        WorkerPool.map = _patched_map
        self._installed = True
        logger.info("[DIAG] WorkerPoolProbe installed")

    def uninstall(self) -> None:
        """Restore original ``WorkerPool.run`` and ``WorkerPool.map``."""
        if self._installed:
            from ui.worker_pool import WorkerPool
            if self._original_run is not None:
                # Re-wrap as classmethod
                WorkerPool.run = classmethod(self._original_run)
            if self._original_map is not None:
                WorkerPool.map = classmethod(self._original_map)
            self._installed = False
            logger.info("[DIAG] WorkerPoolProbe uninstalled")

    # ── Sampling ─────────────────────────────────────────────────────

    def sample(self) -> None:
        """Periodic check for queue depth and active thread count.

        Called by ``DiagnosticsEngine._sampler_loop`` every ~2 s.
        """
        try:
            pool = QThreadPool.globalInstance()
            if pool is not None:
                active = pool.activeThreadCount()
                self.store.set_gauge(
                    "workerpool.active_threads", float(active)
                )

            # Update queue depth gauge
            submitted = self.store.get_counter("workerpool.tasks_submitted")
            completed = self.store.get_counter("workerpool.tasks_completed")
            queue_depth = submitted - completed
            self.store.set_gauge("workerpool.queue_depth", float(queue_depth))

            # Starvation detection
            if queue_depth > STARVATION_QUEUE_DEPTH:
                self.store.record_event(Event(
                    name="workerpool.starvation",
                    category=DiagnosticCategory.WORKER,
                    metadata={
                        "queue_depth": queue_depth,
                        "threshold": STARVATION_QUEUE_DEPTH,
                    },
                ))

        except Exception:
            logger.exception(
                "[DIAG] WorkerPoolProbe.sample failed — suppressed"
            )
