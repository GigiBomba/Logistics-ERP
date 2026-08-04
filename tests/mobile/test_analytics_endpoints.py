"""Mobile analytics endpoint tests (blueprint §6.4) — real DB.

Covers: 4 data endpoints happy path (manager), dispatcher 403 on all 4 AND
export (can_view_analytics), invoice-aging bucket correctness, payload-size
proof (< 50_000 bytes, measured), sync CSV export lifecycle (token download
200, tenant mismatch 403, expired token 403).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

BASE = "/api/v1/mobile/analytics"


def _seed_extra_trips(db, n: int = 80, company_id: int = 1) -> None:
    """Bulk-seed additional trips so the payload-size check is representative."""
    base = datetime(2026, 1, 1)
    for i in range(n):
        day = (base + timedelta(days=i % 90)).strftime("%Y-%m-%d")
        db.execute(
            "INSERT INTO trips (company_id, client_id, client_name, driver_id, "
            "driver_name, truck_number, status, start_date, end_date, promised_date, "
            "place_of_loading, delivery_country, distance_km, total_price_eur, "
            "net_profit, created_at) "
            "VALUES (?, NULL, ?, NULL, ?, ?, 'Delivered', ?, ?, ?, 'Bucharest', 'Vienna', "
            "800, 2000.0, 300.0, ?)",
            (company_id, f"Bulk Client {i % 7}", "Ion Popescu",
             "AB-BULK", day, day, day, day),
        )
    db.conn.commit()


class TestAnalyticsManagerHappyPath:
    def test_revenue(self, mobile_app, real_db, records_seed, manager_client):
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

    def test_fleet_utilization(self, mobile_app, real_db, records_seed, manager_client):
        resp = manager_client.get(f"{BASE}/fleet-utilization")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status_split"] == {"active": 1, "maintenance": 1, "decommissioned": 1}
        trucks = {t["truck"]: t for t in body["trucks"]}
        assert trucks["AB-01-XYZ"]["trip_count"] == 2
        assert trucks["AB-01-XYZ"]["total_km"] == 2700.0
        assert trucks["AB-02-XYZ"]["trip_count"] == 1

    def test_driver_performance(self, mobile_app, real_db, records_seed, manager_client):
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

    def test_invoice_aging_buckets(self, mobile_app, real_db, records_seed, manager_client):
        resp = manager_client.get(f"{BASE}/invoice-aging")
        assert resp.status_code == 200
        body = resp.json()
        assert body["current"] == 500.0
        assert body["bucket_31_60"] == 300.0
        assert body["bucket_61_90"] == 200.0
        assert body["overdue"] == 100.0
        assert body["total_outstanding"] == 1100.0

    def test_invoice_aging_counts_new_statuses_excludes_terminal(
        self, mobile_app, real_db, records_seed, manager_client,
    ):
        """Phase-3 statuses count toward aging; terminal states never do.

        A 'finalized' invoice (due in the 31-60 bucket) must now appear in the
        aging report, while a 'cancelled' invoice (due in the current bucket)
        must NOT be counted.  The seeded 'Paid' invoice is likewise excluded.
        """
        from datetime import date, timedelta

        today = date.today()

        def _carrier_trip(suffix: str) -> int:
            cur = real_db.execute(
                "INSERT INTO trips (company_id, client_id, client_name, driver_id, "
                "driver_name, truck_number, status, start_date, end_date, promised_date, "
                "place_of_loading, delivery_country, distance_km, total_price_eur, "
                "net_profit, created_at) "
                "VALUES (?, NULL, 'Aging Carrier', NULL, NULL, ?, 'Delivered', ?, ?, ?, "
                "'Bucharest', 'Sofia', 0, 0, 0, ?)",
                (1, f"AB-AGING-{suffix}", today.isoformat(), today.isoformat(),
                 today.isoformat(), today.isoformat()),
            )
            return cur.lastrowid

        # 'finalized' invoice, due 45 days ago → 31-60 bucket.
        fin_trip = _carrier_trip("FIN")
        real_db.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
            "total_amount, status, company_id) "
            "VALUES (?, ?, ?, ?, ?, 'finalized', 1)",
            (fin_trip, "INV-1-FINALIZED", (today - timedelta(days=55)).isoformat(),
             (today - timedelta(days=45)).isoformat(), 1500.0),
        )
        # 'cancelled' invoice, due 10 days ago → current bucket IF counted.
        canc_trip = _carrier_trip("CANC")
        real_db.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
            "total_amount, status, company_id) "
            "VALUES (?, ?, ?, ?, ?, 'cancelled', 1)",
            (canc_trip, "INV-1-CANCELLED", (today - timedelta(days=5)).isoformat(),
             (today - timedelta(days=10)).isoformat(), 9999.0),
        )
        real_db.conn.commit()

        resp = manager_client.get(f"{BASE}/invoice-aging")
        assert resp.status_code == 200
        body = resp.json()
        # finalized invoice lands in the 31-60 bucket on top of the seeded 300.0.
        assert body["bucket_31_60"] == 300.0 + 1500.0
        # cancelled (9999.0) is terminal → current bucket unchanged (no cascade).
        assert body["current"] == 500.0
        assert body["total_outstanding"] == 1100.0 + 1500.0

    def test_invalid_date_422(self, mobile_app, real_db, records_seed, manager_client):
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
    def test_dispatcher_403(self, mobile_app, real_db, records_seed, dispatcher_client, path):
        resp = dispatcher_client.get(f"{BASE}{path}")
        assert resp.status_code == 403


class TestAnalyticsPayloadSize:
    def test_payloads_under_50kb(self, mobile_app, real_db, records_seed, manager_client):
        _seed_extra_trips(real_db, n=80)
        sizes = {}
        for path in ("/revenue", "/fleet-utilization", "/driver-performance", "/invoice-aging"):
            resp = manager_client.get(f"{BASE}{path}")
            assert resp.status_code == 200
            sizes[path] = len(resp.content)
        assert sizes["/revenue"] < 50_000
        assert sizes["/fleet-utilization"] < 50_000
        assert sizes["/driver-performance"] < 50_000
        assert sizes["/invoice-aging"] < 50_000
        # Report the measured sizes (printed for the gate evidence).
        print(f"PAYLOAD_BYTES {sizes}")


class TestAnalyticsExport:
    def test_export_csv_and_download(self, mobile_app, real_db, records_seed, manager_client):
        resp = manager_client.get(f"{BASE}/export?report=revenue")
        assert resp.status_code == 200
        body = resp.json()
        assert body["download_url"].startswith("/api/v1/mobile/company/export/download/")
        assert "expires_at" in body

        dl = manager_client.get(body["download_url"])
        assert dl.status_code == 200
        assert dl.headers["content-type"].startswith("text/csv")
        assert "month,revenue" in dl.text

    def test_export_all_reports(self, mobile_app, real_db, records_seed, manager_client):
        for report in ("revenue", "fleet", "drivers", "invoice_aging"):
            resp = manager_client.get(f"{BASE}/export?report={report}")
            assert resp.status_code == 200, f"report={report}"

    def test_export_unknown_report_422(self, mobile_app, real_db, records_seed, manager_client):
        assert manager_client.get(f"{BASE}/export?report=bogus").status_code == 422

    def test_download_tenant_mismatch_403(self, mobile_app, real_db, records_seed, manager_client):
        from backend.services.local_download_service import (
            KIND_EXPORT_FILE,
            create_download_token,
        )

        # Create a real analytics_export job row first.
        assert manager_client.get(f"{BASE}/export?report=revenue").status_code == 200
        job = real_db.execute(
            "SELECT id FROM export_jobs WHERE kind = 'analytics_export' LIMIT 1"
        ).fetchone()
        assert job is not None
        # Token minted for company 2 — must be rejected under company 1's JWT.
        token = create_download_token(record_id=job["id"], company_id=2, kind=KIND_EXPORT_FILE)
        resp = manager_client.get(f"/api/v1/mobile/company/export/download/{token}")
        assert resp.status_code == 403

    def test_download_expired_token_403(self, mobile_app, real_db, records_seed, manager_client):
        from backend.services.local_download_service import (
            KIND_EXPORT_FILE,
            create_download_token,
        )

        assert manager_client.get(f"{BASE}/export?report=revenue").status_code == 200
        job = real_db.execute(
            "SELECT id FROM export_jobs WHERE kind = 'analytics_export' LIMIT 1"
        ).fetchone()
        assert job is not None
        past = datetime.now(timezone.utc) - timedelta(seconds=60)
        token = create_download_token(
            record_id=job["id"], company_id=1, kind=KIND_EXPORT_FILE, expires_at=past,
        )
        resp = manager_client.get(f"/api/v1/mobile/company/export/download/{token}")
        assert resp.status_code == 403

    def test_download_tampered_token_403(self, mobile_app, real_db, records_seed, manager_client):
        from backend.services.local_download_service import (
            KIND_EXPORT_FILE,
            create_download_token,
        )

        token = create_download_token(record_id=1, company_id=1, kind=KIND_EXPORT_FILE)
        resp = manager_client.get(
            f"/api/v1/mobile/company/export/download/{token}x"
        )
        assert resp.status_code == 403
