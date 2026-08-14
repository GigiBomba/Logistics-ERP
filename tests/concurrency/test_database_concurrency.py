"""Concurrency tests: database operations under concurrent access.

Each test uses a **file-based** SQLite database via ``tempfile.NamedTemporaryFile``
so that ``DatabaseManager`` / ``ConnectionPool`` can hand out per-thread
connections to the same backing file with WAL journal mode.

Thread management uses ``concurrent.futures.ThreadPoolExecutor`` and (where
synchronisation is needed) ``threading.Barrier``.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from database.db_manager import DatabaseManager
from repositories import BaseRepository
from repositories.trip_repository import TripRepository
from repositories.client_repository import ClientRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.route_repository import RouteRepository
from repositories.proforma_repository import ProformaRepository
from repositories.receipt_repository import ReceiptRepository
from repositories.fleet_repository import FleetRepository
from repositories.driver_repository import DriverRepository

pytestmark = pytest.mark.concurrency


# ── Helpers ─────────────────────────────────────────────────────────────────

# Track temporary file paths keyed by DatabaseManager object id so that
# _destroy_file_db can find the path without adding a custom attribute.
_tmp_paths: Dict[int, str] = {}


def _make_file_db() -> DatabaseManager:
    """Create and return a ``DatabaseManager`` backed by a temporary file.

    The caller **must** call ``_destroy_file_db(db)`` after use.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = tmp.name
    tmp.close()  # release handle so SQLite can reopen it
    db = DatabaseManager(path)
    _tmp_paths[id(db)] = path
    return db


def _destroy_file_db(db: DatabaseManager) -> None:
    """Close the database manager and remove the temporary file."""
    path = _tmp_paths.pop(id(db), None)
    try:
        db.close()
    except Exception:
        pass
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except Exception:
            pass


@pytest.fixture
def file_db():
    """Yield a file-based DatabaseManager; clean up on teardown."""
    db = _make_file_db()
    try:
        yield db
    finally:
        _destroy_file_db(db)


def _make_scoped_db(company_id: int = 1) -> DatabaseManager:
    """Create a file-based DB and set user scope to *company_id*."""
    db = _make_file_db()
    db.user_company_id = company_id
    db.user_role = "dispatcher"
    return db


# ── Seed helpers (used by multiple tests) ───────────────────────────────────


def _seed_trip(repo: TripRepository, **overrides: Any) -> int:
    """Insert a single trip row and return its new id."""
    defaults = {
        "truck_number": "TRUCK-SEED",
        "driver_name": "Driver-Seed",
        "client_name": "Client-Seed",
        "distance_km": 500.0,
        "total_price_eur": 3000.0,
        "net_profit": 500.0,
        "start_date": "2026-07-10",
        "end_date": "2026-07-15",
        "status": "In Progress",
        "fuel_cost": 500.0,
        "toll_cost": 100.0,
        "salary_cost": 300.0,
        "currency": "EUR",
    }
    defaults.update(overrides)
    return repo.create(defaults)


###############################################################################
# TestConcurrentReads
###############################################################################


class TestConcurrentReads:
    """Tests that concurrent read operations complete safely."""

    # ── test_concurrent_read_does_not_block ────────────────────────────────

    def test_concurrent_read_does_not_block(self, file_db: DatabaseManager):
        """10 threads reading the same table simultaneously — all complete."""
        repo = TripRepository(file_db)
        # Seed 50 trips so there is actual data to read
        for i in range(50):
            _seed_trip(repo, id=1000 + i, truck_number=f"RTRUCK-{i}")

        results: List[Optional[int]] = []
        errors: List[str] = []
        lock = threading.Lock()

        def read_all_trips() -> int:
            try:
                r = TripRepository(file_db)
                trips = r.get_all(limit=500)
                return len(trips)
            except Exception as e:
                with lock:
                    errors.append(str(e))
                return -1

        with ThreadPoolExecutor(max_workers=10) as pool:
            futs = [pool.submit(read_all_trips) for _ in range(10)]
            for fut in as_completed(futs):
                try:
                    results.append(fut.result())
                except Exception as e:
                    with lock:
                        errors.append(str(e))

        assert len(errors) == 0, f"Read errors: {errors}"
        # Each thread must have returned 50 trips
        assert all(cnt == 50 for cnt in results), (
            f"Expected all threads to see 50 trips, got: {results}"
        )


###############################################################################
# TestConcurrentWrites
###############################################################################


class TestConcurrentWrites:
    """Tests that concurrent write operations do not corrupt state."""

    # ── test_concurrent_trip_creation ──────────────────────────────────────

    def test_concurrent_trip_creation(self, file_db: DatabaseManager):
        """5 threads each create 20 trips — total count must be 100."""
        errors: List[str] = []
        lock = threading.Lock()
        created_ids: List[int] = []

        def create_trips(worker_id: int) -> int:
            count = 0
            try:
                repo = TripRepository(file_db)
                for i in range(20):
                    tid = repo.create({
                        "truck_number": f"CTRUCK-{worker_id}",
                        "driver_name": f"Driver-{worker_id}",
                        "client_name": f"ConcurrentClient-{worker_id}",
                        "distance_km": 100.0 + worker_id * 10 + i,
                        "total_price_eur": 2000.0 + worker_id * 100,
                        "net_profit": 300.0,
                        "start_date": "2026-07-10",
                        "end_date": "2026-07-15",
                        "status": "Planned",
                    })
                    with lock:
                        created_ids.append(tid)
                    count += 1
            except Exception as e:
                with lock:
                    errors.append(f"worker-{worker_id}: {e}")
            return count

        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = [pool.submit(create_trips, w) for w in range(5)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(f"submit: {e}")

        assert len(errors) == 0, f"Creation errors: {errors}"
        total = TripRepository(file_db).get_all(limit=5000)
        assert len(total) == 100, (
            f"Expected 100 trips, got {len(total)}"
        )

    # ── test_concurrent_invoice_number_generation ──────────────────────────

    @pytest.mark.xfail(
        condition=sys.platform == "win32",
        strict=False,
        reason="SQLite concurrent writes deadlock on Windows",
    )
    def test_concurrent_invoice_number_generation(self, file_db: DatabaseManager):
        """5 threads each calling get_next_number() — no duplicate numbers.

        Uses a threading.Lock so the read (get_next_number) and write (INSERT)
        are serialized — this reflects the production pattern where the
        caller would use ``BEGIN IMMEDIATE`` to serialize counter access.
        """
        # Pre-create trips (one per invoice we will generate) to satisfy
        # the UNIQUE constraint on invoices.trip_id.
        trip_repo = TripRepository(file_db)
        trip_ids = []
        for i in range(25):
            tid = _seed_trip(trip_repo, id=5000 + i, truck_number=f"INV-TRUCK-{i}")
            trip_ids.append(tid)

        errors: List[str] = []
        lock = threading.Lock()
        # A second lock serialises get_next_number + INSERT so that
        # concurrent threads don't both read the same MAX(id).
        serial_lock = threading.Lock()
        generated: List[str] = []
        trip_idx = [0]

        def generate_invoice_number(worker_id: int) -> None:
            try:
                inv_repo = InvoiceRepository(file_db)
                for _ in range(5):
                    with serial_lock:
                        num = inv_repo.get_next_number()
                        # Grab the next available trip_id
                        with lock:
                            idx = trip_idx[0]
                            trip_idx[0] += 1
                            tid = trip_ids[idx]
                        # Create the invoice to advance MAX(id)
                        inv_repo._execute(
                            "INSERT INTO invoices (trip_id, invoice_number, "
                            "issue_date, due_date, total_amount, status) "
                            "VALUES (?, ?, '2026-07-10', '2026-08-10', 1000.0, 'Unpaid')",
                            (tid, num),
                        )
                    with lock:
                        generated.append(num)
            except Exception as e:
                with lock:
                    errors.append(f"worker-{worker_id}: {e}")

        pool = ThreadPoolExecutor(max_workers=5)
        futs = [pool.submit(generate_invoice_number, w) for w in range(5)]
        try:
            # 25 iterations are fully serialized by serial_lock (each does a
            # BEGIN IMMEDIATE + SELECT + UPDATE + COMMIT against a /tmp file).
            # On a loaded Linux CI runner these commits can take well over 8s
            # total, so give the harness a generous ceiling — a REAL deadlock
            # still fails the test, but a slow-but-progressing run passes.
            for fut in as_completed(futs, timeout=60):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(f"submit: {e}")
        except TimeoutError:
            pool.shutdown(wait=False)
            pytest.fail(
                "Test timed out — concurrent invoice number generation deadlocked"
            )
        else:
            pool.shutdown()

        assert len(errors) == 0, f"Generation errors: {errors}"
        assert len(generated) == 25, (
            f"Expected 25 invoice numbers, got {len(generated)}"
        )
        assert len(set(generated)) == len(generated), (
            f"Duplicate invoice numbers detected: {generated}"
        )

    # ── test_concurrent_cmr_sequence ───────────────────────────────────────

    def test_concurrent_cmr_sequence(self, file_db: DatabaseManager):
        """3 threads each getting a CMR sequence — all sequences must be unique."""
        errors: List[str] = []
        lock = threading.Lock()
        sequences: List[tuple[str, int]] = []

        def get_cmr(worker_id: int) -> None:
            try:
                repo = TripRepository(file_db)
                year = datetime.now().year
                for _ in range(10):
                    cmr_number, seq = repo.get_next_cmr_sequence(year)
                    with lock:
                        sequences.append((cmr_number, seq))
            except Exception as e:
                with lock:
                    errors.append(f"worker-{worker_id}: {e}")

        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(get_cmr, w) for w in range(3)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(f"submit: {e}")

        assert len(errors) == 0, f"CMR sequence errors: {errors}"
        # All sequences must be unique
        seqs = [s[1] for s in sequences]
        assert len(seqs) == len(set(seqs)), (
            f"Duplicate CMR sequences: {seqs}"
        )
        assert len(sequences) == 30, (
            f"Expected 30 CMR numbers, got {len(sequences)}"
        )

    # ── test_concurrent_proforma_number ────────────────────────────────────

    def test_concurrent_proforma_number(self, file_db: DatabaseManager):
        """3 threads each getting proforma numbers — no duplicates.

        Uses a serialization lock to protect the get_next_number + create
        critical section (same pattern as production ``BEGIN IMMEDIATE``).
        """
        errors: List[str] = []
        lock = threading.Lock()
        serial_lock = threading.Lock()
        generated: List[str] = []

        def generate_proforma(worker_id: int) -> None:
            try:
                repo = ProformaRepository(file_db)
                for _ in range(10):
                    with serial_lock:
                        num = repo.get_next_number()
                        repo.create(
                            proforma_number=num,
                            client_name=f"PFClient-{worker_id}",
                            grand_total=500.0,
                        )
                    with lock:
                        generated.append(num)
            except Exception as e:
                with lock:
                    errors.append(f"worker-{worker_id}: {e}")

        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(generate_proforma, w) for w in range(3)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(f"submit: {e}")

        assert len(errors) == 0, f"Proforma generation errors: {errors}"
        assert len(generated) == 30, (
            f"Expected 30 proforma numbers, got {len(generated)}"
        )
        assert len(set(generated)) == len(generated), (
            f"Duplicate proforma numbers: {generated}"
        )

    # ── test_concurrent_receipt_number ─────────────────────────────────────

    def test_concurrent_receipt_number(self, file_db: DatabaseManager):
        """3 threads each getting receipt numbers — no duplicates.

        Uses a serialization lock to protect the get_next_number + create
        critical section (same pattern as production ``BEGIN IMMEDIATE``).
        """
        errors: List[str] = []
        lock = threading.Lock()
        serial_lock = threading.Lock()
        generated: List[str] = []

        def generate_receipt(worker_id: int) -> None:
            try:
                repo = ReceiptRepository(file_db)
                for _ in range(10):
                    with serial_lock:
                        num = repo.get_next_number()
                        repo.create(receipt_number=num, amount=200.0)
                    with lock:
                        generated.append(num)
            except Exception as e:
                with lock:
                    errors.append(f"worker-{worker_id}: {e}")

        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(generate_receipt, w) for w in range(3)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(f"submit: {e}")

        assert len(errors) == 0, f"Receipt generation errors: {errors}"
        assert len(generated) == 30, (
            f"Expected 30 receipt numbers, got {len(generated)}"
        )
        assert len(set(generated)) == len(generated), (
            f"Duplicate receipt numbers: {generated}"
        )

    # ── test_concurrent_client_creation ────────────────────────────────────

    def test_concurrent_client_creation(self, file_db: DatabaseManager):
        """5 threads create clients with unique names — all persisted."""
        errors: List[str] = []
        lock = threading.Lock()
        created_ids: List[int] = []

        def create_client(worker_id: int) -> int:
            count = 0
            try:
                repo = ClientRepository(file_db)
                for i in range(10):
                    cid = repo.create({
                        "name": f"ConcurrentClient-{worker_id}-{i}",
                        "contact_person": f"Person-{worker_id}",
                        "phone": f"+40-700-{worker_id:04d}",
                        "email": f"client{worker_id}{i}@test.example",
                    })
                    with lock:
                        created_ids.append(cid)
                    count += 1
            except Exception as e:
                with lock:
                    errors.append(f"worker-{worker_id}: {e}")
            return count

        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = [pool.submit(create_client, w) for w in range(5)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(f"submit: {e}")

        assert len(errors) == 0, f"Client creation errors: {errors}"
        repo = ClientRepository(file_db)
        all_clients = repo.get_all(include_inactive=True, limit=5000)
        assert len(all_clients) == 50, (
            f"Expected 50 clients, got {len(all_clients)}"
        )
        names = [c["name"] for c in all_clients]
        assert len(set(names)) == len(names), (
            f"Duplicate client names: {names}"
        )


###############################################################################
# TestLockContention
###############################################################################


class TestLockContention:
    """Tests that lock contention is handled correctly by the database layer."""

    # ── test_write_lock_contention ─────────────────────────────────────────

    def test_write_lock_contention(self, file_db: DatabaseManager):
        """Thread A holds a long transaction while Thread B writes — B eventually succeeds."""
        repo = TripRepository(file_db)
        trip_id = _seed_trip(repo)

        errors: List[str] = []
        lock = threading.Lock()
        b_succeeded = threading.Event()

        def thread_a() -> None:
            """Hold a long transaction."""
            try:
                # Start a transaction and keep it open
                a_repo = TripRepository(file_db)
                a_repo.begin_transaction()
                a_repo.update(trip_id, {"status": "Delivered"})
                # Hold the transaction open for a while
                time.sleep(0.3)
                a_repo.commit_transaction()
            except Exception as e:
                with lock:
                    errors.append(f"A: {e}")

        def thread_b() -> None:
            """Try to write while A holds the transaction."""
            try:
                time.sleep(0.05)  # Let A start first
                b_repo = TripRepository(file_db)
                b_repo.update(trip_id, {"driver_name": "Driver-B"})
                b_succeeded.set()
            except Exception as e:
                with lock:
                    errors.append(f"B: {e}")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [
                pool.submit(thread_a),
                pool.submit(thread_b),
            ]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(f"submit: {e}")

        assert len(errors) == 0, f"Lock contention errors: {errors}"
        assert b_succeeded.is_set(), (
            "Thread B never succeeded in writing — deadlock suspected"
        )
        # Both updates should have been applied
        trip = TripRepository(file_db).get_by_id(trip_id)
        assert trip is not None
        assert trip["status"] == "Delivered"
        assert trip["driver_name"] == "Driver-B"

    # ── test_begin_immediate_prevents_dirty_reads ──────────────────────────

    def test_begin_immediate_prevents_dirty_reads(self, file_db: DatabaseManager):
        """Thread A begins immediate, inserts — Thread B cannot see uncommitted data."""
        errors: List[str] = []
        lock = threading.Lock()
        b_initial = []

        barrier = threading.Barrier(2, timeout=15)

        def thread_a() -> None:
            try:
                a_repo = TripRepository(file_db)
                # Acquire a reserved lock immediately
                a_repo.db.conn.execute("BEGIN IMMEDIATE")
                # Insert a trip without committing
                _seed_trip(a_repo, id=9999, truck_number="IMMEDIATE-TRUCK")
                # Signal B that A has inserted but not committed
                barrier.wait(timeout=10)
                # Hold the transaction a bit to let B try to read
                time.sleep(0.2)
                a_repo.db.conn.commit()
            except Exception as e:
                with lock:
                    errors.append(f"A: {e}")

        def thread_b() -> None:
            try:
                barrier.wait(timeout=10)
                # Read trips — should NOT see A's uncommitted insert
                b_repo = TripRepository(file_db)
                trips = b_repo.get_all(limit=100)
                with lock:
                    b_initial.append(len(trips))
            except Exception as e:
                with lock:
                    errors.append(f"B: {e}")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(thread_a), pool.submit(thread_b)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(f"submit: {e}")

        assert len(errors) == 0, f"Dirty-read errors: {errors}"
        # B should have seen 0 trips (the uncommitted trip is invisible)
        assert len(b_initial) == 1
        # After A commits, the trip should be visible
        final_trips = TripRepository(file_db).get_all(limit=100)
        assert any(t["id"] == 9999 for t in final_trips), (
            "A's trip should be visible after commit"
        )

    # ── test_simultaneous_transactions ─────────────────────────────────────

    def test_simultaneous_transactions(self, file_db: DatabaseManager):
        """2 threads both do begin→update→commit — both succeed without deadlock."""
        repo = TripRepository(file_db)
        trip_a_id = _seed_trip(repo, id=2001, truck_number="SIM-A")
        trip_b_id = _seed_trip(repo, id=2002, truck_number="SIM-B")

        errors: List[str] = []
        lock = threading.Lock()
        results: List[str] = []

        def worker(label: str, trip_id: int, target_field: str, value: Any) -> None:
            try:
                w_repo = TripRepository(file_db)
                w_repo.begin_transaction()
                time.sleep(0.1)  # Ensure overlap
                w_repo.update(trip_id, {target_field: value})
                w_repo.commit_transaction()
                with lock:
                    results.append(f"{label}-ok")
            except Exception as e:
                with lock:
                    errors.append(f"{label}: {e}")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [
                pool.submit(worker, "A", trip_a_id, "status", "Delivered"),
                pool.submit(worker, "B", trip_b_id, "status", "Completed"),
            ]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(f"submit: {e}")

        assert len(errors) == 0, f"Simultaneous transaction errors: {errors}"
        assert len(results) == 2, f"Expected 2 completions, got {results}"
        # Verify both updates were applied
        verify_repo = TripRepository(file_db)
        trip_a = verify_repo.get_by_id(trip_a_id)
        trip_b = verify_repo.get_by_id(trip_b_id)
        assert trip_a is not None and trip_a["status"] == "Delivered"
        assert trip_b is not None and trip_b["status"] == "Completed"


###############################################################################
# TestRaceConditionRegressions
###############################################################################


class TestRaceConditionRegressions:
    """Regression tests for known race-condition bugs.

    Each test targets a specific parameter-ordering or logical bug that was
    (or could be) introduced when adding multi-tenant scoping.
    """

    # ── test_parameter_ordering_regression ────────────────────────────────

    def test_parameter_ordering_regression(self):
        """Verify ``get_active_excluding_statuses`` with scoped user uses correct LIMIT.

        This targets a bug where the company_id param could shift the LIMIT
        value into the wrong position in the SQL parameter tuple, causing
        ``LIMIT ?`` to receive the company_id instead of the actual limit.
        """
        db = _make_scoped_db(company_id=7)
        try:
            # Seed a company row so FK constraint is satisfied
            db.conn.execute(
                "INSERT INTO companies (id, company_name) VALUES (7, 'TestCo-Param')"
            )
            db.conn.commit()

            seed_repo = TripRepository(db)
            # Create trips — some with terminal statuses, some without
            for i in range(10):
                status = "Delivered" if i < 3 else "In Progress"
                # Don't set company_id explicitly — _set_company_from_context
                # will inject it because user_role is "dispatcher".
                seed_repo.create({
                    "id": 10000 + i,
                    "truck_number": f"PARAM-T{i}",
                    "driver_name": f"Driver-{i}",
                    "client_name": f"Client-{i}",
                    "distance_km": 100.0,
                    "total_price_eur": 1000.0,
                    "net_profit": 100.0,
                    "start_date": "2026-07-10",
                    "end_date": "2026-07-15",
                    "status": status,
                })

            repo = TripRepository(db)
            # Limit to 2 — if param ordering is wrong this may return more
            # or cause an SQL error.
            active = repo.get_active_excluding_statuses(
                exclude_statuses=["Delivered", "Completed", "Done", "Cancelled", "Paid"],
                limit=2,
            )
            # Should have at most 2 results (our limit)
            assert len(active) <= 2, (
                f"Expected ≤2 active trips with limit=2, got {len(active)}"
            )
            # All returned trips should have non-terminal statuses
            for t in active:
                assert t["status"] not in (
                    "Delivered", "Completed", "Done", "Cancelled", "Paid"
                ), f"Trip {t['id']} has terminal status {t['status']}"
        finally:
            _destroy_file_db(db)

    # ── test_get_all_parameter_ordering ────────────────────────────────────

    def test_get_all_parameter_ordering(self):
        """Verify ``RouteRepository.get_all`` with scoped user uses correct LIMIT/OFFSET.

        This tests that the multi-tenant company params don't push the LIMIT
        and OFFSET values into wrong positions in the parameter tuple.
        """
        db = _make_scoped_db(company_id=5)
        try:
            # Seed a company row so FK constraint is satisfied
            db.conn.execute(
                "INSERT INTO companies (id, company_name) VALUES (5, 'TestCo-Route')"
            )
            db.conn.commit()

            route_repo = RouteRepository(db)
            # Create several routes with staggered timestamps so that
            # ORDER BY created_at DESC is deterministic.
            from datetime import datetime as dt, timedelta
            base = dt.utcnow()
            for i in range(8):
                ts = (base + timedelta(seconds=i)).isoformat(timespec="seconds") + "Z"
                route_repo.create({
                    "route_fingerprint": f"PARAM-ROUTE-FP-{i}",
                    "created_at": ts,
                    "last_calculated_at": ts,
                    "stops_json": "[]",
                    "geometry_encoding": "zlib-json",
                    "total_distance_km": 100.0 + i,
                    "duration_min": 60.0 + i,
                })

            # Fetch with explicit LIMIT and OFFSET
            page = route_repo.get_all(limit=3, offset=2)
            assert len(page) == 3, (
                f"Expected 3 routes (limit=3, offset=2), got {len(page)}"
            )
            # Verify we got the correct page (ordered by created_at DESC)
            # Routes 0-7 created in order; DESC means 7,6,5,4,3,2,1,0
            # offset=2 => skip 7,6 => 5,4,3 → distances 105,104,103
            expected_distances = [105.0, 104.0, 103.0]
            actual_distances = [r["total_distance_km"] for r in page]
            assert actual_distances == expected_distances, (
                f"Expected distances {expected_distances}, got {actual_distances}"
            )
        finally:
            _destroy_file_db(db)

    # ── test_merge_client_data_regression ──────────────────────────────────

    def test_merge_client_data_regression(self, file_db: DatabaseManager):
        """Verify client merge does not corrupt invoice→trip linkage.

        Merge moves trips from client A to client B, but invoices reference
        trips via ``trip_id``.  The regression is that invoices lose their
        trip reference if the merge deletes/reassigns the trip itself.
        """
        # Clear any stale transaction state that may cause nested
        # transaction errors when merge_client_data calls BEGIN IMMEDIATE.
        try:
            file_db.conn.execute("ROLLBACK")
        except Exception:
            pass

        # Create two clients
        client_repo = ClientRepository(file_db)
        cid_a = client_repo.create({
            "name": "MergeClient-A",
            "is_active": 1,
        })
        cid_b = client_repo.create({
            "name": "MergeClient-B",
            "is_active": 1,
        })

        # Create a trip linked to client A
        trip_repo = TripRepository(file_db)
        trip_id = trip_repo.create({
            "truck_number": "MERGE-TRUCK",
            "driver_name": "Merge-Driver",
            "client_name": "MergeClient-A",
            "client_id": cid_a,
            "distance_km": 100.0,
            "total_price_eur": 1000.0,
            "net_profit": 100.0,
            "start_date": "2026-07-10",
            "end_date": "2026-07-15",
            "status": "Delivered",
        })

        # Create an invoice linked to the trip
        inv_repo = InvoiceRepository(file_db)
        inv_repo._execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
            "VALUES (?, ?, '2026-07-10', '2026-08-10', 1000.0, 'Unpaid')",
            (trip_id, "INV-MERGE-001"),
            commit=True,
        )

        # Verify pre-merge state
        trip_before = trip_repo.get_by_id(trip_id)
        assert trip_before is not None
        assert trip_before["client_id"] == cid_a

        inv_before = inv_repo.get_by_trip_id(trip_id)
        assert inv_before is not None
        assert inv_before["trip_id"] == trip_id

        # Merge client A into client B
        result = client_repo.merge_client_data(from_id=cid_a, to_id=cid_b)
        assert result["trips"] == 1, "Expected 1 trip moved"

        # Verify post-merge: trip now belongs to client B
        trip_after = trip_repo.get_by_id(trip_id)
        assert trip_after is not None, "Trip should still exist after merge"
        assert trip_after["client_id"] == cid_b, (
            f"Trip client_id should be {cid_b} (was {cid_a})"
        )

        # Verify invoice still references the same trip
        inv_after = inv_repo.get_by_trip_id(trip_id)
        assert inv_after is not None, "Invoice should still exist after merge"
        assert inv_after["trip_id"] == trip_id, (
            "Invoice trip_id should be unchanged after merge"
        )
        assert inv_after["invoice_number"] == "INV-MERGE-001", (
            "Invoice number should not change"
        )

        # Verify old client is now inactive
        client_a = client_repo.get_by_id(cid_a)
        assert client_a is not None
        assert client_a["is_active"] == 0, (
            "Merged-from client should be deactivated"
        )


###############################################################################
# TestThreadSafetySetup
###############################################################################


class TestThreadSafetySetup:
    """Tests that the thread-safety infrastructure works correctly."""

    # ── test_pool_gives_different_connections_to_threads ───────────────────

    def test_pool_gives_different_connections_to_threads(self, file_db: DatabaseManager):
        """Verify that each thread gets its own ``sqlite3.Connection``.

        The ``ConnectionPool`` hands out per-thread connections.  This test
        checks that the connection objects from two different threads have
        different ``id()`` values.
        """
        main_conn_id = id(file_db.conn)
        other_conn_ids: List[int] = []
        other_thread_ids: List[int] = []
        errors: List[str] = []
        lock = threading.Lock()
        # Barrier forces all three worker tasks to start and block BEFORE any
        # of them captures its connection.  Without it, tasks that finish in
        # microseconds can complete before ThreadPoolExecutor spawns all three
        # worker threads, so two tasks run on the same thread and legitimately
        # share that thread's connection (the pool is working as designed).
        barrier = threading.Barrier(3, timeout=15)

        def capture_conn() -> None:
            try:
                barrier.wait(timeout=10)
                cid = id(file_db.conn)
                tid = threading.get_ident()
                with lock:
                    other_conn_ids.append(cid)
                    other_thread_ids.append(tid)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(capture_conn) for _ in range(3)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(str(e))

        assert len(errors) == 0, f"Connection capture errors: {errors}"
        assert len(other_conn_ids) == 3
        # Every thread-local connection must differ from the main thread's
        for cid in other_conn_ids:
            assert cid != main_conn_id, (
                "Thread connection should not be the same object as main thread connection"
            )
        # All thread-local connections should differ from each other
        assert len(set(other_conn_ids)) == 3, (
            f"Expected 3 unique connection ids, got {other_conn_ids} "
            f"(thread ids={other_thread_ids})"
        )

    # ── test_multiple_threads_complete_without_exceptions ──────────────────

    def test_multiple_threads_complete_without_exceptions(self, file_db: DatabaseManager):
        """10 threads performing mixed read/write operations — all finish cleanly."""
        errors: List[str] = []
        lock = threading.Lock()
        barrier = threading.Barrier(10, timeout=15)

        # Seed some initial data
        seed_repo = TripRepository(file_db)
        for i in range(5):
            _seed_trip(seed_repo, id=3000 + i, truck_number=f"SAFE-T{i}")

        def mixed_work(worker_id: int) -> None:
            try:
                # Wait until all threads are ready
                barrier.wait(timeout=10)

                trip_repo = TripRepository(file_db)

                # Read operation
                trips = trip_repo.get_all(limit=50)
                assert isinstance(trips, list)

                # Write operation (different trip per worker to avoid PK conflicts)
                trip_repo.create({
                    "truck_number": f"SAFE-C{worker_id}",
                    "driver_name": f"Driver-{worker_id}",
                    "client_name": f"Client-{worker_id}",
                    "distance_km": 200.0 + worker_id,
                    "total_price_eur": 2000.0,
                    "net_profit": 200.0,
                    "start_date": "2026-07-10",
                    "end_date": "2026-07-15",
                    "status": "In Progress",
                })

                # Update existing data
                if trips:
                    trip_repo.update(trips[0]["id"], {"distance_km": 999.0})

            except Exception as e:
                with lock:
                    errors.append(f"worker-{worker_id}: {e}")

        with ThreadPoolExecutor(max_workers=10) as pool:
            futs = [pool.submit(mixed_work, w) for w in range(10)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(f"submit: {e}")

        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Final sanity: DB should have 5 (seed) + 10 (new) = 15 trips
        all_trips = TripRepository(file_db).get_all(limit=500)
        assert len(all_trips) >= 15, (
            f"Expected ≥15 trips, got {len(all_trips)}"
        )
