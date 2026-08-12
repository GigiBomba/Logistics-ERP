"""Mobile dispatcher reassign endpoint tests (Gate-29 A1).

Covers ``POST /api/v1/mobile/dispatcher/jobs/{transport_id}/reassign``:
happy path (200 + trip row updated), company-scoped trip 404, unknown /
inactive driver 404, and the ``require_dispatcher`` gate (driver → 403).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.mobile.conftest import _override_auth, _role_user

BASE = "/api/v1/mobile/dispatcher/jobs"


class TestReassignTransport:
    def test_happy_path_updates_trip(self, mobile_app, real_db, records_seed, dispatcher_client):
        trip_id = records_seed["trip_1"]
        driver_b = records_seed["driver_Maria Ionescu"]

        resp = dispatcher_client.post(
            f"{BASE}/{trip_id}/reassign", json={"driver_id": driver_b}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "reassigned"
        assert body["transport_id"] == trip_id
        assert body["driver_id"] == driver_b

        row = real_db.execute(
            "SELECT driver_id FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert dict(row)["driver_id"] == driver_b

    def test_foreign_company_transport_404(self, mobile_app, real_db, records_seed, dispatcher_client):
        from tests.mobile.conftest import seed_records

        other = seed_records(real_db, company_id=2)
        other_trip = other["trip_1"]

        resp = dispatcher_client.post(
            f"{BASE}/{other_trip}/reassign", json={"driver_id": records_seed["driver_Ion Popescu"]}
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Transport not found"

    def test_unknown_driver_404(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.post(
            f"{BASE}/{records_seed['trip_1']}/reassign", json={"driver_id": 999999}
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Driver not found"

    def test_inactive_driver_404(self, mobile_app, real_db, records_seed, dispatcher_client):
        driver_id = _seed_inactive_driver(real_db)
        resp = dispatcher_client.post(
            f"{BASE}/{records_seed['trip_1']}/reassign", json={"driver_id": driver_id}
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Driver not found"

    def test_driver_role_403(self, app, real_db, records_seed):
        # Real ``require_dispatcher`` gate: only get_current_user is overridden,
        # so a driver role user is rejected with 403 before the handler runs.
        _override_auth(app, _role_user(4, "driver@test.com", "driver", is_admin=False), require_gates=False)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            f"{BASE}/{records_seed['trip_1']}/reassign", json={"driver_id": records_seed["driver_Ion Popescu"]}
        )
        assert resp.status_code == 403
        app.dependency_overrides.clear()

    def test_reassign_missing_trip_404(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.post(
            f"{BASE}/999999/reassign", json={"driver_id": records_seed["driver_Ion Popescu"]}
        )
        assert resp.status_code == 404


def _seed_inactive_driver(db) -> int:
    cur = db.execute(
        "INSERT INTO drivers (name, phone, license_number, license_category, "
        "is_active, company_id, created_at, updated_at) "
        "VALUES ('Inactive Driver', '0720999999', 'LIC-INACTIVE', 'C', 0, 1, "
        "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
    )
    db.conn.commit()
    return cur.lastrowid
