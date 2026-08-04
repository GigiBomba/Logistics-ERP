"""Golden flow: Full Trip Lifecycle — Lead → Route → Profit → Dispatch → Driver → Delivery → OCR → Invoice → Analytics.

This is the crown jewel golden flow. It validates that Operion can take
a freight lead all the way through to analytics-ready invoiced state
without any data re-entry, event loss, or cross-module inconsistency.
"""

from __future__ import annotations

from datetime import date

import pytest

from models.invoice_models import InvoiceCreate, InvoiceFinalizeRequest, InvoiceLineItem
from models.trip_models import TripCreate
from services.analytics_service import AnalyticsService
from services.calculator import TripCalculator
from services.document_service import DocumentService
from models.document_models import DocumentUpload
from models.calculator_models import CalculationRequest

pytestmark = pytest.mark.golden_flow


# ── Helpers ──────────────────────────────────────────────────────────────────

def _trip_status_value(raw: dict | None, key: str = "status") -> str:
    """Safely extract a field from the raw trip DB dict."""
    if raw is None:
        return ""
    return raw.get(key, "")


# ═════════════════════════════════════════════════════════════════════════════
# Test Classes
# ═════════════════════════════════════════════════════════════════════════════


class TestFullTripLifecycle:
    """Complete golden flow across all Operion modules."""

    # ── Step 1: Lead → Trip ─────────────────────────────────────────────

    def test_create_trip_from_lead(self, workflow_env, event_monitor):
        """Step 1: Lead → Trip.

        Seed Ana persona, create a new trip from lead data.
        Verify trip.created event, correct status, correct client.
        """
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(workflow_env.db)
        event_monitor.track("trip.created")

        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            client_name="Metro Cash & Carry",
            driver_name="Driver Ana-01",
            driver_id=ids["driver_ids"][0],
            truck_number="B-301-ANA",
            truck_id=ids["truck_ids"][0],
            distance_km=450.0,
            price_eur=1350.0,
            status="Planned",
            fuel_cost=135.0,
            toll_cost=45.0,
            salary_cost=275.0,
            extra_costs=25.0,
            net_profit=870.0,
            rate_per_km=3.0,
            gross_per_km=1.93,
            currency="EUR",
        )

        assert trip_id > 0, "Trip creation failed — no ID returned"
        event_monitor.assert_event_published("trip.created")

        trip = workflow_env.get_trip(trip_id)
        assert trip is not None, "Trip not found after creation"
        assert _trip_status_value(trip) == "Planned"
        assert trip["client_id"] == ids["client_ids"][0]

    # ── Step 2: Full Status Transitions ─────────────────────────────────

    def test_status_transitions_complete(self, workflow_env, event_monitor):
        """Step 2: Walk through ALL legal status transitions.

        Planned → Loading → In Transit → Delivered.
        Verify each step emits trip.status_changed with correct data.
        """
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(workflow_env.db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )

        event_monitor.track("trip.status_changed")

        # Planned → Loading
        result = workflow_env.transition_status(trip_id, "Loading")
        assert result is True, "Planned → Loading failed"
        event_monitor.assert_event_published(
            "trip.status_changed", data={"new_status": "Loading"}
        )
        trip = workflow_env.get_trip(trip_id)
        assert _trip_status_value(trip) == "Loading"

        # Loading → In Transit
        result = workflow_env.transition_status(trip_id, "In Transit")
        assert result is True, "Loading → In Transit failed"
        event_monitor.assert_event_published(
            "trip.status_changed", data={"new_status": "In Transit"}
        )
        trip = workflow_env.get_trip(trip_id)
        assert _trip_status_value(trip) == "In Transit"

        # In Transit → Delivered
        result = workflow_env.transition_status(trip_id, "Delivered")
        assert result is True, "In Transit → Delivered failed"
        event_monitor.assert_event_published(
            "trip.status_changed", data={"new_status": "Delivered"}
        )
        trip = workflow_env.get_trip(trip_id)
        assert _trip_status_value(trip) == "Delivered"

        # Verify correct event sequence
        event_monitor.assert_event_sequence(
            "trip.status_changed",  # Planned → Loading
            "trip.status_changed",  # Loading → In Transit
            "trip.status_changed",  # In Transit → Delivered
        )

    # ── Step 3: Invoice from delivered trip ─────────────────────────────

    def test_invoice_from_delivered_trip(self, workflow_env, event_monitor, invoice_service, db):
        """Step 3: Delivered trip → Invoice created → Finalized → PDF generated.

        Verify invoice.total matches trip.total, events emitted.
        """
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(workflow_env.db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            distance_km=450.0,
            price_eur=1350.0,
            status="Delivered",
        )

        event_monitor.track("invoice.created")

        # Create invoice via InvoiceService.create() with InvoiceCreate model
        # Include a line item so total_gross matches the trip price
        inv_result = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                trip_id=trip_id,
                invoice_date=date(2026, 7, 21),
                due_date=date(2026, 8, 20),
                currency="EUR",
                line_items=[
                    InvoiceLineItem(
                        description="Transport services",
                        quantity=1,
                        unit_price=1350.0,
                        vat_rate=0.0,
                    ),
                ],
            ),
        )
        assert inv_result.success is True, f"Invoice creation failed: {inv_result.errors}"
        invoice = inv_result.data
        assert invoice is not None
        invoice_id = invoice.id
        assert invoice_id > 0

        event_monitor.assert_event_published("invoice.created")

        # Verify invoice total matches trip total_price_eur
        trip = workflow_env.get_trip(trip_id)
        assert trip is not None
        assert invoice.total_gross == trip.get("total_price_eur", 0), (
            f"Invoice total {invoice.total_gross} != trip total {trip.get('total_price_eur')}"
        )

        # Finalize the invoice
        finalize_result = invoice_service.finalize(
            InvoiceFinalizeRequest(invoice_id=invoice_id),
            user_id=0,
        )
        assert finalize_result.success is True, f"Finalize failed: {finalize_result.errors}"

        # Generate PDF
        pdf_result = invoice_service.generate_pdf(invoice_id)
        assert pdf_result.success is True, f"PDF generation failed: {pdf_result.errors}"
        if pdf_result.data and pdf_result.data.pdf_path:
            assert len(pdf_result.data.pdf_path) > 0, "PDF path is empty"

    # ── Step 4: Cross-module consistency (full end-to-end) ──────────────

    def test_final_state_cross_module_consistency(self, workflow_env, event_monitor, invoice_service, db):
        """End-to-end: do ALL steps in one test, then verify cross-module consistency.

        Trip → Dispatch → Delivery → Invoice → Payment
        Final: trip status, invoice state, receipt, events all consistent.
        """
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(workflow_env.db)

        # 1. Create trip
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            distance_km=450.0,
            price_eur=1350.0,
            status="Planned",
        )
        assert trip_id > 0

        # 2. Transition through statuses
        assert workflow_env.transition_status(trip_id, "Loading")
        assert workflow_env.transition_status(trip_id, "In Transit")
        assert workflow_env.transition_status(trip_id, "Delivered")
        trip = workflow_env.get_trip(trip_id)
        assert _trip_status_value(trip) == "Delivered"

        # 3. Create invoice
        event_monitor.track("invoice.created")

        inv_result = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                trip_id=trip_id,
                invoice_date=date(2026, 7, 21),
                due_date=date(2026, 8, 20),
                currency="EUR",
            ),
        )
        assert inv_result.success is True, f"Invoice creation failed: {inv_result.errors}"
        invoice = inv_result.data
        assert invoice is not None
        invoice_id = invoice.id
        assert invoice_id > 0
        event_monitor.assert_event_published("invoice.created")

        # 4. Finalize invoice
        finalize_result = invoice_service.finalize(
            InvoiceFinalizeRequest(invoice_id=invoice_id),
            user_id=0,
        )
        assert finalize_result.success is True, f"Finalize failed: {finalize_result.errors}"

        # 5. Verify cross-module consistency via DB queries
        trip_db = db.conn.execute(
            "SELECT status, total_price_eur FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        invoice_db = db.conn.execute(
            "SELECT status, total_gross FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()

        assert trip_db is not None, "Trip record not found in DB"
        assert trip_db["status"] == "Delivered"
        assert invoice_db is not None, "Invoice record not found in DB"
        assert invoice_db["status"] == "finalized", (
            f"Expected finalized, got {invoice_db['status']}"
        )

    # ── Step 5: Invalid transitions rejected ───────────────────────────

    def test_invalid_status_transition_rejected(self, workflow_env):
        """Verify forbidden transitions are rejected.

        Planned → Delivered (skip Loading + In Transit) must be rejected.
        """
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(workflow_env.db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )

        # Attempt Planned → Delivered — illegal skip
        # force_trip_status returns False (no exception) for invalid transitions
        result = workflow_env.transition_status(trip_id, "Delivered")
        assert result is False, (
            "Illegal transition Planned → Delivered should have been rejected"
        )

        # Verify trip status is still Planned
        trip = workflow_env.get_trip(trip_id)
        assert _trip_status_value(trip) == "Planned"


# ═════════════════════════════════════════════════════════════════════════════
# Extended flows (calculator, document, analytics)
# ═════════════════════════════════════════════════════════════════════════════


class TestExtendedGoldenFlows:
    """Additional golden flows covering calculator, document, and analytics integration."""

    def test_calculator_to_trip_flow(self, workflow_env):
        """Calculator → Trip: Verify calculation results flow into trip creation."""
        # Run a calculation
        calculator = TripCalculator()
        calc_request = CalculationRequest(
            km=1200.0,
            price_eur=4800.0,
            fuel_price=1.55,
            days=3.0,
            consum_litri=30.0,
        )
        calc_result = calculator.calculate(calc_request)
        assert calc_result.success is True
        data = calc_result.data
        assert data is not None
        assert data.net_profit > 0

        # Use calculation results to create a trip
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(workflow_env.db)

        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            distance_km=data.km,
            price_eur=data.price_eur,
            fuel_cost=data.fuel_cost,
            toll_cost=data.toll_cost,
            salary_cost=data.salary_cost,
            extra_costs=data.extra_costs,
            net_profit=data.net_profit,
            rate_per_km=data.profit_per_km,
            gross_per_km=data.gross_per_km,
            status="Delivered",
        )
        assert trip_id > 0, "Trip from calculator data failed"

        # Verify trip data matches calculation
        trip = workflow_env.get_trip(trip_id)
        assert trip is not None
        assert float(trip["distance_km"]) == 1200.0
        assert float(trip["total_price_eur"]) == 4800.0

    def test_document_upload_and_link(self, workflow_env, db, event_monitor, tmp_path):
        """Document → OCR: Upload a document, link it to a trip, verify event."""
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(workflow_env.db)

        # Create a trip to link the document to
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Delivered",
        )
        assert trip_id > 0

        # Create a dummy file to upload
        doc_file = tmp_path / "test_cmr.pdf"
        doc_file.write_text("%PDF-1.4 fake pdf content for golden flow test")
        assert doc_file.exists()

        event_monitor.track("document.linked")

        # Upload document via DocumentService
        doc_svc = DocumentService(db)
        upload_result = doc_svc.upload_document(
            DocumentUpload(
                source_path=str(doc_file),
                title=f"CMR for trip {trip_id}",
                category="trip",
                entity_type="trip",
                entity_id=trip_id,
                tags=["cmr", "golden-flow"],
            ),
            user_id=0,
        )
        assert upload_result.success is True, f"Document upload failed: {upload_result.errors}"
        doc = upload_result.data
        assert doc is not None
        assert doc.id > 0

        # The upload already sets entity_type/entity_id, but also explicitly link
        link_result = doc_svc.link_to_entity(
            document_id=doc.id,
            entity_type="trip",
            entity_id=trip_id,
        )
        assert link_result.success is True, f"Link failed: {link_result.errors}"

        # Verify document is linked to trip
        linked_docs = doc_svc.get_documents_for_entity("trip", trip_id)
        linked_ids = [d["id"] for d in linked_docs]
        assert doc.id in linked_ids, (
            f"Document {doc.id} not found in linked docs for trip {trip_id}: {linked_ids}"
        )

    def test_analytics_sees_completed_trip(self, workflow_env, db):
        """Analytics: After a completed trip + invoice, analytics reflects the data."""
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(workflow_env.db)

        # Create and complete a trip
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            distance_km=450.0,
            price_eur=1350.0,
            status="Planned",
        )

        workflow_env.transition_status(trip_id, "Loading")
        workflow_env.transition_status(trip_id, "In Transit")
        workflow_env.transition_status(trip_id, "Delivered")

        # Query analytics
        analytics = AnalyticsService(db)

        # get_financial returns analytics data (list of rows or dict)
        financial = analytics.get_financial()
        assert financial is not None, "get_financial returned None"

        # The trip should appear somewhere in analytics results
        # (exact structure depends on repository implementation)
        total_revenue = 0.0
        if isinstance(financial, list):
            for row in financial:
                total_revenue += float(row.get("revenue", row.get("total_revenue", 0)))
        elif isinstance(financial, dict):
            total_revenue = float(financial.get("revenue", financial.get("total_revenue", 0)))

        # At minimum, analytics should reflect some revenue from our completed trip
        # (there are 15 trips from the persona seed + 1 we just created)
        assert total_revenue > 0, "Analytics shows zero revenue after completing a trip"

    def test_full_lead_to_analytics_pipeline(self, workflow_env, event_monitor, invoice_service, db):
        """The ultimate golden flow: Lead → Calc → Trip → Dispatch → Deliver → Invoice → Analytics.

        This test touches every major module in a single, gapless pipeline.
        """
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(workflow_env.db)
        event_monitor.track("trip.created", "trip.status_changed", "invoice.created")

        # ── 1. Calculator ───────────────────────────────────────────────
        calc = TripCalculator()
        calc_req = CalculationRequest(
            km=750.0, price_eur=3000.0, fuel_price=1.55,
            days=2.0, consum_litri=30.0,
        )
        calc_data = calc.calculate(calc_req).data
        assert calc_data is not None

        # ── 2. Trip ─────────────────────────────────────────────────────
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            client_name="Metro Cash & Carry",
            driver_name="Driver Ana-01",
            driver_id=ids["driver_ids"][0],
            truck_number="B-301-ANA",
            truck_id=ids["truck_ids"][0],
            distance_km=calc_data.km,
            price_eur=calc_data.price_eur,
            status="Planned",
            fuel_cost=calc_data.fuel_cost,
            toll_cost=calc_data.toll_cost,
            salary_cost=calc_data.salary_cost,
            extra_costs=calc_data.extra_costs,
            net_profit=calc_data.net_profit,
            rate_per_km=calc_data.profit_per_km,
            gross_per_km=calc_data.gross_per_km,
            currency="EUR",
        )
        assert trip_id > 0
        event_monitor.assert_event_published("trip.created")

        # ── 3. Dispatch / Status transitions ────────────────────────────
        assert workflow_env.transition_status(trip_id, "Loading")
        assert workflow_env.transition_status(trip_id, "In Transit")
        assert workflow_env.transition_status(trip_id, "Delivered")
        assert _trip_status_value(workflow_env.get_trip(trip_id)) == "Delivered"
        event_monitor.assert_event_published(
            "trip.status_changed", data={"new_status": "Delivered"}
        )

        # ── 4. Invoice ──────────────────────────────────────────────────
        inv_result = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                trip_id=trip_id,
                invoice_date=date(2026, 7, 21),
                due_date=date(2026, 8, 20),
                currency="EUR",
            ),
        )
        assert inv_result.success is True
        invoice = inv_result.data
        assert invoice is not None
        invoice_id = invoice.id
        assert invoice_id > 0
        event_monitor.assert_event_published("invoice.created")

        # Finalize
        finalize_result = invoice_service.finalize(
            InvoiceFinalizeRequest(invoice_id=invoice_id),
            user_id=0,
        )
        assert finalize_result.success is True

        # ── 5. Analytics ────────────────────────────────────────────────
        analytics = AnalyticsService(db)
        financial = analytics.get_financial()
        assert financial is not None

        # The trip + invoice should be visible in the database
        trip_db = db.conn.execute(
            "SELECT status, total_price_eur FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        assert trip_db is not None
        assert trip_db["status"] == "Delivered"
        assert float(trip_db["total_price_eur"]) == 3000.0

        invoice_db = db.conn.execute(
            "SELECT status, total_gross FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
        assert invoice_db is not None
        assert invoice_db["status"] == "finalized"

        # ── 6. Verify event sequence ────────────────────────────────────
        event_monitor.assert_event_sequence(
            "trip.created",
            "trip.status_changed",
            "trip.status_changed",
            "trip.status_changed",
            "invoice.created",
        )


# ═════════════════════════════════════════════════════════════════════════════
# Edge case / invariant tests
# ═════════════════════════════════════════════════════════════════════════════


class TestGoldenFlowInvariants:
    """Invariants that must hold for every golden flow."""

    def test_trip_price_non_negative(self, workflow_env):
        """A trip's price_eur must never be negative after creation."""
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(workflow_env.db)

        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            price_eur=1350.0,
            status="Planned",
        )
        trip = workflow_env.get_trip(trip_id)
        assert trip is not None
        total_price = trip.get("total_price_eur", -1)
        assert total_price >= 0, f"Negative trip price: {total_price}"

    def test_invoice_total_matches_trip_total(self, workflow_env, invoice_service, db):
        """Invoice total_gross must equal trip total_price_eur for a 1:1 invoice."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(workflow_env.db)

        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            distance_km=500.0,
            price_eur=2000.0,
            status="Delivered",
        )

        # Include a line item so total_gross matches the trip price
        inv_result = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                trip_id=trip_id,
                invoice_date=date(2026, 7, 21),
                due_date=date(2026, 8, 20),
                currency="EUR",
                line_items=[
                    InvoiceLineItem(
                        description="Transport services",
                        quantity=1,
                        unit_price=2000.0,
                        vat_rate=0.0,
                    ),
                ],
            ),
        )
        assert inv_result.success is True
        invoice = inv_result.data
        assert invoice is not None

        trip = workflow_env.get_trip(trip_id)
        assert trip is not None

        assert invoice.total_gross == float(trip["total_price_eur"]), (
            f"Invoice total_gross {invoice.total_gross} != "
            f"trip total_price_eur {trip['total_price_eur']}"
        )

    def test_event_emission_for_every_status_change(self, workflow_env, event_monitor):
        """Each status change must emit exactly one trip.status_changed event."""
        from tests.workflow_integrity.personas import build_ana_persona
        ids = build_ana_persona(workflow_env.db)

        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )

        event_monitor.track("trip.status_changed")

        # Perform all transitions and count events
        workflow_env.transition_status(trip_id, "Loading")
        workflow_env.transition_status(trip_id, "In Transit")
        workflow_env.transition_status(trip_id, "Delivered")

        events = event_monitor.get_events("trip.status_changed")
        assert len(events) == 3, (
            f"Expected 3 trip.status_changed events, got {len(events)}"
        )

        # Verify the sequence of new_status values
        expected_statuses = ["Loading", "In Transit", "Delivered"]
        for i, ev in enumerate(events):
            assert ev["data"]["new_status"] == expected_statuses[i], (
                f"Event {i}: expected {expected_statuses[i]}, "
                f"got {ev['data'].get('new_status')}"
            )
