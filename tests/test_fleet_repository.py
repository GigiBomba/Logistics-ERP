"""Tests for repositories.fleet_repository — CRUD + query methods for trucks,
maintenance records, schedules, and health scores.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from repositories.fleet_repository import FleetRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> FleetRepository:
    return FleetRepository(db)


# ── helpers ──────────────────────────────────────────────────────────

_TRUCK_COUNTER = 0


def _truck(db: InMemoryDB, **kw) -> int:
    global _TRUCK_COUNTER
    _TRUCK_COUNTER += 1
    d: Dict[str, Any] = dict(
        plate_number=f"TRK-{_TRUCK_COUNTER:04d}",
        manufacturer="Volvo",
        model="FH",
        year=2020,
        vin="YV2RT00A6YA123456",
        fuel_consumption=30.0,
        mileage=150000.0,
        monthly_rate=2000.0,
        status="Active",
        insurance_expiry="2027-01-01",
        inspection_expiry="2027-06-01",
        maintenance_due=200000.0,
        active_status=1,
        tracking_device_id="",
        trailer_plate="",
        max_payload_kg=24000.0,
        cmr_insurance_number="",
        cmr_insurance_expiry="",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO trucks ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Truck CRUD ───────────────────────────────────────────────────────


class TestCreateTruck:
    def test_creates_and_returns_id(self, db, repo):
        tid = repo.create({
            "plate_number": "NEW-100",
            "manufacturer": "Scania",
            "model": "R500",
            "vin": "SCANIA123456",
        })
        assert tid > 0
        row = db.conn.execute("SELECT * FROM trucks WHERE id = ?", (tid,)).fetchone()
        assert row is not None
        assert row["plate_number"] == "NEW-100"

    def test_strips_id_field(self, repo):
        tid = repo.create({"id": 999, "plate_number": "NO-ID-OVERRIDE"})
        assert tid != 999


class TestGetTruckById:
    def test_returns_truck(self, db, repo):
        tid = _truck(db, plate_number="GET-ME")
        row = repo.get_by_id(tid)
        assert row is not None
        assert row["plate_number"] == "GET-ME"

    def test_none_for_missing(self, repo):
        assert repo.get_by_id(99999) is None


class TestGetAllTrucks:
    def test_empty_db(self, repo):
        assert repo.get_all() == []

    def test_returns_sorted_by_plate(self, db, repo):
        _truck(db, plate_number="Z-001")
        _truck(db, plate_number="A-001")
        _truck(db, plate_number="M-001")
        results = repo.get_all()
        plates = [r["plate_number"] for r in results]
        assert plates == ["A-001", "M-001", "Z-001"]

    def test_pagination(self, db, repo):
        for i in range(10):
            _truck(db, plate_number=f"PAG-{i:03d}")
        p1 = repo.get_all(limit=3)
        assert len(p1) == 3
        p2 = repo.get_all(limit=3, offset=3)
        assert len(p2) == 3
        assert {r["id"] for r in p1}.isdisjoint({r["id"] for r in p2})


class TestUpdateTruck:
    def test_updates_fields(self, db, repo):
        tid = _truck(db, plate_number="OLD-PLATE")
        repo.update(tid, {"plate_number": "NEW-PLATE", "mileage": 200000.0})
        row = repo.get_by_id(tid)
        assert row["plate_number"] == "NEW-PLATE"
        assert row["mileage"] == 200000.0

    def test_rejects_invalid_column(self, repo):
        with pytest.raises(ValueError, match="Invalid column"):
            repo.update(1, {"nonsense": "x"})


class TestDeleteTruck:
    def test_removes_truck(self, db, repo):
        tid = _truck(db)
        repo.delete(tid)
        assert repo.get_by_id(tid) is None

    def test_delete_nonexistent(self, repo):
        repo.delete(99999)  # should not crash


# ── Truck domain queries ─────────────────────────────────────────────


class TestGetActiveTrucks:
    def test_returns_active_only(self, db, repo):
        _truck(db, plate_number="ACTIVE-1", active_status=1)
        _truck(db, plate_number="INACTIVE", active_status=0)
        _truck(db, plate_number="ACTIVE-2", active_status=1)
        active = repo.get_active_trucks()
        assert len(active) == 2
        assert all(t["active_status"] == 1 for t in active)
        assert "INACTIVE" not in {t["plate_number"] for t in active}


class TestGetByPlate:
    def test_finds_by_plate(self, db, repo):
        _truck(db, plate_number="UNIQUE-PLATE")
        row = repo.get_by_plate("UNIQUE-PLATE")
        assert row is not None
        assert row["plate_number"] == "UNIQUE-PLATE"

    def test_none_for_missing(self, repo):
        assert repo.get_by_plate("NO-SUCH") is None


class TestGetByVin:
    def test_finds_by_vin(self, db, repo):
        _truck(db, vin="VIN-UNIQUE-123")
        row = repo.get_by_vin("VIN-UNIQUE-123")
        assert row is not None

    def test_none_for_missing(self, repo):
        assert repo.get_by_vin("NO-VIN") is None


class TestGetByTrackingDeviceId:
    def test_finds_by_device_id(self, db, repo):
        _truck(db, tracking_device_id="GPS-001")
        row = repo.get_by_tracking_device_id("GPS-001")
        assert row is not None

    def test_none_for_missing(self, repo):
        assert repo.get_by_tracking_device_id("NO-DEVICE") is None


class TestGetByStatus:
    def test_returns_matching(self, db, repo):
        _truck(db, plate_number="A", status="Active")
        _truck(db, plate_number="B", status="In Service")
        _truck(db, plate_number="C", status="Active")
        results = repo.get_by_status("Active")
        assert len(results) == 2


class TestCountActive:
    def test_counts_active(self, db, repo):
        _truck(db, active_status=1)
        _truck(db, active_status=1)
        _truck(db, active_status=0)
        assert repo.count_active() == 2

    def test_zero(self, repo):
        assert repo.count_active() == 0


class TestGetTruckMileage:
    def test_returns_mileage(self, db, repo):
        tid = _truck(db, mileage=123456.0)
        assert repo.get_truck_mileage(tid) == 123456.0

    def test_none_when_null(self, db, repo):
        tid = _truck(db, mileage=None)
        assert repo.get_truck_mileage(tid) is None


class TestGetActiveTruckIds:
    def test_returns_ids(self, db, repo):
        t1 = _truck(db, active_status=1)
        t2 = _truck(db, active_status=1)
        _truck(db, active_status=0)
        ids = repo.get_active_truck_ids()
        assert t1 in ids
        assert t2 in ids
        assert len(ids) == 2


# ── Maintenance Records ──────────────────────────────────────────────


class TestAddMaintenanceRecord:
    def test_creates_record(self, db, repo):
        tid = _truck(db)
        rid = repo.add_maintenance_record(tid, "Oil Change", "2026-06-15",
                                          km=150000.0, cost=500.0,
                                          notes="Regular oil change",
                                          provider="Service Center")
        assert rid > 0
        rows = repo.get_maintenance_records(truck_id=tid)
        assert len(rows) == 1
        assert rows[0]["maintenance_type"] == "Oil Change"

    def test_get_by_type_filter(self, db, repo):
        tid = _truck(db)
        repo.add_maintenance_record(tid, "Oil Change", "2026-01-01")
        repo.add_maintenance_record(tid, "Tire Rotation", "2026-02-01")
        results = repo.get_maintenance_records(truck_id=tid, maint_type="Oil Change")
        assert len(results) == 1


class TestUpdateMaintenanceRecord:
    def test_updates_record(self, db, repo):
        tid = _truck(db)
        rid = repo.add_maintenance_record(tid, "Oil Change", "2026-01-01", cost=100.0)
        repo.update_maintenance_record(rid, "Oil Change", "2026-06-01",
                                       km=160000.0, cost=550.0,
                                       provider="New Shop", notes="Updated")
        rows = db.conn.execute("SELECT * FROM maintenance_records WHERE id = ?", (rid,)).fetchone()
        assert rows["cost"] == 550.0
        assert rows["service_provider"] == "New Shop"


class TestDeleteMaintenanceRecord:
    def test_deletes_record(self, db, repo):
        tid = _truck(db)
        rid = repo.add_maintenance_record(tid, "Oil Change", "2026-01-01")
        repo.delete_maintenance_record(rid)
        rows = repo.get_maintenance_records(truck_id=tid)
        assert len(rows) == 0


class TestCountMaintenanceRecords:
    def test_counts_by_truck(self, db, repo):
        t1 = _truck(db)
        t2 = _truck(db)
        repo.add_maintenance_record(t1, "A", "2026-01-01")
        repo.add_maintenance_record(t1, "B", "2026-02-01")
        repo.add_maintenance_record(t2, "A", "2026-03-01")
        assert repo.count_maintenance_records(truck_id=t1) == 2
        assert repo.count_maintenance_records(truck_id=t2) == 1

    def test_count_by_type(self, db, repo):
        tid = _truck(db)
        repo.add_maintenance_record(tid, "Oil Change", "2026-01-01")
        repo.add_maintenance_record(tid, "Oil Change", "2026-02-01")
        repo.add_maintenance_record(tid, "Tires", "2026-03-01")
        assert repo.count_maintenance_records(truck_id=tid, maint_type="Oil Change") == 2


class TestGetMaintenanceRecordTruckId:
    def test_returns_truck_id(self, db, repo):
        tid = _truck(db)
        rid = repo.add_maintenance_record(tid, "A", "2026-01-01")
        assert repo.get_maintenance_record_truck_id(rid) == tid

    def test_none_for_missing(self, repo):
        assert repo.get_maintenance_record_truck_id(99999) is None


class TestGetMaintenanceTypeCounts:
    def test_returns_types_with_min_count(self, db, repo):
        tid = _truck(db)
        for _ in range(3):
            repo.add_maintenance_record(tid, "Oil Change", "2026-01-01")
        repo.add_maintenance_record(tid, "Tires", "2026-02-01")
        counts = repo.get_maintenance_type_counts(tid)
        types = {c["maintenance_type"]: c["cnt"] for c in counts}
        assert types.get("Oil Change") == 3
        assert "Tires" not in types  # only 1 occurrence


# ── Maintenance Schedules ────────────────────────────────────────────


class TestAddMaintenanceSchedule:
    def test_creates_schedule(self, db, repo):
        tid = _truck(db)
        sid = repo.add_maintenance_schedule(tid, "Oil Change",
                                            interval_km=30000.0,
                                            interval_months=12)
        assert sid > 0
        schedules = repo.get_maintenance_schedules(truck_id=tid)
        assert len(schedules) == 1

    def test_defaults_active(self, db, repo):
        tid = _truck(db)
        sid = repo.add_maintenance_schedule(tid, "Oil Change")
        rows = db.conn.execute("SELECT * FROM maintenance_schedules WHERE id = ?", (sid,)).fetchone()
        assert rows["active"] == 1


class TestGetMaintenanceSchedule:
    def test_get_by_truck_and_type(self, db, repo):
        tid = _truck(db)
        repo.add_maintenance_schedule(tid, "Oil Change", interval_km=30000)
        repo.add_maintenance_schedule(tid, "Tires", interval_km=50000)
        schedule = repo.get_maintenance_schedule(tid, "Oil Change")
        assert schedule is not None
        assert schedule["interval_km"] == 30000

    def test_none_for_missing(self, db, repo):
        tid = _truck(db)
        assert repo.get_maintenance_schedule(tid, "NoSuch") is None


class TestUpdateMaintenanceSchedule:
    def test_updates_schedule(self, db, repo):
        tid = _truck(db)
        sid = repo.add_maintenance_schedule(tid, "Oil Change", interval_km=30000)
        repo.update_maintenance_schedule(sid, interval_km=50000, active=0)
        rows = db.conn.execute("SELECT * FROM maintenance_schedules WHERE id = ?", (sid,)).fetchone()
        assert rows["interval_km"] == 50000
        assert rows["active"] == 0


class TestDeleteMaintenanceSchedule:
    def test_deletes_schedule(self, db, repo):
        tid = _truck(db)
        sid = repo.add_maintenance_schedule(tid, "Oil Change")
        repo.delete_maintenance_schedule(sid)
        assert repo.get_maintenance_schedule(tid, "Oil Change") is None


class TestGetScheduleTruckId:
    def test_returns_truck_id(self, db, repo):
        tid = _truck(db)
        sid = repo.add_maintenance_schedule(tid, "A")
        assert repo.get_schedule_truck_id(sid) == tid


class TestGetAllSchedulesFlat:
    def test_joins_truck_plate(self, db, repo):
        t1 = _truck(db, plate_number="TRK-1")
        t2 = _truck(db, plate_number="TRK-2")
        repo.add_maintenance_schedule(t1, "Oil")
        repo.add_maintenance_schedule(t2, "Tires")
        flat = repo.get_all_schedules_flat()
        assert len(flat) == 2
        plates = {s["plate_number"] for s in flat}
        assert "TRK-1" in plates


class TestCountActiveMaintenanceSchedules:
    def test_counts_only_active(self, db, repo):
        tid = _truck(db)
        repo.add_maintenance_schedule(tid, "A")  # active=1 default
        repo.add_maintenance_schedule(tid, "B", interval_km=10000)  # active=1
        all_schedules = repo.count_active_maintenance_schedules()
        assert all_schedules >= 2  # other tests may add more


# ── Truck Health Scores ──────────────────────────────────────────────


class TestUpsertTruckHealth:
    def test_creates_health_score(self, db, repo):
        tid = _truck(db)
        repo.upsert_truck_health(tid, score=85, compliance_pct=90.0,
                                 overdue_count=2, recurring_issues=1,
                                 downtime_days=3, last_updated="2026-06-01")
        health = repo.get_truck_health(tid)
        assert health is not None
        assert health["score"] == 85
        assert health["compliance_pct"] == 90.0

    def test_replaces_existing(self, db, repo):
        tid = _truck(db)
        repo.upsert_truck_health(tid, score=50, compliance_pct=60.0,
                                 overdue_count=5, recurring_issues=3,
                                 downtime_days=10, last_updated="2026-01-01")
        repo.upsert_truck_health(tid, score=95, compliance_pct=100.0,
                                 overdue_count=0, recurring_issues=0,
                                 downtime_days=0, last_updated="2026-06-01")
        health = repo.get_truck_health(tid)
        assert health["score"] == 95

    def test_none_for_missing(self, repo):
        assert repo.get_truck_health(99999) is None


class TestGetAllTruckHealth:
    def test_returns_all(self, db, repo):
        t1 = _truck(db)
        t2 = _truck(db)
        repo.upsert_truck_health(t1, score=80, compliance_pct=90.0,
                                 overdue_count=0, recurring_issues=0,
                                 downtime_days=0, last_updated="2026-01-01")
        repo.upsert_truck_health(t2, score=70, compliance_pct=80.0,
                                 overdue_count=1, recurring_issues=1,
                                 downtime_days=2, last_updated="2026-01-01")
        all_h = repo.get_all_truck_health()
        assert len(all_h) == 2


# ── Analytics queries ────────────────────────────────────────────────


class TestMaintenanceCostQueries:
    def test_sum_maintenance_cost(self, db, repo):
        tid = _truck(db)
        repo.add_maintenance_record(tid, "Oil Change", "2026-01-01", cost=500)
        repo.add_maintenance_record(tid, "Repair", "2026-02-01", cost=1500)
        total = repo.sum_maintenance_cost()
        assert total == 2000.0

    def test_sum_maintenance_cost_since_date(self, db, repo):
        tid = _truck(db)
        repo.add_maintenance_record(tid, "Old", "2025-12-01", cost=1000)
        repo.add_maintenance_record(tid, "Recent", "2026-06-01", cost=2000)
        total = repo.sum_maintenance_cost(since_date="2026-01-01")
        assert total == 2000.0

    def test_maintenance_cost_by_type(self, db, repo):
        tid = _truck(db)
        repo.add_maintenance_record(tid, "Oil Change", "2026-01-01", cost=500)
        repo.add_maintenance_record(tid, "Oil Change", "2026-02-01", cost=500)
        repo.add_maintenance_record(tid, "Tires", "2026-03-01", cost=2000)
        by_type = repo.get_maintenance_cost_by_type()
        costs = {r["maintenance_type"]: r["total"] for r in by_type}
        assert costs["Oil Change"] == 1000.0
        assert costs["Tires"] == 2000.0

    def test_maintenance_count_by_type(self, db, repo):
        tid = _truck(db)
        repo.add_maintenance_record(tid, "Oil Change", "2026-01-01")
        repo.add_maintenance_record(tid, "Oil Change", "2026-02-01")
        repo.add_maintenance_record(tid, "Tires", "2026-03-01")
        by_type = repo.get_maintenance_count_by_type()
        counts = {r["maintenance_type"]: r["cnt"] for r in by_type}
        assert counts["Oil Change"] == 2

    def test_get_maintenance_cost_monthly(self, db, repo):
        tid = _truck(db)
        repo.add_maintenance_record(tid, "A", "2026-01-15", cost=1000)
        repo.add_maintenance_record(tid, "B", "2026-02-10", cost=2000)
        monthly = repo.get_maintenance_cost_monthly("2026-01-01")
        ym = {r["ym"]: r["total"] for r in monthly}
        assert ym.get("2026-01") == 1000.0
        assert ym.get("2026-02") == 2000.0
