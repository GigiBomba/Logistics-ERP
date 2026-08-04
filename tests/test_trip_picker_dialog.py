"""Tests for the trip picker dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def trip_picker(qt_widget, qtbot):
    db = MagicMock()
    dlg = __import__("ui.dialogs.trip_picker_dialog", fromlist=["QtTripPickerDialog"]).QtTripPickerDialog(
        parent=qt_widget, db=db,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()

class TestQtTripPickerDialog:
    def test_creation(self, trip_picker):
        assert trip_picker._db is not None

    def test_trip_list_created(self, trip_picker):
        assert hasattr(trip_picker, "_list")

    def test_search_input_exists(self, trip_picker):
        assert hasattr(trip_picker, "_search_edit")

    def test_link_button_exists(self, trip_picker):
        assert hasattr(trip_picker, "_link_btn")

    def test_no_auto_selection(self, trip_picker):
        assert trip_picker._list.currentItem() is None

    def test_dialog_is_modal(self, trip_picker):
        assert trip_picker.isModal()

    def test_cancel_closes_dialog(self, trip_picker, qtbot):
        trip_picker.reject()
        assert trip_picker.result() == 0
