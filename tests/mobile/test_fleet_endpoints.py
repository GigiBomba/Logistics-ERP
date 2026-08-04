"""Mobile fleet endpoint tests (blueprint §6.1) — real DB, role-scoped clients.

Covers: paginated list + search + status filter, create/detail/patch/soft-delete,
permission gates (dispatcher 403 on create/update/delete, manager 403 on delete),
422 validation, maintenance list/create, and company isolation.
"""
from __future__ import annotations

import pytest

BASE = "/api/v1/mobile/fleet"


def _seed_truck(db, plate: str, *, manufacturer="Volvo", model="FH", status="Active",
                company_id: int = 1, year: int = 2022) -> int:
    cur = db.execute(
        "INSERT INTO trucks (plate_number, manufacturer, model, status, year, vin, company_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (plate, manufacturer, model, status, year, f"VIN-{plate}", company_id),
    )
    db.conn.commit()
    return cur.lastrowid


def _seed_health(db, truck_id: int, score: int) -> None:
    db.execute(
        "INSERT INTO truck_health_scores (truck_id, score, compliance_pct, overdue_count, "
        "recurring_issues, downtime_days, last_updated) VALUES (?, ?, 100.0, 0, 0, 0, '2026-01-01')",
        (truck_id, score),
    )
    db.conn.commit()


def _seed_assignment(db, truck_id: int, driver_id: int) -> None:
    # driver_truck_assignments has no company_id column; the driver row must
    # exist for the driver_id FK.
    db.execute(
        "INSERT OR IGNORE INTO drivers (id, name, phone, license_number, is_active, company_id, "
        "created_at, updated_at) "
        "VALUES (?, 'Assigned Driver', '0700000000', 'LIC-D', 1, 1, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
        (driver_id,),
    )
    db.execute(
        "INSERT INTO driver_truck_assignments (driver_id, truck_id, assigned_at, active) "
        "VALUES (?, ?, datetime('now'), 1)",
        (driver_id, truck_id),
    )
    db.conn.commit()


class TestFleetList:
    def test_paginated_list(self, mobile_app, real_db, dispatcher_client):
        for plate in ("AB-01-XYZ", "AB-02-XYZ", "AB-03-XYZ"):
            _seed_truck(real_db, plate)
        resp = dispatcher_client.get(f"{BASE}?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 2
        assert {"AB-01-XYZ", "AB-02-XYZ"} <= {i["plate"] for i in data["items"]}

    def test_search(self, mobile_app, real_db, dispatcher_client):
        _seed_truck(real_db, "AB-01-XYZ", model="Actros")
        _seed_truck(real_db, "AB-02-XYZ", model="FH")
        resp = dispatcher_client.get(f"{BASE}?search=Actros")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["model"] == "Actros"

    def test_status_filter(self, mobile_app, real_db, dispatcher_client):
        _seed_truck(real_db, "AB-01-XYZ", status="Active")
        _seed_truck(real_db, "AB-02-XYZ", status="In Service")
        _seed_truck(real_db, "AB-03-XYZ", status="Inactive")
        resp = dispatcher_client.get(f"{BASE}?status=In Service")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["plate"] == "AB-02-XYZ"
        assert items[0]["status"] == "In Service"

    def test_company_isolation(self, mobile_app, real_db, dispatcher_client):
        _seed_truck(real_db, "AB-01-XYZ", company_id=1)
        _seed_truck(real_db, "OTHER-CO", company_id=2)
        resp = dispatcher_client.get(f"{BASE}")
        items = resp.json()["items"]
        assert all(i["plate"] != "OTHER-CO" for i in items)
        assert resp.json()["total"] == 1


class TestFleetCreate:
    def test_admin_create(self, mobile_app, real_db, admin_client):
        resp = admin_client.post(BASE, json={"plate_number": "NEW-01", "manufacturer": "Scania", "model": "R450"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["plate"] == "NEW-01"
        assert body["brand"] == "Scania"
        assert body["model"] == "R450"
        assert body["status"] == "Active"
        assert body["company_id"] == 1

    def test_manager_create_allowed(self, mobile_app, real_db, manager_client):
        resp = manager_client.post(BASE, json={"plate_number": "MGR-01"})
        assert resp.status_code == 201

    def test_dispatcher_create_denied(self, mobile_app, real_db, dispatcher_client):
        resp = dispatcher_client.post(BASE, json={"plate_number": "DISP-01"})
        assert resp.status_code == 403

    def test_driver_create_denied(self, mobile_app, real_db, driver_client):
        resp = driver_client.post(BASE, json={"plate_number": "DRV-01"})
        assert resp.status_code == 403

    def test_create_validation_error(self, mobile_app, real_db, admin_client):
        resp = admin_client.post(BASE, json={})
        assert resp.status_code == 422


class TestFleetDetail:
    def test_get_truck(self, mobile_app, real_db, dispatcher_client):
        truck_id = _seed_truck(real_db, "AB-01-XYZ")
        _seed_health(real_db, truck_id, 87)
        _seed_assignment(real_db, truck_id, driver_id=2)
        resp = dispatcher_client.get(f"{BASE}/{truck_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == truck_id
        assert body["plate"] == "AB-01-XYZ"
        assert body["health_score"] == 87
        assert body["current_driver_id"] == 2

    def test_get_missing_404(self, mobile_app, real_db, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}/999999")
        assert resp.status_code == 404

    def test_get_other_company_404(self, mobile_app, real_db, dispatcher_client):
        truck_id = _seed_truck(real_db, "OTHER-CO", company_id=2)
        resp = dispatcher_client.get(f"{BASE}/{truck_id}")
        assert resp.status_code == 404


class TestFleetUpdate:
    def test_admin_update(self, mobile_app, real_db, admin_client):
        truck_id = _seed_truck(real_db, "AB-01-XYZ")
        resp = admin_client.patch(f"{BASE}/{truck_id}", json={"status": "In Service", "model": "FH500"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "In Service"
        assert body["model"] == "FH500"

    def test_dispatcher_update_denied(self, mobile_app, real_db, dispatcher_client):
        truck_id = _seed_truck(real_db, "AB-01-XYZ")
        resp = dispatcher_client.patch(f"{BASE}/{truck_id}", json={"status": "In Service"})
        assert resp.status_code == 403

    def test_update_other_company_404(self, mobile_app, real_db, admin_client):
        truck_id = _seed_truck(real_db, "OTHER-CO", company_id=2)
        resp = admin_client.patch(f"{BASE}/{truck_id}", json={"status": "In Service"})
        assert resp.status_code == 404


class TestFleetDelete:
    def test_admin_soft_delete(self, mobile_app, real_db, admin_client):
        truck_id = _seed_truck(real_db, "AB-01-XYZ")
        resp = admin_client.delete(f"{BASE}/{truck_id}")
        assert resp.status_code == 204
        row = real_db.execute(
            "SELECT status FROM trucks WHERE id = ?", (truck_id,)
        ).fetchone()
        assert row["status"] == "Inactive"

    def test_manager_delete_denied(self, mobile_app, real_db, manager_client):
        truck_id = _seed_truck(real_db, "AB-01-XYZ")
        resp = manager_client.delete(f"{BASE}/{truck_id}")
        assert resp.status_code == 403

    def test_dispatcher_delete_denied(self, mobile_app, real_db, dispatcher_client):
        truck_id = _seed_truck(real_db, "AB-01-XYZ")
        resp = dispatcher_client.delete(f"{BASE}/{truck_id}")
        assert resp.status_code == 403


class TestMaintenance:
    def test_list_maintenance(self, mobile_app, real_db, dispatcher_client):
        truck_id = _seed_truck(real_db, "AB-01-XYZ")
        for i in range(3):
            real_db.execute(
                "INSERT INTO maintenance_records (truck_id, maintenance_type, date, cost, notes, "
                "service_provider, created_at, company_id) "
                "VALUES (?, 'Oil Change', '2026-0%d-10', 150.0, 'note-%d', 'AutoService', '2026-0%d-10T00:00:00', 1)"
                % (i + 1, i, i + 1),
                (truck_id,),
            )
        real_db.conn.commit()
        resp = dispatcher_client.get(f"{BASE}/{truck_id}/maintenance?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        first = data["items"][0]
        assert first["category"] == "Oil Change"
        assert first["vendor"] == "AutoService"
        assert first["truck_id"] == truck_id

    def test_list_maintenance_other_company_404(self, mobile_app, real_db, dispatcher_client):
        truck_id = _seed_truck(real_db, "OTHER-CO", company_id=2)
        resp = dispatcher_client.get(f"{BASE}/{truck_id}/maintenance")
        assert resp.status_code == 404

    def test_admin_create_maintenance(self, mobile_app, real_db, admin_client):
        truck_id = _seed_truck(real_db, "AB-01-XYZ")
        resp = admin_client.post(
            f"{BASE}/{truck_id}/maintenance",
            json={"date": "2026-03-01", "category": "Tires", "cost": 420.5, "vendor": "TireShop", "notes": "winter set"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["category"] == "Tires"
        assert body["cost"] == 420.5
        assert body["vendor"] == "TireShop"
        assert body["truck_id"] == truck_id

    def test_manager_create_maintenance_allowed(self, mobile_app, real_db, manager_client):
        truck_id = _seed_truck(real_db, "AB-01-XYZ")
        resp = manager_client.post(
            f"{BASE}/{truck_id}/maintenance",
            json={"date": "2026-03-01", "category": "Repair", "cost": 100.0},
        )
        assert resp.status_code == 201

    def test_dispatcher_create_maintenance_denied(self, mobile_app, real_db, dispatcher_client):
        truck_id = _seed_truck(real_db, "AB-01-XYZ")
        resp = dispatcher_client.post(
            f"{BASE}/{truck_id}/maintenance",
            json={"date": "2026-03-01", "category": "Repair", "cost": 100.0},
        )
        assert resp.status_code == 403

    def test_create_maintenance_other_company_404(self, mobile_app, real_db, admin_client):
        truck_id = _seed_truck(real_db, "OTHER-CO", company_id=2)
        resp = admin_client.post(
            f"{BASE}/{truck_id}/maintenance",
            json={"date": "2026-03-01", "category": "Repair"},
        )
        assert resp.status_code == 404


# ── Dispatcher overview (revenue_to_date) ───────────────────────────────────
# Phase-5 contract: DispatcherOverviewResponse.revenue_to_date = month-to-date
# SUM(trips.total_price_eur).  Seeded directly via SQL because the real
# repositories don't own the dispatcher-overview aggregation query.

def _seed_overview_trip(db, start_date: str, price: float, *, company_id: int = 1) -> None:
    db.execute(
        "INSERT INTO trips (company_id, client_id, client_name, driver_id, driver_name, "
        "truck_number, status, start_date, place_of_loading, delivery_country, distance_km, "
        "total_price_eur, net_profit, created_at) "
        "VALUES (?, NULL, 'OV Client', NULL, '', 'OV-TRUCK', 'Delivered', ?, 'Bucharest', "
        "'Vienna', 800, ?, 0.0, ?)",
        (company_id, start_date, price, start_date),
    )
    db.conn.commit()


class TestDispatcherOverviewRevenue:
    def test_revenue_to_date_sums_only_current_month(self, mobile_app, real_db, dispatcher_client):
        from datetime import date, timedelta

        today = date.today()
        first_of_month = today.replace(day=1)
        last_month = (first_of_month - timedelta(days=1)).replace(day=1)

        # In current month → must be counted.
        _seed_overview_trip(real_db, today.isoformat(), 1000.0)
        _seed_overview_trip(real_db, first_of_month.isoformat(), 250.5)
        # Previous month + NULL start_date → must be excluded.
        _seed_overview_trip(real_db, last_month.isoformat(), 9999.0)
        _seed_overview_trip(real_db, "", 7777.0)

        resp = dispatcher_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["revenue_to_date"] == 1250.5

    def test_revenue_to_date_zero_when_no_trips(self, mobile_app, real_db, dispatcher_client):
        resp = dispatcher_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        assert resp.json()["revenue_to_date"] == 0.0

    def test_revenue_to_date_company_scoped(self, mobile_app, real_db, dispatcher_client):
        from datetime import date

        today = date.today()
        _seed_overview_trip(real_db, today.isoformat(), 500.0, company_id=1)
        # Other company's in-month trip must not leak into company 1's total.
        _seed_overview_trip(real_db, today.isoformat(), 8888.0, company_id=2)

        resp = dispatcher_client.get("/api/v1/mobile/dispatcher/overview")
        assert resp.status_code == 200
        assert resp.json()["revenue_to_date"] == 500.0
