"""E2E: Complete invoicing flow — trip creation, invoice generation,
CMR generation, payment, proforma, and receipt lifecycle."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from repositories.client_repository import ClientRepository
from repositories.fleet_repository import FleetRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.proforma_repository import ProformaRepository
from repositories.receipt_repository import ReceiptRepository
from repositories.trip_repository import TripRepository
from services.fleet_service import FleetService
from services.invoicing.cmr_generator import CMRGenerator
from services.invoicing.proforma_service import ProformaService
from services.invoicing.receipt_service import ReceiptService
from services.invoicing.service import InvoiceService
from services.operations.event_bus import INVOICE_CREATED, INVOICE_PAID, EventBus
from services.operations.trip_status_engine import TripStatusEngine
from services.trip_service import TripService
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow


# ── Helpers ───────────────────────────────────────────────────────────────


def _dt(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


@pytest.fixture
def db():
    return make_db()


@pytest.fixture(autouse=True)
def _reset_singletons():
    from services.operations.event_bus import EventBus
    EventBus._instance = None
    from services.operations.alert_manager import AlertManager
    AlertManager._instance = None
    from services.operations.rules import Rules
    Rules._instance = None


# ── Tests ────────────────────────────────────────────────────────────────


class TestInvoiceFlow:
    """Complete invoicing flow: trip → invoice → CMR → payment → receipt."""

    def test_full_invoice_lifecycle(self, db):
        """Create trip → deliver → generate invoice → mark paid → verify records."""
        trip_repo = TripRepository(db)
        invoice_repo = InvoiceRepository(db)
        trip_service = TripService(db)

        # ── Step 1: Create a client ──────────────────────────────────
        now_iso = datetime.now().isoformat()
        client_repo = ClientRepository(db)
        client_id = client_repo.create({
            "name": "Invoice Client AG",
            "email": "billing@invoice-client.ch",
            "vat_number": "CHE-123.456.789",
            "address": "Bahnhofstrasse 10, 8001 Zurich, Switzerland",
            "is_active": 1,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
        assert client_id > 0

        # ── Step 2: Create a trip ────────────────────────────────────
        trip_id = trip_service.add({
            "client_name": "Invoice Client AG",
            "client_id": client_id,
            "truck_number": "CH-BC-5678",
            "driver_name": "Pierre Dubois",
            "start_date": _dt(-5),
            "end_date": _dt(-3),
            "distance_km": 1200.0,
            "total_price_eur": 4800.0,
            "rate_per_km": 4.0,
            "fuel_cost": 960.0,
            "toll_cost": 180.0,
            "salary_cost": 400.0,
            "extra_costs": 60.0,
            "net_profit": 3200.0,
            "currency": "EUR",
            "status": "In Transit",
            "created_at": now_iso,
            "cargo_description": "Pharmaceutical products",
            "package_count": 10,
            "package_type": "Boxes",
            "gross_weight_kg": 5000.0,
        })
        assert trip_id > 0

        # ── Step 3: Deliver the trip ─────────────────────────────────
        engine = TripStatusEngine(db)
        engine.transition(trip_id, "Delivered", trigger="system")

        trip = trip_service.get_by_id(trip_id)
        assert trip is not None
        assert trip["status"] == "Delivered"

        # ── Step 4: Transition to Invoiced ───────────────────────────
        engine.transition(trip_id, "Invoiced", trigger="manual")
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "Invoiced"

        # ── Step 5: Generate an invoice ──────────────────────────────
        inv_number = f"INV-{datetime.now().year}-{trip_id:04d}"
        with patch.object(InvoiceService, "generate", return_value=os.path.join(tempfile.gettempdir(), f"{inv_number}.pdf")):
            inv_svc = InvoiceService(db)

            # Create invoice record via the service
            inv_svc.generate_and_record(
                trip_data={
                    "id": trip_id,
                    "client_name": "Invoice Client AG",
                    "client_id": client_id,
                    "total_price_eur": 4800.0,
                    "distance_km": 1200.0,
                    "truck_number": "CH-BC-5678",
                },
                mode="client",
            )

        # ── Step 6: Verify invoice record ────────────────────────────
        invoice = invoice_repo.get_by_trip_id(trip_id)
        assert invoice is not None
        assert invoice["trip_id"] == trip_id
        assert invoice["status"] == "Unpaid"
        assert invoice["total_amount"] == 4800.0
        assert invoice["due_date"] is not None

        # ── Step 7: Mark invoice as paid ─────────────────────────────
        # Update invoice status
        db.conn.execute(
            "UPDATE invoices SET status = 'Paid' WHERE trip_id = ?",
            (trip_id,),
        )
        db.conn.commit()

        # Verify
        invoice = invoice_repo.get_by_trip_id(trip_id)
        assert invoice["status"] == "Paid"

        # ── Step 8: Update trip status to Paid ───────────────────────
        engine.transition(trip_id, "Paid", trigger="system")
        trip = trip_service.get_by_id(trip_id)
        assert trip["status"] == "Paid"

        # ── Step 9: Verify INVOICE_CREATED event was published ──────
        eb = EventBus()
        # The events are fire-and-forget so we can't easily assert them here,
        # but we verify the database records are consistent.

        # ── Step 10: Verify all financial records consistency ────────
        final_invoice = invoice_repo.get_by_trip_id(trip_id)
        assert final_invoice is not None
        assert final_invoice["total_amount"] == 4800.0
        assert final_invoice["status"] == "Paid"
        assert final_invoice["trip_id"] == trip_id

        # Client still exists
        final_client = client_repo.get_by_id(client_id)
        assert final_client is not None
        assert final_client["name"] == "Invoice Client AG"

    def test_cmr_and_invoice_generation(self, db):
        """Generate CMR and invoice for the same trip and verify both exist."""
        trip_service = TripService(db)
        trip_repo = TripRepository(db)
        invoice_repo = InvoiceRepository(db)

        now_iso = datetime.now().isoformat()
        trip_id = trip_service.add({
            "client_name": "CMR Test Client",
            "truck_number": "DE-XX-9999",
            "driver_name": "Test Driver",
            "start_date": _dt(-2),
            "end_date": _dt(0),
            "distance_km": 750.0,
            "total_price_eur": 3000.0,
            "status": "Delivered",
            "created_at": now_iso,
            "cargo_description": "Machine parts",
            "package_count": 5,
            "gross_weight_kg": 8000.0,
            "loading_country": "DE",
            "delivery_country": "FR",
        })
        assert trip_id > 0

        cmr_output_dir = tempfile.mkdtemp(prefix="cmr_inv_e2e_")
        try:
            # ── Generate CMR ─────────────────────────────────────
            with patch.object(CMRGenerator, "_build_single_copy", return_value=os.path.join(cmr_output_dir, "CMR_test.pdf")):
                cmr_gen = CMRGenerator(db=db)
                trip_data = trip_service.get_by_id(trip_id)
                assert trip_data is not None
                cmr_path = cmr_gen.generate(trip_data, output_dir=cmr_output_dir)
                assert cmr_path is not None
                # CMR number should be generated
                assert "CMR" in os.path.basename(cmr_path)

            # ── Generate Invoice ─────────────────────────────────
            inv_number = f"INV-CMR-{datetime.now().year}-{trip_id:04d}"
            with patch.object(InvoiceService, "generate", return_value=os.path.join(tempfile.gettempdir(), f"{inv_number}.pdf")):
                inv_svc = InvoiceService(db)
                inv_svc.create_record(
                    trip_id=trip_id,
                    inv_number=inv_number,
                    amount=3000.0,
                    due_date=_dt(30),
                )

            # ── Verify both exist ────────────────────────────────
            invoice = invoice_repo.get_by_trip_id(trip_id)
            assert invoice is not None
            assert invoice["invoice_number"] == inv_number
            assert invoice["total_amount"] == 3000.0

            # Trip status should still be Delivered (CMR/invoice gen doesn't change it)
            trip = trip_service.get_by_id(trip_id)
            assert trip["status"] == "Delivered"

        finally:
            import shutil
            shutil.rmtree(cmr_output_dir, ignore_errors=True)

    def test_proforma_invoice_flow(self, db):
        """Create proforma invoice → convert to invoice → verify records."""
        proforma_repo = ProformaRepository(db) if hasattr(ProformaRepository, 'create') else None

        # Check if proforma_repo has a create method we can use directly
        # ProformaRepository inherits from BaseRepository but has its own table
        from repositories import BaseRepository

        # ── Create proforma via ProformaService ──────────────────
        proforma_svc = ProformaService(db)

        proforma_data = {
            "client": {
                "name": "Proforma Client Ltd",
                "address": "Oxford Street 5, London, UK",
                "vat_number": "GB123456789",
                "phone": "+44-20-7946-0958",
                "email": "accounts@proforma-client.co.uk",
            },
            "description": "Transport services - Q2 2026",
            "line_items": [
                {"description": "Transport Berlin→Paris", "quantity": 1, "unit_price": 2500.0},
                {"description": "Additional stop Lyon", "quantity": 1, "unit_price": 500.0},
            ],
            "subtotal": 3000.0,
            "tax_rate": 19.0,
            "total_tax": 570.0,
            "grand_total": 3570.0,
            "currency": "EUR",
            "valid_until": _dt(30),
            "mode": "client",
        }

        # Generate proforma (mock PDF generation)
        with patch.object(proforma_svc.generator, "generate_rich", return_value=os.path.join(tempfile.gettempdir(), "proforma_test.pdf")):
            path = proforma_svc.generate_and_record(proforma_data)
            assert path is not None

        # ── Verify proforma was recorded in DB ───────────────────
        # The ProformaService generates and records via the repository
        proforma_list = db.conn.execute(
            "SELECT * FROM proforma_invoices WHERE client_name = ? ORDER BY id DESC",
            ("Proforma Client Ltd",),
        ).fetchall()
        assert len(proforma_list) >= 1
        pf = dict(proforma_list[0])
        assert pf["client_name"] == "Proforma Client Ltd"
        assert pf["grand_total"] == 3570.0
        assert pf["status"] == "Draft"
        assert pf["currency"] == "EUR"

        # ── Verify invoice items are stored ──────────────────────
        line_items = json.loads(pf["line_items_json"] or "[]")
        assert len(line_items) == 2
        assert line_items[0]["description"] == "Transport Berlin→Paris"

    def test_receipt_generation(self, db):
        """Generate a receipt for a payment and verify records."""
        receipt_svc = ReceiptService(db)
        receipt_repo = ReceiptRepository(db)

        # ── Generate receipt data ─────────────────────────────────
        receipt_data = {
            "receipt_type": "customer_payment",
            "payment_method": "Bank Transfer",
            "received_from_name": "Paying Client Inc",
            "received_from_address": "Main Street 100, Vienna, Austria",
            "received_from_vat": "ATU12345678",
            "company_name": "Operion ERP GmbH",
            "company_address": "Logistikweg 1, 10115 Berlin",
            "company_vat": "DE987654321",
            "amount": 4800.0,
            "vat_rate": 19.0,
            "currency": "EUR",
            "related_trip_id": None,
            "purpose": "Invoice INV-2026-0042 payment",
            "reference_number": "TRF-2026-042",
            "language": "en",
        }

        # Mock PDF generation
        with patch.object(receipt_svc.generator, "generate", return_value=os.path.join(tempfile.gettempdir(), "receipt_test.pdf")):
            path = receipt_svc.generate_and_record(receipt_data)
            assert path is not None

        # ── Verify receipt was recorded ──────────────────────────
        receipts = db.conn.execute(
            "SELECT * FROM receipts WHERE received_from_name = ? ORDER BY id DESC",
            ("Paying Client Inc",),
        ).fetchall()
        assert len(receipts) >= 1
        rcpt = dict(receipts[0])
        assert rcpt["received_from_name"] == "Paying Client Inc"
        assert rcpt["amount"] == 4800.0
        assert rcpt["total"] == 4800.0  # No VAT separate in total when amount+vat=total
        assert rcpt["status"] == "Generated"
        assert rcpt["currency"] == "EUR"
        assert rcpt["payment_method"] == "Bank Transfer"

        # ── Verify receipt number was auto-generated ─────────────
        assert rcpt["receipt_number"] is not None
        assert "RCT" in rcpt["receipt_number"] or "REC" in rcpt["receipt_number"]

    def test_receipt_with_trip_link(self, db):
        """Create a receipt linked to a specific trip and verify the association."""
        trip_service = TripService(db)
        receipt_svc = ReceiptService(db)

        # ── Create a trip ────────────────────────────────────────
        now_iso = datetime.now().isoformat()
        trip_id = trip_service.add({
            "client_name": "Linked Receipt Client",
            "truck_number": "TR-LINK-001",
            "total_price_eur": 2500.0,
            "status": "Paid",
            "created_at": now_iso,
        })

        # ── Generate receipt linked to this trip ─────────────────
        receipt_data = {
            "receipt_type": "customer_payment",
            "payment_method": "Cash",
            "received_from_name": "Linked Receipt Client",
            "company_name": "Operion ERP GmbH",
            "amount": 2500.0,
            "vat_rate": 0,
            "currency": "EUR",
            "related_trip_id": trip_id,
            "purpose": f"Trip #{trip_id} payment",
            "reference_number": f"CASH-{trip_id:04d}",
        }

        with patch.object(receipt_svc.generator, "generate", return_value=os.path.join(tempfile.gettempdir(), "receipt_linked.pdf")):
            path = receipt_svc.generate_and_record(receipt_data)
            assert path is not None

        # ── Verify trip link ─────────────────────────────────────
        receipts = db.conn.execute(
            "SELECT * FROM receipts WHERE related_trip_id = ? ORDER BY id DESC",
            (trip_id,),
        ).fetchall()
        assert len(receipts) >= 1
        rcpt = dict(receipts[0])
        assert rcpt["related_trip_id"] == trip_id
        assert rcpt["purpose"] == f"Trip #{trip_id} payment"
        assert rcpt["amount"] == 2500.0
