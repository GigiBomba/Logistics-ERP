"""Tests for tenant-scoped GPS live keys (R2).

``gps:live:{truck_id}`` must become ``gps:live:{company_id}:{truck_id}`` on
the write (ping + batch) and read (single + batch loop) paths so the same
truck id under two companies cannot share live position data.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.fleet import router as fleet_router
from backend.dependencies import get_fleet_service
from backend.dependencies_security import require_dispatcher

PING = {
    "truck_id": 5,
    "latitude": 48.8566,
    "longitude": 2.3522,
    "speed_kmh": 65,
    "heading": 180,
    "timestamp": "2024-01-15T10:30:00Z",
    "driver_id": 5,
}


def _make_client(company_id: int, truck_lookup=None, trucks_by_ids=None):
    """App with the fleet router and a caller authenticated as *company_id*."""
    app = FastAPI()
    app.include_router(fleet_router)
    mock_service = MagicMock()
    if truck_lookup is not None:
        mock_service.get_truck.return_value = truck_lookup
    if trucks_by_ids is not None:
        mock_service.get_trucks_by_ids.return_value = trucks_by_ids
    app.dependency_overrides[require_dispatcher] = lambda: {
        "id": 1, "email": "u@x.com", "role": "admin", "is_admin": True,
        "company_id": company_id,
    }
    app.dependency_overrides[get_fleet_service] = lambda: mock_service
    return TestClient(app, raise_server_exceptions=False)


class TestGpsLiveTenantKeys:
    @patch("backend.api.v1.fleet.get_cache")
    def test_ping_live_key_is_tenant_scoped(self, mock_get_cache):
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache

        client_a = _make_client(company_id=1, truck_lookup={"id": 5, "company_id": 1})
        resp_a = client_a.post("/fleet/gps/ingest", json=PING)
        assert resp_a.status_code == 202
        assert mock_cache.set.call_args[0][0] == "gps:live:1:5"

        mock_cache.reset_mock()
        client_b = _make_client(company_id=2, truck_lookup={"id": 5, "company_id": 2})
        resp_b = client_b.post("/fleet/gps/ingest", json=PING)
        assert resp_b.status_code == 202
        assert mock_cache.set.call_args[0][0] == "gps:live:2:5"

        # Distinct keys — no cross-tenant sharing of the live entry.
        keys = [c[0][0] for c in mock_cache.set.call_args_list]
        assert keys == ["gps:live:2:5"]
        assert mock_cache.set.call_args[0][0] != "gps:live:1:5"

    @patch("backend.api.v1.fleet.get_cache")
    def test_live_read_key_is_tenant_scoped(self, mock_get_cache):
        mock_cache = MagicMock()
        mock_cache.get.return_value = {
            "truck_id": 5, "latitude": 48.8566, "longitude": 2.3522,
            "speed_kmh": 65, "heading": 180, "timestamp": "2024-01-15T10:30:00Z",
        }
        mock_get_cache.return_value = mock_cache

        client = _make_client(company_id=2, truck_lookup={"id": 5, "company_id": 2})
        resp = client.get("/fleet/gps/live/5")
        assert resp.status_code == 200
        assert mock_cache.get.call_args[0][0] == "gps:live:2:5"

    @patch("backend.api.v1.fleet.get_cache")
    def test_batch_live_keys_are_tenant_scoped(self, mock_get_cache):
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache

        pings = [
            {"truck_id": 1, "latitude": 48.8, "longitude": 2.3,
             "speed_kmh": 60, "heading": 90, "timestamp": "2024-01-15T10:30:00Z"},
            {"truck_id": 2, "latitude": 48.9, "longitude": 2.4,
             "speed_kmh": 70, "heading": 270, "timestamp": "2024-01-15T10:31:00Z"},
        ]
        client = _make_client(company_id=3, trucks_by_ids=[{"id": 1}, {"id": 2}])
        resp = client.post("/fleet/gps/batch", json=pings)
        assert resp.status_code == 202
        keys = [c[0][0] for c in mock_cache.set.call_args_list]
        assert keys == ["gps:live:3:1", "gps:live:3:2"]