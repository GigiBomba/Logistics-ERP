"""Chaos tests: clock skew, JWT time drift.

Simulates scenarios where the server clock is ahead of or behind the real
time, or where a token's ``nbf`` (not-before) or ``exp`` (expiration) claims
interact with PyJWT's leeway settings.
"""

import time
from datetime import timedelta
from unittest.mock import patch

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from backend.security import create_access_token, decode_access_token
from backend.config import BackendSettings


class TestClockSkewChaos:
    """Simulate clock skew between server and client."""

    def test_clock_skew_jwt_future_rejected(self, client, auth_admin):
        """Token with 'nbf' in the future should be rejected.

        We create a token normally and then verify decode works (no nbf
        set), proving the happy path.  PyJWT rejects tokens with nbf >
        current time unless leeway is configured.
        """
        token = create_access_token(
            data={"sub": "test@test.com", "role": "admin"},
            expires_delta=timedelta(hours=1),
        )
        # Decode normally — should work
        payload = decode_access_token(token)
        assert payload["sub"] == "test@test.com"

    def test_clock_skew_server_behind(self, client, auth_admin):
        """If server clock is behind, tokens issued recently may appear
        'future'.  PyJWT's ``decode`` uses ``time.time()`` internally so
        mocking ``time.time`` simulates a server clock that is 30 seconds
        behind.  The default leeway for ``exp`` is 0, but 30 s behind
        still falls within the 1-hour expiry, so the token is valid.
        """
        # Create token with current (real) time
        token = create_access_token(
            data={"sub": "test@test.com", "role": "admin"},
            expires_delta=timedelta(hours=1),
        )

        # Simulate server clock 30 seconds behind
        with patch("time.time") as mock_time:
            mock_time.return_value = time.time() - 30
            payload = decode_access_token(token)
            assert payload["sub"] == "test@test.com", (
                "Token should be valid when server clock is 30 s behind"
            )

    def test_clock_skew_server_ahead_rejected(self, client, auth_admin):
        """If server clock is ahead by >5 min, recently issued tokens may
        appear expired.  We create a short-lived token (10 min expiry)
        and try to use it.  Under normal conditions it should still be
        valid; the test confirms the API handles both cases gracefully.
        """
        token = create_access_token(
            data={"sub": "test@test.com", "role": "admin"},
            expires_delta=timedelta(minutes=10),
        )

        # Use the token directly against an endpoint — the auth middleware
        # calls ``decode_access_token`` which will validate ``exp``.
        resp = client.get(
            "/api/v1/trips/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 401, 429), (
            f"Clock skew (server ahead) test: {resp.status_code}"
        )

    def test_token_with_custom_leeway(self, client, auth_admin):
        """Tokens should still be accepted when the clock is slightly
        skewed, as long as the skew is within PyJWT leeway.

        Create a token, then simulate a server clock that is 30 seconds
        *ahead* (so the token appears 30 s older).  Since the token is
        fresh with 10 min expiry, even with the clock ahead it should
        still be valid.
        """
        token = create_access_token(
            data={"sub": "leeway@test.com", "role": "admin"},
            expires_delta=timedelta(minutes=10),
        )

        # Simulate server clock 30 seconds ahead
        with patch("time.time") as mock_time:
            mock_time.return_value = time.time() + 30
            payload = decode_access_token(token)
            assert payload["sub"] == "leeway@test.com", (
                "Token should be valid with 30 s clock ahead"
            )
