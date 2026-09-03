"""Tests for the additive batch dashboard endpoint (POST /clients/dashboard-batch).

Purely additive; multi-tenant isolation is the core contract under test.
"""
from __future__ import annotations

BASE = "/api/v1/clients"


def _make_service(mocks):
    """Configure the mocked ClientService for a two-tenant scenario.

    - Requester's clients (company 1): ids 1, 2
    - Another tenant's client: id 99  (get_by_id returns None for it)
    - Unknown id: 777  (get_by_id returns None)
    """
    svc = mocks["client_service"]

    def fake_get_by_id(cid, **kwargs):
        return {"id": cid, "name": f"C{cid}"} if cid in (1, 2) else None

    def fake_dashboard(cid, **kwargs):
        return {"total_revenue": cid * 1000, "total_trips": cid}

    svc.get_by_id.side_effect = fake_get_by_id
    svc.get_client_dashboard.side_effect = fake_dashboard
    return svc


class TestClientDashboardBatch:
    def test_returns_requester_clients_revenue_trip_count(self, client_with_mocks):
        client, mocks = client_with_mocks
        _make_service(mocks)

        resp = client.post(f"{BASE}/dashboard-batch", json={"ids": [1, 2]})
        assert resp.status_code == 200
        data = resp.json()
        items = {it["id"]: it for it in data["items"]}
        assert set(items) == {1, 2}
        assert items[1]["revenue"] == 1000
        assert items[1]["trip_count"] == 1
        assert items[2]["revenue"] == 2000
        assert items[2]["trip_count"] == 2

    def test_isolates_other_tenants_client(self, client_with_mocks):
        """A client id belonging to another tenant must NOT be returned."""
        client, mocks = client_with_mocks
        _make_service(mocks)

        resp = client.post(f"{BASE}/dashboard-batch", json={"ids": [1, 99]})
        assert resp.status_code == 200
        data = resp.json()
        items = {it["id"] for it in data["items"]}
        assert items == {1}
        assert 99 not in items

    def test_unknown_ids_handled_gracefully(self, client_with_mocks):
        client, mocks = client_with_mocks
        _make_service(mocks)

        resp = client.post(f"{BASE}/dashboard-batch", json={"ids": [777]})
        assert resp.status_code == 200
        assert resp.json() == {"items": []}

    def test_empty_ids_returns_empty(self, client_with_mocks):
        client, mocks = client_with_mocks
        _make_service(mocks)

        resp = client.post(f"{BASE}/dashboard-batch", json={"ids": []})
        assert resp.status_code == 200
        assert resp.json() == {"items": []}

    def test_rejects_more_than_200_ids(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/dashboard-batch", json={"ids": list(range(201))})
        assert resp.status_code == 422

    def test_requires_dispatcher_auth(self, app):
        from fastapi.testclient import TestClient
        from backend.dependencies_security import require_dispatcher

        # Remove the auth override so the request is unauthorized.
        saved = app.dependency_overrides.get(require_dispatcher)
        app.dependency_overrides.pop(require_dispatcher, None)
        try:
            resp = TestClient(app).post(
                f"{BASE}/dashboard-batch", json={"ids": [1]}
            )
            assert resp.status_code in (401, 403)
        finally:
            if saved is not None:
                app.dependency_overrides[require_dispatcher] = saved
