"""Tests for the routes API router (``/api/v1/routes``).

Most route endpoints use ``get_db`` directly and instantiate repositories
or services inside the handler body.  The mock DB (``mocks["db"]``) is
configured per test, notably with pass-through ``row_to_dict`` /
``rows_to_dicts`` so that the ``BaseRepository`` methods work correctly.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from repositories.route_repository import RouteRepository

BASE = "/api/v1/routes"

# Prevent RouteRepository migration from running against the mocked DB.
# The migration would execute PRAGMA / ALTER TABLE queries that don't
# exist on the MagicMock, causing spurious test failures.
RouteRepository._migrate_done = True

# ── helpers ────────────────────────────────────────────────────────────────


# ── tests ──────────────────────────────────────────────────────────────────


class TestRoutesRouter:
    """History, calculation, archive, export for routes."""

    # ── list history ──────────────────────────────────────────────────────

    def test_list_route_history_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks

        fake_rows = [
            {"id": 1, "fingerprint": "abc", "total_km": 100.0,
             "profile": "truck", "created_at": "2024-01-01"},
        ]
        # RouteRepository.get_all uses db.conn.execute().fetchall()
        mocks["db"].conn.execute.return_value.fetchall.return_value = fake_rows

        resp = client.get(f"{BASE}/history?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == 1
        assert data["total"] == 1

    def test_list_route_history_catches_exception(self, client_with_mocks):
        """When the db query fails the handler returns empty items with an
        error string (the router wraps the call in try/except)."""
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.side_effect = RuntimeError("db failure")

        resp = client.get(f"{BASE}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    # ── get by id ─────────────────────────────────────────────────────────

    def test_get_route_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks

        fake_route = {
            "id": 1, "fingerprint": "abc", "total_km": 100.0,
            "profile": "truck", "created_at": "2024-01-01",
        }
        mocks["db"].conn.execute.return_value.fetchone.return_value = fake_route

        resp = client.get(f"{BASE}/history/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_get_route_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.return_value = None

        resp = client.get(f"{BASE}/history/999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Route not found"

    # ── calculate route ───────────────────────────────────────────────────

    def test_calculate_route_validates_min_points(self, client_with_mocks):
        """Payload with fewer than 2 points must return 400."""
        client, mocks = client_with_mocks

        resp = client.post(f"{BASE}/calculate", json={"points": ["Paris"]})
        assert resp.status_code in (400, 422)
        if resp.status_code == 400:
            assert "2 points" in resp.json()["detail"]

    def test_calculate_route_accepts_lat_lng_points(self, client_with_mocks):
        """Points given as lat/lng dicts skip geocoding."""
        client, mocks = client_with_mocks
        payload = {
            "points": [
                {"lat": 48.85, "lng": 2.35},
                {"lat": 45.75, "lng": 4.85},
            ],
            "profile": "truck",
        }
        # RouteService is imported inside the handler body.
        with patch("backend.services.route_service.RouteService") as mock_route_svc_cls:
            mock_svc = mock_route_svc_cls.return_value
            mock_svc.calculate_route.return_value = {
                "distance_km": 500, "duration_h": 5,
            }

            resp = client.post(f"{BASE}/calculate", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["route"]["distance_km"] == 500

    def test_calculate_route_invalid_point_format(self, client_with_mocks):
        """Integer points hit the else-branch which raises HTTPException(400)."""
        client, mocks = client_with_mocks

        resp = client.post(f"{BASE}/calculate", json={"points": [42, 43]})
        assert resp.status_code in (400, 422)

    # ── duplicate ─────────────────────────────────────────────────────────

    def test_duplicate_route_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        # RouteHistoryService.duplicate_route will query the DB.
        # A simple MagicMock return suffices because the service internally
        # calls repository methods against the mock DB.
        mocks["db"].conn.execute.return_value.fetchall.return_value = [
            {"id": 1, "fingerprint": "abc"},
        ]

        resp = client.post(f"{BASE}/history/1/duplicate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicated"

    # ── archive ───────────────────────────────────────────────────────────

    def test_archive_route_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.return_value = {
            "id": 1, "fingerprint": "abc",
        }

        resp = client.post(f"{BASE}/history/1/archive")
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_archive_route_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.return_value = None

        resp = client.post(f"{BASE}/history/999/archive")
        assert resp.status_code == 404

    # ── delete ────────────────────────────────────────────────────────────

    def test_delete_route_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.return_value = {
            "id": 1, "fingerprint": "abc",
        }

        resp = client.delete(f"{BASE}/history/1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_route_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.return_value = None

        resp = client.delete(f"{BASE}/history/999")
        assert resp.status_code == 404

    # ── export ────────────────────────────────────────────────────────────

    def test_export_route_returns_json_by_default(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_route = {
            "id": 1, "fingerprint": "abc", "total_km": 100.0,
            "profile": "truck", "created_at": "2024-01-01",
        }
        mocks["db"].conn.execute.return_value.fetchone.return_value = fake_route

        resp = client.get(f"{BASE}/history/1/export")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_export_route_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.return_value = None

        resp = client.get(f"{BASE}/history/999/export")
        assert resp.status_code == 404

    def test_export_route_csv_format(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_route = {
            "id": 1, "fingerprint": "abc", "total_km": 100.0,
            "profile": "truck", "created_at": "2024-01-01",
        }
        mocks["db"].conn.execute.return_value.fetchone.return_value = fake_route

        resp = client.get(f"{BASE}/history/1/export?fmt=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    # ── auth ──────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/history")
        assert resp.status_code == 401
