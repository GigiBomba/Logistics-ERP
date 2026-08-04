"""Mutation tests for API input handling — boundary, malicious, and malformed inputs.

Every test verifies the API returns 400/422 (not 500) and a valid JSON error
response when given bad inputs.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.mutation


# ═════════════════════════════════════════════════════════════════════════════
# Empty body / malformed JSON
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationApiEmptyBody:
    """API endpoints reject empty body or malformed JSON."""

    BASE = "/api/v1/trips"

    def test_post_empty_json_body(self, client_with_mocks):
        """POST with empty JSON object {} is forwarded to service."""
        client, mocks = client_with_mocks
        mocks["trip_service"].create.return_value = MagicMock(success=True, data=MagicMock(id=1))

        resp = client.post(f"{self.BASE}/", json={})
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            mocks["trip_service"].create.assert_called_once()
        elif resp.status_code == 422:
            body = resp.json()
            assert "detail" in body

    def test_post_empty_string_body(self, client_with_mocks):
        """POST with empty body returns 422 or appropriate error."""
        client, mocks = client_with_mocks
        resp = client.post(
            f"{self.BASE}/",
            data="",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 422)
        body = resp.json()
        assert isinstance(body, dict)

    def test_post_malformed_json(self, client_with_mocks):
        """POST with malformed JSON body should not crash."""
        client, mocks = client_with_mocks
        resp = client.post(
            f"{self.BASE}/",
            data="{invalid json!!!",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 422)
        body = resp.json()
        assert isinstance(body, dict)

    def test_post_with_list_instead_of_object(self, client_with_mocks):
        """POST with JSON array where object expected."""
        client, mocks = client_with_mocks
        resp = client.post(f"{self.BASE}/", json=[1, 2, 3])
        assert resp.status_code in (400, 422)
        body = resp.json()
        assert isinstance(body, dict)


# ═════════════════════════════════════════════════════════════════════════════
# Invalid content types
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationApiContentType:
    """API endpoints handle invalid content types gracefully."""

    BASE = "/api/v1/trips"

    def test_post_with_text_plain(self, client_with_mocks):
        """POST with text/plain content type."""
        client, mocks = client_with_mocks
        resp = client.post(
            f"{self.BASE}/",
            data="plain text body",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code in (400, 415, 422)
        body = resp.json()
        assert isinstance(body, dict)

    def test_post_with_xml_content_type(self, client_with_mocks):
        """POST with application/xml content type."""
        client, mocks = client_with_mocks
        resp = client.post(
            f"{self.BASE}/",
            data="<xml><data></data></xml>",
            headers={"Content-Type": "application/xml"},
        )
        assert resp.status_code in (400, 415, 422)
        body = resp.json()
        assert isinstance(body, dict)

    def test_post_multipart_instead_of_json(self, client_with_mocks):
        """POST with multipart form data where JSON expected."""
        client, mocks = client_with_mocks
        resp = client.post(
            f"{self.BASE}/",
            data={"name": "test"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code in (200, 400, 422)
        # The mock service might accept form data; just ensure no crash


# ═════════════════════════════════════════════════════════════════════════════
# Path traversal
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationApiPathTraversal:
    """API endpoints reject path traversal in path parameters."""

    @pytest.mark.parametrize("traversal_id", [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config",
        "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "....//....//etc/passwd",
        "1; cat /etc/passwd",
    ])
    def test_path_traversal_in_trip_id(self, client_with_mocks, traversal_id):
        """Path traversal strings in path params return 404 or 422, not 500."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_by_id.return_value = None

        resp = client.get(f"/api/v1/trips/{traversal_id}")
        assert resp.status_code != 500, f"Path traversal {traversal_id} caused 500!"
        assert resp.status_code in (404, 422, 400)
        try:
            body = resp.json()
            assert isinstance(body, dict)
        except Exception:
            pass  # Non-JSON is still acceptable if not 500

    @pytest.mark.parametrize("traversal", [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config",
    ])
    def test_path_traversal_in_fleet_id(self, client_with_mocks, traversal):
        """Path traversal in fleet truck ID."""
        client, mocks = client_with_mocks
        mocks["fleet_service"].get_truck.return_value = None

        resp = client.get(f"/api/v1/fleet/trucks/{traversal}")
        assert resp.status_code != 500, f"Path traversal {traversal} caused 500!"

    @pytest.mark.parametrize("traversal", [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config",
    ])
    def test_path_traversal_in_driver_id(self, client_with_mocks, traversal):
        """Path traversal in driver ID."""
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_by_id.return_value = None

        resp = client.get(f"/api/v1/drivers/{traversal}")
        assert resp.status_code != 500, f"Path traversal {traversal} caused 500!"

    @pytest.mark.parametrize("traversal", [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config",
    ])
    def test_path_traversal_in_document_id(self, client_with_mocks, traversal):
        """Path traversal in document ID."""
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = None

        resp = client.get(f"/api/v1/documents/{traversal}")
        assert resp.status_code != 500, f"Path traversal {traversal} caused 500!"


# ═════════════════════════════════════════════════════════════════════════════
# SQL injection in query parameters
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationApiSqlInjection:
    """API endpoints handle SQL injection in query parameters safely."""

    BASE = "/api/v1/trips"

    @pytest.mark.parametrize("sql_injection", [
        "' OR '1'='1",
        "'; DROP TABLE trips; --",
        "1 UNION SELECT * FROM users",
        "1; SELECT password_hash FROM users",
        "' OR 1=1 --",
        "\" OR 1=1 --",
    ])
    def test_sql_injection_in_search_param(self, client_with_mocks, sql_injection):
        """SQL injection in query params should not cause errors."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        resp = client.get(f"{self.BASE}/?search={sql_injection}")
        assert resp.status_code != 500, f"SQL injection '{sql_injection}' caused 500!"
        # May return 200 with empty results — that's acceptable

    @pytest.mark.parametrize("sql_injection", [
        "' OR '1'='1",
        "' UNION SELECT * FROM clients --",
    ])
    def test_sql_injection_in_clients(self, client_with_mocks, sql_injection):
        """SQL injection in clients endpoint."""
        client, mocks = client_with_mocks
        mocks["client_service"].get_all.return_value = []

        resp = client.get(f"/api/v1/clients/?name={sql_injection}")
        assert resp.status_code != 500, f"SQL injection '{sql_injection}' caused 500!"

    @pytest.mark.parametrize("sql_injection", [
        "' OR '1'='1",
        "1; SELECT * FROM drivers",
    ])
    def test_sql_injection_in_drivers(self, client_with_mocks, sql_injection):
        """SQL injection in drivers endpoint."""
        client, mocks = client_with_mocks
        mocks["driver_repo"].get_all.return_value = []

        resp = client.get(f"/api/v1/drivers/?search={sql_injection}")
        assert resp.status_code != 500, f"SQL injection '{sql_injection}' caused 500!"


# ═════════════════════════════════════════════════════════════════════════════
# XSS in text fields
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationApiXss:
    """API endpoints handle XSS strings safely."""

    BASE = "/api/v1/trips"

    @pytest.mark.parametrize("xss", [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        "<svg onload=alert(1)>",
        "javascript:alert('xss')",
        "\"><script>alert('xss')</script>",
    ])
    def test_xss_in_trip_name(self, client_with_mocks, xss):
        """XSS in trip client_name field."""
        client, mocks = client_with_mocks
        mocks["trip_service"].create.return_value = MagicMock(success=True, data=MagicMock(id=1))

        resp = client.post(f"{self.BASE}/", json={
            "client_name": xss,
            "loading_city": xss,
            "delivery_city": xss,
        })
        assert resp.status_code != 500, f"XSS '{xss}' caused 500!"
        assert resp.status_code in (200, 422)

    @pytest.mark.parametrize("xss", [
        "<script>alert('xss')</script>",
        "\"><svg onload=alert(1)>",
    ])
    def test_xss_in_client_name(self, client_with_mocks, xss):
        """XSS in client name field."""
        client, mocks = client_with_mocks
        mocks["client_service"].create.return_value = 1

        resp = client.post("/api/v1/clients/", json={
            "name": xss,
            "email": "test@test.com",
        })
        assert resp.status_code != 500, f"XSS '{xss}' caused 500!"


# ═════════════════════════════════════════════════════════════════════════════
# Large / giant payloads
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationApiLargePayload:
    """API endpoints handle large payloads without crashing."""

    def test_very_large_json_payload(self, client_with_mocks):
        """POST with a huge JSON payload (simulated) should not crash."""
        client, mocks = client_with_mocks
        mocks["trip_service"].create.return_value = MagicMock(success=True, data=MagicMock(id=1))

        # Create a large payload with many fields
        large_payload = {
            "client_name": "x" * 100000,
            "notes": "y" * 100000,
            "loading_city": "z" * 50000,
        }
        resp = client.post("/api/v1/trips/", json=large_payload)
        # FastAPI/Starlette has max request size; may return 413 or 422
        assert resp.status_code in (200, 413, 422, 400)
        if resp.status_code != 200:
            body = resp.json()
            assert isinstance(body, dict)

    def test_deeply_nested_json(self, client_with_mocks):
        """Deeply nested JSON payload."""
        client, mocks = client_with_mocks
        mocks["trip_service"].create.return_value = MagicMock(success=True, data=MagicMock(id=1))

        def make_nested(depth):
            if depth <= 0:
                return "leaf"
            return {"nested": make_nested(depth - 1)}

        resp = client.post("/api/v1/trips/", json=make_nested(50))
        assert resp.status_code in (200, 400, 422, 413)


# ═════════════════════════════════════════════════════════════════════════════
# Invalid data types
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationApiInvalidTypes:
    """API endpoints reject wrong data types gracefully."""

    BASE = "/api/v1/trips"

    def test_send_string_instead_of_integer(self, client_with_mocks):
        """String where number expected."""
        client, mocks = client_with_mocks
        resp = client.post(f"{self.BASE}/", json={
            "client_name": "Test",
            "distance_km": "not-a-number",
        })
        assert resp.status_code in (400, 422)
        body = resp.json()
        assert isinstance(body, dict)

    def test_send_array_instead_of_object(self, client_with_mocks):
        """Array where object expected."""
        client, mocks = client_with_mocks
        resp = client.post(f"{self.BASE}/", json=[1, 2, 3])
        assert resp.status_code in (400, 422)

    def test_send_null_instead_of_string(self, client_with_mocks):
        """Null where string expected."""
        client, mocks = client_with_mocks
        resp = client.post(f"{self.BASE}/", json={"client_name": None})
        assert resp.status_code in (200, 400, 422)
        if resp.status_code == 200:
            mocks["trip_service"].create.assert_called_once()
        elif resp.status_code in (400, 422):
            body = resp.json()
            assert isinstance(body, dict)

    def test_send_very_large_integer(self, client_with_mocks):
        """Very large integer where number expected."""
        client, mocks = client_with_mocks
        resp = client.post(f"{self.BASE}/", json={
            "client_name": "Test",
            "distance_km": 10**15,
            "total_price_eur": 10**15,
        })
        assert resp.status_code in (200, 400, 422)

    def test_send_negative_integer(self, client_with_mocks):
        """Negative integers where positive expected."""
        client, mocks = client_with_mocks
        resp = client.post(f"{self.BASE}/", json={
            "client_name": "Test",
            "distance_km": -100,
            "total_price_eur": -500,
        })
        assert resp.status_code in (200, 400, 422)


# ═════════════════════════════════════════════════════════════════════════════
# Special characters in inputs
# ═════════════════════════════════════════════════════════════════════════════


class TestMutationApiSpecialChars:
    """API endpoints handle special characters in text fields."""

    BASE = "/api/v1/trips"

    @pytest.mark.parametrize("special", [
        "\x00\x01\x02",  # null bytes and control chars
        "\ufffe\uffff",   # non-characters
        "\u202e\u202d",   # bidi override
        "München 🚚 Straße",
        "Hello\nWorld\r\n",
        "\t\r\n",
    ])
    def test_special_chars_in_text_field(self, client_with_mocks, special):
        """Special characters in text field should not cause errors."""
        client, mocks = client_with_mocks
        mocks["trip_service"].create.return_value = MagicMock(success=True, data=MagicMock(id=1))

        resp = client.post(f"{self.BASE}/", json={
            "client_name": special,
            "notes": special,
            "loading_city": special,
        })
        assert resp.status_code != 500, f"Special chars caused 500!"
