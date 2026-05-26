"""Unit tests for GraphHopper network helpers."""
import unittest
from unittest import mock

from services.graphhopper_network import (
    build_route_endpoint,
    format_point_param,
    is_retryable_request_error,
    normalize_graphhopper_base_url,
    should_use_post_routing,
    validate_route_points,
)


class TestGraphHopperNetwork(unittest.TestCase):
    def test_normalize_preserves_ipv4(self):
        url = normalize_graphhopper_base_url("http://192.168.0.93:8989")
        self.assertEqual(url, "http://192.168.0.93:8989")
        self.assertEqual(build_route_endpoint(url), "http://192.168.0.93:8989/route")

    def test_normalize_rejects_numeric_url(self):
        with self.assertRaises(TypeError):
            normalize_graphhopper_base_url(192.168)

    def test_validate_points_requires_two(self):
        with self.assertRaises(ValueError):
            validate_route_points([(44.4, 26.1)])
        pts = validate_route_points([(44.4, 26.1), (48.8, 2.3)])
        self.assertEqual(len(pts), 2)

    def test_validate_rejects_malformed(self):
        with self.assertRaises(ValueError):
            validate_route_points([(44.4, 26.1), ("x", 2.3)])

    def test_format_point_invariant(self):
        self.assertEqual(format_point_param(44.4361414, 26.102684), "44.4361414,26.1026840")

    def test_should_use_post_long_distance(self):
        self.assertTrue(
            should_use_post_routing(
                has_custom_model=False,
                point_count=2,
                estimated_distance_km=2000.0,
            )
        )

    def test_should_use_post_custom_model(self):
        self.assertTrue(
            should_use_post_routing(
                has_custom_model=True,
                point_count=2,
                estimated_distance_km=10.0,
            )
        )

    def test_http_400_not_retryable(self):
        import requests

        resp = mock.Mock()
        resp.status_code = 400
        err = requests.exceptions.HTTPError(response=resp)
        self.assertFalse(is_retryable_request_error(err))


if __name__ == "__main__":
    unittest.main()
