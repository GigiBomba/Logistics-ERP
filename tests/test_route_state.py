"""Tests for RouteStateManager."""
from unittest.mock import MagicMock, patch

import pytest

from services.route_state import RouteStateManager, ActiveRouteState


@pytest.fixture(autouse=True)
def mock_history_service():
    """Replace RouteHistoryService with a MagicMock so tests can set return values."""
    with patch("services.route_state.RouteHistoryService") as m_cls:
        instance = MagicMock()
        m_cls.return_value = instance
        yield instance


@pytest.fixture
def db_mock():
    return MagicMock()


def test_route_state_manager_singleton(db_mock):
    m1 = RouteStateManager(db_mock)
    m2 = RouteStateManager(db_mock)
    assert m1 is m2


def test_init_sets_up_services(db_mock):
    manager = RouteStateManager(db_mock)
    assert manager.history is not None
    assert manager.trip_context is not None
    assert manager._state == ActiveRouteState()


def test_get_active_route_empty(db_mock):
    manager = RouteStateManager(db_mock)
    manager.history.get_active_route_id.return_value = None
    state = manager.get_active_route()
    assert state.route_id is None


def test_get_active_route_loads_from_db(db_mock):
    manager = RouteStateManager(db_mock)
    manager._state = ActiveRouteState()  # empty
    manager.history.get_active_route_id.return_value = 5
    manager.history.load_route.return_value = MagicMock(
        truck_id=1, total_distance_km=500, duration_min=240, profile="truck",
        countries_traversed=["RO", "HU"],
    )
    state = manager.get_active_route()
    assert state.route_id == 5


def test_set_active_route(db_mock):
    manager = RouteStateManager(db_mock)
    route_mock = MagicMock(truck_id=1, total_distance_km=300)
    manager.history.load_route.return_value = route_mock
    manager.trip_context = MagicMock()
    result = manager.set_active_route(5, source="test")
    assert result is route_mock
    manager.history.set_active_route.assert_called_with(5)
    manager.trip_context.set_active_trip_info.assert_called()


def test_set_active_route_not_found(db_mock):
    manager = RouteStateManager(db_mock)
    manager.history.load_route.return_value = None
    result = manager.set_active_route(999)
    assert result is None


def test_on_route_calculated(db_mock):
    manager = RouteStateManager(db_mock)
    route_mock = MagicMock(truck_id=1, total_distance_km=500, duration_min=240)
    manager.history = MagicMock()
    manager.trip_context = MagicMock()
    manager.on_route_calculated(5, route_mock, source="test")
    assert manager._state.route_id == 5
    manager.history.set_active_route.assert_called_with(5)
    manager.history.assign_route_to_truck.assert_called()
    manager.trip_context.set_active_trip_info.assert_called()


def test_on_route_calculated_no_truck(db_mock):
    manager = RouteStateManager(db_mock)
    route_mock = MagicMock(truck_id=None, total_distance_km=500)
    manager.history = MagicMock()
    manager.trip_context = MagicMock()
    manager.on_route_calculated(5, route_mock)
    # Should not call assign_route_to_truck
    assert not manager.history.assign_route_to_truck.called


def test_complete_active_route(db_mock):
    manager = RouteStateManager(db_mock)
    manager._state = ActiveRouteState(route_id=5, route=MagicMock())
    manager.history.complete_route.return_value = True
    result = manager.complete_active_route()
    assert result is True
    manager.history.complete_route.assert_called_with(5)


def test_complete_active_route_no_state(db_mock):
    manager = RouteStateManager(db_mock)
    manager.history.get_active_route_id.return_value = None
    result = manager.complete_active_route()
    assert result is False


def test_archive_route(db_mock):
    manager = RouteStateManager(db_mock)
    manager._state = ActiveRouteState(route_id=5)
    manager.history.archive_route.return_value = True
    result = manager.archive_route(5)
    assert result is True
    assert manager._state.route_id is None


def test_tracking_snapshot(db_mock):
    manager = RouteStateManager(db_mock)
    route_mock = MagicMock(
        truck_id=1, profile="truck", total_distance_km=500,
        duration_min=240, countries_traversed=["RO", "HU"],
    )
    manager._state = ActiveRouteState(route_id=5, route=route_mock)
    snapshot = manager.tracking_snapshot()
    assert snapshot["active_route_id"] == 5
    assert snapshot["truck_id"] == 1


def test_tracking_snapshot_empty(db_mock):
    manager = RouteStateManager(db_mock)
    manager.history.get_active_route_id.return_value = None
    snapshot = manager.tracking_snapshot()
    assert snapshot["active_route_id"] is None


def test_subscribe_unsubscribe(db_mock):
    manager = RouteStateManager(db_mock)
    with patch("services.route_state.RouteEventBus") as mock_bus:
        cb = lambda: None
        manager.subscribe("test_event", cb)
        mock_bus.subscribe.assert_called_with("test_event", cb)
        manager.unsubscribe("test_event", cb)
        mock_bus.unsubscribe.assert_called_with("test_event", cb)


def test_get_active_route_returns_cached_state(db_mock):
    """When _state already has route_id and route, it should return directly."""
    manager = RouteStateManager(db_mock)
    route_mock = MagicMock(truck_id=1)
    manager._state = ActiveRouteState(route_id=5, route=route_mock)
    state = manager.get_active_route()
    assert state.route_id == 5
    assert state.route is route_mock
    # Should NOT call DB
    manager.history.get_active_route_id.assert_not_called()


def test_on_route_calculated_emits_event(db_mock):
    manager = RouteStateManager(db_mock)
    route_mock = MagicMock(truck_id=1, total_distance_km=500, duration_min=240)
    manager.history = MagicMock()
    manager.trip_context = MagicMock()
    manager.on_route_calculated(10, route_mock, source="planner")
    manager.history.record_event.assert_called_once_with(
        10, "route_calculated", {"source": "planner"},
    )


def test_complete_active_route_emits_event(db_mock):
    manager = RouteStateManager(db_mock)
    manager._state = ActiveRouteState(route_id=5, route=MagicMock())
    manager.history.complete_route.return_value = True
    result = manager.complete_active_route()
    assert result is True
    manager.history.record_event.assert_called_with(
        5, "route_completed", {"source": "route_state"},
    )


def test_archive_route_different_id_does_not_clear_state(db_mock):
    """Archiving a different route should not clear the active state."""
    manager = RouteStateManager(db_mock)
    manager._state = ActiveRouteState(route_id=5, route=MagicMock())
    manager.history.archive_route.return_value = True
    result = manager.archive_route(10)
    assert result is True
    assert manager._state.route_id == 5  # unchanged


def test_sync_to_trip_context_delegates(db_mock):
    manager = RouteStateManager(db_mock)
    manager._state = ActiveRouteState(route_id=5, route=MagicMock())
    route_mock = MagicMock(total_distance_km=200, duration_min=90)
    manager.trip_context = MagicMock()
    manager.sync_to_trip_context(route_mock)
    manager.trip_context.set_active_trip_info.assert_called_with(
        distance_km=200, duration_min=90, route_history_v2_id=5,
    )
