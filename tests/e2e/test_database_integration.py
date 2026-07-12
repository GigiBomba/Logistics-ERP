"""Comprehensive integration tests for DatabaseManager with file-based SQLite.

Tests all repositories together (TripRepository, ClientRepository, FleetRepository,
DriverRepository, InvoiceRepository) via a real DatabaseManager backed by a
temporary SQLite file.  Covers CRUD, cross-table operations, transactions,
multi-tenant isolation, and edge cases.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, Generator, List

import pytest

from database.db_manager import DatabaseManager
from repositories.client_repository import ClientRepository
from repositories.driver_repository import DriverRepository
from repositories.fleet_repository import FleetRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.trip_repository import TripRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path() -> Generator[str, None, None]:
    """Create a temporary SQLite database file, yield its path, then delete."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def db(db_path: str) -> Generator[DatabaseManager, None, None]:
    """Create and yield a DatabaseManager backed by a temp file, then close."""
    _db = DatabaseManager(db_path)
    yield _db
    try:
        _db.close()
    except Exception:
        pass


@pytest.fixture
def trip_repo(db: DatabaseManager) -> TripRepository:
    return TripRepository(db)


@pytest.fixture
def client_repo(db: DatabaseManager) -> ClientRepository:
    return ClientRepository(db)


@pytest.fixture
def fleet_repo(db: DatabaseManager) -> FleetRepository:
    return FleetRepository(db)


@pytest.fixture
def driver_repo(db: DatabaseManager) -> DriverRepository:
    return DriverRepository(db)


@pytest.fixture
def invoice_repo(db: DatabaseManager) -> InvoiceRepository:
    return InvoiceRepository(db)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dt(days_offset: int = 0) -> str:
    """Return an ISO-formatted date string offset from today."""
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


def _now() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _create_company(db: DatabaseManager, name: str) -> int:
    """Insert a company record and return its id."""
    c = db.conn.execute(
        "INSERT INTO companies (company_name, subscription_tier) VALUES (?, ?)",
        (name, "starter"),
    )
    db.conn.commit()
    rid = c.lastrowid
    assert rid is not None and rid > 0
    return rid


def _sample_trip(client_name: str = "Acme Corp", **overrides: Any) -> Dict[str, Any]:
    """Return a dict of trip fields with sensible defaults."""
    data: Dict[str, Any] = {
        "created_at": _now(),
        "truck_number": "AB-123-CD",
        "driver_name": "John Doe",
        "client_name": client_name,
        "distance_km": 850.0,
        "total_price_eur": 3400.0,
        "rate_per_km": 4.0,
        "gross_per_km": 3.6,
        "net_profit": 500.0,
        "start_date": _dt(-2),
        "end_date": _dt(0),
        "currency": "EUR",
        "status": "Delivered",
        "loading_country": "DE",
        "delivery_country": "FR",
    }
    data.update(overrides)
    return data


# ===================================================================
# TestDatabaseInitialization
# ===================================================================

class TestDatabaseInitialization:
    """Verify the DatabaseManager creates and manages the SQLite schema correctly."""

    EXPECTED_TABLES = {
        "trips", "trucks", "drivers", "clients", "invoices",
        "settings", "companies", "users",
        "route_history_v2", "route_events", "truck_route_assignments",
        "alerts", "operation_events", "trip_status_history",
        "documents", "document_links", "document_versions",
        "contracts", "document_templates",
        "maintenance_records", "maintenance_schedules", "truck_health_scores",
        "driver_truck_assignments",
        "tacho_imports", "tacho_driver_activity", "tacho_vehicle_data",
        "client_contacts", "client_tags",
        "proforma_invoices", "invoice_reminders",
        "receipts",
        "automail_templates", "automail_schedules",
        "automail_client_overrides", "automail_settings",
        "gps_telemetry",
        "document_pipeline_runs", "document_package", "document_package_items",
        "successive_carriers", "cmr_counter", "cmr_audit_log",
        "email_logs",
    }

    def test_init_creates_all_tables(self, db: DatabaseManager) -> None:
        """Verify all expected tables exist after initialization."""
        present = {
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing = self.EXPECTED_TABLES - present
        assert not missing, f"Missing tables: {sorted(missing)}"

    def test_init_is_idempotent(self, db_path: str) -> None:
        """Running DatabaseManager.__init__ twice on the same file is safe."""
        dm1 = DatabaseManager(db_path)
        dm1.close()
        dm2 = DatabaseManager(db_path)
        dm2.close()

    def test_close_and_reopen_preserves_data(self, db_path: str) -> None:
        """Write data, close, reopen, and verify the data is still there."""
        # First session — create a trip
        dm1 = DatabaseManager(db_path)
        repo1 = TripRepository(dm1)
        tid = repo1.create(_sample_trip())
        dm1.close()

        # Second session — read it back
        dm2 = DatabaseManager(db_path)
        repo2 = TripRepository(dm2)
        trip = repo2.get_by_id(tid)
        assert trip is not None
        assert trip["client_name"] == "Acme Corp"
        dm2.close()

    def test_wal_mode_active(self, db: DatabaseManager) -> None:
        """Verify journal_mode is set to WAL."""
        row = db.conn.execute("PRAGMA journal_mode").fetchone()
        mode = row[0] if row else ""
        assert mode.upper() == "WAL", f"Expected WAL, got {mode}"

    def test_table_columns_trips(self, db: DatabaseManager) -> None:
        """Spot-check that trips has expected columns from migrations."""
        cols = {r[1] for r in db.conn.execute("PRAGMA table_info(trips)").fetchall()}
        for expected in ("id", "client_name", "status", "company_id", "client_id", "driver_id", "truck_id"):
            assert expected in cols, f"Missing column 'trips.{expected}'"

    def test_table_columns_clients(self, db: DatabaseManager) -> None:
        """Spot-check clients columns including migrated ones."""
        cols = {r[1] for r in db.conn.execute("PRAGMA table_info(clients)").fetchall()}
        for expected in ("id", "name", "company_id", "client_type", "payment_terms_days"):
            assert expected in cols, f"Missing column 'clients.{expected}'"


# ===================================================================
# TestTripCRUDIntegration
# ===================================================================

class TestTripCRUDIntegration:
    """End-to-end CRUD operations on the trips table via TripRepository."""

    def test_create_and_read_trip(self, trip_repo: TripRepository) -> None:
        """Create a trip, then read it back and verify all fields."""
        data = _sample_trip(client_name="TestCorp")
        trip_id = trip_repo.create(data)
        assert trip_id > 0

        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        for key in ("client_name", "truck_number", "driver_name", "status", "currency"):
            assert trip[key] == data[key], f"Mismatch on {key}"

    def test_update_trip_fields(self, trip_repo: TripRepository) -> None:
        """Create a trip, update multiple fields, and verify persistence."""
        trip_id = trip_repo.create(_sample_trip(status="Planned"))

        trip_repo.update(trip_id, {"status": "In Transit", "truck_number": "XY-999-ZZ"})

        updated = trip_repo.get_by_id(trip_id)
        assert updated is not None
        assert updated["status"] == "In Transit"
        assert updated["truck_number"] == "XY-999-ZZ"

    def test_delete_trip_cascades_to_invoice(
        self, trip_repo: TripRepository, db: DatabaseManager
    ) -> None:
        """Deleting a trip cascades to its linked invoice (ON DELETE CASCADE)."""
        trip_id = trip_repo.create(_sample_trip())
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trip_id, "INV-CASCADE-001", _dt(0), _dt(30), 3400.0, "Unpaid"),
        )
        db.conn.commit()
        inv = db.conn.execute(
            "SELECT id FROM invoices WHERE trip_id = ?", (trip_id,)
        ).fetchone()
        inv_id = inv["id"]

        # Verify both exist
        assert db.conn.execute("SELECT id FROM invoices WHERE id = ?", (inv_id,)).fetchone() is not None

        # Delete the trip — invoice should cascade-delete
        trip_repo.delete(trip_id)

        assert trip_repo.get_by_id(trip_id) is None, "Trip should be deleted"
        assert db.conn.execute("SELECT id FROM invoices WHERE id = ?", (inv_id,)).fetchone() is None, "Invoice should cascade-delete"

    def test_bulk_create_100_trips(self, trip_repo: TripRepository) -> None:
        """Bulk-insert 100 trips and verify the count."""
        for i in range(100):
            trip_repo.create(_sample_trip(
                client_name=f"BulkClient-{i}",
                truck_number=f"TRK-{i:04d}",
            ))

        all_trips = trip_repo.get_all(limit=500)
        assert len(all_trips) == 100

    def test_filtered_search_by_status(
        self, trip_repo: TripRepository
    ) -> None:
        """Create trips with different statuses, then filter by status."""
        trip_repo.create(_sample_trip(status="Planned", client_name="Alpha"))
        trip_repo.create(_sample_trip(status="In Transit", client_name="Beta"))
        trip_repo.create(_sample_trip(status="Delivered", client_name="Gamma"))
        trip_repo.create(_sample_trip(status="Delivered", client_name="Delta"))
        trip_repo.create(_sample_trip(status="Cancelled", client_name="Epsilon"))

        delivered = trip_repo.get_filtered(status="Delivered")
        assert len(delivered) == 2
        for t in delivered:
            assert t["status"] == "Delivered"

    def test_filtered_search_by_text(
        self, trip_repo: TripRepository
    ) -> None:
        """Search trips by client_name partial match."""
        trip_repo.create(_sample_trip(client_name="Global Transport Inc"))
        trip_repo.create(_sample_trip(client_name="Global Logistics Ltd"))
        trip_repo.create(_sample_trip(client_name="Local Movers"))

        results = trip_repo.get_filtered(search="Global")
        assert len(results) == 2

    def test_get_by_id_returns_none_for_missing(self, trip_repo: TripRepository) -> None:
        """get_by_id returns None for a non-existent trip."""
        assert trip_repo.get_by_id(99999) is None


# ===================================================================
# TestCrossTableOperations
# ===================================================================

class TestCrossTableOperations:
    """Tests that involve multiple related tables."""

    def test_create_trip_with_client_and_truck(
        self,
        db: DatabaseManager,
        trip_repo: TripRepository,
        client_repo: ClientRepository,
        fleet_repo: FleetRepository,
        driver_repo: DriverRepository,
    ) -> None:
        """Create a client, truck, and driver; then create a trip referencing all three."""
        # Create client
        client_id = client_repo.create({
            "name": "CrossTable Client",
            "contact_person": "Jane Smith",
            "email": "jane@example.com",
            "created_at": _now(),
        })
        assert client_id > 0

        # Create truck
        truck_id = fleet_repo.create({
            "plate_number": "CT-555-TRUCK",
            "model": "Actros",
            "manufacturer": "Mercedes",
            "active_status": 1,
        })
        assert truck_id > 0

        # Create driver
        driver_id = driver_repo.create({
            "name": "Alice Driver",
            "phone": "+123456789",
            "is_active": 1,
        })
        assert driver_id > 0

        # Create trip referencing all three
        trip_id = trip_repo.create(_sample_trip(
            client_id=client_id,
            truck_id=truck_id,
            driver_id=driver_id,
            client_name="CrossTable Client",
        ))
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        assert trip["client_id"] == client_id
        assert trip["truck_id"] == truck_id
        assert trip["driver_id"] == driver_id

    def test_invoice_linked_to_trip(
        self,
        db: DatabaseManager,
        trip_repo: TripRepository,
    ) -> None:
        """Create a trip, then an invoice for it, and verify the link works both ways."""
        trip_id = trip_repo.create(_sample_trip(client_name="Invoice Test"))
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trip_id, "INV-LINK-001", _dt(0), _dt(30), 3400.0, "Unpaid"),
        )
        db.conn.commit()

        # Read invoice via get_by_trip_id
        invoice_repo = InvoiceRepository(db)
        invoice = invoice_repo.get_by_trip_id(trip_id)
        assert invoice is not None
        assert invoice["total_amount"] == 3400.0

        # Read trip via get_by_invoice_via_trip_invoice (trips join invoices)
        trips = trip_repo.get_by_invoice_via_trip_invoice("INV-LINK-001")
        assert len(trips) == 1
        assert trips[0]["id"] == trip_id

    def test_client_merge_flow(
        self,
        db: DatabaseManager,
        client_repo: ClientRepository,
        trip_repo: TripRepository,
    ) -> None:
        """Merge client A into client B: trips reassigned, client A deactivated."""
        client_a_id = client_repo.create({"name": "Merge Source", "created_at": _now()})
        client_b_id = client_repo.create({"name": "Merge Target", "created_at": _now()})

        # Create trips for both clients
        trip_a1 = trip_repo.create(_sample_trip(client_id=client_a_id, client_name="Merge Source"))
        trip_a2 = trip_repo.create(_sample_trip(client_id=client_a_id, client_name="Merge Source"))
        trip_b1 = trip_repo.create(_sample_trip(client_id=client_b_id, client_name="Merge Target"))

        # Merge
        result = client_repo.merge_client_data(from_id=client_a_id, to_id=client_b_id)
        assert result["trips"] == 2

        # Verify trips reassigned
        trips_for_b = client_repo.get_trips(client_b_id)
        assert len(trips_for_b) == 3

        # Verify source client deactivated
        source = client_repo.get_by_id(client_a_id)
        assert source is not None
        assert source["is_active"] == 0

    def test_route_to_trip_link(
        self, db: DatabaseManager, trip_repo: TripRepository
    ) -> None:
        """Create a route_history_v2 entry, then a trip with route_history_v2_id."""
        cursor = db.conn.execute(
            "INSERT INTO route_history_v2 (route_fingerprint, created_at, last_calculated_at, stops_json) "
            "VALUES (?, ?, ?, ?)",
            ("route-001", _now(), _now(), '[]'),
        )
        db.conn.commit()
        route_id = cursor.lastrowid
        assert route_id is not None and route_id > 0

        trip_id = trip_repo.create(_sample_trip(route_history_v2_id=route_id))
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        assert trip["route_history_v2_id"] == route_id


# ===================================================================
# TestTransactionIntegrity
# ===================================================================

class TestTransactionIntegrity:
    """Verify that explicit transaction commit and rollback work correctly."""

    def test_commit_persists_data(self, db: DatabaseManager) -> None:
        """Begin a transaction, insert via raw SQL, commit — data must be visible."""
        db.conn.execute("BEGIN")
        db.conn.execute(
            "INSERT INTO trips (created_at, client_name, truck_number, status, currency, "
            "loading_country, delivery_country) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now(), "Commit Test", "TX-001", "Planned", "EUR", "DE", "FR"),
        )
        db.conn.commit()

        row = db.conn.execute(
            "SELECT client_name FROM trips WHERE client_name = ?", ("Commit Test",)
        ).fetchone()
        assert row is not None
        assert row["client_name"] == "Commit Test"

    def test_rollback_discards_data(self, db: DatabaseManager) -> None:
        """Begin a transaction, insert via raw SQL, rollback — data must NOT be visible."""
        db.conn.execute("BEGIN")
        db.conn.execute(
            "INSERT INTO trips (created_at, client_name, truck_number, status, currency, "
            "loading_country, delivery_country) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now(), "Rollback Test", "TX-002", "Planned", "EUR", "DE", "FR"),
        )
        db.conn.execute("ROLLBACK")

        row = db.conn.execute(
            "SELECT client_name FROM trips WHERE client_name = ?", ("Rollback Test",)
        ).fetchone()
        assert row is None, "Rolled-back data should not be visible"

    def test_nested_operations_in_transaction(self, db: DatabaseManager) -> None:
        """Multiple inserts in one transaction — all or nothing on rollback."""
        # Insert two trips + an invoice in one transaction
        db.conn.execute("BEGIN")
        db.conn.execute(
            "INSERT INTO trips (created_at, client_name, truck_number, status, currency, "
            "loading_country, delivery_country) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now(), "Nested A", "TX-003", "Planned", "EUR", "DE", "FR"),
        )
        db.conn.execute(
            "INSERT INTO trips (created_at, client_name, truck_number, status, currency, "
            "loading_country, delivery_country) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now(), "Nested B", "TX-004", "Planned", "EUR", "DE", "FR"),
        )
        # Fetch the IDs we just inserted
        t1 = db.conn.execute(
            "SELECT id FROM trips WHERE client_name = ?", ("Nested A",)
        ).fetchone()["id"]
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (t1, "INV-NEST-001", _dt(0), _dt(30), 1000.0, "Unpaid"),
        )
        db.conn.commit()

        # Both trips and invoice should be visible
        assert db.conn.execute(
            "SELECT id FROM trips WHERE client_name = ?", ("Nested A",)
        ).fetchone() is not None
        assert db.conn.execute(
            "SELECT id FROM trips WHERE client_name = ?", ("Nested B",)
        ).fetchone() is not None
        assert db.conn.execute(
            "SELECT id FROM invoices WHERE invoice_number = ?", ("INV-NEST-001",)
        ).fetchone() is not None

        # Now test rollback
        db.conn.execute("BEGIN")
        db.conn.execute(
            "INSERT INTO trips (created_at, client_name, truck_number, status, currency, "
            "loading_country, delivery_country) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now(), "Nested C", "TX-005", "Planned", "EUR", "DE", "FR"),
        )
        db.conn.execute(
            "INSERT INTO trips (created_at, client_name, truck_number, status, currency, "
            "loading_country, delivery_country) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now(), "Nested D", "TX-006", "Planned", "EUR", "DE", "FR"),
        )
        db.conn.execute("ROLLBACK")

        assert db.conn.execute(
            "SELECT id FROM trips WHERE client_name = ?", ("Nested C",)
        ).fetchone() is None
        assert db.conn.execute(
            "SELECT id FROM trips WHERE client_name = ?", ("Nested D",)
        ).fetchone() is None


# ===================================================================
# TestMultiTenantIsolation
# ===================================================================

class TestMultiTenantIsolation:
    """Verify company-level data isolation via user_company_id and user_role."""

    def _setup_companies_and_data(
        self, db: DatabaseManager
    ) -> tuple[int, int, int, int]:
        """Create two companies and populate with data. Returns (company_a_id, company_b_id, trip_a_id, trip_b_id)."""
        # Create companies (admin backfill sets company_id=1 automatically)
        cid_a = _create_company(db, "Company A")
        cid_b = _create_company(db, "Company B")

        # Create data for company A — scoped user
        db.user_company_id = cid_a
        db.user_role = "dispatcher"
        trip_repo = TripRepository(db)
        trip_a_id = trip_repo.create(_sample_trip(client_name="Company A Client"))

        # Create data for company B — scoped user
        db.user_company_id = cid_b
        trip_b_id = trip_repo.create(_sample_trip(client_name="Company B Client"))

        return cid_a, cid_b, trip_a_id, trip_b_id

    def test_admin_sees_all_companies(self, db: DatabaseManager) -> None:
        """Admin user (user_role='admin', company_id=None) sees all records."""
        _, _, trip_a_id, trip_b_id = self._setup_companies_and_data(db)

        # Act as admin
        db.user_company_id = None
        db.user_role = "admin"
        trip_repo = TripRepository(db)

        all_trips = trip_repo.get_all(limit=100)
        ids = {t["id"] for t in all_trips}
        assert trip_a_id in ids, "Admin should see company A's trip"
        assert trip_b_id in ids, "Admin should see company B's trip"

    def test_scoped_user_sees_only_own_company(self, db: DatabaseManager) -> None:
        """A scoped user sees only their own company's data."""
        cid_a, _, trip_a_id, trip_b_id = self._setup_companies_and_data(db)

        # Act as company A user
        db.user_company_id = cid_a
        db.user_role = "dispatcher"
        trip_repo = TripRepository(db)

        all_trips = trip_repo.get_all(limit=100)
        ids = {t["id"] for t in all_trips}
        assert trip_a_id in ids, "Should see own company's trip"
        assert trip_b_id not in ids, "Should NOT see other company's trip"

    def test_scoped_user_cannot_see_other_company_directly(
        self, db: DatabaseManager
    ) -> None:
        """A scoped user cannot read a specific trip from another company."""
        cid_a, cid_b, _, trip_b_id = self._setup_companies_and_data(db)

        # Act as company A user — switch to company A's scope
        db.user_role = "dispatcher"
        db.user_company_id = cid_a
        trip_repo = TripRepository(db)

        # Try to access trip B directly — should be blocked by company filter
        trip = trip_repo.get_by_id(trip_b_id)
        assert trip is None, "Scoped user should not see other company's trip"

    def test_scoped_user_cannot_access_cross_company_client(
        self, db: DatabaseManager
    ) -> None:
        """Verify scoped user cannot see clients from another company."""
        cid_a, cid_b = _create_company(db, "Company A"), _create_company(db, "Company B")

        # Create client in company B
        db.user_company_id = cid_b
        db.user_role = "dispatcher"
        client_repo = ClientRepository(db)
        client_b_id = client_repo.create({"name": "B-Client", "created_at": _now()})

        # Switch to company A and try to read it
        db.user_company_id = cid_a
        client_b = client_repo.get_by_id(client_b_id)
        assert client_b is None, "Should not see other company's client"


# ===================================================================
# TestEdgeCases
# ===================================================================

class TestEdgeCases:
    """Edge cases and defensive behaviour."""

    def test_empty_search_returns_all(
        self, trip_repo: TripRepository
    ) -> None:
        """Calling get_filtered with no filters returns all trips."""
        trip_repo.create(_sample_trip(client_name="A"))
        trip_repo.create(_sample_trip(client_name="B"))
        trip_repo.create(_sample_trip(client_name="C"))

        results = trip_repo.get_filtered(search="", truck="", status="")
        assert len(results) >= 3

    def test_delete_nonexistent_is_safe(
        self, trip_repo: TripRepository
    ) -> None:
        """Deleting a trip that does not exist should not raise."""
        trip_repo.delete(99999)  # should not raise

    def test_update_nonexistent_does_nothing(
        self, trip_repo: TripRepository
    ) -> None:
        """Updating a non-existent trip silently does nothing (no rows affected)."""
        trip_repo.update(99999, {"status": "Delivered"})  # should not raise

    def test_very_long_string_data(
        self, trip_repo: TripRepository
    ) -> None:
        """Very long strings in text fields are handled correctly."""
        long_name = "A" * 5000
        trip_id = trip_repo.create(_sample_trip(
            client_name=long_name,
            cargo_description=long_name,
        ))
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        assert trip["client_name"] == long_name
        assert trip["cargo_description"] == long_name

    def test_special_characters_in_names(
        self,
        trip_repo: TripRepository,
        client_repo: ClientRepository,
        driver_repo: DriverRepository,
        fleet_repo: FleetRepository,
    ) -> None:
        """Unicode and special characters in text fields."""
        # Trip with special characters
        trip_id = trip_repo.create(_sample_trip(
            client_name="Müller & Söhne GmbH",
            driver_name="José María García",
            cargo_description="Café Français — 100% Arabica ♻",
        ))
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        assert trip["client_name"] == "Müller & Söhne GmbH"
        assert trip["driver_name"] == "José María García"
        assert "♻" in trip["cargo_description"]

        # Client with special characters
        client_id = client_repo.create({
            "name": "Ål足 Exprés",
            "contact_person": "Łukasz Wiśniewski",
            "email": "test@exemple.com",
            "created_at": _now(),
        })
        client = client_repo.get_by_id(client_id)
        assert client is not None
        assert client["name"] == "Ål足 Exprés"

        # Truck with special character in plate
        truck_id = fleet_repo.create({
            "plate_number": "B-100-XL",
            "model": "重卡",
            "active_status": 1,
        })
        truck = fleet_repo.get_by_id(truck_id)
        assert truck is not None
        assert truck["model"] == "重卡"

    def test_null_and_empty_string_handling(
        self,
        trip_repo: TripRepository,
        client_repo: ClientRepository,
    ) -> None:
        """Fields set to None or empty string are handled gracefully."""
        # Create with minimal fields
        client_id = client_repo.create({
            "name": "Nullable Fields Client",
            "created_at": _now(),
        })
        client = client_repo.get_by_id(client_id)
        assert client is not None
        # Optional fields should be None / empty
        assert client.get("phone") is None or client.get("phone") == ""

        # Trip with empty strings for optional fields
        trip_id = trip_repo.create(_sample_trip(
            cargo_description="",
            adr_info_json="",
            cmr_remarks="",
        ))
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None

        # Search with empty query should return all
        results = client_repo.search("")
        assert len(results) >= 1

        # Search with None-like value
        results = client_repo.search("%")
        assert isinstance(results, list)

    def test_trip_with_null_fk_fields(
        self, trip_repo: TripRepository
    ) -> None:
        """Trip can be created without FK references (client_id, truck_id, driver_id)."""
        trip_id = trip_repo.create(_sample_trip(client_id=None, truck_id=None, driver_id=None))
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        assert trip["client_id"] is None
        assert trip["truck_id"] is None
        assert trip["driver_id"] is None


# ===================================================================
# TestConcurrentSafety (basic — no threading, just pattern verification)
# ===================================================================

class TestConcurrentSafety:
    """Basic safety patterns without actual threading."""

    def test_cmr_sequence_isolation(self, db: DatabaseManager) -> None:
        """CMR sequence generation should produce unique numbers in sequence."""
        trip_repo = TripRepository(db)

        year = datetime.now().year
        seen: set = set()
        for _ in range(10):
            cmr_number, seq = trip_repo.get_next_cmr_sequence(year)
            assert cmr_number not in seen, f"Duplicate CMR number: {cmr_number}"
            seen.add(cmr_number)

    def test_repository_instances_share_connection(
        self, db: DatabaseManager
    ) -> None:
        """Multiple repository instances share the same DB connection."""
        repo_a = TripRepository(db)
        repo_b = TripRepository(db)
        assert repo_a.db.conn is repo_b.db.conn


# ===================================================================
# TestDataConsistency
# ===================================================================

class TestDataConsistency:
    """Verify invariants and referential integrity across operations."""

    def test_company_backfill_on_init(self, db_path: str) -> None:
        """After init, all tenant tables have company_id set to 1 for existing rows."""
        # First session: seed a company with id=1 for FK compliance, then create a trip
        dm = DatabaseManager(db_path)
        dm.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
            "VALUES (1, 'Default Co', 'starter')"
        )
        dm.conn.commit()
        repo = TripRepository(dm)

        # Create a trip (admin mode — no company_id injected)
        dm.user_role = "admin"
        dm.user_company_id = None
        tid = repo.create(_sample_trip(client_name="Backfill Test"))
        # Verify company_id was not set by the repo (admin mode)
        trip = repo.get_by_id(tid)
        assert trip is not None
        assert trip["company_id"] is None
        dm.close()

        # Re-open — the _run_column_migrations backfill should set company_id=1 for NULL rows
        dm2 = DatabaseManager(db_path)
        row = dm2.conn.execute("SELECT company_id FROM trips WHERE id = ?", (tid,)).fetchone()
        assert row is not None
        assert row["company_id"] == 1, f"Expected backfill to set company_id=1, got {row['company_id']}"
        dm2.close()

    def test_invoice_cascade_on_trip_delete(
        self,
        db: DatabaseManager,
        trip_repo: TripRepository,
    ) -> None:
        """Verify ON DELETE CASCADE removes invoice when trip is deleted."""
        trip_id = trip_repo.create(_sample_trip())
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trip_id, "INV-CASCADE-VRFY", _dt(0), _dt(30), 100.0, "Unpaid"),
        )
        db.conn.commit()
        inv = db.conn.execute(
            "SELECT id FROM invoices WHERE trip_id = ?", (trip_id,)
        ).fetchone()
        inv_id = inv["id"]

        trip_repo.delete(trip_id)
        inv_repo = InvoiceRepository(db)
        assert inv_repo.get_by_id(inv_id) is None
        assert trip_repo.get_by_id(trip_id) is None

    def test_duplicate_invoice_number_rejected(
        self, db: DatabaseManager, trip_repo: TripRepository
    ) -> None:
        """Creating an invoice with a duplicate number raises IntegrityError."""
        trip_id_1 = trip_repo.create(_sample_trip(client_name="Duplicate Invoice Test A"))
        trip_id_2 = trip_repo.create(_sample_trip(client_name="Duplicate Invoice Test B"))

        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trip_id_1, "INV-DUP-001", _dt(0), _dt(30), 500.0, "Unpaid"),
        )
        db.conn.commit()

        with pytest.raises(Exception):
            db.conn.execute(
                "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (trip_id_2, "INV-DUP-001", _dt(0), _dt(30), 600.0, "Unpaid"),
            )
            db.conn.commit()

    def test_unique_trip_invoice_link(
        self, db: DatabaseManager, trip_repo: TripRepository
    ) -> None:
        """Only one invoice can be linked to a trip (trip_id is UNIQUE in invoices)."""
        trip_id = trip_repo.create(_sample_trip(client_name="Unique Link Test"))

        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trip_id, "INV-UNIQUE-001", _dt(0), _dt(30), 500.0, "Unpaid"),
        )
        db.conn.commit()

        with pytest.raises(Exception):
            db.conn.execute(
                "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (trip_id, "INV-UNIQUE-002", _dt(0), _dt(30), 600.0, "Unpaid"),
            )
            db.conn.commit()


# ===================================================================
# TestScopedFilterEndToEnd
# ===================================================================

class TestScopedFilterEndToEnd:
    """End-to-end verification that the company filter is applied across all repositories."""

    def test_all_repositories_respect_company_filter(
        self, db: DatabaseManager
    ) -> None:
        """Verify TripRepository, ClientRepository, FleetRepository, DriverRepository,
        and InvoiceRepository all apply the company filter when scoped."""
        cid_a = _create_company(db, "Scope E2E A")
        cid_b = _create_company(db, "Scope E2E B")

        # ── Populate company A ──────────────────────────────────────
        db.user_company_id = cid_a
        db.user_role = "dispatcher"

        client_repo = ClientRepository(db)
        ca = client_repo.create({"name": "A-Client", "created_at": _now()})

        fleet_repo = FleetRepository(db)
        ta = fleet_repo.create({"plate_number": "A-TRUCK", "active_status": 1})

        driver_repo = DriverRepository(db)
        da = driver_repo.create({"name": "A-Driver", "is_active": 1})

        trip_repo = TripRepository(db)
        tra = trip_repo.create(_sample_trip(
            client_name="A-Trip", client_id=ca, truck_id=ta, driver_id=da,
        ))

        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
            "total_amount, status, company_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tra, "INV-SCOPE-A", _dt(0), _dt(30), 100.0, "Unpaid", cid_a),
        )
        db.conn.commit()

        # ── Populate company B ──────────────────────────────────────
        db.user_company_id = cid_b

        cb = client_repo.create({"name": "B-Client", "created_at": _now()})
        tb = fleet_repo.create({"plate_number": "B-TRUCK", "active_status": 1})
        db2 = driver_repo.create({"name": "B-Driver", "is_active": 1})
        trb = trip_repo.create(_sample_trip(
            client_name="B-Trip", client_id=cb, truck_id=tb, driver_id=db2,
        ))
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
            "total_amount, status, company_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trb, "INV-SCOPE-B", _dt(0), _dt(30), 200.0, "Unpaid", cid_b),
        )
        db.conn.commit()

        # ── Verify admin sees all ───────────────────────────────────
        db.user_role = "admin"
        db.user_company_id = None

        inv_repo = InvoiceRepository(db)
        assert len(trip_repo.get_all(limit=100)) == 2
        assert len(client_repo.get_all(include_inactive=True)) == 2
        assert len(fleet_repo.get_all()) == 2
        assert len(driver_repo.get_all()) == 2
        assert len(inv_repo.get_all()) == 2

        # ── Verify scoped to A sees only A ──────────────────────────
        db.user_role = "dispatcher"
        db.user_company_id = cid_a

        a_trips = trip_repo.get_all(limit=100)
        assert len(a_trips) == 1
        assert a_trips[0]["id"] == tra

        a_clients = client_repo.get_all(include_inactive=True)
        assert len(a_clients) == 1
        assert a_clients[0]["name"] == "A-Client"

        a_trucks = fleet_repo.get_all()
        assert len(a_trucks) == 1

        a_drivers = driver_repo.get_all()
        assert len(a_drivers) == 1

        a_invs = inv_repo.get_all()
        assert len(a_invs) == 1

        # ── Verify scoped to B sees only B ──────────────────────────
        db.user_company_id = cid_b

        b_trips = trip_repo.get_all(limit=100)
        assert len(b_trips) == 1
        assert b_trips[0]["id"] == trb


# ===================================================================
# TestInvoiceLifecycle
# ===================================================================

class TestInvoiceLifecycle:
    """Invoice CRUD and status transitions linked to trips."""

    def test_invoice_create_and_read(
        self, db: DatabaseManager, trip_repo: TripRepository
    ) -> None:
        """Create an invoice and read it back by id, number, and trip_id."""
        trip_id = trip_repo.create(_sample_trip())
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trip_id, "INV-LIFECYCLE-001", _dt(0), _dt(30), 2500.0, "Unpaid"),
        )
        db.conn.commit()
        inv = db.conn.execute(
            "SELECT id FROM invoices WHERE trip_id = ?", (trip_id,)
        ).fetchone()
        inv_id = inv["id"]

        invoice_repo = InvoiceRepository(db)
        # By id
        assert invoice_repo.get_by_id(inv_id) is not None
        # By number
        assert invoice_repo.get_by_number("INV-LIFECYCLE-001") is not None
        # By trip_id
        assert invoice_repo.get_by_trip_id(trip_id) is not None

    def test_invoice_status_transitions(
        self, db: DatabaseManager, trip_repo: TripRepository
    ) -> None:
        """Update invoice status from Unpaid → Paid."""
        trip_id = trip_repo.create(_sample_trip())
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trip_id, "INV-STATUS-001", _dt(0), _dt(30), 1500.0, "Unpaid"),
        )
        db.conn.commit()
        inv = db.conn.execute(
            "SELECT id FROM invoices WHERE trip_id = ?", (trip_id,)
        ).fetchone()
        inv_id = inv["id"]

        # Mark as paid via direct SQL (InvoiceRepository has no update method)
        db.conn.execute("UPDATE invoices SET status = ? WHERE id = ?", ("Paid", inv_id))
        db.conn.commit()

        invoice_repo = InvoiceRepository(db)
        inv_updated = invoice_repo.get_by_id(inv_id)
        assert inv_updated is not None
        assert inv_updated["status"] == "Paid"


# ===================================================================
# TestDriverAndFleetIntegration
# ===================================================================

class TestDriverAndFleetIntegration:
    """Integration between FleetRepository and DriverRepository."""

    def test_create_and_link_truck_driver_trip(
        self,
        fleet_repo: FleetRepository,
        driver_repo: DriverRepository,
        trip_repo: TripRepository,
    ) -> None:
        """Create a truck and driver, link them to a trip, verify queries."""
        truck_id = fleet_repo.create({
            "plate_number": "FLEET-001",
            "model": "FH16",
            "manufacturer": "Volvo",
            "active_status": 1,
        })
        driver_id = driver_repo.create({
            "name": "Truck Driver",
            "license_number": "LIC-12345",
            "is_active": 1,
        })

        trip_id = trip_repo.create(_sample_trip(
            truck_id=truck_id,
            driver_id=driver_id,
            truck_number="FLEET-001",
            driver_name="Truck Driver",
        ))

        # Verify queries work across repos
        trips_by_driver = trip_repo.get_by_driver_id(driver_id)
        assert len(trips_by_driver) == 1
        assert trips_by_driver[0]["id"] == trip_id

        trips_by_truck = trip_repo.get_by_truck_id(truck_id)
        assert len(trips_by_truck) == 1
        assert trips_by_truck[0]["id"] == trip_id

        truck = fleet_repo.get_by_plate("FLEET-001")
        assert truck is not None
        assert truck["id"] == truck_id


# ===================================================================
# TestClientExtendedOperations
# ===================================================================

class TestClientExtendedOperations:
    """Extended client operations: search, deactivation, dashboard data."""

    def test_client_search_and_deactivation(
        self, client_repo: ClientRepository
    ) -> None:
        """Create clients, search by name, deactivate, verify filtered out."""
        client_repo.create({"name": "Active Client", "created_at": _now()})
        client_repo.create({"name": "Inactive Client", "created_at": _now()})

        # Search (active only)
        results = client_repo.search("Client")
        active_names = {c["name"] for c in results}
        assert "Active Client" in active_names
        assert "Inactive Client" in active_names  # still active by default

        # Deactivate one
        inactive = client_repo.get_by_name("Inactive Client")
        assert inactive is not None
        client_repo.deactivate(inactive["id"])

        # Now search should only return the active one
        results = client_repo.search("Client")
        active_names = {c["name"] for c in results}
        assert "Active Client" in active_names
        assert "Inactive Client" not in active_names

    def test_client_dashboard_data(
        self,
        client_repo: ClientRepository,
        trip_repo: TripRepository,
    ) -> None:
        """Verify get_dashboard_data returns correct aggregates."""
        client_id = client_repo.create({
            "name": "Dashboard Client",
            "created_at": _now(),
        })

        # Create a few trips
        trip_repo.create(_sample_trip(
            client_id=client_id, client_name="Dashboard Client",
            status="Delivered", total_price_eur=1000, net_profit=200,
        ))
        trip_repo.create(_sample_trip(
            client_id=client_id, client_name="Dashboard Client",
            status="Delivered", total_price_eur=2000, net_profit=400,
        ))
        trip_repo.create(_sample_trip(
            client_id=client_id, client_name="Dashboard Client",
            status="Planned", total_price_eur=3000, net_profit=600,
        ))

        dash = client_repo.get_dashboard_data(client_id)
        assert dash["total_trips"] == 3
        assert dash["total_revenue"] == 6000.0  # all 3 trips
        assert dash["total_profit"] == 1200.0
        assert "delivered" in dash["status_counts"]
        assert "planned" in dash["status_counts"]
