"""Tests for the maintenance view dialog."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def maintenance_view(qt_widget, qtbot):
    db = MagicMock()
    truck_id = 1
    dlg = __import__("ui.dialogs.maintenance_view", fromlist=["QtMaintenanceView"]).QtMaintenanceView(
        parent=qt_widget, db=db, truck_id=truck_id, truck_plate="AG01ABC",
    )
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()

class TestQtMaintenanceView:
    def test_creation(self, maintenance_view):
        assert maintenance_view.truck_id == 1

    def test_has_three_tabs(self, maintenance_view):
        assert hasattr(maintenance_view, "_tab_widget")
        assert maintenance_view._tab_widget.count() == 3

    def test_tab_labels(self, maintenance_view):
        texts = [maintenance_view._tab_widget.tabText(i) for i in range(3)]
        assert all(len(t) > 0 for t in texts)

    def test_records_tab_exists(self, maintenance_view):
        assert hasattr(maintenance_view, "_record_table")

    def test_schedules_tab_exists(self, maintenance_view):
        assert hasattr(maintenance_view, "_schedule_table")

    def test_health_tab_exists(self, maintenance_view):
        assert hasattr(maintenance_view, "_health_cards")
