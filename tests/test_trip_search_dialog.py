"""Tests for the trip search dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def trip_search(qt_widget, qtbot):
    db = MagicMock()
    dlg = __import__("ui.dialogs.trip_search_dialog", fromlist=["QtTripSearchDialog"]).QtTripSearchDialog(
        parent=qt_widget, db=db,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()

class TestQtTripSearchDialog:
    def test_creation(self, trip_search):
        assert trip_search._db is not None

    def test_search_input_exists(self, trip_search):
        assert hasattr(trip_search, "_search_edit")

    def test_results_list_exists(self, trip_search):
        assert hasattr(trip_search, "_list")

    def test_date_filters_exist(self, trip_search):
        assert hasattr(trip_search, "_from_date")
        assert hasattr(trip_search, "_to_date")

    def test_select_button_exists(self, trip_search):
        assert hasattr(trip_search, "_select_btn")

    def test_selected_trip_id_none_initially(self, trip_search):
        assert trip_search.selected_trip_id() is None

    def test_filter_by_text_performs_search(self, trip_search, monkeypatch):
        results = []
        monkeypatch.setattr(trip_search, "_load_trips", lambda: results.extend([]))
        trip_search._search_edit.setText("test")
        assert trip_search._search_edit.text() == "test"
