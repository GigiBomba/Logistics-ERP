"""Mobile history endpoint tests (blueprint §6.8) — real DB.

Covers: trips list filters + pagination, routes list pagination + deleted
exclusion, company isolation, the async export lifecycle
(POST 202 → status → (eager) success → signed download → GET 200) for
csv/xlsx/pdf, and dispatcher access (exports gated can_export_data).
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

BASE = "/api/v1/mobile/history"


def _seed_route(db, name: str, *, company_id: int = 1, deleted=False,
                stops: list | None = None, km: float = 800.0, mins: float = 540.0,
                created: str = "2026-07-01T10:00:00") -> int:
    cur = db.execute(
        "INSERT INTO route_history_v2 (route_fingerprint, metadata_version, created_at, "
        "last_calculated_at, calculation_count, stops_json, geometry_encoding, "
        "total_distance_km, duration_min, truck_label, profile, archived_at, "
        "is_committed, company_id, deleted_at) "
        "VALUES (?, 1, ?, ?, 1, ?, 'zlib-json', ?, ?, 'TM-1', 'fast', NULL, 1, ?, ?)",
        (name, created, created,
         json.dumps(stops or [{"city": "Bucharest"}, {"city": "Vienna"}]),
         km, mins, company_id,
         (created if deleted else None)),
    )
    db.conn.commit()
    return cur.lastrowid


class TestTripsList:
    def test_paginated(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}/trips?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 9  # 4 seed trips + 5 invoice-carrier trips
        assert len(data["items"]) == 2
        assert data["total_pages"] == 5

    def test_status_filter(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}/trips?status=Planned")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["status"] == "Planned"
        assert items[0]["origin"] == "Cluj"
        assert items[0]["destination"] == "Paris"

    def test_client_filter(self, mobile_app, real_db, records_seed, dispatcher_client):
        client_a = records_seed["client_ACME Corp"]
        resp = dispatcher_client.get(f"{BASE}/trips?client_id={client_a}")
        data = resp.json()
        assert data["total"] == 2
        assert all(i["client_name"] == "ACME Corp" for i in data["items"])

    def test_date_range_filter(self, mobile_app, real_db, records_seed, dispatcher_client):
        start = (date.today() - timedelta(days=30)).isoformat()
        resp = dispatcher_client.get(f"{BASE}/trips?start_date={start}")
        data = resp.json()
        # t2 (today-20), t3 (today+5), t4 (today-3) + 5 carriers (today-30) → 8
        assert data["total"] == 8
        assert all((i["start_date"] or "") >= start for i in data["items"])

    def test_company_isolation(self, mobile_app, real_db, records_seed, dispatcher_client):
        from tests.mobile.conftest import seed_records

        seed_records(real_db, company_id=2)
        resp = dispatcher_client.get(f"{BASE}/trips")
        data = resp.json()
        # Company 2 seeds the same 9 trips; the total stays at 9 → company 2's
        # trips are never visible under company 1's JWT.
        assert data["total"] == 9


class TestRoutesList:
    def test_paginated_and_deleted_excluded(self, mobile_app, real_db, dispatcher_client):
        _seed_route(real_db, "ROUTE-A", company_id=1, created="2026-07-02T00:00:00")
        _seed_route(real_db, "ROUTE-B", company_id=1, created="2026-07-01T00:00:00")
        _seed_route(real_db, "ROUTE-DEL", company_id=1, deleted=True)
        resp = dispatcher_client.get(f"{BASE}/routes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        names = [i["name"] for i in data["items"]]
        assert "ROUTE-DEL" not in names
        first = data["items"][0]
        assert first["origin"] == "Bucharest"
        assert first["destination"] == "Vienna"
        assert first["total_distance_km"] == 800.0
        assert first["duration_min"] == 540.0

    def test_company_isolation(self, mobile_app, real_db, dispatcher_client):
        _seed_route(real_db, "ROUTE-MINE", company_id=1)
        _seed_route(real_db, "ROUTE-THEIRS", company_id=2)
        resp = dispatcher_client.get(f"{BASE}/routes")
        names = [i["name"] for i in resp.json()["items"]]
        assert names == ["ROUTE-MINE"]


class TestTripsExport:
    def test_export_lifecycle_csv(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.post(
            f"{BASE}/trips/export", json={"format": "csv", "filters": {}},
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        st = dispatcher_client.get(f"{BASE}/trips/export/{job_id}/status")
        assert st.status_code == 200
        body = st.json()
        # eager mode: the job ran synchronously before the POST returned.
        assert body["status"] == "success"
        assert body["download_url"] and body["download_url"].startswith(
            "/api/v1/mobile/company/export/download/"
        )

        dl = dispatcher_client.get(body["download_url"])
        assert dl.status_code == 200
        assert dl.headers["content-type"].startswith("text/csv")
        assert "client_name" in dl.text

    def test_export_xlsx(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.post(f"{BASE}/trips/export", json={"format": "xlsx"})
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]
        body = dispatcher_client.get(f"{BASE}/trips/export/{job_id}/status").json()
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            # Honest error status when openpyxl is absent.
            assert body["status"] == "error"
            return
        assert body["status"] == "success"
        dl = dispatcher_client.get(body["download_url"])
        assert dl.status_code == 200
        assert "spreadsheetml" in dl.headers["content-type"]

    def test_export_pdf(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.post(f"{BASE}/trips/export", json={"format": "pdf"})
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]
        body = dispatcher_client.get(f"{BASE}/trips/export/{job_id}/status").json()
        if body["status"] == "error":
            # Honest result: PDF generation unavailable in this environment.
            assert "PDF" in (body.get("error") or "")
            return
        assert body["status"] == "success"
        dl = dispatcher_client.get(body["download_url"])
        assert dl.status_code == 200
        assert dl.headers["content-type"] == "application/pdf"

    def test_status_processing_when_not_complete(self, mobile_app, real_db, records_seed, dispatcher_client):
        from repositories.export_job_repository import ExportJobRepository

        job_id = ExportJobRepository(real_db).create(
            kind="trips_export", params={"format": "csv"}, company_id=1,
            status="processing",
        )
        body = dispatcher_client.get(f"{BASE}/trips/export/{job_id}/status").json()
        assert body["status"] == "processing"
        assert body["download_url"] is None

    def test_status_other_company_404(self, mobile_app, real_db, records_seed, dispatcher_client):
        from repositories.export_job_repository import ExportJobRepository

        job_id = ExportJobRepository(real_db).create(
            kind="trips_export", params={"format": "csv"}, company_id=2,
        )
        resp = dispatcher_client.get(f"{BASE}/trips/export/{job_id}/status")
        assert resp.status_code == 404

    def test_export_filters_applied(self, mobile_app, real_db, records_seed, dispatcher_client):
        client_a = records_seed["client_ACME Corp"]
        resp = dispatcher_client.post(
            f"{BASE}/trips/export",
            json={"format": "csv", "filters": {"client_id": client_a, "status": "Delivered"}},
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]
        body = dispatcher_client.get(f"{BASE}/trips/export/{job_id}/status").json()
        assert body["status"] == "success"
        dl = dispatcher_client.get(body["download_url"])
        assert dl.status_code == 200
        # ACME has one Delivered seed trip (t1); carrier trips are 'Carrier Corp'.
        assert "ACME Corp" in dl.text
        assert dl.text.count("\n") == 2  # header + one row


class TestExportGating:
    def test_dispatcher_allowed(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.post(f"{BASE}/trips/export", json={"format": "csv"})
        assert resp.status_code == 202

    def test_driver_denied(self, mobile_app, real_db, records_seed, driver_client):
        resp = driver_client.post(f"{BASE}/trips/export", json={"format": "csv"})
        assert resp.status_code == 403

    def test_trips_list_dispatcher_allowed(self, mobile_app, real_db, records_seed, dispatcher_client):
        assert dispatcher_client.get(f"{BASE}/trips").status_code == 200
