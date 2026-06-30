"""Base worker with graceful shutdown support.

Replaces ``daemon=True`` threads across the codebase with non-daemon
threads that respond to a stop event.  This ensures ``finally`` blocks
run and in-progress DB writes complete before the process exits.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


class GracefulWorker:
    """Add controlled shutdown to a background thread.

    Usage::

        class MyService(GracefulWorker):
            def refresh(self):
                self._spawn("my-worker", self._run)

            def _run(self):
                while not self.stop_requested:
                    ... do work ...
    """

    def __init__(self) -> None:
        self._stop_event = threading.Event()

    @property
    def stop_requested(self) -> bool:
        """Check whether shutdown has been requested."""
        return self._stop_event.is_set()

    def request_stop(self) -> None:
        """Signal the worker loop to exit at the next opportunity."""
        self._stop_event.set()

    def _spawn(
        self,
        name: str,
        target,
        daemon: bool = False,
    ) -> threading.Thread:
        """Start a thread with the given *name* and *target*.

        Unlike plain ``threading.Thread(daemon=True)`` this thread is
        non-daemon by default so cleanup code runs on shutdown.
        """
        t = threading.Thread(target=target, daemon=daemon, name=name)
        t.start()
        return t

    def _spawn_daemon(
        self,
        name: str,
        target,
    ) -> threading.Thread:
        """Start a daemon thread (opt-in for deliberately fire-and-forget tasks).

        Only use this for tasks whose failure or truncation on shutdown
        is truly harmless (e.g. logging a metric).
        """
        return self._spawn(name, target, daemon=True)
