"""Tests for the offline-first sync PULL lane (Phase 3b).

Covers ``SyncPullService``:
- pull upsert: local rows created + ``sync_id_map`` populated (both directions)
- FK translation: server ids → local ids via ``sync_id_map``
- soft-delete propagation: server ``deleted_at`` → local row soft-deleted
- unmapped FK → NULL (self-healing on the next pull)
- echo suppression: pull-apply writes NO outbox rows
- column filtering: server rows with extra columns → only local columns written
- pagination via next_after_id / has_more
"""
from __future__ import annotations

import os
import tempfile

import pytest

from database.db_manager import DatabaseManager
from services.sync_pull_service import SyncPullService


class FakeApiClient:
    """Stub ApiClient returning canned pull responses.

    ``responses`` maps entity_type → list of record dicts.  ``get``
    implements the same pagination contract as the real pull endpoint
    (records with id > after_id, ordered by id, has_more when a full page
    was returned and more records remain).
    """

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def get(self, path, params=None):
        params = dict(params or {})
        self.calls.append((path, params))
        entity = params.get("entity")
        after_id = params.get("after_id", 0)
        limit = params.get("limit", 500)
        records = sorted(
            (r for r in self.responses.get(entity, []) if r["id"] > after_id),
            key=lambda r: r["id"],
        )
        page = records[:limit]
        next_after_id = max((r["id"] for r in page), default=after_id)
        has_more = len(page) >= limit and len(records) > limit
        return {
            "records": page,
            "next_after_id": next_after_id,
            "has_more": has_more,
        }


@pytest.fixture
def db_path():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def db(db_path):
    _db = DatabaseManager(db_path)
    yield _db
    try:
        _db.close()
    except Exception:
        pass


def _make_service(db, responses, page_size=500):
    return SyncPullService(db, FakeApiClient(responses), page_size=page_size)


def _outbox_rows(db):
    return [
        dict(r)
        for r in db.conn.execute("SELECT * FROM sync_outbox ORDER BY id").fetchall()
    ]


def _id_map_rows(db):
    return [
        dict(r)
        for r in db.conn.execute("SELECT * FROM sync_id_map ORDER BY id").fetchall()
    ]


# ── Pull upsert ───────────────────────────────────────────────────────────


class TestPullUpsert:
    def test_pull_creates_local_rows_and_mapping(self, db):
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "Server Client", "email": "s@c.com",
                 "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()

        rows = db.conn.execute("SELECT * FROM clients").fetchall()
        assert len(rows) == 1
        local = dict(rows[0])
        assert local["name"] == "Server Client"
        assert local["email"] == "s@c.com"
        assert local["id"] != 100  # fresh local AUTOINCREMENT id

        # sync_id_map populated in BOTH directions
        by_server = db.conn.execute(
            "SELECT local_id FROM sync_id_map "
            "WHERE entity_type = 'client' AND server_id = 100"
        ).fetchone()
        assert by_server is not None and by_server["local_id"] == local["id"]
        by_local = db.conn.execute(
            "SELECT server_id FROM sync_id_map "
            "WHERE entity_type = 'client' AND local_id = ?",
            (local["id"],),
        ).fetchone()
        assert by_local is not None and by_local["server_id"] == 100

    def test_pull_upsert_updates_existing_local_row(self, db):
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "First", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()
        local_id = db.conn.execute("SELECT id FROM clients").fetchone()["id"]

        # Second pull with the same server row (updated) → UPDATE, no duplicate
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "Second", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-02T00:00:00Z"},
            ],
        })
        service.pull_all()
        rows = db.conn.execute("SELECT * FROM clients").fetchall()
        assert len(rows) == 1
        assert dict(rows[0])["name"] == "Second"
        assert dict(rows[0])["id"] == local_id
        assert len(_id_map_rows(db)) == 1


# ── FK translation ────────────────────────────────────────────────────────


class TestFkTranslation:
    def test_trip_truck_id_translated(self, db):
        service = _make_service(db, {
            "truck": [
                {"id": 5, "plate_number": "AB-01", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "trip": [
                {"id": 50, "truck_id": 5, "status": "Planned",
                 "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()

        local_truck_id = db.conn.execute("SELECT id FROM trucks").fetchone()["id"]
        trip = dict(db.conn.execute("SELECT * FROM trips").fetchone())
        assert trip["truck_id"] == local_truck_id

    def test_unmapped_fk_is_null(self, db):
        service = _make_service(db, {
            "trip": [
                {"id": 50, "truck_id": 999, "status": "Planned",
                 "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()
        trip = dict(db.conn.execute("SELECT * FROM trips").fetchone())
        assert trip["truck_id"] is None


# ── Soft-delete propagation ───────────────────────────────────────────────


class TestSoftDelete:
    def test_soft_delete_propagates(self, db):
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "Active", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()
        local_id = db.conn.execute("SELECT id FROM clients").fetchone()["id"]
        assert db.conn.execute(
            "SELECT deleted_at FROM clients WHERE id = ?", (local_id,)
        ).fetchone()["deleted_at"] is None

        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "Active", "deleted_at": "2026-08-03T00:00:00Z",
                 "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-03T00:00:00Z"},
            ],
        })
        service.pull_all()
        row = db.conn.execute(
            "SELECT deleted_at FROM clients WHERE id = ?", (local_id,)
        ).fetchone()
        assert row["deleted_at"] == "2026-08-03T00:00:00Z"

    def test_soft_deleted_never_pulled_skips(self, db):
        service = _make_service(db, {
            "client": [
                {"id": 200, "name": "Gone", "deleted_at": "2026-08-03T00:00:00Z",
                 "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-03T00:00:00Z"},
            ],
        })
        service.pull_all()
        assert db.conn.execute("SELECT COUNT(*) AS n FROM clients").fetchone()["n"] == 0
        assert _id_map_rows(db) == []


# ── Echo suppression ──────────────────────────────────────────────────────


class TestEchoSuppression:
    def test_pull_writes_no_outbox_rows(self, db):
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "No Echo", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "trip": [
                {"id": 50, "status": "Planned", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()
        assert _outbox_rows(db) == []


# ── Column filtering ──────────────────────────────────────────────────────


class TestColumnFiltering:
    def test_extra_server_columns_ignored(self, db):
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "Filtered", "bogus_column": "nope",
                 "created_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()
        row = dict(db.conn.execute("SELECT * FROM clients").fetchone())
        assert row["name"] == "Filtered"
        assert "bogus_column" not in row


# ── Pagination ────────────────────────────────────────────────────────────


class TestPagination:
    def test_pull_paginates(self, db):
        records = [
            {"id": i, "name": f"C{i}", "created_at": "2026-08-01T00:00:00Z",
             "updated_at": "2026-08-01T00:00:00Z"}
            for i in range(1, 6)
        ]
        service = _make_service(db, {"client": records}, page_size=2)
        service.pull_entity("client")
        assert db.conn.execute("SELECT COUNT(*) AS n FROM clients").fetchone()["n"] == 5
        # pagination: 3 pages requested (after_id 0 → 2 → 4)
        calls = [c for c in service.api_client.calls if c[0] == "/api/v1/sync/pull"]
        assert len(calls) == 3


# ── R5: stamping-trigger echo suppression ────────────────────────────────


class TestR5StampingSuppression:
    def test_pull_apply_does_not_restamp_updated_at(self, db):
        """R5: pull-apply runs with sync_in_progress=1 — the Phase-0 updated_at
        stamping triggers must NOT overwrite the server's updated_at with the
        local clock (that would fabricate false conflicts and lose the server
        version)."""
        server_updated_at = "2026-08-01T00:00:00Z"
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "Server Timestamp",
                 "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": server_updated_at},
            ],
        })
        service.pull_all()
        row = dict(db.conn.execute("SELECT * FROM clients").fetchone())
        assert row["updated_at"] == server_updated_at

        # UPDATE path (second pull) must also preserve the server value
        server_updated_at2 = "2026-08-02T00:00:00Z"
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "Server Timestamp 2",
                 "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": server_updated_at2},
            ],
        })
        service.pull_all()
        row = dict(db.conn.execute("SELECT * FROM clients").fetchone())
        assert row["updated_at"] == server_updated_at2


# ── Phase A: device_id in pull requests ───────────────────────────────────


class TestDeviceId:
    def test_pull_requests_include_device_id(self, db):
        """Phase A: every pull request carries the device_id query param."""
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "C", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all(device_id="device-xyz")

        assert service.api_client.calls
        for _, params in service.api_client.calls:
            assert params.get("device_id") == "device-xyz"


# ── Phase B: entity completeness ───────────────────────────────────────────


class TestPhaseBPull:
    def test_pull_includes_new_entities(self, db):
        """Phase B: pull_all pulls the newly synced entities (client_contact,
        client_tag, tacho_import) in dependency order."""
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "C", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "client_contact": [
                {"id": 200, "client_id": 100, "full_name": "Contact",
                 "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "client_tag": [
                {"id": 300, "client_id": 100, "tag": "VIP",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "tacho_import": [
                {"id": 400, "file_name": "f.ddd", "file_type": "ddd",
                 "file_hash": "abc", "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()

        assert db.conn.execute("SELECT COUNT(*) AS n FROM clients").fetchone()["n"] == 1
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM client_contacts"
        ).fetchone()["n"] == 1
        assert db.conn.execute("SELECT COUNT(*) AS n FROM client_tags").fetchone()["n"] == 1
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM tacho_imports"
        ).fetchone()["n"] == 1

    def test_fk_translation_new_entity(self, db):
        """Phase B: client_contact.client_id is translated to the local id."""
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "C", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "client_contact": [
                {"id": 200, "client_id": 100, "full_name": "Contact",
                 "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()

        local_client_id = db.conn.execute("SELECT id FROM clients").fetchone()["id"]
        contact = dict(db.conn.execute("SELECT * FROM client_contacts").fetchone())
        assert contact["client_id"] == local_client_id

    def test_pull_expense_soft_delete(self, db):
        """Phase B: a server expense row with deleted_at soft-deletes locally."""
        service = _make_service(db, {
            "expense": [
                {"id": 700, "truck_id": None, "category": "Fuel", "amount": 10.0,
                 "company_id": 1, "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-02T00:00:00Z",
                 "deleted_at": "2026-08-03T00:00:00Z"},
            ],
        })
        service.pull_all()

        # The soft-deleted expense row must be soft-deleted locally, not inserted.
        assert db.conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()["n"] == 0


# ── C1: FK translation gaps ────────────────────────────────────────────────


class TestC1FkGaps:
    def test_invoice_client_id_translated(self, db):
        """C1: invoice.client_id is translated to the local client id."""
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "C", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "invoice": [
                {"id": 50, "trip_id": None, "client_id": 100, "status": "Unpaid",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()

        local_client_id = db.conn.execute("SELECT id FROM clients").fetchone()["id"]
        invoice = dict(db.conn.execute("SELECT * FROM invoices").fetchone())
        assert invoice["client_id"] == local_client_id

    def test_document_link_polymorphic_fk_translated(self, db):
        """C1: document_links.linked_entity_id is translated via linked_entity_type."""
        service = _make_service(db, {
            "document": [
                {"id": 55, "doc_number": "D1", "title": "T",
                 "file_path": "/f.pdf", "file_name": "f.pdf",
                 "uploaded_at": "2026-08-01T00:00:00Z",
                 "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "trip": [
                {"id": 50, "status": "Planned",
                 "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "document_link": [
                {"id": 77, "document_id": 55, "linked_entity_type": "trip",
                 "linked_entity_id": 50, "relation_type": "attached",
                 "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()

        local_trip_id = db.conn.execute("SELECT id FROM trips").fetchone()["id"]
        link = dict(db.conn.execute("SELECT * FROM document_links").fetchone())
        assert link["linked_entity_id"] == local_trip_id


# ── C2: NOT NULL FK self-healing ──────────────────────────────────────────


class TestC2NotNullFkSelfHeal:
    def test_unmapped_notnull_fk_skips_row_cycle_continues(self, db):
        """C2: a client_contact whose client FK is unmapped is SKIPPED (not a
        crash), and the pull cycle continues to later entities."""
        service = _make_service(db, {
            "client": [],  # client NOT pulled → client_contact FK unmapped
            "client_contact": [
                {"id": 200, "client_id": 999, "full_name": "Orphan Contact",
                 "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "truck": [
                {"id": 50, "plate_number": "AB-01",
                 "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()

        # The orphan contact must NOT be inserted (NOT NULL client_id unmapped).
        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM client_contacts"
        ).fetchone()["n"] == 0
        # The cycle continued: the later truck entity was pulled successfully.
        assert db.conn.execute("SELECT COUNT(*) AS n FROM trucks").fetchone()["n"] == 1

    def test_fully_qualified_fk_applies_normally(self, db):
        """C2 sanity: when the parent IS mapped, the child row applies."""
        service = _make_service(db, {
            "client": [
                {"id": 100, "name": "C", "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
            "client_contact": [
                {"id": 200, "client_id": 100, "full_name": "Contact",
                 "created_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        service.pull_all()

        assert db.conn.execute(
            "SELECT COUNT(*) AS n FROM client_contacts"
        ).fetchone()["n"] == 1