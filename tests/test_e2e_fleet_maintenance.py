"""E2E: Fleet maintenance lifecycle — truck creation, maintenance schedules,
records, health scores, overdue detection, and interval-based predictions."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from repositories.fleet_repository import FleetRepository
from services.fleet_maintenance_service import (
    FleetMaintenanceService,
    MaintType,
    TruckHealth,
)
from services.fleet_service import FleetService
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def fleet_svc(db):
    return FleetService(db)


@pytest.fixture
def fleet_repo(db):
    return FleetRepository(db)


@pytest.fixture
def maint_svc(db):
    return FleetMaintenanceService(db)


@pytest.fixture(autouse=True)
def _reset_singletons():
    from services.operations.event_bus import EventBus
    EventBus._instance = None
    from services.operations.alert_manager import AlertManager
    AlertManager._instance = None
    from services.operations.rules import Rules
    Rules._instance = None


# ── Helpers ───────────────────────────────────────────────────────────────


def _dt(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


# ── Tests ────────────────────────────────────────────────────────────────


class TestFleetMaintenance:
    """Complete fleet maintenance lifecycle tests."""

    def test_full_maintenance_lifecycle(self, db, fleet_svc, fleet_repo, maint_svc):
        """Create truck → add schedules → add records → verify health scores."""
        # ── Step 1: Create a truck ───────────────────────────────────
        truck_id = fleet_svc.add_truck({
            "plate_number": "TR-E2E-001",
            "model": "Actros 1845",
            "manufacturer": "Mercedes-Benz",
            "year": 2023,
            "vin": "WDB9634031L999999",
            "fuel_consumption": 28.5,
            "mileage": 50000.0,
            "status": "Active",
            "active_status": 1,
        })
        assert truck_id > 0
        truck = fleet_repo.get_by_id(truck_id)
        assert truck is not None
        assert truck["plate_number"] == "TR-E2E-001"

        # ── Step 2: Create maintenance schedules ─────────────────────
        # Oil change every 15,000 km or 6 months
        oil_sched_id = maint_svc.add_schedule(
            truck_id=truck_id,
            maint_type=MaintType.OIL_CHANGE.value,
            interval_km=15000.0,
            interval_months=6,
            last_done_km=35000.0,
            last_done_date=_dt(-30),
        )
        assert oil_sched_id > 0

        # Tire replacement every 60,000 km
        tire_sched_id = maint_svc.add_schedule(
            truck_id=truck_id,
            maint_type=MaintType.TIRE_REPLACEMENT.value,
            interval_km=60000.0,
            last_done_km=10000.0,
            last_done_date=_dt(-365),
        )
        assert tire_sched_id > 0

        # Inspection every 12 months
        insp_sched_id = maint_svc.add_schedule(
            truck_id=truck_id,
            maint_type=MaintType.INSPECTION.value,
            interval_months=12,
            last_done_date=_dt(-400),  # overdue
        )
        assert insp_sched_id > 0

        # ── Step 3: Verify schedules exist ───────────────────────────
        schedules = maint_svc.get_schedules(truck_id=truck_id)
        assert len(schedules) >= 3
        sched_types = {s["maintenance_type"] for s in schedules}
        assert MaintType.OIL_CHANGE.value in sched_types
        assert MaintType.TIRE_REPLACEMENT.value in sched_types
        assert MaintType.INSPECTION.value in sched_types

        # ── Step 4: Add maintenance records ──────────────────────────
        # Oil change record
        record_id = maint_svc.add_record(
            truck_id=truck_id,
            maint_type=MaintType.OIL_CHANGE.value,
            date=_dt(-1),
            km=50000.0,
            cost=450.0,
            notes="Regular oil change, 10W-40 synthetic",
            provider="AutoService Berlin",
        )
        assert record_id > 0

        # Brake inspection record
        brake_rec_id = maint_svc.add_record(
            truck_id=truck_id,
            maint_type=MaintType.BRAKES.value,
            date=_dt(-5),
            km=49000.0,
            cost=1200.0,
            notes="Front brake pads replaced",
            provider="TruckRepair Hamburg",
        )
        assert brake_rec_id > 0

        # ── Step 5: Verify records ───────────────────────────────────
        records = maint_svc.get_records(truck_id=truck_id)
        assert len(records) >= 2
        rec_types = {r["maintenance_type"] for r in records}
        assert MaintType.OIL_CHANGE.value in rec_types
        assert MaintType.BRAKES.value in rec_types

        # ── Step 6: Compute and verify health score ──────────────────
        health = maint_svc.compute_health(truck_id)
        assert isinstance(health, TruckHealth)
        assert health.truck_id == truck_id
        assert health.score >= 0
        assert health.score <= 100
        # At least one overdue schedule (inspection is overdue)
        assert health.overdue_count >= 1

        # ── Step 7: Verify health score persisted to DB ──────────────
        db_health = fleet_repo.get_truck_health(truck_id)
        assert db_health is not None
        assert db_health["score"] == health.score
        assert db_health["overdue_count"] == health.overdue_count
        assert db_health["compliance_pct"] == health.compliance_pct

        # ── Step 8: Test predict_next_service ────────────────────────
        oil_pred = maint_svc.predict_next_service(truck_id, MaintType.OIL_CHANGE.value)
        assert oil_pred is not None
        # After oil change at 50,000 km with 15,000 km interval → next due at 65,000 km
        assert oil_pred["due_by_km"] is not None
        assert oil_pred["current_km"] == 50000.0
        # The interval is 15000, last_done_km was auto-updated to 50000 by add_record
        # So due_km = 50000 + 15000 = 65000, remaining = 65000 - 50000 = 15000
        assert oil_pred["due_by_km"] > 0  # not overdue yet

        tire_pred = maint_svc.predict_next_service(truck_id, MaintType.TIRE_REPLACEMENT.value)
        assert tire_pred is not None
        # last_done_km was 10000, interval 60000 → due at 70000
        # current_km is 50000, so remaining = 20000
        assert tire_pred["due_by_km"] is not None
        assert tire_pred["overdue"] is False

        insp_pred = maint_svc.predict_next_service(truck_id, MaintType.INSPECTION.value)
        assert insp_pred is not None
        # Inspection is overdue (last done 400 days ago, interval 12 months)
        assert insp_pred["overdue"] is True

    def test_overdue_detection_and_alerts(self, db, fleet_svc, maint_svc, fleet_repo):
        """Detect overdue maintenance and verify health report."""
        # ── Create a truck ───────────────────────────────────────────
        truck_id = fleet_svc.add_truck({
            "plate_number": "TR-OVERDUE-001",
            "model": "FH16",
            "manufacturer": "Volvo",
            "mileage": 80000.0,
            "status": "Active",
            "active_status": 1,
        })

        # ── Add a schedule that's overdue (km-based) ─────────────────
        # Oil change: last done at 30000 km, interval 15000 km
        # Current mileage 80000 → should be overdue (80000 >= 30000 + 15000 = 45000)
        maint_svc.add_schedule(
            truck_id=truck_id,
            maint_type=MaintType.OIL_CHANGE.value,
            interval_km=15000.0,
            last_done_km=30000.0,
            last_done_date=_dt(-180),
        )

        # ── Add a schedule that's NOT overdue (date-based, recent) ───
        maint_svc.add_schedule(
            truck_id=truck_id,
            maint_type=MaintType.INSPECTION.value,
            interval_months=12,
            last_done_date=_dt(-30),  # only 30 days ago
        )

        # ── Compute health ───────────────────────────────────────────
        health = maint_svc.compute_health(truck_id)
        assert health.overdue_count >= 1
        # Score should be reduced due to overdue
        assert health.score < 100

        # ── Verify predict_all_upcoming returns overdue items ────────
        upcoming = maint_svc.predict_all_upcoming(truck_id, days_ahead=30)
        oil_upcoming = [p for p in upcoming if p["type"] == MaintType.OIL_CHANGE.value]
        assert len(oil_upcoming) >= 1
        assert oil_upcoming[0]["overdue"] is True

    def test_schedule_auto_update_on_record(self, db, fleet_svc, maint_svc, fleet_repo):
        """Adding a maintenance record should auto-update the corresponding schedule."""
        # ── Create a truck ───────────────────────────────────────────
        truck_id = fleet_svc.add_truck({
            "plate_number": "TR-AUTO-001",
            "model": "Daf XF",
            "manufacturer": "DAF",
            "mileage": 60000.0,
            "status": "Active",
            "active_status": 1,
        })

        # ── Create a schedule ────────────────────────────────────────
        sched_id = maint_svc.add_schedule(
            truck_id=truck_id,
            maint_type=MaintType.OIL_CHANGE.value,
            interval_km=15000.0,
            last_done_km=45000.0,
            last_done_date=_dt(-60),
        )
        assert sched_id > 0

        # ── Add a maintenance record ─────────────────────────────────
        maint_svc.add_record(
            truck_id=truck_id,
            maint_type=MaintType.OIL_CHANGE.value,
            date=_dt(0),
            km=60000.0,
            cost=500.0,
            notes="Scheduled oil change",
            provider="Service Center",
        )

        # ── Verify schedule was auto-updated ─────────────────────────
        schedules = maint_svc.get_schedules(truck_id=truck_id)
        oil_sched = [s for s in schedules if s["maintenance_type"] == MaintType.OIL_CHANGE.value]
        assert len(oil_sched) >= 1
        assert oil_sched[0]["last_done_km"] == 60000.0
        assert oil_sched[0]["last_done_date"] == _dt(0)

    def test_summary_and_dashboard_data(self, db, fleet_svc, maint_svc):
        """Verify get_summary returns expected dashboard metrics."""
        # ── Create trucks with maintenance data ──────────────────────
        for i in range(2):
            truck_id = fleet_svc.add_truck({
                "plate_number": f"TR-SUM-{i:03d}",
                "model": "Test Truck",
                "manufacturer": "TestMan",
                "mileage": 20000.0 + i * 10000,
                "status": "Active",
                "active_status": 1,
            })

            # Add a schedule and a record
            maint_svc.add_schedule(
                truck_id=truck_id,
                maint_type=MaintType.OIL_CHANGE.value,
                interval_km=15000.0,
                last_done_km=10000.0,
                last_done_date=_dt(-30),
            )
            maint_svc.add_record(
                truck_id=truck_id,
                maint_type=MaintType.OIL_CHANGE.value,
                date=_dt(-1),
                km=20000.0 + i * 10000,
                cost=400.0 + i * 50,
                notes="Oil change",
            )

        # ── Verify summary ───────────────────────────────────────────
        summary = maint_svc.get_summary()
        assert summary["total_records"] >= 2
        assert summary["total_cost"] >= 800.0
        assert summary["trucks_needing_service"] >= 0
        assert summary["avg_health"] >= 0

        # Cost by type should include oil_change
        assert "oil_change" in summary["cost_by_type"]
        assert summary["cost_by_type"]["oil_change"] >= 800.0

        # Top maintained trucks should exist
        assert len(summary["top_maintained_trucks"]) >= 1
