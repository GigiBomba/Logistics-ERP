"""Regression tests for the route planner calculation flow.

The route planner used to call ``QTimer.singleShot(0, ...)`` from a
worker thread to marshal the result back to the GUI thread.  Qt
creates the timer in the calling thread, so its event loop never
ran, the slot was never invoked, and the "Calculating…" state hung
forever.  The fix uses a ``Signal`` (which Qt marshals across
threads) connected to ``_on_route_result``.
"""

import os
import tempfile
import threading
import time
import unittest

from PySide6.QtWidgets import QApplication


def _ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _new_db():
    from database.db_manager import DatabaseManager
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    db = DatabaseManager(tmp.name)
    return db, tmp.name


def _insert_truck(db, plate: str, consumption: float = 25.0) -> None:
    db.conn.execute(
        "INSERT INTO trucks (plate_number, fuel_consumption, active_status) "
        "VALUES (?, ?, 1)",
        (plate, consumption),
    )
    db.conn.commit()


class _RoutePlannerHarness:
    """Builds a QtRoutePlannerView wired with in-memory stops."""

    def __init__(self) -> None:
        self.db, self.path = _new_db()
        _insert_truck(self.db, "B-123-ABC")
        from ui.views.route_planner_view import QtRoutePlannerView
        self.view = QtRoutePlannerView(None, db=self.db)
        # Inject a fake truck selection — the view normally builds this
        # from the fleet combo, but we want a deterministic test.
        self.view._trucks_map = {
            "1": {
                "id": "1",
                "plate_number": "B-123-ABC",
                "fuel_consumption": 25.0,
            },
        }
        self.view._selected_truck_id = "1"
        # Two pre-resolved stops so the runner doesn't hit the network
        # for geocoding.
        self.view.stops_state = [
            {"address": "A", "lat": 46.0, "lon": 25.0, "resolved": True},
            {"address": "B", "lat": 47.0, "lon": 26.0, "resolved": True},
        ]

    def close(self) -> None:
        try:
            self.db.close()
        finally:
            os.unlink(self.path)
        self.view.deleteLater()


class TestRoutePlannerSignalMarshaling(unittest.TestCase):
    """The result callback must reach the GUI thread and clear the
    "Calculating…" state."""

    def test_route_result_received_signal_exists(self) -> None:
        _ensure_qapp()
        h = _RoutePlannerHarness()
        try:
            v = h.view
            self.assertTrue(hasattr(v, "route_result_received"))
        finally:
            h.close()

    def test_callback_uses_signal_not_qtimer(self) -> None:
        """Defensive: the click handler must use the signal-based marshal,
        not a raw QTimer.singleShot that would lose results when called
        from a worker thread."""
        _ensure_qapp()
        h = _RoutePlannerHarness()
        try:
            import inspect
            from ui.views.route_planner_view import QtRoutePlannerView
            src = inspect.getsource(QtRoutePlannerView._on_calculate_click)
            # The QTimer.singleShot in the callback would be the broken path.
            self.assertNotIn("QTimer.singleShot", src)
            # The signal must be used instead.
            self.assertIn("route_result_received", src)
        finally:
            h.close()

    def test_calculation_completes_and_clears_ui(self) -> None:
        """End-to-end: click calculate → wait for result → button re-enables,
        info label updated, history id set."""
        _ensure_qapp()
        h = _RoutePlannerHarness()
        try:
            v = h.view
            v._on_calculate_click()
            self.assertFalse(v.calculate_btn.isEnabled(),
                             "Calculate button should be disabled while running")
            # Pump events until the route arrives (graphhopper call may take
            # 1-10s; allow 30s for a CI-friendly upper bound).
            deadline = time.time() + 30.0
            done = False
            while time.time() < deadline:
                QApplication.processEvents()
                if v.calculate_btn.isEnabled():
                    done = True
                    break
                time.sleep(0.2)
            self.assertTrue(
                done,
                "Calculate button never re-enabled — the worker-thread "
                "callback was never delivered to the GUI thread.",
            )
            self.assertTrue(v.calculate_btn.isEnabled())
            self.assertTrue(v.lbl_info.text(),
                            "lbl_info should have been updated with the result")
            self.assertIsNotNone(v._last_route_history_id,
                                 "History id should be set after a successful calc")
        finally:
            h.close()


class TestSignalDeliversAcrossThreads(unittest.TestCase):
    """Direct verification: emitting the signal from a non-GUI thread
    queues the slot for execution on the GUI thread."""

    def test_signal_from_worker_thread_reaches_gui(self) -> None:
        _ensure_qapp()
        h = _RoutePlannerHarness()
        try:
            v = h.view
            received = []

            def slot(result, ctx, token):
                received.append((threading.current_thread().name, token))

            v.route_result_received.connect(slot)

            def worker():
                # Pretend the runner finished — emit from this thread.
                v.route_result_received.emit({"ok": True}, None, 1)

            t = threading.Thread(target=worker, daemon=True)
            t.start()
            t.join()

            # Pump the GUI event loop so the queued slot runs.
            for _ in range(20):
                QApplication.processEvents()
                if received:
                    break
                time.sleep(0.05)
            self.assertEqual(len(received), 1)
            # The slot ran in the main thread, not the worker.
            self.assertNotEqual(received[0][0], t.name)
        finally:
            h.close()


if __name__ == "__main__":
    unittest.main()
