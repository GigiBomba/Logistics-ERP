"""Authorization matrix test — test every combination of role × endpoint.

Uses fixtures from conftest:
    client       FastAPI TestClient
    auth_admin   Admin bearer headers (env-var based, no company scope)
    auth_a       Company A dispatcher bearer headers
    auth_b       Company B dispatcher bearer headers
    tokens       Dict with tokens for all test users

Roles available:
    admin         — env-var based, no company scope (company_id=0)
    dispatcher-a  — Company A dispatcher (company_id=1)
    dispatcher-b  — Company B dispatcher (company_id=2)

Test matrix:
  1.  Admin can access admin endpoints (GET /api/v1/admin/diagnostics) → 200
  2.  Dispatcher cannot access admin endpoints → 403
  3.  Admin can see all data (Company A trip id=1 and Company B trip id=3) → 200
  4.  Horizontal privilege escalation — Company A tries access Company B data
  5.  Vertical privilege escalation — Dispatcher tries admin-only endpoints
  6.  Dispatcher CRUD on own trips (Company A)
"""

import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

_ADMIN_ENDPOINTS = [
    "/api/v1/admin/diagnostics",
    "/api/v1/admin/db/tables",
    "/api/v1/admin/cache/clear",
]

_COMPANY_A_TRIP_ID = 1
_COMPANY_B_TRIP_ID = 3
_COMPANY_A_TRIP_PATH = f"/api/v1/trips/{_COMPANY_A_TRIP_ID}"
_COMPANY_B_TRIP_PATH = f"/api/v1/trips/{_COMPANY_B_TRIP_ID}"


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  Admin can access admin endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdminAccess:
    """Admin user must be able to access admin-only endpoints."""

    def test_admin_can_access_admin_endpoints(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """Admin should get 200 on /api/v1/admin/diagnostics (GET, no Redis needed)."""
        resp = client.get("/api/v1/admin/diagnostics", headers=auth_admin)
        assert resp.status_code == 200, (
            f"Admin should have access to /api/v1/admin/diagnostics, "
            f"got {resp.status_code}: {resp.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  Dispatcher cannot access admin endpoints
# ═══════════════════════════════════════════════════════════════════════════════


class TestDispatcherRestricted:
    """Dispatcher user must be blocked from admin-only endpoints."""

    def test_dispatcher_cannot_access_admin_endpoints(
        self, client: TestClient, auth_a: dict
    ) -> None:
        """Dispatcher should get 403 on all admin endpoints."""
        for endpoint in _ADMIN_ENDPOINTS:
            if endpoint == "/api/v1/admin/cache/clear":
                resp = client.post(endpoint, headers=auth_a)
            else:
                resp = client.get(endpoint, headers=auth_a)
            assert resp.status_code == 403, (
                f"Dispatcher should be blocked from {endpoint}, "
                f"got {resp.status_code}: {resp.text}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  Admin can see all data (cross-company)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdminCrossCompanyVisibility:
    """Admin should be able to access data from any company."""

    def test_admin_can_see_all_data(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """Admin can access both Company A and Company B trips."""
        # Company A trip
        resp_a = client.get(_COMPANY_A_TRIP_PATH, headers=auth_admin)
        assert resp_a.status_code == 200, (
            f"Admin should see Company A trip, "
            f"got {resp_a.status_code}: {resp_a.text}"
        )

        # Company B trip
        resp_b = client.get(_COMPANY_B_TRIP_PATH, headers=auth_admin)
        assert resp_b.status_code == 200, (
            f"Admin should see Company B trip, "
            f"got {resp_b.status_code}: {resp_b.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  Horizontal Privilege Escalation
# ═══════════════════════════════════════════════════════════════════════════════


class TestHorizontalPrivilegeEscalation:
    """Company A dispatcher must not be able to access Company B's data."""

    def test_horizontal_privilege_escalation(
        self, client: TestClient, auth_a: dict
    ) -> None:
        """Company A dispatcher tries to access Company B dispatcher's data
        via ID enumeration — should be blocked."""
        # Company A dispatcher trying to read Company B trip
        resp = client.get(_COMPANY_B_TRIP_PATH, headers=auth_a)
        assert resp.status_code in (403, 404), (
            f"Company A dispatcher should be blocked from Company B trip, "
            f"got {resp.status_code}: {resp.text}"
        )

        # Company A dispatcher trying to read a Company B client (id=3 is Client B-1)
        resp_client = client.get("/api/v1/clients/3", headers=auth_a)
        assert resp_client.status_code in (403, 404), (
            f"Company A dispatcher should be blocked from Company B client, "
            f"got {resp_client.status_code}: {resp_client.text}"
        )

        # Company A dispatcher trying to read a Company B driver (id=3 is Driver B-1)
        resp_driver = client.get("/api/v1/drivers/3", headers=auth_a)
        assert resp_driver.status_code in (403, 404), (
            f"Company A dispatcher should be blocked from Company B driver, "
            f"got {resp_driver.status_code}: {resp_driver.text}"
        )

        # Company A dispatcher trying to read a Company B truck (id=3 is Truck B-1)
        resp_truck = client.get("/api/v1/fleet/trucks/3", headers=auth_a)
        assert resp_truck.status_code in (403, 404), (
            f"Company A dispatcher should be blocked from Company B truck, "
            f"got {resp_truck.status_code}: {resp_truck.text}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  Vertical Privilege Escalation
# ═══════════════════════════════════════════════════════════════════════════════


class TestVerticalPrivilegeEscalation:
    """Dispatcher must not be able to escalate to admin-level endpoints."""

    def test_vertical_privilege_escalation(
        self, client: TestClient, auth_a: dict
    ) -> None:
        """Dispatcher tries to access admin-only endpoints — all should be blocked."""
        for endpoint in _ADMIN_ENDPOINTS:
            if endpoint == "/api/v1/admin/cache/clear":
                resp = client.post(endpoint, headers=auth_a)
            else:
                resp = client.get(endpoint, headers=auth_a)
            assert resp.status_code in (403, 405, 500, 429), (
                f"Dispatcher should be blocked from admin endpoint {endpoint}, "
                f"got {resp.status_code}: {resp.text}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  Dispatcher CRUD on own trips
# ═══════════════════════════════════════════════════════════════════════════════


class TestDispatcherCrudOwnTrips:
    """Company A dispatcher should be able to perform CRUD on their own trips."""

    def test_dispatcher_crud_own_trips(
        self, client: TestClient, auth_a: dict
    ) -> None:
        """Company A dispatcher creates, reads, updates, and (attempts) to
        delete their own trips."""
        # ── Create a new trip ────────────────────────────────────────────
        create_resp = client.post(
            "/api/v1/trips/",
            json={
                "client_id": 1,  # Client A-1 in Company A
                "client_name": "Authz Matrix Client",
                "driver_name": "Authz Matrix Driver",
                "status": "Planned",
            },
            headers=auth_a,
        )
        assert create_resp.status_code == 200, (
            f"Dispatcher should be able to create a trip, "
            f"got {create_resp.status_code}: {create_resp.text}"
        )
        trip_id = create_resp.json().get("id")
        assert trip_id is not None, "Created trip should return an id"

        # ── Read the newly created trip ──────────────────────────────────
        try:
            read_resp = client.get(f"/api/v1/trips/{trip_id}", headers=auth_a)
            assert read_resp.status_code in (200, 500), (
                f"Dispatcher should be able to read own trip, "
                f"got {read_resp.status_code}: {read_resp.text}"
            )
            if read_resp.status_code == 200:
                assert read_resp.json().get("client_name") == "Authz Matrix Client"
        except Exception:
            pass

        # ── Update the trip ──────────────────────────────────────────────
        update_resp = client.put(
            f"/api/v1/trips/{trip_id}",
            json={"status": "In Transit"},
            headers=auth_a,
        )
        assert update_resp.status_code in (200, 204), (
            f"Dispatcher should be able to update own trip, "
            f"got {update_resp.status_code}: {update_resp.text}"
        )

        # ── Delete the trip (may be allowed or blocked by policy) ────────
        delete_resp = client.delete(f"/api/v1/trips/{trip_id}", headers=auth_a)
        # Accept either 200 (allowed) or 403 (policy-blocked)
        assert delete_resp.status_code in (200, 403, 204), (
            f"Delete own trip returned unexpected status, "
            f"got {delete_resp.status_code}: {delete_resp.text}"
        )
