"""Tests for TripContext module."""
from unittest.mock import MagicMock, patch

import pytest

from services.trip_context import (
    TripContext,
    TripContextService,
    RouteModel,
    TruckModel,
    DriverModel,
    CostsModel,
    ProfitModel,
    update_trip_route,
    update_trip_truck,
    update_trip_driver,
    update_trip_revenue,
    save_trip_to_db,
    load_trip_from_db,
    register_trip_listener,
    unregister_trip_listener,
    _compute_costs_for_tc,
    _compute_profit_for_tc,
    _notify_listeners,
)


def test_trip_context_create_default():
    tc = TripContext.create()
    assert tc.status == "draft"
    assert tc.trip_id is not None
    assert isinstance(tc.route, RouteModel)
    assert isinstance(tc.truck, TruckModel)


def test_trip_context_create_with_id():
    tc = TripContext.create("my-trip-1")
    assert tc.trip_id == "my-trip-1"


def test_trip_context_to_dict():
    tc = TripContext.create("test-1")
    d = tc.to_dict()
    assert d["trip_id"] == "test-1"
    assert d["status"] == "draft"
    assert "route" in d


def test_trip_context_from_dict():
    data = {
        "trip_id": "test-1",
        "route": {"distance_km": 500},
        "truck": {"name": "Truck1", "fuel_consumption_l_per_100km": 30},
        "driver": {"name": "John"},
        "costs": {"fuel_liters": 150},
        "profit": {"revenue_estimate": 1000},
        "status": "active",
    }
    tc = TripContext.from_dict(data)
    assert tc.trip_id == "test-1"
    assert tc.route.distance_km == 500
    assert tc.truck.fuel_consumption_l_per_100km == 30
    assert tc.driver.name == "John"
    assert tc.costs.fuel_liters == 150
    assert tc.profit.revenue_estimate == 1000
    assert tc.status == "active"


def test_set_route():
    tc = TripContext.create()
    tc.set_route({"distance_km": 300, "duration_min": 240})
    assert tc.route.distance_km == 300
    assert tc.route.duration_min == 240


def test_set_truck():
    tc = TripContext.create()
    tc.set_truck({"id": "1", "name": "Truck1", "fuel_consumption_l_per_100km": 30})
    assert tc.truck.name == "Truck1"
    assert tc.truck.fuel_consumption_l_per_100km == 30


def test_set_driver():
    tc = TripContext.create()
    tc.set_driver({"id": "1", "name": "John"})
    assert tc.driver.name == "John"


def test_set_costs():
    tc = TripContext.create()
    tc.set_costs({"fuel_liters": 150, "fuel_cost": 225, "toll_cost": 50})
    assert tc.costs.fuel_liters == 150


def test_set_profit():
    tc = TripContext.create()
    tc.set_profit({"revenue_estimate": 1000, "total_cost": 500, "net_profit": 500})
    assert tc.profit.net_profit == 500


def test_mark_status():
    tc = TripContext.create()
    assert tc.status == "draft"
    tc.mark_active()
    assert tc.status == "active"
    tc.mark_saved()
    assert tc.status == "saved"
    tc.mark_draft()
    assert tc.status == "draft"


def test_update_trip_route_invalid():
    tc = TripContext.create()
    with pytest.raises(ValueError):
        update_trip_route(tc, "not_a_dict")


def test_update_trip_truck_invalid():
    tc = TripContext.create()
    with pytest.raises(ValueError):
        update_trip_truck(tc, "not_a_dict")


def test_update_trip_driver_invalid():
    tc = TripContext.create()
    with pytest.raises(ValueError):
        update_trip_driver(tc, "not_a_dict")


def test_compute_costs_no_distance():
    tc = TripContext.create()
    tc.route.distance_km = None
    tc.truck.fuel_consumption_l_per_100km = 30
    _compute_costs_for_tc(tc)
    assert tc.costs.fuel_liters is None


def test_compute_costs_no_consumption():
    tc = TripContext.create()
    tc.route.distance_km = 100
    tc.truck.fuel_consumption_l_per_100km = None
    _compute_costs_for_tc(tc)
    assert tc.costs.fuel_liters is None


@patch("services.trip_context._get_fuel_price_service")
def test_compute_costs_full(mock_get_fps):
    mock_fps = MagicMock()
    mock_fps.get_price.return_value = 1.5
    mock_get_fps.return_value = mock_fps
    tc = TripContext.create()
    tc.route.distance_km = 100
    tc.truck.fuel_consumption_l_per_100km = 30
    _compute_costs_for_tc(tc)
    assert tc.costs.fuel_liters == pytest.approx(30.0)
    assert tc.costs.fuel_cost == pytest.approx(45.0)
    assert tc.costs.toll_cost == pytest.approx(5.0)


def test_compute_profit_no_revenue():
    tc = TripContext.create()
    tc.costs = CostsModel(fuel_cost=100, toll_cost=50)
    tc.profit.revenue_estimate = None
    _compute_profit_for_tc(tc)
    assert tc.profit.total_cost == 150
    assert tc.profit.net_profit is None


def test_compute_profit_with_revenue():
    tc = TripContext.create()
    tc.costs = CostsModel(fuel_cost=100, toll_cost=50)
    tc.profit.revenue_estimate = 500
    _compute_profit_for_tc(tc)
    assert tc.profit.total_cost == 150
    assert tc.profit.net_profit == 350


def test_compute_profit_no_costs():
    tc = TripContext.create()
    tc.costs = CostsModel(fuel_liters=None, fuel_cost=None, toll_cost=None)
    tc.profit.revenue_estimate = 500
    _compute_profit_for_tc(tc)
    assert tc.profit.total_cost is None


def test_update_trip_revenue():
    tc = TripContext.create()
    tc.costs = CostsModel(fuel_cost=100, toll_cost=50)
    update_trip_revenue(tc, 1000)
    assert tc.profit.revenue_estimate == 1000
    assert tc.profit.net_profit == 850


def test_update_trip_revenue_none():
    tc = TripContext.create()
    tc.costs = CostsModel(fuel_cost=100, toll_cost=50)
    update_trip_revenue(tc, None)
    assert tc.profit.revenue_estimate is None


def test_save_trip_to_db():
    db_mock = MagicMock()
    db_mock.add_trip.return_value = 42
    tc = TripContext.create("test-1")
    tc.route.distance_km = 500
    tc.truck.name = "Truck1"
    tc.driver.name = "John"
    tc.profit.revenue_estimate = 1000
    result = save_trip_to_db(db_mock, tc, client_name="Client1")
    assert result == 42
    db_mock.add_trip.assert_called_once()
    payload = db_mock.add_trip.call_args[0][0]
    assert payload["truck_number"] == "Truck1"
    assert payload["distance_km"] == 500


def test_save_trip_to_db_none():
    with pytest.raises(ValueError):
        save_trip_to_db(MagicMock(), None)


def test_load_trip_from_db():
    db_mock = MagicMock()
    db_mock.get_trip_by_id.return_value = {
        "context_json": '{"trip_id": "test-1", "status": "saved"}',
        "status": "saved",
    }
    tc = load_trip_from_db(db_mock, 42)
    assert tc is not None
    assert tc.trip_id == "test-1"


def test_load_trip_from_db_not_found():
    db_mock = MagicMock()
    db_mock.get_trip_by_id.return_value = None
    assert load_trip_from_db(db_mock, 999) is None


def test_load_trip_from_db_no_json():
    db_mock = MagicMock()
    db_mock.get_trip_by_id.return_value = {
        "context_json": None,
        "distance_km": 100,
        "truck_number": "Truck1",
        "driver_name": "John",
        "status": "saved",
    }
    tc = load_trip_from_db(db_mock, 42)
    assert tc is not None
    assert tc.route.distance_km == 100


def test_listeners():
    calls = []
    def listener(tc, fields):
        calls.append((tc.trip_id, fields))

    register_trip_listener(listener)
    tc = TripContext.create("test-1")
    _notify_listeners(tc, ["test"])
    assert len(calls) == 1
    assert calls[0] == ("test-1", ["test"])

    unregister_trip_listener(listener)
    _notify_listeners(tc, ["test"])
    assert len(calls) == 1


def test_trip_context_service_singleton():
    svc1 = TripContextService()
    svc2 = TripContextService()
    assert svc1 is svc2


def test_trip_context_service_defaults():
    svc = TripContextService()
    info = svc.get_active_trip_info()
    assert info["distance_km"] == 0.0
    assert info["fuel_cost"] == 0.0


def test_set_active_trip_info():
    svc = TripContextService()
    svc.set_active_trip_info(distance_km=500, fuel_cost=150)
    info = svc.get_active_trip_info()
    assert info["distance_km"] == 500
    assert info["fuel_cost"] == 150
