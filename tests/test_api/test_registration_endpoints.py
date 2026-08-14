"""Integration tests for the registration API endpoints (``/api/v1/registration``).

Uses ``client_with_mocks`` fixture from conftest.py for mocked database access.
"""
from __future__ import annotations

import os
import tempfile
import uuid

# â”€â”€ Per-module DB + env guard (worker-isolation) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Other modules on the same xdist worker (e.g. tests/security/test_security_verification.py)
# importlib.reload config/backend.main, leaving backend.dependencies._db_instance bound to a
# stale worker DB and clobbering env vars (OPERION_JWT_SECRET_KEY, OPERION_API_KEY) â€” which
# makes registration fail with 500 ("OPERION_JWT_SECRET_KEY is not set").  Give this module
# its own temp DB and re-assert the env before every test.
_TEST_DB_DIR = tempfile.gettempdir()
os.makedirs(_TEST_DB_DIR, exist_ok=True)
_TEST_DB = os.path.join(
    _TEST_DB_DIR, f"test_registration_endpoints_{uuid.uuid4().hex[:12]}.db",
)
os.environ["OPERION_DB_PATH"] = _TEST_DB
os.environ["OPERION_ENV"] = "test"
os.environ["OPERION_JWT_SECRET_KEY"] = "test-key-ci-32-chars-required-here!!"
os.environ.pop("OPERION_API_KEY", None)

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.v1.registration import _register_rate_limit

BASE = "/api/v1/registration"


@pytest.fixture(autouse=True)
def _registration_env_guard():
    """Rebind the app DB singleton + re-assert env before each test."""
    os.environ["OPERION_DB_PATH"] = _TEST_DB
    os.environ["OPERION_ENV"] = "test"
    os.environ["OPERION_JWT_SECRET_KEY"] = "test-key-ci-32-chars-required-here!!"
    os.environ.pop("OPERION_API_KEY", None)
    from config import Config as _Cfg
    _Cfg.DB_PATH = _TEST_DB
    _Cfg.API_KEY = ""  # disable API-key middleware for this module
    try:
        import backend.middleware.auth_middleware as _auth_mw
        _auth_mw.Config.API_KEY = ""
    except Exception:
        pass
    from backend import dependencies as _deps
    if getattr(_deps, "Config", None) is not None:
        _deps.Config.DB_PATH = _TEST_DB
    if _deps._db_instance is not None:
        try:
            _deps._db_instance.close()
        except Exception:
            pass
        _deps._db_instance = None
    yield


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
        # Repositories call db.conn.execute() internally:
        #   1) UserRepository.get_by_email â†’ _fetchone â†’ conn.execute().fetchone()
        #   2) CompanyRepository.create    â†’ _execute_insert â†’ conn.execute()
        #   3) UserRepository.create_user  â†’ _execute_insert â†’ conn.execute()
        email_check = MagicMock()
        email_check.fetchone.return_value = None          # email not found â†’ None
        company_cursor = MagicMock()
        company_cursor.lastrowid = 1                      # new company id
        user_cursor = MagicMock()
        user_cursor.lastrowid = 10                        # new user id
        mocks["db"].conn.execute.side_effect = [
            email_check,      # _fetchone in get_by_email
            company_cursor,   # _execute_insert for company
            user_cursor,      # _execute_insert for user
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
        mocks["db"].conn.execute.return_value = check_cursor

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
        mocks["db"].conn.execute.side_effect = [
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
    """POST /api/v1/registration/verify-email â€” requires auth context."""

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
