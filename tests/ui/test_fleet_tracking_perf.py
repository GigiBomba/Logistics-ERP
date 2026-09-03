"""A2 regression tests: fleet_tracking_view must schedule position polling on
the shared WorkerPool instead of spawning a new threading.Thread per poll.
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def view(qapp):
    """A bare QtFleetTrackingView instance (skips heavy __init__)."""
    from ui.views.fleet_tracking_view import QtFleetTrackingView

    v = QtFleetTrackingView.__new__(QtFleetTrackingView)
    v._lock = threading.Lock()
    v._fetching = False
    v._poll_timer = MagicMock()
    return v


def test_poll_uses_worker_pool(view):
    """_poll_and_update must dispatch via WorkerPool, not a raw Thread."""
    with patch("ui.views.fleet_tracking_view.WorkerPool.run") as run:
        view._poll_and_update()
        run.assert_called_once()
        # The pooled task must be the position fetch routine itself.
        assert run.call_args.kwargs["fn"] == view._fetch_positions


def test_poll_skipped_when_fetching(view):
    """A poll while a fetch is in flight must be skipped."""
    with view._lock:
        view._fetching = True
    with patch("ui.views.fleet_tracking_view.WorkerPool.run") as run:
        view._poll_and_update()
        run.assert_not_called()
