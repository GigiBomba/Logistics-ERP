"""Unit tests for RouteService — cache, geocode, validation."""
import json
import unittest
from unittest import mock

import pytest

from services.route_service import GeocodeCache, RouteCache, RouteService, GraphHopperClient


class TestGeocodeCache(unittest.TestCase):
    def setUp(self):
        self.cache = GeocodeCache(max_size=5, ttl_seconds=3600)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.cache.get("nonexistent"))

    def test_set_and_get(self):
        self.cache.set("Paris", (48.8566, 2.3522))
        self.assertEqual(self.cache.get("Paris"), (48.8566, 2.3522))

    def test_expired_entry_returns_none(self):
        short_cache = GeocodeCache(max_size=5, ttl_seconds=-1)
        short_cache.set("Paris", (48.8566, 2.3522))
        self.assertIsNone(short_cache.get("Paris"))

    def test_evicts_oldest_when_full(self):
        for i in range(10):
            self.cache.set(f"addr{i}", (float(i), float(i)))
        self.assertIsNone(self.cache.get("addr0"))
        self.assertIsNotNone(self.cache.get("addr9"))

    def test_set_updates_existing(self):
        self.cache.set("Paris", (48.8566, 2.3522))
        self.cache.set("Paris", (48.8566, 2.3523))
        self.assertEqual(self.cache.get("Paris"), (48.8566, 2.3523))

    def test_empty_address_returns_none(self):
        self.assertIsNone(self.cache.get(""))


class TestRouteCache(unittest.TestCase):
    def setUp(self):
        self.cache = RouteCache(max_size=3, ttl_seconds=3600)
        self.points = [(48.8566, 2.3522), (44.4268, 26.1025)]

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.cache.get(self.points, "truck"))

    def test_set_and_get(self):
        result = {"distance_km": 100.0}
        self.cache.set(self.points, "truck", result)
        cached = self.cache.get(self.points, "truck")
        self.assertEqual(cached["distance_km"], 100.0)

    def test_different_profile_miss(self):
        result = {"distance_km": 100.0}
        self.cache.set(self.points, "truck", result)
        self.assertIsNone(self.cache.get(self.points, "car"))

    def test_evicts_oldest_when_full(self):
        for i in range(5):
            pts = [(float(i), float(i)), (float(i + 1), float(i + 1))]
            self.cache.set(pts, "truck", {"id": i})
        self.assertIsNone(self.cache.get([(0.0, 0.0), (1.0, 1.0)], "truck"))

    def test_expired_entry_returns_none(self):
        short_cache = RouteCache(max_size=10, ttl_seconds=0)
        short_cache.set(self.points, "truck", {"distance_km": 100.0})
        self.assertIsNone(short_cache.get(self.points, "truck"))

    def test_exclusions_key(self):
        result = {"distance_km": 100.0}
        self.cache.set(self.points, "truck", result, exclusions=["RO"])
        cached = self.cache.get(self.points, "truck", exclusions=["RO"])
        self.assertEqual(cached["distance_km"], 100.0)

    def test_exclusions_mismatch(self):
        result = {"distance_km": 100.0}
        self.cache.set(self.points, "truck", result, exclusions=["RO"])
        self.assertIsNone(self.cache.get(self.points, "truck", exclusions=["FR"]))


class TestGraphHopperClient(unittest.TestCase):
    def test_validate_coordinates_valid(self):
        self.assertTrue(GraphHopperClient._validate_coordinates(45.0, 10.0))
        self.assertTrue(GraphHopperClient._validate_coordinates(-90.0, -180.0))
        self.assertTrue(GraphHopperClient._validate_coordinates(90.0, 180.0))

    def test_validate_coordinates_invalid(self):
        self.assertFalse(GraphHopperClient._validate_coordinates(91.0, 0.0))
        self.assertFalse(GraphHopperClient._validate_coordinates(0.0, 181.0))
        self.assertFalse(GraphHopperClient._validate_coordinates(-91.0, 0.0))

    def test_validate_coordinates_nan(self):
        self.assertFalse(GraphHopperClient._validate_coordinates(float("nan"), 0.0))
        self.assertFalse(GraphHopperClient._validate_coordinates(0.0, float("inf")))

    def test_validate_coordinates_string(self):
        self.assertTrue(GraphHopperClient._validate_coordinates("45.0", "10.0"))
        self.assertFalse(GraphHopperClient._validate_coordinates("abc", "10.0"))

    def test_haversine_distance_zero(self):
        d = GraphHopperClient._haversine_distance(48.8566, 2.3522, 48.8566, 2.3522)
        self.assertAlmostEqual(d, 0.0)

    def test_haversine_distance_paris_bucharest(self):
        d = GraphHopperClient._haversine_distance(48.8566, 2.3522, 44.4268, 26.1025)
        self.assertAlmostEqual(d, 1870.0, delta=10)

    def test_split_routing_params_internal_keys_filtered(self):
        params = {
            "avoid_countries": ["RO"],
            "weight": "40000",
            "_custom_model": {"some": "value"},
        }
        gh, cm, meta = GraphHopperClient(None)._split_routing_params(params)
        self.assertIn("weight", gh)
        self.assertNotIn("avoid_countries", gh)
        self.assertNotIn("_custom_model", gh)
        self.assertEqual(cm, {"some": "value"})
        self.assertIn("avoid_countries", meta)


class TestRouteServiceCoordinateHandling(unittest.TestCase):
    def test_validate_segment_rejects_none_point(self):
        with self.assertRaises(ValueError):
            RouteService._validate_segment([(45.0, 10.0), None])

    def test_validate_segment_rejects_malformed(self):
        with self.assertRaises(ValueError):
            RouteService._validate_segment([(45.0, 10.0), (45.0,)])

    def test_validate_segment_rejects_nan(self):
        with self.assertRaises(ValueError):
            RouteService._validate_segment([(45.0, 10.0), (float("nan"), 20.0)])

    def test_validate_segment_rejects_inf(self):
        with self.assertRaises(ValueError):
            RouteService._validate_segment([(45.0, 10.0), (float("inf"), 20.0)])

    def test_validate_segment_rejects_invalid_lat(self):
        with self.assertRaises(ValueError):
            RouteService._validate_segment([(45.0, 10.0), (91.0, 20.0)])

    def test_validate_segment_rejects_duplicate_consecutive(self):
        with self.assertRaises(ValueError):
            RouteService._validate_segment([(45.0, 10.0), (45.0, 10.0)])

    def test_validate_segment_accepts_valid(self):
        try:
            RouteService._validate_segment([(45.0, 10.0), (46.0, 11.0)])
        except ValueError:
            self.fail("_validate_segment raised on valid input")

    def test_validate_segment_rejects_empty(self):
        with self.assertRaises(ValueError):
            RouteService._validate_segment([])

    def test_validate_segment_rejects_single_point(self):
        with self.assertRaises(ValueError):
            RouteService._validate_segment([(45.0, 10.0)])

    def test_segment_midpoint(self):
        a = (48.8566, 2.3522)
        b = (44.4268, 26.1025)
        mid = RouteService._segment_midpoint(a, b)
        self.assertAlmostEqual(mid[0], 46.7, delta=1)
        self.assertAlmostEqual(mid[1], 14.2, delta=1)

    def test_is_segmentation_worthy_error_keywords(self):
        class DummyError(Exception):
            pass

        self.assertTrue(RouteService._is_segmentation_worthy_error(
            ValueError("PointDistanceExceededException")
        ))
        self.assertTrue(RouteService._is_segmentation_worthy_error(
            ValueError("No route found")
        ))
        self.assertTrue(RouteService._is_segmentation_worthy_error(
            RuntimeError("timeout")
        ))
        self.assertFalse(RouteService._is_segmentation_worthy_error(
            ValueError("Some other error")
        ))

    def test_is_segmentation_worthy_error_connection_error(self):
        import requests
        self.assertTrue(RouteService._is_segmentation_worthy_error(
            requests.exceptions.ConnectionError("DNS failure")
        ))

    def test_should_split_segment_max_depth(self):
        svc = RouteService(db=None, graphhopper_url="http://fake:8989")
        result = svc._should_split_segment(
            distance_km=2000, depth=3, exc=ValueError("timeout"), segments_total=1,
        )
        self.assertFalse(result)

    def test_should_split_segment_too_short(self):
        svc = RouteService(db=None, graphhopper_url="http://fake:8989")
        result = svc._should_split_segment(
            distance_km=100, depth=0, exc=ValueError("PointDistanceExceededException"), segments_total=1,
        )
        self.assertFalse(result)

    def test_should_split_segment_max_count(self):
        svc = RouteService(db=None, graphhopper_url="http://fake:8989")
        result = svc._should_split_segment(
            distance_km=2000, depth=0, exc=ValueError("timeout"), segments_total=4,
        )
        self.assertFalse(result)

    def test_should_split_segment_worthy(self):
        svc = RouteService(db=None, graphhopper_url="http://fake:8989")
        result = svc._should_split_segment(
            distance_km=2000, depth=0, exc=ValueError("timeout"), segments_total=1,
        )
        self.assertTrue(result)

    def test_should_split_segment_not_worthy_below_threshold(self):
        svc = RouteService(db=None, graphhopper_url="http://fake:8989")
        result = svc._should_split_segment(
            distance_km=500, depth=0, exc=ValueError("Some other error"), segments_total=1,
        )
        self.assertFalse(result)

    def test_should_segment_route_short_distance(self):
        svc = RouteService(db=None, graphhopper_url="http://fake:8989")
        self.assertFalse(svc._should_segment_route(
            distance_km=100, exc=ValueError("timeout"),
        ))

    def test_should_segment_route_long_distance_worthy(self):
        svc = RouteService(db=None, graphhopper_url="http://fake:8989")
        self.assertTrue(svc._should_segment_route(
            distance_km=2000, exc=ValueError("timeout"),
        ))

    def test_merge_segment_results(self):
        svc = RouteService(db=None, graphhopper_url="http://fake:8989")
        parts = [
            {"distance_km": 500.0, "duration_min": 300.0, "geometry": [(1, 1), (2, 2)], "graphhopper_response": {"p1": 1}},
            {"distance_km": 300.0, "duration_min": 180.0, "geometry": [(2, 2), (3, 3)], "graphhopper_response": {"p2": 2}},
        ]
        merged = svc._merge_segment_results(parts, [(1, 1), (3, 3)])
        self.assertAlmostEqual(merged["distance_km"], 800.0)
        self.assertAlmostEqual(merged["duration_min"], 480.0)
        self.assertEqual(len(merged["geometry"]), 3)

    def test_merge_segment_results_no_overlap(self):
        svc = RouteService(db=None, graphhopper_url="http://fake:8989")
        parts = [
            {"distance_km": 100.0, "duration_min": 60.0, "geometry": [(1, 1), (2, 2)], "graphhopper_response": {}},
            {"distance_km": 200.0, "duration_min": 120.0, "geometry": [(3, 3), (4, 4)], "graphhopper_response": {}},
        ]
        merged = svc._merge_segment_results(parts, [(1, 1), (4, 4)])
        # No overlap so geometry is concatenated directly
        self.assertEqual(len(merged["geometry"]), 4)


class TestGraphHopperClientRoute(unittest.TestCase):
    """Tests for GraphHopperClient.route() with mocked HTTP session."""

    def setUp(self):
        self.client = GraphHopperClient(base_url="http://fake-gh:8989", timeout=30)
        self.client.session = mock.MagicMock()
        # Use close points (<400km apart) to ensure GET routing by default
        self.short_points = [(52.5200, 13.4050), (51.0504, 13.7373)]  # Berlin → Dresden (~165km)
        self.long_points = [(48.8566, 2.3522), (44.4268, 26.1025)]  # Paris → Bucharest (~1870km)

    def _make_response(self, status_code=200, data=None):
        resp = mock.MagicMock()
        resp.status_code = status_code
        resp.text = json.dumps(data) if data else ""
        resp.json.return_value = data or {"paths": [{"distance": 165000, "time": 5400000, "points": {"coordinates": [[13.405, 52.52], [13.737, 51.05]]}}]}
        return resp

    def _make_long_response(self):
        resp = mock.MagicMock()
        resp.status_code = 200
        data = {"paths": [{"distance": 1870000, "time": 72000000, "points": {"coordinates": [[2.35, 48.85], [26.10, 44.43]]}}]}
        resp.text = json.dumps(data)
        resp.json.return_value = data
        return resp

    def test_route_success_get(self):
        """Short-distance route uses GET."""
        resp = self._make_response()
        self.client.session.get.return_value = resp
        self.client.session.post.return_value = resp
        result = self.client.route(self.short_points, profile="truck")
        self.assertIn("distance_km", result)
        self.assertEqual(result["routing_method"], "GET")

    def test_route_success_post_long_distance(self):
        """Long-distance route (>400km) uses POST."""
        resp = self._make_long_response()
        self.client.session.post.return_value = resp
        self.client.session.get.return_value = resp
        result = self.client.route(self.long_points, profile="truck")
        self.assertEqual(result["routing_method"], "POST")

    def test_route_with_avoid_countries(self):
        """Custom model forces POST."""
        resp = self._make_response()
        self.client.session.post.return_value = resp
        self.client.session.get.return_value = resp
        result = self.client.route(
            self.short_points, profile="truck",
            params={"avoid_countries": ["UA"], "_custom_model": {"some": "restriction"}},
        )
        self.assertEqual(result["routing_method"], "POST")

    def test_route_http_500_retry_then_success(self):
        fail_resp = mock.MagicMock(status_code=500, text="")
        fail_resp.json.side_effect = ValueError("not json")
        ok_resp = self._make_response()
        self.client.session.get.side_effect = [fail_resp, ok_resp]
        self.client.session.post.side_effect = [fail_resp, ok_resp]
        result = self.client.route(self.short_points, profile="truck")
        self.assertIn("distance_km", result)

    def test_route_all_retries_exhausted(self):
        import requests
        fail_resp = mock.MagicMock(status_code=503, text="Service Unavailable")
        fail_resp.json.side_effect = ValueError("not json")
        # raise_for_status must raise a real HTTPError for the retry logic to work
        http_error = requests.exceptions.HTTPError("503 Server Error", response=fail_resp)
        fail_resp.raise_for_status.side_effect = http_error
        self.client.session.get.side_effect = [fail_resp] * 6
        self.client.session.post.side_effect = [fail_resp] * 6
        # The last attempt's raise_for_status raises HTTPError (not RuntimeError)
        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.route(self.short_points, profile="truck")

    def test_route_no_paths_raises_value_error(self):
        resp = self._make_response(status_code=200, data={"paths": []})
        self.client.session.get.return_value = resp
        self.client.session.post.return_value = resp
        with self.assertRaises(ValueError):
            self.client.route(self.short_points, profile="truck")

    def test_route_no_paths_with_message(self):
        resp = self._make_response(status_code=200, data={"paths": [], "message": "No route found between locations"})
        self.client.session.get.return_value = resp
        self.client.session.post.return_value = resp
        with self.assertRaises(ValueError):
            self.client.route(self.short_points, profile="truck")

    def test_route_ch_distance_auto_retry_with_ch_disable(self):
        """When GH returns PointDistanceExceeded, the client should retry with ch.disable=true."""
        err_body = json.dumps({"message": "PointDistanceExceededException: The distance between points exceeds the maximum for CH routing"})
        err_resp = mock.MagicMock(status_code=400, text=err_body)
        err_resp.json.return_value = {"message": "PointDistanceExceededException: The distance between points exceeds the maximum for CH routing"}
        ok_resp = self._make_long_response()
        # Long distance uses POST routing
        self.client.session.post.side_effect = [err_resp, ok_resp]
        self.client.session.get.side_effect = [err_resp, ok_resp]
        result = self.client.route(self.long_points, profile="truck")
        self.assertIn("distance_km", result)
        # Verify that POST was retried with ch.disable=true in the body
        post_call_args = self.client.session.post.call_args_list
        self.assertEqual(len(post_call_args), 2)
        second_body = post_call_args[1][1].get("json", {})
        self.assertTrue(second_body.get("ch.disable", False))

    def test_route_parse_geometry_coordinates_dict(self):
        path = {
            "distance": 100000,
            "time": 3600000,
            "points": {
                "coordinates": [[13.405, 52.52], [13.45, 52.30], [13.737, 51.05]],
            },
        }
        data = {"paths": [path]}
        resp = self._make_response(status_code=200, data=data)
        self.client.session.get.return_value = resp
        self.client.session.post.return_value = resp
        result = self.client.route(self.short_points, profile="truck")
        self.assertEqual(len(result["geometry"]), 3)

    def test_route_parse_geometry_list_of_pairs(self):
        path = {
            "distance": 100000,
            "time": 3600000,
            "points": [(13.405, 52.52), (13.737, 51.05)],
        }
        data = {"paths": [path]}
        resp = self._make_response(status_code=200, data=data)
        self.client.session.get.return_value = resp
        self.client.session.post.return_value = resp
        result = self.client.route(self.short_points, profile="truck")
        self.assertEqual(len(result["geometry"]), 2)

    def test_route_preserves_exclusions_applied_flag(self):
        resp = self._make_response()
        self.client.session.post.return_value = resp
        self.client.session.get.return_value = resp
        result = self.client.route(
            self.short_points, profile="truck",
            params={"avoid_countries": ["UA"], "_custom_model": {"restrict": "UA"}},
        )
        self.assertTrue(result["exclusions_applied"])

    def test_route_http_400_with_gh_message_raises(self):
        """Non-retryable HTTP 400 with a meaningful GH message should raise ValueError."""
        err_body = json.dumps({"message": "Cannot find route: some points are not connected"})
        err_resp = mock.MagicMock(status_code=400, text=err_body)
        err_resp.json.return_value = {"message": "Cannot find route: some points are not connected"}
        self.client.session.get.return_value = err_resp
        self.client.session.post.return_value = err_resp
        with self.assertRaises(ValueError, msg="Cannot find route"):
            self.client.route(self.short_points, profile="truck")


class TestRouteServiceFullFlow(unittest.TestCase):
    """Integration-style tests for RouteService orchestration methods."""

    def setUp(self):
        self.svc = RouteService(db=None, graphhopper_url="http://fake-gh:8989", timeout=30)
        self.svc.client.session = mock.MagicMock()
        # Mock the external engines
        self.svc.country_exclusion = mock.MagicMock()
        self.svc.country_exclusion.prepare.return_value = mock.MagicMock(
            active=False, requested=[], applied=[], skipped_at_stops=[], strategy=None,
        )
        self.svc.country_exclusion.merge_into_params.return_value = {}
        self.svc.constraint_engine = mock.MagicMock()
        self.svc.constraint_engine.build_params.return_value = {}
        # Use short-distance points (<400km) to ensure GET routing
        self.short_stops = [(52.5200, 13.4050), (51.0504, 13.7373)]  # Berlin → Dresden
        self.short_distance_km = 165.0

    def _make_gh_response(self, distance_km=165.0):
        resp = mock.MagicMock()
        resp.status_code = 200
        data = {"paths": [{"distance": int(distance_km * 1000), "time": int(distance_km * 60 * 1000 * 0.6), "points": {"coordinates": [[13.405, 52.52], [13.737, 51.05]]}}]}
        resp.text = json.dumps(data)
        resp.json.return_value = data
        return resp

    @mock.patch("services.route_service.geocode_place")
    def test_geocode_address(self, mock_geocode):
        mock_geocode.return_value = (48.8566, 2.3522)
        coords = self.svc._geocode_address("Paris")
        self.assertEqual(coords, (48.8566, 2.3522))
        mock_geocode.assert_called_once_with("Paris", timeout=15)

    @mock.patch("services.route_service.geocode_place")
    def test_geocode_address_empty(self, mock_geocode):
        with self.assertRaises(ValueError):
            self.svc._geocode_address("")

    @mock.patch("services.route_service.geocode_place")
    def test_geocode_address_uses_cache(self, mock_geocode):
        self.svc._geocode_cache.set("Paris", (48.8566, 2.3522))
        coords = self.svc._geocode_address("Paris")
        self.assertEqual(coords, (48.8566, 2.3522))
        mock_geocode.assert_not_called()

    @mock.patch("services.route_service.geocode_place")
    def test_geocode_address_failure(self, mock_geocode):
        mock_geocode.return_value = None
        with self.assertRaises(ValueError):
            self.svc._geocode_address("Nowhere")

    @mock.patch("services.route_service.GraphHopperClient._validate_coordinates")
    @mock.patch("services.route_service.geocode_place")
    def test_geocode_address_invalid_coords(self, mock_geocode, mock_validate):
        mock_geocode.return_value = (100.0, 200.0)
        mock_validate.return_value = False
        with self.assertRaises(ValueError):
            self.svc._geocode_address("BadPlace")

    def test_resolve_stops_with_coordinates(self):
        result = self.svc._resolve_stops(self.short_stops)
        self.assertEqual(len(result), 2)

    def test_resolve_stops_less_than_two_raises(self):
        with self.assertRaises(ValueError):
            self.svc._resolve_stops([(48.8566, 2.3522)])

    def test_resolve_stops_deduplicates_consecutive(self):
        result = self.svc._resolve_stops([
            (52.5200, 13.4050), (52.5200, 13.4050), (51.0504, 13.7373),
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], (52.5200, 13.4050))
        self.assertEqual(result[1], (51.0504, 13.7373))

    @mock.patch("services.route_service.geocode_place")
    def test_resolve_stops_mixed_coords_and_geocode(self, mock_geocode):
        mock_geocode.return_value = (51.0504, 13.7373)
        result = self.svc._resolve_stops([(52.5200, 13.4050), "Dresden"])
        self.assertEqual(len(result), 2)
        mock_geocode.assert_called_once_with("Dresden", timeout=15)

    def test_calculate_route_with_coordinates(self):
        """Basic calculate_route with direct coordinates (no geocoding)."""
        resp = self._make_gh_response()
        self.svc.client.session.get.return_value = resp
        self.svc.client.session.post.return_value = resp
        results = self.svc.calculate_route(
            self.short_stops,
            profile="truck",
            stops_are_coordinates=True,
        )
        self.assertEqual(len(results), 1)
        self.assertIn("distance_km", results[0])
        self.assertFalse(results[0].get("cached", False))

    def test_calculate_route_uses_cache(self):
        """When route cache has an entry, it should be returned."""
        self.svc._route_cache.set(
            self.short_stops,
            "truck",
            {"distance_km": 100.0, "cached": False},
        )
        results = self.svc.calculate_route(
            self.short_stops,
            profile="truck",
            stops_are_coordinates=True,
            use_cache=True,
        )
        self.assertTrue(results[0].get("cached", False))

    def test_calculate_route_with_truck_params(self):
        """Truck constraint engine params should be passed to GH client."""
        resp = self._make_gh_response()
        self.svc.client.session.get.return_value = resp
        self.svc.client.session.post.return_value = resp
        self.svc.constraint_engine.build_params.return_value = {"weight": "40000"}
        results = self.svc.calculate_route(
            self.short_stops,
            profile="truck",
            truck={"id": "T1", "weight": 40000},
            stops_are_coordinates=True,
        )
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
