"""Mobile driver endpoint tests (blueprint §6.2) — real DB, role-scoped clients.

Covers: paginated list + search + derived-status filter + expiring_within_days,
create/detail/patch, permission gates, and the tachograph timeline endpoint.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

BASE = "/api/v1/mobile/drivers"


def _seed_driver(db, name: str, *, phone="0700000000", license_number="LIC-1",
                 license_expiry=None, medical_expiry=None, adr_certificate_expiry=None,
                 company_id: int = 1, is_active: int = 1) -> int:
    cur = db.execute(
        "INSERT INTO drivers (name, phone, email, license_number, license_category, "
        "license_expiry, medical_expiry, adr_certificate_expiry, is_active, company_id, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'C', ?, ?, ?, ?, ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
        (name, phone, f"{name}@test.com", license_number, license_expiry, medical_expiry,
         adr_certificate_expiry, is_active, company_id),
    )
    db.conn.commit()
    return cur.lastrowid


def _seed_truck(db, truck_id: int = 1) -> None:
    db.execute(
        "INSERT OR IGNORE INTO trucks (id, plate_number, manufacturer, model, status, year, vin, company_id) "
        "VALUES (?, 'T-TRUCK', 'Volvo', 'FH', 'Active', 2022, 'VIN-T', 1)",
        (truck_id,),
    )
    db.conn.commit()


def _seed_assignment(db, driver_id: int, truck_id: int = 1) -> None:
    _seed_truck(db, truck_id)
    # driver_truck_assignments has no company_id column.
    db.execute(
        "INSERT INTO driver_truck_assignments (driver_id, truck_id, assigned_at, active) "
        "VALUES (?, ?, datetime('now'), 1)",
        (driver_id, truck_id),
    )
    db.conn.commit()


def _seed_trip(db, driver_id: int, status: str = "Planned") -> None:
    db.execute(
        "INSERT INTO trips (created_at, driver_name, status, driver_id, company_id) "
        "VALUES ('2026-01-01T00:00:00Z', 'D', ?, ?, 1)",
        (status, driver_id),
    )
    db.conn.commit()


def _seed_tacho(db, driver_id: int, day: str, *, driving=480, work=60, rest=420, avail=480) -> int:
    imp = db.execute(
        "INSERT INTO tacho_imports (file_name, file_type, file_hash) VALUES ('f.ddd', 'ddd', 'h')"
    ).lastrowid
    # tacho_driver_activity has no company_id column.
    db.execute(
        "INSERT INTO tacho_driver_activity (import_id, driver_id, activity_date, driving_minutes, "
        "work_minutes, rest_minutes, avail_minutes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (imp, driver_id, day, driving, work, rest, avail),
    )
    db.conn.commit()
    return imp


class TestDriversList:
    def test_list_paginated(self, mobile_app, real_db, dispatcher_client):
        for i in range(3):
            _seed_driver(real_db, f"Driver {i}")
        resp = dispatcher_client.get(f"{BASE}?page=1&page_size=2&expiring_within_days=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["total_pages"] == 2

    def test_search(self, mobile_app, real_db, dispatcher_client):
        _seed_driver(real_db, "Alice", license_number="LIC-ALICE")
        _seed_driver(real_db, "Bob", license_number="LIC-BOB")
        resp = dispatcher_client.get(f"{BASE}?search=ALICE&expiring_within_days=0")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Alice"

    def test_search_by_license_number(self, mobile_app, real_db, dispatcher_client):
        _seed_driver(real_db, "Alice", license_number="LIC-ALICE")
        resp = dispatcher_client.get(f"{BASE}?search=LIC-ALICE&expiring_within_days=0")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    def test_derived_status_filter(self, mobile_app, real_db, dispatcher_client):
        d_off = _seed_driver(real_db, "Off-Driver")
        d_avail = _seed_driver(real_db, "Avail-Driver")
        d_driving = _seed_driver(real_db, "Driving-Driver")
        _seed_assignment(real_db, d_avail)
        _seed_trip(real_db, d_driving, status="In Transit")

        resp = dispatcher_client.get(f"{BASE}?status=driving&expiring_within_days=0")
        assert [i["name"] for i in resp.json()["items"]] == ["Driving-Driver"]

        resp = dispatcher_client.get(f"{BASE}?status=available&expiring_within_days=0")
        assert [i["name"] for i in resp.json()["items"]] == ["Avail-Driver"]

        resp = dispatcher_client.get(f"{BASE}?status=off&expiring_within_days=0")
        assert [i["name"] for i in resp.json()["items"]] == ["Off-Driver"]

    def test_expiring_within_days(self, mobile_app, real_db, dispatcher_client):
        soon = (date.today() + timedelta(days=10)).isoformat()
        later = (date.today() + timedelta(days=40)).isoformat()
        d_soon = _seed_driver(real_db, "Soon", license_expiry=soon)
        d_later = _seed_driver(real_db, "Later", license_expiry=later)
        resp = dispatcher_client.get(f"{BASE}?expiring_within_days=30")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert [i["id"] for i in items] == [d_soon]
        assert d_later not in [i["id"] for i in items]

    def test_company_isolation(self, mobile_app, real_db, dispatcher_client):
        _seed_driver(real_db, "Mine")
        _seed_driver(real_db, "Other", company_id=2)
        resp = dispatcher_client.get(f"{BASE}?expiring_within_days=0")
        assert resp.json()["total"] == 1


class TestDriversCreate:
    def test_admin_create(self, mobile_app, real_db, admin_client):
        resp = admin_client.post(
            BASE, json={"name": "New Driver", "phone": "0711111111", "license_number": "LIC-NEW"}
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "New Driver"
        assert body["company_id"] == 1
        assert body["status"] == "off"

    def test_dispatcher_create_denied(self, mobile_app, real_db, dispatcher_client):
        resp = dispatcher_client.post(BASE, json={"name": "Denied"})
        assert resp.status_code == 403

    def test_create_validation_error(self, mobile_app, real_db, admin_client):
        resp = admin_client.post(BASE, json={})
        assert resp.status_code == 422


class TestDriversDetail:
    def test_get_driver(self, mobile_app, real_db, dispatcher_client):
        driver_id = _seed_driver(real_db, "Alice", license_number="LIC-A")
        _seed_assignment(real_db, driver_id)
        resp = dispatcher_client.get(f"{BASE}/{driver_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == driver_id
        assert body["status"] == "available"
        assert body["current_truck_id"] == 1

    def test_get_missing_404(self, mobile_app, real_db, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}/999999")
        assert resp.status_code == 404

    def test_get_other_company_404(self, mobile_app, real_db, dispatcher_client):
        driver_id = _seed_driver(real_db, "Other", company_id=2)
        resp = dispatcher_client.get(f"{BASE}/{driver_id}")
        assert resp.status_code == 404


class TestDriversUpdate:
    def test_admin_update(self, mobile_app, real_db, admin_client):
        driver_id = _seed_driver(real_db, "Alice")
        resp = admin_client.patch(f"{BASE}/{driver_id}", json={"phone": "0722222222", "is_active": False})
        assert resp.status_code == 200
        assert resp.json()["phone"] == "0722222222"
        assert resp.json()["is_active"] is False

    def test_dispatcher_update_denied(self, mobile_app, real_db, dispatcher_client):
        driver_id = _seed_driver(real_db, "Alice")
        resp = dispatcher_client.patch(f"{BASE}/{driver_id}", json={"phone": "0722222222"})
        assert resp.status_code == 403


class TestDriversTacho:
    def test_tacho_timeline(self, mobile_app, real_db, dispatcher_client):
        driver_id = _seed_driver(real_db, "Alice")
        _seed_tacho(real_db, driver_id, "2026-01-03", driving=480, work=60, rest=420, avail=480)
        _seed_tacho(real_db, driver_id, "2026-01-05", driving=240, work=120, rest=360, avail=720)
        resp = dispatcher_client.get(f"{BASE}/{driver_id}/tacho?start_date=2026-01-01&end_date=2026-01-07")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["days"]) == 2
        day_by_date = {d["date"]: d for d in body["days"]}
        assert day_by_date["2026-01-03"]["driving_minutes"] == 480
        assert day_by_date["2026-01-03"]["working_minutes"] == 60
        assert day_by_date["2026-01-03"]["rest_minutes"] == 420
        assert day_by_date["2026-01-03"]["availability_minutes"] == 480
        assert body["weekly_driving_minutes"] == 720
        assert body["weekly_limit_minutes"] == 3360

    def test_tacho_outside_range_excluded(self, mobile_app, real_db, dispatcher_client):
        driver_id = _seed_driver(real_db, "Alice")
        _seed_tacho(real_db, driver_id, "2026-02-01", driving=600, work=0, rest=0, avail=0)
        resp = dispatcher_client.get(f"{BASE}/{driver_id}/tacho?start_date=2026-01-01&end_date=2026-01-07")
        assert resp.status_code == 200
        body = resp.json()
        assert body["days"] == []
        assert body["weekly_driving_minutes"] == 0

    def test_tacho_other_company_404(self, mobile_app, real_db, dispatcher_client):
        driver_id = _seed_driver(real_db, "Other", company_id=2)
        resp = dispatcher_client.get(f"{BASE}/{driver_id}/tacho")
        assert resp.status_code == 404

    def test_tacho_invalid_date_422(self, mobile_app, real_db, dispatcher_client):
        driver_id = _seed_driver(real_db, "Alice")
        resp = dispatcher_client.get(f"{BASE}/{driver_id}/tacho?start_date=not-a-date")
        assert resp.status_code == 422
