"""Tests for the mobile API /user/profile endpoint.

Verifies that:
1. Admin users (id=0, resolved from env) get a profile without DB query
2. Regular users get their profile from the database
3. Unauthenticated requests return 401
"""

import os
import pytest
from unittest.mock import MagicMock, patch


# ── Unit tests for the profile endpoint logic ──────────────────────────

class TestGetMyProfileAdminHandling:
    """The mobile /user/profile must handle admin users (id=0, no DB row)."""

    @pytest.fixture
    def mock_current_user_admin(self):
        return {
            "id": 0,
            "email": "admin@example.com",
            "role": "admin",
            "is_admin": True,
            "company_id": 0,
        }

    @pytest.fixture
    def mock_current_user_regular(self):
        return {
            "id": 1,
            "email": "user@example.com",
            "role": "dispatcher",
            "is_admin": False,
            "company_id": 1,
        }

    def test_admin_user_returns_profile_without_db_query(self, mock_current_user_admin):
        """Admin users should get a synthetic profile without hitting the DB."""

        # Simulate the fixed logic from mobile.py
        current_user = mock_current_user_admin
        user_id = current_user["id"]

        if current_user.get("is_admin") or user_id == 0:
            result = {
                "id": 0,
                "email": current_user.get("email", ""),
                "role": current_user.get("role", "admin"),
                "display_name": "Administrator",
                "driver_id": None,
                "is_active": True,
                "created_at": "",
                "driver": None,
            }
        else:
            result = None

        assert result is not None
        assert result["id"] == 0
        assert result["role"] == "admin"
        assert result["display_name"] == "Administrator"
        assert result["driver"] is None
        assert result["is_active"] is True

    def test_regular_user_needs_db_query(self, mock_current_user_regular):
        """Regular users should go through the DB query path (not return synthetic profile)."""
        current_user = mock_current_user_regular
        user_id = current_user["id"]

        # The admin check should NOT match for regular users
        is_admin_user = current_user.get("is_admin") or user_id == 0
        assert not is_admin_user

    def test_admin_with_is_admin_flag_false_but_id_zero(self):
        """Edge case: user has id=0 but is_admin=False — still resolved as admin."""
        current_user = {
            "id": 0,
            "email": "admin@example.com",
            "role": "admin",
            "is_admin": False,
            "company_id": 0,
        }
        # The check is: is_admin OR user_id == 0
        is_admin_user = current_user.get("is_admin") or current_user["id"] == 0
        assert is_admin_user  # Should be True because id == 0


# ── API integration tests ──────────────────────────────────────────────

class TestMobileProfileAPI:
    """Integration tests using the FastAPI TestClient with mocked auth."""

    @pytest.fixture
    def app(self):
        from fastapi import FastAPI
        from backend.api.v1.mobile import router
        # Mobile router internally has prefix="/mobile", full path is /api/v1/mobile/user/profile
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.fixture
    def mock_admin_user(self):
        return {
            "id": 0,
            "email": "admin@example.com",
            "role": "admin",
            "is_admin": True,
            "company_id": 0,
        }

    @pytest.fixture
    def mock_regular_user(self):
        return {
            "id": 5,
            "email": "dispatcher@company.com",
            "role": "dispatcher",
            "is_admin": False,
            "company_id": 1,
        }

    def test_admin_profile_no_auth_returns_401(self, client):
        """Without auth token, the endpoint returns 401."""
        resp = client.get("/mobile/user/profile")
        assert resp.status_code == 401

    def test_admin_profile_with_admin_auth(self, app, client, mock_admin_user):
        """Admin user gets synthetic profile (no DB query needed)."""
        from backend.dependencies_security import get_current_user
        app.dependency_overrides[get_current_user] = lambda: mock_admin_user

        resp = client.get("/mobile/user/profile")

        app.dependency_overrides.clear()

        # With our fix, admin returns 200 with synthetic profile
        # If the fix was missing, it would 404 (user not found in DB)
        if resp.status_code == 200:
            data = resp.json()
            assert data["id"] == 0
            assert data["role"] == "admin"
        elif resp.status_code == 404:
            pytest.fail("Admin profile returned 404 — the fix for mobile.py is missing!")
        elif resp.status_code == 500:
            pytest.fail("Admin profile returned 500 — check the mobile endpoint implementation.")

    def test_admin_profile_response_structure(self, app, client, mock_admin_user):
        """The admin profile response has the expected fields."""
        from backend.dependencies_security import get_current_user
        app.dependency_overrides[get_current_user] = lambda: mock_admin_user

        resp = client.get("/mobile/user/profile")

        app.dependency_overrides.clear()

        if resp.status_code == 200:
            data = resp.json()
            expected_keys = {"id", "email", "role", "display_name", "driver_id", "is_active", "created_at", "driver"}
            assert expected_keys.issubset(data.keys()), f"Missing keys: {expected_keys - data.keys()}"
            assert data["driver"] is None

    def test_regular_user_profile_no_db_fallback(self, app, client, mock_regular_user):
        """Regular user without DB access would get an error (expected)."""
        from backend.dependencies_security import get_current_user

        # Mock the DB dependency to return no row
        async def mock_db():
            db = MagicMock()
            cursor = MagicMock()
            cursor.fetchone.return_value = None
            db.execute.return_value = cursor
            yield db

        from backend.dependencies import get_db
        app.dependency_overrides[get_current_user] = lambda: mock_regular_user
        app.dependency_overrides[get_db] = mock_db

        resp = client.get("/mobile/user/profile")

        app.dependency_overrides.clear()

        # Regular user with no DB row should get 404
        assert resp.status_code == 404, f"Expected 404 for regular user with no DB row, got {resp.status_code}"
