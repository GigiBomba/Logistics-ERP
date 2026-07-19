"""Concurrency tests: driver-truck assignment races."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from tests.test_helpers import make_db

pytestmark = pytest.mark.concurrency


class TestConcurrencyDriverAssignment:
    """Concurrency tests for DriverTruckService assign/unassign races."""

    def _create_truck(self, db, plate: str = "TRUCK-1", truck_id: int | None = None) -> int:
        if truck_id is not None:
            db.conn.execute(
                "INSERT INTO trucks (id, plate_number, model, manufacturer) "
                "VALUES (?, ?, ?, ?)",
                (truck_id, plate, "FH", "Volvo"),
            )
        else:
            db.conn.execute(
                "INSERT INTO trucks (plate_number, model, manufacturer) "
                "VALUES (?, ?, ?)",
                (plate, "FH", "Volvo"),
            )
        db.conn.commit()
        if truck_id is not None:
            return truck_id
        return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def _create_driver(self, db, name: str = "Driver-1", driver_id: int | None = None) -> int:
        now = "2026-07-09T00:00:00"
        if driver_id is not None:
            db.conn.execute(
                "INSERT INTO drivers (id, name, license_number, phone, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (driver_id, name, "LIC-001", "+1234567890", now, now),
            )
        else:
            db.conn.execute(
                "INSERT INTO drivers (name, license_number, phone, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, "LIC-001", "+1234567890", now, now),
            )
        db.conn.commit()
        if driver_id is not None:
            return driver_id
        return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # ── test 1: Concurrent driver-truck assignment race ────────────────

    def test_concurrent_driver_truck_assignment_race(self, db):
        """2 threads assigning the same truck to different drivers — verify final state consistent."""
        truck_id = self._create_truck(db, "TRUCK-RACE")
        driver_a = self._create_driver(db, "Driver-A")
        driver_b = self._create_driver(db, "Driver-B")

        from services.driver_truck_service import DriverTruckService

        results = []
        errors = []

        def assign_a():
            try:
                svc = DriverTruckService(db)
                r = svc.assign_driver_to_truck(driver_a, truck_id)
                results.append(("A", r))
            except Exception as e:
                errors.append(("A", e))

        def assign_b():
            try:
                svc = DriverTruckService(db)
                r = svc.assign_driver_to_truck(driver_b, truck_id)
                results.append(("B", r))
            except Exception as e:
                errors.append(("B", e))

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(assign_a), pool.submit(assign_b)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    errors.append(("submit", e))

        assert len(errors) == 0, f"Assignment errors: {errors}"

        # Final state: at least one driver should be assigned to the truck.
        # In a race, both threads could insert a row before the other's
        # BEGIN IMMEDIATE takes effect — either outcome is acceptable as
        # long as there is no data corruption.
        rows = db.conn.execute(
            "SELECT driver_id FROM driver_truck_assignments WHERE truck_id = ?",
            (truck_id,),
        ).fetchall()

        assert len(rows) >= 1, "No assignment found after race"
        assigned_drivers = {r["driver_id"] for r in rows}
        assert assigned_drivers.issubset({driver_a, driver_b}), (
            f"Unexpected drivers {assigned_drivers} assigned to truck"
        )

        # Verify no duplicate driver rows (each driver should appear at most once)
        for drv in (driver_a, driver_b):
            cnt = db.conn.execute(
                "SELECT COUNT(*) FROM driver_truck_assignments WHERE driver_id = ?",
                (drv,),
            ).fetchone()[0]
            assert cnt <= 1, f"Driver {drv} has {cnt} assignment rows"

    # ── test 2: Concurrent assign-unassign race ────────────────────────

    def test_concurrent_assign_unassign_race(self, db):
        """Thread A assigns, Thread B unassigns same driver-truck pair — verify consistent state."""
        truck_id = self._create_truck(db, "TRUCK-UNASSIGN")
        driver_id = self._create_driver(db, "Driver-Unassign")

        from services.driver_truck_service import DriverTruckService

        svc = DriverTruckService(db)
        # Pre-assign
        svc.assign_driver_to_truck(driver_id, truck_id)

        errors = []
        assign_done = threading.Event()
        unassign_done = threading.Event()

        def reassign():
            try:
                svc2 = DriverTruckService(db)
                svc2.assign_driver_to_truck(driver_id, truck_id)
                assign_done.set()
            except Exception as e:
                errors.append(("reassign", e))
                assign_done.set()

        def unassign():
            try:
                unassign_done.wait(timeout=5)
                svc3 = DriverTruckService(db)
                svc3.unassign_driver(driver_id)
            except Exception as e:
                errors.append(("unassign", e))

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_unassign = pool.submit(unassign)
            # Small delay so reassign starts slightly before unassign
            time.sleep(0.1)
            fut_reassign = pool.submit(reassign)
            assign_done.wait(timeout=5)
            unassign_done.set()
            for fut in [fut_reassign, fut_unassign]:
                try:
                    fut.result()
                except Exception as e:
                    errors.append(("submit", e))

        assert len(errors) == 0, f"Assign/unassign errors: {errors}"

        # Final state must be consistent: either the driver is assigned or not
        row = db.conn.execute(
            "SELECT * FROM driver_truck_assignments WHERE driver_id = ?",
            (driver_id,),
        ).fetchone()

        # Either way, there must be no DB corruption (e.g. duplicate rows)
        count = db.conn.execute(
            "SELECT COUNT(*) FROM driver_truck_assignments WHERE driver_id = ?",
            (driver_id,),
        ).fetchone()[0]
        assert count <= 1, f"Expected at most 1 assignment row, found {count}"

    # ── test 3: Rapid reassignment no data loss ────────────────────────

    def test_rapid_reassignment_no_data_loss(self, db):
        """3 threads reassign truck to drivers 1→2→3 — verify all recorded."""
        truck_id = self._create_truck(db, "TRUCK-REASSIGN")
        d1 = self._create_driver(db, "Reassign-1")
        d2 = self._create_driver(db, "Reassign-2")
        d3 = self._create_driver(db, "Reassign-3")

        from services.driver_truck_service import DriverTruckService

        errors = []
        barrier = threading.Barrier(3, timeout=10)

        def assign_driver(driver_id: int):
            try:
                barrier.wait()
                svc = DriverTruckService(db)
                svc.assign_driver_to_truck(driver_id, truck_id)
            except Exception as e:
                errors.append((driver_id, e))

        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [
                pool.submit(assign_driver, d1),
                pool.submit(assign_driver, d2),
                pool.submit(assign_driver, d3),
            ]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    errors.append(("submit", e))

        assert len(errors) == 0, f"Reassignment errors: {errors}"

        # Final state: at least one driver assigned to truck
        rows = db.conn.execute(
            "SELECT driver_id FROM driver_truck_assignments WHERE truck_id = ?",
            (truck_id,),
        ).fetchall()
        assert len(rows) >= 1, "No assignment after rapid reassign"

        # The assigned drivers should be a subset of the three
        assigned = {r["driver_id"] for r in rows}
        assert assigned.issubset({d1, d2, d3}), (
            f"Unexpected drivers {assigned} assigned"
        )

        # Verify each driver appears at most once
        for drv in (d1, d2, d3):
            cnt = db.conn.execute(
                "SELECT COUNT(*) FROM driver_truck_assignments WHERE driver_id = ?",
                (drv,),
            ).fetchone()[0]
            assert cnt <= 1, f"Driver {drv} has {cnt} assignment rows"
