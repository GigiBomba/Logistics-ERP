"""Background task utility for running work off the UI thread.

Usage::

    from ui.widgets.async_task import AsyncTask

    task = AsyncTask()
    task.run(
        fn=lambda: trip_service.get_filtered(search="test"),
        on_result=lambda data: self._update_table(data),
        on_error=lambda msg: self._show_error(msg),
    )
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal

logger = logging.getLogger(__name__)


class _Worker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn: Callable, args: tuple, kwargs: dict):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            logger.exception("AsyncTask worker error")
            self.error.emit(str(e))


class AsyncTask(QObject):
    """Run a callable on a background QThread and get the result via signals.

    Usage::

        task = AsyncTask()
        task.run(db_query_function, on_result=self._handle_data)
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _Worker | None = None
        # Strong self-reference taken while a task is running and released
        # once the worker thread has fully finished.  The worker QThread is
        # a child of this object; if the AsyncTask is garbage-collected while
        # the native thread is still finishing, PySide6 aborts the whole
        # process ("QThread: Destroyed while thread is still running").  The
        # self-reference guarantees the task — and therefore its QThread
        # child — stays alive until ``_cleanup`` runs.
        self._keep_alive: "AsyncTask | None" = None

    def run(
        self,
        fn: Callable,
        on_result: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        *args,
        **kwargs,
    ) -> None:
        """Execute ``fn(*args, **kwargs)`` on a background thread.

        Args:
            fn: The callable to execute (must not touch Qt objects).
            on_result: Called on the GUI thread with the return value.
            on_error: Called on the GUI thread with the error message.
        """
        self.cancel()

        self._worker = _Worker(fn, args, kwargs)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        if on_result:
            self._worker.finished.connect(on_result)
        if on_error:
            self._worker.error.connect(on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)

        # Hold a self-reference until the thread finishes (see __init__).
        self._keep_alive = self
        self._thread.start()

    def cancel(self) -> None:
        """Cancel any running task (waits for thread to finish)."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        self._worker = None
        self._thread = None

    def _cleanup(self) -> None:
        self._worker = None
        self._thread = None
        # Release the self-reference: the worker thread has finished, so the
        # QThread child can now be destroyed safely even if the caller has
        # already dropped the AsyncTask.
        self._keep_alive = None
