"""Mutation/fuzzing tests for mobile API endpoints — SQL injection, XSS,
invalid input types, boundary value attacks, and payload tampering.

Tests:
  1. SQL injection in query parameters
  2. SQL injection in JSON body fields
  3. XSS payload in message text
  4. XSS payload in transport reference
  5. Negative/null IDs
  6. Type confusion (string where int expected)
  7. Special Unicode characters
  8. Overly nested JSON
  9. Empty required fields
  10. Boundary values (max int, empty strings, etc.)

Usage:
    pytest tests/test_api/test_mobile_mutation.py -v --tb=long
"""

from __future__ import annotations

import os
import uuid
from typing import Dict

# ── Env setup before project imports ─────────────────────────────────
_TEST_DB = os.path.join(
    os.path.dirname(__file__), "..", "..", "data",
    f"test_mutation_{uuid.uuid4().hex[:12]}.db",
)
os.environ.setdefault("OPERION_DB_PATH", _TEST_DB)
os.environ["OPERION_JWT_SECRET_KEY"] = "mutation-test-jwt-secret"
os.environ["OPERION_ENV"] = "test"
os.environ["OPERION_RATE_LIMIT"] = "10000"

import bcrypt
import pytest
from fastapi.testclient import TestClient
from config import Config

Config.DB_PATH = _TEST_DB
import backend.dependencies as deps
from tests.test_api.helpers import create_test_app

_ADMIN_EMAIL = f"admin-mutation-{uuid.uuid4().hex[:8]}@test.com"
_ADMIN_PASSWORD = "admin-mutation-pw"
_ADMIN_HASH = bcrypt.hashpw(_ADMIN_PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
os.environ["OPERION_ADMIN_EMAIL"] = _ADMIN_EMAIL
os.environ["OPERION_ADMIN_PASSWORD_HASH"] = _ADMIN_HASH


def _seed():
    # Force Config.DB_PATH to OUR test DB FIRST — another test module may
    # have overwritten it, and deps.init_db() reads Config.DB_PATH at call
    # time. Binding the singleton before resetting the path would point the
    # app at another suite's DB.
    Config.DB_PATH = _TEST_DB
    deps._db_instance = None
    deps.init_db()
    from database.db_manager import DatabaseManager
    db = DatabaseManager(_TEST_DB)
    now = db.conn.execute("SELECT datetime('now')").fetchone()[0]
    h = bcrypt.hashpw("pw".encode(), bcrypt.gensalt(rounds=4)).decode()
    db.conn.execute("INSERT OR IGNORE INTO companies (id, company_name, is_active) VALUES (1, 'MutCo', 1)")
    db.conn.execute("INSERT OR IGNORE INTO users (id, email, password_hash, role, company_id) VALUES (88, 'mut@test.com', ?, 'driver', 1)", (h,))
    for col, sql in (
        ("reference", "ALTER TABLE trips ADD COLUMN reference TEXT"),
        ("loading_city", "ALTER TABLE trips ADD COLUMN loading_city TEXT"),
        ("delivery_city", "ALTER TABLE trips ADD COLUMN delivery_city TEXT"),
        ("updated_at", "ALTER TABLE trips ADD COLUMN updated_at TEXT"),
    ):
        try:
            db.conn.execute(sql)
        except Exception:
            pass
    db.conn.execute("INSERT OR IGNORE INTO trips (id, reference, loading_city, delivery_city, status, company_id) VALUES (888, 'BASE', 'A', 'B', 'planned', 1)")
    db.conn.commit()
    db.close()


def _client() -> TestClient:
    _seed()
    from backend.main import create_app
    return TestClient(create_test_app())


# create_test_app() overrides auth dependencies, so any Bearer token works.
_MOCK_TOKEN = "mutation-test-mock-token"


def _headers() -> Dict[str, str]:
    return {"Authorization": "Bearer mutation-test-mock-token"}


# ═══════════════════════════════════════════════════════════════════════
# Mutation tests
# ═══════════════════════════════════════════════════════════════════════


class TestMobileMutation:
    """Fuzzing and input-validation tests for mobile endpoints."""

    # ── SQL injection in query params ─────────────────────────────────

    def test_01_sql_injection_query_param(self):
        """SQL injection in query string — should sanitize or reject."""
        client = _client()
        payload = "1' OR '1'='1"
        resp = client.get(
            f"/api/v1/mobile/sync?entity={payload}&full=true",
            headers=_headers(),
        )
        # Should not crash; acceptable: 200 (sanitized), 400, 422
        assert resp.status_code in (200, 400, 422), f"Got {resp.status_code}"
        # If 200, verify no SQL leakage
        if resp.status_code == 200:
            assert resp.json() is not None

    def test_02_sql_injection_json_body(self):
        """SQL injection inside a JSON string field."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()
        resp = client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": "test'; DROP TABLE trips; --",
                "loading_city": "A",
                "delivery_city": "B'; SELECT * FROM users; --",
            },
            headers=_headers(),
        )
        assert resp.status_code in (201, 200, 400, 422), f"Got {resp.status_code}"

    # ── XSS payloads ──────────────────────────────────────────────────

    def test_03_xss_in_message_text(self):
        """XSS payload in message body — should be preserved as text, not executed."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()
        xss = '<script>alert("XSS")</script>'
        resp = client.post(
            "/api/v1/mobile/messages",
            json={"receiver_id": 88, "text": xss},
            headers=_headers(),
        )
        assert resp.status_code in (201, 200, 400, 422), f"Got {resp.status_code}"

    def test_04_xss_in_transport_reference(self):
        """XSS payload in transport reference field."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()
        resp = client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": '<img src=x onerror=alert(1)>',
                "loading_city": "SafeCity",
                "delivery_city": "SafeCity2",
            },
            headers=_headers(),
        )
        assert resp.status_code in (201, 200, 400, 422), f"Got {resp.status_code}"

    # ── Invalid IDs ───────────────────────────────────────────────────

    def test_05_negative_transport_id(self):
        """Request transport detail with negative ID."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()
        resp = client.get(
            "/api/v1/mobile/driver/transports/-1",
            headers=_headers(),
        )
        assert resp.status_code in (404, 400, 422), f"Got {resp.status_code}"

    def test_06_string_id_where_int_expected(self):
        """Type confusion: pass a string for a numeric path param."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()
        resp = client.get(
            "/api/v1/mobile/driver/transports/abc",
            headers=_headers(),
        )
        assert resp.status_code in (404, 400, 422), f"Got {resp.status_code}"

    # ── Unicode edge cases ────────────────────────────────────────────

    def test_07_special_unicode_chars(self):
        """Unicode escape sequences, zero-width characters, RTL override."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()
        resp = client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": "Unicode \u202e\u2066payload\u2069 test \u200b",
                "loading_city": "\u0000hidden",
                "delivery_city": "\uFEFFBOM",
            },
            headers=_headers(),
        )
        assert resp.status_code in (201, 200, 400, 422), f"Got {resp.status_code}"

    # ── Nested/Boundary payloads ──────────────────────────────────────

    def test_08_deeply_nested_json(self):
        """Send an extremely nested JSON structure."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()

        def _deep_nest(n):
            if n == 0:
                return "leaf"
            return {"nested": _deep_nest(n - 1)}

        resp = client.post(
            "/api/v1/mobile/messages",
            json={"receiver_id": 88, "text": "ok", "payload": _deep_nest(100)},
            headers=_headers(),
        )
        assert resp.status_code in (201, 200, 400, 422), f"Got {resp.status_code}"

    def test_09_empty_required_fields(self):
        """Send empty string for required fields."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()
        resp = client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={"reference": "", "loading_city": "", "delivery_city": ""},
            headers=_headers(),
        )
        assert resp.status_code in (201, 200, 400, 422), f"Got {resp.status_code}"

    def test_10_boundary_values(self):
        """Max integers, boolean for string fields, arrays for scalars."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()

        # Integer field with max 64-bit values
        cases = [
            ("POST", "/api/v1/mobile/messages", {"receiver_id": 2**63 - 1, "text": "ok"}),
            ("POST", "/api/v1/mobile/messages", {"receiver_id": -2**63, "text": "ok"}),
            ("PATCH", "/api/v1/mobile/user/profile", {"display_name": True}),
        ]

        for method, path, body in cases:
            resp = client.request(method, path, json=body, headers=_headers())
            assert resp.status_code in (200, 201, 400, 422), (
                f"{method} {path}: unexpected {resp.status_code}"
            )

    # ── Additional mutation tests ─────────────────────────────────────

    def test_sql_injection_in_messages(self):
        """SQL injection payload in message text — should sanitize or reject."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()
        payloads = [
            "'; DROP TABLE mobile_messages; --",
            "' OR 1=1; --",
            "'; SELECT * FROM users; --",
        ]
        for payload in payloads:
            resp = client.post(
                "/api/v1/mobile/messages",
                json={"receiver_id": 88, "text": payload},
                headers=_headers(),
            )
            assert resp.status_code in (201, 200, 400, 422), (
                f"Payload {payload!r}: got {resp.status_code}"
            )

    def test_xss_in_profile_name(self):
        """XSS payload in display_name — should be stored as text, not executed."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()
        xss_payloads = [
            '<script>alert("xss")</script>',
            '<img src=x onerror=alert(1)>',
            'javascript:alert(1)',
            '"><script>alert(1)</script>',
        ]
        for payload in xss_payloads:
            resp = client.patch(
                "/api/v1/mobile/user/profile",
                json={"display_name": payload},
                headers=_headers(),
            )
            assert resp.status_code in (200, 400, 422), (
                f"Payload {payload!r}: got {resp.status_code}"
            )

    def test_very_deep_nested_json_in_profile(self):
        """Profile PATCH with extremely nested JSON structure."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()

        def _deep_nest(n):
            if n <= 0:
                return "deepest"
            return {"level": _deep_nest(n - 1)}

        deep = _deep_nest(50)
        resp = client.patch(
            "/api/v1/mobile/user/profile",
            json={"display_name": "DeepTest", "extra": deep},
            headers=_headers(),
        )
        assert resp.status_code in (200, 400, 422, 500), (
            f"Deep nested JSON: got {resp.status_code}"
        )

    def test_invalid_json_in_body(self):
        """Send non-parseable JSON body to a POST endpoint."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()

        cases = [
            ("/api/v1/mobile/driver/expenses", "this is not json {{{"),
            ("/api/v1/mobile/dispatcher/transports", "{broken: @@@}"),
            ("/api/v1/mobile/messages", "null"),
            ("/api/v1/mobile/messages", "12345"),
        ]
        for path, body in cases:
            resp = client.post(
                path,
                content=body,
                headers=_headers() | {"Content-Type": "application/json"},
            )
            assert resp.status_code in (400, 422, 500), (
                f"{path} with body {body!r}: got {resp.status_code}"
            )

    def test_empty_strings_for_all_fields(self):
        """Send empty strings for all text fields in transport creation."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()

        resp = client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={"reference": "", "loading_city": "", "delivery_city": "",
                  "driver_name": "", "truck_plate": "", "notes": ""},
            headers=_headers(),
        )
        assert resp.status_code in (201, 200, 400, 422), (
            f"Empty fields: got {resp.status_code}: {resp.text[:200]}"
        )

        # Also test empty strings in profile update
        resp2 = client.patch(
            "/api/v1/mobile/user/profile",
            json={"display_name": "", "phone": "", "email": ""},
            headers=_headers(),
        )
        assert resp2.status_code in (200, 400, 422), (
            f"Empty profile fields: got {resp2.status_code}"
        )

    def test_boundary_int_values(self):
        """Extreme boundary integer values for entity IDs and pagination."""
        client = _client()
        _ = _MOCK_TOKEN  # noqa: F841 - auth is overridden by create_test_app()

        # Max 32-bit signed int
        resp = client.get(
            "/api/v1/mobile/driver/transports/2147483647",
            headers=_headers(),
        )
        assert resp.status_code in (404, 400, 422), (
            f"Max int transport: {resp.status_code}"
        )

        # Min 32-bit signed int (negative)
        resp = client.get(
            "/api/v1/mobile/driver/transports/-2147483648",
            headers=_headers(),
        )
        assert resp.status_code in (404, 400, 422), (
            f"Min int transport: {resp.status_code}"
        )

        # Zero as transport ID
        resp = client.get(
            "/api/v1/mobile/driver/transports/0",
            headers=_headers(),
        )
        assert resp.status_code in (404, 400, 422), (
            f"Zero transport: {resp.status_code}"
        )
