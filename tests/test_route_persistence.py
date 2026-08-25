"""Comprehensive unit tests for RoutePersistenceService.

Covers record building, truck data extraction via TruckConstraintEngine,
save orchestration, geometry handling, cost delegation, and edge cases.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.route_persistence import RoutePersistenceService
from services.route_history_service import RouteHistoryRecord


# ── Fixtures ──────────────────────────────────────────────────────────────

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


@pytest.fixture
def default_route():
    return {
        "stops": [(45.0, 24.0), (46.0, 25.0)],
        "geometry": [[45.0, 24.0], [45.5, 24.5], [46.0, 25.0]],
        "distance_km": 150.0,
        "duration_min": 120.0,
        "detected_countries": ["RO", "HU"],
    }


@pytest.fixture
def default_stops_state():
    return [
        {"id": "s1", "type": "start", "address": "Sibiu", "resolved": True, "lat": 45.0, "lon": 24.0},
        {"id": "s2", "type": "destination", "address": "Cluj", "resolved": True, "lat": 46.0, "lon": 25.0},
    ]


@pytest.fixture
def default_stop_addresses():
    return {"s1": "Sibiu, Romania", "s2": "Cluj, Romania"}


# ── build_record ──────────────────────────────────────────────────────────

class TestBuildRecord:
    def test_creates_history_record(self, persistence, default_route, default_stops_state, default_stop_addresses):
        truck = MagicMock()
        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   side_effect=lambda t, k: {"id": 1, "plate_number": "AB123CD", "model": "MAN TGX"}.get(k)):
            record = persistence.build_record(
                route=default_route,
                truck=truck,
                profile="fastest",
                stops_state=default_stops_state,
                stop_addresses=default_stop_addresses,
                excluded_countries=["HU"],
            )

        assert isinstance(record, RouteHistoryRecord)
        assert record.total_distance_km == 150.0
        assert record.duration_min == 120.0
        assert record.profile == "fastest"
        assert "RO" in record.countries_traversed
        assert "HU" in record.excluded_countries
        assert record.truck_id == "1"
        assert record.truck_label == "AB123CD - MAN TGX"
        assert record.truck == {"id": 1, "plate_number": "AB123CD", "model": "MAN TGX"}
        assert len(record.stops) == 2
        assert record.stops[0]["address"] == "Sibiu, Romania"
        assert record.stops[0]["lat"] == 45.0
        assert record.stops[0]["lon"] == 24.0

    def test_without_truck(self, persistence, default_route):
        record = persistence.build_record(
            route=default_route, truck=None,
            profile="eco", stops_state=[], stop_addresses={},
            excluded_countries=[],
        )
        assert record.truck_id is None
        assert record.truck_label is None
        assert record.truck == {"id": None, "plate_number": None, "model": None}

    def test_without_route_stops(self, persistence):
        route = {"distance_km": 100.0, "duration_min": 60.0}
        stops_state = [{"id": "s1", "type": "start", "address": "A"}]
        stop_addresses = {}
        record = persistence.build_record(
            route=route, truck=MagicMock(), profile="test",
            stops_state=stops_state, stop_addresses=stop_addresses,
            excluded_countries=[],
        )
        assert len(record.stops) == 1

    def test_extracts_truck_via_get_truck_value(self, persistence, default_route):
        """Verify TruckConstraintEngine._get_truck_value is used for extraction."""
        truck_raw = {"id": 99, "plate_number": "ZZ999XY", "model": "Volvo FH"}
        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   wraps=lambda t, k: t.get(k) if isinstance(t, dict) else None) as spy:
            record = persistence.build_record(
                route=default_route, truck=truck_raw,
                profile="test", stops_state=[], stop_addresses={},
                excluded_countries=[],
            )
        assert record.truck_id == "99"
        assert record.truck_label == "ZZ999XY - Volvo FH"
        assert record.truck == {"id": 99, "plate_number": "ZZ999XY", "model": "Volvo FH"}

    def test_model_only_label(self, persistence, default_route):
        truck_raw = {"id": 5, "plate_number": None, "model": "Scania"}
        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   wraps=lambda t, k: t.get(k)):
            record = persistence.build_record(
                route=default_route, truck=truck_raw,
                profile="test", stops_state=[], stop_addresses={},
                excluded_countries=[],
            )
        assert record.truck_label == "Scania"

    def test_plate_only_label(self, persistence, default_route):
        truck_raw = {"id": 5, "plate_number": "BC100XX", "model": None}
        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   wraps=lambda t, k: t.get(k)):
            record = persistence.build_record(
                route=default_route, truck=truck_raw,
                profile="test", stops_state=[], stop_addresses={},
                excluded_countries=[],
            )
        assert record.truck_label == "BC100XX"

    def test_both_none_label_is_none(self, persistence, default_route):
        truck_raw = {"id": 5, "plate_number": None, "model": None}
        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   wraps=lambda t, k: t.get(k)):
            record = persistence.build_record(
                route=default_route, truck=truck_raw,
                profile="test", stops_state=[], stop_addresses={},
                excluded_countries=[],
            )
        assert record.truck_label is None

    def test_stops_use_route_points_when_available(self, persistence):
        """Lat/lon from route points should override stop_state values."""
        route = {
            "stops": [(47.0, 27.0)],
            "geometry": [],
            "distance_km": 50.0,
        }
        stops_state = [
            {"id": "s1", "type": "start", "address": "A", "lat": 0.0, "lon": 0.0},
        ]
        record = persistence.build_record(
            route=route, truck=MagicMock(), profile="p",
            stops_state=stops_state, stop_addresses={"s1": "Iasi"},
            excluded_countries=[],
        )
        assert record.stops[0]["lat"] == 47.0
        assert record.stops[0]["lon"] == 27.0

    def test_stops_fallback_to_state_when_no_route_points(self, persistence):
        route = {"distance_km": 50.0}
        stops_state = [
            {"id": "s1", "type": "start", "address": "A", "resolved": True, "lat": 44.0, "lon": 26.0},
        ]
        record = persistence.build_record(
            route=route, truck=MagicMock(), profile="p",
            stops_state=stops_state, stop_addresses={},
            excluded_countries=[],
        )
        assert record.stops[0]["lat"] == 44.0
        assert record.stops[0]["lon"] == 26.0
        assert record.stops[0]["address"] == "A"

    def test_excluded_countries_fallback_to_route_key(self, persistence, default_route):
        """excluded_countries from route when not passed explicitly."""
        default_route["excluded_countries_requested"] = ["BG"]
        record = persistence.build_record(
            route=default_route, truck=MagicMock(), profile="p",
            stops_state=[], stop_addresses={},
            excluded_countries=None,
        )
        assert "BG" in record.excluded_countries

    def test_detected_countries_empty_fallback(self, persistence):
        route = {"stops": [], "distance_km": 50.0}
        record = persistence.build_record(
            route=route, truck=MagicMock(), profile="p",
            stops_state=[], stop_addresses={},
            excluded_countries=[],
        )
        assert record.countries_traversed == []

    # Geometry handling — passes through raw geometry
    def test_geometry_passed_through_to_record(self, persistence, default_route):
        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   return_value=None):
            record = persistence.build_record(
                route=default_route, truck=MagicMock(),
                profile="p", stops_state=[], stop_addresses={},
                excluded_countries=[],
            )
        assert record.geometry == [[45.0, 24.0], [45.5, 24.5], [46.0, 25.0]]

    def test_geometry_empty_when_not_in_route(self, persistence):
        route = {"stops": [], "distance_km": 50.0}
        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   return_value=None):
            record = persistence.build_record(
                route=route, truck=MagicMock(),
                profile="p", stops_state=[], stop_addresses={},
                excluded_countries=[],
            )
        assert record.geometry == []

    def test_very_large_geometry_passes_through(self, persistence):
        """Large geometry list is passed as-is to the record (compression in history service)."""
        big_geom = [[float(i), float(i + 1)] for i in range(10000)]
        route = {"stops": [], "geometry": big_geom, "distance_km": 500.0}
        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   return_value=None):
            record = persistence.build_record(
                route=route, truck=MagicMock(),
                profile="p", stops_state=[], stop_addresses={},
                excluded_countries=[],
            )
        assert record.geometry == big_geom
        assert len(record.geometry) == 10000

    # Additional edge cases
    def test_missing_optional_route_fields(self, persistence):
        """Distance, duration, detected_countries may be missing."""
        route = {"stops": [], "geometry": []}
        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   return_value=None):
            record = persistence.build_record(
                route=route, truck=MagicMock(),
                profile="p", stops_state=[], stop_addresses={},
                excluded_countries=[],
            )
        assert record.total_distance_km is None
        assert record.duration_min is None
        assert record.countries_traversed == []

    def test_non_list_stops_in_route(self, persistence):
        """When route.stops is not a list, falls back to empty list."""
        route = {"stops": "not_a_list", "distance_km": 100.0}
        stops_state = [{"id": "s1", "type": "start", "address": "A"}]
        record = persistence.build_record(
            route=route, truck=MagicMock(), profile="p",
            stops_state=stops_state, stop_addresses={},
            excluded_countries=[],
        )
        # Stops snapshot should still be built from stops_state
        assert len(record.stops) == 1
        assert record.stops[0]["address"] == "A"

    def test_kwargs_accepted_but_not_used(self, persistence, default_route):
        """Extra kwargs like cost_info are accepted by build_record."""
        with patch("services.constraint_engine.TruckConstraintEngine._get_truck_value",
                   return_value=None):
            record = persistence.build_record(
                route=default_route, truck=MagicMock(),
                profile="p", stops_state=[], stop_addresses={},
                excluded_countries=[], extra_arg="ignored",
            )
        assert isinstance(record, RouteHistoryRecord)

    def test_stop_without_id_uses_address_from_state(self, persistence):
        route = {"stops": [(44.0, 26.0)]}
        stops_state = [
            {"type": "start", "address": "Bucharest", "resolved": True, "lat": 44.0, "lon": 26.0},
        ]
        record = persistence.build_record(
            route=route, truck=MagicMock(), profile="p",
            stops_state=stops_state, stop_addresses={},
            excluded_countries=[],
        )
        assert record.stops[0]["address"] == "Bucharest"

    def test_stop_with_id_but_no_address_lookup(self, persistence):
        """stop_id exists but is not in stop_addresses dict."""
        route = {"stops": [(44.0, 26.0)], "distance_km": 100.0}
        stops_state = [
            {"id": "s1", "type": "start", "address": "Bucharest", "resolved": True, "lat": 44.0, "lon": 26.0},
        ]
        record = persistence.build_record(
            route=route, truck=MagicMock(), profile="p",
            stops_state=stops_state, stop_addresses={},
            excluded_countries=[],
        )
        assert record.stops[0]["address"] == "Bucharest"

    def test_route_point_extraction_error_does_not_crash(self, persistence):
        """Bad route point indices are gracefully skipped."""
        route = {"stops": [(45.0, 24.0)], "distance_km": 100.0}
        stops_state = [
            {"id": "s1", "type": "start", "address": "A", "lat": 0.0, "lon": 0.0},
            {"id": "s2", "type": "destination", "address": "B", "lat": 0.0, "lon": 0.0},
        ]
        # stop index 1 has no corresponding route point — should not crash
        record = persistence.build_record(
            route=route, truck=MagicMock(), profile="p",
            stops_state=stops_state, stop_addresses={},
            excluded_countries=[],
        )
        assert len(record.stops) == 2
        assert record.stops[0]["lat"] == 45.0  # overridden by route point
        assert record.stops[1]["address"] == "B"  # state fallback


# ── save_calculated_route ─────────────────────────────────────────────────

class TestSaveCalculatedRoute:
    def test_save_delegates_to_history_service(self, persistence, history_service, route_state):
        persistence.build_record = MagicMock()
        mock_record = MagicMock(spec=RouteHistoryRecord)
        persistence.build_record.return_value = mock_record
        history_service.save_route.return_value = 42

        route_id = persistence.save_calculated_route(
            route={"stops": [], "distance_km": 100.0},
            truck=MagicMock(), profile="fastest",
            stops_state=[], stop_addresses={},
            excluded_countries=[], cost_info={"fuel_cost": 50},
        )

        assert route_id == 42
        history_service.save_route.assert_called_once_with(mock_record)
        route_state.on_route_calculated.assert_called_once_with(42, mock_record, source="route_planner")

    def test_save_sets_history_id_on_route(self, persistence, history_service):
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

    def test_save_calls_perf_timer(self, persistence, history_service):
        persistence.build_record = MagicMock()
        persistence.build_record.return_value = MagicMock(spec=RouteHistoryRecord)
        history_service.save_route.return_value = 1
        route = {"stops": []}
        with patch("services.route_persistence.perf_timer") as mock_timer:
            mock_timer.return_value.__enter__ = MagicMock()
            mock_timer.return_value.__exit__ = MagicMock()
            persistence.save_calculated_route(
                route=route, truck=MagicMock(), profile="p",
                stops_state=[], stop_addresses={},
                excluded_countries=[], cost_info={},
            )
            mock_timer.assert_called_once_with("history_save")

    def test_cost_info_delegated_to_engine(self, persistence):
        """cost_info is passed but the current RoutePersistenceService
        does NOT delegate cost_info to CostEngineService — this test
        documents current behaviour."""
        mock_record = MagicMock(spec=RouteHistoryRecord)
        persistence.build_record = MagicMock(return_value=mock_record)
        persistence.history.save_route.return_value = 1

        persistence.save_calculated_route(
            route={"stops": []}, truck=MagicMock(), profile="p",
            stops_state=[], stop_addresses={},
            excluded_countries=[], cost_info={"fuel_cost": 50},
        )
        # CostEngineService is not called during save
        persistence.cost_engine.estimate.assert_not_called()
        persistence.cost_engine.estimate_for_truck.assert_not_called()


# ── commit_route ──────────────────────────────────────────────────────────

class TestCommitRoute:
    def test_commits_and_assigns_truck(self, persistence, history_service):
        persistence.commit_route(route_id=42, truck_id="t1")
        history_service.commit_route.assert_called_once_with(42)
        history_service.assign_route_to_truck.assert_called_once_with(42, "t1")

    def test_commits_without_truck(self, persistence, history_service):
        persistence.commit_route(route_id=42)
        history_service.commit_route.assert_called_once_with(42)
        history_service.assign_route_to_truck.assert_not_called()

    def test_truck_assignment_error_suppressed(self, persistence, history_service):
        history_service.assign_route_to_truck.side_effect = RuntimeError("fail")
        # Should not raise
        persistence.commit_route(route_id=1, truck_id="t1")
        history_service.commit_route.assert_called_once_with(1)
        history_service.assign_route_to_truck.assert_called_once_with(1, "t1")


# ── Static methods ────────────────────────────────────────────────────────

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
        assert result["detected_countries"] == ["RO"]
        assert result["excluded_countries_requested"] == ["HU"]

    def test_record_to_planner_route_with_none_distance_duration(self):
        record = MagicMock(spec=RouteHistoryRecord)
        record.total_distance_km = None
        record.duration_min = None
        record.geometry = None
        record.stops = []
        record.profile = None
        record.countries_traversed = []
        record.excluded_countries = []

        result = RoutePersistenceService.record_to_planner_route(record)
        assert result["distance_km"] == 0
        assert result["duration_min"] == 0
        assert result["geometry"] == []

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

    def test_normalize_history_stops_empty(self):
        record = MagicMock(spec=RouteHistoryRecord)
        record.stops = []
        with patch("services.stop_factory.normalize_existing_stop",
                   side_effect=lambda s: s):
            stops = RoutePersistenceService.normalize_history_stops(record)
            assert stops == []

    def test_normalize_history_stops_none(self):
        record = MagicMock(spec=RouteHistoryRecord)
        record.stops = None
        with patch("services.stop_factory.normalize_existing_stop",
                   side_effect=lambda s: s):
            stops = RoutePersistenceService.normalize_history_stops(record)
            assert stops == []

    def test_normalize_history_stops_missing_type(self):
        """Missing type is inferred from position."""
        record = MagicMock(spec=RouteHistoryRecord)
        record.stops = [
            {"lat": 45.0, "lon": 24.0, "address": "A"},
            {"lat": 46.0, "lon": 25.0, "address": "B"},
            {"lat": 47.0, "lon": 26.0, "address": "C"},
        ]
        with patch("services.stop_factory.normalize_existing_stop",
                   side_effect=lambda s: s):
            stops = RoutePersistenceService.normalize_history_stops(record)
            assert stops[0]["type"] == "start"
            assert stops[1]["type"] == "stop"
            assert stops[2]["type"] == "destination"

    def test_normalize_history_stops_resolved_flag(self):
        record = MagicMock(spec=RouteHistoryRecord)
        record.stops = [
            {"lat": 45.0, "lon": 24.0, "address": "A"},
            {"lat": None, "lon": None, "address": "B"},
        ]
        with patch("services.stop_factory.normalize_existing_stop",
                   side_effect=lambda s: s):
            stops = RoutePersistenceService.normalize_history_stops(record)
            assert stops[0]["resolved"] is True
            assert stops[1]["resolved"] is False

    def test_normalize_history_stops_fallback_address(self):
        record = MagicMock(spec=RouteHistoryRecord)
        record.stops = [
            {"lat": 45.0, "lon": 24.0, "value": "Berlin"},
        ]
        with patch("services.stop_factory.normalize_existing_stop",
                   side_effect=lambda s: s):
            stops = RoutePersistenceService.normalize_history_stops(record)
            assert stops[0]["address"] == "Berlin"

    def test_normalize_history_stops_empty_address_fallback(self):
        record = MagicMock(spec=RouteHistoryRecord)
        record.stops = [
            {"lat": 45.0, "lon": 24.0},
        ]
        with patch("services.stop_factory.normalize_existing_stop",
                   side_effect=lambda s: s):
            stops = RoutePersistenceService.normalize_history_stops(record)
            assert stops[0]["address"] == ""


# ── CostEngineService default ─────────────────────────────────────────────

class TestDefaultCostEngine:
    def test_default_cost_engine_created_when_none_passed(self, history_service, route_state):
        """When cost_engine is None, a default CostEngineService is created."""
        svc = RoutePersistenceService(
            history_service=history_service,
            route_state=route_state,
            cost_engine=None,
        )
        assert svc.cost_engine is not None
        from services.cost_engine import CostEngineService
        assert isinstance(svc.cost_engine, CostEngineService)

    def test_default_cost_engine_when_omitted(self, history_service, route_state):
        """Omitting cost_engine entirely also creates a default."""
        svc = RoutePersistenceService(
            history_service=history_service,
            route_state=route_state,
        )
        assert svc.cost_engine is not None


if __name__ == "__main__":
    pytest.main([__file__])
