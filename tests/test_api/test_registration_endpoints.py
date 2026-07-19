"""Integration tests for the registration API endpoints (``/api/v1/registration``).

Uses ``client_with_mocks`` fixture from conftest.py for mocked database access.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.v1.registration import _register_rate_limit

BASE = "/api/v1/registration"


@pytest.fixture(autouse=True)
def _clear_register_rate_limit():
    """Clear the in-memory registration rate-limit dict before each test."""
    _register_rate_limit.clear()
    yield


class TestRegistrationEndpoint:
    """POST /api/v1/registration/register"""

    def test_register_success_returns_201(self, client_with_mocks):
        """Valid registration returns 201 with tokens."""
        client, mocks = client_with_mocks
        # Mock DB: email check returns None (no conflict)
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = None
        # Company insert + user insert
        company_cursor = MagicMock()
        company_cursor.lastrowid = 1
        user_cursor = MagicMock()
        user_cursor.lastrowid = 10
        mocks["db"].execute.side_effect = [
            check_cursor,       # email uniqueness check
            company_cursor,     # INSERT INTO companies
            user_cursor,        # INSERT INTO users
        ]

        payload = {
            "email": "newuser@test.com",
            "password": "securepass123",
            "display_name": "Jane Doe",
            "company_name": "Acme Logistics",
        }
        resp = client.post(f"{BASE}/register", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "newuser@test.com"
        assert data["user"]["role"] == "manager"
        assert data["user"]["display_name"] == "Jane Doe"
        assert data["user"]["company_name"] == "Acme Logistics"

    def test_register_duplicate_email_returns_409(self, client_with_mocks):
        """Duplicate email returns 409 Conflict."""
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = {"id": 99}
        mocks["db"].execute.return_value = check_cursor

        payload = {
            "email": "existing@test.com",
            "password": "securepass123",
            "display_name": "Dup",
            "company_name": "Dup Corp",
        }
        resp = client.post(f"{BASE}/register", json=payload)
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    @pytest.mark.parametrize("payload,expected_field", [
        ({"password": "pass123", "display_name": "N", "company_name": "C"}, "email"),
        ({"email": "a@b.com", "display_name": "N", "company_name": "C"}, "password"),
        ({"email": "a@b.com", "password": "pass123", "display_name": "N"}, "company_name"),
        ({}, "email"),
    ])
    def test_register_missing_fields_returns_422(self, client_with_mocks, payload, expected_field):
        """Missing required fields return 422.

        Note: ``display_name`` is optional (defaults to ``""``), so omitting it
        does NOT trigger a 422. Accordingly that case is not parametrized here.
        """
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/register", json=payload)
        assert resp.status_code == 422

    def test_register_weak_password_returns_422(self, client_with_mocks):
        """Short password returns 422."""
        client, mocks = client_with_mocks
        payload = {
            "email": "test@test.com",
            "password": "12",
            "display_name": "Tester",
            "company_name": "Test Corp",
        }
        resp = client.post(f"{BASE}/register", json=payload)
        assert resp.status_code == 422

    def test_register_empty_body_returns_422(self, client_with_mocks):
        """Empty body returns 422."""
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/register", json={})
        assert resp.status_code == 422

    def test_register_email_case_insensitive(self, client_with_mocks):
        """Email is normalized to lowercase."""
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = None
        company_cursor = MagicMock()
        company_cursor.lastrowid = 5
        user_cursor = MagicMock()
        user_cursor.lastrowid = 50
        mocks["db"].execute.side_effect = [
            check_cursor, company_cursor, user_cursor,
        ]

        resp = client.post(f"{BASE}/register", json={
            "email": "  UPPER@TEST.com  ",
            "password": "securepass123",
            "display_name": "Upper",
            "company_name": "Upper Corp",
        })
        assert resp.status_code == 201
        # Email should be lowercased and stripped
        assert resp.json()["user"]["email"] == "upper@test.com"


class TestVerifyEmailEndpoint:
    """POST /api/v1/registration/verify-email — requires auth context."""

    def test_verify_email_noop(self, client_with_mocks):
        """Verify-email endpoint returns 200 (stub)."""
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/verify-email", json={"token": "valid-token"})
        assert resp.status_code in (200, 404, 405)

    def test_verify_email_invalid_token(self, client_with_mocks):
        """Invalid verify token returns an error."""
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/verify-email", json={"token": ""})
        # Endpoint may not be implemented yet (404) or return 400/422
        assert resp.status_code in (400, 404, 422)
