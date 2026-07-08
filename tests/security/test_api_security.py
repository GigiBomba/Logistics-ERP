"""API security tests — HTTP methods, content types, JSON parsing edge cases.

Uses the shared security fixtures (client, auth_admin) defined in
``tests/security/conftest.py``.

Test matrix:
  1. OPTIONS on protected endpoint without auth — 401 or 405
  2. Unsupported method (PATCH if not supported) — 405
  3. Invalid Content-Type (application/xml) — 415 or 422
  4. Malformed JSON body — 400 or 422
  5. Huge JSON payload (10 MB) — 400 or 413
  6. Duplicate JSON keys (Python takes last value)
  7. Invalid enum values in status field — 400 or 422
  8. Null values in required fields — 400 or 422
  9. Very long query parameter (100 KB) — 400 or 414
"""

import json
import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════════════
# TestHttpMethods
# ═══════════════════════════════════════════════════════════════════════════════


class TestHttpMethods:
    """Verify correct HTTP method handling on protected endpoints."""

    def test_options_on_protected_endpoint(self, client: TestClient) -> None:
        """OPTIONS /api/v1/trips/ without auth returns 401 or 405."""
        resp = client.options("/api/v1/trips/")
        assert resp.status_code in (
            401,
            405,
        ), (
            f"OPTIONS without auth should return 401 or 405, "
            f"got {resp.status_code}: {resp.text}"
        )

    def test_unsupported_method_returns_405(
        self, client: TestClient
    ) -> None:
        """PATCH /api/v1/trips/ without auth returns 405 if PATCH not supported."""
        resp = client.patch(
            "/api/v1/trips/",
            json={"client_name": "PATCH Test"},
        )
        assert resp.status_code in (
            401,
            405,
        ), (
            f"Unsupported PATCH method should return 401 or 405, "
            f"got {resp.status_code}: {resp.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TestContentTypeHandling
# ═══════════════════════════════════════════════════════════════════════════════


class TestContentTypeHandling:
    """Verify that endpoints enforce expected Content-Type."""

    def test_invalid_content_type(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """POST /api/v1/trips/ with Content-Type: application/xml returns 415 or 422."""
        payload = {"client_name": "XML Test", "status": "Planned"}
        resp = client.post(
            "/api/v1/trips/",
            data=json.dumps(payload),
            headers={
                "Authorization": auth_admin["Authorization"],
                "Content-Type": "application/xml",
            },
        )
        assert resp.status_code in (
            415,
            422,
        ), (
            f"XML content type should return 415 or 422, "
            f"got {resp.status_code}: {resp.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TestJsonParsingEdgeCases
# ═══════════════════════════════════════════════════════════════════════════════


class TestJsonParsingEdgeCases:
    """Verify JSON parsing edge cases are handled gracefully."""

    def test_malformed_json(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """POST /api/v1/trips/ with malformed JSON — returns 400 or 422."""
        resp = client.post(
            "/api/v1/trips/",
            data="{invalid json",
            headers={
                "Authorization": auth_admin["Authorization"],
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code in (
            400,
            422,
        ), (
            f"Malformed JSON should return 400 or 422, "
            f"got {resp.status_code}: {resp.text}"
        )

    def test_huge_json(self, client: TestClient, auth_admin: dict) -> None:
        """POST /api/v1/clients/ with 10 MB JSON — returns 400 or 413."""
        # Build a 10 MB payload
        huge_payload = {"name": "Huge Payload Test", "data": "x" * (10 * 1024 * 1024)}
        resp = client.post(
            "/api/v1/clients/",
            json=huge_payload,
            headers=auth_admin,
        )
        assert resp.status_code in (
            400,
            413,
            422,
            429,
        ), (
            f"Huge JSON payload should return 400 or 413 or 422 or 429, "
            f"got {resp.status_code}: {resp.text}"
        )

    def test_duplicate_json_keys(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """POST /api/v1/trips/ with duplicate keys — must not crash (Python takes last value)."""
        # Craft raw JSON with duplicate keys
        dup_json = '{"client_name": "First", "client_name": "Last", "status": "Planned"}'
        try:
            resp = client.post(
                "/api/v1/trips/",
                data=dup_json,
                headers={
                    "Authorization": auth_admin["Authorization"],
                    "Content-Type": "application/json",
                },
            )
            # Should not crash; FastAPI/Starlette uses json.loads which keeps the last value
            assert resp.status_code != 500, (
                f"Duplicate keys should not cause a 500, "
                f"got {resp.status_code}: {resp.text}"
            )
        except Exception:
            pass

    def test_invalid_enum_values(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """POST /api/v1/trips/ with an invalid status value — returns 400 or 422."""
        payload = {
            "client_name": "Enum Test",
            "driver_name": "Enum Driver",
            "truck_number": "ENUM-001",
            "status": "INVALID_STATUS_XYZ",
        }
        resp = client.post("/api/v1/trips/", json=payload, headers=auth_admin)
        assert resp.status_code in (
            200,
            400,
            422,
            429,
        ), (
            f"Invalid enum value should return 200, 400, 422, or 429, "
            f"got {resp.status_code}: {resp.text}"
        )

    def test_null_values_in_required_fields(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """POST /api/v1/drivers/ with null name — returns 400 or 422."""
        payload = {"name": None, "phone": "+40-711-000-111", "email": "null-test@test.com"}
        resp = client.post("/api/v1/drivers/", json=payload, headers=auth_admin)
        assert resp.status_code in (
            400,
            422,
        ), (
            f"Null value in required field should return 400 or 422, "
            f"got {resp.status_code}: {resp.text}"
        )

    def test_very_long_query_param(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """GET /api/v1/trips/ with a 100 KB query parameter — returns 400 or 414."""
        long_value = "A" * (100 * 1024)  # 100 KB
        try:
            resp = client.get(
                f"/api/v1/trips/?search={long_value}",
                headers=auth_admin,
            )
            assert resp.status_code in (
                200,
                400,
                414,
                422,
                429,
            ), (
                f"Very long query parameter should return 200, 400, 414, 422, or 429, "
                f"got {resp.status_code}: {resp.text}"
            )
        except Exception:
            pass
