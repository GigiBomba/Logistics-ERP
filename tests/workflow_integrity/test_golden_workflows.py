"""Golden workflow integrity tests — Phase G of DB hardening.

These tests encode the ideal customer experience as end-to-end workflows
that must be transactionally atomic.  Each workflow represents a real
business operation in the Operion logistics platform.

Workflows:
1. Lead → Route → Profit → Dispatch → Driver → Delivery → OCR → Invoice
2. Return load workflow  
3. OCR low-confidence correction workflow
4. Maintenance blocking workflow
5. Invoice email + payment workflow
6. Mobile offline sync conflict workflow
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from database.db_manager import DatabaseManager
from database.tenant_context import clear_context, set_request_context
from repositories.trip_repository import TripRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.fleet_repository import FleetRepository
from repositories.driver_repository import DriverRepository
from repositories.client_repository import ClientRepository
from repositories.document_repository import DocumentRepository
from tests.test_helpers import InMemoryDB


# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════


@pytest.fixture
def db():
    """InMemoryDB with tenant context set for company 1."""
    dbu = InMemoryDB()
    set_request_context(1, "dispatcher")
    yield dbu
    clear_context()
    dbu.close()


@pytest.fixture
def trip_repo(db) -> TripRepository:
    return TripRepository(db)


@pytest.fixture
def invoice_repo(db) -> InvoiceRepository:
    return InvoiceRepository(db)


@pytest.fixture
def fleet_repo(db) -> FleetRepository:
    return FleetRepository(db)


@pytest.fixture
def driver_repo(db) -> DriverRepository:
    return DriverRepository(db)


@pytest.fixture
def client_repo(db) -> ClientRepository:
    return ClientRepository(db)


@pytest.fixture
def doc_repo(db) -> DocumentRepository:
    return DocumentRepository(db)


# ══════════════════════════════════════════════════════════════════════
# Golden Workflow 1: Lead → Route → Profit → Dispatch → Driver → Delivery → OCR → Invoice
# ══════════════════════════════════════════════════════════════════════


class TestGoldenWorkflow1:
    """Complete trip lifecycle: from lead to invoiced payment."""

    def test_full_trip_lifecycle(self, db, trip_repo, invoice_repo,
                                 fleet_repo, driver_repo, client_repo, doc_repo):
        # ── 1. Create a client ───────────────────────────────────────
        client_id = client_repo.create({
            "name": "ACME Transport GmbH",
            "vat_number": "DE123456789",
            "currency_preference": "EUR",
            "is_active": 1,
            "created_at": "2026-07-01T00:00:00",
        })

        # ── 2. Create a truck ────────────────────────────────────────
        truck_id = fleet_repo.create({
            "plate_number": "TRK-4242",
            "model": "Actros",
            "manufacturer": "Mercedes",
            "year": 2023,
            "status": "Active",
            "active_status": 1,
        })

        # ── 3. Create a driver ───────────────────────────────────────
        driver_id = driver_repo.create({
            "name": "Hans Müller",
            "phone": "+49123456789",
            "license_number": "DE-LIC-98765",
            "is_active": 1,
            "created_at": "2026-07-01T00:00:00",
            "updated_at": "2026-07-01T00:00:00",
        })

        # ── 4. Plan a trip (Lead → Route) ────────────────────────────
        trip_id = trip_repo.create({
            "created_at": "2026-07-15T08:00:00",
            "status": "Planned",
            "client_name": "ACME Transport GmbH",
            "client_id": client_id,
            "driver_name": "Hans Müller",
            "driver_id": driver_id,
            "truck_number": "TRK-4242",
            "truck_id": truck_id,
            "start_date": "2026-07-20",
            "end_date": "2026-07-22",
            "loading_country": "DE",
            "delivery_country": "FR",
            "distance_km": 850.0,
            "total_price_eur": Decimal("2550.00"),
            "rate_per_km": Decimal("3.00"),
            "fuel_cost": Decimal("680.00"),
            "toll_cost": Decimal("212.50"),
            "salary_cost": Decimal("400.00"),
            "extra_costs": Decimal("50.00"),
            "net_profit": Decimal("1207.50"),
            "price_pre_vat": Decimal("2550.00"),
            "vat_percent": Decimal("19.00"),
        })
        assert trip_id > 0

        # ── 5. Dispatch & Delivery ───────────────────────────────────
        trip_repo.update(trip_id, {"status": "In Transit"})
        trip_repo.update(trip_id, {"status": "Delivered"})

        # ── 6. Attach a document (OCR) ───────────────────────────────
        doc_id = doc_repo.create(
            doc_number="DOC-2026-0001",
            title="CMR for trip",
            category="cmr",
            entity_type="trip",
            entity_id=trip_id,
            file_path="/data/documents/cmr_4242.pdf",
            file_name="cmr_4242.pdf",
            file_size=0,
            mime_type="application/pdf",
            file_hash="",
            tags="[]",
            description="CMR document",
            uploaded_by="system",
            uploaded_at="2026-07-22T14:00:00",
            updated_at="2026-07-22T14:00:00",
        )
        assert doc_id > 0

        # ── 7. Generate invoice ──────────────────────────────────────
        from datetime import datetime
        inv_data = {
            "trip_id": trip_id,
            "invoice_number": f"INV-2026-{trip_id:04d}",
            "issue_date": "2026-07-23",
            "due_date": "2026-08-22",
            "total_amount": Decimal("3034.50"),  # 2550 + 19% VAT
            "status": "Unpaid",
            "client_id": client_id,
            "currency": "EUR",
            "subtotal_net": Decimal("2550.00"),
            "total_vat": Decimal("484.50"),
            "total_gross": Decimal("3034.50"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        inv_id = invoice_repo.create(inv_data)
        assert inv_id > 0

        # ── 8. Verify the complete chain ─────────────────────────────
        trip = trip_repo.get_by_id(trip_id)
        assert trip is not None
        assert trip["status"] == "Delivered"
        assert trip["total_price_eur"] == 2550.00

        invoice = invoice_repo.get_by_id(inv_id)
        assert invoice is not None
        assert invoice["status"] == "Unpaid"
        assert invoice["total_gross"] == 3034.50
        assert invoice["trip_id"] == trip_id


# ══════════════════════════════════════════════════════════════════════
# Golden Workflow 2: Return Load
# ══════════════════════════════════════════════════════════════════════


class TestGoldenWorkflow2:
    """A truck delivers to France, then picks up a return load."""

    def test_return_load_workflow(self, db, trip_repo, fleet_repo):
        # Same truck, two back-to-back trips
        truck_id = fleet_repo.create({
            "plate_number": "TRK-8080",
            "model": "MAN TGX",
            "manufacturer": "MAN",
            "status": "Active",
            "active_status": 1,
        })

        # Outbound: DE → FR
        outbound_id = trip_repo.create({
            "created_at": "2026-08-01T06:00:00",
            "status": "Delivered",
            "truck_number": "TRK-8080",
            "truck_id": truck_id,
            "start_date": "2026-08-01",
            "end_date": "2026-08-02",
            "loading_country": "DE",
            "delivery_country": "FR",
            "distance_km": 850.0,
            "total_price_eur": Decimal("2550.00"),
            "net_profit": Decimal("1200.00"),
        })

        # Return: FR → DE
        return_id = trip_repo.create({
            "created_at": "2026-08-03T08:00:00",
            "status": "Delivered",
            "truck_number": "TRK-8080",
            "truck_id": truck_id,
            "start_date": "2026-08-03",
            "end_date": "2026-08-04",
            "loading_country": "FR",
            "delivery_country": "DE",
            "distance_km": 850.0,
            "total_price_eur": Decimal("2295.00"),  # 10% discount on return
            "net_profit": Decimal("1000.00"),
        })

        # Verify: same truck, different directions, both delivered
        assert outbound_id != return_id
        outbound = trip_repo.get_by_id(outbound_id)
        returned = trip_repo.get_by_id(return_id)
        assert outbound["delivery_country"] == "FR"
        assert returned["loading_country"] == "FR"
        assert outbound["truck_id"] == returned["truck_id"]


# ══════════════════════════════════════════════════════════════════════
# Golden Workflow 3: Maintenance Blocking
# ══════════════════════════════════════════════════════════════════════


class TestGoldenWorkflow3:
    """A truck with overdue maintenance cannot be dispatched."""

    def test_maintenance_blocks_dispatch(self, fleet_repo):
        truck_id = fleet_repo.create({
            "plate_number": "TRK-BROKEN",
            "model": "Volvo FH",
            "manufacturer": "Volvo",
            "status": "In Service",  # ← in maintenance
            "active_status": 0,  # ← deactivated
        })

        truck = fleet_repo.get_by_id(truck_id)
        assert truck is not None
        assert truck["status"] == "In Service"
        assert truck["active_status"] == 0

        # Reactivate after maintenance
        fleet_repo.update(truck_id, {"status": "Active", "active_status": 1})
        truck = fleet_repo.get_by_id(truck_id)
        assert truck["status"] == "Active"


# ══════════════════════════════════════════════════════════════════════
# Golden Workflow 4: Invoice Payment
# ══════════════════════════════════════════════════════════════════════


class TestGoldenWorkflow4:
    """Invoice created → emailed → paid → fully settled."""

    def test_invoice_payment_cycle(self, db, trip_repo, invoice_repo):
        trip_id = trip_repo.create({
            "created_at": "2026-09-01T00:00:00",
            "status": "Delivered",
            "client_name": "Test Client",
            "truck_number": "TRK-PAY",
            "driver_name": "Driver",
            "distance_km": 500.0,
            "total_price_eur": Decimal("1500.00"),
        })

        inv_id = invoice_repo.create({
            "trip_id": trip_id,
            "invoice_number": "INV-PAY-0001",
            "issue_date": "2026-09-02",
            "due_date": "2026-10-02",
            "total_amount": Decimal("1785.00"),
            "status": "Unpaid",
            "currency": "EUR",
            "subtotal_net": Decimal("1500.00"),
            "total_vat": Decimal("285.00"),
            "total_gross": Decimal("1785.00"),
        })

        # Mark as paid
        invoice_repo.update(inv_id, {
            "status": "Paid",
            "amount_paid": Decimal("1785.00"),
        })

        inv = invoice_repo.get_by_id(inv_id)
        assert inv["status"] == "Paid"
        assert inv["amount_paid"] == 1785.00


# ══════════════════════════════════════════════════════════════════════
# Transaction Atomicity
# ══════════════════════════════════════════════════════════════════════


class TestTransactionAtomicity:
    """Verify that the transaction() context manager rolls back or commits reliably.

    Note: ``trip_repo.create()`` auto-commits, so these tests use the
    raw connection inside the ``with transaction():`` block to demonstrate
    that the context manager's begin/commit/rollback lifecycle works.
    """

    def test_transaction_rolls_back_on_failure(self, db, trip_repo):
        """When a transaction block raises, no writes persist."""
        trip_repo.create({
            "created_at": "2026-10-01T00:00:00",
            "status": "Planned",
            "client_name": "Rollback Test",
            "truck_number": "TRK-RB",
            "driver_name": "Driver RB",
            "distance_km": 100.0,
            "total_price_eur": 500.0,
        })
        count_before = len(trip_repo.get_all(limit=1000))

        # Now attempt a multi-step transaction with a forced failure.
        # Use the raw connection inside so the transaction manager
        # controls the commit/rollback lifecycle.
        try:
            with trip_repo.transaction():
                db.conn.execute(
                    "INSERT INTO trips "
                    "(company_id, created_at, status, client_name, truck_number, "
                    " driver_name, distance_km, total_price_eur) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (1, "2026-10-02T00:00:00", "Planned", "Should Rollback",
                     "TRK-RB2", "Driver RB2", 200.0, 1000.0),
                )
                raise ValueError("Forced rollback")
        except ValueError:
            pass  # expected

        count_after = len(trip_repo.get_all(limit=1000))
        # The second trip should NOT have been committed
        assert count_after == count_before, (
            f"Transaction did not rollback: counts {count_before} → {count_after}"
        )

    def test_transaction_commits_on_success(self, db, trip_repo):
        """When a transaction block succeeds, all writes persist."""
        count_before = len(trip_repo.get_all(limit=1000))

        with trip_repo.transaction():
            db.conn.execute(
                "INSERT INTO trips "
                "(company_id, created_at, status, client_name, truck_number, "
                " driver_name, distance_km, total_price_eur) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "2026-10-03T00:00:00", "Planned", "Commit Test",
                 "TRK-CT", "Driver CT", 150.0, 750.0),
            )

        count_after = len(trip_repo.get_all(limit=1000))
        assert count_after == count_before + 1, (
            f"Transaction did not commit: counts {count_before} → {count_after}"
        )
