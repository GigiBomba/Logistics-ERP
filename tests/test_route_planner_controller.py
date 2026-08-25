"""Tests for RoutePlannerController."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.route_planner_controller import (
    ProcessedRouteResult,
    RouteCalculationContext,
    RoutePlannerController,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def controller(mock_db):
    with patch("services.route_planner_controller.RouteService"), \
         patch("services.route_planner_controller.CountryAvoidanceManager"), \
         patch("services.route_planner_controller.CostEngineService"), \
         patch("services.route_planner_controller.TripContextService"), \
         patch("services.route_planner_controller.RouteComplianceAnalyzer"), \
         patch("services.route_planner_controller.RouteRunner"):
        ctrl = RoutePlannerController(mock_db)
        return ctrl


class TestValidateInput:
    def test_validate_missing_truck(self, controller):
        ctx, err = controller.validate_calculation_input(
            truck_id="", trucks_map={}, profile_label="Fastest",
            stops_state=[], row_addresses=[],
        )
        assert ctx is None
        assert err is not None

    def test_validate_invalid_truck(self, controller):
        ctx, err = controller.validate_calculation_input(
            truck_id="999", trucks_map={"1": {"id": 1}}, profile_label="Fastest",
            stops_state=[], row_addresses=[],
        )
        assert ctx is None
        assert err is not None

    def test_validate_empty_stop(self, controller):
        ctx, err = controller.validate_calculation_input(
            truck_id="1", trucks_map={"1": {"id": 1}},
            profile_label="Fastest",
            stops_state=[{"address": ""}],
            row_addresses=[(0, "")],
        )
        assert ctx is None
        assert err is not None

    def test_validate_less_than_2_stops(self, controller):
        ctx, err = controller.validate_calculation_input(
            truck_id="1", trucks_map={"1": {"id": 1}},
            profile_label="Fastest",
            stops_state=[{"address": "Sibiu"}],
            row_addresses=[(0, "Sibiu")],
        )
        assert ctx is None
        assert err is not None

    def test_validate_success(self, controller):
        controller.get_excluded_countries = MagicMock(return_value=[])
        with patch("services.route_planner_controller.gh_profile_for_ui_label",
                   return_value="fastest"):
            ctx, err = controller.validate_calculation_input(
                truck_id="1",
                trucks_map={"1": {"id": 1, "plate_number": "AB123CD"}},
                profile_label="Fastest",
                stops_state=[{"address": "Sibiu"}, {"address": "Cluj"}],
                row_addresses=[(0, "Sibiu"), (1, "Cluj")],
            )
            assert err is None
            assert isinstance(ctx, RouteCalculationContext)
            assert ctx.truck["id"] == 1
            assert ctx.profile == "fastest"


class TestStartCancelCalculation:
    def test_start_calculation_calls_runner(self, controller):
        ctx = RouteCalculationContext(
            truck={"id": 1}, profile="fastest",
            stops_state=[{"address": "Sibiu"}, {"address": "Cluj"}],
            excluded_countries=[],
        )
        callback = MagicMock()

        controller.start_calculation(ctx, callback)
        controller._runner.run_route_async.assert_called_once_with(
            route_service=controller.route_service,
            stops_state=ctx.stops_state,
            truck=ctx.truck,
            profile=ctx.profile,
            callback=callback,
            geocode_cache=controller.geocode_cache,
            avoid_countries=[],
        )

    def test_cancel_calculation(self, controller):
        controller.cancel_calculation()
        controller._runner.cancel.assert_called_once()


class TestProcessResult:
    def test_process_calculation_result_error(self, controller):
        ctx = RouteCalculationContext(
            truck={"id": 1}, profile="fastest",
            stops_state=[], excluded_countries=[],
        )
        result = {"error": "timeout", "error_type": "timeout"}
        processed, err = controller.process_calculation_result(result, ctx, {})
        assert processed is None
        assert err is not None

    def test_process_calculation_result_success(self, controller):
        ctx = RouteCalculationContext(
            truck={"id": 1, "plate_number": "AB123CD", "fuel_consumption": 30},
            profile="fastest",
            stops_state=[{"address": "A"}, {"address": "B"}],
            excluded_countries=[],
        )
        result = [{"distance_km": 150.0, "duration_min": 120.0}]

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = MagicMock()
        mock_result.data.model_dump.return_value = {"fuel_liters": 50, "fuel_cost": 100}
        controller.cost_engine.estimate.return_value = mock_result
        controller.compliance.analyze.return_value = MagicMock()
        controller._truck_cost_payload = MagicMock(return_value={"id": 1})
        controller._sync_trip_context = MagicMock()

        with patch("services.route_planner_controller.format_success_info",
                   return_value="Info text"):
            processed, err = controller.process_calculation_result(result, ctx, {})

            assert err is None
            assert isinstance(processed, ProcessedRouteResult)
            assert processed.route["distance_km"] == 150.0

    def test_process_calculation_result_saves_persistence(self, controller):
        ctx = RouteCalculationContext(
            truck={"id": 1, "plate_number": "AB123CD", "fuel_consumption": 30},
            profile="fastest",
            stops_state=[{"id": "s1"}, {"id": "s2"}],
            excluded_countries=[],
        )
        result = [{"distance_km": 200.0, "duration_min": 180.0}]

        mock_persistence = MagicMock()
        controller._persistence = mock_persistence
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = MagicMock()
        mock_result.data.model_dump.return_value = {"fuel_liters": 60}
        controller.cost_engine.estimate.return_value = mock_result
        controller.compliance.analyze.return_value = MagicMock()
        controller._truck_cost_payload = MagicMock(return_value={"id": 1})
        controller._sync_trip_context = MagicMock()

        processed, err = controller.process_calculation_result(
            result, ctx, {"s1": "address1", "s2": "address2"},
        )
        mock_persistence.save_calculated_route.assert_called_once()


class TestCommitDiscard:
    def test_commit_route(self, controller):
        mock_persistence = MagicMock()
        controller._persistence = mock_persistence
        controller.commit_route(42, truck_id="t1")
        mock_persistence.commit_route.assert_called_once_with(42, truck_id="t1")

    def test_commit_route_no_persistence(self, controller):
        controller.commit_route(42)  # should not raise

    def test_discard_route(self, controller):
        mock_persistence = MagicMock()
        controller._persistence = mock_persistence
        controller.discard_route(42)
        mock_persistence.history.discard_route.assert_called_once_with(42)


class TestEstimateCost:
    def test_estimate_cost(self, controller):
        truck = MagicMock()
        controller._truck_cost_payload = MagicMock(return_value={"id": 1, "fuel_consumption_l_per_100km": 30})
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = MagicMock()
        mock_result.data.model_dump.return_value = {"fuel_liters": 50}
        controller.cost_engine.estimate.return_value = mock_result
        result = controller.estimate_cost(truck, 200.0)
        # Verify estimate was called with a CostEstimateRequest
        from models.cost_models import CostEstimateRequest
        controller.cost_engine.estimate.assert_called_once()
        args, _ = controller.cost_engine.estimate.call_args
        assert isinstance(args[0], CostEstimateRequest)
        assert args[0].distance_km == 200.0


class TestLoadHistory:
    def test_load_history_record(self, controller):
        record = MagicMock()
        record.stops = [{"lat": 45.0, "lon": 24.0}]
        record.profile = "fastest"
        record.truck_id = "1"
        record.excluded_countries = ["HU"]
        record.total_distance_km = 100.0
        record.duration_min = 60.0
        record.geometry = []
        record.countries_traversed = []

        with patch("services.route_planner_controller.RoutePersistenceService.normalize_history_stops",
                   return_value=[]), \
             patch("services.route_planner_controller.RoutePersistenceService.record_to_planner_route",
                   return_value={}), \
             patch("services.route_profiles.ui_label_for_profile",
                   return_value="Fastest"):
            result = controller.load_history_record(record)
            assert "stops" in result
            assert "profile_label" in result
            assert result["profile_label"] == "Fastest"


class TestLoadFromUrl:
    def test_load_from_url_valid(self, controller):
        with patch("services.route_sharing_service.parse_share_url",
                   return_value={
                       "stops": [(45.0, 24.0), (46.0, 25.0)],
                       "profile": "fastest",
                       "truck_id": "1",
                       "truck_label": "AB123CD",
                   }), \
             patch("services.route_profiles.ui_label_for_profile",
                   return_value="Fastest"):
            result = controller.load_from_url("https://operion.app/route?stops=...")
            assert result is not None
            assert len(result["stops"]) == 2

    def test_load_from_url_no_stops(self, controller):
        with patch("services.route_sharing_service.parse_share_url",
                   return_value={"stops": []}):
            result = controller.load_from_url("https://operion.app/route?stops=")
            assert result is None


class TestLoadFromRouteFile:
    def test_load_from_route_file(self, controller):
        with patch("builtins.open", MagicMock()), \
             patch("services.route_sharing_service.decode_route_file",
                   return_value={
                       "stops": [(45.0, 24.0)],
                       "profile": "fastest",
                       "truck_id": "1",
                       "truck_label": "AB123CD",
                       "distance_km": 100.0,
                       "duration_min": 60.0,
                   }), \
             patch("services.route_profiles.ui_label_for_profile",
                   return_value="Fastest"):
            result = controller.load_from_route_file("/path/file.operionroute")
            assert result is not None
            assert "route" in result

    def test_load_from_route_file_no_stops(self, controller):
        with patch("builtins.open", MagicMock()), \
             patch("services.route_sharing_service.decode_route_file",
                   return_value={"stops": []}):
            result = controller.load_from_route_file("/path/file.operionroute")
            assert result is None

    def test_load_from_route_file_os_error(self, controller):
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = controller.load_from_route_file("/path/file.operionroute")
            assert result is None


class TestExportMetadata:
    def test_export_route_metadata(self, controller):
        route = {"distance_km": 100.0}
        with patch("builtins.open", MagicMock()), \
             patch("json.dump"):
            path, err = controller.export_route_metadata(route)
            assert path is not None
            assert err is None

    def test_export_route_metadata_no_route(self, controller):
        path, err = controller.export_route_metadata(None)
        assert path is None
        assert err is not None


class TestBindPersistence:
    def test_bind_persistence(self, controller):
        persistence = MagicMock()
        controller.bind_persistence(persistence)
        assert controller._persistence is persistence


class TestCountryExclusion:
    def test_get_excluded_countries(self, controller):
        controller.country_avoidance.get_selected.return_value = ["HU", "BG"]
        assert controller.get_excluded_countries() == ["HU", "BG"]

    def test_set_excluded_countries(self, controller):
        controller.set_excluded_countries(["HU"])
        controller.country_avoidance.set_selected.assert_called_once_with(["HU"])
