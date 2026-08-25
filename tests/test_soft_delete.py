"""Soft-delete sweep tests (Phase 3a).

Verifies that desktop services soft-delete (stamp ``deleted_at``) instead of
hard-deleting, and that repository list/get paths exclude soft-deleted rows —
the desktop half of the offline-first sync delete propagation.
"""
from __future__ import annotations

import pytest

from repositories.document_repository import DocumentRepository
from repositories.trip_repository import TripRepository
from services.client_service import ClientService
from services.document_service import DocumentService
from services.driver_truck_service import DriverTruckService
from services.fleet_maintenance_service import FleetMaintenanceService
from services.fleet_service import FleetService
from services.trip_service import TripService
from tests.test_helpers import make_db, seed_admin_user
from tests.test_trip_service import _create_trip


# ── TripService ────────────────────────────────────────────────────────────


class TestTripSoftDelete:
    def test_delete_sets_deleted_at_and_keeps_row(self):
        db = make_db()
        svc = TripService(db)
        trip_id = _create_trip(svc)

        result = svc.delete(trip_id)
        assert result.success is True

        row = db.conn.execute(
            "SELECT deleted_at FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row is not None, "row must still exist after soft-delete"
        assert row["deleted_at"] is not None

    def test_delete_excludes_from_list_all(self):
        db = make_db()
        svc = TripService(db)
        trip_id = _create_trip(svc)
        _create_trip(svc, client_name="Keep Me")

        svc.delete(trip_id)
        listed = svc.list_all()
        assert listed.success is True
        ids = [t.id for t in listed.data]
        assert trip_id not in ids
        assert len(ids) == 1

    def test_delete_excludes_from_get(self):
        db = make_db()
        svc = TripService(db)
        trip_id = _create_trip(svc)
        svc.delete(trip_id)
        assert svc.get_by_id(trip_id) is None


# ── ClientService ──────────────────────────────────────────────────────────


class TestClientSoftDelete:
    def _make_client(self, svc, name):
        # Provide all non-optional ClientResult fields (the legacy create()
        # path filters kwargs against ClientRepository.COLUMNS).
        return svc.create(
            name, vat_number="RO123", address="Test Address",
            email=f"{name.lower()}@test.com", phone="+40700000000", country="RO",
        )

    def test_delete_sets_is_active_zero_and_deleted_at(self):
        db = make_db()
        seed_admin_user(db, user_id=1, company_id=1)
        svc = ClientService(db)
        client_id = self._make_client(svc, "ACME Corp")

        result = svc.delete(client_id, user_id=1)
        assert result.success is True

        row = db.conn.execute(
            "SELECT is_active, deleted_at FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        assert row is not None
        assert row["is_active"] == 0
        assert row["deleted_at"] is not None

    def test_delete_excludes_from_get_all(self):
        db = make_db()
        seed_admin_user(db, user_id=1, company_id=1)
        svc = ClientService(db)
        client_id = self._make_client(svc, "Delete Me")
        self._make_client(svc, "Keep Me")

        svc.delete(client_id, user_id=1)
        active = svc.get_all()
        names = {c["name"] for c in active}
        assert "Delete Me" not in names
        assert "Keep Me" in names

    def test_plain_deactivate_does_not_stamp_deleted_at(self):
        """The UI's deactivate action must NOT look like a delete to sync."""
        db = make_db()
        svc = ClientService(db)
        client_id = self._make_client(svc, "Just Deactivate")

        svc.deactivate(client_id)
        row = db.conn.execute(
            "SELECT is_active, deleted_at FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        assert row["is_active"] == 0
        assert row["deleted_at"] is None


# ── DocumentService ────────────────────────────────────────────────────────


class TestDocumentSoftDelete:
    def _make_doc(self, db, doc_number="DOC-1"):
        db.conn.execute(
            "INSERT INTO documents (doc_number, title, category, entity_type, "
            "entity_id, file_path, file_name, file_size, mime_type, file_hash, "
            "tags, description, uploaded_by, uploaded_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_number, "Test Doc", "general", "", None, "/tmp/test.pdf",
             "test.pdf", 100, "application/pdf", "hash1", "[]", "", "1",
             "2026-01-01", "2026-01-01"),
        )
        db.conn.commit()
        return db.conn.execute(
            "SELECT id FROM documents WHERE doc_number = ?", (doc_number,)
        ).fetchone()["id"]

    def test_archive_sets_is_archived_and_deleted_at(self):
        db = make_db()
        doc_id = self._make_doc(db)
        svc = DocumentService(db)

        svc.archive(doc_id)
        row = db.conn.execute(
            "SELECT is_archived, deleted_at FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        assert row is not None
        assert row["is_archived"] == 1
        assert row["deleted_at"] is not None

    def test_delete_document_sets_deleted_at(self):
        db = make_db()
        seed_admin_user(db, user_id=1, company_id=1)
        doc_id = self._make_doc(db)
        svc = DocumentService(db)

        result = svc.delete_document(doc_id, user_id=1)
        assert result.success is True
        row = db.conn.execute(
            "SELECT deleted_at FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        assert row is not None
        assert row["deleted_at"] is not None

    def test_repo_get_excludes_soft_deleted_document(self):
        db = make_db()
        doc_id = self._make_doc(db)
        repo = DocumentRepository(db)
        repo.delete(doc_id)
        assert repo.get_by_id(doc_id) is None


# ── FleetService ───────────────────────────────────────────────────────────


class TestFleetSoftDelete:
    def test_delete_sets_deleted_at_and_excludes_from_list(self):
        db = make_db()
        seed_admin_user(db, user_id=1, company_id=1)
        svc = FleetService(db)
        truck_id = svc._fleet_repo.create({
            "plate_number": "B-123-ABC", "model": "FH", "manufacturer": "Volvo",
            "status": "active", "active_status": 1,
        })

        result = svc.delete(truck_id, user_id=1)
        assert result.success is True

        row = db.conn.execute(
            "SELECT deleted_at FROM trucks WHERE id = ?", (truck_id,)
        ).fetchone()
        assert row is not None
        assert row["deleted_at"] is not None

        listed = svc.list_all()
        assert listed.success is True
        assert all(v.id != truck_id for v in listed.data)


# ── DriverTruckService ─────────────────────────────────────────────────────


class TestDriverSoftDelete:
    def test_delete_driver_sets_deleted_at_and_excludes_from_list(self):
        db = make_db()
        seed_admin_user(db, user_id=1, company_id=1)
        svc = DriverTruckService(db)
        driver_id = svc._driver_repo.create({
            "name": "John Doe", "is_active": 1, "email": "john@test.com",
            "phone": "+40700123456", "license_number": "L1",
            "created_at": "2026-01-01", "updated_at": "2026-01-01",
        })
        # DriverResult requires hours_worked/max_hours_per_day/status which the
        # drivers table does not store (pre-existing model/DB mismatch) — patch
        # the enrichment so we can exercise the delete path itself.
        svc._enrich_with_truck = lambda d: None

        result = svc.delete_driver(driver_id, user_id=1)
        assert result.success is True

        row = db.conn.execute(
            "SELECT deleted_at FROM drivers WHERE id = ?", (driver_id,)
        ).fetchone()
        assert row is not None
        assert row["deleted_at"] is not None

        # list_drivers() enriches each row (patched above) — check the repo's
        # get_all() excludes the soft-deleted driver instead.
        remaining = svc._driver_repo.get_all(limit=100)
        assert all(d["id"] != driver_id for d in remaining)


# ── FleetMaintenanceService ────────────────────────────────────────────────


class TestMaintenanceSoftDelete:
    def test_delete_record_sets_deleted_at(self):
        db = make_db()
        svc = FleetMaintenanceService(db)
        truck_id = svc._fleet_repo.create({
            "plate_number": "B-1", "active_status": 1,
        })
        rid = svc.add_record(truck_id, "oil_change", "2026-01-01")

        assert svc.delete_record(rid) is True
        row = db.conn.execute(
            "SELECT deleted_at FROM maintenance_records WHERE id = ?", (rid,)
        ).fetchone()
        assert row is not None
        assert row["deleted_at"] is not None

    def test_delete_schedule_sets_deleted_at(self):
        db = make_db()
        svc = FleetMaintenanceService(db)
        truck_id = svc._fleet_repo.create({
            "plate_number": "B-2", "active_status": 1,
        })
        sid = svc.add_schedule(truck_id, "oil_change", interval_km=15000)

        assert svc.delete_schedule(sid) is True
        row = db.conn.execute(
            "SELECT deleted_at FROM maintenance_schedules WHERE id = ?", (sid,)
        ).fetchone()
        assert row is not None
        assert row["deleted_at"] is not None


# ── Repository-level ───────────────────────────────────────────────────────


class TestTripRepositorySoftDelete:
    def test_get_excludes_soft_deleted(self):
        db = make_db()
        repo = TripRepository(db)
        trip_id = repo.create({
            "client_name": "Repo Client", "truck_number": "TRK-1",
            "status": "Planned", "created_at": "2026-01-01",
        })
        repo.delete(trip_id)
        assert repo.get_by_id(trip_id) is None

    def test_get_all_excludes_soft_deleted(self):
        db = make_db()
        repo = TripRepository(db)
        keep_id = repo.create({
            "client_name": "Keep", "truck_number": "TRK-2",
            "status": "Planned", "created_at": "2026-01-01",
        })
        gone_id = repo.create({
            "client_name": "Gone", "truck_number": "TRK-3",
            "status": "Planned", "created_at": "2026-01-01",
        })
        repo.delete(gone_id)
        rows = repo.get_all(limit=100)
        ids = {r["id"] for r in rows}
        assert gone_id not in ids
        assert keep_id in ids

    def test_get_filtered_excludes_soft_deleted(self):
        db = make_db()
        repo = TripRepository(db)
        gone_id = repo.create({
            "client_name": "Filter Gone", "truck_number": "TRK-4",
            "status": "Planned", "created_at": "2026-01-01",
        })
        repo.delete(gone_id)
        rows = repo.get_filtered(search="Filter Gone")
        assert all(r["id"] != gone_id for r in rows)