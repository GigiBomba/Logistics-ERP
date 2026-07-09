"""Tests for RouteRunner service."""
import time
from unittest.mock import MagicMock, patch

import pytest

from services.route_runner import RouteRunner, run_route_async


@pytest.fixture
def runner():
    return RouteRunner()


class TestInitAndCancel:
    def test_cancel_sets_flag(self, runner):
        assert runner._cancel_flag.is_set() is False
        runner.cancel()
        assert runner._cancel_flag.is_set() is True

    def test_is_cancelled(self, runner):
        assert runner._is_cancelled() is False
        runner._cancel_flag.set()
        assert runner._is_cancelled() is True

    def test_reset_cancel_flag(self, runner):
        runner._cancel_flag.set()
        runner._reset_cancel_flag()
        assert runner._cancel_flag.is_set() is False


class TestSafeInvoke:
    def test_safe_invoke_calls_callback(self, runner):
        cb = MagicMock()
        runner._safe_invoke(cb, {"data": 42})
        cb.assert_called_once_with({"data": 42})

    def test_safe_invoke_handles_exception(self, runner):
        cb = MagicMock(side_effect=RuntimeError("fail"))
        runner._safe_invoke(cb, "test")  # should not raise

    def test_safe_invoke_skips_none(self, runner):
        runner._safe_invoke(None, "test")  # should not raise


class TestResolveStops:
    def test_resolve_pre_resolved(self, runner):
        stops_state = [
            {"resolved": True, "lat": "45.0", "lon": "24.0"},
            {"resolved": True, "lat": "46.0", "lon": "25.0"},
        ]
        result = runner._resolve_stops(stops_state)
        assert result == [(45.0, 24.0), (46.0, 25.0)]

    def test_resolve_with_geocode(self, runner):
        stops_state = [
            {"resolved": False, "address": "Sibiu, Romania"},
            {"resolved": False, "address": "Cluj, Romania"},
        ]
        with patch("services.route_runner.geocode_place",
                   side_effect=[(45.0, 24.0), (46.0, 25.0)]):
            result = runner._resolve_stops(stops_state)
            assert result == [(45.0, 24.0), (46.0, 25.0)]

    def test_resolve_uses_geocode_cache(self, runner):
        class FakeCache:
            def get(self, addr):
                return (47.0, 26.0) if addr == "cached" else None
            def set(self, addr, coord):
                pass

        stops_state = [
            {"resolved": False, "address": "cached"},
            {"resolved": True, "lat": "46.0", "lon": "25.0"},
        ]
        with patch("services.route_runner.geocode_place") as mock_geo:
            result = runner._resolve_stops(stops_state, geocode_cache=FakeCache())
            mock_geo.assert_not_called()  # used cache
            assert result == [(47.0, 26.0), (46.0, 25.0)]

    def test_resolve_invalid_coordinates_raises(self, runner):
        stops_state = [
            {"resolved": True, "lat": "999", "lon": "999", "address": ""},
        ]
        with patch("services.route_runner.geocode_place") as mock_geo:
            mock_geo.return_value = (46.0, 25.0)
            with pytest.raises(ValueError, match="no address"):
                runner._resolve_stops(stops_state)

    def test_resolve_zero_coordinates_fallback(self, runner):
        """Zero coordinates that aren't pre-resolved should trigger geocoding."""
        stops_state = [
            {"resolved": True, "lat": "0.0", "lon": "0.0", "address": ""},
        ]
        with pytest.raises(ValueError, match="no address"):
            runner._resolve_stops(stops_state)

    def test_resolve_fewer_than_2_raises(self, runner):
        stops_state = [
            {"resolved": True, "lat": "45.0", "lon": "24.0"},
        ]
        with pytest.raises(ValueError, match="At least 2"):
            runner._resolve_stops(stops_state)

    def test_deduplicate_consecutive_points(self, runner):
        stops_state = [
            {"resolved": True, "lat": "45.0", "lon": "24.0"},
            {"resolved": True, "lat": "45.0", "lon": "24.0"},
            {"resolved": True, "lat": "46.0", "lon": "25.0"},
        ]
        result = runner._resolve_stops(stops_state)
        assert result == [(45.0, 24.0), (46.0, 25.0)]

    def test_resolve_cancelled_raises(self, runner):
        runner._cancel_flag.set()
        stops_state = [
            {"resolved": False, "address": "Sibiu"},
        ]
        with pytest.raises(InterruptedError, match="cancelled"):
            runner._resolve_stops(stops_state)

    def test_resolve_no_address_raises(self, runner):
        stops_state = [
            {"resolved": False, "address": ""},
        ]
        with pytest.raises(ValueError, match="no address"):
            runner._resolve_stops(stops_state)


class TestRunRouteAsync:
    def test_run_route_async_calls_callback_with_result(self, runner):
        callback = MagicMock()
        route_service = MagicMock()
        route_service.calculate_route.return_value = {"distance_km": 150.0, "duration_min": 120.0}

        stops_state = [
            {"resolved": True, "lat": "45.0", "lon": "24.0"},
            {"resolved": True, "lat": "46.0", "lon": "25.0"},
        ]

        runner.run_route_async(
            route_service=route_service,
            stops_state=stops_state,
            truck={"id": 1},
            profile="fastest",
            callback=callback,
        )

        # Wait for thread to finish
        if runner._current_thread:
            runner._current_thread.join(timeout=5.0)

        callback.assert_called_once()
        args = callback.call_args[0][0]
        assert isinstance(args, dict)
        assert args["distance_km"] == 150.0

    def test_run_route_async_error_returns_error_dict(self, runner):
        callback = MagicMock()

        with patch.object(runner, "_resolve_stops",
                          side_effect=ValueError("Invalid stops")):
            runner.run_route_async(
                route_service=MagicMock(),
                stops_state=[],
                truck={},
                profile="fastest",
                callback=callback,
            )

            if runner._current_thread:
                runner._current_thread.join(timeout=5.0)

            callback.assert_called_once()
            args = callback.call_args[0][0]
            assert "error" in args

    def test_run_route_async_cancelled(self, runner):
        callback = MagicMock()

        # Simulate cancellation during _resolve_stops
        with patch.object(runner, "_resolve_stops",
                          side_effect=InterruptedError("Route calculation cancelled")):
            runner.run_route_async(
                route_service=MagicMock(),
                stops_state=[{"resolved": True, "lat": "45.0", "lon": "24.0"},
                             {"resolved": True, "lat": "46.0", "lon": "25.0"}],
                truck={},
                profile="fastest",
                callback=callback,
            )

            if runner._current_thread:
                runner._current_thread.join(timeout=5.0)

        callback.assert_called_once()
        args = callback.call_args[0][0]
        assert args.get("cancelled") is True

    def test_run_route_async_cancels_previous(self, runner):
        callback1 = MagicMock()

        stops_state = [
            {"resolved": True, "lat": "45.0", "lon": "24.0"},
            {"resolved": True, "lat": "46.0", "lon": "25.0"},
        ]
        route_service = MagicMock()
        route_service.calculate_route.return_value = {"distance_km": 100.0}

        # The first run starts a long-lived thread that blocks on route_service.
        # We patch _resolve_stops to simulate cancellation quickly.
        with patch.object(runner, "_resolve_stops", side_effect=InterruptedError("cancelled")):
            runner.run_route_async(
                route_service=route_service,
                stops_state=stops_state,
                truck={}, profile="fastest",
                callback=callback1,
            )

        runner._current_thread.join(timeout=5.0)

        # Start second run (first should have terminated)
        callback2 = MagicMock()
        runner.run_route_async(
            route_service=route_service,
            stops_state=stops_state,
            truck={}, profile="fastest",
            callback=callback2,
        )

        if runner._current_thread:
            runner._current_thread.join(timeout=5.0)

        assert callback2.called


class TestLegacyFunction:
    def test_run_route_async_function(self):
        callback = MagicMock()
        route_service = MagicMock()
        route_service.calculate_route.return_value = {"distance_km": 100.0}

        stops_state = [
            {"resolved": True, "lat": "45.0", "lon": "24.0"},
            {"resolved": True, "lat": "46.0", "lon": "25.0"},
        ]

        import services.route_runner as rr_mod
        original = rr_mod._RUNNER_INSTANCE
        try:
            runner = MagicMock()
            rr_mod._RUNNER_INSTANCE = runner

            run_route_async(
                route_service=route_service,
                stops_state=stops_state,
                truck={}, profile="fastest",
                callback=callback,
            )
            runner.run_route_async.assert_called_once()
        finally:
            rr_mod._RUNNER_INSTANCE = original
