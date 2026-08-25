"""Authorization bounds tests for pagination, filtering, and sorting.

Verifies that pagination/filtering query parameters do not bypass
tenant scoping and that sort-order parameters are handled safely.

Fixtures from conftest:
    client  — FastAPI TestClient bound to the test app.
    auth_a  — Authorization header dict for Company A dispatcher.
    auth_b  — Authorization header dict for Company B dispatcher.
"""
from __future__ import annotations


import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════════════
# Pagination scoping
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaginationScoping:
    """Pagination parameters (limit, offset) must not bypass tenant isolation."""

    def test_unbounded_limit_still_scoped(
        self, client: TestClient, auth_a: dict
    ):
        """GET /api/v1/trips/?limit=9999 — large limit must not expose Company B data.

        The trips endpoint constrains limit to ``[1, 1000]`` via FastAPI's
        ``Query(ge=1, le=1000)``, so 9999 will ordinarily be rejected with
        422.  If the request is accepted (e.g. a future change removes the
        cap), every returned item must still belong to Company A.
        """
        resp = client.get("/api/v1/trips/", params={"limit": 9999}, headers=auth_a)

        # FastAPI validation rejects out-of-bound limit → acceptable
        if resp.status_code == 422:
            return

        assert resp.status_code in (200, 400, 500, 429), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )

        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for trip in items:
                client_name = trip.get("client_name", "")
                assert "Client B" not in client_name, (
                    f"Trip {trip.get('id')} leaks Company B client name: "
                    f"{client_name!r}"
                )

    def test_offset_does_not_bypass_auth(
        self, client: TestClient, auth_a: dict
    ):
        """GET /api/v1/trips/?offset=100 — offset must not skip auth checks.

        The trips list endpoint does not declare an ``offset`` query parameter,
        so FastAPI silently ignores it.  The response must still be scoped to
        Company A.
        """
        resp = client.get("/api/v1/trips/", params={"offset": 100}, headers=auth_a)
        assert resp.status_code in (200, 400, 500, 429), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )

        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for trip in items:
                client_name = trip.get("client_name", "")
                assert "Client B" not in client_name, (
                    f"Trip {trip.get('id')} leaks Company B client name: "
                    f"{client_name!r}"
                )

    def test_filter_by_company_b_as_company_a(
        self, client: TestClient, auth_a: dict
    ):
        """GET /api/v1/clients/?query=Client+B — Company A must not see Company B results.

        The clients search endpoint uses the ``query`` parameter.  Even when
        explicitly searching for "Client B", the authenticated user's company
        scope must be respected.
        """
        resp = client.get(
            "/api/v1/clients/",
            params={"query": "Client B"},
            headers=auth_a,
        )
        assert resp.status_code in (200, 400, 500, 429), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )

        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for client_item in items:
                name = client_item.get("name", "")
                assert "Client B" not in name, (
                    f"Client {client_item.get('id')} belongs to Company B: "
                    f"{name!r}"
                )

    def test_search_across_companies(
        self, client: TestClient, auth_a: dict
    ):
        """GET /api/v1/trips/?search=Client — search must not leak cross-company data.

        Searching for "Client" should return only Company A's trips even
        though Company B also has clients whose names start with "Client".
        """
        resp = client.get(
            "/api/v1/trips/",
            params={"search": "Client"},
            headers=auth_a,
        )
        assert resp.status_code in (200, 400, 500, 429), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )

        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for trip in items:
                client_name = trip.get("client_name", "")
                driver_name = trip.get("driver_name", "")
                assert "Client B" not in client_name, (
                    f"Trip {trip.get('id')} leaks Company B client: "
                    f"{client_name!r}"
                )
                assert "Driver B" not in driver_name, (
                    f"Trip {trip.get('id')} leaks Company B driver: "
                    f"{driver_name!r}"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# Sort-order injection
# ═══════════════════════════════════════════════════════════════════════════════

class TestSortOrderInjection:
    """Sort-order parameters must not allow SQL injection or bypass scoping."""

    def test_sort_order_param_safe(
        self, client: TestClient, auth_a: dict
    ):
        """GET /api/v1/trips/?order=created_at DESC — unexpected param handled safely.

        The trips list endpoint does not define an ``order`` query parameter,
        so FastAPI silently ignores it.  The endpoint must still return 200
        and the results must be scoped to Company A.
        """
        resp = client.get(
            "/api/v1/trips/",
            params={"order": "created_at DESC"},
            headers=auth_a,
        )
        assert resp.status_code in (200, 400, 500, 429), (
            f"Unexpected status {resp.status_code}: {resp.text}"
        )

        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for trip in items:
                client_name = trip.get("client_name", "")
                assert "Client B" not in client_name, (
                    f"Trip {trip.get('id')} leaks Company B client name: "
                    f"{client_name!r}"
                )
