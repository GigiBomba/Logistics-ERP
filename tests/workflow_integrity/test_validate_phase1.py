"""Phase 1 infrastructure validation test."""

from __future__ import annotations

import pytest
from tests.test_helpers import make_db
from tests.workflow_integrity.personas import (
    build_ana_persona,
    build_andrei_persona,
    build_elena_persona,
    build_ionut_persona,
    build_marius_persona,
    build_mihai_persona,
)
from services.operations.event_bus import EventBus
from services.trip_service import TripService


class TestPersonaDataIntegrity:
    """Verify all 6 persona builders produce valid, queryable data."""

    def test_ionut_persona(self):
        db = make_db()
        ids = build_ionut_persona(db)
        svc = TripService(db)
        # Verify delivered trip
        t = svc.get_by_id(ids["trip_ids"]["delivered"])
        assert t is not None, "Delivered trip not found"
        assert t["status"] == "Delivered"
        assert t["driver_name"] == "Ionut Popescu"
        assert t["truck_number"] == "CJ-01-ION"
        # Verify all 3 trips
        for key in ("planned", "in_transit", "delivered"):
            assert svc.get_by_id(ids["trip_ids"][key]) is not None, f"{key} trip missing"

    def test_mihai_persona(self):
        db = make_db()
        ids = build_mihai_persona(db)
        assert len(ids["driver_ids"]) == 5
        assert len(ids["truck_ids"]) == 5
        assert len(ids["owned_truck_ids"]) == 3
        assert len(ids["leased_truck_ids"]) == 2
        assert len(ids["trip_ids"]) == 5

    def test_ana_persona(self):
        db = make_db()
        ids = build_ana_persona(db)
        assert len(ids["driver_ids"]) == 12
        assert len(ids["truck_ids"]) == 10
        assert len(ids["trip_ids"]) == 15
        assert len(ids["user_ids"]) == 3

    def test_andrei_persona(self):
        db = make_db()
        ids = build_andrei_persona(db)
        assert len(ids["driver_ids"]) == 30
        assert len(ids["truck_ids"]) == 25
        assert len(ids["trip_ids"]) == 40

    def test_elena_persona(self):
        db = make_db()
        ids = build_elena_persona(db)
        assert len(ids["trip_ids"]["delivered"]) == 5
        assert len(ids["trip_ids"]["invoiced"]) == 3
        assert len(ids["trip_ids"]["paid"]) == 2

    def test_marius_persona(self):
        db = make_db()
        ids = build_marius_persona(db)
        assert len(ids["driver_ids"]) == 20
        assert len(ids["truck_ids"]) == 20
        assert len(ids["trip_ids"]) == 30


class TestEventMonitor:
    """Verify EventMonitor works with EventBus."""

    def test_track_and_assert(self):
        bus = EventBus()
        if hasattr(bus, "_instance"):
            bus.__class__._instance = None
        bus = EventBus()
        bus.reset()
        bus.inject_db(None)

        from tests.workflow_integrity.fixtures.event_monitor import EventMonitor
        monitor = EventMonitor(bus)
        monitor.track("trip.status_changed")

        bus.publish("trip.status_changed", {"status": "Delivered", "id": 42})
        monitor.assert_event_published("trip.status_changed", data={"status": "Delivered"})

    def test_assert_not_published(self):
        bus = EventBus()
        if hasattr(bus, "_instance"):
            bus.__class__._instance = None
        bus = EventBus()
        bus.reset()

        from tests.workflow_integrity.fixtures.event_monitor import EventMonitor
        monitor = EventMonitor(bus)
        monitor.track("invoice.created")
        bus.publish("trip.status_changed", {})
        monitor.assert_event_not_published("invoice.created")

    def test_assert_event_sequence(self):
        bus = EventBus()
        if hasattr(bus, "_instance"):
            bus.__class__._instance = None
        bus = EventBus()
        bus.reset()

        from tests.workflow_integrity.fixtures.event_monitor import EventMonitor
        monitor = EventMonitor(bus)
        monitor.track_all()
        bus.publish("trip.created", {})
        bus.publish("trip.status_changed", {})
        bus.publish("invoice.created", {})
        monitor.assert_event_sequence("trip.created", "trip.status_changed", "invoice.created")


class TestWorkflowEnvironment:
    """Verify WorkflowEnvironment seed helpers."""

    def test_seed_company_and_trip(self):
        db = make_db()

        from services.invoicing.service import InvoiceService
        from services.operations.alert_manager import AlertManager
        from services.operations.operations_engine import OperationsEngine
        from services.trip_service import TripService
        from tests.workflow_integrity.fixtures.workflow_environment import WorkflowEnvironment

        bus = EventBus()
        if hasattr(bus, "_instance"):
            bus.__class__._instance = None
        bus = EventBus()
        bus.reset()
        bus.inject_db(db)

        ts = TripService(db)
        engine = OperationsEngine.create(db=db, event_bus=bus, alert_mgr=AlertManager(db), trip_service=ts)
        env = WorkflowEnvironment(db=db, trip_service=ts, invoice_service=InvoiceService(db),
                                  event_bus=bus, alert_manager=AlertManager(db), operations_engine=engine)

        company_id = env.seed_company("Validity Test")
        assert company_id > 0

        client_id = env.seed_client("Test Client")
        assert client_id > 0

        truck_id = env.seed_truck("XX-999-TEST")
        assert truck_id > 0

        driver_id = env.seed_driver(company_id, "Test Driver")
        assert driver_id > 0

        trip_id = env.create_trip(status="Planned")
        assert trip_id > 0

        trip = env.get_trip(trip_id)
        assert trip is not None
        assert trip["status"] == "Planned"
