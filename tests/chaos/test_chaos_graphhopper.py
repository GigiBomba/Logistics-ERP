"""Chaos tests: GraphHopper API failures, retry exhaustion, transient errors.

The ``GraphHopperClient.route()`` method has built-in retry logic
(``MAX_ROUTE_RETRIES = 5``).  These tests verify that:

- Network-level errors (ConnectionError, Timeout) result in a 500
- HTTP-level transient errors (502, 503) are retried and eventually
  return 500 if all retries are exhausted
- A transient failure followed by a success works correctly
- Empty / malformed responses are handled gracefully
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.route_service import GraphHopperClient

pytestmark = pytest.mark.chaos


class TestChaosGraphhopper:
    """Simulate GraphHopper API failures — route calculation should degrade gracefully."""

    PAYLOAD_2PT = {
        "points": [
            {"lat": 45.0, "lng": 15.0},
            {"lat": 46.0, "lng": 16.0},
        ],
        "profile": "truck",
    }

    PAYLOAD_3PT = {
        "points": [
            {"lat": 45.0, "lng": 15.0},
            {"lat": 46.0, "lng": 16.0},
            {"lat": 47.0, "lng": 17.0},
        ],
        "profile": "truck",
    }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _gh_success_response() -> MagicMock:
        """A mock ``requests.Response`` that ``GraphHopperClient.route``
        considers a valid result."""
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 200
        resp.text = json.dumps({
            "paths": [{
                "distance": 123000,
                "time": 3600000,
                "points": {"coordinates": [[15.0, 45.0], [16.0, 46.0]]},
            }],
        })
        resp.json.return_value = json.loads(resp.text)
        resp.raise_for_status.return_value = None
        return resp

    @staticmethod
    def _gh_error_response(status_code: int = 503) -> MagicMock:
        """A mock ``requests.Response`` with a server-error status code."""
        resp = MagicMock(spec=requests.Response)
        resp.status_code = status_code
        resp.text = json.dumps({"message": f"Upstream error {status_code}"})
        resp.json.return_value = {"message": f"Upstream error {status_code}"}

        def _raise_for_status():
            raise requests.exceptions.HTTPError(
                f"{status_code} Server Error", response=resp,
            )

        resp.raise_for_status.side_effect = _raise_for_status
        return resp

    # ------------------------------------------------------------------
    # Tests 1-5: mock at ``GraphHopperClient.route`` level (retry logic
    # is bypassed — we only verify the callers handle exceptions).
    # ------------------------------------------------------------------

    def test_gh_connection_refused(self, client, auth_admin):
        """When GraphHopper is unreachable, POST /routes/calculate returns 500."""
        with patch.object(GraphHopperClient, "route") as mock_route:
            mock_route.side_effect = ConnectionError("Connection refused")
            resp = client.post(
                "/api/v1/routes/calculate",
                json=self.PAYLOAD_2PT,
                headers=auth_admin,
            )
            assert resp.status_code == 500

    def test_gh_timeout(self, client, auth_admin):
        """When GraphHopper times out, verify 500 response."""
        with patch.object(GraphHopperClient, "route") as mock_route:
            mock_route.side_effect = requests.exceptions.Timeout(
                "Connection timed out",
            )
            resp = client.post(
                "/api/v1/routes/calculate",
                json=self.PAYLOAD_2PT,
                headers=auth_admin,
            )
            assert resp.status_code == 500

    def test_gh_5xx_response(self, client, auth_admin):
        """When GraphHopper returns 502 Bad Gateway, verify 500."""
        with patch.object(GraphHopperClient, "route") as mock_route:
            mock_route.side_effect = requests.exceptions.HTTPError(
                "502 Server Error",
            )
            resp = client.post(
                "/api/v1/routes/calculate",
                json=self.PAYLOAD_2PT,
                headers=auth_admin,
            )
            assert resp.status_code == 500

    def test_gh_malformed_json(self, client, auth_admin):
        """When GraphHopper returns non-JSON, verify 500."""
        with patch.object(GraphHopperClient, "route") as mock_route:
            mock_route.side_effect = json.JSONDecodeError(
                "Expecting value", "", 0,
            )
            resp = client.post(
                "/api/v1/routes/calculate",
                json=self.PAYLOAD_2PT,
                headers=auth_admin,
            )
            assert resp.status_code == 500

    def test_gh_empty_response(self, client, auth_admin):
        """When GraphHopper returns ``paths`` empty, verify 400/500."""
        with patch.object(GraphHopperClient, "route") as mock_route:
            mock_route.side_effect = ValueError("No route found")
            resp = client.post(
                "/api/v1/routes/calculate",
                json=self.PAYLOAD_2PT,
                headers=auth_admin,
            )
            assert resp.status_code in (400, 500)

    # ------------------------------------------------------------------
    # Tests 6-7: mock at ``_route_post`` level so the retry loop inside
    # ``GraphHopperClient.route`` is exercised.
    # Use 3 points (-> POST mode) so ``_route_post`` is always called.
    # ------------------------------------------------------------------

    def test_gh_transient_then_success(self, client, auth_admin):
        """First 3 calls fail with 503, 4th succeeds — verify retry works."""
        success = self._gh_success_response()
        failure = self._gh_error_response(503)

        with patch.object(GraphHopperClient, "_route_post") as mock_post:
            mock_post.side_effect = [failure, failure, failure, success]
            resp = client.post(
                "/api/v1/routes/calculate",
                json=self.PAYLOAD_3PT,
                headers=auth_admin,
            )
            assert resp.status_code == 200, (
                f"Expected 200 after retry recovery, got {resp.status_code}"
            )
            # At least 4 calls to _route_post (3 failures + 1 success)
            assert mock_post.call_count >= 4

    def test_gh_all_retries_exhausted(self, client, auth_admin):
        """All retry attempts fail with 503 — verify 500 + message."""
        failure = self._gh_error_response(503)

        with patch.object(GraphHopperClient, "_route_post") as mock_post:
            mock_post.return_value = failure
            resp = client.post(
                "/api/v1/routes/calculate",
                json=self.PAYLOAD_3PT,
                headers=auth_admin,
            )
            assert resp.status_code == 500, (
                f"Expected 500 after retry exhaustion, got {resp.status_code}"
            )
            # Should have been called MAX_ROUTE_RETRIES times (5)
            assert mock_post.call_count == 5
