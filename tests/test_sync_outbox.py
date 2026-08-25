"""Tests for the offline-first sync CAPTURE layer (Phase 1).

Covers the ``sync_outbox`` / ``sync_meta`` tables, the outbox capture
triggers (INSERT/UPDATE/DELETE on syncable tables), the echo-suppression
flag, and the ``SyncOutboxService`` read/drain API.
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from database.db_manager import DatabaseManager
from services.sync_outbox_service import SyncOutboxService


# ── Fixtures ──────────────────────────────────────────────────────────────


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


@pytest.fixture
def outbox(db):
    return SyncOutboxService(db)


def _outbox_rows(db):
    return [
        dict(r)
        for r in db.conn.execute("SELECT * FROM sync_outbox ORDER BY id").fetchall()
    ]


def _insert_trip(db, truck_number="AB-01", status="Planned"):
    cur = db.conn.execute(
        "INSERT INTO trips (truck_number, driver_name, client_name, status) "
        "VALUES (?, 'John', 'ACME', ?)",
        (truck_number, status),
    )
    db.conn.commit()
    return cur.lastrowid


# ── Schema ────────────────────────────────────────────────────────────────


class TestSchema:
    def test_outbox_and_meta_tables_exist(self, db):
        tables = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "sync_outbox" in tables
        assert "sync_meta" in tables

    def test_outbox_triggers_exist_for_syncable_tables(self, db):
        triggers = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
        }
        for table in ("trips", "trucks", "expenses", "clients", "documents"):
            assert f"trg_{table}_outbox_ai" in triggers
            assert f"trg_{table}_outbox_au" in triggers
            assert f"trg_{table}_outbox_ad" in triggers


# ── Trigger capture ───────────────────────────────────────────────────────


class TestOutboxCapture:
    def test_insert_captured(self, db, outbox):
        trip_id = _insert_trip(db)
        rows = _outbox_rows(db)
        assert len(rows) == 1
        # entity_type is the SINGULAR entity type (matches the push API
        # contract), not the table name.
        assert rows[0]["entity_type"] == "trip"
        assert rows[0]["op"] == "INSERT"
        assert rows[0]["local_id"] == trip_id
        assert rows[0]["payload_json"] is None
        assert rows[0]["synced_at"] is None
        assert rows[0]["retry_count"] == 0

    def test_update_captured(self, db, outbox):
        trip_id = _insert_trip(db)
        db.conn.execute(
            "UPDATE trips SET status = 'In Transit' WHERE id = ?", (trip_id,)
        )
        db.conn.commit()
        rows = _outbox_rows(db)
        assert [r["op"] for r in rows] == ["INSERT", "UPDATE"]
        assert rows[1]["entity_type"] == "trip"
        assert rows[1]["local_id"] == trip_id
        assert rows[1]["payload_json"] is None

    def test_delete_captured_with_payload(self, db, outbox):
        trip_id = _insert_trip(db, truck_number="AB-42", status="Delivered")
        db.conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        db.conn.commit()
        rows = _outbox_rows(db)
        assert [r["op"] for r in rows] == ["INSERT", "DELETE"]
        delete_row = rows[-1]
        assert delete_row["entity_type"] == "trip"
        assert delete_row["local_id"] == trip_id
        payload = json.loads(delete_row["payload_json"])
        assert payload["id"] == trip_id
        assert payload["truck_number"] == "AB-42"
        assert payload["status"] == "Delivered"
        assert payload["driver_name"] == "John"

    def test_suppression_when_sync_in_progress(self, db, outbox):
        outbox.set_sync_in_progress(True)
        trip_id = _insert_trip(db)
        db.conn.execute(
            "UPDATE trips SET status = 'Delivered' WHERE id = ?", (trip_id,)
        )
        db.conn.commit()
        db.conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        db.conn.commit()
        assert _outbox_rows(db) == []

        # Flag cleared → capture resumes
        outbox.set_sync_in_progress(False)
        _insert_trip(db, truck_number="AB-02")
        rows = _outbox_rows(db)
        assert len(rows) == 1
        assert rows[0]["op"] == "INSERT"


class TestStampingTriggerSuppression:
    """R5: the Phase-0 updated_at stamping triggers must skip when
    ``sync_in_progress=1`` (pull-apply) so the server's updated_at survives
    instead of being overwritten by the local clock."""

    def test_updated_at_not_restamped_when_sync_in_progress(self, db, outbox):
        outbox.set_sync_in_progress(True)
        db.conn.execute(
            "INSERT INTO trips (truck_number, driver_name, client_name, status, updated_at) "
            "VALUES ('AB-77', 'John', 'ACME', 'Planned', '2026-08-01T00:00:00Z')"
        )
        db.conn.commit()
        row = db.conn.execute("SELECT updated_at FROM trips").fetchone()
        assert row["updated_at"] == "2026-08-01T00:00:00Z"

        # UPDATE path too
        db.conn.execute(
            "UPDATE trips SET status = 'In Transit', updated_at = '2026-08-02T00:00:00Z' "
            "WHERE truck_number = 'AB-77'"
        )
        db.conn.commit()
        row = db.conn.execute("SELECT updated_at FROM trips").fetchone()
        assert row["updated_at"] == "2026-08-02T00:00:00Z"

    def test_updated_at_stamped_when_not_suppressed(self, db, outbox):
        """Sanity check: with sync_in_progress cleared, the stamping triggers
        still fire (normal desktop writes keep updated_at fresh)."""
        outbox.set_sync_in_progress(False)
        db.conn.execute(
            "INSERT INTO trips (truck_number, driver_name, client_name, status, updated_at) "
            "VALUES ('AB-78', 'John', 'ACME', 'Planned', '2026-08-01T00:00:00Z')"
        )
        db.conn.commit()
        row = db.conn.execute("SELECT updated_at FROM trips").fetchone()
        assert row["updated_at"] != "2026-08-01T00:00:00Z"


# ── SyncOutboxService ─────────────────────────────────────────────────────


class TestSyncOutboxService:
    def test_pending_fifo_and_fields(self, db, outbox):
        id1 = _insert_trip(db, truck_number="AB-01")
        id2 = _insert_trip(db, truck_number="AB-02")
        pending = outbox.pending()
        assert [p["local_id"] for p in pending] == [id1, id2]
        assert pending[0]["entity_type"] == "trip"
        assert pending[0]["op"] == "INSERT"
        assert pending[0]["payload_json"] is None
        assert pending[0]["retry_count"] == 0
        assert "id" in pending[0]

    def test_pending_limit(self, db, outbox):
        for i in range(5):
            _insert_trip(db, truck_number=f"AB-{i:02d}")
        assert len(outbox.pending(limit=2)) == 2

    def test_resolve_payload_returns_current_row(self, db, outbox):
        trip_id = _insert_trip(db, truck_number="AB-09")
        payload = outbox.resolve_payload("trip", trip_id)
        assert payload is not None
        assert payload["id"] == trip_id
        assert payload["truck_number"] == "AB-09"
        assert payload["status"] == "Planned"

        db.conn.execute(
            "UPDATE trips SET status = 'In Transit' WHERE id = ?", (trip_id,)
        )
        db.conn.commit()
        payload = outbox.resolve_payload("trip", trip_id)
        assert payload["status"] == "In Transit"

    def test_resolve_payload_missing_row_returns_none(self, db, outbox):
        trip_id = _insert_trip(db)
        db.conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        db.conn.commit()
        assert outbox.resolve_payload("trip", trip_id) is None

    def test_resolve_payload_rejects_unknown_entity(self, db, outbox):
        assert outbox.resolve_payload("not_a_table; DROP TABLE trips", 1) is None
        # trips table must still exist (no SQL injection)
        assert db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trips'"
        ).fetchone() is not None

    def test_resolve_payload_rejects_table_name(self, db, outbox):
        """The plural table name is NOT a valid entity type — only the
        singular form ('trip') resolves.  Guards against callers passing
        the old table-name contract."""
        trip_id = _insert_trip(db)
        assert outbox.resolve_payload("trips", trip_id) is None

    def test_entity_type_to_table_mapping(self, db, outbox):
        assert outbox.entity_type_to_table("trip") == "trips"
        assert outbox.entity_type_to_table("client") == "clients"
        assert outbox.entity_type_to_table("maintenance_record") == "maintenance_records"
        assert outbox.entity_type_to_table("expense") == "expenses"
        assert outbox.entity_type_to_table("bogus") is None

    def test_mark_synced_excludes_from_pending(self, db, outbox):
        trip_id = _insert_trip(db)
        pending = outbox.pending()
        assert len(pending) == 1
        outbox.mark_synced(pending[0]["id"])
        assert outbox.pending() == []
        row = db.conn.execute(
            "SELECT synced_at FROM sync_outbox WHERE id = ?", (pending[0]["id"],)
        ).fetchone()
        assert row["synced_at"] is not None
        assert row["synced_at"].endswith("Z")

    def test_mark_retry_increments(self, db, outbox):
        _insert_trip(db)
        pending = outbox.pending()
        assert pending[0]["retry_count"] == 0
        outbox.mark_retry(pending[0]["id"])
        assert outbox.pending()[0]["retry_count"] == 1

    def test_prune_removes_old_synced_rows(self, db, outbox):
        trip_id = _insert_trip(db)
        pending = outbox.pending()
        outbox.mark_synced(pending[0]["id"])
        # Backdate the synced_at so it is older than the prune window.
        db.conn.execute(
            "UPDATE sync_outbox SET synced_at = '2020-01-01T00:00:00Z' WHERE id = ?",
            (pending[0]["id"],),
        )
        db.conn.commit()
        deleted = outbox.prune(days=30)
        assert deleted == 1
        assert _outbox_rows(db) == []

    def test_prune_keeps_recent_synced_rows(self, db, outbox):
        trip_id = _insert_trip(db)
        pending = outbox.pending()
        outbox.mark_synced(pending[0]["id"])
        deleted = outbox.prune(days=30)
        assert deleted == 0
        assert len(_outbox_rows(db)) == 1


# ── Non-service write paths ───────────────────────────────────────────────


class TestNonServiceWritePaths:
    def test_repository_write_captured(self, db, outbox):
        from repositories.trip_repository import TripRepository

        trip_id = TripRepository(db).create(
            {
                "truck_number": "AB-77",
                "driver_name": "Repo Driver",
                "client_name": "Repo Client",
                "status": "Planned",
            }
        )
        rows = _outbox_rows(db)
        assert len(rows) == 1
        assert rows[0]["entity_type"] == "trip"
        assert rows[0]["op"] == "INSERT"
        assert rows[0]["local_id"] == trip_id

    def test_all_syncable_tables_write_captured(self, db, outbox):
        """Phase B: capture scope is now ALL 25 syncable entities.

        Previously client_tags was in SYNCABLE_ENTITIES but NOT in the v1
        push scope, so writes to it produced no outbox row.  Phase B extended
        the outbox triggers to every SYNCABLE_ENTITIES table — a write to
        client_tags must now create an outbox row.
        """
        client_id = db.conn.execute(
            "INSERT INTO clients (name, created_at) "
            "VALUES ('Tag Client', '2026-08-17T00:00:00Z')"
        ).lastrowid
        db.conn.commit()
        rows = _outbox_rows(db)
        assert len(rows) == 1
        assert rows[0]["entity_type"] == "client"

        db.conn.execute(
            "INSERT INTO client_tags (client_id, tag) VALUES (?, 'VIP')",
            (client_id,),
        )
        db.conn.commit()
        rows = _outbox_rows(db)
        assert len(rows) == 2
        tag_row = rows[1]
        assert tag_row["entity_type"] == "client_tag"
        assert tag_row["op"] == "INSERT"
        assert tag_row["local_id"] == db.conn.execute(
            "SELECT id FROM client_tags WHERE client_id = ?", (client_id,)
        ).fetchone()["id"]

        # Outbox triggers now exist for the previously non-V1 table.
        triggers = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
        }
        assert "trg_client_tags_outbox_ai" in triggers
        assert "trg_client_tags_outbox_au" in triggers
        assert "trg_client_tags_outbox_ad" in triggers

    def test_operations_engine_write_captured(self, db, outbox):
        from services.operations.event_bus import EventBus
        from services.operations.operations_engine import OperationsEngine
        from services.operations.trip_status_workflow import TripStatusWorkflow
        from services.operations.undo_stack import UndoStack
        from services.trip_service import TripService

        trip_service = TripService(db)
        engine = OperationsEngine.create(
            db,
            trip_service=trip_service,
            maintenance_engine=MagicMock(),
            trip_workflow=TripStatusWorkflow(
                db, trip_service, EventBus(), MagicMock(), UndoStack()
            ),
        )
        trip_id = _insert_trip(db, status="Planned")
        assert engine.force_trip_status(trip_id, "Loading") is True

        rows = _outbox_rows(db)
        assert [r["op"] for r in rows] == ["INSERT", "UPDATE"]
        assert rows[-1]["entity_type"] == "trip"
        assert rows[-1]["local_id"] == trip_id
        # The UPDATE payload resolves to the new status at push time.
        assert outbox.resolve_payload("trip", trip_id)["status"] == "Loading"