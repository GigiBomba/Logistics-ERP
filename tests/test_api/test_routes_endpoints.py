"""Integration tests for the routes API endpoints (``/api/v1/routes``).

Uses ``client_with_mocks`` with mocked DB layer.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from repositories.route_repository import RouteRepository

BASE = "/api/v1/routes"

# Prevent RouteRepository migration from running against mocked DB
RouteRepository._migrate_done = True


class TestRoutesHistoryList:
    """GET /api/v1/routes/history"""

    def test_list_history_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_rows = [
            {"id": 1, "fingerprint": "abc", "total_km": 100.0,
             "profile": "truck", "created_at": "2024-01-01"},
        ]
        mocks["db"].conn.execute.return_value.fetchall.return_value = fake_rows

        resp = client.get(f"{BASE}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1

    def test_list_history_empty(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchall.return_value = []

        resp = client.get(f"{BASE}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_history_catches_exception(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.side_effect = RuntimeError("db failure")

        resp = client.get(f"{BASE}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        # Error field may or may not be present

    def test_list_history_passes_limit(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchall.return_value = []

        resp = client.get(f"{BASE}/history?limit=10")
        assert resp.status_code == 200


class TestRoutesHistoryGet:
    """GET /api/v1/routes/history/{route_id}"""

    def test_get_route_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake = {"id": 1, "fingerprint": "abc", "total_km": 100.0,
                "profile": "truck", "created_at": "2024-01-01"}
        mocks["db"].conn.execute.return_value.fetchone.return_value = fake

        resp = client.get(f"{BASE}/history/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_get_route_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.return_value = None

        resp = client.get(f"{BASE}/history/999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Route not found"


class TestRoutesCalculate:
    """POST /api/v1/routes/calculate"""

    def test_calculate_validates_min_points(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/calculate", json={"points": ["Paris"]})
        assert resp.status_code in (400, 422)
        if resp.status_code == 400:
            assert "2 points" in resp.json()["detail"]

    def test_calculate_accepts_lat_lng(self, client_with_mocks):
        client, mocks = client_with_mocks
        payload = {
            "points": [
                {"lat": 48.85, "lng": 2.35},
                {"lat": 45.75, "lng": 4.85},
            ],
            "profile": "truck",
        }
        with patch("backend.services.route_service.RouteService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.calculate_route.return_value = {
                "distance_km": 500, "duration_h": 5,
            }
            resp = client.post(f"{BASE}/calculate", json=payload)
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    def test_calculate_invalid_point_format(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/calculate", json={"points": [42, 43]})
        assert resp.status_code in (400, 422)


class TestRoutesDuplicate:
    """POST /api/v1/routes/history/{route_id}/duplicate"""

    def test_duplicate_route_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchall.return_value = [
            {"id": 1, "fingerprint": "abc"},
        ]

        resp = client.post(f"{BASE}/history/1/duplicate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicated"


class TestRoutesArchive:
    """POST /api/v1/routes/history/{route_id}/archive"""

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


class TestRoutesDelete:
    """DELETE /api/v1/routes/history/{route_id}"""

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


class TestRoutesExport:
    """GET /api/v1/routes/history/{route_id}/export"""

    def test_export_json_default(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.return_value = {
            "id": 1, "fingerprint": "abc", "total_km": 100.0,
            "profile": "truck", "created_at": "2024-01-01",
        }

        resp = client.get(f"{BASE}/history/1/export")
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_export_csv_format(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.return_value = {
            "id": 1, "fingerprint": "abc", "total_km": 100.0,
            "profile": "truck", "created_at": "2024-01-01",
        }

        resp = client.get(f"{BASE}/history/1/export?fmt=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_export_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].conn.execute.return_value.fetchone.return_value = None

        resp = client.get(f"{BASE}/history/999/export")
        assert resp.status_code == 404


class TestRoutesAuth:
    """Authentication gates."""

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/history")
        assert resp.status_code == 401
