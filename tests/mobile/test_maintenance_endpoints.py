"""Mobile maintenance endpoint tests (blueprint §6.5) — REAL DB.

Covers: schedule create + permission gates (manager 201, truck 404, 422
cadence, dispatcher/driver 403), plus the two records-only "empty company"
tests that require a DB with NO finance rows.

The read-only schedule-list / cost-trend tests (list shape, overdue flags,
filters, next_due, pagination, cost-trend aggregation) moved to
``test_maintenance_readonly.py``, which shares one module-scoped DB.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

BASE = "/api/v1/mobile/maintenance"


class TestMaintenanceScheduleList:
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
