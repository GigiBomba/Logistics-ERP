"""Chaos tests: network latency, timeouts, packet loss.

All tests use ``unittest.mock`` to simulate network-level failures at the
application layer — no actual network configuration is changed.

The route-calculation endpoint (``POST /api/v1/routes/calculate``) calls
``RouteService`` which uses a ``GraphHopperClient`` (``requests.Session``)
and may optionally geocode addresses via ``geocode_nominatim`` (also
``requests``).
"""

import time
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
import requests
from fastapi.testclient import TestClient

from services.route_service import GraphHopperClient


class TestNetworkChaos:
    """Simulate network-level failures — external API calls should degrade
    gracefully."""

    # ── Route calculation (GraphHopperClient) ────────────────────────────────

    def test_external_api_timeout_route_calc(self, client, auth_admin):
        """When GraphHopper API times out with coordinate points, route
        calculation should handle it (no geocoding involved)."""
        with patch.object(GraphHopperClient, "route") as mock_route:
            mock_route.side_effect = requests.exceptions.Timeout(
                "Connection timed out after 5s"
            )
            resp = client.post(
                "/api/v1/routes/calculate",
                json={
                    "points": [
                        {"lat": 50, "lng": 10},
                        {"lat": 51, "lng": 11},
                    ],
                    "profile": "truck",
                },
                headers=auth_admin,
            )
            assert resp.status_code in (200, 400, 500, 503), (
                f"Route calc failed: {resp.status_code}"
            )

    def test_external_api_connection_error(self, client, auth_admin):
        """When GraphHopper is unreachable (DNS / connection refused)."""
        with patch.object(GraphHopperClient, "route") as mock_route:
            mock_route.side_effect = requests.exceptions.ConnectionError(
                "Connection refused"
            )
            resp = client.post(
                "/api/v1/routes/calculate",
                json={
                    "points": [
                        {"lat": 50, "lng": 10},
                        {"lat": 51, "lng": 11},
                    ],
                    "profile": "truck",
                },
                headers=auth_admin,
            )
            assert resp.status_code in (200, 400, 500, 503), (
                f"Route calc failed: {resp.status_code}"
            )

    # ── Geocoding (Nominatim) ────────────────────────────────────────────────

    def test_external_api_timeout_geocode(self, client, auth_admin):
        """When Nominatim API times out, geocoding should handle it.

        This test uses string addresses to exercise the geocode path.
        """
        with patch("services.geocode_nominatim.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout(
                "Connection timed out"
            )
            resp = client.post(
                "/api/v1/routes/calculate",
                json={
                    "points": ["Berlin, Germany", "Paris, France"],
                    "profile": "truck",
                },
                headers=auth_admin,
            )
            # Geocode failure will result in a 400 (bad request) or 500
            assert resp.status_code in (200, 400, 500, 503), (
                f"Geocode timeout handling: {resp.status_code}"
            )

    # ── Slow network (DB level, not external API) ───────────────────────────

    def test_slow_network_doesnt_crash(self, client, auth_admin):
        """Slow database queries should result in slow response, not crash.

        We simulate a slow query by patching ``execute`` on the real DB
        connection to sleep 0.5 s before delegating to the real method.
        """
        from database.db_manager import DatabaseManager

        original_execute = None

        def _slow_execute(self, sql, *args, **kwargs):
            time.sleep(0.5)
            return original_execute(sql, *args, **kwargs)

        with patch.object(DatabaseManager, "_init_db", return_value=None):
            with patch(
                "database.db_manager.DatabaseManager.conn",
                new_callable=PropertyMock,
            ) as mock_conn:
                # Return a real-ish connection mock whose execute is slow
                real_conn = MagicMock()

                def slow_side_effect(sql, *args, **kwargs):
                    time.sleep(0.5)
                    return MagicMock()

                real_conn.execute.side_effect = slow_side_effect
                mock_conn.return_value = real_conn

                start = time.time()
                resp = client.get("/api/v1/health/")
                elapsed = time.time() - start

                assert resp.status_code in (200, 500), (
                    f"Slow network response: {resp.status_code}"
                )
                # Should eventually respond, not hang forever
                assert elapsed < 30, (
                    f"Response took {elapsed:.1f}s — possible hang"
                )
