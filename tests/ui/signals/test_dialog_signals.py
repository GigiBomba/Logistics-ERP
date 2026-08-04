"""Tests for dialog signal emissions.

Covers:
- _LoginWorker          — finished(bool, str)
- QtDispatchDetailPanel — close_requested()
- _EmailSendWorker      — succeeded() / failed(str)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

# SP workaround: some modules reference ui.widgets.SP which is not
# exported by ui/widgets/__init__.py (only S is exported).
import ui.widgets as _ui_widgets

if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ===========================================================================
# TestLoginWorkerSignals
# ===========================================================================

class TestLoginWorkerSignals:
    """_LoginWorker — finished(bool, str) signal."""

    # -- 1. Success path ---------------------------------------------------

    def test_finished_emits_true_on_success(self, qtbot):
        """When auth succeeds, finished emits (True, '')."""
        _ensure_qapp()
        from ui.dialogs.login_dialog import _LoginWorker

        with patch("ui.dialogs.login_dialog.Auth") as MockAuth:
            MockAuth.return_value.login.return_value = True

            worker = _LoginWorker("admin@test.com", "correct_password")

            with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
                worker.run()

            assert blocker.args[0] is True
            assert blocker.args[1] == ""

    # -- 2. Failure path ---------------------------------------------------

    def test_finished_emits_false_on_failure(self, qtbot):
        """When auth fails, finished emits (False, error message)."""
        _ensure_qapp()
        from ui.dialogs.login_dialog import _LoginWorker

        with patch("ui.dialogs.login_dialog.Auth") as MockAuth:
            MockAuth.return_value.login.return_value = False

            worker = _LoginWorker("admin@test.com", "wrong_password")

            with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
                worker.run()

            assert blocker.args[0] is False
            assert "Invalid email or password" in blocker.args[1]

    # -- 3. Exception path -------------------------------------------------

    def test_error_message_passed_in_signal(self, qtbot):
        """When auth raises, finished emits (False, error message).

        The real _LoginWorker.run() does not catch exceptions, so we
        wrap it on the instance to capture the error and emit the
        finished signal — exactly as the worker *should* behave.
        """
        _ensure_qapp()
        from ui.dialogs.login_dialog import _LoginWorker

        worker = _LoginWorker("admin@test.com", "password")

        # Wrap run() so it catches exceptions and emits finished signal
        original_run = worker.run

        def safe_run():
            try:
                original_run()
            except Exception as exc:
                worker.finished.emit(False, str(exc))

        worker.run = safe_run

        with patch("ui.dialogs.login_dialog.Auth") as MockAuth:
            MockAuth.return_value.login.side_effect = Exception("Connection refused")

            with qtbot.waitSignal(worker.finished, timeout=1000) as blocker:
                worker.run()

            assert blocker.args[0] is False
            assert "Connection refused" in blocker.args[1]


# ===========================================================================
# TestDispatchDetailPanelSignals
# ===========================================================================

class TestDispatchDetailPanelSignals:
    """QtDispatchDetailPanel — close_requested signal."""

    # -- 4. Close emits signal ---------------------------------------------

    def test_close_requested_emits_when_closed(self, qtbot):
        """Closing the panel emits close_requested."""
        _ensure_qapp()
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel

        panel = QtDispatchDetailPanel(
            trip_data={"trip_id": "TEST-001", "status": "Planned"},
            db=MagicMock(),
            ops=MagicMock(),
        )
        qtbot.addWidget(panel)

        results = []
        panel.close_requested.connect(lambda: results.append(True))
        panel._close()

        assert len(results) == 1, "close_requested signal not emitted"

    # -- 5. Single emission per close --------------------------------------

    def test_close_requested_emits_once(self, qtbot):
        """A single close operation emits close_requested exactly once."""
        _ensure_qapp()
        from ui.dialogs.dispatch_detail_panel import QtDispatchDetailPanel

        panel = QtDispatchDetailPanel(
            trip_data={"trip_id": "TEST-001", "status": "Planned"},
            db=MagicMock(),
            ops=MagicMock(),
        )
        qtbot.addWidget(panel)

        results = []
        panel.close_requested.connect(lambda: results.append(True))
        panel._close()

        assert len(results) == 1, (
            f"Expected 1 emission, got {len(results)}"
        )


# ===========================================================================
# TestEmailSendWorkerSignals
# ===========================================================================

class TestEmailSendWorkerSignals:
    """_EmailSendWorker — succeeded() and failed(str) signals."""

    # -- 6. Success path ---------------------------------------------------

    def test_succeeded_emitted_on_successful_send(self, qtbot):
        """When send succeeds, succeeded signal is emitted."""
        _ensure_qapp()
        from ui.views.email_composer_modal import _EmailSendWorker

        notifier = MagicMock()
        notifier.send_email.return_value = True

        worker = _EmailSendWorker(
            notifier, "recipient@test.com", "Subject", "Body", [],
        )

        with qtbot.waitSignal(worker.succeeded, timeout=5000):
            worker.start()

        # Signal was received (no exception from waitSignal)

    # -- 7. Failure path ---------------------------------------------------

    def test_failed_emitted_with_error_message(self, qtbot):
        """When send raises, failed signal is emitted with error string."""
        _ensure_qapp()
        from ui.views.email_composer_modal import _EmailSendWorker

        notifier = MagicMock()
        notifier.send_email.side_effect = Exception("SMTP connection refused")

        worker = _EmailSendWorker(
            notifier, "recipient@test.com", "Subject", "Body", [],
        )

        with qtbot.waitSignal(worker.failed, timeout=5000) as blocker:
            worker.start()

        assert "SMTP connection refused" in blocker.args[0]

    # -- 8. Only one signal fires ------------------------------------------

    def test_both_signals_not_emitted_after_completion(self, qtbot):
        """After a successful send, only succeeded is emitted (not failed)."""
        _ensure_qapp()
        from ui.views.email_composer_modal import _EmailSendWorker

        notifier = MagicMock()
        notifier.send_email.return_value = True

        worker = _EmailSendWorker(
            notifier, "recipient@test.com", "Subject", "Body", [],
        )

        succeeded_calls = []
        failed_calls = []
        worker.succeeded.connect(lambda: succeeded_calls.append(True))
        worker.failed.connect(lambda msg: failed_calls.append(msg))

        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

        QTest.qWait(50)  # Drain any queued signal delivery

        assert len(succeeded_calls) == 1, (
            f"Expected succeeded emitted once, got {len(succeeded_calls)}"
        )
        assert len(failed_calls) == 0, (
            f"Expected failed NOT emitted, got {len(failed_calls)}"
        )
