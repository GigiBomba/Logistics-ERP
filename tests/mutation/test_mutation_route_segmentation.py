from __future__ import annotations

import pytest
from unittest import mock

from services.route_service import RouteService

pytestmark = pytest.mark.mutation


class TestKillMutationShouldSplitSegment:
    """Kill mutations in RouteService._should_split_segment.

    _should_split_segment(distance_km, depth, exc, segments_total) -> bool
    """

    @pytest.fixture
    def service(self):
        svc = RouteService(db=None, graphhopper_url="http://127.0.0.1:8989", timeout=10)
        svc.client = mock.Mock()
        svc.country_exclusion = mock.Mock()
        return svc

    # ── 1. depth >= max_segmentation_depth → depth > max ──
    def test_depth_at_max_returns_false(self, service):
        """depth == max_segmentation_depth (2) must return False.
        A mutation changing >= to > would let depth==max fall through."""
        assert service._should_split_segment(
            distance_km=500.0,
            depth=service.max_segmentation_depth,
            exc=ValueError("no route"),
            segments_total=1,
        ) is False, "depth at max must return False"

    # ── 2. distance_km < min_segment_distance_km → <= ──
    def test_distance_at_min_does_not_split(self, service):
        """distance_km == min_segment_distance_km (350) with no worthy error
        must return False. A mutation changing < to <= would return True."""
        assert service._should_split_segment(
            distance_km=service.min_segment_distance_km,
            depth=0,
            exc=ValueError("some non-worthy error"),
            segments_total=1,
        ) is False, "distance at min with no worthy error must return False"

    # ── 3. segments_total >= max_segment_count → > ──
    def test_segments_at_max_returns_false(self, service):
        """segments_total == max_segment_count (4) must return False.
        A mutation changing >= to > would let segments==max fall through."""
        assert service._should_split_segment(
            distance_km=500.0,
            depth=0,
            exc=ValueError("no route"),
            segments_total=service.max_segment_count,
        ) is False, "segments at max must return False"

    # ── 4. Distance below threshold WITH worthy error → splits ──
    def test_below_threshold_with_worthy_error_splits(self, service):
        """When distance < segment_distance_threshold but >= min_segment,
        and the error is worthy, _should_split_segment returns True."""
        # distance between min (350) and threshold (800)
        dist = 500.0
        assert service.min_segment_distance_km <= dist < service.segment_distance_threshold_km
        result = service._should_split_segment(
            distance_km=dist,
            depth=0,
            exc=ValueError("PointDistanceExceededException"),
            segments_total=1,
        )
        assert result is True, "below threshold with worthy error must split"

    # ── 5. Distance below threshold WITHOUT worthy error → does NOT split ──
    def test_below_threshold_without_worthy_error_does_not_split(self, service):
        """When distance < segment_distance_threshold but >= min_segment,
        and the error is NOT worthy, _should_split_segment returns False."""
        dist = 500.0
        assert service.min_segment_distance_km <= dist < service.segment_distance_threshold_km
        result = service._should_split_segment(
            distance_km=dist,
            depth=0,
            exc=ValueError("some harmless message"),
            segments_total=1,
        )
        assert result is False, "below threshold without worthy error must not split"


class TestKillMutationIsSegmentationWorthyError:
    """Kill mutations in RouteService._is_segmentation_worthy_error."""

    # ── 6. Each keyword triggers True ──
    @pytest.mark.parametrize("keyword, msg", [
        ("pointdistanceexceededexception", "PointDistanceExceededException"),
        ("no route", "No route found"),
        ("no paths", "No paths returned by GraphHopper"),
        ("no path found", "No path found"),
        ("invalid route", "Invalid route for given profile"),
        ("search exceeded", "Search exceeded time limit"),
        ("timeout", "Request timeout after 30s"),
        ("too far", "Points are too far apart"),
        ("bad request", "Bad request: invalid coordinates"),
    ])
    def test_worthy_keyword_detected(self, keyword, msg):
        """Each keyword in the worthy list must cause _is_segmentation_worthy_error
        to return True. A mutation that removes any keyword will fail."""
        exc = ValueError(msg)
        assert RouteService._is_segmentation_worthy_error(exc) is True, (
            f"Keyword {keyword!r} must be detected as worthy"
        )

    # ── 7. Non-matching error → False ──
    def test_non_matching_error_returns_false(self):
        """An exception whose message contains no keywords must return False."""
        exc = ValueError("This is a completely unrelated error message")
        assert RouteService._is_segmentation_worthy_error(exc) is False

    # ── 8. Retryable HTTP error (500) → worthy; non-retryable (400) → not worthy ──
    def test_http_500_is_worthy(self):
        """HTTP 500 status should be detected as worthy via is_retryable_request_error."""
        import requests
        resp = mock.Mock()
        resp.status_code = 500
        exc = requests.exceptions.HTTPError(response=resp)
        assert RouteService._is_segmentation_worthy_error(exc) is True

    def test_http_400_is_not_worthy(self):
        """HTTP 400 status is NOT retryable, so should NOT be worthy."""
        import requests
        resp = mock.Mock()
        resp.status_code = 400
        exc = requests.exceptions.HTTPError(response=resp)
        assert RouteService._is_segmentation_worthy_error(exc) is False
