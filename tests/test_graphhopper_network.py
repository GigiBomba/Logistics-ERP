"""Unit tests for GraphHopper network helpers."""
import unittest
from unittest import mock

from services.graphhopper_network import (
    RETRY_BACKOFF_SECONDS,
    build_route_endpoint,
    format_point_param,
    is_retryable_request_error,
    is_transient_http_status,
    normalize_graphhopper_base_url,
    retry_delay_seconds,
    should_use_post_routing,
    validate_route_points,
)


class TestGraphHopperNetwork(unittest.TestCase):
    def test_normalize_preserves_ipv4(self):
        url = normalize_graphhopper_base_url("http://192.168.0.93:8989")
        self.assertEqual(url, "http://192.168.0.93:8989")
        self.assertEqual(build_route_endpoint(url), "http://192.168.0.93:8989/route")

    def test_normalize_adds_scheme(self):
        url = normalize_graphhopper_base_url("192.168.0.93:8989")
        self.assertEqual(url, "http://192.168.0.93:8989")

    def test_normalize_rejects_numeric_url(self):
        with self.assertRaises(TypeError):
            normalize_graphhopper_base_url(192.168)

    def test_normalize_rejects_none(self):
        with self.assertRaises(ValueError):
            normalize_graphhopper_base_url(None)

    def test_normalize_rejects_empty(self):
        with self.assertRaises(ValueError):
            normalize_graphhopper_base_url("")

    def test_normalize_rejects_bad_scheme(self):
        with self.assertRaises(ValueError, msg="must use http or https"):
            normalize_graphhopper_base_url("ftp://example.com")

    def test_validate_points_requires_two(self):
        with self.assertRaises(ValueError):
            validate_route_points([(44.4, 26.1)])
        pts = validate_route_points([(44.4, 26.1), (48.8, 2.3)])
        self.assertEqual(len(pts), 2)

    def test_validate_rejects_malformed(self):
        with self.assertRaises(ValueError):
            validate_route_points([(44.4, 26.1), ("x", 2.3)])

    def test_validate_rejects_zero_coordinates(self):
        with self.assertRaises(ValueError, msg="Invalid zero coordinates"):
            validate_route_points([(0.0, 0.0), (48.8, 2.3)])

    def test_validate_rejects_none_point(self):
        with self.assertRaises(ValueError):
            validate_route_points([None, (48.8, 2.3)])

    def test_format_point_invariant(self):
        self.assertEqual(format_point_param(44.4361414, 26.102684), "44.4361414,26.1026840")

    def test_format_point_invariant_negative(self):
        self.assertIn("-", format_point_param(-33.8688, 151.2093))

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

    def test_should_use_post_multi_point(self):
        self.assertTrue(
            should_use_post_routing(
                has_custom_model=False,
                point_count=5,
                estimated_distance_km=100.0,
            )
        )

    def test_should_use_get_short_simple(self):
        self.assertFalse(
            should_use_post_routing(
                has_custom_model=False,
                point_count=2,
                estimated_distance_km=100.0,
            )
        )

    def test_http_400_not_retryable(self):
        import requests

        resp = mock.Mock()
        resp.status_code = 400
        err = requests.exceptions.HTTPError(response=resp)
        self.assertFalse(is_retryable_request_error(err))

    def test_http_500_is_retryable(self):
        import requests

        resp = mock.Mock()
        resp.status_code = 500
        err = requests.exceptions.HTTPError(response=resp)
        self.assertTrue(is_retryable_request_error(err))

    def test_http_429_is_retryable(self):
        import requests

        resp = mock.Mock()
        resp.status_code = 429
        err = requests.exceptions.HTTPError(response=resp)
        self.assertTrue(is_retryable_request_error(err))

    def test_timeout_is_retryable(self):
        import requests

        err = requests.exceptions.Timeout("timed out")
        self.assertTrue(is_retryable_request_error(err))

    def test_connection_error_is_retryable(self):
        import requests

        err = requests.exceptions.ConnectionError("refused")
        self.assertTrue(is_retryable_request_error(err))

    def test_is_transient_http_status_true(self):
        for code in (408, 429, 500, 502, 503, 504):
            self.assertTrue(is_transient_http_status(code))

    def test_is_transient_http_status_false(self):
        for code in (200, 400, 401, 403, 404, 422):
            self.assertFalse(is_transient_http_status(code))

    def test_retry_delay_seconds_first(self):
        self.assertEqual(retry_delay_seconds(0), RETRY_BACKOFF_SECONDS[0])

    def test_retry_delay_seconds_beyond_list(self):
        """Beyond the defined backoff list, should use the last value."""
        self.assertEqual(retry_delay_seconds(100), RETRY_BACKOFF_SECONDS[-1])

    def test_build_route_endpoint_https(self):
        self.assertEqual(
            build_route_endpoint("https://gh.example.com"),
            "https://gh.example.com/route",
        )


if __name__ == "__main__":
    unittest.main()
