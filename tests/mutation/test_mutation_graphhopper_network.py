from __future__ import annotations

import pytest
from unittest import mock

from services.graphhopper_network import (
    POST_DISTANCE_THRESHOLD_KM,
    is_retryable_request_error,
    is_transient_http_status,
    should_use_post_routing,
)

pytestmark = pytest.mark.mutation


class TestKillMutationShouldUsePostRouting:
    """Kill mutations in graphhopper_network.should_use_post_routing.

    should_use_post_routing(*, has_custom_model, point_count, estimated_distance_km) -> bool
    """

    # ── 1. has_custom_model=True → always True (guard deletion) ──
    def test_has_custom_model_returns_true(self):
        """When has_custom_model is True, the result must be True regardless of
        other inputs. A mutation that removes the early return will fail."""
        result = should_use_post_routing(
            has_custom_model=True,
            point_count=2,
            estimated_distance_km=10.0,
        )
        assert result is True, (
            "has_custom_model=True must always return True"
        )

    # ── 2. point_count=2 does NOT force post (point_count > 2 → >= mutation) ──
    def test_point_count_two_does_not_force_post(self):
        """With 2 points, short distance, no custom model → must return False.
        A mutation changing '>' to '>=' will return True for 2 points."""
        result = should_use_post_routing(
            has_custom_model=False,
            point_count=2,
            estimated_distance_km=10.0,
        )
        assert result is False, (
            "2 points with short distance must use GET (False)"
        )

    # ── 3. point_count=3 forces post ──
    def test_point_count_three_forces_post(self):
        """3+ points must force POST routing."""
        result = should_use_post_routing(
            has_custom_model=False,
            point_count=3,
            estimated_distance_km=10.0,
        )
        assert result is True, "3+ points must force POST"

    # ── 4. estimated_distance_km >= threshold forces post ──
    def test_distance_at_threshold_forces_post(self):
        """Distance exactly at POST_DISTANCE_THRESHOLD_KM must force POST.
        A mutation changing >= to > will fail."""
        result = should_use_post_routing(
            has_custom_model=False,
            point_count=2,
            estimated_distance_km=POST_DISTANCE_THRESHOLD_KM,
        )
        assert result is True, (
            f"Distance at {POST_DISTANCE_THRESHOLD_KM} km must force POST"
        )

    # ── 5. estimated_distance_km = threshold - 1 does NOT force post ──
    def test_distance_below_threshold_does_not_force_post(self):
        """Distance just below the threshold with 2 points and no custom model
        must return False."""
        result = should_use_post_routing(
            has_custom_model=False,
            point_count=2,
            estimated_distance_km=POST_DISTANCE_THRESHOLD_KM - 1.0,
        )
        assert result is False, (
            f"Distance {POST_DISTANCE_THRESHOLD_KM - 1} km must not force POST"
        )


class TestKillMutationIsRetryableRequestError:
    """Kill mutations in graphhopper_network.is_retryable_request_error."""

    # ── 6. ConnectionError → retryable ──
    def test_connection_error_is_retryable(self):
        import requests
        err = requests.exceptions.ConnectionError("Connection refused")
        assert is_retryable_request_error(err) is True

    # ── 7. Timeout → retryable ──
    def test_timeout_is_retryable(self):
        import requests
        err = requests.exceptions.Timeout("timed out")
        assert is_retryable_request_error(err) is True

    # ── 8. HTTP 400 → not retryable ──
    def test_http_400_not_retryable(self):
        import requests
        resp = mock.Mock()
        resp.status_code = 400
        err = requests.exceptions.HTTPError(response=resp)
        assert is_retryable_request_error(err) is False


class TestKillMutationIsTransientHttpStatus:
    """Kill mutations in graphhopper_network.is_transient_http_status."""

    # ── 9. HTTP 500/502/503/504 → transient ──
    @pytest.mark.parametrize("status_code", [500, 502, 503, 504])
    def test_transient_statuses(self, status_code):
        """These status codes must be detected as transient."""
        assert is_transient_http_status(status_code) is True

    # ── 10. HTTP 200/301/404 → not transient ──
    @pytest.mark.parametrize("status_code", [200, 301, 404])
    def test_non_transient_statuses(self, status_code):
        """These status codes must NOT be detected as transient."""
        assert is_transient_http_status(status_code) is False
