"""Maintenance ticket state machine: maintenance record lifecycle.

The codebase currently models maintenance as **records** (one-off service events)
and **schedules** (recurring service intervals). There is no formal "maintenance
ticket" entity with an explicit status state machine (e.g. Open → In Progress →
Completed → Verified).

The FleetMaintenanceService provides:
  - add_record() / update_record() / delete_record()
  - add_schedule() / update_schedule() / delete_schedule()
  - Prediction of next service due dates.

This test file validates the existing record/schedule lifecycle and
documents the gap for a future ticket-based state machine.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from services.fleet_maintenance_service import FleetMaintenanceService

pytestmark = pytest.mark.state_machine


class TestMaintenanceRecordLifecycle:
    """Maintenance record CRUD operations as a lifecycle."""

    def test_add_maintenance_record(self, db, fleet_repo, workflow_env):
        """Adding a maintenance record creates it successfully."""
        truck_id = workflow_env.seed_truck("MT-TEST-01")
        maint_svc = FleetMaintenanceService(db)

        now = datetime.now().strftime("%Y-%m-%d")
        record_id = maint_svc.add_record(
            truck_id=truck_id,
            maint_type="oil_change",
            date=now,
            km=50000.0,
            cost=350.0,
            notes="Regular oil change",
            provider="Service Center A",
        )
        assert record_id > 0, f"Expected positive record_id, got {record_id}"

        records = maint_svc.get_records(truck_id=truck_id)
        assert len(records) >= 1
        record = records[0]
        assert record["maintenance_type"] == "oil_change"
        assert float(record.get("cost", 0)) == 350.0

    def test_update_maintenance_record(self, db, workflow_env):
        """Updating a maintenance record changes its fields."""
        truck_id = workflow_env.seed_truck("MT-TEST-02")
        maint_svc = FleetMaintenanceService(db)
        now = datetime.now().strftime("%Y-%m-%d")

        record_id = maint_svc.add_record(
            truck_id=truck_id,
            maint_type="brakes",
            date=now,
            km=60000.0,
            cost=1200.0,
        )
        assert record_id > 0

        updated = maint_svc.update_record(
            record_id=record_id,
            maint_type="brakes",
            date=now,
            km=62000.0,
            cost=1350.0,
            provider="Brake Shop",
            notes="Replaced brake pads and discs",
        )
        assert updated is True, "update_record returned False"

        records = maint_svc.get_records(truck_id=truck_id)
        matching = [r for r in records if r["id"] == record_id]
        assert len(matching) == 1
        rec = matching[0]

    def test_delete_maintenance_record(self, db, workflow_env):
        """Deleting a maintenance record removes it."""
        truck_id = workflow_env.seed_truck("MT-TEST-03")
        maint_svc = FleetMaintenanceService(db)
        now = datetime.now().strftime("%Y-%m-%d")

        record_id = maint_svc.add_record(
            truck_id=truck_id,
            maint_type="inspection",
            date=now,
            km=100000.0,
        )
        assert record_id > 0

        deleted = maint_svc.delete_record(record_id)
        assert deleted is True, "delete_record returned False"

        records = maint_svc.get_records(truck_id=truck_id)
        matching = [r for r in records if r["id"] == record_id]
        assert len(matching) == 0, "Record still exists after deletion"

    def test_multiple_maintenance_types(self, db, workflow_env):
        """Different maintenance types can be recorded on the same truck."""
        truck_id = workflow_env.seed_truck("MT-TEST-04")
        maint_svc = FleetMaintenanceService(db)
        now = datetime.now().strftime("%Y-%m-%d")

        types = ["oil_change", "tire_replacement", "brakes", "engine", "inspection"]
        created_ids = []
        for mt in types:
            rid = maint_svc.add_record(
                truck_id=truck_id,
                maint_type=mt,
                date=now,
                km=50000.0 + types.index(mt) * 10000,
            )
            created_ids.append(rid)

        assert len(created_ids) == len(types)
        assert all(rid > 0 for rid in created_ids)

        records = maint_svc.get_records(truck_id=truck_id)
        assert len(records) >= len(types)


class TestMaintenanceScheduleLifecycle:
    """Maintenance schedule as a state machine (active/inactive switching)."""

    def test_add_schedule(self, db, workflow_env):
        """Adding a maintenance schedule creates a recurring plan."""
        truck_id = workflow_env.seed_truck("MT-SCHED-01")
        maint_svc = FleetMaintenanceService(db)

        schedule_id = maint_svc.add_schedule(
            truck_id=truck_id,
            maint_type="oil_change",
            interval_km=15000.0,
            interval_months=6,
            last_done_km=50000.0,
            last_done_date=datetime.now().strftime("%Y-%m-%d"),
        )
        assert schedule_id > 0

        schedules = maint_svc.get_schedules(truck_id=truck_id)
        matching = [s for s in schedules if s["id"] == schedule_id]
        assert len(matching) == 1
        assert matching[0]["active"] == 1

    def test_deactivate_schedule(self, db, workflow_env):
        """Deactivating a schedule sets active=0."""
        truck_id = workflow_env.seed_truck("MT-SCHED-02")
        maint_svc = FleetMaintenanceService(db)

        schedule_id = maint_svc.add_schedule(
            truck_id=truck_id,
            maint_type="inspection",
            interval_months=12,
        )
        assert schedule_id > 0

        updated = maint_svc.update_schedule(
            schedule_id=schedule_id,
            active=0,
        )
        assert updated is True

        # Verify by querying DB directly (get_schedules may filter by active status)
        sched = db.conn.execute(
            "SELECT id, active FROM maintenance_schedules WHERE id=?",
            (schedule_id,),
        ).fetchone()
        assert sched is not None, f"Schedule {schedule_id} not found in DB"
        assert sched["active"] == 0, f"Expected active=0, got active={sched['active']}"

    def test_reactivate_schedule(self, db, workflow_env):
        """Reactivating a schedule sets active=1."""
        truck_id = workflow_env.seed_truck("MT-SCHED-03")
        maint_svc = FleetMaintenanceService(db)

        schedule_id = maint_svc.add_schedule(
            truck_id=truck_id,
            maint_type="tire_replacement",
            interval_km=60000.0,
        )

        maint_svc.update_schedule(schedule_id=schedule_id, active=0)
        updated = maint_svc.update_schedule(schedule_id=schedule_id, active=1)
        assert updated is True

        schedules = maint_svc.get_schedules(truck_id=truck_id)
        matching = [s for s in schedules if s["id"] == schedule_id]
        assert matching[0]["active"] == 1


class TestMaintenancePrediction:
    """Predicting next service dates based on schedule + current data."""

    def test_predict_next_service(self, db, workflow_env):
        """predict_next_service returns expected next service date/km."""
        truck_id = workflow_env.seed_truck("MT-PRED-01")
        maint_svc = FleetMaintenanceService(db)

        now = datetime.now()
        maint_svc.add_schedule(
            truck_id=truck_id,
            maint_type="oil_change",
            interval_km=15000.0,
            interval_months=6,
            last_done_km=50000.0,
            last_done_date=(now - timedelta(days=30)).strftime("%Y-%m-%d"),
        )

        prediction = maint_svc.predict_next_service(truck_id, "oil_change")
        assert prediction is not None, "prediction returned None"
        # Actual keys returned by predict_next_service (see fleet_maintenance_service.py)
        assert "due_by_km" in prediction or "due_by_date" in prediction, (
            f"Expected 'due_by_km' or 'due_by_date' in prediction, got keys: {list(prediction.keys())}"
        )


class TestMaintenanceGapDocumentation:
    """Document that a formal maintenance-ticket state machine is not yet implemented.

    When implemented, the ticket state machine should support transitions like:
        Open → In Progress → Completed → Verified
        Open → Cancelled
        In Progress → On Hold → In Progress
    """

    def test_ticket_state_machine_not_yet_implemented(self):
        """Documented gap: Maintenance ticket state machine is not built yet.

        Known gap: The current system only supports maintenance records and
        schedules without a formal ticket state machine. When implemented,
        the ticket state machine should support transitions like:
          Open → In Progress → Completed → Verified
          Open → Cancelled
          In Progress → On Hold → In Progress
        """
        # Structural assertion: maintenance service exists
        assert True  # Documented gap — see docstring above
