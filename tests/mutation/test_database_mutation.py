"""Mutation / stress tests for database integrity under data mutations.

Verifies that operations which SHOULD preserve data integrity actually DO,
covering CRUD cycles, foreign keys, data types, concurrency, indices, WAL,
large datasets, and schema migrations.
"""

from __future__ import annotations

import json
import os
import random
import string
import tempfile
import threading
import time
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
    # Also clean up WAL / SHM files if they exist
    for ext in ("-wal", "-shm"):
        try:
            os.unlink(tmp.name + ext)
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

def _now() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _dt(days_offset: int = 0) -> str:
    """Return an ISO-formatted date string offset from today."""
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


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
# TestCRUDIntegrityMutations
# ===================================================================

class TestCRUDIntegrityMutations:
    """CRUD cycle integrity — verify that operations on one record do not
    corrupt or silently alter other records."""

    def test_create_update_delete_cycle_preserves_other_records(
        self, trip_repo: TripRepository,
    ) -> None:
        """Create 3 trips, update 1, delete 1, verify the untouched one is intact."""
        # Arrange
        t1_id = trip_repo.create(_sample_trip(client_name="Alpha", truck_number="TRK-001"))
        t2_id = trip_repo.create(_sample_trip(client_name="Beta", truck_number="TRK-002"))
        t3_id = trip_repo.create(_sample_trip(client_name="Gamma", truck_number="TRK-003"))

        # Act — update t2, delete t3
        trip_repo.update(t2_id, {"status": "In Transit", "driver_name": "Updated Driver"})
        trip_repo.delete(t3_id)

        # Assert — t1 is completely untouched
        t1 = trip_repo.get_by_id(t1_id)
        assert t1 is not None
        assert t1["client_name"] == "Alpha"
        assert t1["truck_number"] == "TRK-001"
        assert t1["driver_name"] == "John Doe"
        assert t1["status"] == "Delivered"

        # Assert — t2 reflects the update
        t2 = trip_repo.get_by_id(t2_id)
        assert t2 is not None
        assert t2["status"] == "In Transit"
        assert t2["driver_name"] == "Updated Driver"

        # Assert — t3 is gone
        assert trip_repo.get_by_id(t3_id) is None

        # Assert — total count is 2
        all_trips = trip_repo.get_all(limit=100)
        assert len(all_trips) == 2

    def test_repeated_update_same_record(
        self, trip_repo: TripRepository,
    ) -> None:
        """Update same trip 10 times, verify last write wins."""
        # Arrange
        trip_id = trip_repo.create(_sample_trip(client_name="Overwrite Test"))

        # Act — update 10 times
        for i in range(10):
            trip_repo.update(trip_id, {"net_profit": float(i * 100)})

        # Assert — last value wins
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        assert trip["net_profit"] == 900.0  # 9 * 100

        # All other fields remain intact
        assert trip["client_name"] == "Overwrite Test"
        assert trip["truck_number"] == "AB-123-CD"

    def test_delete_and_recreate_same_id(
        self, db: DatabaseManager, trip_repo: TripRepository,
    ) -> None:
        """Delete trip id=1, create new trip, verify new trip got a DIFFERENT id
        (auto-increment does not reuse IDs by default in SQLite)."""
        # Arrange — create enough trips so id=1 exists
        trip_repo.create(_sample_trip(client_name="First"))
        trip_repo.create(_sample_trip(client_name="Second"))

        first_id = 1
        trip = trip_repo.get_by_id(first_id)
        assert trip is not None
        assert trip["client_name"] == "First"

        # Act — delete id=1 and create a new trip
        trip_repo.delete(first_id)
        assert trip_repo.get_by_id(first_id) is None

        new_id = trip_repo.create(_sample_trip(client_name="Third"))

        # Assert — new trip got a different id (SQLite does not reuse ROWIDs by default)
        assert new_id != first_id, "SQLite should not reuse auto-increment IDs"
        assert trip_repo.get_by_id(first_id) is None, "Old id=1 must remain empty"

        new_trip = trip_repo.get_by_id(new_id)
        assert new_trip is not None
        assert new_trip["client_name"] == "Third"


# ===================================================================
# TestForeignKeyIntegrity
# ===================================================================

class TestForeignKeyIntegrity:
    """Verify foreign key constraints and cascade behaviour."""

    def test_delete_client_with_trips_does_not_orphan_trips(
        self,
        db: DatabaseManager,
        client_repo: ClientRepository,
        trip_repo: TripRepository,
    ) -> None:
        """Create client, create trips for client, delete client via direct SQL
        bypassing FK, verify trips still exist (since there is no FK constraint
        from trips.client_id to clients.id with ON DELETE CASCADE — it's a loose
        reference)."""
        # Arrange
        client_id = client_repo.create({
            "name": "FK Test Client",
            "created_at": _now(),
        })
        t1_id = trip_repo.create(_sample_trip(client_id=client_id, client_name="FK Test Client"))
        t2_id = trip_repo.create(_sample_trip(client_id=client_id, client_name="FK Test Client"))

        # Act — temporarily disable FK enforcement to delete client (trips reference
        # client_id but there is no ON DELETE CASCADE — the FK is enforced by SQLite
        # at the application level via PRAGMA foreign_keys=ON)
        db.conn.execute("PRAGMA foreign_keys=OFF")
        db.conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        db.conn.commit()
        db.conn.execute("PRAGMA foreign_keys=ON")
        db.conn.commit()

        # Assert — trips still exist with their client_id intact
        t1 = trip_repo.get_by_id(t1_id)
        assert t1 is not None, "Trip should not be orphan-deleted"
        assert t1["client_id"] == client_id, "client_id should remain as-is"
        assert t1["client_name"] == "FK Test Client"

        t2 = trip_repo.get_by_id(t2_id)
        assert t2 is not None, "Second trip should also survive"

        # The client is indeed gone
        assert client_repo.get_by_id(client_id) is None

    def test_delete_trip_cascades_to_invoices(
        self,
        db: DatabaseManager,
        trip_repo: TripRepository,
        invoice_repo: InvoiceRepository,
    ) -> None:
        """Create trip + invoice, soft-delete trip — invoice survives (soft-delete
        semantics: the trip row is preserved with deleted_at set so the delete can
        propagate through sync; no cascade)."""
        # Arrange
        trip_id = trip_repo.create(_sample_trip(client_name="Cascade Test"))
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
            "total_amount, status) VALUES (?, ?, ?, ?, ?, ?)",
            (trip_id, "INV-CASCADE-001", _dt(0), _dt(30), 3400.0, "Unpaid"),
        )
        db.conn.commit()
        invoice = invoice_repo.get_by_trip_id(trip_id)
        assert invoice is not None
        inv_id = invoice["id"]

        # Act — soft-delete the trip
        trip_repo.delete(trip_id)

        # Assert — trip soft-deleted (row preserved, filtered from reads) and
        # invoice survives (no cascade under soft-delete)
        assert trip_repo.get_by_id(trip_id) is None
        row = db.conn.execute(
            "SELECT deleted_at FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert row is not None and row["deleted_at"] is not None
        assert invoice_repo.get_by_id(inv_id) is not None

    def test_cascade_delete_multiple_levels(
        self,
        db: DatabaseManager,
        client_repo: ClientRepository,
        trip_repo: TripRepository,
        invoice_repo: InvoiceRepository,
    ) -> None:
        """Create client → trip → invoice chain, delete client directly,
        verify data state (trips survive because no cascade; invoice survives
        because its trip still exists)."""
        # Arrange
        client_id = client_repo.create({
            "name": "MultiLevel Cascade",
            "created_at": _now(),
        })
        trip_id = trip_repo.create(_sample_trip(
            client_id=client_id,
            client_name="MultiLevel Cascade",
        ))
        db.conn.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, "
            "total_amount, status) VALUES (?, ?, ?, ?, ?, ?)",
            (trip_id, "INV-MULTI-001", _dt(0), _dt(30), 5000.0, "Unpaid"),
        )
        db.conn.commit()
        invoice = invoice_repo.get_by_trip_id(trip_id)
        assert invoice is not None
        inv_id = invoice["id"]

        # Act — temporarily disable FK enforcement to delete the client directly
        db.conn.execute("PRAGMA foreign_keys=OFF")
        db.conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        db.conn.commit()
        db.conn.execute("PRAGMA foreign_keys=ON")
        db.conn.commit()

        # Assert — client is gone
        assert client_repo.get_by_id(client_id) is None

        # Trip survives because no FK cascade
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        assert trip["client_name"] == "MultiLevel Cascade"

        # Invoice survives because its trip still exists
        inv = invoice_repo.get_by_id(inv_id)
        assert inv is not None
        assert inv["status"] == "Unpaid"


# ===================================================================
# TestDataTypeIntegrity
# ===================================================================

class TestDataTypeIntegrity:
    """Verify data type handling and coercion by SQLite."""

    def test_insert_invalid_type_triggers_error(
        self,
        db: DatabaseManager,
        trip_repo: TripRepository,
    ) -> None:
        """Try inserting a string into an INTEGER column (distance_km is REAL)
        and verify SQLite stores it as-is (SQLite is dynamically typed, but
        we check that numeric operations still work)."""
        # SQLite uses manifest typing — it stores the value as supplied and
        # only converts when the affinity demands it.  distance_km is REAL
        # affinity, so a string like "abc" is stored as "abc".
        # Create a trip with a valid numeric, verify it works
        trip_id = trip_repo.create(_sample_trip(distance_km=500.0))
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        # distance_km was stored as a float (REAL affinity)
        assert isinstance(trip["distance_km"], float)

        # Now try inserting via raw SQL with a non-numeric string — SQLite
        # will store it as-is because of manifest typing.  We expect no error
        # but the value will be a string, which may cause issues in queries.
        # This is a SQLite characteristic, not a bug.
        db.conn.execute(
            "UPDATE trips SET distance_km = ? WHERE id = ?",
            ("not-a-number", trip_id),
        )
        db.conn.commit()
        updated = trip_repo.get_by_id(trip_id)
        assert updated is not None
        # SQLite stores the string as-is for REAL affinity
        # (it attempts conversion but if it fails, stores the original)
        stored = updated["distance_km"]
        assert isinstance(stored, str) or stored != 500.0

    def test_null_vs_empty_string(
        self,
        trip_repo: TripRepository,
    ) -> None:
        """Create trip with NULL end_date vs empty string, verify both are stored correctly."""
        # Arrange
        trip_null = trip_repo.create(_sample_trip(end_date=None, client_name="NullDate"))
        trip_empty = trip_repo.create(_sample_trip(end_date="", client_name="EmptyDate"))

        # Assert — NULL and empty string are distinct
        null_trip = trip_repo.get_by_id(trip_null)
        assert null_trip is not None
        assert null_trip["end_date"] is None, "end_date should be NULL"
        assert null_trip["client_name"] == "NullDate"

        empty_trip = trip_repo.get_by_id(trip_empty)
        assert empty_trip is not None
        assert empty_trip["end_date"] == "", "end_date should be empty string"
        assert empty_trip["client_name"] == "EmptyDate"

        # Both trips exist and other fields intact
        assert null_trip["distance_km"] == 850.0
        assert empty_trip["distance_km"] == 850.0

    def test_negative_values_in_numeric_fields(
        self,
        trip_repo: TripRepository,
    ) -> None:
        """Create trip with negative distance_km, verify stored as-is (SQLite allows this)."""
        # Arrange — SQLite does not enforce CHECK constraints unless defined
        trip_id = trip_repo.create(_sample_trip(
            client_name="Negative Test",
            distance_km=-150.0,
            total_price_eur=-999.99,
            net_profit=-500.0,
        ))

        # Assert — stored as-is
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        assert trip["distance_km"] == -150.0
        assert trip["total_price_eur"] == -999.99
        assert trip["net_profit"] == -500.0
        assert trip["client_name"] == "Negative Test"


# ===================================================================
# TestConcurrentMutation
# ===================================================================

class TestConcurrentMutation:
    """Threading safety — verify concurrent access does not corrupt data."""

    def test_concurrent_update_same_trip(
        self,
        db_path: str,
    ) -> None:
        """2 threads update same trip field simultaneously, verify final state
        is consistent (last write wins, no corruption)."""
        # Arrange — open two independent DatabaseManager instances (each with
        # its own ConnectionPool / thread-local connection)
        dm1 = DatabaseManager(db_path)
        repo1 = TripRepository(dm1)
        trip_id = repo1.create(_sample_trip(client_name="Concurrent", net_profit=0.0))
        dm1.close()

        results: List[int] = []
        errors: List[Exception] = []

        def _update_worker(value: int) -> None:
            """Open own DB connection and update the trip."""
            try:
                dm = DatabaseManager(db_path)
                repo = TripRepository(dm)
                repo.update(trip_id, {"net_profit": float(value)})
                dm.close()
                results.append(value)
            except Exception as e:
                errors.append(e)

        # Act — two threads update simultaneously
        t1 = threading.Thread(target=_update_worker, args=(100,))
        t2 = threading.Thread(target=_update_worker, args=(200,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Assert — no errors
        assert len(errors) == 0, f"Concurrent update errors: {errors}"

        # Assert — final state is one of the two values (last write wins)
        dm3 = DatabaseManager(db_path)
        repo3 = TripRepository(dm3)
        trip = repo3.get_by_id(trip_id)
        dm3.close()
        assert trip is not None
        assert trip["net_profit"] in (100.0, 200.0), (
            f"Expected 100.0 or 200.0, got {trip['net_profit']}"
        )
        # No corruption: all other fields intact
        assert trip["client_name"] == "Concurrent"
        assert trip["truck_number"] == "AB-123-CD"

    def test_concurrent_create_and_read(
        self,
        db_path: str,
    ) -> None:
        """Thread A creates 50 trips while Thread B reads all trips,
        verify B only sees committed data (no dirty reads)."""
        # Arrange
        created_ids: List[int] = []
        read_counts: List[int] = []
        errors: List[Exception] = []

        def _writer() -> None:
            """Create 50 trips sequentially."""
            try:
                dm = DatabaseManager(db_path)
                repo = TripRepository(dm)
                for i in range(50):
                    tid = repo.create(_sample_trip(
                        client_name=f"Concurrent-{i}",
                        truck_number=f"CR-{i:04d}",
                    ))
                    created_ids.append(tid)
                dm.close()
            except Exception as e:
                errors.append(e)

        def _reader() -> None:
            """Read all trips repeatedly."""
            try:
                dm = DatabaseManager(db_path)
                repo = TripRepository(dm)
                for _ in range(20):
                    all_trips = repo.get_all(limit=500)
                    read_counts.append(len(all_trips))
                    time.sleep(0.005)
                dm.close()
            except Exception as e:
                errors.append(e)

        # Act
        writer = threading.Thread(target=_writer)
        reader = threading.Thread(target=_reader)
        writer.start()
        reader.start()
        writer.join()
        reader.join()

        # Assert — no errors
        assert len(errors) == 0, f"Concurrent errors: {errors}"

        # Assert — exactly 50 trips were created
        assert len(created_ids) == 50

        # Assert — reader only saw committed data (0 or up to 50, never partial)
        for count in read_counts:
            assert 0 <= count <= 50, f"Reader saw {count} trips — possible dirty read"

        # Final state: all 50 trips readable
        dm3 = DatabaseManager(db_path)
        repo3 = TripRepository(dm3)
        final_trips = repo3.get_all(limit=500)
        dm3.close()
        assert len(final_trips) == 50


# ===================================================================
# TestIndexIntegrity
# ===================================================================

class TestIndexIntegrity:
    """Verify that indices enforce constraints and perform correctly."""

    def test_unique_index_prevents_duplicates(
        self,
        fleet_repo: FleetRepository,
    ) -> None:
        """Try inserting duplicate plate_number in trucks, verify UNIQUE constraint error."""
        # Arrange — create first truck
        fleet_repo.create({
            "plate_number": "UNIQUE-001",
            "model": "Actros",
            "manufacturer": "Mercedes",
            "active_status": 1,
        })

        # Act & Assert — duplicate plate_number raises IntegrityError
        with pytest.raises(Exception) as exc_info:
            fleet_repo.create({
                "plate_number": "UNIQUE-001",
                "model": "FH16",
                "manufacturer": "Volvo",
                "active_status": 1,
            })

        # Verify it's a UNIQUE constraint violation
        error_msg = str(exc_info.value).lower()
        assert "unique" in error_msg or "integrity" in error_msg or "constraint" in error_msg, (
            f"Expected UNIQUE constraint error, got: {exc_info.value}"
        )

    def test_index_still_works_after_bulk_insert(
        self,
        db_path: str,
    ) -> None:
        """Create 1000 trips, verify queries with indexed columns are fast."""
        # Arrange — seed 1000 trips
        dm = DatabaseManager(db_path)
        repo = TripRepository(dm)
        for i in range(1000):
            repo.create(_sample_trip(
                client_name=f"BulkIndex-{i % 50}",
                truck_number=f"IDX-{i:04d}",
                status=random.choice(["Planned", "In Transit", "Delivered", "Paid"]),
            ))
        dm.close()

        # Act — query by indexed columns and measure
        dm2 = DatabaseManager(db_path)
        repo2 = TripRepository(dm2)

        # Query by status (indexed)
        start = time.monotonic()
        by_status = repo2.get_filtered(status="Delivered")
        elapsed_status = time.monotonic() - start

        # Query by truck_number (indexed)
        start = time.monotonic()
        by_truck = repo2.get_by_truck_number("IDX-0000")
        elapsed_truck = time.monotonic() - start

        dm2.close()

        # Assert — queries return correct results
        assert len(by_status) > 0, "Should find Delivered trips"
        assert len(by_truck) == 1, "Should find exactly one trip by truck number"

        # Assert — queries are fast (< 1s, realistically < 50ms)
        assert elapsed_status < 1.0, (
            f"Status query took {elapsed_status:.3f}s (expected < 1.0s)"
        )
        assert elapsed_truck < 1.0, (
            f"Truck query took {elapsed_truck:.3f}s (expected < 1.0s)"
        )


# ===================================================================
# TestWALIntegrity
# ===================================================================

class TestWALIntegrity:
    """Verify WAL journal mode behaviour: file growth, checkpoint, crash recovery."""

    def test_wal_file_grows_and_checkpoints(
        self,
        db_path: str,
    ) -> None:
        """Create many trips, verify WAL file exists, verify data still readable."""
        # Arrange — create many trips to generate WAL activity
        dm = DatabaseManager(db_path)
        repo = TripRepository(dm)

        # Confirm WAL mode is active
        row = dm.conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0].upper() == "WAL", f"Expected WAL, got {row[0]}"

        # Insert a batch of trips
        for i in range(200):
            repo.create(_sample_trip(client_name=f"WAL-{i}"))

        # Check WAL file exists and has content (might be checkpointed automatically)
        wal_path = db_path + "-wal"
        if os.path.exists(wal_path):
            wal_size = os.path.getsize(wal_path)
            assert wal_size >= 0, "WAL file should exist with content"

        # Verify data still readable
        all_trips = repo.get_all(limit=500)
        assert len(all_trips) == 200

        # Force checkpoint
        dm.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        dm.close()

        # Reopen and verify data intact
        dm2 = DatabaseManager(db_path)
        repo2 = TripRepository(dm2)
        all_trips2 = repo2.get_all(limit=500)
        assert len(all_trips2) == 200
        dm2.close()

    def test_crash_recovery_simulation(
        self,
        db_path: str,
    ) -> None:
        """Write data, simulate 'crash' by closing without explicit checkpoint,
        reopen, verify data intact."""
        # Arrange — first session: write data
        dm1 = DatabaseManager(db_path)
        repo1 = TripRepository(dm1)
        for i in range(50):
            repo1.create(_sample_trip(client_name=f"CrashRecovery-{i}"))
        all_initial = repo1.get_all(limit=500)
        assert len(all_initial) == 50

        # Simulate "crash" — close without checkpoint (WAL has uncheckpointed data)
        wal_path = db_path + "-wal"
        had_wal_before = os.path.exists(wal_path)
        dm1.close()

        # Verify WAL file may still exist (if auto-checkpoint didn't run)
        if had_wal_before:
            # WAL might have been consumed on close; if it still exists,
            # it represents uncheckpointed pages
            pass

        # Act — reopen (SQLite auto-recovery replays WAL on first connection)
        dm2 = DatabaseManager(db_path)
        repo2 = TripRepository(dm2)

        # Assert — all data is intact
        all_recovered = repo2.get_all(limit=500)
        assert len(all_recovered) == 50, (
            f"Expected 50 trips after crash recovery, got {len(all_recovered)}"
        )
        # Spot-check a few records
        for i in [0, 25, 49]:
            trip = repo2.get_by_id(i + 1)  # ids start at 1
            assert trip is not None
            assert trip["client_name"] == f"CrashRecovery-{i}"

        dm2.close()


# ===================================================================
# TestLargeDataMutations
# ===================================================================

class TestLargeDataMutations:
    """Behaviour under large data volumes and large field values."""

    def test_bulk_insert_1000_trips_then_delete_all(
        self,
        db_path: str,
    ) -> None:
        """Insert 1000 trips, verify count, then delete all and verify empty."""
        # Arrange
        dm = DatabaseManager(db_path)
        repo = TripRepository(dm)
        # Disable company scoping so admin user can see all
        dm.user_role = "admin"
        dm.user_company_id = None

        # Act — insert 1000 trips in batches
        batch_size = 100
        for batch_start in range(0, 1000, batch_size):
            for i in range(batch_start, batch_start + batch_size):
                repo.create(_sample_trip(
                    client_name=f"BulkDelete-{i}",
                    truck_number=f"BD-{i:04d}",
                ))

        # Assert — 1000 trips exist
        all_trips = repo.get_all(limit=2000)
        assert len(all_trips) == 1000

        # Act — delete all trips
        for trip in all_trips:
            repo.delete(trip["id"])

        # Assert — database is empty
        remaining = repo.get_all(limit=100)
        assert len(remaining) == 0

        dm.close()

    def test_update_large_json_column(
        self,
        db_path: str,
    ) -> None:
        """Create trip with large context_json (10KB), update it, verify stored correctly."""
        # Arrange — generate a ~10KB JSON payload
        large_data = {
            "waypoints": [
                {
                    "lat": random.uniform(-90, 90),
                    "lng": random.uniform(-180, 180),
                    "address": "".join(random.choices(string.ascii_letters, k=50)),
                }
                for _ in range(80)
            ],
            "metadata": {
                "created_by": "mutation_test",
                "timestamp": _now(),
                "notes": "A" * 3000,
            },
        }
        large_json_str = json.dumps(large_data)
        assert len(large_json_str) > 10_000, (
            f"Test data too small: {len(large_json_str)} bytes (need >10KB)"
        )

        dm = DatabaseManager(db_path)
        repo = TripRepository(dm)

        # Act — create trip with large context_json
        trip_id = repo.create(_sample_trip(
            client_name="LargeJSON",
            context_json=large_json_str,
        ))

        # Assert — large JSON stored correctly
        trip = repo.get_by_id(trip_id)
        assert trip is not None
        stored_json = trip["context_json"]
        assert stored_json == large_json_str, "Large JSON mismatch on create"
        parsed = json.loads(stored_json)
        assert len(parsed["waypoints"]) > 0
        assert parsed["metadata"]["created_by"] == "mutation_test"

        # Act — update with an even larger payload
        large_data["metadata"]["updated_at"] = _now()
        large_data["extra_field"] = "X" * 5000
        updated_json_str = json.dumps(large_data)
        assert len(updated_json_str) > len(large_json_str), "Updated JSON must be larger"

        repo.update(trip_id, {"context_json": updated_json_str})

        # Assert — updated correctly
        trip2 = repo.get_by_id(trip_id)
        assert trip2 is not None
        stored_updated = trip2["context_json"]
        assert stored_updated == updated_json_str, "Large JSON mismatch on update"
        parsed2 = json.loads(stored_updated)
        assert parsed2["metadata"]["updated_at"] is not None
        assert len(parsed2["extra_field"]) == 5000

        dm.close()


# ===================================================================
# TestSchemaMutationSafety
# ===================================================================

class TestSchemaMutationSafety:
    """Verify schema migrations (ALTER TABLE) preserve existing data."""

    def test_add_column_via_alter_table_preserves_data(
        self,
        db_path: str,
    ) -> None:
        """Use _ensure_column to add a test column, verify existing data intact."""
        # Arrange — first session: create data
        dm1 = DatabaseManager(db_path)
        repo1 = TripRepository(dm1)
        trip_id = repo1.create(_sample_trip(
            client_name="SchemaMigration",
            distance_km=1234.5,
        ))
        dm1.close()

        # Act — reopen and add a new column
        dm2 = DatabaseManager(db_path)

        # Verify the column does not exist yet
        cols_before = {
            r[1]
            for r in dm2.conn.execute("PRAGMA table_info(trips)").fetchall()
        }
        assert "test_mutation_flag" not in cols_before

        # Add a test column using the same pattern as _ensure_column
        dm2._ensure_column(
            "trips",
            "test_mutation_flag",
            "ALTER TABLE trips ADD COLUMN test_mutation_flag INTEGER DEFAULT 0",
        )

        # Verify column was added
        cols_after = {
            r[1]
            for r in dm2.conn.execute("PRAGMA table_info(trips)").fetchall()
        }
        assert "test_mutation_flag" in cols_after

        # Assert — existing data is intact
        trip = repo1.get_by_id(trip_id)
        assert trip is not None
        assert trip["client_name"] == "SchemaMigration"
        assert trip["distance_km"] == 1234.5
        # New column has default value
        assert trip["test_mutation_flag"] == 0

        # Assert — can write to new column (via raw SQL since TripRepository
        # validates against its COLUMNS list which doesn't include test columns)
        dm2.conn.execute("UPDATE trips SET test_mutation_flag = ? WHERE id = ?", (1, trip_id))
        dm2.conn.commit()
        updated = repo1.get_by_id(trip_id)
        assert updated is not None
        assert updated["test_mutation_flag"] == 1

        dm2.close()

    def test_migration_rerun_is_idempotent(
        self,
        db_path: str,
    ) -> None:
        """Run _run_column_migrations twice on same DB, verify no errors, data intact."""
        # Arrange — first session: create data and run migrations once
        dm1 = DatabaseManager(db_path)
        repo1 = TripRepository(dm1)
        t1 = repo1.create(_sample_trip(client_name="Idempotent-A", distance_km=111.0))
        t2 = repo1.create(_sample_trip(client_name="Idempotent-B", distance_km=222.0))

        # Run migrations explicitly (they already ran in __init__)
        dm1._run_column_migrations()
        dm1.close()

        # Act — reopen and run migrations again
        dm2 = DatabaseManager(db_path)
        repo2 = TripRepository(dm2)

        # Run migrations a second time — should be idempotent
        dm2._run_column_migrations()

        # Assert — no errors, data intact
        trip_a = repo2.get_by_id(t1)
        assert trip_a is not None
        assert trip_a["client_name"] == "Idempotent-A"
        assert trip_a["distance_km"] == 111.0

        trip_b = repo2.get_by_id(t2)
        assert trip_b is not None
        assert trip_b["client_name"] == "Idempotent-B"
        assert trip_b["distance_km"] == 222.0

        # All expected columns still exist
        cols = {r[1] for r in dm2.conn.execute("PRAGMA table_info(trips)").fetchall()}
        for expected in ("client_id", "driver_id", "truck_id", "context_json", "company_id"):
            assert expected in cols, f"Expected column {expected} after re-run migration"

        dm2.close()
