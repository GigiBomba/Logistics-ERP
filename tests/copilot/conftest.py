"""Co-Pilot test configuration.

Provides cross-cutting fixtures for the copilot test suite.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="function")
def _clear_kill_switch_memo():
    """Clear the in-process kill-switch memo before and after each test.

    ``_check_kill_switch`` memoizes pass-through results for ~2s; tests that
    exercise kill-switch behaviour need a clean memo or a memo entry written
    by a prior test would short-circuit their Redis reads.
    """
    from backend.api.v1.copilot_router import _kill_switch_memo
    _kill_switch_memo.clear()
    yield
    _kill_switch_memo.clear()


@pytest.fixture(autouse=True, scope="function")
def _qt_event_loop_cleanup():
    """Drain pending Qt events after each test to prevent stale timer
    callbacks from ``guided_overlay_widget`` polluting subsequent tests.

    ``QTimer.singleShot`` callbacks that reference deleted C++ objects
    produce RuntimeErrors that pytest-qt captures and surfaces as setup
    errors in the next test.  Processing the event loop between tests
    allows those callbacks to fire (and fail) harmlessly while pytest-qt
    exception capture is still scoped to the current test.
    """
    yield
    try:
        from PySide6.QtCore import QCoreApplication

        app = QCoreApplication.instance()
        if app is not None:
            # Process pending events so any stale QTimer callbacks fire
            # and are caught by the current test's exception scope rather
            # than leaking into the setup of the next test.
            for _ in range(5):
                app.processEvents()
    except Exception:
        pass
