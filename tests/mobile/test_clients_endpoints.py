"""Mobile client endpoint tests (blueprint §6.3) — real DB, role-scoped clients.

Covers: list/search/detail (contacts + counts), create/update/add-contact,
permission gates, the multi-source merge, and the merge CONCURRENCY invariant:
two simultaneous merges of the SAME source into different targets → exactly one
succeeds, no rows lost, no partial state.
"""
from __future__ import annotations

import threading

import pytest

BASE = "/api/v1/mobile/clients"


def _seed_client(db, cid: int, name: str, *, company_id: int = 1, payment_terms=30, rating=4) -> None:
    db.execute(
        "INSERT INTO clients (id, name, contact_person, phone, email, address, vat_number, "
        "currency_preference, notes, is_active, created_at, updated_at, client_type, "
        "payment_terms_days, credit_limit_eur, default_rate_per_km, rating, company_id) "
        "VALUES (?, ?, '', '', ?, ?, ?, 'EUR', '', 1, '2026-01-01T00:00:00Z', "
        "'2026-01-01T00:00:00Z', '', ?, 0, NULL, ?, ?)",
        (cid, name, f"{name}@test.com", f"Addr {name}", f"RO{cid}", payment_terms, rating, company_id),
    )
    db.conn.commit()


def _seed_trip(db, client_id: int, *, status="Planned", company_id: int = 1) -> int:
    cur = db.execute(
        "INSERT INTO trips (created_at, client_name, status, client_id, company_id) "
        "VALUES ('2026-01-01T00:00:00Z', 'C', ?, ?, ?)",
        (status, client_id, company_id),
    )
    db.conn.commit()
    return cur.lastrowid


def _seed_invoice(db, trip_id: int, number: str) -> None:
    db.execute(
        "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
        "VALUES (?, ?, '2026-01-01', '2026-02-01', 100.0, 'Unpaid')",
        (trip_id, number),
    )
    db.conn.commit()


def _seed_contact(db, client_id: int, name: str = "Contact", *, company_id: int = 1) -> None:
    db.execute(
        "INSERT INTO client_contacts (client_id, contact_type, full_name, title, phone, email, "
        "is_primary, notes, created_at, company_id) "
        "VALUES (?, 'operations', ?, 'Manager', '0700000000', 'c@t.com', 0, '', '2026-01-01T00:00:00Z', ?)",
        (client_id, name, company_id),
    )
    db.conn.commit()


def _seed_tag(db, client_id: int, tag: str, *, company_id: int = 1) -> None:
    db.execute(
        "INSERT INTO client_tags (client_id, tag, company_id) VALUES (?, ?, ?)",
        (client_id, tag, company_id),
    )
    db.conn.commit()


class TestClientsList:
    def test_list_search(self, mobile_app, real_db, dispatcher_client):
        _seed_client(real_db, 101, "ACME Corp")
        _seed_client(real_db, 102, "Globex")
        resp = dispatcher_client.get(f"{BASE}?search=ACME")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "ACME Corp"
        assert data["items"][0]["vat_number"] == "RO101"

    def test_list_paginated(self, mobile_app, real_db, dispatcher_client):
        for cid, name in ((103, "A Corp"), (104, "B Corp"), (105, "C Corp")):
            _seed_client(real_db, cid, name)
        resp = dispatcher_client.get(f"{BASE}?page=1&page_size=2")
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2

    def test_company_isolation(self, mobile_app, real_db, dispatcher_client):
        _seed_client(real_db, 101, "Mine")
        _seed_client(real_db, 102, "Other", company_id=2)
        resp = dispatcher_client.get(f"{BASE}")
        assert resp.json()["total"] == 1


class TestClientsCreate:
    def test_admin_create(self, mobile_app, real_db, admin_client):
        resp = admin_client.post(BASE, json={"name": "New Client", "vat_number": "RO-XYZ", "rating": 5})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "New Client"
        assert body["rating"] == 5
        assert body["company_id"] == 1

    def test_dispatcher_create_denied(self, mobile_app, real_db, dispatcher_client):
        resp = dispatcher_client.post(BASE, json={"name": "Denied"})
        assert resp.status_code == 403

    def test_create_validation_error(self, mobile_app, real_db, admin_client):
        resp = admin_client.post(BASE, json={})
        assert resp.status_code == 422


class TestClientsDetail:
    def test_detail_with_contacts_and_counts(self, mobile_app, real_db, dispatcher_client):
        _seed_client(real_db, 101, "ACME Corp")
        _seed_contact(real_db, 101, "John Doe")
        t1 = _seed_trip(real_db, 101)
        t2 = _seed_trip(real_db, 101, status="Delivered")
        _seed_invoice(real_db, t1, "INV-101-1")
        _seed_invoice(real_db, t2, "INV-101-2")
        resp = dispatcher_client.get(f"{BASE}/101")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "ACME Corp"
        assert body["recent_trip_count"] == 2
        assert body["recent_invoice_count"] == 2
        assert len(body["contacts"]) == 1
        assert body["contacts"][0]["name"] == "John Doe"
        assert body["contacts"][0]["role"] == "Manager"

    def test_detail_other_company_404(self, mobile_app, real_db, dispatcher_client):
        _seed_client(real_db, 101, "Other", company_id=2)
        resp = dispatcher_client.get(f"{BASE}/101")
        assert resp.status_code == 404

    def test_detail_missing_404(self, mobile_app, real_db, dispatcher_client):
        resp = dispatcher_client.get(f"{BASE}/999999")
        assert resp.status_code == 404


class TestClientsUpdate:
    def test_admin_update(self, mobile_app, real_db, admin_client):
        _seed_client(real_db, 101, "ACME Corp")
        resp = admin_client.patch(f"{BASE}/101", json={"name": "ACME Corp 2", "rating": 3})
        assert resp.status_code == 200
        assert resp.json()["name"] == "ACME Corp 2"
        assert resp.json()["rating"] == 3

    def test_dispatcher_update_denied(self, mobile_app, real_db, dispatcher_client):
        _seed_client(real_db, 101, "ACME Corp")
        resp = dispatcher_client.patch(f"{BASE}/101", json={"name": "Nope"})
        assert resp.status_code == 403

    def test_update_other_company_404(self, mobile_app, real_db, admin_client):
        _seed_client(real_db, 101, "Other", company_id=2)
        resp = admin_client.patch(f"{BASE}/101", json={"name": "Nope"})
        assert resp.status_code == 404


class TestClientsAddContact:
    def test_admin_add_contact(self, mobile_app, real_db, admin_client):
        _seed_client(real_db, 101, "ACME Corp")
        resp = admin_client.post(
            f"{BASE}/101/contacts",
            json={"full_name": "Jane Doe", "title": "CFO", "phone": "0711111111", "email": "j@t.com"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Jane Doe"
        assert body["role"] == "CFO"
        assert body["phone"] == "0711111111"

    def test_dispatcher_add_contact_denied(self, mobile_app, real_db, dispatcher_client):
        _seed_client(real_db, 101, "ACME Corp")
        resp = dispatcher_client.post(f"{BASE}/101/contacts", json={"full_name": "Jane Doe"})
        assert resp.status_code == 403

    def test_add_contact_missing_client_404(self, mobile_app, real_db, admin_client):
        resp = admin_client.post(f"{BASE}/999999/contacts", json={"full_name": "Jane Doe"})
        assert resp.status_code == 404


class TestClientsMerge:
    def test_admin_merge_multi_source(self, mobile_app, real_db, admin_client):
        _seed_client(real_db, 101, "Target")
        _seed_client(real_db, 102, "SourceA")
        _seed_client(real_db, 103, "SourceB")
        ta1 = _seed_trip(real_db, 102)
        ta2 = _seed_trip(real_db, 102)
        tb1 = _seed_trip(real_db, 103)
        _seed_invoice(real_db, ta1, "INV-A1")
        _seed_invoice(real_db, ta2, "INV-A2")
        _seed_invoice(real_db, tb1, "INV-B1")
        _seed_contact(real_db, 102, "CA")
        _seed_contact(real_db, 103, "CB")
        _seed_tag(real_db, 102, "vip")
        _seed_tag(real_db, 103, "vip")  # duplicate against target-less tag

        resp = admin_client.post(BASE + "/merge", json={"target_id": 101, "source_ids": [102, 103]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["merged_trip_count"] == 3
        assert body["merged_invoice_count"] == 3
        assert body["merged_contact_count"] == 2

        # Sources are hard-deleted; trips/contacts moved onto the target.
        assert real_db.execute("SELECT id FROM clients WHERE id IN (102, 103)").fetchone() is None
        trips = real_db.execute(
            "SELECT COUNT(*) AS cnt FROM trips WHERE client_id = 101"
        ).fetchone()
        assert trips["cnt"] == 3
        contacts = real_db.execute(
            "SELECT COUNT(*) AS cnt FROM client_contacts WHERE client_id = 101"
        ).fetchone()
        assert contacts["cnt"] == 2

    def test_merge_target_in_sources_404(self, mobile_app, real_db, admin_client):
        _seed_client(real_db, 101, "Target")
        resp = admin_client.post(BASE + "/merge", json={"target_id": 101, "source_ids": [101]})
        assert resp.status_code == 404

    def test_merge_manager_denied(self, mobile_app, real_db, manager_client):
        _seed_client(real_db, 101, "Target")
        _seed_client(real_db, 102, "Source")
        resp = manager_client.post(BASE + "/merge", json={"target_id": 101, "source_ids": [102]})
        assert resp.status_code == 403

    def test_merge_dispatcher_denied(self, mobile_app, real_db, dispatcher_client):
        _seed_client(real_db, 101, "Target")
        _seed_client(real_db, 102, "Source")
        resp = dispatcher_client.post(BASE + "/merge", json={"target_id": 101, "source_ids": [102]})
        assert resp.status_code == 403

    def test_merge_driver_denied(self, mobile_app, real_db, driver_client):
        _seed_client(real_db, 101, "Target")
        _seed_client(real_db, 102, "Source")
        resp = driver_client.post(BASE + "/merge", json={"target_id": 101, "source_ids": [102]})
        assert resp.status_code == 403


class TestClientsMergeConcurrency:
    def test_concurrent_merge_overlapping_sources(self, mobile_app, real_db, admin_user):
        """Two simultaneous merges of the SAME source into different targets.

        BEGIN IMMEDIATE (SQLite) serialises the writers: the second merge
        blocks until the first commits, then its in-lock re-validation sees
        the source is gone and returns 404.  Exactly ONE merge returns 200
        with the counts; no rows are lost and no partial state remains.

        WITHOUT the lock both requests would pass validation concurrently and
        both would return 200 (one with counts, one with zeros) — this test
        fails in that case.
        """
        from fastapi.testclient import TestClient

        from tests.mobile.conftest import _override_auth

        # Seed two targets and one shared source.
        _seed_client(real_db, 201, "TargetB")
        _seed_client(real_db, 202, "TargetC")
        _seed_client(real_db, 203, "SharedSource")
        t1 = _seed_trip(real_db, 203)
        t2 = _seed_trip(real_db, 203)
        _seed_invoice(real_db, t1, "INV-S1")
        _seed_invoice(real_db, t2, "INV-S2")
        _seed_contact(real_db, 203, "SharedContact")

        _override_auth(mobile_app, admin_user, require_gates=True)
        results: dict = {}

        def run_merge(target_id: int, key: str) -> None:
            client = TestClient(mobile_app, raise_server_exceptions=False)
            results[key] = client.post(
                BASE + "/merge", json={"target_id": target_id, "source_ids": [203]}
            )

        threads = [
            threading.Thread(target=run_merge, args=(201, "b")),
            threading.Thread(target=run_merge, args=(202, "c")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        mobile_app.dependency_overrides.clear()

        codes = sorted(r.status_code for r in results.values())
        assert codes == [200, 404], f"expected exactly one winner, got {codes}"

        winner = [k for k, r in results.items() if r.status_code == 200][0]
        winner_body = results[winner].json()
        assert winner_body["merged_trip_count"] == 2
        assert winner_body["merged_invoice_count"] == 2
        assert winner_body["merged_contact_count"] == 1

        # Source deleted; trips/contacts live under exactly one target.
        assert real_db.execute("SELECT id FROM clients WHERE id = 203").fetchone() is None
        winning_target = 201 if winner == "b" else 202
        trips = real_db.execute(
            "SELECT COUNT(*) AS cnt FROM trips WHERE client_id = ?", (winning_target,)
        ).fetchone()
        assert trips["cnt"] == 2
        contacts = real_db.execute(
            "SELECT COUNT(*) AS cnt FROM client_contacts WHERE client_id = ?", (winning_target,)
        ).fetchone()
        assert contacts["cnt"] == 1
        losing_target = 202 if winner == "b" else 201
        assert real_db.execute(
            "SELECT COUNT(*) AS cnt FROM trips WHERE client_id = ?", (losing_target,)
        ).fetchone()["cnt"] == 0
        assert real_db.execute(
            "SELECT COUNT(*) AS cnt FROM client_contacts WHERE client_id = ?", (losing_target,)
        ).fetchone()["cnt"] == 0

    def test_merge_repository_lock_serializes(self, real_db):
        """Repository-level proof of the dialect-aware lock.

        Two threads call ``merge_clients_multi`` on the SAME shared source via
        a barrier.  SQLite's ``BEGIN IMMEDIATE`` guarantees exactly one wins;
        the loser's in-lock re-validation raises ValueError (source gone).
        Without the lock both would pass validation → both succeed → fail.
        """
        from repositories.client_repository import ClientRepository

        _seed_client(real_db, 301, "TargetB")
        _seed_client(real_db, 302, "TargetC")
        _seed_client(real_db, 303, "SharedSource")
        _seed_trip(real_db, 303)
        _seed_contact(real_db, 303)

        repo = ClientRepository(real_db)
        barrier = threading.Barrier(2)
        results: dict = {}

        def worker(target_id: int, key: str) -> None:
            try:
                barrier.wait(timeout=15)
                results[key] = ("ok", repo.merge_clients_multi(target_id, [303], company_id=1))
            except ValueError as exc:
                results[key] = ("value_error", str(exc))

        threads = [
            threading.Thread(target=worker, args=(301, "b")),
            threading.Thread(target=worker, args=(302, "c")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert len(results) == 2
        assert sorted(v[0] for v in results.values()) == ["ok", "value_error"]

        winner = [k for k, v in results.items() if v[0] == "ok"][0]
        winning_target = 301 if winner == "b" else 302
        assert real_db.execute(
            "SELECT COUNT(*) AS cnt FROM trips WHERE client_id = ?", (winning_target,)
        ).fetchone()["cnt"] == 1
        assert real_db.execute(
            "SELECT COUNT(*) AS cnt FROM client_contacts WHERE client_id = ?", (winning_target,)
        ).fetchone()["cnt"] == 1
        assert real_db.execute("SELECT id FROM clients WHERE id = 303").fetchone() is None
