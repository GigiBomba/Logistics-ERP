"""Mobile global search endpoint tests (blueprint §6.11) — real DB.

Covers: per-type hits, cap 5 + total_count, min-query validation, company
isolation, LIKE wildcard escaping, types subset, documents via FTS.
"""
from __future__ import annotations

import pytest

BASE = "/api/v1/mobile/search"


def _seed_doc(db, doc_number: str, title: str, *, company_id: int = 1,
              archived: bool = False, description: str = "") -> int:
    cur = db.execute(
        "INSERT INTO documents (doc_number, title, category, entity_type, "
        "file_path, file_name, file_size, mime_type, description, is_archived, "
        "uploaded_at, updated_at, company_id) "
        "VALUES (?, ?, 'invoice', 'trip', '/tmp/x.pdf', 'x.pdf', 10, "
        "'application/pdf', ?, ?, '2026-07-01T00:00:00', '2026-07-01T00:00:00', ?)",
        (doc_number, title, description, 1 if archived else 0, company_id),
    )
    db.conn.commit()
    return cur.lastrowid


def _seed_trip(db, company_id: int, client_name: str, truck: str = "AB-CAP",
               driver: str = "Cap Driver", status: str = "Planned",
               origin: str = "Bucharest", dest: str = "Vienna") -> int:
    cur = db.execute(
        "INSERT INTO trips (company_id, client_name, truck_number, driver_name, "
        "status, start_date, place_of_loading, delivery_country, created_at) "
        "VALUES (?, ?, ?, ?, ?, '2026-07-01', ?, ?, '2026-07-01')",
        (company_id, client_name, truck, driver, status, origin, dest),
    )
    db.conn.commit()
    return cur.lastrowid


class TestSearchHits:
    def test_trips_hit(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}?q=ACME")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trips"]["total_count"] == 2
        assert all("ACME" in t["client_name"] for t in body["trips"]["items"])

    def test_clients_and_drivers_hit(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}?q=Popescu")
        body = resp.json()
        assert body["drivers"]["total_count"] == 1
        assert body["drivers"]["items"][0]["name"] == "Ion Popescu"

        resp2 = dispatcher_client.get(f"{BASE}?q=Globex")
        body2 = resp2.json()
        assert body2["clients"]["total_count"] == 1
        assert body2["clients"]["items"][0]["name"] == "Globex Ltd"

    def test_trucks_hit(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}?q=AB-01")
        body = resp.json()
        assert body["trucks"]["total_count"] == 1
        assert body["trucks"]["items"][0]["plate_number"] == "AB-01-XYZ"

    def test_documents_hit(self, mobile_app, real_db, dispatcher_client):
        _seed_doc(real_db, "DOC-1", "Invoice ACME Corp")
        resp = dispatcher_client.get(f"{BASE}?q=ACME&types=documents")
        body = resp.json()
        assert body["documents"]["total_count"] == 1
        assert body["documents"]["items"][0]["title"] == "Invoice ACME Corp"

    def test_cap_5_and_total_count(self, mobile_app, real_db, dispatcher_client):
        for i in range(8):
            _seed_trip(real_db, 1, "CapClient")
        resp = dispatcher_client.get(f"{BASE}?q=CapClient&types=trips")
        body = resp.json()
        assert len(body["trips"]["items"]) == 5
        assert body["trips"]["total_count"] == 8

    def test_all_five_sections_present(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}?q=ACME")
        body = resp.json()
        for key in ("trips", "clients", "drivers", "trucks", "documents"):
            assert key in body

    def test_types_subset(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}?q=ACME&types=clients,drivers")
        body = resp.json()
        assert body["clients"]["total_count"] == 1
        assert body["drivers"]["total_count"] == 0
        assert body["trips"]["total_count"] == 0
        assert body["documents"]["total_count"] == 0

    def test_unknown_type_422(self, mobile_app, real_db, records_seed, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}?q=ACME&types=bogus")
        assert resp.status_code == 422


class TestSearchValidation:
    def test_missing_query_422(self, mobile_app, real_db, records_seed, dispatcher_client):
        assert dispatcher_client.get(f"{BASE}").status_code == 422
        assert dispatcher_client.get(f"{BASE}?q=").status_code == 422


class TestSearchIsolation:
    def test_other_company_never_returned(self, mobile_app, real_db, records_seed, dispatcher_client):
        from tests.mobile.conftest import seed_records

        seed_records(real_db, company_id=2)
        _seed_doc(real_db, "DOC-2", "Secret Doc", company_id=2)
        _seed_trip(real_db, 2, "Hidden Corp", truck="AB-HIDDEN")

        resp = dispatcher_client.get(f"{BASE}?q=Secret")
        assert resp.json()["documents"]["total_count"] == 0

        resp = dispatcher_client.get(f"{BASE}?q=Hidden")
        assert resp.json()["trips"]["total_count"] == 0

        # Company 2 seeds the SAME client/trip names — the counts stay at the
        # company-1 level, proving scoping (unscoped → 2 clients / 4 trips).
        resp = dispatcher_client.get(f"{BASE}?q=ACME")
        assert resp.json()["clients"]["total_count"] == 1
        assert resp.json()["trips"]["total_count"] == 2


class TestSearchLikeEscaping:
    def test_percent_is_literal(self, mobile_app, real_db, dispatcher_client):
        from tests.mobile.conftest import _insert_client

        _insert_client(real_db, "100% Organic")
        _insert_client(real_db, "100X Inc")
        resp = dispatcher_client.get(f"{BASE}?q=100%25&types=clients")
        body = resp.json()
        names = [c["name"] for c in body["clients"]["items"]]
        assert names == ["100% Organic"]
        assert "100X Inc" not in names
