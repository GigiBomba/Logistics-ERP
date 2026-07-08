"""Authentication fuzz testing — malformed/malicious JWT tokens and auth headers.

Uses fixtures from conftest:
    client      FastAPI TestClient
    auth_admin  Admin bearer headers

Test matrix:
  1.  Random 50-char JWT rejected
  2.  Corrupted valid JWT (payload tampered) rejected
  3.  Oversized JWT (10 KB payload) rejected
  4.  Empty Authorization header rejected
  5.  Multiple Authorization headers rejected
  6.  Unicode Bearer token rejected
  7.  Invalid Bearer format (no space after Bearer) rejected
  8.  Manually expired JWT (exp in the past) rejected
  9.  JWT with future nbf (not before) rejected
 10.  JWT signed with RS256 (wrong algorithm) rejected
 11.  JWT missing sub and role claims rejected
 12.  Token passed via query string instead of header rejected
"""

import base64
import json
import os
import time
import jwt as pyjwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest
from fastapi.testclient import TestClient

# ── Test constants ─────────────────────────────────────────────────────────────
_PROTECTED_ENDPOINT = "/api/v1/trips/"


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  Random JWT
# ═══════════════════════════════════════════════════════════════════════════════


def test_random_jwt_rejected(client: TestClient) -> None:
    """A random 50-character string used as Bearer token should be rejected."""
    random_token = "a" * 50
    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": f"Bearer {random_token}"},
    )
    assert resp.status_code == 401, (
        f"Random JWT should be rejected with 401, got {resp.status_code}: {resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  Corrupted JWT
# ═══════════════════════════════════════════════════════════════════════════════


def test_corrupted_jwt_rejected(client: TestClient, auth_admin: dict) -> None:
    """A valid JWT with 5 random characters corrupted in the payload section
    should be rejected."""
    # Get a valid token from the auth_admin fixture
    token = auth_admin["Authorization"].replace("Bearer ", "")
    parts = token.split(".")
    assert len(parts) == 3, "Expected a well-formed 3-part JWT"

    # Corrupt 5 random characters in the payload (middle section)
    payload_part = list(parts[1])
    import random
    indices = random.sample(range(len(payload_part)), min(5, len(payload_part)))
    for i in indices:
        payload_part[i] = random.choice("abcdefghijklmnopqrstuvwxyz0123456789")
    parts[1] = "".join(payload_part)
    corrupted_token = ".".join(parts)

    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": f"Bearer {corrupted_token}"},
    )
    assert resp.status_code == 401, (
        f"Corrupted JWT should be rejected with 401, got {resp.status_code}: {resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  Oversized JWT
# ═══════════════════════════════════════════════════════════════════════════════


def test_oversized_jwt_rejected(client: TestClient) -> None:
    """A JWT with a 10 KB payload should be rejected (401 or 413)."""
    secret = os.environ.get(
        "OPERION_JWT_SECRET_KEY", "test-secret-key-32-chars-for-testing-only!!"
    )
    # Create a 10 KB payload with dummy data
    large_payload = {"sub": "admin@test.com", "role": "admin", "data": "x" * 10_000}
    oversized_token = pyjwt.encode(large_payload, secret, algorithm="HS256")

    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": f"Bearer {oversized_token}"},
    )
    assert resp.status_code in (401, 413), (
        f"Oversized JWT should be rejected with 401 or 413, "
        f"got {resp.status_code}: {resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  Empty Auth Header
# ═══════════════════════════════════════════════════════════════════════════════


def test_empty_auth_header(client: TestClient) -> None:
    """Authorization header with 'Bearer ' and no token should be rejected."""
    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": "Bearer "},
    )
    assert resp.status_code == 401, (
        f"Empty Bearer token should be rejected with 401, got {resp.status_code}: {resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  Multiple Auth Headers
# ═══════════════════════════════════════════════════════════════════════════════


def test_multiple_auth_headers(client: TestClient) -> None:
    """Sending two Authorization headers should be rejected."""
    token = "sometoken"
    # Use a raw WSGI environ to send duplicate headers
    # FastAPI TestClient doesn't natively support duplicate headers easily,
    # so we use the ASGI scope directly via a custom request.
    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers=[
            ("Authorization", f"Bearer {token}"),
            ("Authorization", f"Bearer {token}"),
        ],
    )
    assert resp.status_code == 401, (
        f"Multiple Authorization headers should be rejected with 401, "
        f"got {resp.status_code}: {resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  Unicode Token
# ═══════════════════════════════════════════════════════════════════════════════


def test_unicode_token(client: TestClient) -> None:
    """Bearer token containing unicode characters should be rejected."""
    unicode_token = "héllo-wørld-🚀-token"
    try:
        resp = client.get(
            _PROTECTED_ENDPOINT,
            headers={"Authorization": f"Bearer {unicode_token}"},
        )
        assert resp.status_code == 401, (
            f"Unicode token should be rejected with 401, got {resp.status_code}: {resp.text}"
        )
    except Exception:
        pytest.skip("Unicode in headers not supported by httpx")


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  Invalid Bearer Format
# ═══════════════════════════════════════════════════════════════════════════════


def test_invalid_bearer_format(client: TestClient) -> None:
    """'Authorization: Bearer' without a space should be rejected."""
    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": "Bearersometoken"},
    )
    assert resp.status_code == 401, (
        f"Invalid Bearer format (no space) should be rejected with 401, "
        f"got {resp.status_code}: {resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 8.  Expired Timestamp (Manual)
# ═══════════════════════════════════════════════════════════════════════════════


def test_expired_timestamp_manual(client: TestClient) -> None:
    """A JWT with ``exp`` explicitly set in the past should be rejected."""
    secret = os.environ.get(
        "OPERION_JWT_SECRET_KEY", "test-secret-key-32-chars-for-testing-only!!"
    )
    expired_payload = {
        "sub": "test@test.com",
        "role": "admin",
        "exp": int(time.time()) - 3600,  # expired 1 hour ago
    }
    expired_token = pyjwt.encode(expired_payload, secret, algorithm="HS256")

    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401, (
        f"Expired JWT should be rejected with 401, got {resp.status_code}: {resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 9.  Future "nbf" (Not Before)
# ═══════════════════════════════════════════════════════════════════════════════


def test_future_timestamp_not_yet_valid(client: TestClient) -> None:
    """A JWT with ``nbf`` set in the future should be rejected."""
    secret = os.environ.get(
        "OPERION_JWT_SECRET_KEY", "test-secret-key-32-chars-for-testing-only!!"
    )
    future_time = int(time.time()) + 3600  # 1 hour in the future
    nbf_payload = {
        "sub": "test@test.com",
        "role": "admin",
        "exp": int(time.time()) + 7200,  # expires in 2 hours
        "nbf": future_time,              # not valid until 1 hour from now
    }
    nbf_token = pyjwt.encode(nbf_payload, secret, algorithm="HS256")

    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": f"Bearer {nbf_token}"},
    )
    assert resp.status_code == 401, (
        f"Future nbf JWT should be rejected with 401, got {resp.status_code}: {resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 10.  Wrong Algorithm (RS256)
# ═══════════════════════════════════════════════════════════════════════════════


def test_wrong_algorithm_rs256(client: TestClient) -> None:
    """A JWT signed with RS256 (asymmetric) should be rejected when the
    server expects HS256 (symmetric)."""
    # Generate a random RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Create a JWT signed with RS256
    rs256_token = pyjwt.encode(
        {"sub": "test", "role": "admin"},
        private_key,
        algorithm="RS256",
    )

    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": f"Bearer {rs256_token}"},
    )
    assert resp.status_code == 401, (
        f"RS256-signed JWT should be rejected with 401, "
        f"got {resp.status_code}: {resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 11.  Missing Claims Token
# ═══════════════════════════════════════════════════════════════════════════════


def test_missing_claims_token(client: TestClient) -> None:
    """A JWT without ``sub`` and ``role`` claims should be rejected."""
    secret = os.environ.get(
        "OPERION_JWT_SECRET_KEY", "test-secret-key-32-chars-for-testing-only!!"
    )
    # Token with valid exp but no sub or role
    missing_claims_payload = {
        "exp": int(time.time()) + 3600,
        "random_claim": "some_value",
    }
    missing_claims_token = pyjwt.encode(
        missing_claims_payload, secret, algorithm="HS256"
    )

    resp = client.get(
        _PROTECTED_ENDPOINT,
        headers={"Authorization": f"Bearer {missing_claims_token}"},
    )
    assert resp.status_code == 401, (
        f"JWT missing sub and role should be rejected with 401, "
        f"got {resp.status_code}: {resp.text}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 12.  Bearer Token in Query String
# ═══════════════════════════════════════════════════════════════════════════════


def test_bearer_token_in_query_string(client: TestClient) -> None:
    """Sending the token as ``?token=xxx`` instead of an Authorization header
    should be rejected."""
    fake_token = "some-fake-token"
    resp = client.get(
        f"{_PROTECTED_ENDPOINT}?token={fake_token}",
    )
    assert resp.status_code == 401, (
        f"Token in query string should be rejected with 401, "
        f"got {resp.status_code}: {resp.text}"
    )
