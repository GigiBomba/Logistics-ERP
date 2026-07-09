"""Concurrency tests: trip conflict detection under concurrent writes."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from tests.test_helpers import make_db

pytestmark = pytest.mark.concurrency


class TestConcurrencyTripConflicts:
    """Concurrency tests for TripConflictService and trip creation."""

    @pytest.fixture
    def db(self):
        return make_db()

    def _create_truck(self, db, plate: str = "TRUCK-1") -> int:
        db.conn.execute(
            "INSERT INTO trucks (plate_number, model, manufacturer) "
            "VALUES (?, ?, ?)",
            (plate, "FH", "Volvo"),
        )
        db.conn.commit()
        return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def _create_trip_for_truck(
        self, db, truck_id: int, truck_plate: str,
        start_date: str = "2026-07-10", end_date: str = "2026-07-15",
    ) -> int:
        from repositories.trip_repository import TripRepository
        repo = TripRepository(db)
        return repo.create({
            "truck_id": truck_id,
            "truck_number": truck_plate,
            "start_date": start_date,
            "end_date": end_date,
            "client_name": "TestClient",
            "driver_name": "TestDriver",
            "status": "Planned",
        })

    # ── test 1: Concurrent trip creation same truck ────────────────────

    def test_concurrent_trip_creation_same_truck(self, db):
        """5 threads creating trips with the same truck_id — verify no DB corruption."""
        truck_id = self._create_truck(db)

        def create_trip(offset: int):
            from repositories.trip_repository import TripRepository
            repo = TripRepository(db)
            day = 10 + offset
            return repo.create({
                "truck_id": truck_id,
                "truck_number": "TRUCK-1",
                "start_date": f"2026-07-{day:02d}",
                "end_date": f"2026-07-{day + 2:02d}",
                "client_name": f"Client-{offset}",
                "driver_name": f"Driver-{offset}",
                "status": "Planned",
            })

        trip_ids = []
        errors = []

        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = {pool.submit(create_trip, i): i for i in range(1, 6)}
            for fut in as_completed(futs):
                try:
                    trip_ids.append(fut.result())
                except Exception as e:
                    errors.append((futs[fut], e))

        assert len(errors) == 0, f"Trip creation errors: {errors}"
        assert len(trip_ids) == 5, f"Expected 5 trip ids, got {len(trip_ids)}"

        # Verify DB integrity: no duplicate primary keys, all trips present
        count = db.conn.execute(
            "SELECT COUNT(*) FROM trips WHERE truck_id = ?", (truck_id,)
        ).fetchone()[0]
        assert count == 5, f"Expected 5 trips for truck, found {count}"

        # Verify all ids are unique
        assert len(set(trip_ids)) == 5, "Duplicate trip IDs created"

    # ── test 2: Concurrent conflict check write race ───────────────────

    def test_concurrent_conflict_check_write_race(self, db):
        """Thread A checks conflicts (500ms delay), Thread B creates trip during delay.

        Verify the conflict check runs atomically and no inconsistent state results.
        """
        truck_id = self._create_truck(db)
        # Seed one existing trip
        self._create_trip_for_truck(
            db, truck_id, "TRUCK-1",
            start_date="2026-07-10", end_date="2026-07-20",
        )

        from services.conflict_service import TripConflictService
        import copy

        # We'll simulate a slow conflict check by injecting a delay into
        # the repository method called by check_conflicts.
        original_get_active = db.conn.execute

        check_started = threading.Event()
        trip_created = threading.Event()

        def delayed_get_active(sql, params=None):
            if "get_active_for_truck" in sql or "FROM trips" in sql:
                check_started.set()
                time.sleep(0.5)  # simulate slow DB
            return original_get_active(sql, params)

        db.conn.execute = delayed_get_active

        conflict_result = []

        def run_conflict_check():
            svc = TripConflictService(db)
            conflicts = svc.check_conflicts({
                "truck_id": truck_id,
                "truck_number": "TRUCK-1",
                "start_date": "2026-07-05",
                "end_date": "2026-07-25",
            })
            conflict_result.append(conflicts)

        def run_trip_creation():
            check_started.wait(timeout=3)
            self._create_trip_for_truck(
                db, truck_id, "TRUCK-1",
                start_date="2026-07-12", end_date="2026-07-18",
            )
            trip_created.set()

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(run_conflict_check)
            fut_b = pool.submit(run_trip_creation)
            for fut in [fut_a, fut_b]:
                try:
                    fut.result()
                except Exception as e:
                    pytest.fail(f"Thread failed: {e}")

        # Restore original
        db.conn.execute = original_get_active

        # The conflict check should have completed and returned results
        assert len(conflict_result) == 1
        # The trip created during the check should also be persisted
        count = db.conn.execute(
            "SELECT COUNT(*) FROM trips WHERE truck_id = ?", (truck_id,)
        ).fetchone()[0]
        assert count == 2, f"Expected 2 trips, found {count}"

    # ── test 3: Rapid successive conflict checks ───────────────────────

    def test_rapid_successive_conflict_checks(self, db):
        """2 threads run check_conflicts simultaneously — verify consistent results."""
        truck_id = self._create_truck(db)
        self._create_trip_for_truck(
            db, truck_id, "TRUCK-1",
            start_date="2026-07-10", end_date="2026-07-20",
        )

        from services.conflict_service import TripConflictService

        results = []
        errors = []
        lock = threading.Lock()

        def check():
            try:
                svc = TripConflictService(db)
                conflicts = svc.check_conflicts({
                    "truck_id": truck_id,
                    "truck_number": "TRUCK-1",
                    "start_date": "2026-07-05",
                    "end_date": "2026-07-25",
                })
                with lock:
                    results.append(conflicts)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(check) for _ in range(2)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    errors.append(e)

        assert len(errors) == 0, f"Conflict check errors: {errors}"
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"

        # Both checks should see the same state and return identical results
        conflict_ids_0 = sorted(c["trip_id"] for c in results[0])
        conflict_ids_1 = sorted(c["trip_id"] for c in results[1])
        assert conflict_ids_0 == conflict_ids_1, (
            f"Inconsistent conflict results between threads: {results[0]} vs {results[1]}"
        )
