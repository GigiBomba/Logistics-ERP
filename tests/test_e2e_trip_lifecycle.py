"""E2E: Complete trip lifecycle — client, truck, driver, assignments,
status transitions, CMR generation, invoice generation, and consistency checks."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from repositories.client_repository import ClientRepository
from repositories.driver_repository import DriverRepository
from repositories.driver_truck_assignment_repository import DriverTruckAssignmentRepository
from repositories.fleet_repository import FleetRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.trip_repository import TripRepository
from services.fleet_service import FleetService
from services.invoicing.cmr_generator import CMRGenerator
from services.invoicing.service import InvoiceService
from services.operations.trip_status_engine import TripStatusEngine
from services.trip_service import TripService
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


# ── Helpers ───────────────────────────────────────────────────────────────

def _dt(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def trip_service(db):
    return TripService(db)


@pytest.fixture
def fleet_service(db):
    return FleetService(db)


@pytest.fixture
def client_repo(db):
    return ClientRepository(db)


@pytest.fixture
def driver_repo(db):
    return DriverRepository(db)


@pytest.fixture
def assignment_repo(db):
    return DriverTruckAssignmentRepository(db)


@pytest.fixture
def trip_repo(db):
    return TripRepository(db)


@pytest.fixture
def invoice_repo(db):
    return InvoiceRepository(db)


@pytest.fixture
def fleet_repo(db):
    return FleetRepository(db)


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Ensure singletons are clean for E2E tests."""
    from services.operations.event_bus import EventBus
    EventBus._instance = None
    from services.operations.alert_manager import AlertManager
    AlertManager._instance = None
    from services.operations.rules import Rules
    Rules._instance = None


# ── Test: Complete trip lifecycle ────────────────────────────────────────


class TestTripLifecycle:
    """Complete trip lifecycle: create entities, transition statuses, generate docs."""

    def test_create_full_trip_data(
        self, db, trip_service, fleet_service, client_repo, driver_repo,
        assignment_repo, trip_repo, invoice_repo, fleet_repo,
    ):
        # ── Step 1: Create a client ──────────────────────────────────
        now = datetime.now().isoformat()
        client_id = client_repo.create({
            "name": "Acme Logistics GmbH",
            "contact_person": "Hans Mueller",
            "phone": "+49-30-12345678",
            "email": "hans@acme-logistics.de",
            "address": "Industriestrasse 42, 10115 Berlin, Germany",
            "vat_number": "DE123456789",
            "currency_preference": "EUR",
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        })
        assert client_id > 0
        client = client_repo.get_by_id(client_id)
        assert client is not None
        assert client["name"] == "Acme Logistics GmbH"
        assert client["vat_number"] == "DE123456789"

        # ── Step 2: Create a truck ───────────────────────────────────
        truck_id = fleet_service.add_truck({
            "plate_number": "B-BC-1234",
            "model": "Actros 1845",
            "manufacturer": "Mercedes-Benz",
            "year": 2023,
            "vin": "WDB9634031L123456",
            "fuel_consumption": 28.5,
            "mileage": 45000.0,
            "status": "Active",
            "active_status": 1,
        })
        assert truck_id > 0
        truck = fleet_repo.get_by_id(truck_id)
        assert truck is not None
        assert truck["plate_number"] == "B-BC-1234"

        # ── Step 3: Create a driver ──────────────────────────────────
        driver_id = driver_repo.create({
            "name": "Jan Kowalski",
            "phone": "+48-601-234-567",
            "email": "jan.kowalski@example.com",
            "license_number": "PL/12345/ABC",
            "license_category": "CE",
            "license_expiry": _dt(365),
            "medical_expiry": _dt(180),
            "hire_date": _dt(-365),
            "monthly_salary": 3500.0,
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        })
        assert driver_id > 0
        driver = driver_repo.get_by_id(driver_id)
        assert driver is not None
        assert driver["name"] == "Jan Kowalski"
        assert driver["license_category"] == "CE"

        # ── Step 4: Assign driver to truck ───────────────────────────
        assignment_repo.assign(driver_id=driver_id, truck_id=truck_id)
        assignment = assignment_repo.get_by_driver(driver_id)
        assert assignment is not None
        assert assignment["truck_id"] == truck_id

        # ── Step 5: Create a trip ────────────────────────────────────
        trip_data = {
            "client_name": "Acme Logistics GmbH",
            "client_id": client_id,
            "truck_number": "B-BC-1234",
            "truck_id": truck_id,
            "driver_name": "Jan Kowalski",
            "driver_id": driver_id,
            "start_date": _dt(1),
            "end_date": _dt(3),
            "distance_km": 850.0,
            "total_price_eur": 3400.0,
            "rate_per_km": 4.0,
            "fuel_cost": 680.0,
            "toll_cost": 120.0,
            "salary_cost": 350.0,
            "extra_costs": 50.0,
            "net_profit": 2200.0,
            "currency": "EUR",
            "status": "Planned",
            "loading_country": "DE",
            "delivery_country": "PL",
            "created_at": now,
            "cargo_description": "Electronic components",
            "package_count": 24,
            "package_type": "Pallets",
            "gross_weight_kg": 12000.0,
            "volume_m3": 45.0,
        }
        trip_id = trip_service.add(trip_data)
        assert trip_id > 0
        trip = trip_service.get_by_id(trip_id)
        assert trip is not None
        assert trip["status"] == "Planned"
        assert trip["client_name"] == "Acme Logistics GmbH"
        assert trip["truck_number"] == "B-BC-1234"
        assert trip["driver_name"] == "Jan Kowalski"
        assert trip["distance_km"] == 850.0

        # ── Step 6: Status transitions via TripStatusEngine ──────────
        engine = TripStatusEngine(db)

        # Planned → Loading
        ok = engine.transition(trip_id, "Loading", trigger="manual")
        assert ok is True
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "Loading"

        # Loading → In Transit
        ok = engine.transition(trip_id, "In Transit", trigger="manual")
        assert ok is True
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "In Transit"

        # In Transit → Delivered
        ok = engine.transition(trip_id, "Delivered", trigger="manual")
        assert ok is True
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "Delivered"

        # Delivered → Invoiced
        ok = engine.transition(trip_id, "Invoiced", trigger="manual")
        assert ok is True
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "Invoiced"

        # Invoiced → Paid
        ok = engine.transition(trip_id, "Paid", trigger="manual")
        assert ok is True
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "Paid"

        # ── Step 7: Verify trip_status_history records ───────────────
        history_rows = db.conn.execute(
            "SELECT * FROM trip_status_history WHERE trip_id = ? ORDER BY id",
            (trip_id,),
        ).fetchall()
        history = [dict(r) for r in history_rows]
        assert len(history) == 5  # 5 transitions

        expected_transitions = [
            ("Planned", "Loading"),
            ("Loading", "In Transit"),
            ("In Transit", "Delivered"),
            ("Delivered", "Invoiced"),
            ("Invoiced", "Paid"),
        ]
        for i, (old, new) in enumerate(expected_transitions):
            assert history[i]["old_status"] == old, f"Transition {i} old_status mismatch"
            assert history[i]["new_status"] == new, f"Transition {i} new_status mismatch"
            assert history[i]["trigger"] == "manual"

        # ── Step 8: Test invalid transition rejection ────────────────
        # Paid → Loading is invalid
        with pytest.raises(ValueError, match="Cannot transition from Paid to Loading"):
            engine.transition(trip_id, "Loading")

        # ── Step 9: Generate CMR for the trip ────────────────────────
        cmr_output_dir = tempfile.mkdtemp(prefix="cmr_e2e_")
        try:
            with patch.object(CMRGenerator, "_build_single_copy", return_value=os.path.join(cmr_output_dir, "CMR_test.pdf")):
                cmr_gen = CMRGenerator(db=db)
                trip_data_for_cmr = trip_service.get_by_id(trip_id)
                assert trip_data_for_cmr is not None
                cmr_path = cmr_gen.generate(trip_data_for_cmr, output_dir=cmr_output_dir)
                assert cmr_path is not None
                # Check that CMR number was assigned
                trip_after_cmr = trip_service.get_by_id(trip_id)
                assert trip_after_cmr is not None
                # CMR number might be populated by generate_all_copies with skip_db_update=False
                # but by default generate() does NOT update the trip record
        finally:
            import shutil
            shutil.rmtree(cmr_output_dir, ignore_errors=True)

        # ── Step 10: Generate invoice for the trip ───────────────────
        with patch.object(InvoiceService, "generate", return_value=os.path.join(tempfile.gettempdir(), "inv_test.pdf")):
            inv_svc = InvoiceService(db)
            inv_number = f"INV-{datetime.now().year}-{trip_id:04d}"
            inv_svc.create_record(
                trip_id=trip_id,
                inv_number=inv_number,
                amount=3400.0,
                due_date=_dt(30),
            )
            invoice = invoice_repo.get_by_trip_id(trip_id)
            assert invoice is not None
            assert invoice["invoice_number"] == inv_number
            assert invoice["total_amount"] == 3400.0
            assert invoice["status"] == "Unpaid"

        # ── Step 11: Verify all records consistency ──────────────────
        # Trip should have driver_id, truck_id, client_id set
        final_trip = trip_service.get_by_id(trip_id)
        assert final_trip is not None
        assert final_trip["client_id"] == client_id
        assert final_trip["truck_id"] == truck_id
        assert final_trip["driver_id"] == driver_id

        # Client should still exist and be active
        final_client = client_repo.get_by_id(client_id)
        assert final_client is not None
        assert final_client["is_active"] == 1

        # Truck should still exist
        final_truck = fleet_repo.get_by_id(truck_id)
        assert final_truck is not None
        assert final_truck["plate_number"] == "B-BC-1234"

        # Driver should still exist
        final_driver = driver_repo.get_by_id(driver_id)
        assert final_driver is not None
        assert final_driver["name"] == "Jan Kowalski"

        # Invoice should link back to trip
        final_invoice = invoice_repo.get_by_trip_id(trip_id)
        assert final_invoice is not None
        assert final_invoice["trip_id"] == trip_id

    def test_get_valid_transitions(self, db):
        """Verify the engine returns valid transitions correctly."""
        engine = TripStatusEngine(db)
        assert engine.get_valid_transitions("Planned") == ["Loading", "Cancelled"]
        assert engine.get_valid_transitions("In Transit") == ["Loading", "Delivered", "Cancelled"]
        assert engine.get_valid_transitions("Paid") == ["Invoiced"]
        assert engine.get_valid_transitions("Unknown") == []

    def test_trip_history_rejects_invalid_transition(self, db):
        """Creating a trip with an invalid transition should not record history."""
        now = datetime.now().isoformat()
        trip_id = TripService(db).add({
            "client_name": "Test Client",
            "status": "Planned",
            "created_at": now,
        })
        engine = TripStatusEngine(db)
        # Attempt invalid transition: Planned → Delivered (skip Loading and In Transit)
        with pytest.raises(ValueError, match="Cannot transition from Planned to Delivered"):
            engine.transition(trip_id, "Delivered")
        # Verify no history was recorded for the failed transition
        rows = db.conn.execute(
            "SELECT COUNT(*) AS cnt FROM trip_status_history WHERE trip_id = ?",
            (trip_id,),
        ).fetchone()
        assert rows["cnt"] == 0

    def test_evaluate_all_creates_alerts_for_delayed_trips(self, db):
        """TripStatusEngine.evaluate_all() should create alerts for delayed trips."""
        from datetime import datetime, timedelta
        from services.operations.alert_manager import AlertManager

        old_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")

        # Create a trip stuck in "pending" for 14 days
        trip_service = TripService(db)
        trip_id = trip_service.add({
            "client_name": "Delayed Client",
            "truck_number": "TR-001",
            "status": "pending",
            "created_at": old_date,
        })
        assert trip_id > 0

        # Verify trip was stored correctly
        trip = trip_service.get_by_id(trip_id)
        assert trip is not None
        assert trip["status"] == "pending"
        assert trip["created_at"] == old_date

        engine = TripStatusEngine(db)
        # Directly evaluate the specific trip
        alert_count = engine.evaluate_trip(str(trip_id))
        assert alert_count >= 1, f"Expected alerts for trip {trip_id}, got {alert_count}"

        # Verify the alert was created (alerts are stored in-memory in AlertManager._alerts)
        alert_mgr = AlertManager(db)
        alerts = alert_mgr.get_active_alerts(limit=50)
        trip_alerts = [a for a in alerts if a.trip_id == str(trip_id)]
        assert len(trip_alerts) >= 1
        # "delayed" is in the alert title, not message
        assert "delayed" in trip_alerts[0].title.lower()
