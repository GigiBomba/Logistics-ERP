"""Tests for ``AsyncTask`` and ``_Worker`` pure logic (no QApplication required).

All Qt dependencies (``QThread``, ``QTimer``, ``QObject``, ``Signal``) are
mocked via ``unittest.mock.MagicMock`` so that these tests can run without a
display server or a running QApplication.
"""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import MagicMock, patch

import pytest

from ui.widgets.async_task import AsyncTask, _Worker


# ── _Worker ─────────────────────────────────────────────────────────────────


class TestWorker:
    """Tests for the internal ``_Worker`` class."""

    def test_calls_fn_and_emits_finished(self) -> None:
        """When ``run()`` is called, the worker should invoke the stored
        function and emit ``finished`` with the result."""
        worker = _Worker(fn=lambda x: x * 2, args=(21,), kwargs={})
        worker.finished = MagicMock()
        worker.error = MagicMock()

        worker.run()

        worker.finished.emit.assert_called_once_with(42)
        worker.error.emit.assert_not_called()

    def test_emits_error_on_exception(self) -> None:
        """When the function raises an exception, the worker should emit
        ``error`` with the string representation."""
        def _explode() -> None:
            raise ValueError("boom")

        worker = _Worker(fn=_explode, args=(), kwargs={})
        worker.finished = MagicMock()
        worker.error = MagicMock()

        worker.run()

        worker.finished.emit.assert_not_called()
        worker.error.emit.assert_called_once()
        error_msg = worker.error.emit.call_args[0][0]
        assert "boom" in error_msg

    def test_passes_args_and_kwargs(self) -> None:
        """``args`` and ``kwargs`` should be forwarded to the target
        function."""
        mock_fn = MagicMock(return_value="done")
        worker = _Worker(fn=mock_fn, args=(1, 2), kwargs={"key": "val"})
        worker.finished = MagicMock()
        worker.error = MagicMock()

        worker.run()

        mock_fn.assert_called_once_with(1, 2, key="val")
        worker.finished.emit.assert_called_once_with("done")


# ── AsyncTask ───────────────────────────────────────────────────────────────


class TestAsyncTask:
    """Tests for the public ``AsyncTask`` class."""

    @pytest.fixture
    def task(self) -> AsyncTask:
        """Provide a plain ``AsyncTask`` instance with no real Qt parent."""
        return AsyncTask()

    def test_creates_thread_and_worker(self, task: AsyncTask) -> None:
        """``run()`` should instantiate a new ``_Worker`` and ``QThread``."""
        mock_worker_cls = MagicMock()
        mock_thread_cls = MagicMock()
        mock_thread = mock_thread_cls.return_value

        with patch("ui.widgets.async_task._Worker", mock_worker_cls):
            with patch("ui.widgets.async_task.QThread", mock_thread_cls):
                fn = MagicMock()
                task.run(fn=fn, on_result=MagicMock())

        mock_worker_cls.assert_called_once_with(fn, (), {})
        mock_thread_cls.assert_called_once_with(task)
        assert task._worker is not None
        assert task._thread is not None

    def test_cancels_previous_task(self, task: AsyncTask) -> None:
        """Calling ``run()`` a second time should cancel any running
        task first."""
        task.cancel = MagicMock()
        with patch("ui.widgets.async_task._Worker", MagicMock()):
            with patch("ui.widgets.async_task.QThread", MagicMock()):
                task.run(fn=MagicMock(), on_result=MagicMock())

        task.cancel.assert_called_once()

    def test_connects_signals(self, task: AsyncTask) -> None:
        """The thread's ``started`` signal should connect to
        ``_worker.run``, and ``finished`` should connect to
        ``_thread.quit``."""
        mock_worker = MagicMock()
        mock_worker_cls = MagicMock(return_value=mock_worker)
        mock_thread = MagicMock()
        mock_thread_cls = MagicMock(return_value=mock_thread)

        with patch("ui.widgets.async_task._Worker", mock_worker_cls):
            with patch("ui.widgets.async_task.QThread", mock_thread_cls):
                task.run(fn=MagicMock(), on_result=MagicMock())

        mock_thread.started.connect.assert_any_call(mock_worker.run)
        mock_worker.finished.connect.assert_any_call(mock_thread.quit)
        mock_worker.error.connect.assert_any_call(mock_thread.quit)

    def test_connects_on_result_signal(self, task: AsyncTask) -> None:
        """The provided ``on_result`` callback should be wired to the
        worker's ``finished`` signal."""
        on_result = MagicMock()
        mock_worker = MagicMock()
        mock_worker_cls = MagicMock(return_value=mock_worker)

        with patch("ui.widgets.async_task._Worker", mock_worker_cls):
            with patch("ui.widgets.async_task.QThread", MagicMock()):
                task.run(fn=MagicMock(), on_result=on_result)

        mock_worker.finished.connect.assert_any_call(on_result)

    def test_connects_on_error_signal(self, task: AsyncTask) -> None:
        """The provided ``on_error`` callback should be wired to the
        worker's ``error`` signal."""
        on_error = MagicMock()
        mock_worker = MagicMock()
        mock_worker_cls = MagicMock(return_value=mock_worker)

        with patch("ui.widgets.async_task._Worker", mock_worker_cls):
            with patch("ui.widgets.async_task.QThread", MagicMock()):
                task.run(fn=MagicMock(), on_error=on_error)

        mock_worker.error.connect.assert_any_call(on_error)

    def test_cleanup_on_thread_finished(self, task: AsyncTask) -> None:
        """When the thread emits ``finished``, ``_cleanup`` should be
        called and both ``_worker`` and ``_thread`` set to ``None``."""
        mock_thread = MagicMock()
        mock_thread_cls = MagicMock(return_value=mock_thread)

        with patch("ui.widgets.async_task._Worker", MagicMock()):
            with patch("ui.widgets.async_task.QThread", mock_thread_cls):
                task.run(fn=MagicMock())

        # Simulate the thread finishing.
        assert task._worker is not None
        assert task._thread is not None
        task._cleanup()
        assert task._worker is None
        assert task._thread is None

    def test_cancel_stops_running_thread(self, task: AsyncTask) -> None:
        """``cancel()`` should quit and wait on a running thread."""
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = True
        task._thread = mock_thread
        task._worker = MagicMock()

        task.cancel()

        mock_thread.quit.assert_called_once()
        mock_thread.wait.assert_called_once_with(2000)
        assert task._worker is None
        assert task._thread is None

    def test_cancel_noop_when_idle(self, task: AsyncTask) -> None:
        """``cancel()`` should be a no-op when no thread is running."""
        task._thread = None
        task._worker = None
        # Should not raise.
        task.cancel()
        assert task._thread is None
        assert task._worker is None

    def test_cancel_skips_wait_when_not_running(self, task: AsyncTask) -> None:
        """``cancel()`` should not call ``wait`` when the thread exists
        but is not running."""
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = False
        task._thread = mock_thread
        task._worker = MagicMock()

        task.cancel()

        mock_thread.quit.assert_not_called()
        mock_thread.wait.assert_not_called()
        assert task._worker is None
        assert task._thread is None
