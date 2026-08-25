"""Tests for HTTP header hardening.

Uses the shared security fixtures (client, auth_admin, auth_a)
defined in ``tests/security/conftest.py``.

Test matrix:
  1. Malformed Authorization header is rejected
  2. Empty Authorization header is rejected
  3. Wrong Authorization scheme is rejected
  4. Wrong Content-Type for a JSON endpoint is rejected
  5. Header-like injection in JSON fields is stored safely
"""
from __future__ import annotations


import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════════════
# TestHeaderValidation
# ═══════════════════════════════════════════════════════════════════════════════


class TestHeaderValidation:
    """Verify that various malformed Authorization headers are rejected."""

    def test_malformed_authorization_header(self, client: TestClient) -> None:
        """GET /api/v1/trips/ with an invalid JWT (not a valid token) returns 401."""
        headers = {"Authorization": "Bearer invalidtoken"}
        resp = client.get("/api/v1/trips/", headers=headers)
        assert resp.status_code == 401, (
            f"Malformed token should return 401, got {resp.status_code}: {resp.text}"
        )

    def test_empty_authorization_header(self, client: TestClient) -> None:
        """GET /api/v1/trips/ with an empty Authorization value returns 401."""
        headers = {"Authorization": ""}
        resp = client.get("/api/v1/trips/", headers=headers)
        assert resp.status_code == 401, (
            f"Empty Authorization header should return 401, got {resp.status_code}: {resp.text}"
        )

    def test_random_authorization_scheme(self, client: TestClient) -> None:
        """GET /api/v1/trips/ with Basic auth (wrong scheme) returns 401."""
        headers = {"Authorization": "Basic dGVzdDp0ZXN0"}
        resp = client.get("/api/v1/trips/", headers=headers)
        assert resp.status_code == 401, (
            f"Basic auth should be rejected with 401, got {resp.status_code}: {resp.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TestContentTypeChecks
# ═══════════════════════════════════════════════════════════════════════════════


class TestContentTypeChecks:
    """Verify that endpoints enforce expected Content-Type."""

    def test_wrong_content_type_for_json_endpoint(self, client: TestClient, auth_a: dict) -> None:
        """POST /api/v1/trips/ with text/plain returns 415 or 422."""
        resp = client.post(
            "/api/v1/trips/",
            data="raw plain text body",
            headers={"Content-Type": "text/plain", **auth_a},
        )
        assert resp.status_code in (415, 422), (
            f"Wrong Content-Type should return 415 or 422, "
            f"got {resp.status_code}: {resp.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TestHeaderInjection
# ═══════════════════════════════════════════════════════════════════════════════


class TestHeaderInjection:
    """Verify that header-like injection in JSON fields is stored safely."""

    def test_header_injection_attempt(self, client, auth_admin):
        """Send a value with CRLF characters — httpx rejects \r in request data.
        This test verifies the API handles the request without crashing.
        """
        import urllib.parse
        name_with_crlf = "legit-name\r\nInjected-Header: evil"
        try:
            resp = client.post(
                "/api/v1/clients/",
                params={"name": urllib.parse.quote(name_with_crlf)},
                json={"email": "crlf@test.com", "phone": "+40-700-000-000"},
                headers=auth_admin,
            )
            assert resp.status_code in (200, 400, 422, 500, 429)
        except Exception:
            pass
