"""Tests for the fleet tab view."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def fleet_tab(qt_widget, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui.views.fleet_tab.QtFleetTab._initial_load",
        lambda self: None,
    )
    db = MagicMock()
    ops = MagicMock()
    ops.event_bus = MagicMock()
    ops.event_bus.subscribe = MagicMock(return_value="sub_id")
    ops.event_bus.unsubscribe = MagicMock()
    fleet_service = MagicMock()
    api_client = MagicMock()
    view = __import__("ui.views.fleet_tab", fromlist=["QtFleetTab"]).QtFleetTab(
        qt_widget, db=db, ops=ops, fleet_service=fleet_service, api_client=api_client,
    )
    qtbot.addWidget(view)
    yield view
    with __import__("contextlib", fromlist=["suppress"]).suppress(Exception):
        view.shutdown()

class TestQtFleetTab:
    def test_creation(self, fleet_tab):
        assert fleet_tab.db is not None

    def test_kpi_cards_created(self, fleet_tab):
        assert hasattr(fleet_tab, "_kpi_cards")
        assert isinstance(fleet_tab._kpi_cards, list)

    def test_truck_table_created(self, fleet_tab):
        assert hasattr(fleet_tab, "_truck_table")

    def test_add_button_exists(self, fleet_tab):
        assert hasattr(fleet_tab, "_btn_add_truck")

    def test_import_export_buttons(self, fleet_tab):
        assert hasattr(fleet_tab, "_btn_import_csv")

    def test_shutdown_unsubscribes(self, fleet_tab):
        fleet_tab.shutdown()
        fleet_tab.ops.event_bus.unsubscribe.assert_called()

    def test_wakeup_does_not_crash(self, fleet_tab):
        fleet_tab.wakeup()

class TestTruckFormDialog:
    def test_creation(self, qt_widget, qtbot):
        db = MagicMock()
        dlg = __import__("ui.views.fleet_tab", fromlist=["_TruckFormDialog"])._TruckFormDialog(
            qt_widget, db=db,
        )
        qtbot.addWidget(dlg)

    def test_fields_present(self, qt_widget, qtbot):
        db = MagicMock()
        dlg = __import__("ui.views.fleet_tab", fromlist=["_TruckFormDialog"])._TruckFormDialog(
            qt_widget, db=db,
        )
        qtbot.addWidget(dlg)
        assert hasattr(dlg, "_plate_input")
