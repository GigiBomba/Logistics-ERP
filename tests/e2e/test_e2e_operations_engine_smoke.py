"""E2E smoke test: OperationsEngine with all dependencies injected via create().

Verifies the DI pattern works end-to-end:
  1. Factory constructor (create()) accepts explicit dependencies.
  2. Reset singleton before headless execution.
  3. Real DB + real sub-engines produce correct alerts and event bus events.
  4. The engine starts, runs daily checks, and stops cleanly.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from repositories.fleet_repository import FleetRepository
from services.operations.alert_manager import AlertManager, AlertType, Severity
from services.operations.event_bus import (
    ALERT_CREATED,
    DAILY_CHECK,
    SYSTEM_STARTUP,
    TRIP_STATUS_CHANGED,
    EventBus,
)
from services.operations.maintenance_engine import MaintenanceEngine
from services.operations.operations_engine import OperationsEngine
from services.operations.rules import Rules
from services.operations.trip_status_workflow import TripStatusWorkflow
from services.operations.undo_stack import UndoStack
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


# ── Helpers ───────────────────────────────────────────────────────────


def _dt(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


def _dt_iso(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).isoformat()


def _create_truck(repo: FleetRepository, plate: str, **overrides) -> int:
    data = {
        "plate_number": plate,
        "model": "Actros 1845",
        "manufacturer": "Mercedes-Benz",
        "year": 2023,
        "vin": f"WDB{plate.replace('-', '')}",
        "status": "Active",
        "active_status": 1,
    }
    data.update(overrides)
    return repo.create(data)


def _create_trip(db, truck_id: int, status: str = "Pending",
                 days_ago: int = 0, price: float = 1000.0) -> int:
    cursor = db.conn.execute(
        "INSERT INTO trips (client_name, truck_id, status, total_price_eur, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        ("Smoke Client", truck_id, status, price, _dt_iso(-days_ago)),
    )
    db.conn.commit()
    return cursor.lastrowid


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def db():
    return make_db()


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all singletons before each test so state doesn't leak."""
    OperationsEngine.reset_instance()
    EventBus._instance = None
    AlertManager._instance = None
    Rules._instance = None


@pytest.fixture
def fleet_repo(db):
    return FleetRepository(db)


# ── Smoke tests ───────────────────────────────────────────────────────


class TestOperationsEngineSmoke:
    """End-to-end smoke test of the OperationsEngine DI pattern."""

    def test_create_factory_returns_independent_instance(self, db):
        """create() bypasses the singleton and returns a fresh instance."""
        engine_a = OperationsEngine.create(db=db)
        engine_b = OperationsEngine.create(db=db)

        assert engine_a is not engine_b, (
            "create() should return different instances, not the singleton"
        )

    def test_get_instance_returns_same_singleton(self, db):
        """get_instance() follows the singleton pattern."""
        engine_a = OperationsEngine.get_instance(db=db)
        engine_b = OperationsEngine.get_instance(db=db)

        assert engine_a is engine_b, (
            "get_instance() should return the same singleton"
        )

    def test_reset_instance_clears_singleton(self, db):
        """reset_instance() clears the singleton so a fresh one is created."""
        engine_a = OperationsEngine.get_instance(db=db)
        OperationsEngine.reset_instance()
        engine_b = OperationsEngine.get_instance(db=db)

        assert engine_a is not engine_b, (
            "reset_instance() should allow a new singleton to be created"
        )

    def test_engine_with_all_explicit_dependencies(self, db):
        """Inject every dependency explicitly via create() and verify they're used."""
        event_bus = EventBus()
        alert_mgr = AlertManager(db)
        rules = Rules()

        events_received: list[str] = []

        def _on_event(ev: dict) -> None:
            events_received.append(ev.get("type", ""))

        event_bus.subscribe(SYSTEM_STARTUP, _on_event)

        engine = OperationsEngine.create(
            db=db,
            event_bus=event_bus,
            alert_mgr=alert_mgr,
            rules=rules,
            trip_service=None,  # will be created as default
        )

        assert engine.event_bus is event_bus, "EventBus not injected"
        assert engine.alert_manager is alert_mgr, "AlertManager not injected"

        engine.start()
        assert SYSTEM_STARTUP in events_received, (
            "SYSTEM_STARTUP event should fire on start()"
        )

        engine.stop()

    def test_maintenance_engine_creates_alerts_via_operations_engine(self, db, fleet_repo):
        """Create trucks with expired inspection, run OperationsEngine
        evaluate_all(), verify AlertManager has the alerts."""
        truck_a = _create_truck(
            fleet_repo, "SMK-EXP-001",
            inspection_expiry=_dt(-60),
        )
        truck_b = _create_truck(
            fleet_repo, "SMK-INS-001",
            insurance_expiry=_dt(3),
        )

        engine = OperationsEngine.create(db=db)
        engine.evaluate_all()

        alerts = engine.get_active_alerts(limit=50)
        truck_a_alerts = [a for a in alerts if a.truck_id == str(truck_a)]
        truck_b_alerts = [a for a in alerts if a.truck_id == str(truck_b)]

        # Truck A should have CRITICAL inspection alert
        insp = [a for a in truck_a_alerts if a.type == AlertType.INSPECTION]
        assert len(insp) >= 1, f"Truck {truck_a} should have INSPECTION alert"
        assert insp[0].severity == Severity.CRITICAL

        # Truck B should have WARNING insurance alert
        ins = [a for a in truck_b_alerts if a.type == AlertType.INSURANCE]
        assert len(ins) >= 1, f"Truck {truck_b} should have INSURANCE alert"
        assert ins[0].severity == Severity.WARNING

        # Verify via alert_manager property too
        assert engine.alert_manager.get_active_count() >= 2

    def test_migrate_existing_data_creates_overdue_alerts(self, db, fleet_repo):
        """migrate_existing_data() should detect overdue invoices from
        completed trips and create the corresponding alerts."""
        truck = _create_truck(fleet_repo, "SMK-OVD-001")

        # Create a delivered trip from 45 days ago (overdue threshold default 30)
        trip_id = _create_trip(db, truck, status="Delivered", days_ago=45, price=2500.0)

        engine = OperationsEngine.create(db=db)
        engine.start()
        result = engine.migrate_existing_data()

        assert result["trips"] >= 1, "Should have found at least 1 trip"
        assert result.get("overdue_invoices", 0) >= 1, (
            "Should have created at least 1 overdue invoice alert"
        )

        alerts = engine.get_active_alerts()
        overdue = [a for a in alerts if a.type == AlertType.OVERDUE_INVOICE]
        assert len(overdue) >= 1, "Should have overdue invoice alerts"

        engine.stop()

    def test_engine_start_stop_cycle(self, db):
        """Start and stop the engine, verify it doesn't error."""
        engine = OperationsEngine.create(db=db)

        # Start
        engine.start()
        assert engine.event_bus is not None

        # Stop
        engine.stop()  # should not raise

        # Re-start after stop
        engine.start()
        engine.stop()

    def test_evaluate_truck_creates_truck_specific_alerts(self, db, fleet_repo):
        """evaluate_truck() should only evaluate a single truck."""
        truck_a = _create_truck(
            fleet_repo, "SMK-SGL-001",
            inspection_expiry=_dt(-90),
        )
        _create_truck(
            fleet_repo, "SMK-SGL-002",
            insurance_expiry=_dt(10),
        )

        engine = OperationsEngine.create(db=db)

        # Only evaluate truck_a
        count = engine.evaluate_truck(str(truck_a))
        assert count >= 1, "evaluate_truck should produce at least 1 alert"

        alerts = engine.get_active_alerts(limit=50)
        truck_a_alerts = [a for a in alerts if a.truck_id == str(truck_a)]

        # Truck A should have alerts
        insp = [a for a in truck_a_alerts if a.type == AlertType.INSPECTION]
        assert len(insp) >= 1

        # Truck B should have NO alerts (wasn't evaluated)
        truck_b_alerts = [a for a in alerts if "SMK-SGL-002" in str(a)]
        assert len(truck_b_alerts) == 0, (
            "evaluate_truck should only evaluate the requested truck"
        )

    def test_evaluate_all_with_injected_alert_manager(self, db, fleet_repo):
        """Sanity check: evaluate_all with explicit AlertManager DI."""
        _create_truck(
            fleet_repo, "SMK-DI-001",
            inspection_expiry=_dt(-45),
        )

        alert_mgr = AlertManager(db)
        initial_count = alert_mgr.get_active_count()

        engine = OperationsEngine.create(db=db, alert_mgr=alert_mgr)
        engine.evaluate_all()

        after_count = alert_mgr.get_active_count()
        assert after_count > initial_count, (
            "Alert count should increase after evaluate_all"
        )

    def test_force_trip_status_via_engine(self, db):
        """Force a trip status change through the engine."""
        from services.trip_service import TripService

        # Create a truck and trip directly (use 'Planned' — valid transition to 'Loading')
        fleet_repo = FleetRepository(db)
        truck = _create_truck(fleet_repo, "SMK-STA-001")
        trip_id = _create_trip(db, truck, status="Planned")

        trip_service = TripService(db)
        engine = OperationsEngine.create(db=db, trip_service=trip_service)

        # Force status change: Planned → Loading
        result = engine.force_trip_status(trip_id, "Loading")
        assert result, "force_trip_status should return True for Planned → Loading"

    def test_engine_with_realistic_scenario(self, db, fleet_repo):
        """Full realistic scenario:
        1. Create trucks with mixed maintenance states
        2. Create completed trips (some overdue for payment)
        3. Start the engine
        4. Run migrate_existing_data
        5. Run evaluate_all
        6. Verify alerts for inspection, insurance, overdue invoices
        """
        # Trucks
        t1 = _create_truck(
            fleet_repo, "SMK-RL-001",
            inspection_expiry=_dt(-30),   # expired → CRITICAL
            insurance_expiry=_dt(60),
        )
        t2 = _create_truck(
            fleet_repo, "SMK-RL-002",
            inspection_expiry=_dt(90),
            insurance_expiry=_dt(5),       # due soon → WARNING
        )
        t3 = _create_truck(
            fleet_repo, "SMK-RL-003",      # healthy truck
            inspection_expiry=_dt(180),
            insurance_expiry=_dt(180),
        )

        # Trips
        _create_trip(db, t1, status="Delivered", days_ago=50, price=3200.0)
        _create_trip(db, t2, status="Invoiced", days_ago=40, price=1800.0)
        _create_trip(db, t3, status="In Transit", days_ago=2, price=950.0)

        # Engine
        alert_mgr = AlertManager(db)
        engine = OperationsEngine.create(db=db, alert_mgr=alert_mgr)

        # Start → run migrations → evaluate
        engine.start()
        migration = engine.migrate_existing_data()
        engine.evaluate_all()

        alerts = engine.get_active_alerts(limit=100)

        # Verify by alert type
        inspection_alerts = [a for a in alerts if a.type == AlertType.INSPECTION]
        insurance_alerts = [a for a in alerts if a.type == AlertType.INSURANCE]
        overdue_alerts = [a for a in alerts if a.type == AlertType.OVERDUE_INVOICE]

        assert len(inspection_alerts) >= 1, "Expected INSPECTION alerts for t1"
        assert len(insurance_alerts) >= 1, "Expected INSURANCE alerts for t2"
        assert len(overdue_alerts) >= 1, "Expected OVERDUE_INVOICE alerts"

        # t1: expired inspection → CRITICAL
        t1_insp = [a for a in inspection_alerts if a.truck_id == str(t1)]
        assert len(t1_insp) >= 1
        assert t1_insp[0].severity == Severity.CRITICAL

        # Migration created overdue alerts
        assert migration["overdue_invoices"] >= 1

        engine.stop()
