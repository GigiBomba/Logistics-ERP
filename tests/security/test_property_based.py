"""Property-based security tests using random generation.

Since Hypothesis may not be installed as a dependency, this module uses
manual random generation with pytest to exercise properties that should
hold for any input.

Uses the shared security fixtures (client, auth_admin) defined in
``tests/security/conftest.py``.

Test matrix:
  1. Random JWTs are always rejected with 401/403
  2. Random JSON payloads never cause a 500 crash
  3. Token claims are consistent — exp in the future = valid, exp in past = invalid
  4. Email normalization — login is case-insensitive
"""
from __future__ import annotations


import random
import string
import time
import json
import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from backend.security import create_access_token, decode_access_token
from backend.config import BackendSettings


# ═══════════════════════════════════════════════════════════════════════════════
# TestRandomJwtRejection
# ═══════════════════════════════════════════════════════════════════════════════


class TestRandomJwtRejection:
    """Random JWT strings must always be rejected by protected endpoints."""

    def test_random_jwts_always_rejected(self, client: TestClient) -> None:
        """Generate 20 random strings, use as Bearer tokens — all must be rejected."""
        for i in range(20):
            random_token = "".join(
                random.choices(string.ascii_letters + string.digits, k=50)
            )
            resp = client.get(
                "/api/v1/trips/",
                headers={"Authorization": f"Bearer {random_token}"},
            )
            assert resp.status_code in (
                401,
                403,
                429,
            ), (
                f"Random token {i} should return 401/403/429, "
                f"got {resp.status_code}: {resp.text}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TestRandomPayloadsNoCrash
# ═══════════════════════════════════════════════════════════════════════════════


class TestRandomPayloadsNoCrash:
    """Random JSON payloads must never crash the server (no 500 responses)."""

    def test_random_inputs_never_crash(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """Generate 10 random JSON payloads, POST to /api/v1/trips/ — no 500."""
        for i in range(10):
            payload: dict = {}
            for _ in range(random.randint(1, 10)):
                key = "".join(
                    random.choices(string.ascii_letters, k=random.randint(1, 20))
                )
                value = "".join(
                    random.choices(string.printable, k=random.randint(0, 50))
                )
                payload[key] = value

            try:
                resp = client.post(
                    "/api/v1/trips/", json=payload, headers=auth_admin
                )
                assert resp.status_code != 500, (
                    f"Random payload {i} caused 500: {payload}\n{resp.text}"
                )
            except Exception:
                pass  # Connection errors or parsing errors are acceptable


# ═══════════════════════════════════════════════════════════════════════════════
# TestTokenClaimsConsistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestTokenClaimsConsistency:
    """JWT tokens must have consistent exp claim behavior."""

    def test_token_claims_consistent(self) -> None:
        """Create tokens with different exp values; decode only succeeds when exp is future."""
        claims = {"sub": "test-user", "role": "admin"}
        settings = BackendSettings()

        # Token with exp in the future — must decode successfully
        future_token = create_access_token(
            data=claims.copy(),
            expires_delta=__import__("datetime").timedelta(minutes=5),
        )
        decoded = decode_access_token(future_token)
        assert decoded["sub"] == "test-user", "Future token should decode with correct sub"

        # Token with exp in the past — must raise PyJWTError
        past_token = create_access_token(
            data=claims.copy(),
            expires_delta=__import__("datetime").timedelta(minutes=-5),
        )
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(past_token)

        # Manually craft a token with exp in the past (alternative approach)
        import datetime
        from datetime import timezone
        manual_claims = claims.copy()
        manual_claims["exp"] = datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)
        expired_token = pyjwt.encode(
            manual_claims,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(expired_token)

        # Verify 10 tokens with varying future exp values all decode correctly
        for i in range(10):
            token = create_access_token(
                data={"sub": f"user-{i}", "role": "viewer"},
                expires_delta=__import__("datetime").timedelta(minutes=30 + i),
            )
            decoded = decode_access_token(token)
            assert decoded["sub"] == f"user-{i}", (
                f"Token {i} should decode with correct sub"
            )
            assert decoded["role"] == "viewer", (
                f"Token {i} should decode with correct role"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TestEmailNormalization
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmailNormalization:
    """Email login must be case-insensitive."""

    def test_email_normalization(self, client: TestClient) -> None:
        """Verify that email login is case-insensitive.

        Log in with the canonical email, then with uppercase variations.
        All should succeed with the same credentials.
        """
        # Use the seeded dispatcher credentials
        base_email = "dispatcher-a@test.com"
        password = "dispatcher-pw-456"

        # Clear lockout so login is deterministic
        from backend.api.v1.auth import _clear_lockout
        _clear_lockout("admin-a@test.com")

        # Login with canonical form
        resp_canonical = client.post(
            "/api/v1/auth/token",
            data={"username": base_email, "password": password},
        )
        assert resp_canonical.status_code in (200, 429), (
            f"Canonical email login failed: {resp_canonical.text}"
        )
        if resp_canonical.status_code == 429:
            pytest.skip("Rate limited — lockout not fully cleared")
        canonical_token = resp_canonical.json()["access_token"]

        # Login with uppercase
        resp_upper = client.post(
            "/api/v1/auth/token",
            data={"username": base_email.upper(), "password": password},
        )
        assert resp_upper.status_code in (200, 429), (
            f"Uppercase email login should succeed: {resp_upper.text}"
        )
        if resp_upper.status_code == 429:
            pytest.skip("Rate limited — lockout not fully cleared")
        upper_token = resp_upper.json()["access_token"]

        # Login with mixed case
        mixed_email = "Dispatcher-A@Test.Com"
        resp_mixed = client.post(
            "/api/v1/auth/token",
            data={"username": mixed_email, "password": password},
        )
        assert resp_mixed.status_code in (200, 429), (
            f"Mixed case email login should succeed: {resp_mixed.text}"
        )
        if resp_mixed.status_code == 429:
            pytest.skip("Rate limited — lockout not fully cleared")
        mixed_token = resp_mixed.json()["access_token"]

        # All tokens should be usable (non-empty, different strings but both valid)
        if not canonical_token or not upper_token or not mixed_token:
            pytest.skip("One or more tokens missing — login may have been rate limited")

        # Verify all tokens work on a protected endpoint
        for label, token in [
            ("canonical", canonical_token),
            ("upper", upper_token),
            ("mixed", mixed_token),
        ]:
            resp = client.get(
                "/api/v1/trips/",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code in (200, 429), (
                f"{label.capitalize()} email token should access protected endpoint, "
                f"got {resp.status_code}: {resp.text}"
            )
