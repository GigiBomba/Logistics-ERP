"""World Model tests — §6 (blueprint §27.1 ``tests/copilot/test_world_model.py``).

The snapshot must be a *faithful read-view* of the operational state: the
aggregate counts it reports must match what a direct service query returns
against the same database.  These tests seed a real SQLite DB (``InMemoryDB``)
and compare the ``WorldModelService`` snapshot counts against the underlying
``FleetService`` / ``DriverTruckService`` queries — aggregate counts, never
full row dumps.
"""
from __future__ import annotations

import pytest

from backend.copilot.world_model import WorldModelService
from services.fleet_service import FleetService
from tests.test_helpers import InMemoryDB


@pytest.fixture(autouse=True)
def _clear_tenant_context():
    """World-model builders read the tenant context for scoping."""
    from database.tenant_context import clear_context
    yield
    clear_context()


@pytest.fixture
def db():
    d = InMemoryDB()
    yield d
    d.close()


def _seed_fleet(db, company_id: int, rows: list) -> None:
    """Seed truck rows via the repository so company_id scoping applies."""
    from database.tenant_context import set_company_context
    from repositories.fleet_repository import FleetRepository

    set_company_context(company_id)
    repo = FleetRepository(db)
    for r in rows:
        repo.create({
            "plate_number": r["plate"],
            "manufacturer": r.get("manufacturer", "TestCo"),
            "model": r.get("model", "TestModel"),
            "status": r["status"],
            "active_status": 1 if r["status"] == "active" else 0,
        })


class TestFleetSnapshotAccuracy:
    """Fleet snapshot counts equal the direct service query."""

    def test_fleet_counts_match_direct_query(self, db):
        from database.tenant_context import set_company_context

        set_company_context(1)
        _seed_fleet(db, 1, [
            {"plate": "AB-01", "status": "active"},
            {"plate": "AB-02", "status": "active"},
            {"plate": "AB-03", "status": "maintenance"},
        ])

        snapshot = WorldModelService(db).get_slice(company_id=1, sections=["fleet"])

        # Direct service query — the source of truth for the read-view.
        direct = FleetService(db).list_all()
        assert direct.success is True
        direct_total = len(direct.data)
        direct_available = sum(
            1 for v in direct.data
            if (v.get("status") if isinstance(v, dict) else getattr(v, "status", "")) == "active"
        )

        assert snapshot.fleet.total_vehicles == 3
        assert snapshot.fleet.available_count == 2
        assert snapshot.fleet.total_vehicles == direct_total
        assert snapshot.fleet.available_count == direct_available

    def test_fleet_counts_are_tenant_scoped(self, db):
        """Company 1's snapshot must not include company 2's trucks.

        Tenant scoping flows through the ambient tenant context (the same
        mechanism the HTTP/auth path uses), so the context is set per snapshot.
        """
        from database.tenant_context import set_company_context

        set_company_context(1)
        _seed_fleet(db, 1, [
            {"plate": "A-01", "status": "active"},
            {"plate": "A-02", "status": "active"},
        ])
        set_company_context(2)
        _seed_fleet(db, 2, [
            {"plate": "B-01", "status": "active"},
            {"plate": "B-02", "status": "active"},
            {"plate": "B-03", "status": "active"},
        ])

        set_company_context(1)
        snap_1 = WorldModelService(db).get_slice(company_id=1, sections=["fleet"])
        set_company_context(2)
        snap_2 = WorldModelService(db).get_slice(company_id=2, sections=["fleet"])

        assert snap_1.fleet.total_vehicles == 2
        assert snap_2.fleet.total_vehicles == 3

    def test_get_slice_company_id_scopes_independently_of_context(self, db):
        """§6 contract: ``get_slice(company_id=N)`` must return company N's data
        regardless of the ambient tenant context of the caller."""
        from database.tenant_context import set_company_context

        set_company_context(1)
        _seed_fleet(db, 1, [{"plate": "A-01", "status": "active"}])
        set_company_context(2)
        _seed_fleet(db, 2, [
            {"plate": "B-01", "status": "active"},
            {"plate": "B-02", "status": "active"},
        ])

        # Ambient context is company 2, but the caller explicitly asks for
        # company 1's snapshot.  get_slice scopes the builders via the
        # tenant-context API (database.tenant_context.set_company_context),
        # so the snapshot reflects company 1 — not the ambient context.
        set_company_context(2)
        snap = WorldModelService(db).get_slice(company_id=1, sections=["fleet"])
        assert snap.company_id == 1
        assert snap.fleet.total_vehicles == 1

    def test_empty_fleet_returns_zero_counts(self, db):
        from database.tenant_context import set_company_context

        set_company_context(1)
        snapshot = WorldModelService(db).get_slice(company_id=1, sections=["fleet"])
        assert snapshot.fleet.total_vehicles == 0
        assert snapshot.fleet.available_count == 0

    def test_snapshot_metadata(self, db):
        """Snapshot carries company_id, ttl and a generated_at timestamp."""
        from database.tenant_context import set_company_context
        from datetime import datetime

        set_company_context(1)
        snapshot = WorldModelService(db).get_slice(company_id=1, sections=["fleet"])
        assert snapshot.company_id == 1
        assert snapshot.ttl_seconds == 60
        assert isinstance(snapshot.generated_at, datetime)


class TestDriverSnapshotAccuracy:
    """Driver snapshot counts equal the direct repository query.

    NOTE: ``DriverTruckService.list_drivers()`` maps rows to ``DriverResult``,
    which requires ``hours_worked`` / ``max_hours_per_day`` fields that the
    real ``drivers`` table does not have — so the direct source of truth for
    the read-view is the ``DriverRepository`` row query, which is also what
    the world-model builder now uses.
    """

    def _seed_drivers(self, db, company_id: int, count: int) -> None:
        from database.tenant_context import set_company_context
        from repositories.driver_repository import DriverRepository

        set_company_context(company_id)
        repo = DriverRepository(db)
        for i in range(count):
            repo.create({
                "name": f"Driver {i}",
                "email": f"d{i}@test.com",
                "phone": "+40700000000",
                "license_number": f"L{i}",
                "is_active": 1,
            })

    def test_driver_counts_match_direct_query(self, db):
        from database.tenant_context import set_company_context
        from repositories.driver_repository import DriverRepository

        set_company_context(1)
        self._seed_drivers(db, 1, count=3)

        snapshot = WorldModelService(db).get_slice(company_id=1, sections=["drivers"])

        # Direct repository query — the real source of truth for the read-view
        # (the drivers table's actual columns: count + is_active).
        direct = DriverRepository(db).get_all()
        assert snapshot.drivers.total_drivers == len(direct)
        assert snapshot.drivers.total_drivers == 3
        assert snapshot.drivers.available_count == sum(
            1 for d in direct if d.get("is_active")
        )


class TestDocumentSnapshotAccuracy:
    """Document summary counts equal the direct repository query (§9.1)."""

    def _seed_document(self, db, company_id: int, ocr_run_at: str, expiry_date: str = "") -> None:
        from database.tenant_context import set_company_context
        from repositories.document_repository import DocumentRepository

        set_company_context(company_id)
        repo = DocumentRepository(db)
        repo.create(
            doc_number=f"DOC-{company_id}-{ocr_run_at or 'na'}-{abs(hash(expiry_date)) % 10000}",
            title="Test doc", category="other", entity_type="", entity_id=None,
            file_path="/tmp/x.pdf", file_name="x.pdf", file_size=1,
            mime_type="application/pdf", file_hash="", tags="[]", description="",
            uploaded_by="test", uploaded_at="2026-08-01T00:00:00Z",
            updated_at="2026-08-01T00:00:00Z", company_id=company_id,
        )
        # Stamp OCR/expiry directly so the builder sees them.
        db.conn.execute(
            "UPDATE documents SET ocr_run_at = ?, expiry_date = ? WHERE doc_number = ?",
            (ocr_run_at, expiry_date, f"DOC-{company_id}-{ocr_run_at or 'na'}-{abs(hash(expiry_date)) % 10000}"),
        )

    def test_document_counts_match_direct_query(self, db):
        from database.tenant_context import set_company_context
        from datetime import datetime, timedelta

        set_company_context(1)
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        later = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        self._seed_document(db, 1, ocr_run_at="")                 # pending OCR
        self._seed_document(db, 1, ocr_run_at="2026-08-01T00:00:00Z", expiry_date=tomorrow)  # processed, expiring
        self._seed_document(db, 1, ocr_run_at="2026-08-01T00:00:00Z", expiry_date=later)     # processed, not expiring

        snapshot = WorldModelService(db).get_slice(company_id=1, sections=["documents"])
        assert snapshot.documents.pending_ocr == 1
        assert snapshot.documents.expiring_soon == 1


class TestDispatchSnapshotAccuracy:
    """Dispatch summary counts from trips by status."""

    def _seed_trip(self, db, company_id: int, status: str) -> None:
        from database.tenant_context import set_company_context
        from repositories.trip_repository import TripRepository

        set_company_context(company_id)
        TripRepository(db).create({
            "truck_number": "AB-01", "client_name": "ACME", "status": status,
            "distance_km": 100.0, "created_at": "2026-08-01T00:00:00Z",
        })

    def test_dispatch_counts_match_statuses(self, db):
        from database.tenant_context import set_company_context

        set_company_context(1)
        self._seed_trip(db, 1, "loading")
        self._seed_trip(db, 1, "planned")
        self._seed_trip(db, 1, "in_transit")
        self._seed_trip(db, 1, "delivered")

        snapshot = WorldModelService(db).get_slice(company_id=1, sections=["dispatches"])
        assert snapshot.dispatches.pending_dispatches == 2   # loading + planned
        assert snapshot.dispatches.in_transit == 1


class TestNotificationSnapshotAccuracy:
    """Notification summary counts from company alerts."""

    def _seed_alert(self, db, company_id: int, severity: str, resolved: int = 0) -> None:
        db.conn.execute(
            "INSERT INTO alerts (id, type, severity, title, message, company_id, created_at, resolved) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"alert-{company_id}-{severity}-{resolved}-{id(self)}", "alert", severity,
             "T", "M", company_id, "2026-08-01T00:00:00Z", resolved),
        )

    def test_notification_counts_match_alerts(self, db):
        from database.tenant_context import set_company_context

        set_company_context(1)
        # alerts table may not be in the base InMemoryDB schema — ensure it exists.
        db.conn.execute(
            "CREATE TABLE IF NOT EXISTS alerts ("
            "id TEXT PRIMARY KEY, type TEXT NOT NULL, severity TEXT NOT NULL, title TEXT, "
            "message TEXT, truck_id TEXT, trip_id INTEGER, created_at TEXT NOT NULL, "
            "resolved INTEGER DEFAULT 0, resolved_at TEXT, metadata_json TEXT, company_id INTEGER)"
        )
        self._seed_alert(db, 1, severity="critical", resolved=0)
        self._seed_alert(db, 1, severity="high", resolved=0)
        self._seed_alert(db, 1, severity="low", resolved=0)
        self._seed_alert(db, 1, severity="high", resolved=1)  # resolved → not unread

        snapshot = WorldModelService(db).get_slice(company_id=1, sections=["notifications"])
        assert snapshot.notifications.unread_count == 3
        assert snapshot.notifications.critical_count == 2  # critical + high

    def test_notification_counts_are_company_scoped(self, db):
        from database.tenant_context import set_company_context

        set_company_context(1)
        db.conn.execute(
            "CREATE TABLE IF NOT EXISTS alerts ("
            "id TEXT PRIMARY KEY, type TEXT NOT NULL, severity TEXT NOT NULL, title TEXT, "
            "message TEXT, truck_id TEXT, trip_id INTEGER, created_at TEXT NOT NULL, "
            "resolved INTEGER DEFAULT 0, resolved_at TEXT, metadata_json TEXT, company_id INTEGER)"
        )
        self._seed_alert(db, 1, severity="low", resolved=0)
        self._seed_alert(db, 2, severity="critical", resolved=0)

        snap_1 = WorldModelService(db).get_slice(company_id=1, sections=["notifications"])
        snap_2 = WorldModelService(db).get_slice(company_id=2, sections=["notifications"])
        assert snap_1.notifications.unread_count == 1
        assert snap_2.notifications.unread_count == 1
        assert snap_1.notifications.critical_count == 0