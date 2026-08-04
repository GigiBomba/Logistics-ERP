"""Tests for utils.error_handling — global excepthook + error-dialog marshalling.

Covers:
- install/uninstall of sys.excepthook, threading.excepthook, Qt msg handler
- the handler functions log the failure and do not raise
- SystemExit/KeyboardInterrupt are delegated (no dialog)
- the error dialog is marshalled to the GUI thread when the hook fires on a
  worker thread, and shown directly on the GUI thread
- no dialog when the application is shutting down
- Qt message handler is conservative (Critical/Fatal only)
"""

from __future__ import annotations

import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

import utils.error_handling as eh


@pytest.fixture(autouse=True)
def _clean_handlers():
    """Ensure handlers are uninstalled and dialog state reset around every test."""
    eh.uninstall_global_handlers()
    eh._reset_dialog_state()
    yield
    eh.uninstall_global_handlers()
    eh._reset_dialog_state()


class TestInstallGlobalHandlers:
    def test_installs_sys_and_threading_hooks(self):
        eh.install_global_handlers()
        assert sys.excepthook is eh._handle_uncaught
        assert threading.excepthook is eh._threading_excepthook

    def test_install_is_idempotent(self):
        eh.install_global_handlers()
        first_original = eh._original_sys_excepthook
        eh.install_global_handlers()
        assert eh._original_sys_excepthook is first_original
        assert sys.excepthook is eh._handle_uncaught

    def test_uninstall_restores_original_hooks(self):
        original_sys = sys.excepthook
        original_threading = threading.excepthook
        eh.install_global_handlers()
        eh.uninstall_global_handlers()
        assert sys.excepthook is original_sys
        assert threading.excepthook is original_threading
        assert eh._handlers_installed is False


class TestHandleUncaught:
    def test_logs_critical_and_presents_error(self):
        eh.install_global_handlers()
        with patch.object(eh.logger, "critical") as mock_crit, \
             patch.object(eh, "_present_error") as mock_present:
            eh._handle_uncaught(ValueError, ValueError("boom"), None)
        mock_crit.assert_called_once()
        args = mock_crit.call_args[0]
        assert any("boom" in str(a) for a in args)
        mock_present.assert_called_once()

    def test_does_not_raise_inside_handler(self):
        eh.install_global_handlers()
        # A failure inside _present_error must not propagate out of the hook.
        with patch.object(eh, "_present_error", side_effect=RuntimeError("nested")):
            eh._handle_uncaught(ValueError, ValueError("boom"), None)
        # No assertion needed — the point is that the call returned normally.

    def test_system_exit_delegated_without_dialog(self):
        eh.install_global_handlers()
        original = MagicMock()
        eh._original_sys_excepthook = original
        with patch.object(eh.logger, "critical") as mock_crit, \
             patch.object(eh, "_present_error") as mock_present:
            eh._handle_uncaught(SystemExit, SystemExit(0), None)
        mock_crit.assert_not_called()
        mock_present.assert_not_called()
        original.assert_called_once()

    def test_keyboard_interrupt_delegated_without_dialog(self):
        eh.install_global_handlers()
        original = MagicMock()
        eh._original_sys_excepthook = original
        with patch.object(eh, "_present_error") as mock_present:
            eh._handle_uncaught(KeyboardInterrupt, KeyboardInterrupt(), None)
        mock_present.assert_not_called()
        original.assert_called_once()


class TestThreadingExcepthook:
    def test_logs_thread_context(self):
        eh.install_global_handlers()
        args = MagicMock()
        args.exc_type = ValueError
        args.exc_value = ValueError("thread boom")
        args.exc_traceback = None
        args.thread = None
        with patch.object(eh.logger, "critical") as mock_crit, \
             patch.object(eh, "_present_error") as mock_present:
            eh._threading_excepthook(args)
        mock_crit.assert_called_once()
        assert any("thread boom" in str(a) for a in mock_crit.call_args[0])
        mock_present.assert_called_once()

    def test_benign_exception_in_thread_ignored(self):
        eh.install_global_handlers()
        args = MagicMock()
        args.exc_type = SystemExit
        args.exc_value = SystemExit(0)
        args.exc_traceback = None
        with patch.object(eh.logger, "critical") as mock_crit, \
             patch.object(eh, "_present_error") as mock_present:
            eh._threading_excepthook(args)
        mock_crit.assert_not_called()
        mock_present.assert_not_called()


class TestDialogMarshalling:
    def test_error_from_gui_thread_shows_dialog_directly(self, qtbot):
        eh.install_global_handlers()
        with patch.object(eh, "_show_error_dialog") as mock_show:
            eh._handle_uncaught(ValueError, ValueError("boom"), None)
        mock_show.assert_called_once()
        assert "boom" in mock_show.call_args[0][0]

    def test_error_from_worker_thread_marshals_dialog_to_gui_thread(self, qtbot):
        eh.install_global_handlers()
        with patch.object(eh, "_show_error_dialog") as mock_show:
            def worker():
                eh._handle_uncaught(RuntimeError, RuntimeError("worker boom"), None)
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            t.join()
            qtbot.waitUntil(lambda: mock_show.called, timeout=3000)
        mock_show.assert_called_once()
        assert "worker boom" in mock_show.call_args[0][0]

    def test_no_dialog_when_application_is_shutting_down(self, qtbot, monkeypatch):
        eh.install_global_handlers()
        monkeypatch.setattr(
            eh.QCoreApplication, "closingDown", staticmethod(lambda: True),
        )
        with patch.object(eh, "_show_error_dialog") as mock_show, \
             patch.object(eh.logger, "critical") as mock_crit:
            eh._handle_uncaught(ValueError, ValueError("boom"), None)
        mock_crit.assert_called_once()   # still logged
        mock_show.assert_not_called()    # but no dialog during shutdown


class TestQtMessageHandler:
    def test_critical_qt_message_logged_and_dialog_shown(self, qtbot):
        eh.install_global_handlers()
        with patch.object(eh.logger, "critical") as mock_crit, \
             patch.object(eh, "_show_error_dialog") as mock_show:
            eh._qt_message_handler(eh.QtMsgType.QtCriticalMsg, None, "qt boom")
        mock_crit.assert_called_once()
        args = mock_crit.call_args[0]
        assert any("qt boom" in str(a) for a in args)
        mock_show.assert_called_once()
        assert "qt boom" in mock_show.call_args[0][0]

    def test_warning_qt_message_ignored(self, qtbot):
        eh.install_global_handlers()
        with patch.object(eh.logger, "critical") as mock_crit, \
             patch.object(eh, "_show_error_dialog") as mock_show:
            eh._qt_message_handler(eh.QtMsgType.QtWarningMsg, None, "ignored")
        mock_crit.assert_not_called()
        mock_show.assert_not_called()

    def test_debug_qt_message_ignored(self, qtbot):
        eh.install_global_handlers()
        with patch.object(eh.logger, "critical") as mock_crit, \
             patch.object(eh, "_show_error_dialog") as mock_show:
            eh._qt_message_handler(eh.QtMsgType.QtDebugMsg, None, "ignored")
        mock_crit.assert_not_called()
        mock_show.assert_not_called()
