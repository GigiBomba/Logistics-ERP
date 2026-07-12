"""Integration tests for the integration health check endpoints.

GET  /api/v1/integrations/status              — all integration statuses
GET  /api/v1/integrations/status/{name}        — single integration detail
POST /api/v1/integrations/status/{name}/check  — force health check

NOTE: The ``integrations`` router is **not** included in the main
``api_v1_router``, so we build a minimal test app that mounts the
integrations router directly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.integrations import router as integrations_router
from backend.dependencies_security import get_current_user, require_admin, require_dispatcher
from backend.dependencies import get_db

BASE = "/api/v1/integrations"
MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}

ALL_STATUSES_RESPONSE = {
    "integrations": {
        "graphhopper": {"name": "GraphHopper Routing", "connected": True, "last_error": None},
        "nominatim": {"name": "Nominatim Geocoding", "connected": True, "last_error": None},
    },
    "healthy_count": 2,
    "total_count": 2,
}

SINGLE_STATUS_RESPONSE = {
    "name": "GraphHopper Routing",
    "connected": True,
    "last_check": "2026-07-13T12:00:00",
    "last_success": "2026-07-13T12:00:00",
    "last_error": None,
    "latency_ms": 45.2,
    "details": {},
}


def _make_client(extra_overrides=None):
    """Build a TestClient with auth + db overrides and the integrations router.

    Integration endpoints use ``Depends(get_db)``, so we mock ``get_db``
    with a plain ``MagicMock`` to avoid connecting to a real database.
    """
    app = FastAPI()
    app.include_router(integrations_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[require_admin] = lambda: MOCK_USER
    app.dependency_overrides[require_dispatcher] = lambda: MOCK_USER
    app.dependency_overrides[get_db] = lambda: MagicMock()
    if extra_overrides:
        app.dependency_overrides.update(extra_overrides)
    return TestClient(app)


class TestIntegrationListStatus:
    """GET /api/v1/integrations/status"""

    def test_list_status_returns_all(self):
        """Returns 200 with all integration statuses."""
        client = _make_client()
        with patch("services.integration_health_service.IntegrationHealthService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.get_all_statuses.return_value = ALL_STATUSES_RESPONSE
            mock_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/status")
            assert resp.status_code == 200
            data = resp.json()
            assert "integrations" in data
            assert data["healthy_count"] == 2
            assert data["total_count"] == 2

    def test_list_status_empty(self):
        """Returns empty integrations dict when none registered."""
        empty = {"integrations": {}, "healthy_count": 0, "total_count": 0}
        client = _make_client()
        with patch("services.integration_health_service.IntegrationHealthService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.get_all_statuses.return_value = empty
            mock_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/status")
            assert resp.status_code == 200
            assert resp.json()["total_count"] == 0

    def test_list_status_some_unhealthy(self):
        """Shows reduced healthy_count when some integrations are down."""
        mixed = {
            "integrations": {
                "graphhopper": {"name": "GraphHopper Routing", "connected": True},
                "nominatim": {"name": "Nominatim Geocoding", "connected": False, "last_error": "Connection refused"},
            },
            "healthy_count": 1,
            "total_count": 2,
        }
        client = _make_client()
        with patch("services.integration_health_service.IntegrationHealthService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.get_all_statuses.return_value = mixed
            mock_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/status")
            assert resp.status_code == 200
            assert resp.json()["healthy_count"] == 1

    def test_list_status_requires_auth(self):
        """Without auth token, returns 401."""
        app = FastAPI()
        app.include_router(integrations_router, prefix="/api/v1")
        raw_client = TestClient(app)
        resp = raw_client.get(f"{BASE}/status")
        assert resp.status_code == 401


class TestIntegrationDetail:
    """GET /api/v1/integrations/status/{integration_name}"""

    def test_detail_known_integration(self):
        """Returns 200 with detailed status for a known integration."""
        client = _make_client()
        with patch("services.integration_health_service.IntegrationHealthService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.get_status.return_value = SINGLE_STATUS_RESPONSE
            mock_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/status/graphhopper")
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "GraphHopper Routing"
            assert data["connected"] is True

    def test_detail_unknown_integration(self):
        """Returns 200 with connected=False and error for unknown integration."""
        unknown_response = {
            "name": "unknown_svc",
            "connected": False,
            "error": "Unknown integration",
        }
        client = _make_client()
        with patch("services.integration_health_service.IntegrationHealthService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.get_status.return_value = unknown_response
            mock_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/status/unknown_svc")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is False
            assert "Unknown integration" in data.get("error", "")

    def test_detail_disconnected_integration(self):
        """Returns connected=False with last_error for a down integration."""
        disconnected = dict(SINGLE_STATUS_RESPONSE)
        disconnected["connected"] = False
        disconnected["last_error"] = "HTTP 503"
        client = _make_client()
        with patch("services.integration_health_service.IntegrationHealthService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.get_status.return_value = disconnected
            mock_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/status/graphhopper")
            assert resp.status_code == 200
            assert resp.json()["connected"] is False
            assert resp.json()["last_error"] == "HTTP 503"

    def test_detail_requires_auth(self):
        """Without auth token, returns 401."""
        app = FastAPI()
        app.include_router(integrations_router, prefix="/api/v1")
        raw_client = TestClient(app)
        resp = raw_client.get(f"{BASE}/status/graphhopper")
        assert resp.status_code == 401


class TestIntegrationCheck:
    """POST /api/v1/integrations/status/{integration_name}/check"""

    def test_check_known_integration(self):
        """Returns 200 with forced check result."""
        client = _make_client()
        with patch("services.integration_health_service.IntegrationHealthService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.check_now.return_value = SINGLE_STATUS_RESPONSE
            mock_cls.return_value = mock_svc

            resp = client.post(f"{BASE}/status/graphhopper/check")
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "GraphHopper Routing"
            assert data["connected"] is True
            mock_svc.check_now.assert_called_once_with("graphhopper")

    def test_check_unknown_integration(self):
        """Returns 200 with connected=False for an unknown integration."""
        unknown = {"name": "ghost", "connected": False, "error": "Unknown integration"}
        client = _make_client()
        with patch("services.integration_health_service.IntegrationHealthService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.check_now.return_value = unknown
            mock_cls.return_value = mock_svc

            resp = client.post(f"{BASE}/status/ghost/check")
            assert resp.status_code == 200
            assert resp.json()["connected"] is False
            mock_svc.check_now.assert_called_once_with("ghost")

    def test_check_disconnected_integration(self):
        """Returns connected=False for a failing integration check."""
        disconnected = dict(SINGLE_STATUS_RESPONSE)
        disconnected["connected"] = False
        disconnected["last_error"] = "Connection timed out"
        client = _make_client()
        with patch("services.integration_health_service.IntegrationHealthService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.check_now.return_value = disconnected
            mock_cls.return_value = mock_svc

            resp = client.post(f"{BASE}/status/graphhopper/check")
            assert resp.status_code == 200
            assert resp.json()["connected"] is False
            assert "timed out" in resp.json()["last_error"]

    def test_check_updates_cache(self):
        """Verifies that check_now clears cache and re-runs the health check."""
        client = _make_client()
        with patch("services.integration_health_service.IntegrationHealthService") as mock_cls:
            mock_svc = MagicMock()
            mock_svc.check_now.return_value = SINGLE_STATUS_RESPONSE
            mock_cls.return_value = mock_svc

            client.post(f"{BASE}/status/nominatim/check")
            mock_svc.check_now.assert_called_once_with("nominatim")
            mock_svc.get_status.assert_not_called()

    def test_check_requires_auth(self):
        """Without auth token, returns 401."""
        app = FastAPI()
        app.include_router(integrations_router, prefix="/api/v1")
        raw_client = TestClient(app)
        resp = raw_client.post(f"{BASE}/status/graphhopper/check")
        assert resp.status_code == 401
