"""Tests for the PySide6 profit calculator view."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ui.views.calculator_view import QtCalculatorView


@pytest.fixture
def calc_view(qt_widget, qtbot, monkeypatch):
    fleet = MagicMock()
    fleet.get_trucks.return_value = [
        {
            "id": 1, "plate_number": "B-123-ABC", "model": "Volvo",
            "fuel_consumption": 30.0, "driver_id": 5, "driver_name": "John",
        },
    ]
    trip = MagicMock()
    trip.add.return_value = 42
    client = MagicMock()
    client.get_or_create.return_value = 7
    prefs = MagicMock()
    prefs.get_currency.return_value = "EUR"
    fuel = MagicMock()
    fuel.get_price.return_value = 1.50
    api = MagicMock()
    api.get_rates.return_value = {"EUR": 1.0}

    monkeypatch.setattr("ui.views.calculator_view.Toast.show_success", lambda *a, **k: None)

    view = QtCalculatorView(
        qt_widget,
        db=None,
        fleet_service=fleet,
        trip_service=trip,
        client_service=client,
        prefs=prefs,
        ops=None,
        fuel_service=fuel,
        api=api,
    )
    qtbot.addWidget(view)
    yield view
    try:
        view.shutdown()
    except Exception:
        pass


class TestQtCalculatorView:
    def test_creation(self, calc_view):
        assert calc_view.calculate_btn is not None
        assert calc_view.l_res is not None

    def test_truck_dropdown_populated(self, calc_view):
        assert calc_view.truck_combo.count() == 1
        assert "B-123-ABC" in calc_view.truck_combo.currentText()
        assert calc_view._selected_truck_fuel == 30.0

    def test_vat_toggle_shows_fields(self, calc_view, qtbot):
        calc_view.show()
        qtbot.waitForWindowShown(calc_view)
        calc_view._vat_check.setChecked(True)
        qtbot.wait(50)
        assert not calc_view._vat_fields_frame.isHidden()
        calc_view._vat_check.setChecked(False)
        qtbot.wait(50)
        assert calc_view._vat_fields_frame.isHidden()

    def test_vat_fields_update(self, calc_view):
        calc_view.e_price.setText("1000")
        calc_view._vat_percent.setText("19")
        calc_view._vat_check.setChecked(True)
        calc_view._update_vat_fields()
        assert calc_view._e_price_post.text() == "1190.00"

    def test_calculate_displays_result(self, calc_view, qtbot, monkeypatch):
        monkeypatch.setattr("ui.views.calculator_view.QMessageBox", MagicMock())
        calc_view._route_distance = 500.0
        calc_view.e_price.setText("1000")
        calc_view.e_days.setText("1")
        calc_view.e_sal.setText("100")
        calc_view.e_extra.setText("50")
        calc_view._on_truck_selected(0)

        calc_view._handle_calculate()

        assert "Net" in calc_view.l_res.text() or calc_view.l_res.text() != ""
        assert calc_view.l_res.styleSheet() != ""

    def test_calculate_saves_trip(self, calc_view, qtbot, monkeypatch):
        monkeypatch.setattr("ui.views.calculator_view.QMessageBox", MagicMock())
        calc_view._route_distance = 500.0
        calc_view.e_price.setText("1000")
        calc_view.e_days.setText("1")
        calc_view.e_sal.setText("100")
        calc_view.e_extra.setText("50")
        calc_view.e_client.setText("ACME")
        calc_view._on_truck_selected(0)

        calc_view._handle_calculate()

        assert calc_view.trip_service.add.called
        args = calc_view.trip_service.add.call_args[0][0]
        assert args["client_name"] == "ACME"
        assert args["distance_km"] == 500.0

    def test_trip_context_sync(self, calc_view, qtbot):
        calc_view._truck_map = {"1": {"id": 1, "plate_number": "B-123-ABC", "fuel_consumption": 30.0}}
        calc_view.truck_combo.clear()
        calc_view.truck_combo.addItem("B-123-ABC", "1")

        class FakeRoute:
            distance_km = 750.0
            route_history_v2_id = 99

        class FakeCosts:
            fuel_liters = 200.0
            toll_cost = 100.0

        class FakeTruck:
            id = "1"

        class FakeTC:
            route = FakeRoute()
            costs = FakeCosts()
            truck = FakeTruck()

        calc_view._apply_trip_context(FakeTC(), ["route", "costs", "truck"])
        assert calc_view._route_distance == 750.0
        assert calc_view._current_route_history_id == 99
        assert calc_view._route_fuel_liters == 200.0
        assert calc_view._route_toll == 100.0
