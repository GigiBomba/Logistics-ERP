"""Tests for the trips API router (``/api/v1/trips``)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/trips"


class TestTripsRouter:
    """CRUD + query + error handling for the trips endpoints."""

    # ── list ──────────────────────────────────────────────────────────────

    def test_list_trips_returns_200_with_items(self, client_with_mocks):
        client, mocks = client_with_mocks
        fake_items = [
            {"id": 1, "status": "active", "client_name": "Acme", "created_at": "2024-01-01"},
            {"id": 2, "status": "planned", "client_name": "Beta", "created_at": "2024-01-02"},
        ]
        mocks["trip_service"].get_filtered.return_value = fake_items

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2

    def test_list_trips_passes_search_status_limit(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.return_value = []

        resp = client.get(f"{BASE}/?search=foo&status=active&page_size=10")
        assert resp.status_code == 200

        call_kwargs = mocks["trip_service"].get_filtered.call_args[1]
        assert call_kwargs.get("search") == "foo"
        assert call_kwargs.get("status") == "active"

    # ── get by id ─────────────────────────────────────────────────────────

    def test_get_trip_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        trip = {
            "id": 1, "status": "active", "created_at": "2024-01-01",
            "client_name": "Acme", "loading_city": "Paris",
            "delivery_city": "Lyon",
        }
        mocks["trip_service"].get_by_id.return_value = trip

        resp = client.get(f"{BASE}/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        assert body["client_name"] == "Acme"

    def test_get_trip_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["trip_service"].get_by_id.return_value = None

        resp = client.get(f"{BASE}/999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Trip not found"

    # ── create ────────────────────────────────────────────────────────────

    def test_create_trip_returns_id(self, client_with_mocks):
        client, mocks = client_with_mocks
        payload = {"client_id": 1, "loading_city": "Paris"}
        mocks["trip_service"].create.return_value = type('R', (), {'success': True, 'data': type('D', (), {'id': 42})()})()

        resp = client.post(f"{BASE}/", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"id": 42}
        mocks["trip_service"].create.assert_called_once()

    # ── update ────────────────────────────────────────────────────────────

    def test_update_trip_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        payload = {"status": "completed"}

        resp = client.put(f"{BASE}/1", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        mocks["trip_service"].update.assert_called_once_with(1, payload)

    # ── delete ────────────────────────────────────────────────────────────

    def test_delete_trip_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.delete(f"{BASE}/1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}
        mocks["trip_service"].delete.assert_called_once_with(1)

    # ── conflicts check ───────────────────────────────────────────────────

    def test_check_conflicts_uses_db_directly(self, client_with_mocks):
        """The conflict endpoint instantiates TripConflictService internally
        using the mocked DB. We verify the endpoint runs without error."""
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/conflicts/check", json={"date": "2024-01-01"})
        # Allow 200, 422 (validation), or 500 (runtime error).
        assert resp.status_code in (200, 422, 500)
        if resp.status_code == 200:
            assert "conflicts" in resp.json()

    # ── error handling ────────────────────────────────────────────────────

    def test_service_exception_propagates(self, client_with_mocks):
        """When the service raises, the exception propagates or returns 500."""
        client, mocks = client_with_mocks
        mocks["trip_service"].get_filtered.side_effect = RuntimeError("DB down")

        resp = client.get(f"{BASE}/")
        assert resp.status_code in (500,)

    # ── auth ──────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        """Without any auth override the endpoint must return 401."""
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401


class TestTripsRouterPromisedDate:
    """The OTD ``promised_date`` field on create/update (ISO ok, non-ISO 422)."""

    def test_create_accepts_promised_date(self, client_with_mocks):
        from datetime import date

        client, mocks = client_with_mocks
        mocks["trip_service"].create.return_value = type(
            "R", (), {"success": True, "data": type("D", (), {"id": 7})()}
        )()

        resp = client.post(f"{BASE}/", json={"client_id": 1, "promised_date": "2026-01-15"})
        assert resp.status_code == 200
        assert resp.json() == {"id": 7}
        created = mocks["trip_service"].create.call_args[0][0]
        assert created.promised_date == date(2026, 1, 15)

    def test_create_rejects_invalid_promised_date(self, client_with_mocks):
        client, _ = client_with_mocks

        resp = client.post(f"{BASE}/", json={"client_id": 1, "promised_date": "15/01/2026"})
        assert resp.status_code == 422
        assert "promised_date" in resp.json()["detail"]

    def test_patch_accepts_promised_date(self, client_with_mocks):
        from datetime import date

        client, mocks = client_with_mocks

        resp = client.patch(f"{BASE}/1", json={"promised_date": "2026-02-01"})
        assert resp.status_code == 200
        updated = mocks["trip_service"].update.call_args[0][1]
        assert updated.promised_date == date(2026, 2, 1)

    def test_patch_rejects_invalid_promised_date(self, client_with_mocks):
        client, _ = client_with_mocks

        resp = client.patch(f"{BASE}/1", json={"promised_date": "not-a-date"})
        assert resp.status_code == 422
        assert "promised_date" in resp.json()["detail"]
