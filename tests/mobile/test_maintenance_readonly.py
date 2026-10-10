"""Read-only mobile maintenance endpoint tests (blueprint §6.5) — shared DB.

These tests only READ the seeded schedules/records/invoices, so they share ONE
module-scoped real DB (``real_db_ro`` + a module-scoped finance seed) instead
of building a fresh file-backed SQLite database per test.

The write-style tests (schedule create + its 403/404/422 gates) and the two
records-only "empty company" tests (which require a DB with NO finance rows)
stay in ``test_maintenance_endpoints.py`` on the function-scoped fixtures.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.mobile.conftest import seed_finance, seed_records

BASE = "/api/v1/mobile/maintenance"


@pytest.fixture
def mobile_app_ro(app, real_db_ro):
    """``app`` with ``get_db`` overridden to the module-scoped read-only DB."""
    from backend.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: real_db_ro
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def finance_seed_ro(real_db_ro):
    """Seed the standard record set + finance data ONCE for the whole module."""
    base = seed_records(real_db_ro, company_id=1)
    fin = seed_finance(real_db_ro, company_id=1)
    return {**base, **fin}


class TestMaintenanceScheduleList:
    def test_list_shape(self, mobile_app_ro, real_db_ro, finance_seed_ro, manager_client):
        resp = manager_client.get(f"{BASE}/schedule")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        by_type = {it["maintenance_type"]: it for it in body["items"]}
        assert "Oil Change" in by_type
        item = by_type["Oil Change"]
        assert item["truck_plate"]
        assert item["truck_id"] == finance_seed_ro["trucks"][0]
        assert isinstance(item["overdue"], bool)
        assert item["interval_months"] == 3

    def test_overdue_flags_via_real_thresholds(self, mobile_app_ro, real_db_ro, finance_seed_ro, manager_client):
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

    def test_overdue_only_filter(self, mobile_app_ro, real_db_ro, finance_seed_ro, manager_client):
        resp = manager_client.get(f"{BASE}/schedule", params={"overdue_only": "true"})
        body = resp.json()
        assert body["total"] == 3
        assert all(it["overdue"] for it in body["items"])
        names = {it["maintenance_type"] for it in body["items"]}
        assert names == {"Oil Change", "Inspection", "Gearbox"}

    def test_next_due(self, mobile_app_ro, real_db_ro, finance_seed_ro, manager_client):
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

    def test_pagination(self, mobile_app_ro, real_db_ro, finance_seed_ro, manager_client):
        resp = manager_client.get(f"{BASE}/schedule", params={"page": 1, "page_size": 2})
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["total_pages"] >= 3


class TestMaintenanceCostTrend:
    def test_monthly_and_by_type(self, mobile_app_ro, real_db_ro, finance_seed_ro, manager_client):
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

    def test_explicit_date_range(self, mobile_app_ro, real_db_ro, finance_seed_ro, manager_client):
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

    def test_invalid_date_422(self, mobile_app_ro, real_db_ro, finance_seed_ro, manager_client):
        assert manager_client.get(
            f"{BASE}/cost-trend", params={"start_date": "not-a-date"},
        ).status_code == 422
        assert manager_client.get(
            f"{BASE}/cost-trend", params={"start_date": "2026-06-01", "end_date": "2026-01-01"},
        ).status_code == 422

    def test_dispatcher_read_ok(self, mobile_app_ro, real_db_ro, finance_seed_ro, dispatcher_client):
        # cost-trend is gated require_dispatcher — dispatcher allowed.
        assert dispatcher_client.get(f"{BASE}/cost-trend").status_code == 200
        assert dispatcher_client.get(f"{BASE}/schedule").status_code == 200