"""Tests for the edit window dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def edit_window(qt_widget, qtbot):
    db = MagicMock()
    trip_id = 1
    trip_data = {
        "id": 1, "client": "Test Co", "origin": "A", "destination": "B",
        "price": 500, "distance_km": 200, "status": "planned",
    }
    dlg = __import__("ui.dialogs.edit_window", fromlist=["QtEditWindow"]).QtEditWindow(
        parent=qt_widget, db=db, trip_id=trip_id, trip_data=trip_data,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()

class TestQtEditWindow:
    def test_creation(self, edit_window):
        assert edit_window._trip_id == 1

    def test_trip_fields_populated(self, edit_window):
        assert edit_window._trip_data["client"] == "Test Co"

    def test_has_save_button(self, edit_window):
        assert hasattr(edit_window, "_btn_save")

    def test_can_modify_fields(self, edit_window):
        assert hasattr(edit_window, "_price_input")
        assert hasattr(edit_window, "_distance_input")

    def test_dialog_is_modal(self, edit_window):
        assert edit_window.isModal()
