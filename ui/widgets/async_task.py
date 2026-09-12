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
        # User callbacks of the task that most recently ran.  They are
        # stored so ``cancel()`` can detach them from the worker's signals
        # and guarantee a cancelled task never invokes them.
        self._on_result_cb: Callable[[Any], None] | None = None
        self._on_error_cb: Callable[[str], None] | None = None
        # Every background thread that is still finishing, including ones
        # that were cancelled (``cancel()`` is non-blocking, so a thread may
        # outlive the task that started it).  ``_cleanup`` removes a thread
        # once it has fully stopped.
        self._active_threads: set[QThread] = set()
        # Strong self-reference taken while a task is running and released
        # once every worker thread has fully finished.  The worker QThreads
        # are children of this object; if the AsyncTask is garbage-collected
        # while a native thread is still finishing, PySide6 aborts the whole
        # process ("QThread: Destroyed while thread is still running").  The
        # self-reference guarantees the task — and therefore its QThread
        # children — stays alive until ``_cleanup`` runs.
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

        worker = _Worker(fn, args, kwargs)
        thread = QThread(self)
        worker.moveToThread(thread)

        self._on_result_cb = on_result
        self._on_error_cb = on_error
        self._worker = worker
        self._thread = thread

        thread.started.connect(worker.run)
        if on_result:
            worker.finished.connect(on_result)
        if on_error:
            worker.error.connect(on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        # Capture the thread in the default argument so a later run() or
        # cancel() cannot rebind this connection to a different thread.
        thread.finished.connect(lambda t=thread: self._cleanup(t))

        # Hold a self-reference until every thread finishes (see __init__).
        self._active_threads.add(thread)
        self._keep_alive = self
        thread.start()

    def cancel(self) -> None:
        """Cancel any running task without blocking the calling thread.

        Detaches the task's state immediately and only requests the worker
        thread to stop via ``quit()``.  ``wait()`` is never called, so the
        GUI thread is never blocked; ``_cleanup`` runs from the thread's
        ``finished`` signal once the thread actually stops.
        """
        worker = self._worker
        thread = self._thread
        # Detach immediately: from here on this task no longer owns the
        # (possibly still running) thread and worker.
        self._worker = None
        self._thread = None

        if worker is not None:
            # A cancelled task must never invoke its user callbacks, even if
            # the worker finishes afterwards — drop those connections.
            for signal, callback in (
                (worker.finished, self._on_result_cb),
                (worker.error, self._on_error_cb),
            ):
                if callback is not None:
                    try:
                        signal.disconnect(callback)
                    except (RuntimeError, TypeError):
                        # Signal already disconnected / slot never connected.
                        pass
            self._on_result_cb = None
            self._on_error_cb = None

        if thread is not None and thread.isRunning():
            thread.quit()

    def _cleanup(self, thread: QThread | None = None) -> None:
        """Release state once ``thread`` has fully finished.

        ``thread`` is the QThread that just stopped.  With the default
        ``None`` it also clears the current task state (used by tests and
        safe because no specific thread is being tracked).
        """
        self._active_threads.discard(thread)
        if self._thread is thread or thread is None:
            self._worker = None
            self._thread = None
        # Release the self-reference once every worker thread has finished,
        # so the QThread children can be destroyed safely even if the caller
        # has already dropped the AsyncTask.
        if not self._active_threads:
            self._keep_alive = None
