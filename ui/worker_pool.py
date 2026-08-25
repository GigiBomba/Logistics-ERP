"""QThreadPool-based async worker for offloading DB/IO work.

Provides a singleton ``WorkerPool`` that manages background execution
and delivers results back to the GUI thread via signals.

Usage::

    from ui.worker_pool import WorkerPool

    WorkerPool.run(
        fn=lambda: trip_service.get_filtered(search="test"),
        on_result=lambda data: self._update_table(data),
        on_error=lambda msg: self._show_error(msg),
    )

Replaces the per-task ``AsyncTask`` with a shared thread pool,
eliminating thread creation/destruction overhead.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

logger = logging.getLogger(__name__)


class _WorkerSignals(QObject):
    """Signals for a single background task."""
    result = Signal(object)   # Success result (any type)
    error = Signal(str)       # Error message


class _Runnable(QRunnable):
    """A single task to run on the thread pool."""

    def __init__(
        self,
        fn: Callable[[], Any],
        signals: _WorkerSignals,
    ):
        super().__init__()
        self._fn = fn
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            result = self._fn()
            self._signals.result.emit(result)
        except Exception as exc:
            logger.exception("WorkerPool task failed")
            tb = traceback.format_exc()
            self._signals.error.emit(f"{exc}\n{tb}")


class WorkerPool:
    """Shared thread pool for background work.

    Uses ``QThreadPool.globalInstance()`` which manages threads
    efficiently (creates up to ``QThreadPool.maxThreadCount()`` threads,
    reuses idle threads, and scales down automatically).

    This is a static-only class — instantiate for custom pools if needed.
    """

    _pool: QThreadPool | None = None

    # Strong references to in-flight ``_WorkerSignals`` senders.  The result
    # signal is emitted from a worker thread via a queued connection, so the
    # sender must stay alive until the main-thread event loop delivers the
    # callback.  Without this, PySide6 garbage-collects ``_WorkerSignals`` as
    # soon as the ``QRunnable`` finishes and the queued delivery is silently
    # dropped (async results never reach ``on_result``).  Each entry is
    # removed from the set once its callback has run.
    _pending_signals: set = set()

    @classmethod
    def _pool_instance(cls) -> QThreadPool:
        if cls._pool is None:
            cls._pool = QThreadPool.globalInstance()
            # Set a reasonable max thread count (leave 1 for UI)
            max_threads = max(2, cls._pool.maxThreadCount() - 1)
            cls._pool.setMaxThreadCount(max_threads)
            logger.info(
                "WorkerPool initialized: max_threads=%d",
                cls._pool.maxThreadCount(),
            )
        return cls._pool

    @classmethod
    def run(
        cls,
        fn: Callable[[], Any],
        on_result: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        priority: int = 0,
    ) -> None:
        """Schedule *fn* for background execution.

        Args:
            fn: Zero-argument callable to run off the UI thread.
                Capture arguments via ``lambda`` or ``functools.partial``.
            on_result: Called on the GUI thread with the return value.
            on_error: Called on the GUI thread with the error message.
            priority: Task priority (higher = more urgent). Default 0.
        """
        signals = _WorkerSignals()
        # Hold a strong reference until delivery completes (see class doc).
        WorkerPool._pending_signals.add(signals)

        def _release(*_args: Any) -> None:
            WorkerPool._pending_signals.discard(signals)

        if on_result:
            signals.result.connect(lambda data: (on_result(data), _release()))
        if on_error:
            signals.error.connect(lambda msg: (on_error(msg), _release()))

        runnable = _Runnable(fn, signals)
        cls._pool_instance().start(runnable, priority)

    @classmethod
    def run_async(
        cls,
        fn: Callable[[], Any],
        callback: Callable[[Any], None] | None = None,
        errback: Callable[[str], None] | None = None,
    ) -> None:
        """Alias for ``run()`` with clearer naming."""
        cls.run(fn=fn, on_result=callback, on_error=errback)

    @classmethod
    def map(
        cls,
        fn: Callable[[Any], Any],
        items: list[Any],
        on_each: Callable[[Any], None] | None = None,
        on_done: Callable[[], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> list[Any]:
        """Run *fn* for each *item* in parallel.

        Args:
            fn: Callable taking a single item, returning a result.
            items: List of items to process.
            on_each: Called on GUI thread with each result as it arrives.
            on_done: Called on GUI thread when all items are done.
            on_error: Called on GUI thread on any error.

        Returns:
            Empty list immediately (results arrive via callbacks).
        """
        results: list = []
        errors: list[str] = []
        remaining = len(items)

        if remaining == 0:
            if on_done:
                on_done()
            return results

        def _make_handler(item_idx: int):
            def _handler(result: Any) -> None:
                nonlocal remaining
                results.append(result)
                if on_each:
                    on_each(result)
                remaining -= 1
                if remaining <= 0 and on_done:
                    on_done()
            return _handler

        def _error_handler(msg: str) -> None:
            nonlocal remaining
            errors.append(msg)
            if on_error:
                on_error(msg)
            remaining -= 1
            if remaining <= 0 and on_done:
                on_done()

        for i, item in enumerate(items):
            sig = _WorkerSignals()
            # Hold a strong reference until delivery completes (same reason
            # as ``run``: queued cross-thread signal senders must stay alive).
            cls._pending_signals.add(sig)
            if on_each:
                sig.result.connect(
                    lambda data, i=i, sig=sig: (
                        _make_handler(i)(data),
                        cls._pending_signals.discard(sig),
                    )
                )
            if on_error:
                sig.error.connect(
                    lambda msg, sig=sig: (
                        _error_handler(msg),
                        cls._pending_signals.discard(sig),
                    )
                )
            runnable = _Runnable(lambda i=i, item=item: fn(item), sig)
            cls._pool_instance().start(runnable)

        return results

    @classmethod
    def stats(cls) -> dict[str, int]:
        """Return pool statistics."""
        pool = cls._pool_instance()
        return {
            "active_thread_count": pool.activeThreadCount(),
            "max_thread_count": pool.maxThreadCount(),
        }
