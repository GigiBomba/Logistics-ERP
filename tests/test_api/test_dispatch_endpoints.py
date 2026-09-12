"""Tests for the dispatch API endpoints (``/api/v1/dispatch``).

Covers the B5 bulk status transition endpoint
(``POST /api/v1/dispatch/trips/bulk-status``).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.dependencies import get_trip_service
from backend.dependencies_security import require_dispatcher

BASE = "/api/v1/dispatch"


def _make_client(app, service, company_id: int = 1):
    """Build a TestClient with ``require_dispatcher`` -> ``company_id`` user."""
    app.dependency_overrides[get_trip_service] = lambda: service
    app.dependency_overrides[require_dispatcher] = lambda: {
        "id": 1, "email": "test@test.com", "role": "dispatcher",
        "company_id": company_id,
    }
    return TestClient(app, raise_server_exceptions=False)


def _ok_result(status: str):
    from models.common import ServiceResult
    from models.trip_models import TripResult
    return ServiceResult(
        success=True,
        data=TripResult(
            id=1, client_id=1, reference="", start_date="2000-01-01",
            price_eur=0.0, currency="EUR", status=status,
        ),
    )


class TestBulkStatusEndpoint:
    """POST /api/v1/dispatch/trips/bulk-status"""

    def test_bulk_status_returns_updated_and_failed(self, app):
        svc = MagicMock()
        trips = {
            1: {"id": 1, "status": "Planned"},
            2: {"id": 2, "status": "In Transit"},
            3: {"id": 3, "status": "Delivered"},
        }
        svc.get_by_id.side_effect = lambda trip_id, **kw: trips.get(trip_id)
        svc.update.return_value = _ok_result("Cancelled")

        client = _make_client(app, svc)
        resp = client.post(
            f"{BASE}/trips/bulk-status",
            json={"trip_ids": [1, 2, 3], "status": "Cancelled"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Planned→Cancelled, In Transit→Cancelled, Delivered→Cancelled all valid.
        assert sorted(data["updated"]) == [1, 2, 3]
        assert data["failed"] == []

    def test_bulk_status_invalid_transition_fails_per_trip(self, app):
        svc = MagicMock()
        svc.get_by_id.side_effect = lambda trip_id, **kw: {
            "id": trip_id, "status": "Planned",
        }
        svc.update.return_value = _ok_result("Planned")

        client = _make_client(app, svc)
        resp = client.post(
            f"{BASE}/trips/bulk-status",
            json={"trip_ids": [1], "status": "Paid"},  # Planned→Paid is invalid
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == []
        assert len(data["failed"]) == 1
        assert data["failed"][0]["trip_id"] == 1
        assert "Cannot transition" in data["failed"][0]["error"]
        svc.update.assert_not_called()

    def test_bulk_status_update_failure_reported_per_trip(self, app):
        from models.common import ErrorDetail, ServiceResult
        svc = MagicMock()
        svc.get_by_id.side_effect = lambda trip_id, **kw: {
            "id": trip_id, "status": "Planned",
        }
        svc.update.return_value = ServiceResult(
            success=False,
            errors=[ErrorDetail(message="boom", code="internal_error")],
        )

        client = _make_client(app, svc)
        resp = client.post(
            f"{BASE}/trips/bulk-status",
            json={"trip_ids": [1], "status": "Loading"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == []
        assert data["failed"] == [{"trip_id": 1, "error": "boom"}]

    def test_bulk_status_company_scoped_trip_not_found(self, app):
        """A trip outside the caller's company resolves as not found -> failed."""
        svc = MagicMock()
        # Simulate scoping: only trip 1 belongs to the caller's company.
        svc.get_by_id.side_effect = lambda trip_id, **kw: (
            {"id": trip_id, "status": "Planned"} if trip_id == 1 else None
        )
        svc.update.return_value = _ok_result("Loading")

        client = _make_client(app, svc)
        resp = client.post(
            f"{BASE}/trips/bulk-status",
            json={"trip_ids": [1, 999], "status": "Loading"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == [1]
        assert data["failed"] == [{"trip_id": 999, "error": "Trip not found"}]

    def test_bulk_status_passes_company_id_to_service(self, app):
        """Every lookup/update must be scoped by the JWT company_id."""
        svc = MagicMock()
        svc.get_by_id.return_value = {"id": 1, "status": "Planned"}
        svc.update.return_value = _ok_result("Loading")

        client = _make_client(app, svc)
        resp = client.post(
            f"{BASE}/trips/bulk-status",
            json={"trip_ids": [1], "status": "Loading"},
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == [1]
        svc.get_by_id.assert_called_once_with(1, company_id=1)
        assert svc.update.call_args.kwargs["company_id"] == 1