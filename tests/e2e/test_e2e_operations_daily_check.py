"""E2E: Operations daily check — maintenance evaluation, alerts, events."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from repositories.document_repository import DocumentRepository
from repositories.fleet_repository import FleetRepository
from repositories.trip_repository import TripRepository
from services.document.expiry_service import ExpiryService
from services.operations.alert_manager import AlertManager, AlertType, Severity
from services.operations.event_bus import (
    ALERT_CREATED,
    ALERT_RESOLVED,
    DAILY_CHECK,
    EventBus,
)
from services.operations.maintenance_engine import MaintenanceEngine
from services.operations.rules import Rules
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


# ── Helpers ───────────────────────────────────────────────────────────


def _dt(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


def _dt_iso(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).isoformat()


def _create_truck(repo: FleetRepository, plate: str, **overrides) -> int:
    """Create a truck and return its id."""
    data = {
        "plate_number": plate,
        "model": "Actros 1845",
        "manufacturer": "Mercedes-Benz",
        "year": 2023,
        "vin": f"WDB{plate.replace('-', '')}",
        "fuel_consumption": 28.5,
        "mileage": 50000.0,
        "status": "Active",
        "active_status": 1,
    }
    data.update(overrides)
    return repo.create(data)


def _create_trip(db, truck_id: int, days_ago: int = 0) -> int:
    """Create a trip with a specific created_at date."""
    cursor = db.conn.execute(
        "INSERT INTO trips (client_name, truck_id, status, total_price_eur, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        (
            "Test Client",
            truck_id,
            "Delivered",
            1000.0,
            _dt_iso(-days_ago),
        ),
    )
    db.conn.commit()
    return cursor.lastrowid


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def fleet_repo(db):
    return FleetRepository(db)


@pytest.fixture(autouse=True)
def _reset_singletons():
    EventBus._instance = None
    AlertManager._instance = None
    Rules._instance = None


# ── Tests ─────────────────────────────────────────────────────────────


class TestOperationsDailyCheck:
    """Daily check: maintenance evaluation, event bus, alert lifecycle."""

    def test_maintenance_engine_evaluates_all_trucks(
        self, db, fleet_repo,
    ):
        """Create 2 trucks (one with expired inspection, one with upcoming
        insurance), run evaluate_all(), verify alerts."""
        # Truck 1: expired inspection (30 days ago)
        truck_a = _create_truck(
            fleet_repo, "TR-EXP-001",
            inspection_expiry=_dt(-30),
        )
        # Truck 2: insurance due soon (within 10-day warning window)
        truck_b = _create_truck(
            fleet_repo, "TR-INS-001",
            insurance_expiry=_dt(5),  # expires in 5 days
        )

        engine = MaintenanceEngine(db)
        count = engine.evaluate_all()

        assert count >= 2, (
            f"Expected at least 2 alerts (expired inspection + insurance soon), got {count}"
        )

        am = AlertManager()
        alerts = am.get_active_alerts(limit=50)

        truck_a_alerts = [a for a in alerts if a.truck_id == str(truck_a)]
        truck_b_alerts = [a for a in alerts if a.truck_id == str(truck_b)]

        # Truck A should have an INSPECTION alert (expired → CRITICAL)
        insp_alerts = [a for a in truck_a_alerts if a.type == AlertType.INSPECTION]
        assert len(insp_alerts) >= 1, (
            f"Truck {truck_a} should have INSPECTION alert"
        )
        assert insp_alerts[0].severity == Severity.CRITICAL

        # Truck B should have an INSURANCE alert (due soon → WARNING)
        ins_alerts = [a for a in truck_b_alerts if a.type == AlertType.INSURANCE]
        assert len(ins_alerts) >= 1, (
            f"Truck {truck_b} should have INSURANCE alert"
        )
        assert ins_alerts[0].severity == Severity.WARNING

    def test_daily_check_publishes_and_subscribers_fire(
        self, db,
    ):
        """Subscribe callback to DAILY_CHECK, publish event, verify callback fired."""
        eb = EventBus()
        callback = MagicMock()

        eb.subscribe(DAILY_CHECK, callback)
        eb.publish(DAILY_CHECK, {"trigger": "test"})

        callback.assert_called_once()
        # Verify the event data was passed
        call_args = callback.call_args[0][0]
        assert call_args["type"] == DAILY_CHECK
        assert call_args["data"]["trigger"] == "test"

    def test_alert_created_event_published(
        self, db,
    ):
        """Create alert, verify ALERT_CREATED event on EventBus."""
        eb = EventBus()
        callback = MagicMock()
        eb.subscribe(ALERT_CREATED, callback)

        am = AlertManager(db)
        alert = am.create_alert(
            alert_type=AlertType.INSPECTION,
            severity=Severity.WARNING,
            title="Test alert",
            message="This is a test alert for event bus",
            truck_id="42",
        )

        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args["type"] == ALERT_CREATED
        alert_data = call_args["data"]["alert"]
        assert alert_data["title"] == "Test alert"
        assert alert_data["type"] == AlertType.INSPECTION.value
        assert alert_data["truck_id"] == "42"

    def test_alert_resolved_event_published(
        self, db,
    ):
        """Create alert, resolve it, verify ALERT_RESOLVED event."""
        eb = EventBus()
        resolve_callback = MagicMock()
        eb.subscribe(ALERT_RESOLVED, resolve_callback)

        am = AlertManager(db)
        alert = am.create_alert(
            alert_type=AlertType.MAINTENANCE,
            severity=Severity.CRITICAL,
            title="Resolve test",
            message="This alert will be resolved",
            truck_id="99",
        )

        resolved = am.resolve_alert(alert.id)
        assert resolved is not None
        assert resolved.resolved is True

        resolve_callback.assert_called_once()
        call_args = resolve_callback.call_args[0][0]
        assert call_args["type"] == ALERT_RESOLVED
        alert_data = call_args["data"]["alert"]
        assert alert_data["id"] == alert.id
        assert alert_data["resolved"] is True

    def test_document_expiry_evaluation(
        self, db,
    ):
        """Create document with expiry_date 3 days from now, verify expiry alert."""
        now = datetime.now().isoformat()
        repo = DocumentRepository(db)

        # Create a document with an expiry date 3 days in the future
        doc_id = repo.create(
            doc_number="DOC-EXP-0001",
            title="Expiring Contract",
            category="contracts",
            entity_type="client",
            entity_id=1,
            file_path="/tmp/test_expiry.pdf",
            file_name="test_expiry.pdf",
            file_size=100,
            mime_type="application/pdf",
            file_hash="expiry_test_hash",
            tags="[]",
            description="Test document for expiry",
            uploaded_by="tester",
            uploaded_at=now,
            updated_at=now,
        )
        # Set expiry date to 3 days from now
        repo.update(doc_id, expiry_date=_dt(3))

        am = AlertManager(db)
        expiry_svc = ExpiryService(repo)
        count = expiry_svc.evaluate_document_expiries(alert_mgr=am, db=db)

        # Should create a WARNING alert (expiring within 30 days)
        assert count >= 1, (
            f"Expected at least 1 expiry alert, got {count}"
        )

        alerts = am.get_active_alerts(limit=50)
        expiry_alerts = [a for a in alerts if a.type == AlertType.DOCUMENT_EXPIRY]
        assert len(expiry_alerts) >= 1, "No DOCUMENT_EXPIRY alerts found"

        # Also test with an overdue document
        overdue_id = repo.create(
            doc_number="DOC-OVR-0001",
            title="Overdue License",
            category="licenses",
            entity_type="driver",
            entity_id=1,
            file_path="/tmp/test_overdue.pdf",
            file_name="test_overdue.pdf",
            file_size=100,
            mime_type="application/pdf",
            file_hash="overdue_test_hash",
            tags="[]",
            description="Overdue document",
            uploaded_by="tester",
            uploaded_at=now,
            updated_at=now,
        )
        repo.update(overdue_id, expiry_date=_dt(-5))  # 5 days overdue

        count2 = expiry_svc.evaluate_document_expiries(alert_mgr=am, db=db)
        assert count2 >= 1, "Expected alerts for overdue document"

    def test_inactive_truck_detection(
        self, db, fleet_repo,
    ):
        """Create truck with no trips in 40 days, verify INACTIVE_TRUCK alert."""
        truck_id = _create_truck(fleet_repo, "TR-INACTIVE-001")

        # Create a trip that's 40 days old (inactive_truck_days default is 30)
        _create_trip(db, truck_id, days_ago=40)

        engine = MaintenanceEngine(db)
        count = engine.evaluate_all()

        assert count >= 1, (
            f"Expected at least 1 alert for inactive truck, got {count}"
        )

        am = AlertManager()
        alerts = am.get_active_alerts(limit=50)
        inactive_alerts = [
            a for a in alerts
            if a.type == AlertType.INACTIVE_TRUCK
            and a.truck_id == str(truck_id)
        ]
        assert len(inactive_alerts) >= 1, (
            f"No INACTIVE_TRUCK alert for truck {truck_id}"
        )

    def test_alert_deduplication(
        self, db, fleet_repo,
    ):
        """Run evaluate_truck twice, verify only 1 active alert (dedup)."""
        truck_id = _create_truck(
            fleet_repo, "TR-DEDUP-001",
            inspection_expiry=_dt(-15),  # expired 15 days ago
        )

        engine = MaintenanceEngine(db)

        # First evaluation
        count1 = engine.evaluate_truck(truck_id)
        assert count1 >= 1, "First evaluation should produce alerts"

        am = AlertManager()
        alerts_after_first = am.get_active_alerts(limit=50)
        truck_alerts_1 = [
            a for a in alerts_after_first
            if a.truck_id == str(truck_id) and a.type == AlertType.INSPECTION
        ]
        assert len(truck_alerts_1) == 1, (
            f"Expected 1 active INSPECTION alert after first eval, "
            f"got {len(truck_alerts_1)}"
        )

        # Second evaluation
        count2 = engine.evaluate_truck(truck_id)
        # The second call may return 0 (duplicate) or 1 (resolved+recreated)
        # Either way, there should be exactly 1 active alert

        alerts_after_second = am.get_active_alerts(limit=50)
        truck_alerts_2 = [
            a for a in alerts_after_second
            if a.truck_id == str(truck_id) and a.type == AlertType.INSPECTION
        ]
        assert len(truck_alerts_2) == 1, (
            f"Expected exactly 1 active INSPECTION alert after second eval "
            f"(dedup), got {len(truck_alerts_2)}"
        )
