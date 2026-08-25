"""Regression tests for invoice auto-fill (Issue 6a).

The original ``_auto_fill_from_trip`` updated the editor's internal
state attributes (``self._truck_plate`` etc.) but never pushed the
new values to the visible ``StyledLineEdit`` widgets.  The user saw
empty text boxes even though the PDF generation worked correctly.

These tests pin down the corrected behaviour.
"""
from __future__ import annotations


import os
import tempfile
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


def _make_view():
    _ensure_qapp()
    db, path = _new_db()
    from ui.views.invoice_editor import QtInvoiceEditor
    view = QtInvoiceEditor(None, db=db, prefs=None)
    return view, db, path


def _build_trip(view, **overrides) -> dict:
    """Build a trip dict and inject it as the editor's selected trip."""
    base = {
        "id": 1,
        "truck_number": "B-123-ABC",
        "driver_name": "John Doe",
        "distance_km": 250.5,
        "start_date": "2024-06-01T08:00:00",
        "end_date": "2024-06-03T18:00:00",
        "total_price_eur": 1500.00,
        "route_history_v2_id": None,
        "client_name": "Acme Corp",
    }
    base.update(overrides)
    view._selected_trip_data = base
    view._selected_trip_id = base["id"]
    return base


class TestAutoFillUpdatesWidgets(unittest.TestCase):
    def setUp(self) -> None:
        self.view, self.db, self.path = _make_view()

    def tearDown(self) -> None:
        try:
            self.db.close()
        finally:
            os.unlink(self.path)
        self.view.deleteLater()

    def test_truck_plate_widget_shows_trip_value(self) -> None:
        _build_trip(self.view)
        self.view._auto_fill_from_trip()
        self.assertEqual(self.view._truck_plate_edit.text(), "B-123-ABC")
        # The internal state matches too.
        self.assertEqual(self.view._truck_plate, "B-123-ABC")

    def test_driver_widget_shows_trip_value(self) -> None:
        _build_trip(self.view)
        self.view._auto_fill_from_trip()
        self.assertEqual(self.view._driver_name_edit.text(), "John Doe")
        self.assertEqual(self.view._driver_name, "John Doe")

    def test_distance_widget_shows_trip_value(self) -> None:
        _build_trip(self.view)
        self.view._auto_fill_from_trip()
        # 250.5 km formatted with thousands separator.
        self.assertEqual(self.view._distance_edit.text(), "250.5 km")
        self.assertEqual(self.view._distance, "250.5 km")

    def test_issue_date_widget_shows_trip_start(self) -> None:
        _build_trip(self.view)
        self.view._auto_fill_from_trip()
        self.assertEqual(self.view._issue_date_edit.text(), "2024-06-01")
        self.assertEqual(self.view._issue_date, "2024-06-01")

    def test_due_date_widget_shows_end_plus_30_days(self) -> None:
        _build_trip(self.view)
        self.view._auto_fill_from_trip()
        self.assertEqual(self.view._due_date_edit.text(), "2024-07-03")
        self.assertEqual(self.view._due_date, "2024-07-03")

    def test_description_widget_filled_even_when_distance_zero(self) -> None:
        _build_trip(self.view, distance_km=0)
        self.view._auto_fill_from_trip()
        # Previously this branch was skipped when ``dist == 0``,
        # leaving the description empty.  Now it fills with a
        # sensible default.
        self.assertNotEqual(self.view._desc_text_edit.toPlainText(), "")

    def test_handles_missing_trip_data(self) -> None:
        # If trip is None, the method must early-return without
        # raising and without touching the widgets.
        self.view._selected_trip_data = None
        before_plate = self.view._truck_plate_edit.text()
        self.view._auto_fill_from_trip()
        # No change.
        self.assertEqual(self.view._truck_plate_edit.text(), before_plate)

    def test_handles_empty_trip_fields(self) -> None:
        # A trip with all None fields should clear the widgets (set
        # text to empty string) without crashing.
        _build_trip(self.view,
                     truck_number=None, driver_name=None,
                     distance_km=None, start_date="", end_date="")
        self.view._auto_fill_from_trip()
        self.assertEqual(self.view._truck_plate_edit.text(), "")
        self.assertEqual(self.view._driver_name_edit.text(), "")
        # Distance falls back to empty (the f"... km" format only
        # applies when dist > 0).
        self.assertEqual(self.view._distance_edit.text(), "")

    def test_set_text_helper_does_not_recursive_fire(self) -> None:
        # ``_set_text`` must use ``blockSignals`` so the
        # ``textChanged`` handlers don't fire during auto-fill.
        # We verify this by counting how many times the handler runs.
        _build_trip(self.view)
        calls = []
        original_handler = self.view._on_truck_plate_changed

        def counting_handler(text):
            calls.append(text)
            original_handler(text)

        self.view._on_truck_plate_changed = counting_handler
        self.view._set_text(self.view._truck_plate_edit, "NEW-PLATE")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
