"""Concurrency tests: database write isolation, updates, deletes under threading."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from tests.test_helpers import make_db

pytestmark = pytest.mark.concurrency


class TestConcurrencyDbWrite:
    """Concurrency tests for database write patterns with SQLite."""

    def _seed_trip(self, db, trip_id: int = 1) -> dict:
        """Insert a single trip row and return it."""
        from repositories.trip_repository import TripRepository
        repo = TripRepository(db)
        repo.create({
            "id": trip_id,
            "truck_number": "TRUCK-1",
            "driver_name": "Driver-1",
            "client_name": "Client-1",
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
        })
        return repo.get_by_id(trip_id)

    # ── test 1: Concurrent trip updates same row ───────────────────────

    def test_concurrent_trip_updates_same_row(self, db):
        """10 threads updating different columns of the same trip — verify no corruption."""
        self._seed_trip(db, trip_id=1)

        from repositories.trip_repository import TripRepository

        errors = []
        lock = threading.Lock()

        updates = [
            {"distance_km": 600.0},
            {"total_price_eur": 3500.0},
            {"net_profit": 800.0},
            {"fuel_cost": 450.0},
            {"toll_cost": 120.0},
            {"salary_cost": 350.0},
            {"status": "Delivered"},
            {"driver_name": "Driver-Updated"},
            {"client_name": "Client-Updated"},
            {"end_date": "2026-07-16"},
        ]

        def update_trip(update_data: dict):
            try:
                repo = TripRepository(db)
                repo.update(1, update_data)
            except Exception as e:
                with lock:
                    errors.append((update_data, str(e)))

        with ThreadPoolExecutor(max_workers=10) as pool:
            futs = [pool.submit(update_trip, upd) for upd in updates]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(("submit", str(e)))

        assert len(errors) == 0, f"Concurrent update errors: {errors}"

        # Verify final state: trip exists and has the last-written values
        trip = db.get_trip_by_id(1)
        assert trip is not None, "Trip was deleted or lost"

        # All fields should have been written (last writer wins for each field)
        assert trip["distance_km"] == 600.0
        assert trip["total_price_eur"] == 3500.0
        assert trip["net_profit"] == 800.0
        assert trip["fuel_cost"] == 450.0
        assert trip["toll_cost"] == 120.0
        assert trip["salary_cost"] == 350.0
        assert trip["status"] == "Delivered"
        assert trip["driver_name"] == "Driver-Updated"
        assert trip["client_name"] == "Client-Updated"
        assert trip["end_date"] == "2026-07-16"

    # ── test 2: Concurrent inserts and reads ───────────────────────────

    def test_concurrent_inserts_and_reads(self, db):
        """5 readers + 5 writers on trips table — verify readers see consistent state."""
        from repositories.trip_repository import TripRepository

        writers_done = threading.Event()
        stop_readers = threading.Event()
        read_errors = []
        write_errors = []
        lock = threading.Lock()
        inserted_ids: list[int] = []

        def writer(wid: int):
            try:
                for i in range(50):
                    repo = TripRepository(db)
                    tid = repo.create({
                        "truck_number": f"TRUCK-{wid}",
                        "driver_name": f"Driver-{wid}",
                        "client_name": f"Client-{wid}",
                        "distance_km": 100.0 + wid * 10 + i,
                        "total_price_eur": 2000.0 + wid * 100,
                        "net_profit": 300.0 + wid * 10,
                        "start_date": "2026-07-10",
                        "end_date": "2026-07-15",
                        "status": "Planned",
                    })
                    with lock:
                        inserted_ids.append(tid)
                    time.sleep(0.005)
            except Exception as e:
                with lock:
                    write_errors.append(("writer", wid, str(e)))
            finally:
                writers_done.set()

        def reader():
            while not stop_readers.is_set():
                try:
                    repo = TripRepository(db)
                    _ = repo.get_all(limit=100)
                    _ = repo.get_filtered()
                except Exception as e:
                    with lock:
                        read_errors.append(("reader", str(e)))
                    break
                time.sleep(0.003)

        with ThreadPoolExecutor(max_workers=10) as pool:
            writers = [pool.submit(writer, i) for i in range(5)]
            readers = [pool.submit(reader) for _ in range(5)]

            # Let writers finish
            for fut in writers:
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        write_errors.append(("submit", str(e)))

            stop_readers.set()
            for fut in readers:
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        read_errors.append(("submit", str(e)))

        assert len(write_errors) == 0, f"Writer errors: {write_errors}"
        assert len(read_errors) == 0, f"Reader errors: {read_errors}"
        assert len(inserted_ids) == 250, (
            f"Expected 250 inserts, got {len(inserted_ids)}"
        )

    # ── test 3: Concurrent delete and read ─────────────────────────────

    def test_concurrent_delete_and_read(self, db):
        """Thread A reads trip, Thread B deletes same trip — verify reader gets trip or 404."""
        self._seed_trip(db, trip_id=1)

        from repositories.trip_repository import TripRepository

        barrier = threading.Barrier(2, timeout=10)
        read_result = []
        errors = []

        def reader_thread():
            try:
                barrier.wait()
                repo = TripRepository(db)
                trip = repo.get_by_id(1)
                read_result.append(trip)
            except Exception as e:
                errors.append(("reader", str(e)))

        def deleter_thread():
            try:
                barrier.wait()
                repo = TripRepository(db)
                repo.delete(1)
            except Exception as e:
                errors.append(("deleter", str(e)))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(reader_thread), pool.submit(deleter_thread)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    errors.append(("submit", str(e)))

        assert len(errors) == 0, f"Delete/read errors: {errors}"

        # Reader should either get the trip (if read won the race) or None (trip already deleted)
        assert len(read_result) == 1
        trip = read_result[0]
        if trip is not None:
            assert trip["id"] == 1
        # Either outcome is valid — the important thing is no crash or data corruption

        # Verify DB is consistent
        remaining = db.get_trip_by_id(1)
        assert remaining is None or remaining["id"] == 1

    # ── test 4: Transaction isolation write-write ──────────────────────

    def test_transaction_isolation_write_write(self, db):
        """2 threads updating different columns of same trip — verify both applied."""
        self._seed_trip(db, trip_id=1)

        from repositories.trip_repository import TripRepository

        errors = []
        barrier = threading.Barrier(2, timeout=10)

        def update_a():
            try:
                barrier.wait()
                repo = TripRepository(db)
                repo.update(1, {"distance_km": 999.0, "net_profit": 1234.0})
            except Exception as e:
                errors.append(("A", str(e)))

        def update_b():
            try:
                barrier.wait()
                repo = TripRepository(db)
                repo.update(1, {"status": "Completed", "driver_name": "NewDriver"})
            except Exception as e:
                errors.append(("B", str(e)))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(update_a), pool.submit(update_b)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    errors.append(("submit", str(e)))

        assert len(errors) == 0, f"Write-write errors: {errors}"

        # Both updates should have been applied (last writer wins per column)
        trip = db.get_trip_by_id(1)
        assert trip is not None

        # Thread A's columns
        assert trip["distance_km"] == 999.0
        assert trip["net_profit"] == 1234.0

        # Thread B's columns
        assert trip["status"] == "Completed"
        assert trip["driver_name"] == "NewDriver"

        # Unchanged columns
        assert trip["truck_number"] == "TRUCK-1"
        assert trip["client_name"] == "Client-1"
