"""Tests for the users API router (``/api/v1/users``)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/users"


class TestUsersRouter:
    """User CRUD endpoints (manager/admin only)."""

    # ── list ──────────────────────────────────────────────────────────────

    def test_list_users_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "email": "alice@test.com",
                "role": "dispatcher",
                "display_name": "Alice",
                "is_active": True,
                "created_at": "2024-01-01",
                "driver_id": None,
                "driver_name": None,
            },
        ]
        mocks["db"].conn.execute.return_value = mock_cursor

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["email"] == "alice@test.com"

    def test_list_users_empty(self, client_with_mocks):
        client, mocks = client_with_mocks
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mocks["db"].conn.execute.return_value = mock_cursor

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    # ── create ────────────────────────────────────────────────────────────

    def test_create_user_dispatcher_success(self, client_with_mocks):
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = None  # email is unique
        insert_cursor = MagicMock()
        insert_cursor.lastrowid = 42
        mocks["db"].conn.execute.side_effect = [check_cursor, insert_cursor]

        payload = {
            "email": "new@test.com",
            "password": "secret123",
            "role": "dispatcher",
            "display_name": "New Dispatcher",
        }
        resp = client.post(f"{BASE}/", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"] == 42

    def test_create_user_driver_success(self, client_with_mocks):
        """Driver creation also inserts a drivers row."""
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = None
        driver_cursor = MagicMock()
        driver_cursor.lastrowid = 99
        user_cursor = MagicMock()
        user_cursor.lastrowid = 43
        mocks["db"].conn.execute.side_effect = [
            check_cursor,
            driver_cursor,
            user_cursor,
        ]

        payload = {
            "email": "driver@test.com",
            "password": "secret123",
            "role": "driver",
            "display_name": "New Driver",
        }
        resp = client.post(f"{BASE}/", json=payload)
        assert resp.status_code == 201
        assert resp.json()["id"] == 43

    def test_create_user_invalid_role(self, client_with_mocks):
        client, mocks = client_with_mocks

        payload = {
            "email": "bad@test.com",
            "password": "secret123",
            "role": "superadmin",
        }
        resp = client.post(f"{BASE}/", json=payload)
        assert resp.status_code == 400
        assert "Role" in resp.json()["detail"]

    def test_create_user_duplicate_email(self, client_with_mocks):
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = {"id": 99}  # email exists
        mocks["db"].conn.execute.return_value = check_cursor

        payload = {
            "email": "existing@test.com",
            "password": "secret123",
            "role": "dispatcher",
        }
        resp = client.post(f"{BASE}/", json=payload)
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    def test_create_user_missing_fields(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.post(f"{BASE}/", json={})
        assert resp.status_code == 422

    # ── update ────────────────────────────────────────────────────────────

    def test_update_user_success(self, client_with_mocks):
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = {"id": 2}
        mocks["db"].conn.execute.return_value = check_cursor

        resp = client.put(f"{BASE}/2", json={"display_name": "Updated Name"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_update_user_not_found(self, client_with_mocks):
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = None
        mocks["db"].conn.execute.return_value = check_cursor

        resp = client.put(f"{BASE}/999", json={"display_name": "Nope"})
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_update_user_self_deactivation(self, client_with_mocks):
        """User id==1 tries to deactivate themselves → 400."""
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = {"id": 1}
        mocks["db"].conn.execute.return_value = check_cursor

        resp = client.put(f"{BASE}/1", json={"is_active": False})
        assert resp.status_code == 400
        assert "deactivate yourself" in resp.json()["detail"].lower()

    def test_update_user_no_fields(self, client_with_mocks):
        """Empty update body → no-op, still returns 200."""
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = {"id": 2}
        mocks["db"].conn.execute.return_value = check_cursor

        resp = client.put(f"{BASE}/2", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    # ── deactivate ────────────────────────────────────────────────────────

    def test_deactivate_user_success(self, client_with_mocks):
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = {"id": 2}
        mocks["db"].conn.execute.return_value = check_cursor

        resp = client.delete(f"{BASE}/2")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deactivated"

    def test_deactivate_user_not_found(self, client_with_mocks):
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = None
        mocks["db"].conn.execute.return_value = check_cursor

        resp = client.delete(f"{BASE}/999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_deactivate_self(self, client_with_mocks):
        """User id==1 deletes themselves → 400."""
        client, mocks = client_with_mocks
        check_cursor = MagicMock()
        check_cursor.fetchone.return_value = {"id": 1}
        mocks["db"].conn.execute.return_value = check_cursor

        resp = client.delete(f"{BASE}/1")
        assert resp.status_code == 400
        assert "deactivate yourself" in resp.json()["detail"].lower()

    # ── auth ──────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
