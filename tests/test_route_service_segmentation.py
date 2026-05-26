"""Unit tests for route segmentation behavior."""
import types
import unittest
from unittest import mock

from services.route_service import RouteService


def _make_service() -> RouteService:
    service = RouteService(db=None, graphhopper_url="http://127.0.0.1:8989", timeout=10)
    service.client = mock.Mock()
    service.country_exclusion = mock.Mock(
        prepare=mock.Mock(return_value=types.SimpleNamespace(
            active=False,
            requested=[],
            applied=[],
            skipped_at_stops=[],
            strategy="none",
        )),
        merge_into_params=mock.Mock(side_effect=lambda params, plan: params),
    )
    service._detect_countries_from_geometry = mock.Mock(return_value=[])
    return service


class TestRouteServiceSegmentation(unittest.TestCase):
    def test_short_route_does_not_segment_on_failure(self):
        service = _make_service()
        service.client.route.side_effect = ValueError("No route found")

        with self.assertRaises(ValueError):
            service.calculate_route(
                stops=[(44.4268, 26.1025), (47.4979, 19.0402)],
                use_cache=False,
            )

        self.assertEqual(service.client.route.call_count, 1)

    def test_long_route_splits_once_after_direct_failure(self):
        service = _make_service()
        a = (44.4268, 26.1025)  # Bucharest
        b = (48.8566, 2.3522)   # Paris
        mid = service._segment_midpoint(a, b)

        def route_side_effect(points, profile="truck", params=None):
            pts = [tuple(p) for p in points]
            if pts == [a, b]:
                raise ValueError("PointDistanceExceededException")
            if pts in ([a, mid], [mid, b]):
                return {
                    "distance_km": 1.0,
                    "duration_min": 1.0,
                    "geometry": pts,
                    "graphhopper_response": {},
                    "points_count": 2,
                }
            raise AssertionError(f"Unexpected route request: {pts!r}")

        service.client.route.side_effect = route_side_effect

        result = service.calculate_route(stops=[a, b], use_cache=False)[0]

        self.assertEqual(service.client.route.call_count, 4)
        self.assertEqual(result["distance_km"], 2.0)
        self.assertEqual(result["points_count"], 2)


if __name__ == "__main__":
    unittest.main()
