"""Read-only mobile analytics endpoint tests (blueprint §6.4) — shared DB.

These tests only READ the seeded record set, so they share ONE module-scoped
real DB (``real_db_ro`` + ``records_seed_ro``) instead of building a fresh
file-backed SQLite database per test.  The write-style tests (aging-status
cascade, payload-size bulk-seed, CSV export token lifecycle) stay in
``test_analytics_endpoints.py`` on the function-scoped fixtures.
"""
from __future__ import annotations

import pytest

BASE = "/api/v1/mobile/analytics"


@pytest.fixture
def mobile_app_ro(app, real_db_ro):
    """``app`` with ``get_db`` overridden to the module-scoped read-only DB."""
    from backend.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: real_db_ro
    yield app
    app.dependency_overrides.clear()


class TestAnalyticsManagerHappyPath:
    def test_revenue(self, mobile_app_ro, real_db_ro, records_seed_ro, manager_client):
        resp = manager_client.get(f"{BASE}/revenue")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["trend"], list) and body["trend"]
        assert isinstance(body["per_client"], list) and body["per_client"]
        assert isinstance(body["per_route"], list)
        by_label = {p["label"]: p["value"] for p in body["per_client"]}
        assert by_label["ACME Corp"] == 3700.0
        assert by_label["Globex Ltd"] == 4600.0
        # group_by accepted
        assert manager_client.get(f"{BASE}/revenue?group_by=client").status_code == 200

    def test_fleet_utilization(self, mobile_app_ro, real_db_ro, records_seed_ro, manager_client):
        resp = manager_client.get(f"{BASE}/fleet-utilization")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status_split"] == {"active": 1, "maintenance": 1, "decommissioned": 1}
        trucks = {t["truck"]: t for t in body["trucks"]}
        assert trucks["AB-01-XYZ"]["trip_count"] == 2
        assert trucks["AB-01-XYZ"]["total_km"] == 2700.0
        assert trucks["AB-02-XYZ"]["trip_count"] == 1

    def test_driver_performance(self, mobile_app_ro, real_db_ro, records_seed_ro, manager_client):
        resp = manager_client.get(f"{BASE}/driver-performance")
        assert resp.status_code == 200
        rows = {r["driver"]: r for r in resp.json()["rows"]}
        assert "rating" not in rows["Ion Popescu"]
        ion = rows["Ion Popescu"]
        assert ion["trips_completed"] == 2
        assert ion["on_time_pct"] == 50.0
        assert ion["profit_per_km"] == pytest.approx(0.3533, abs=0.001)
        assert ion["revenue"] == 3700.0
        # Maria has no OTD-qualifying trips → 0.0 (not invented)
        assert rows["Maria Ionescu"]["on_time_pct"] == 0.0

    def test_invoice_aging_buckets(self, mobile_app_ro, real_db_ro, records_seed_ro, manager_client):
        resp = manager_client.get(f"{BASE}/invoice-aging")
        assert resp.status_code == 200
        body = resp.json()
        assert body["current"] == 500.0
        assert body["bucket_31_60"] == 300.0
        assert body["bucket_61_90"] == 200.0
        assert body["overdue"] == 100.0
        assert body["total_outstanding"] == 1100.0

    def test_invalid_date_422(self, mobile_app_ro, real_db_ro, records_seed_ro, manager_client):
        resp = manager_client.get(f"{BASE}/revenue?start_date=not-a-date")
        assert resp.status_code == 422


class TestAnalyticsDispatcherDenied:
    """Dispatcher gets 403 on every analytics endpoint AND the export."""

    @pytest.mark.parametrize("path", [
        "/revenue",
        "/fleet-utilization",
        "/driver-performance",
        "/invoice-aging",
        "/export?report=revenue",
    ])
    def test_dispatcher_403(self, mobile_app_ro, real_db_ro, records_seed_ro, dispatcher_client, path):
        resp = dispatcher_client.get(f"{BASE}{path}")
        assert resp.status_code == 403