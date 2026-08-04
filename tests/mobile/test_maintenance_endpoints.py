"""Mobile maintenance endpoint tests (blueprint §6.5) — REAL DB.

Covers: schedule list (fields, overdue flags via the real repo thresholds,
overdue_only filter, next_due derivation), schedule create + permission gates
(dispatcher 403, manager 201, truck 404), and cost-trend aggregation shapes
(monthly + by-type totals).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

BASE = "/api/v1/mobile/maintenance"


class TestMaintenanceScheduleList:
    def test_list_shape(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(f"{BASE}/schedule")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        by_type = {it["maintenance_type"]: it for it in body["items"]}
        assert "Oil Change" in by_type
        item = by_type["Oil Change"]
        assert item["truck_plate"]
        assert item["truck_id"] == finance_seed["trucks"][0]
        assert isinstance(item["overdue"], bool)
        assert item["interval_months"] == 3

    def test_overdue_flags_via_real_thresholds(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(f"{BASE}/schedule")
        body = resp.json()
        by_type = {it["maintenance_type"]: it for it in body["items"]}
        # months-based overdue (last_done 200d ago, interval 3mo)
        assert by_type["Oil Change"]["overdue"] is True
        # months-based NOT overdue (last_done 30d ago, interval 12mo)
        assert by_type["Tire Rotation"]["overdue"] is False
        # fixed-expiry overdue (yesterday)
        assert by_type["Inspection"]["overdue"] is True
        # km-based NOT overdue (truck 2 mileage 0 < last_done 5000 + 50000)
        assert by_type["Brakes"]["overdue"] is False
        # km-based overdue (truck 1 mileage 200000 >= last_done 100000 + 50000)
        assert by_type["Gearbox"]["overdue"] is True

    def test_overdue_only_filter(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(f"{BASE}/schedule", params={"overdue_only": "true"})
        body = resp.json()
        assert body["total"] == 3
        assert all(it["overdue"] for it in body["items"])
        names = {it["maintenance_type"] for it in body["items"]}
        assert names == {"Oil Change", "Inspection", "Gearbox"}

    def test_next_due(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(f"{BASE}/schedule")
        body = resp.json()
        by_type = {it["maintenance_type"]: it for it in body["items"]}
        today = date.today()
        # months: last_done 30d ago + 12 months
        expected = (today - timedelta(days=30)).replace(year=today.year + 1).isoformat()
        assert by_type["Tire Rotation"]["next_due"] == expected
        # fixed expiry
        assert by_type["Inspection"]["next_due"] == (today - timedelta(days=5)).isoformat()
        # km-only cadence → no date-based next_due
        assert by_type["Brakes"]["next_due"] is None

    def test_pagination(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(f"{BASE}/schedule", params={"page": 1, "page_size": 2})
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["total_pages"] >= 3

    def test_list_other_company_empty(self, mobile_app, real_db, records_seed, manager_client):
        # No schedules seeded for company 1 in the plain records seed.
        resp = manager_client.get(f"{BASE}/schedule")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_company_scoped_404(self, mobile_app, real_db, records_seed, manager_client):
        from tests.mobile.conftest import seed_finance, seed_records

        seed_records(real_db, company_id=2)
        seed_finance(real_db, company_id=2)
        resp = manager_client.get(f"{BASE}/schedule")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestMaintenanceScheduleCreate:
    def test_create_manager(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.post(f"{BASE}/schedule", json={
            "truck_id": finance_seed["trucks"][1],
            "maintenance_type": "AC Filter",
            "interval_months": 6,
        })
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["maintenance_type"] == "AC Filter"
        assert body["truck_id"] == finance_seed["trucks"][1]
        assert body["truck_plate"]
        assert body["overdue"] is False

    def test_create_missing_cadence_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.post(f"{BASE}/schedule", json={
            "truck_id": finance_seed["trucks"][0],
            "maintenance_type": "Nothing",
        })
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "missing_cadence"

    def test_create_truck_404(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.post(f"{BASE}/schedule", json={
            "truck_id": 999999,
            "maintenance_type": "Oil Change",
            "interval_months": 3,
        })
        assert resp.status_code == 404

    def test_create_truck_other_company_404(self, mobile_app, real_db, finance_seed, manager_client):
        from tests.mobile.conftest import seed_finance, seed_records

        seed_records(real_db, company_id=2)
        other = seed_finance(real_db, company_id=2)
        resp = manager_client.post(f"{BASE}/schedule", json={
            "truck_id": other["trucks"][0],
            "maintenance_type": "Oil Change",
            "interval_months": 3,
        })
        assert resp.status_code == 404

    def test_dispatcher_403(self, mobile_app, real_db, finance_seed, dispatcher_client):
        resp = dispatcher_client.post(f"{BASE}/schedule", json={
            "truck_id": finance_seed["trucks"][0],
            "maintenance_type": "Oil Change",
            "interval_months": 3,
        })
        assert resp.status_code == 403

    def test_driver_403(self, mobile_app, real_db, finance_seed, driver_client):
        resp = driver_client.post(f"{BASE}/schedule", json={
            "truck_id": finance_seed["trucks"][0],
            "maintenance_type": "Oil Change",
            "interval_months": 3,
        })
        assert resp.status_code == 403


class TestMaintenanceCostTrend:
    def test_monthly_and_by_type(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(f"{BASE}/cost-trend")
        assert resp.status_code == 200
        body = resp.json()
        # Default 1y window: excludes the 400-day-old record.
        monthly = {p["label"]: p["total"] for p in body["monthly"]}
        by_type = {p["label"]: p["total"] for p in body["by_type"]}
        today = date.today()
        this_month = today.strftime("%Y-%m")
        last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        # records: today-30 (300, last month or this), today-10 (1500), today-5 (250), today-60 (900)
        assert sum(monthly.values()) == pytest.approx(300.0 + 1500.0 + 250.0 + 900.0)
        assert by_type["Oil Change"] == pytest.approx(550.0)  # 300 + 250
        assert by_type["Brakes"] == pytest.approx(1500.0)
        assert by_type["Tires"] == pytest.approx(900.0)
        assert "Gearbox" not in by_type  # no maintenance records for it
        assert this_month in monthly or last_month in monthly

    def test_explicit_date_range(self, mobile_app, real_db, finance_seed, manager_client):
        today = date.today()
        resp = manager_client.get(
            f"{BASE}/cost-trend",
            params={
                "start_date": (today - timedelta(days=12)).isoformat(),
                "end_date": (today - timedelta(days=8)).isoformat(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        monthly_total = sum(p["total"] for p in body["monthly"])
        assert monthly_total == pytest.approx(1500.0)  # only the Brakes record

    def test_invalid_date_422(self, mobile_app, real_db, finance_seed, manager_client):
        assert manager_client.get(
            f"{BASE}/cost-trend", params={"start_date": "not-a-date"},
        ).status_code == 422
        assert manager_client.get(
            f"{BASE}/cost-trend", params={"start_date": "2026-06-01", "end_date": "2026-01-01"},
        ).status_code == 422

    def test_dispatcher_read_ok(self, mobile_app, real_db, finance_seed, dispatcher_client):
        # cost-trend is gated require_dispatcher — dispatcher allowed.
        assert dispatcher_client.get(f"{BASE}/cost-trend").status_code == 200
        assert dispatcher_client.get(f"{BASE}/schedule").status_code == 200
