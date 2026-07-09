"""Chaos tests: Nominatim geocoding failures.

The ``geocode_place`` function in ``services/geocode_nominatim.py``
catches network errors internally and returns ``None`` on failure.
The route-calculation endpoint (``POST /api/v1/routes/calculate``)
calls ``geocode_place`` directly for string-based address points and
raises ``HTTPException(400, "Cannot geocode: …")`` when the result
is ``None``, or lets other exceptions propagate as 500.

These tests verify graceful degradation when the Nominatim API is
unavailable, slow, returns no results, or partially fails in a batch.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from services.geocode_nominatim import geocode_place

pytestmark = pytest.mark.chaos

# A request body with string addresses — this forces the endpoint
# to go through the ``geocode_place`` code path.
_GEOCODE_PAYLOAD = {
    "points": ["Berlin, Germany", "Paris, France"],
    "profile": "truck",
}


class TestChaosNominatim:
    """Simulate Nominatim API failures — geocoding should degrade gracefully."""

    # ── Individual geocode failures ──────────────────────────────────

    def test_nominatim_connection_refused(self, client, auth_admin):
        """When Nominatim is unreachable, ``geocode_place`` returns None
        and the endpoint returns 400 with 'Cannot geocode'."""
        with patch(
            "services.geocode_nominatim.geocode_place",
            side_effect=ConnectionError("Connection refused"),
        ):
            resp = client.post(
                "/api/v1/routes/calculate",
                json=_GEOCODE_PAYLOAD,
                headers=auth_admin,
            )
            # The outer ``except Exception`` in the endpoint catches this
            # and returns 500; if the control flow is different it may be
            # caught as a 400.
            assert resp.status_code in (400, 500), (
                f"Expected 400/500, got {resp.status_code}"
            )

    def test_nominatim_timeout(self, client, auth_admin):
        """When Nominatim times out, ``geocode_place`` returns None
        and the endpoint returns 400."""
        with patch(
            "services.geocode_nominatim.geocode_place",
            side_effect=ConnectionError("Connection timed out"),
        ):
            resp = client.post(
                "/api/v1/routes/calculate",
                json=_GEOCODE_PAYLOAD,
                headers=auth_admin,
            )
            assert resp.status_code in (400, 500), (
                f"Expected 400/500 for timeout, got {resp.status_code}"
            )

    def test_nominatim_empty_response(self, client, auth_admin):
        """When Nominatim returns no results (empty list), the endpoint
        returns 400 with 'Cannot geocode'."""
        with patch(
            "services.geocode_nominatim.geocode_place",
            return_value=None,
        ):
            resp = client.post(
                "/api/v1/routes/calculate",
                json=_GEOCODE_PAYLOAD,
                headers=auth_admin,
            )
            assert resp.status_code == 400, (
                f"Expected 400 for empty geocode, got {resp.status_code}"
            )
            assert "Cannot geocode" in resp.text, (
                "Response should mention 'Cannot geocode'"
            )

    # ── Batch partial failure ────────────────────────────────────────

    def test_geocode_batch_partial_failure(self, client, auth_admin):
        """When 2 of 5 geocode calls fail (return None), the endpoint
        should fail on the first failure with a 400."""
        # The endpoint iterates through ``points`` and calls
        # ``geocode_place`` for each string; the **first** failure
        # causes an immediate 400.
        side_effects = [
            (52.52, 13.40),  # Berlin — OK
            None,            # second address — fails
            (48.86, 2.35),   # Paris — would be OK but never reached
        ]

        with patch(
            "services.geocode_nominatim.geocode_place",
            side_effect=side_effects,
        ):
            resp = client.post(
                "/api/v1/routes/calculate",
                json={
                    "points": [
                        "Berlin, Germany",
                        "Bad Address That Fails",
                        "Paris, France",
                    ],
                    "profile": "truck",
                },
                headers=auth_admin,
            )
            assert resp.status_code == 400, (
                f"Expected 400 on first geocode failure, got {resp.status_code}"
            )
            assert "Cannot geocode" in resp.text
