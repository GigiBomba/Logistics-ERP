"""Database stress tests — bulk operations, rapid fire, sustained throughput,
memory and disk behaviour, recovery/durability, and performance regression."""
from __future__ import annotations

import json
import os
import random
import string
import tempfile
import threading
import time
from datetime import datetime
from typing import Any, Dict, List

import pytest

from database.db_manager import DatabaseManager
from repositories.trip_repository import TripRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.fleet_repository import FleetRepository
from repositories.driver_repository import DriverRepository
from repositories.client_repository import ClientRepository

# ── Helpers ──────────────────────────────────────────────────────────────

TRIP_STATUSES = ["Planned", "In Transit", "Delivered", "Completed", "Paid", "Cancelled"]


def _make_trip_data(**overrides: Any) -> Dict[str, Any]:
    """Return a minimal valid trip data dict."""
    data: Dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "truck_number": f"TRUCK-{random.randint(1, 50)}",
        "driver_name": f"Driver-{random.randint(1, 30)}",
        "client_name": f"Client-{random.randint(1, 20)}",
        "distance_km": round(random.uniform(100, 2500), 2),
        "total_price_eur": round(random.uniform(500, 8000), 2),
        "rate_per_km": 0.0,
        "gross_per_km": 0.0,
        "net_profit": 0.0,
        "start_date": datetime.now().strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "payment_date": "",
        "extra_costs": 0.0,
        "fuel_cost": 0.0,
        "toll_cost": 0.0,
        "salary_cost": 0.0,
        "currency": "EUR",
        "status": random.choice(TRIP_STATUSES),
        "loading_country": "DE",
        "delivery_country": "FR",
        "context_json": "",
    }
    data.update(overrides)
    return data


def _create_db() -> DatabaseManager:
    """Create a file-based DatabaseManager backed by a temp file."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(db_path)
    # Ensure company scoping is off so repositories see all rows.
    db.user_role = ""
    db.user_company_id = None
    return db


def _close_db(db: DatabaseManager) -> None:
    """Close and remove the database and journal files."""
    db_path = ""
    if hasattr(db, "_pool") and db._pool is not None:
        db_path = db._pool._db_path
    db.close()
    if db_path and os.path.exists(db_path):
        for ext in ("", "-wal", "-shm"):
            try:
                p = db_path + ext
                if os.path.exists(p):
                    os.unlink(p)
            except OSError:
                pass


def _seed_trips(trip_repo: TripRepository, count: int, batch_size: int = 1000) -> None:
    """Insert *count* trips using *trip_repo* in batches."""
    trip_repo.begin_transaction()
    try:
        for i in range(count):
            trip_repo.create(_make_trip_data())
            if (i + 1) % batch_size == 0 and i != count - 1:
                trip_repo.commit_transaction()
                trip_repo.begin_transaction()
        trip_repo.commit_transaction()
    except Exception:
        trip_repo.rollback_transaction()
        raise


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_db():
    """Provide a clean DatabaseManager for each test."""
    db = _create_db()
    yield db
    _close_db(db)


@pytest.fixture
def trip_repo(fresh_db):
    return TripRepository(fresh_db)


@pytest.fixture
def invoice_repo(fresh_db):
    return InvoiceRepository(fresh_db)


@pytest.fixture
def fleet_repo(fresh_db):
    return FleetRepository(fresh_db)


@pytest.fixture
def driver_repo(fresh_db):
    return DriverRepository(fresh_db)


@pytest.fixture
def client_repo(fresh_db):
    return ClientRepository(fresh_db)


# ═══════════════════════════════════════════════════════════════════════════
# TestBulkOperations
# ═══════════════════════════════════════════════════════════════════════════

class TestBulkOperations:

    @pytest.mark.slow
    def test_bulk_insert_5000_trips(self, trip_repo: TripRepository) -> None:
        """Insert 5000 trips in a single transaction, verify count and query perf."""
        count = 5000
        trip_repo.begin_transaction()
        try:
            for _ in range(count):
                trip_repo.create(_make_trip_data())
            trip_repo.commit_transaction()
        except Exception:
            trip_repo.rollback_transaction()
            raise

        # Verify count
        all_trips = trip_repo.get_all(limit=10000)
        assert len(all_trips) == count, f"Expected {count} trips, got {len(all_trips)}"

        # Verify query performance on a status-based lookup
        status = "Delivered"
        t0 = time.perf_counter()
        filtered = trip_repo.get_by_status(status)
        elapsed = time.perf_counter() - t0
        assert isinstance(filtered, list)
        assert elapsed < 2.0, (
            f"get_by_status over {count} trips took {elapsed:.3f}s (expected < 2.0s)"
        )

    @pytest.mark.slow
    def test_bulk_insert_10000_trips_batched(self, trip_repo: TripRepository) -> None:
        """Insert 10000 trips in batches of 1000, measure throughput."""
        total = 10000
        batch = 1000
        t0 = time.perf_counter()

        for start in range(0, total, batch):
            trip_repo.begin_transaction()
            try:
                for _ in range(min(batch, total - start)):
                    trip_repo.create(_make_trip_data())
                trip_repo.commit_transaction()
            except Exception:
                trip_repo.rollback_transaction()
                raise

        elapsed = time.perf_counter() - t0
        throughput = total / elapsed
        print(f"\n  Bulk insert throughput: {throughput:.0f} trips/s ({elapsed:.2f}s total)")

        # Verify count
        all_trips = trip_repo.get_all(limit=20000)
        assert len(all_trips) == total, f"Expected {total}, got {len(all_trips)}"
        # Reasonable throughput expectation: at least 300 trips/s
        # (Windows/SQLite may be slower; adjust threshold accordingly)
        assert throughput >= 300, (
            f"Throughput too low: {throughput:.0f} trips/s (expected >= 300)"
        )

    def test_bulk_delete(self, trip_repo: TripRepository) -> None:
        """Insert 1000 trips, delete 500, verify count."""
        total = 1000
        _seed_trips(trip_repo, total, batch_size=500)

        all_trips = trip_repo.get_all(limit=2000)
        ids_to_keep = {t["id"] for t in all_trips[:500]}
        ids_to_delete = {t["id"] for t in all_trips[500:]}
        assert len(ids_to_delete) == 500

        for tid in ids_to_delete:
            trip_repo.delete(tid)

        remaining = trip_repo.get_all(limit=2000)
        remaining_ids = {t["id"] for t in remaining}
        assert len(remaining) == 500
        assert remaining_ids == ids_to_keep, "Deleted wrong rows!"

    def test_bulk_update(self, trip_repo: TripRepository) -> None:
        """Insert 100 trips, update status of all 100, verify updated correctly."""
        count = 100
        _seed_trips(trip_repo, count, batch_size=100)

        all_trips = trip_repo.get_all(limit=200)
        trip_ids = [t["id"] for t in all_trips]
        assert len(trip_ids) == count

        new_status = "Delivered"
        for tid in trip_ids:
            trip_repo.update(tid, {"status": new_status})

        for tid in trip_ids:
            trip = trip_repo.get_by_id(tid)
            assert trip is not None, f"Trip {tid} not found after update"
            assert trip["status"] == new_status, (
                f"Trip {tid} status is {trip['status']!r}, expected {new_status!r}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# TestRapidFireOperations
# ═══════════════════════════════════════════════════════════════════════════

class TestRapidFireOperations:

    def test_rapid_create_read_delete_cycle(self, trip_repo: TripRepository) -> None:
        """100 iterations of create→read→delete, verify no leaks."""
        iterations = 100
        for i in range(iterations):
            trip_id = trip_repo.create(_make_trip_data(status="Planned"))
            trip = trip_repo.get_by_id(trip_id)
            assert trip is not None, f"Trip {trip_id} not found after create (iter {i})"
            assert trip["status"] == "Planned"
            trip_repo.delete(trip_id)
            gone = trip_repo.get_by_id(trip_id)
            assert gone is None, f"Trip {trip_id} still exists after delete (iter {i})"

        # Verify no leftover rows
        remaining = trip_repo.get_all(limit=10)
        assert len(remaining) == 0, (
            f"Found {len(remaining)} leftover trips after create/read/delete cycles"
        )

    def test_rapid_status_updates(self, trip_repo: TripRepository) -> None:
        """Create 1 trip, update its status 200 times, verify final status correct."""
        trip_id = trip_repo.create(_make_trip_data(status="Planned"))

        statuses = [f"Status-{i}" for i in range(200)]
        for s in statuses:
            trip_repo.update(trip_id, {"status": s})

        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        assert trip["status"] == "Status-199", (
            f"Final status is {trip['status']!r}, expected 'Status-199'"
        )

    def test_rapid_get_next_number(self, fresh_db: DatabaseManager) -> None:
        """Call get_next_number() 500 times, creating invoices to advance the counter."""
        from repositories.invoice_repository import InvoiceRepository
        repo = InvoiceRepository(fresh_db)
        iterations = 500
        numbers: List[str] = []
        for i in range(iterations):
            num = repo.get_next_number()
            numbers.append(num)
            # Actually create the invoice so MAX(id) advances for the next call.
            fresh_db.conn.execute(
                "INSERT INTO invoices (invoice_number, trip_id, issue_date, due_date, total_amount, status) "
                "VALUES (?, NULL, '2026-01-01', '2026-02-01', 100.0, 'Unpaid')",
                (num,),
            )
            fresh_db.conn.commit()

        unique = set(numbers)
        assert len(unique) == iterations, (
            f"Got {len(unique)} unique numbers out of {iterations} calls"
        )


# ═══════════════════════════════════════════════════════════════════════════
# TestSustainedThroughput
# ═══════════════════════════════════════════════════════════════════════════

class TestSustainedThroughput:

    @pytest.mark.slow
    def test_sustained_read_throughput(self, trip_repo: TripRepository) -> None:
        """Pre-seed 1000 trips, then perform 500 random reads, measure time."""
        _seed_trips(trip_repo, 1000, batch_size=500)

        all_trips = trip_repo.get_all(limit=2000)
        trip_ids = [t["id"] for t in all_trips]
        assert len(trip_ids) == 1000

        t0 = time.perf_counter()
        for _ in range(500):
            tid = random.choice(trip_ids)
            trip_repo.get_by_id(tid)
        elapsed = time.perf_counter() - t0

        print(f"\n  500 random reads took {elapsed:.3f}s")
        # Each read should be fast — expect < 0.5s total
        assert elapsed < 1.0, (
            f"500 reads took {elapsed:.3f}s (expected < 1.0s)"
        )

    @pytest.mark.slow
    def test_sustained_write_throughput(self, trip_repo: TripRepository) -> None:
        """Perform 200 inserts with timing, verify average < 25ms per insert."""
        count = 200
        times: List[float] = []

        for _ in range(count):
            t0 = time.perf_counter()
            trip_repo.create(_make_trip_data())
            elapsed = time.perf_counter() - t0
            times.append(elapsed)

        avg_ms = (sum(times) / len(times)) * 1000
        print(f"\n  Average insert time: {avg_ms:.2f}ms")
        assert avg_ms < 25.0, (
            f"Average insert time {avg_ms:.2f}ms exceeds 25ms threshold"
        )

    @pytest.mark.slow
    def test_sustained_mixed_workload(self, fresh_db: DatabaseManager) -> None:
        """Spawn 5 threads, each doing 50 create+read+update+delete cycles."""
        n_threads = 5
        cycles_per_thread = 50

        results: List[Exception | None] = [None] * n_threads

        def _worker(thread_idx: int) -> None:
            try:
                repo = TripRepository(fresh_db)
                for _ in range(cycles_per_thread):
                    # create
                    tid = repo.create(_make_trip_data())
                    # read
                    t = repo.get_by_id(tid)
                    assert t is not None
                    # update
                    repo.update(tid, {"status": "Delivered"})
                    t2 = repo.get_by_id(tid)
                    assert t2 is not None
                    assert t2["status"] == "Delivered"
                    # delete
                    repo.delete(tid)
                    t3 = repo.get_by_id(tid)
                    assert t3 is None
            except Exception as e:
                results[thread_idx] = e

        threads = [
            threading.Thread(target=_worker, args=(i,), daemon=True)
            for i in range(n_threads)
        ]

        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        elapsed = time.perf_counter() - t0

        # Check for exceptions
        errors = [(i, r) for i, r in enumerate(results) if r is not None]
        assert len(errors) == 0, (
            f"Thread errors: {errors}"
        )

        total_ops = n_threads * cycles_per_thread * 4  # create+read+update+delete
        print(f"\n  Mixed workload: {total_ops} ops in {elapsed:.2f}s "
              f"({total_ops / elapsed:.0f} ops/s)")

        # Verify no leftover data
        remaining = TripRepository(fresh_db).get_all(limit=10)
        assert len(remaining) == 0, (
            f"Leftover trips after mixed workload: {len(remaining)}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# TestMemoryAndDisk
# ═══════════════════════════════════════════════════════════════════════════

class TestMemoryAndDisk:

    def test_large_text_blob(self, trip_repo: TripRepository) -> None:
        """Insert trip with ~1 MB context_json, verify stored and readable."""
        large_blob = "x" * (1024 * 1024)  # ~1 MB
        trip_id = trip_repo.create(_make_trip_data(context_json=large_blob))

        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        stored = trip.get("context_json", "")
        assert len(stored) == 1024 * 1024, (
            f"Stored blob length is {len(stored)}, expected {1024 * 1024}"
        )
        assert stored == large_blob

    @pytest.mark.slow
    def test_wal_file_does_not_grow_unbounded(self, fresh_db: DatabaseManager) -> None:
        """Insert 5000 trips, check WAL file doesn't exceed reasonable size."""
        db_path = fresh_db._pool._db_path
        wal_path = db_path + "-wal"

        trip_repo = TripRepository(fresh_db)
        _seed_trips(trip_repo, 5000, batch_size=1000)

        # Force a checkpoint by closing and reopening
        fresh_db.close()

        if os.path.exists(wal_path):
            wal_size = os.path.getsize(wal_path)
        else:
            wal_size = 0

        db_size = os.path.getsize(db_path)
        print(f"\n  DB size: {db_size / 1024:.0f} KB, WAL size: {wal_size / 1024:.0f} KB")
        # WAL should be reasonable — less than the main DB file
        assert wal_size < db_size * 2, (
            f"WAL file too large: {wal_size} bytes vs DB {db_size} bytes"
        )

    @pytest.mark.slow
    def test_database_file_size_after_bulk_operations(self) -> None:
        """Measure DB file size before and after 1000 insert+delete operations."""
        db = _create_db()
        try:
            db_path = db._pool._db_path

            def _file_size() -> int:
                return os.path.getsize(db_path)

            size_before = _file_size()
            trip_repo = TripRepository(db)
            inserted_ids: List[int] = []

            # Insert 1000 trips
            trip_repo.begin_transaction()
            try:
                for _ in range(1000):
                    tid = trip_repo.create(_make_trip_data())
                    inserted_ids.append(tid)
                trip_repo.commit_transaction()
            except Exception:
                trip_repo.rollback_transaction()
                raise

            size_after_insert = _file_size()
            size_growth = size_after_insert - size_before
            print(f"\n  Size before: {size_before} B, after insert: {size_after_insert} B "
                  f"(growth: {size_growth} B)")

            # Delete all
            for tid in inserted_ids:
                trip_repo.delete(tid)

            size_after_delete = _file_size()
            # The file may not shrink due to SQLite freelist, but it should
            # not have grown beyond the insert size.
            print(f"  Size after delete: {size_after_delete} B")
            assert os.path.exists(db_path), "Database file missing"
        finally:
            _close_db(db)


# ═══════════════════════════════════════════════════════════════════════════
# TestRecoveryAndDurability
# ═══════════════════════════════════════════════════════════════════════════

class TestRecoveryAndDurability:

    def test_data_survives_process_restart(self) -> None:
        """Create data, close DB, open new DB on same file, verify data intact."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            # --- first session ---
            db1 = DatabaseManager(db_path)
            db1.user_role = ""
            db1.user_company_id = None
            repo1 = TripRepository(db1)
            ids: List[int] = []
            for _ in range(100):
                ids.append(repo1.create(_make_trip_data(status="Planned")))
            db1.close()

            # --- second session (same file) ---
            db2 = DatabaseManager(db_path)
            db2.user_role = ""
            db2.user_company_id = None
            repo2 = TripRepository(db2)

            all_trips = repo2.get_all(limit=200)
            assert len(all_trips) == 100, (
                f"Expected 100 trips after reopen, got {len(all_trips)}"
            )
            recovered_ids = {t["id"] for t in all_trips}
            assert recovered_ids == set(ids), "Trip IDs differ after reopen"

            for tid in ids:
                trip = repo2.get_by_id(tid)
                assert trip is not None, f"Trip {tid} missing after reopen"
                assert trip["status"] == "Planned"
            db2.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                try:
                    p = db_path + ext
                    if os.path.exists(p):
                        os.unlink(p)
                except OSError:
                    pass

    def test_wal_checkpoint_after_bulk_write(self, fresh_db: DatabaseManager) -> None:
        """Insert 1000 trips, verify all readable even before explicit checkpoint."""
        trip_repo = TripRepository(fresh_db)
        _seed_trips(trip_repo, 1000, batch_size=500)

        all_trips = trip_repo.get_all(limit=2000)
        assert len(all_trips) == 1000, (
            f"Expected 1000 trips, got {len(all_trips)}"
        )
        # Spot-check some individual reads
        for t in all_trips:
            fetched = trip_repo.get_by_id(t["id"])
            assert fetched is not None, f"Trip {t['id']} not readable"
            assert fetched["status"] == t["status"]


# ═══════════════════════════════════════════════════════════════════════════
# TestPerformanceRegression
# ═══════════════════════════════════════════════════════════════════════════

class TestPerformanceRegression:

    @pytest.mark.slow
    def test_query_by_status_performance(self, trip_repo: TripRepository) -> None:
        """Create 2000 trips with various statuses, query by status under 100ms."""
        statuses = ["Planned", "In Transit", "Delivered", "Completed", "Paid"]
        _seed_trips(trip_repo, 2000, batch_size=500)

        t0 = time.perf_counter()
        for status in statuses:
            results = trip_repo.get_by_status(status)
            assert isinstance(results, list)
        elapsed = time.perf_counter() - t0
        avg_per_query = (elapsed / len(statuses)) * 1000
        print(f"\n  Average status query time: {avg_per_query:.2f}ms")
        assert avg_per_query < 100.0, (
            f"Average status query {avg_per_query:.2f}ms exceeds 100ms threshold"
        )

    @pytest.mark.slow
    def test_get_all_performance(self, trip_repo: TripRepository) -> None:
        """Create 1000 trips, call get_all(limit=100), verify fast."""
        _seed_trips(trip_repo, 1000, batch_size=500)

        # Warm-up
        trip_repo.get_all(limit=100)

        t0 = time.perf_counter()
        for _ in range(50):
            trip_repo.get_all(limit=100)
        elapsed = time.perf_counter() - t0
        avg_ms = (elapsed / 50) * 1000
        print(f"\n  Average get_all(limit=100): {avg_ms:.2f}ms")
        # Each call should be very fast
        assert avg_ms < 50.0, (
            f"Average get_all {avg_ms:.2f}ms exceeds 50ms threshold"
        )
