"""Tests for the Payment Profiles API endpoints.

GET    /payment-profiles/                 — paginated list
GET    /payment-profiles/{profile_id}     — single profile
POST   /payment-profiles/                — create
PATCH  /payment-profiles/{profile_id}    — partial update
PUT    /payment-profiles/{profile_id}    — deprecated full update
DELETE /payment-profiles/{profile_id}    — delete
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BASE = "/api/v1/payment-profiles"


# The payment_profiles router is NOT included in backend.api.v1.router,
# so we include it manually in each test via _make_app().
def _make_app():
    """Return a FastAPI app with the payment-profiles router registered."""
    from backend.api.v1.payment_profiles import router as payment_profiles_router
    from backend.api.v1.router import api_v1_router

    app = FastAPI()
    app.include_router(api_v1_router)
    app.include_router(payment_profiles_router, prefix="/api/v1")
    return app


def _override_deps(app, mock_svc):
    """Set up dependency overrides for PaymentProfileService + auth."""
    from backend.dependencies import get_payment_profile_service
    from backend.dependencies_security import require_dispatcher

    mock_user = {"id": 1, "company_id": 1}
    app.dependency_overrides[get_payment_profile_service] = lambda: mock_svc
    app.dependency_overrides[require_dispatcher] = lambda: mock_user


class TestListPaymentProfiles:
    """GET /api/v1/payment-profiles/"""

    def test_list_success(self):
        """List all payment profiles returns 200 with paginated response."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_all.return_value = [
            {"id": 1, "profile_name": "Standard", "is_active": True},
            {"id": 2, "profile_name": "Premium", "is_active": True},
        ]
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.get(f"{BASE}/")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 20
        mock_svc.get_all.assert_called_once_with(include_inactive=False, limit=20)
        app.dependency_overrides.clear()

    def test_list_with_query_search(self):
        """List with search query calls service.search()."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.search.return_value = [
            {"id": 1, "profile_name": "Standard", "is_active": True},
        ]
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.get(f"{BASE}/", params={"query": "Standard"})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["profile_name"] == "Standard"
        mock_svc.search.assert_called_once_with("Standard", limit=20)
        app.dependency_overrides.clear()

    def test_list_with_include_inactive(self):
        """include_inactive=True is passed to service.get_all()."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_all.return_value = [
            {"id": 1, "profile_name": "Standard", "is_active": True},
            {"id": 2, "profile_name": "Inactive", "is_active": False},
        ]
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.get(f"{BASE}/", params={"include_inactive": "true"})

        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2
        mock_svc.get_all.assert_called_once_with(include_inactive=True, limit=20)
        app.dependency_overrides.clear()

    def test_list_with_pagination(self):
        """Pagination params are passed to service and response."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_all.return_value = [
            {"id": 3, "profile_name": "Profile 3", "is_active": True},
        ]
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.get(f"{BASE}/", params={"page": "2", "page_size": "5"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["page_size"] == 5
        mock_svc.get_all.assert_called_once_with(include_inactive=False, limit=5)
        app.dependency_overrides.clear()

    def test_list_service_error_returns_500(self):
        """Service exception propagates as 500."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_all.side_effect = Exception("DB error")
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.get(f"{BASE}/")

        assert resp.status_code == 500
        data = resp.json()
        assert "Operation failed" in data["detail"]
        app.dependency_overrides.clear()


class TestGetPaymentProfile:
    """GET /api/v1/payment-profiles/{profile_id}"""

    def test_get_success(self):
        """Get single payment profile returns 200 with profile data."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"id": 1, "profile_name": "Standard", "is_active": True}
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.get(f"{BASE}/1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["profile_name"] == "Standard"
        mock_svc.get_by_id.assert_called_once_with(1)
        app.dependency_overrides.clear()

    def test_get_not_found_returns_404(self):
        """Non-existent profile returns 404."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = None
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.get(f"{BASE}/999")

        assert resp.status_code == 404
        data = resp.json()
        assert "not found" in data["detail"].lower()
        app.dependency_overrides.clear()

    def test_get_service_error_returns_500(self):
        """Service exception propagates as 500."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.side_effect = Exception("DB error")
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.get(f"{BASE}/1")

        assert resp.status_code == 500
        app.dependency_overrides.clear()

    def test_get_invalid_id_returns_422(self):
        """Non-integer profile_id returns 422."""
        app = _make_app()
        mock_svc = MagicMock()
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.get(f"{BASE}/abc")

        assert resp.status_code == 422
        app.dependency_overrides.clear()


class TestCreatePaymentProfile:
    """POST /api/v1/payment-profiles/"""

    def test_create_success(self):
        """Create payment profile returns 201 with new id."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.create.return_value = 42
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.post(
            f"{BASE}/",
            json={"profile_name": "Standard", "client_id": 1, "payment_term_days": 30, "currency": "EUR"},
        )

        assert resp.status_code == 201
        assert resp.json() == {"id": 42}
        mock_svc.create.assert_called_once()
        app.dependency_overrides.clear()

    def test_create_with_all_fields(self):
        """Create with all optional fields populates data correctly."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.create.return_value = 7
        _override_deps(app, mock_svc)

        client = TestClient(app)
        payload = {
            "name": "Premium",
            "client_id": 2,
            "payment_term_days": 60,
            "currency": "USD",
            "notes": "Test profile",
            "is_active": True,
        }
        resp = client.post(f"{BASE}/", json=payload)

        assert resp.status_code == 201
        assert resp.json() == {"id": 7}
        app.dependency_overrides.clear()

    def test_create_validation_error_empty_body(self):
        """Sending a non-dict value returns 422."""
        app = _make_app()
        mock_svc = MagicMock()
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.post(f"{BASE}/", json="not_a_dict")

        assert resp.status_code == 422
        app.dependency_overrides.clear()

    def test_create_service_error_returns_500(self):
        """Service exception propagates as 500."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.create.side_effect = Exception("DB error")
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.post(
            f"{BASE}/",
            json={"profile_name": "Standard", "client_id": 1, "payment_term_days": 30, "currency": "EUR"},
        )

        assert resp.status_code == 500
        app.dependency_overrides.clear()


class TestUpdatePaymentProfilePartial:
    """PATCH /api/v1/payment-profiles/{profile_id}"""

    def test_patch_success(self):
        """PATCH updates profile fields and returns status."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"id": 1, "profile_name": "Standard", "is_active": True}
        mock_svc.update.return_value = None
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.patch(f"{BASE}/1", json={"profile_name": "Updated Name"})

        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        mock_svc.get_by_id.assert_called_once_with(1)
        mock_svc.update.assert_called_once_with(1, {"profile_name": "Updated Name"})
        app.dependency_overrides.clear()

    def test_patch_not_found_returns_404(self):
        """PATCH on non-existent profile returns 404."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = None
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.patch(f"{BASE}/999", json={"profile_name": "Updated"})

        assert resp.status_code == 404
        mock_svc.update.assert_not_called()
        app.dependency_overrides.clear()

    def test_patch_empty_update_noop(self):
        """PATCH with no fields to update does not call service.update()."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"id": 1, "profile_name": "Standard", "is_active": True}
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.patch(f"{BASE}/1", json={})

        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        mock_svc.get_by_id.assert_called_once_with(1)
        mock_svc.update.assert_not_called()
        app.dependency_overrides.clear()

    def test_patch_service_error_on_get_returns_500(self):
        """Service exception on get_by_id propagates as 500."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.side_effect = Exception("DB error")
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.patch(f"{BASE}/1", json={"profile_name": "Updated"})

        assert resp.status_code == 500
        app.dependency_overrides.clear()

    def test_patch_service_error_on_update_returns_500(self):
        """Service exception on update propagates as 500."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"id": 1, "profile_name": "Standard", "is_active": True}
        mock_svc.update.side_effect = Exception("DB error")
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.patch(f"{BASE}/1", json={"profile_name": "Updated"})

        assert resp.status_code == 500
        app.dependency_overrides.clear()

    def test_patch_validation_error_invalid_data(self):
        """Invalid field in body returns 422 (extra fields forbidden in PaymentProfileUpdate)."""
        app = _make_app()
        mock_svc = MagicMock()
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.patch(f"{BASE}/1", json={"unknown_field": "value"})

        assert resp.status_code == 422
        app.dependency_overrides.clear()


class TestUpdatePaymentProfileDeprecated:
    """PUT /api/v1/payment-profiles/{profile_id} (deprecated)"""

    def test_put_success_with_deprecation_headers(self):
        """PUT returns 200 with Deprecation and Sunset headers."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"id": 1, "profile_name": "Standard", "is_active": True}
        mock_svc.update.return_value = None
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.put(f"{BASE}/1", json={"profile_name": "Updated Name"})

        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        assert resp.headers.get("deprecation") == "true"
        assert resp.headers.get("sunset") == "Tue, 12 Jan 2027 00:00:00 GMT"
        mock_svc.get_by_id.assert_called_once_with(1)
        mock_svc.update.assert_called_once_with(1, {"profile_name": "Updated Name"})
        app.dependency_overrides.clear()

    def test_put_not_found_returns_404(self):
        """PUT on non-existent profile returns 404."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = None
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.put(f"{BASE}/999", json={"profile_name": "Updated"})

        assert resp.status_code == 404
        mock_svc.update.assert_not_called()
        app.dependency_overrides.clear()

    def test_put_no_update_fields(self):
        """PUT with no update fields does not call service.update()."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"id": 1, "profile_name": "Standard", "is_active": True}
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.put(f"{BASE}/1", json={})

        assert resp.status_code == 200
        mock_svc.update.assert_not_called()
        app.dependency_overrides.clear()

    def test_put_service_error_on_get_returns_500(self):
        """Service exception on get_by_id propagates as 500."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.side_effect = Exception("DB error")
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.put(f"{BASE}/1", json={"profile_name": "Updated"})

        assert resp.status_code == 500
        app.dependency_overrides.clear()

    def test_put_service_error_on_update_returns_500(self):
        """Service exception on update propagates as 500."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"id": 1, "profile_name": "Standard", "is_active": True}
        mock_svc.update.side_effect = Exception("DB error")
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.put(f"{BASE}/1", json={"profile_name": "Updated"})

        assert resp.status_code == 500
        app.dependency_overrides.clear()


class TestDeletePaymentProfile:
    """DELETE /api/v1/payment-profiles/{profile_id}"""

    def test_delete_success(self):
        """Delete returns 200 with status."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"id": 1, "profile_name": "Standard", "is_active": True}
        mock_svc.delete.return_value = None
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.delete(f"{BASE}/1")

        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}
        mock_svc.get_by_id.assert_called_once_with(1)
        mock_svc.delete.assert_called_once_with(1)
        app.dependency_overrides.clear()

    def test_delete_not_found_returns_404(self):
        """Delete on non-existent profile returns 404."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = None
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.delete(f"{BASE}/999")

        assert resp.status_code == 404
        mock_svc.delete.assert_not_called()
        app.dependency_overrides.clear()

    def test_delete_service_error_on_get_returns_500(self):
        """Service exception on get_by_id propagates as 500."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.side_effect = Exception("DB error")
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.delete(f"{BASE}/1")

        assert resp.status_code == 500
        app.dependency_overrides.clear()

    def test_delete_service_error_on_delete_returns_500(self):
        """Service exception on delete propagates as 500."""
        app = _make_app()
        mock_svc = MagicMock()
        mock_svc.get_by_id.return_value = {"id": 1, "profile_name": "Standard", "is_active": True}
        mock_svc.delete.side_effect = Exception("DB error")
        _override_deps(app, mock_svc)

        client = TestClient(app)
        resp = client.delete(f"{BASE}/1")

        assert resp.status_code == 500
        app.dependency_overrides.clear()
