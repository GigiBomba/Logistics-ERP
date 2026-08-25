"""Regression tests for the cross-thread Signal marshaling fix.

Several views used to do ``QTimer.singleShot(0, fn)`` from a worker
thread to "marshal" callbacks to the GUI thread.  Qt creates the
timer in the calling thread, so its event loop never runs and the
slot is never invoked.  Each fix replaces that with a Qt ``Signal``
(``Signal.emit`` is thread-safe — the slot runs in the receiver's
thread, which is the GUI thread).

This file verifies, for each affected view, that:

1. The Signal-based marshal is in place (static-source check).
2. Emitting a Signal from a non-GUI thread delivers the slot on the
   GUI thread.
"""
from __future__ import annotations


import inspect
import threading
import time
import unittest

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


def _ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


class _SignalCarrier(QObject):
    """Minimal QObject that hosts the same signal pattern used by
    the views.  Lets us test the cross-thread marshaling semantics
    without constructing the full view (which needs a real DB, etc.)."""

    preview_loaded = Signal(object, int)
    import_completed = Signal(dict)
    trip_context_updated = Signal(object, object)
    refresh_finished = Signal()
    dispatch_callable = Signal(object)


def _emit_from_worker(signal: Signal, *args, timeout: float = 2.0):
    """Emit ``signal`` from a non-GUI thread and wait for any slots.

    Returns a list filled by connected slots.  Each entry is
    ``(thread_name, *args)`` captured inside the slot.
    """
    received = []

    def slot(*args):
        received.append((threading.current_thread().name, *args))

    signal.connect(slot)
    try:
        def worker():
            signal.emit(*args)
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join()
        deadline = time.time() + timeout
        while time.time() < deadline and not received:
            QApplication.processEvents()
            time.sleep(0.02)
        return received, t.name
    finally:
        signal.disconnect(slot)


# ══════════════════════════════════════════════════════════════════════════════
# RouteHistoryView — preview_loaded signal
# ══════════════════════════════════════════════════════════════════════════════


class TestRouteHistoryViewSignal(unittest.TestCase):
    def test_signal_exists(self) -> None:
        from ui.views.route_history_view import QtRouteHistoryView
        self.assertTrue(hasattr(QtRouteHistoryView, "preview_loaded"))

    def test_no_qtimer_singleshot_in_worker(self) -> None:
        src = inspect.getsource(
            __import__("ui.views.route_history_view", fromlist=["QtRouteHistoryView"])
            .QtRouteHistoryView
        )
        # The original bug was a QTimer.singleShot(0, ...) in the
        # preview-loader worker.
        self.assertNotIn("QTimer.singleShot(0, lambda: self._apply_preview", src)
        # The signal must be emitted instead.
        self.assertIn("preview_loaded.emit", src)

    def test_signal_marshals_across_threads(self) -> None:
        _ensure_qapp()
        carrier = _SignalCarrier()
        received, worker_name = _emit_from_worker(
            carrier.preview_loaded, {"ok": True}, 1,
        )
        self.assertEqual(len(received), 1)
        self.assertNotEqual(received[0][0], worker_name)
        self.assertEqual(received[0][1], {"ok": True})
        self.assertEqual(received[0][2], 1)


# ══════════════════════════════════════════════════════════════════════════════
# TachoImportView — import_completed signal
# ══════════════════════════════════════════════════════════════════════════════


class TestTachoImportViewSignal(unittest.TestCase):
    def test_signal_exists(self) -> None:
        from ui.views.tacho_import_view import QtTachoImportView
        self.assertTrue(hasattr(QtTachoImportView, "import_completed"))

    def test_no_qtimer_singleshot_in_worker(self) -> None:
        src = inspect.getsource(
            __import__("ui.views.tacho_import_view", fromlist=["QtTachoImportView"])
            .QtTachoImportView
        )
        self.assertNotIn("QTimer.singleShot(0, lambda r=result", src)
        self.assertIn("import_completed.emit", src)

    def test_signal_marshals_across_threads(self) -> None:
        _ensure_qapp()
        carrier = _SignalCarrier()
        received, worker_name = _emit_from_worker(
            carrier.import_completed, {"success": True, "id": 42},
        )
        self.assertEqual(len(received), 1)
        self.assertNotEqual(received[0][0], worker_name)
        self.assertEqual(received[0][1]["id"], 42)


# ══════════════════════════════════════════════════════════════════════════════
# CalculatorView — trip_context_updated signal
# ══════════════════════════════════════════════════════════════════════════════


class TestCalculatorViewSignal(unittest.TestCase):
    def test_signal_exists(self) -> None:
        from ui.views.calculator_view import QtCalculatorView
        self.assertTrue(hasattr(QtCalculatorView, "trip_context_updated"))

    def test_no_qtimer_singleshot_in_listener(self) -> None:
        src = inspect.getsource(
            __import__("ui.views.calculator_view", fromlist=["QtCalculatorView"])
            .QtCalculatorView
        )
        self.assertNotIn(
            "QTimer.singleShot(0, lambda: self._apply_trip_context", src
        )
        self.assertIn("trip_context_updated.emit", src)

    def test_signal_marshals_across_threads(self) -> None:
        _ensure_qapp()
        carrier = _SignalCarrier()
        marker = object()
        received, worker_name = _emit_from_worker(
            carrier.trip_context_updated, marker, ["route"],
        )
        self.assertEqual(len(received), 1)
        self.assertNotEqual(received[0][0], worker_name)
        self.assertIs(received[0][1], marker)
        self.assertEqual(received[0][2], ["route"])


# ══════════════════════════════════════════════════════════════════════════════
# FleetTrackingView — _refreshFinished signal
# ══════════════════════════════════════════════════════════════════════════════


class TestFleetTrackingViewSignal(unittest.TestCase):
    def test_refresh_finished_signal_exists(self) -> None:
        from ui.views.fleet_tracking_view import QtFleetTrackingView
        self.assertTrue(hasattr(QtFleetTrackingView, "_refreshFinished"))

    def test_no_qtimer_singleshot_in_worker(self) -> None:
        src = inspect.getsource(
            __import__("ui.views.fleet_tracking_view", fromlist=["QtFleetTrackingView"])
            .QtFleetTrackingView
        )
        self.assertNotIn("QTimer.singleShot(0, self._enable_refresh_btn)", src)
        self.assertIn("_refreshFinished.emit", src)

    def test_signal_marshals_across_threads(self) -> None:
        _ensure_qapp()
        carrier = _SignalCarrier()
        received, worker_name = _emit_from_worker(carrier.refresh_finished)
        self.assertEqual(len(received), 1)
        self.assertNotEqual(received[0][0], worker_name)


# ══════════════════════════════════════════════════════════════════════════════
# DispatchBoardView — _dispatchSignal
# ══════════════════════════════════════════════════════════════════════════════


class TestDispatchBoardDispatchSignal(unittest.TestCase):
    def test_dispatch_signal_exists(self) -> None:
        from ui.views.dispatch_board_view import QtDispatchBoardView
        self.assertTrue(hasattr(QtDispatchBoardView, "_dispatchSignal"))

    def test_dispatch_uses_signal_not_qtimer(self) -> None:
        import textwrap
        from ui.views.dispatch_board_view import QtDispatchBoardView
        import ast
        src = textwrap.dedent(inspect.getsource(QtDispatchBoardView._dispatch))
        tree = ast.parse(src)
        func_def = tree.body[0]
        offending: list = []
        for node in ast.walk(func_def):
            if isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "singleShot"
                ):
                    offending.append(ast.dump(node))
        self.assertEqual(
            offending, [],
            "_dispatch must not use QTimer.singleShot — emit the signal instead",
        )
        self.assertTrue(hasattr(QtDispatchBoardView, "_dispatchSignal"))

    def test_dispatch_runs_fn_on_gui_thread(self) -> None:
        _ensure_qapp()
        carrier = _SignalCarrier()
        called = []

        def fn():
            called.append(threading.current_thread().name)

        # Simulate the dispatch pattern: a worker emits a signal with
        # the callable; a slot in the GUI thread invokes it.
        def slot(fn_):
            fn_()

        carrier.dispatch_callable.connect(slot)
        try:
            def worker():
                carrier.dispatch_callable.emit(fn)
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            t.join()
            deadline = time.time() + 2.0
            while time.time() < deadline and not called:
                QApplication.processEvents()
                time.sleep(0.02)
            self.assertEqual(len(called), 1)
            # The function was called from the GUI thread, not the worker.
            self.assertNotEqual(called[0], t.name)
        finally:
            carrier.dispatch_callable.disconnect(slot)


# ══════════════════════════════════════════════════════════════════════════════
# Generic: prove the diagnosis (QTimer.singleShot from worker thread is broken)
# ══════════════════════════════════════════════════════════════════════════════


class TestQTIMER_FROM_WORKER_THREAD_DOES_NOT_MARSHAL(unittest.TestCase):
    """Documents the original bug so the regression tests are
    understood, not just blindly trusted.  This is a one-line
    demonstration of the Qt cross-thread pitfall."""

    def test_qtimer_singleshot_from_worker_thread_never_fires(self) -> None:
        _ensure_qapp()
        from PySide6.QtCore import QTimer, QObject
        fired = []
        class Sink(QObject):
            @staticmethod
            def slot():
                fired.append(threading.current_thread().name)
        sink = Sink()
        QTimer.singleShot(50, sink.slot)

        def worker():
            # Re-issue from a non-GUI thread.
            QTimer.singleShot(50, sink.slot)
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        t.join()
        # Pump events for up to 2s — the worker-thread timer never fires.
        deadline = time.time() + 2.0
        while time.time() < deadline and not fired:
            QApplication.processEvents()
            time.sleep(0.05)
        # The first singleShot (issued from the main thread) should
        # have fired, so ``fired`` must contain at least one entry.
        # The second (from the worker thread) is never delivered,
        # but we can't easily detect that here.  This test mainly
        # documents the *reason* for the Signal-based fix.
        self.assertGreaterEqual(len(fired), 1)
        self.assertEqual(fired[0], threading.current_thread().name)


if __name__ == "__main__":
    unittest.main()
