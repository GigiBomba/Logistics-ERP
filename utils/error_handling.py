"""Global exception handling for the Operion ERP desktop app.

Installs ``sys.excepthook``, ``threading.excepthook`` and a conservative
``qInstallMessageHandler`` (Qt Critical/Fatal only) so that uncaught runtime
exceptions are:

1. logged with a full traceback via the module logger, and
2. surfaced to the user through a modal error dialog.

GUI-thread marshalling
----------------------
The hook may run on any thread.  The dialog is marshalled to the GUI thread
through a dedicated ``QObject`` whose ``Signal`` is connected on the main
thread: emitting a ``Signal`` is thread-safe and, with the default
AutoConnection, queues the slot to the receiver's thread (the GUI thread's
event loop).  This is the same pattern already used across the codebase
(``ui/worker_pool.py``, ``tests/test_cross_thread_signals.py``) and avoids
``QTimer.singleShot(0, ...)`` from a worker thread — Qt creates that timer in
the *calling* thread, whose event loop never runs (see ``services/stop_factory.py``).

If the hook fires on the GUI thread the dialog is shown directly; otherwise
the bridge signal is emitted and the queued slot runs on the GUI thread.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import traceback
from typing import Any, Optional

from PySide6.QtCore import (
    QCoreApplication,
    QObject,
    QThread,
    QtMsgType,
    Signal,
    qInstallMessageHandler,
)
from PySide6.QtWidgets import QApplication, QMessageBox

logger = logging.getLogger(__name__)

# Only surface Qt messages of Critical/Fatal severity; Qt warnings and debug
# output are intentionally left untouched.
_QT_FATAL_LEVELS: frozenset[int] = frozenset(
    {int(QtMsgType.QtCriticalMsg), int(QtMsgType.QtFatalMsg)}
)

# Show at most one dialog every N seconds to avoid dialog storms when a
# background thread is in a crash loop.
_DIALOG_THROTTLE_SECONDS = 5.0
_last_dialog_ts: float = 0.0
_dialog_in_progress: bool = False

_bridge: Optional["_ErrorDialogBridge"] = None
_handlers_installed: bool = False
_original_sys_excepthook: Any = None
_original_threading_excepthook: Any = None
_original_qt_message_handler: Any = None


class _ErrorDialogBridge(QObject):
    """Lives on the GUI thread; forwards error reports to a modal dialog.

    Created by :func:`install_global_handlers` (main thread, after
    QApplication creation).  ``errorOccurred`` uses the default AutoConnection:
    emitting from a background thread queues the slot to this object's thread —
    the GUI thread.
    """

    errorOccurred = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.errorOccurred.connect(self._on_error_reported)

    def _on_error_reported(self, message: str) -> None:
        _show_error_dialog(message)


# ── Public API ──────────────────────────────────────────────────────────


def install_global_handlers() -> None:
    """Install the global exception handlers.

    Must be called from the GUI thread after ``QApplication`` has been created
    so error dialogs can be marshalled and shown.  Safe to call multiple times
    (idempotent).
    """
    global _bridge, _handlers_installed
    global _original_sys_excepthook, _original_threading_excepthook
    global _original_qt_message_handler

    if _handlers_installed:
        return

    _original_sys_excepthook = sys.excepthook
    sys.excepthook = _handle_uncaught

    _original_threading_excepthook = threading.excepthook
    threading.excepthook = _threading_excepthook

    _original_qt_message_handler = qInstallMessageHandler(_qt_message_handler)

    # The bridge must be created on the GUI thread so its queued slots run there.
    if _bridge is None:
        _bridge = _ErrorDialogBridge()

    _handlers_installed = True


def uninstall_global_handlers() -> None:
    """Restore the original hooks.  Primarily used by the test suite."""
    global _bridge, _handlers_installed
    global _original_sys_excepthook, _original_threading_excepthook
    global _original_qt_message_handler

    if not _handlers_installed:
        return

    if _original_sys_excepthook is not None:
        sys.excepthook = _original_sys_excepthook
    if _original_threading_excepthook is not None:
        threading.excepthook = _original_threading_excepthook
    if _original_qt_message_handler is not None:
        try:
            qInstallMessageHandler(_original_qt_message_handler)
        except Exception:  # pragma: no cover - Qt teardown edge
            pass

    _bridge = None
    _handlers_installed = False
    _original_sys_excepthook = None
    _original_threading_excepthook = None
    _original_qt_message_handler = None


# ── Excepthook implementations ──────────────────────────────────────────


def _handle_uncaught(exc_type, exc_value, exc_tb) -> None:
    """``sys.excepthook`` replacement: log + dialog for uncaught exceptions."""
    try:
        if _is_benign(exc_type):
            _delegate_to_original(exc_type, exc_value, exc_tb)
            return

        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical(
            "Uncaught exception %s: %s\n%s",
            getattr(exc_type, "__name__", exc_type), exc_value, tb_text,
        )
        _present_error(_build_dialog_message(exc_type, exc_value))
    except Exception:  # pragma: no cover - an excepthook must never raise
        try:
            logger.exception("Error inside the global exception handler")
        except Exception:
            pass


def _threading_excepthook(args) -> None:
    """``threading.excepthook`` replacement."""
    try:
        exc_type = getattr(args, "exc_type", None)
        exc_value = getattr(args, "exc_value", None)
        exc_tb = getattr(args, "exc_traceback", None)
        thread = getattr(args, "thread", None)
        thread_label = getattr(thread, "name", str(thread)) if thread is not None else "?"

        if _is_benign(exc_type):
            return

        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical(
            "Uncaught exception in thread %s: %s: %s\n%s",
            thread_label, getattr(exc_type, "__name__", exc_type), exc_value, tb_text,
        )
        _present_error(_build_dialog_message(exc_type, exc_value))
    except Exception:  # pragma: no cover - a thread excepthook must never raise
        try:
            logger.exception("Error inside the threading exception handler")
        except Exception:
            pass


def _qt_message_handler(mode, context, message) -> None:
    """``qInstallMessageHandler`` replacement — conservative.

    Only Critical/Fatal Qt messages are logged and surfaced; Qt warnings, info
    and debug output are ignored so normal Qt behaviour is preserved.
    """
    try:
        if int(mode) not in _QT_FATAL_LEVELS:
            return
    except (TypeError, ValueError):  # pragma: no cover - unknown mode type
        return

    try:
        logger.critical(
            "Qt message (severity %s): %s", _qt_severity_name(mode), message,
        )
        _present_error(_build_qt_dialog_message(message))
    except Exception:  # pragma: no cover - a Qt handler must never raise
        try:
            logger.exception("Error inside the Qt message handler")
        except Exception:
            pass


# ── Dialog marshalling ──────────────────────────────────────────────────


def _present_error(message: str) -> None:
    """Marshal the error to the GUI thread and show a dialog.

    On the GUI thread the dialog is shown directly; from any other thread the
    bridge signal is emitted (AutoConnection queues the slot to the GUI
    thread's event loop).
    """
    if not _can_show_dialog() or _bridge is None:
        return
    app = QApplication.instance()
    if app is not None and QThread.currentThread() is app.thread():
        _show_error_dialog(message)
    else:
        try:
            _bridge.errorOccurred.emit(message)
        except Exception:  # pragma: no cover - signal marshal failure
            logger.exception("Failed to marshal error dialog to the GUI thread")


def _show_error_dialog(message: str) -> None:
    """Show a modal error dialog on the GUI thread.

    Guarded so it never recurses (a failure while rendering the dialog must
    not spawn another dialog) and never fires during shutdown.
    """
    global _dialog_in_progress, _last_dialog_ts

    if not _can_show_dialog():
        return

    now = time.monotonic()
    if now - _last_dialog_ts < _DIALOG_THROTTLE_SECONDS:
        return
    _last_dialog_ts = now

    if _dialog_in_progress:
        return
    _dialog_in_progress = True
    try:
        QMessageBox.critical(None, _error_dialog_title(), message)
    except Exception:  # pragma: no cover - dialog rendering failure
        logger.exception("Failed to display the error dialog")
    finally:
        _dialog_in_progress = False


def _can_show_dialog() -> bool:
    """True when a dialog can be shown: a QApplication exists and the
    application is not shutting down."""
    if QApplication.instance() is None:
        return False
    try:
        if QCoreApplication.closingDown():
            return False
    except Exception:
        return False
    return True


# ── Helpers ─────────────────────────────────────────────────────────────


def _is_benign(exc_type) -> bool:
    """SystemExit/KeyboardInterrupt/GeneratorExit are normal control flow —
    never dialogs; defer to the interpreter default."""
    if not isinstance(exc_type, type) or not issubclass(exc_type, BaseException):
        return False
    return issubclass(exc_type, (SystemExit, KeyboardInterrupt, GeneratorExit))


def _delegate_to_original(exc_type, exc_value, exc_tb) -> None:
    """Pass control-flow exceptions to the original hook so interpreter
    behaviour (e.g. SystemExit exit code) is unchanged."""
    hook = _original_sys_excepthook or sys.__excepthook__
    try:
        hook(exc_type, exc_value, exc_tb)
    except Exception:  # pragma: no cover
        pass


def _error_dialog_title() -> str:
    try:
        from services.i18n import t
        return t("error_dialog_title", "Unexpected Error")
    except Exception:
        return "Unexpected Error"


def _build_dialog_message(exc_type, exc_value) -> str:
    """Short, user-friendly summary for the dialog (no full traceback)."""
    exc_name = getattr(exc_type, "__name__", str(exc_type))
    exc_msg = str(exc_value) or "—"
    try:
        from services.i18n import t
        summary = t(
            "error_dialog_summary",
            "An unexpected error occurred. Details were logged.",
        )
    except Exception:
        summary = "An unexpected error occurred. Details were logged."
    return f"{summary}\n\n{exc_name}: {exc_msg}"


def _build_qt_dialog_message(message: str) -> str:
    try:
        from services.i18n import t
        summary = t(
            "error_dialog_qt_summary",
            "An unexpected error occurred inside the application UI. "
            "The application may be in an unstable state — save your work "
            "and restart. Details were logged.",
        )
    except Exception:
        summary = (
            "An unexpected error occurred inside the application UI. "
            "The application may be in an unstable state — save your work "
            "and restart. Details were logged."
        )
    return f"{summary}\n\n{message}"


def _qt_severity_name(mode) -> str:
    try:
        return QtMsgType(int(mode)).name
    except Exception:
        return str(mode)


def _reset_dialog_state() -> None:
    """Clear dialog throttle/re-entrancy state (test helper)."""
    global _last_dialog_ts, _dialog_in_progress
    _last_dialog_ts = 0.0
    _dialog_in_progress = False
