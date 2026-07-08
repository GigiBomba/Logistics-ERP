"""Tests for authentication endpoints and JWT security.

Uses the shared security fixtures (client, admin_token, auth_admin)
defined in ``tests/security/conftest.py``.

Test matrix:
  1. Correct credentials return token pair
  2. Wrong password returns 401 (no email leakage)
  3. Unknown email returns 401 (same error as wrong password)
  4. Brute-force lockout after 5 failures
  5. Expired JWT raises PyJWTError on decode
  6. Tampered JWT rejected by protected endpoint
  7. ``alg: none`` JWT rejected by protected endpoint
  8. Refresh token rotation (reuse blocked)
  9. Logout invalidates refresh token
 10. Admin env-var auth path also triggers lockout
"""

import base64
import json
import time
from datetime import timedelta

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from backend.api.v1.auth import _clear_lockout, _failed_attempts
from backend.config import BackendSettings
from backend.security import create_access_token, decode_access_token

# ── Test constants ─────────────────────────────────────────────────────────────
ADMIN_EMAIL = "admin-a@test.com"
ADMIN_PW = "test-admin-pw-123"
WRONG_PW = "this-is-definitely-wrong"
UNKNOWN_EMAIL = "nobody@unknown.test"

# Use a lightweight protected endpoint for token rejection tests.
# /api/v1/admin/diagnostics is gated by require_admin → get_current_user →
# decode_access_token, so it exercises the full auth chain.
_PROTECTED_ENDPOINT = "/api/v1/admin/diagnostics"


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  Correct credentials
# ═══════════════════════════════════════════════════════════════════════════════


def test_correct_credentials_succeed(client: TestClient) -> None:
    """POST valid credentials to /api/v1/auth/token returns 200 with tokens."""
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body, "Response missing access_token"
    assert "refresh_token" in body, "Response missing refresh_token"
    assert body.get("token_type") == "bearer"


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  Wrong password
# ═══════════════════════════════════════════════════════════════════════════════


def test_wrong_password_fails(client: TestClient) -> None:
    """POST with wrong password returns 401 without revealing email existence."""
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": ADMIN_EMAIL, "password": WRONG_PW},
    )
    assert resp.status_code == 401
    detail = resp.json().get("detail", "").lower()
    assert "admin" not in detail, "Error message leaked 'admin'"
    assert "email" not in detail, "Error message leaked 'email'"
    assert "invalid" in detail, (
        "Error message does not match expected generic phrasing"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  Unknown email
# ═══════════════════════════════════════════════════════════════════════════════


def test_wrong_email_fails(client: TestClient) -> None:
    """POST with unknown email returns 401 with the same generic message."""
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": UNKNOWN_EMAIL, "password": "irrelevant"},
    )
    assert resp.status_code == 401
    detail = resp.json().get("detail", "").lower()
    # The message should be identical in style to the wrong-password case
    # (e.g. "Incorrect email or password.") and must not hint at which
    # field is wrong.
    assert "email" not in detail, "Error message should not mention 'email'"
    assert "password" not in detail, "Error message should not mention 'password' (blaming one field)"


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  Brute-force lockout
# ═══════════════════════════════════════════════════════════════════════════════


def test_lockout_blocks_after_5_failures(client: TestClient) -> None:
    """5 wrong attempts then a correct one should return 429."""
    _clear_lockout(ADMIN_EMAIL)

    try:
        # 5 failed attempts
        for i in range(5):
            resp = client.post(
                "/api/v1/auth/token",
                data={"username": ADMIN_EMAIL, "password": WRONG_PW},
            )
            assert resp.status_code == 401, (
                f"Attempt {i + 1} should be 401, got {resp.status_code}"
            )

        # 6th attempt — correct password, but lockout should block it
        resp = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
        )
        assert resp.status_code == 429, (
            f"Lockout should return 429, got {resp.status_code}: {resp.text}"
        )
        # Verify the Retry-After header is present
        assert "Retry-After" in resp.headers, "Missing Retry-After header in lockout response"
    finally:
        _clear_lockout(ADMIN_EMAIL)


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  Expired JWT
# ═══════════════════════════════════════════════════════════════════════════════


def test_jwt_expires() -> None:
    """Token with ``exp`` in the past should raise ``PyJWTError`` on decode."""
    expired_token = create_access_token(
        data={"sub": "test@test.com", "role": "admin"},
        expires_delta=timedelta(seconds=-10),  # 10 seconds in the past
    )

    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token(expired_token)


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  Tampered JWT
# ═══════════════════════════════════════════════════════════════════════════════


def test_tampered_jwt_rejected(client: TestClient, admin_token: str) -> None:
    """Flipping one character in the signature causes 401 on a protected endpoint."""
    parts = admin_token.split(".")
    assert len(parts) == 3, "Expected a well-formed 3-part JWT"

    # Flip the first character of the signature
    sig = list(parts[2])
    sig[0] = "a" if sig[0] != "a" else "b"
    parts[2] = "".join(sig)
    tampered = ".".join(parts)

    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": f"Bearer {tampered}"},
    )
    assert resp.status_code == 401, (
        f"Tampered token should be rejected with 401, got {resp.status_code}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  ``alg: none`` attack
# ═══════════════════════════════════════════════════════════════════════════════


def test_alg_none_rejected(client: TestClient) -> None:
    """JWT with ``alg: none`` header is rejected by the protected endpoint."""
    # Manually craft a token with algorithm "none".
    # The server's decode_access_token uses algorithms=[settings.jwt_algorithm]
    # (HS256), so PyJWT will reject a token whose header says "none".
    header_b64 = _b64encode({"alg": "none", "typ": "JWT"})
    payload_b64 = _b64encode({
        "sub": ADMIN_EMAIL,
        "role": "admin",
        "exp": 9_999_999_999,
    })
    none_token = f"{header_b64}.{payload_b64}."

    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": f"Bearer {none_token}"},
    )
    assert resp.status_code == 401, (
        f"alg:none token should be rejected with 401, got {resp.status_code}"
    )


def _b64encode(data: dict) -> str:
    """URL-safe base64 encode a JSON-serialisable dict (no padding)."""
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).rstrip(b"=").decode()


# ═══════════════════════════════════════════════════════════════════════════════
# 8.  Refresh token rotation
# ═══════════════════════════════════════════════════════════════════════════════


def test_refresh_rotation(client: TestClient) -> None:
    """Using a refresh token a second time fails (rotation deletes old token)."""
    # Obtain a fresh token pair
    login_resp = client.post(
        "/api/v1/auth/token",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # First use — should succeed
    first = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert first.status_code == 200, f"First refresh should succeed: {first.text}"
    first_body = first.json()
    assert "access_token" in first_body
    assert "refresh_token" in first_body  # New rotated token

    # Second use with the **original** refresh token — should fail
    second = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert second.status_code == 401, (
        f"Reused refresh token should be rejected with 401, got {second.status_code}: {second.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 9.  Logout invalidates refresh
# ═══════════════════════════════════════════════════════════════════════════════


def test_logout_invalidates_refresh(client: TestClient) -> None:
    """After logout, using the refresh token at /refresh returns 401."""
    # Obtain a fresh token pair
    login_resp = client.post(
        "/api/v1/auth/token",
        data={"username": ADMIN_EMAIL, "password": ADMIN_PW},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # Logout with the refresh token
    logout_resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200, f"Logout should succeed: {logout_resp.text}"

    # Attempt to use the now-revoked refresh token
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401, (
        f"Refresh after logout should be 401, got {refresh_resp.status_code}: {refresh_resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 10.  Admin auth lockout
# ═══════════════════════════════════════════════════════════════════════════════


def test_admin_auth_gets_lockout_too(client: TestClient) -> None:
    """The admin env-var auth path also triggers brute-force lockout."""
    _clear_lockout(ADMIN_EMAIL)

    try:
        # 5 failed admin login attempts
        for i in range(5):
            resp = client.post(
                "/api/v1/auth/token",
                data={"username": ADMIN_EMAIL, "password": WRONG_PW},
            )
            assert resp.status_code == 401, (
                f"Admin attempt {i + 1} should be 401, got {resp.status_code}"
            )

        # 6th attempt — also wrong, should be blocked with 429
        resp = client.post(
            "/api/v1/auth/token",
            data={"username": ADMIN_EMAIL, "password": "yet-another-wrong-pw"},
        )
        assert resp.status_code == 429, (
            f"Admin lockout should return 429, got {resp.status_code}: {resp.text}"
        )
        assert "Retry-After" in resp.headers, "Missing Retry-After header"
    finally:
        _clear_lockout(ADMIN_EMAIL)
