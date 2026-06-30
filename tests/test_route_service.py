"""Unit tests for RouteService — cache, geocode, validation."""
import unittest
from unittest import mock

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


if __name__ == "__main__":
    unittest.main()
