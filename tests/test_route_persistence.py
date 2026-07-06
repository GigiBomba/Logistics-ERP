"""Tests for RoutePersistenceService."""
from unittest.mock import MagicMock, patch

import pytest

from services.route_persistence import RoutePersistenceService
from services.route_history_service import RouteHistoryRecord


@pytest.fixture
def history_service():
    return MagicMock()


@pytest.fixture
def route_state():
    return MagicMock()


@pytest.fixture
def cost_engine():
    return MagicMock()


@pytest.fixture
def persistence(history_service, route_state, cost_engine):
    return RoutePersistenceService(
        history_service=history_service,
        route_state=route_state,
        cost_engine=cost_engine,
    )


class TestBuildRecord:
    def test_build_record_creates_history_record(self, persistence):
        route = {
            "stops": [(45.0, 24.0), (46.0, 25.0)],
            "geometry": [[45.0, 24.0], [45.5, 24.5], [46.0, 25.0]],
            "distance_km": 150.0,
            "duration_min": 120.0,
            "detected_countries": ["RO", "HU"],
        }
        truck = MagicMock()
        stops_state = [
            {"id": "s1", "type": "start", "address": "Sibiu", "resolved": True, "lat": 45.0, "lon": 24.0},
            {"id": "s2", "type": "destination", "address": "Cluj", "resolved": True, "lat": 46.0, "lon": 25.0},
        ]
        stop_addresses = {"s1": "Sibiu, Romania", "s2": "Cluj, Romania"}

        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   side_effect=lambda t, k: {"id": 1, "plate_number": "AB123CD", "model": "MAN TGX"}.get(k)):
            record = persistence.build_record(
                route=route,
                truck=truck,
                profile="fastest",
                stops_state=stops_state,
                stop_addresses=stop_addresses,
                excluded_countries=["HU"],
            )

        assert isinstance(record, RouteHistoryRecord)
        assert record.total_distance_km == 150.0
        assert record.duration_min == 120.0
        assert record.profile == "fastest"
        assert "RO" in record.countries_traversed
        assert record.truck_id == "1"
        assert record.truck_label == "AB123CD - MAN TGX"
        assert len(record.stops) == 2
        assert record.stops[0]["address"] == "Sibiu, Romania"

    def test_build_record_without_truck(self, persistence):
        route = {
            "stops": [],
            "distance_km": 100.0,
            "duration_min": 60.0,
        }
        stops_state = []
        stop_addresses = {}

        record = persistence.build_record(
            route=route, truck=None, profile="eco",
            stops_state=stops_state, stop_addresses=stop_addresses,
            excluded_countries=[],
        )

        assert record.truck_id is None
        assert record.truck_label is None

    def test_build_record_without_route_stops(self, persistence):
        route = {"distance_km": 100.0, "duration_min": 60.0}
        stops_state = [{"id": "s1", "type": "start", "address": "A"}]
        stop_addresses = {}

        record = persistence.build_record(
            route=route, truck=MagicMock(), profile="test",
            stops_state=stops_state, stop_addresses=stop_addresses,
            excluded_countries=[],
        )
        assert len(record.stops) == 1


class TestSaveCalculatedRoute:
    def test_save_calculated_route(self, persistence, history_service, route_state):
        persistence.build_record = MagicMock()
        persistence.build_record.return_value = MagicMock(spec=RouteHistoryRecord)
        history_service.save_route.return_value = 42

        route = {"stops": [], "distance_km": 100.0}
        truck = MagicMock()

        route_id = persistence.save_calculated_route(
            route=route, truck=truck, profile="fastest",
            stops_state=[], stop_addresses={},
            excluded_countries=[], cost_info={"fuel_cost": 50},
        )

        assert route_id == 42
        assert route.get("history_id") == 42
        persistence.build_record.assert_called_once()
        route_state.on_route_calculated.assert_called_once_with(42, persistence.build_record.return_value, source="route_planner")

    def test_save_calculated_route_sets_history_id(self, persistence, history_service):
        persistence.build_record = MagicMock()
        persistence.build_record.return_value = MagicMock(spec=RouteHistoryRecord)
        history_service.save_route.return_value = 99

        route = {"stops": []}
        persistence.save_calculated_route(
            route=route, truck=MagicMock(), profile="p",
            stops_state=[], stop_addresses={},
            excluded_countries=[], cost_info={},
        )
        assert route["history_id"] == 99


class TestCommitRoute:
    def test_commit_route(self, persistence, history_service):
        persistence.commit_route(route_id=42, truck_id="t1")
        history_service.commit_route.assert_called_once_with(42)
        history_service.assign_route_to_truck.assert_called_once_with(42, "t1")

    def test_commit_route_without_truck(self, persistence, history_service):
        persistence.commit_route(route_id=42)
        history_service.commit_route.assert_called_once_with(42)
        history_service.assign_route_to_truck.assert_not_called()


class TestStaticMethods:
    def test_record_to_planner_route(self):
        record = MagicMock(spec=RouteHistoryRecord)
        record.total_distance_km = 150.0
        record.duration_min = 120.0
        record.geometry = [[45.0, 24.0], [46.0, 25.0]]
        record.stops = [
            {"lat": 45.0, "lon": 24.0},
            {"lat": 46.0, "lon": 25.0},
        ]
        record.profile = "fastest"
        record.countries_traversed = ["RO"]
        record.excluded_countries = ["HU"]

        result = RoutePersistenceService.record_to_planner_route(record)
        assert result["distance_km"] == 150.0
        assert result["duration_min"] == 120.0
        assert result["profile"] == "fastest"
        assert result["cached"] is True
        assert len(result["stops"]) == 2

    def test_normalize_history_stops(self):
        record = MagicMock(spec=RouteHistoryRecord)
        record.stops = [
            {"lat": 45.0, "lon": 24.0, "address": "Sibiu"},
            {"lat": 46.0, "lon": 25.0, "address": "Cluj"},
        ]

        with patch("services.stop_factory.normalize_existing_stop",
                   side_effect=lambda s: s):
            stops = RoutePersistenceService.normalize_history_stops(record)
            assert len(stops) == 2
            assert stops[0]["type"] == "start"
            assert stops[1]["type"] == "destination"
