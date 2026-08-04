"""WorkflowEnvironment — convenience wrapper around test DB + services.

Holds references to all services and provides helper methods for
common workflow operations that tests need repeatedly (seeding
a company, creating a trip, transitioning status, etc.).

Usage::

    def test_golden_flow(workflow_env):
        company_id = workflow_env.seed_company("Test Co")
        trip_id = workflow_env.create_trip(
            company_id=company_id,
            client_name="Client A",
            status="Planned",
        )
        workflow_env.transition_status(trip_id, "Loading")
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from models.trip_models import TripCreate


_TODAY = date.today()
_NOW = datetime.now().isoformat()


class WorkflowEnvironment:
    """Thin integration wrapper over the test DB and service layer.

    Provided via pytest fixture so tests don't need to manually
    import repositories or write raw SQL for common setup steps.
    """

    def __init__(self, db, trip_service, invoice_service, event_bus,
                 alert_manager, operations_engine) -> None:
        self.db = db
        self.trip_service = trip_service
        self.invoice_service = invoice_service
        self.event_bus = event_bus
        self.alert_manager = alert_manager
        self.operations_engine = operations_engine

    # ── Quick seed helpers ──────────────────────────────────────

    def seed_company(self, name: str, tier: str = "starter") -> int:
        """Create a company row and return its id."""
        self.db.conn.execute(
            "INSERT INTO companies (company_name, subscription_tier, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (name, tier, _NOW, _NOW),
        )
        self.db.conn.commit()
        return self.db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def seed_client(self, name: str, **overrides: Any) -> int:
        """Create a client row and return its id."""
        defaults = {
            "email": f"{name.lower().replace(' ', '_')}@example.com",
            "phone": "+40-700-000-000",
            "address": "Test Street 1",
            "vat_number": f"RO-TEST-{name[:4].upper()}",
        }
        defaults.update(overrides)
        self.db.conn.execute(
            "INSERT INTO clients (name, email, phone, address, vat_number, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
            (name, defaults["email"], defaults["phone"],
             defaults["address"], defaults["vat_number"], _NOW, _NOW),
        )
        self.db.conn.commit()
        return self.db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def seed_truck(self, plate: str, **overrides: Any) -> int:
        """Create a truck row and return its id."""
        defaults = {
            "manufacturer": "Volvo",
            "model": "FH 460",
            "year": 2022,
            "mileage": 0.0,
        }
        defaults.update(overrides)
        self.db.conn.execute(
            "INSERT INTO trucks (plate_number, manufacturer, model, year, mileage, status, active_status) "
            "VALUES (?, ?, ?, ?, ?, 'active', 1)",
            (plate, defaults["manufacturer"], defaults["model"],
             defaults["year"], defaults["mileage"]),
        )
        self.db.conn.commit()
        return self.db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def seed_user(self, company_id: int, display_name: str = "Test User",
                  email: str = "test@example.com", role: str = "dispatcher") -> int:
        """Create a user row and return its id."""
        self.db.conn.execute(
            "INSERT INTO users (company_id, display_name, email, password_hash, role, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (company_id, display_name, email, "hash", role, _NOW),
        )
        self.db.conn.commit()
        return self.db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def seed_driver(self, company_id: int, name: str, **overrides: Any) -> int:
        """Create a driver row and return its id."""
        defaults = {
            "license_number": f"LIC-{name.replace(' ', '-')}",
            "phone": "+40-700-111-111",
            "email": f"{name.lower().replace(' ', '.')}@example.com",
        }
        defaults.update(overrides)
        self.db.conn.execute(
            "INSERT INTO drivers (company_id, name, license_number, phone, email, "
            "is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
            (company_id, name, defaults["license_number"],
             defaults["phone"], defaults["email"], _NOW, _NOW),
        )
        self.db.conn.commit()
        return self.db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # ── Workflow actions ────────────────────────────────────────

    def create_trip(self, **overrides: Any) -> int:
        """Create a trip via TripService and return the new id.

        If ``client_id`` is not provided, a default client is
        auto-created so the TripService validation passes.
        """
        if "client_id" not in overrides:
            client_id = self.seed_client("Auto Client")
            overrides["client_id"] = client_id
        defaults = {
            "client_name": "Test Client",
            "driver_name": "Test Driver",
            "truck_plate": "AB-123-CD",
            "distance_km": 500.0,
            "price_eur": 1500.0,
            "status": "Planned",
            "start_date": _TODAY.isoformat(),
            "end_date": (_TODAY + timedelta(days=3)).isoformat(),
            "fuel_cost": 150.0,
            "toll_cost": 50.0,
            "salary_cost": 300.0,
            "extra_costs": 0.0,
            "net_profit": 1000.0,
            "rate_per_km": 3.0,
            "gross_per_km": 2.0,
            "currency": "EUR",
        }
        defaults.update(overrides)
        request = TripCreate(**defaults)
        result = self.trip_service.create(request)
        return result.data.id

    def transition_status(self, trip_id: int, new_status: str) -> bool:
        """Transition a trip to a new status via OperationsEngine."""
        return self.operations_engine.force_trip_status(trip_id, new_status)

    def get_trip(self, trip_id: int) -> dict | None:
        """Retrieve a trip dict by id."""
        return self.trip_service.get_by_id(trip_id)
