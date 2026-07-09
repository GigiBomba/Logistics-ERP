"""Tests for the graceful worker with shutdown support."""
from __future__ import annotations

import threading
import time

import pytest

from services.base_worker import GracefulWorker


class TestGracefulWorker:
    """Test suite for GracefulWorker."""

    def test_stop_not_requested_initially(self):
        w = GracefulWorker()
        assert not w.stop_requested

    def test_request_stop_sets_flag(self):
        w = GracefulWorker()
        w.request_stop()
        assert w.stop_requested

    def test_request_stop_is_idempotent(self):
        w = GracefulWorker()
        w.request_stop()
        w.request_stop()
        assert w.stop_requested

    def test_spawn_creates_thread_and_starts(self):
        w = GracefulWorker()
        started = []

        def target():
            started.append(True)

        t = w._spawn("test-thread", target)
        t.join(timeout=5)
        assert not t.is_alive()
        assert len(started) == 1

    def test_spawn_non_daemon_by_default(self):
        w = GracefulWorker()

        def target():
            pass

        t = w._spawn("test-nondaemon", target)
        t.join(timeout=5)
        assert not t.daemon

    def test_spawn_daemon_creates_daemon_thread(self):
        w = GracefulWorker()

        def target():
            pass

        t = w._spawn_daemon("test-daemon", target)
        t.join(timeout=5)
        assert t.daemon

    @pytest.mark.slow
    def test_worker_loop_exits_on_stop_requested(self):
        w = GracefulWorker()
        loop_ran = []

        def target():
            while not w.stop_requested:
                loop_ran.append("tick")
                time.sleep(0.01)

        t = w._spawn("loop", target)
        time.sleep(0.05)  # let the loop run a few iterations
        w.request_stop()
        t.join(timeout=5)
        assert not t.is_alive()
        assert len(loop_ran) > 0

    def test_spawn_returns_thread_object(self):
        w = GracefulWorker()

        def target():
            pass

        t = w._spawn("test-return", target)
        t.join(timeout=5)
        assert isinstance(t, threading.Thread)

    def test_spawn_with_args_via_lambda(self):
        w = GracefulWorker()
        results = []

        def target(a, b):
            results.append((a, b))

        t = w._spawn("test-args", lambda: target(1, 2))
        t.join(timeout=5)
        assert results == [(1, 2)]
