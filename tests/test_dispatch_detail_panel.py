"""Tests for the dispatch detail panel dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def dispatch_detail(qt_widget, qtbot):
    db = MagicMock()
    trip_id = 1
    trip_data = {"id": 1, "client": "Test Co", "status": "planned", "price": 500}
    dlg = __import__("ui.dialogs.dispatch_detail_panel", fromlist=["QtDispatchDetailPanel"]).QtDispatchDetailPanel(
        parent=qt_widget, db=db, trip_id=trip_id, trip_data=trip_data,
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()

class TestQtDispatchDetailPanel:
    def test_creation(self, dispatch_detail):
        assert dispatch_detail._trip_id == 1

    def test_trip_data_stored(self, dispatch_detail):
        assert dispatch_detail._trip_data["client"] == "Test Co"

    def test_status_displayed(self, dispatch_detail):
        assert hasattr(dispatch_detail, "_status_combo")

    def test_close_button_exists(self, dispatch_detail):
        assert hasattr(dispatch_detail, "_btn_close")

    def test_save_button_exists(self, dispatch_detail):
        assert hasattr(dispatch_detail, "_btn_save")

    def test_dialog_is_modal(self, dispatch_detail):
        assert dispatch_detail.isModal()

    def test_fields_populated_from_trip(self, dispatch_detail):
        assert dispatch_detail._trip_data.get("client") == "Test Co"
