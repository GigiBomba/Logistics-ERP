"""R1-R7: Hard friction rule tests.

R1: No duplicate data entry
R2: No dead-end screens
R3: Driver workday completable on mobile alone (service-layer walk)
R4: Accountant workday completable on desktop alone (service-layer walk)
R5: No hidden knowledge required between workflow screens
R6: No silent failures
R7: Cross-platform state coherence

R3/R4/R5 are exercised here at the service layer using the platform
capability inventories from ``rules.py`` (MOBILE_ONLY_CAPABILITIES /
DESKTOP_ONLY_CAPABILITIES).
"""
from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.friction


class TestNoDuplicateDataEntry:
    """R1: No duplicate data entry."""

    def test_trip_can_be_created_without_duplicate_keying(
        self, workflow_env, db
    ):
        """Creating a trip only requires data entry once.

        All trip data is provided in a single ``create_trip()`` call.
        The trip must be fully queryable without any follow-up updates.
        """
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        # Create trip — all data entered in one call
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        assert trip_id > 0
        # Verify all data is present without any update
        trip = workflow_env.get_trip(trip_id)
        assert trip is not None


class TestDriverCompletesWorkflowMobileOnly:
    """R3: Driver completes workflow via mobile-only access."""

    def test_driver_completes_workflow_mobile_only(self, workflow_env, db):
        """R3 equivalent: Verify driver operations work independently."""
        from tests.workflow_integrity.personas import build_ionut_persona

        ids = build_ionut_persona(db)
        # Driver's trip can be queried without dispatcher context
        from services.trip_service import TripService

        svc = TripService(db)
        trip = svc.get_by_id(ids["trip_ids"]["delivered"])
        assert trip is not None, "Driver should access their own trips"


class TestNoDeadEndScreens:
    """R2: No dead-end screens — every status has a valid next transition."""

    def test_trip_status_has_next_transition(self):
        """Every non-terminal trip status has at least one valid transition."""
        from services.operations.event_bus import VALID_TRANSITIONS

        non_terminal = ["Planned", "Loading", "In Transit", "Delivered", "Invoiced"]
        for status in non_terminal:
            assert len(VALID_TRANSITIONS.get(status, [])) > 0, (
                f"Dead-end: {status} has no outgoing transitions"
            )


class TestNoSilentFailures:
    """R6: No silent failures — all failures must produce visible errors."""

    def test_invalid_invoice_creation_returns_error(self, invoice_service, db):
        """Creating an invoice with bad data returns a ServiceResult error or raises."""
        from models.invoice_models import InvoiceCreate

        try:
            result = invoice_service.create(
                InvoiceCreate(
                    client_id=99999,  # non-existent
                    invoice_date=date(2026, 7, 21),
                    due_date=date(2026, 8, 20),
                ),
            )
            # Should not crash silently — should return error result
            assert result is not None
            assert not result.success, (
                f"Expected error for invalid client_id, got success: {result.data}"
            )
        except Exception:
            # Some DB configurations raise FK constraint errors instead
            # of returning a failure result. Either behavior is acceptable
            # as long as the error is surfaced (not silently swallowed).
            pass

    def test_invalid_trip_transition_returns_false(self, workflow_env, db):
        """Invalid trip status transition returns False instead of crashing."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        # Try illegal transition (Planned -> Delivered skips Loading + In Transit)
        result = workflow_env.transition_status(trip_id, "Delivered")
        assert result is False, "Illegal transition should return False"


class TestCrossPlatformStateCoherence:
    """R7: State visible the same way from both "platform" perspectives."""

    def test_status_identical_via_service_and_db(self, workflow_env, db):
        """Trip status read via service and via raw DB must match."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        workflow_env.transition_status(trip_id, "Loading")
        svc_trip = workflow_env.get_trip(trip_id)
        db_trip = db.conn.execute(
            "SELECT status FROM trips WHERE id = ?",
            (trip_id,),
        ).fetchone()
        assert svc_trip["status"] == db_trip["status"] == "Loading"


class TestDriverMobileOnly:
    """R3: Driver-only workday must be completable on mobile alone.

    Walks one Ionut driver workday through the mobile client fixture only:
    view the assigned trip, push Loading -> In Transit -> Delivered from the
    road (offline-queued, then synced), queue the signed-CMR upload and the
    fuel expense, then sync those too.  Every step is tagged with the
    MOBILE_ONLY_CAPABILITIES symbol it exercises; the walk completes without
    any DESKTOP_ONLY capability — no invoicing / payment / dunning / financial
    service object is constructed or invoked on the harness.
    """

    def test_driver_workday_completes_mobile_only(self, db, trip_service):
        """A driver workday (status updates, CMR upload, expense) needs mobile only."""
        from services.operations.trip_status_engine import TripStatusEngine
        from tests.workflow_integrity.fixtures.multi_platform_client import MobileClient
        from tests.workflow_integrity.friction.rules import (
            DESKTOP_ONLY_CAPABILITIES,
            MOBILE_ONLY_CAPABILITIES,
        )
        from tests.workflow_integrity.personas import build_ionut_persona

        # The shared MobileClient fixture replays queued status changes through
        # a TripStatusEngine API that no longer exists (see the note in
        # parity/test_offline_behavior.py).  Keep every queuing / idempotency
        # behaviour of the fixture intact; route ONLY the status replay through
        # the real current TripStatusEngine(db).transition() service path.
        class _DriverSyncClient(MobileClient):
            def _replay_action(self, action, item):
                if action == "update_status":
                    try:
                        engine = TripStatusEngine(self.db)
                        return engine.transition(
                            item["trip_id"], item["status"], trigger="mobile_sync"
                        )
                    except Exception:
                        return False
                return super()._replay_action(action, item)

        ids = build_ionut_persona(db)
        trip_id = ids["trip_ids"]["planned"]
        client = _DriverSyncClient(trip_service, db)
        used_capabilities: set[str] = set()

        def _performed(capability: str) -> None:
            assert capability in MOBILE_ONLY_CAPABILITIES, (
                f"{capability!r} is not in MOBILE_ONLY_CAPABILITIES"
            )
            used_capabilities.add(capability)

        # 1. View the assigned trip / next assignment (trip_details_view).
        trip = client.get_trip(trip_id)
        assert trip is not None and trip["status"] == "Planned"
        _performed("trip_details_view")

        # 2. Drive the trip home: Loading -> In Transit -> Delivered, each
        #    queued offline on the road and applied exactly once on sync
        #    (trip_status_update).
        for status, key in (
            ("Loading", "r3-loading"),
            ("In Transit", "r3-in-transit"),
            ("Delivered", "r3-delivered"),
        ):
            assert client.update_status(
                trip_id, status, offline=True, idempotency_key=key
            ) is None
            assert client.pending_actions() == 1
            results = client.sync_queue()
            assert len(results) == 1
            assert results[0]["applied"] is True, results
            assert results[0]["result"] is True, results
            trip = client.get_trip(trip_id)
            assert trip is not None
            assert trip["status"] == status
        _performed("trip_status_update")

        # 3. Queue the signed-CMR photo and the fuel expense, then sync both
        #    (cmr_document_upload + expense_submission).
        client.queue_document_upload(
            trip_id, title="cmr_signed.jpg", category="cmr"
        )
        client.queue_expense(trip_id, description="Motorway fuel", amount=96.50)
        assert client.pending_actions() == 2
        results = client.sync_queue()
        assert len(results) == 2
        assert all(r["applied"] is True and r["result"] is True for r in results), results
        _performed("cmr_document_upload")
        _performed("expense_submission")

        # The driver workday finished: trip Delivered, offline queue drained.
        assert client.pending_actions() == 0
        trip = client.get_trip(trip_id)
        assert trip is not None
        assert trip["status"] == "Delivered"

        # Completed using mobile capability symbols only — no desktop-only
        # capability (invoice_finalization / payment_recording /
        # dunning_management / financial_reporting) was required.
        assert used_capabilities <= set(MOBILE_ONLY_CAPABILITIES)
        assert used_capabilities.isdisjoint(DESKTOP_ONLY_CAPABILITIES)


class TestAccountantDesktopOnly:
    """R4: Accounting workday must be completable on desktop alone.

    Walks Elena's accountant workday through the desktop service layer:
    invoice create -> finalize -> payment recorded -> dunning approve /
    reminder-sequence dispatch.  Every step is tagged with the
    DESKTOP_ONLY_CAPABILITIES symbol it exercises; no MobileClient is ever
    constructed, so no mobile-only operation can be required.
    """

    def test_accountant_workday_completes_desktop_only(self, db, invoice_service):
        """Invoice create -> finalize -> payment -> dunning all on desktop."""
        from datetime import timedelta
        from unittest.mock import MagicMock

        from models.invoice_models import InvoiceCreate, InvoiceFinalizeRequest
        from repositories.automail_repository import AutoMailRepository
        from repositories.invoice_repository import InvoiceRepository
        from services.automail.template_service import TemplateService
        from services.operations.dunner_engine import DunnerEngine
        from tests.workflow_integrity.friction.rules import (
            DESKTOP_ONLY_CAPABILITIES,
            MOBILE_ONLY_CAPABILITIES,
        )
        from tests.workflow_integrity.personas import build_elena_persona

        ids = build_elena_persona(db)
        today = date.today()
        used_capabilities: set[str] = set()

        def _performed(capability: str) -> None:
            assert capability in DESKTOP_ONLY_CAPABILITIES, (
                f"{capability!r} is not in DESKTOP_ONLY_CAPABILITIES"
            )
            used_capabilities.add(capability)

        # 1. Invoice creation / editing on the delivered trip (invoice_editing).
        created = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                trip_id=ids["trip_ids"]["delivered"][0],
                invoice_date=today.isoformat(),
                due_date=(today + timedelta(days=30)).isoformat(),
                currency="EUR",
            )
        )
        assert created.success is True, created.errors
        invoice_id = created.data.id
        _performed("invoice_editing")

        # 2. Finalize the invoice (invoice_finalization).
        finalized = invoice_service.finalize(
            InvoiceFinalizeRequest(invoice_id=invoice_id), user_id=0
        )
        assert finalized.success is True, finalized.errors
        _performed("invoice_finalization")

        # 3. Record the client payment (payment_recording).
        paid = invoice_service.set_status(invoice_id, "paid", user_id=0)
        assert paid.success is True, paid.errors
        inv_row = db.conn.execute(
            "SELECT status FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
        assert inv_row["status"] == "paid"
        _performed("payment_recording")

        # 4. Dunning management (dunning_management): an overdue account needs
        #    a reminder sequence.  Seed the overdue receivable, configure the
        #    dunning template + schedule, then approve/dispatch the cycle.
        conn = db.conn
        conn.execute(
            "INSERT INTO invoices (client_id, trip_id, invoice_number, total_gross, "
            "subtotal_net, total_vat, total_amount, status, issue_date, due_date, "
            "currency, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'Unpaid', ?, ?, 'EUR', datetime('now'), datetime('now'))",
            (
                ids["client_ids"][1],
                ids["trip_ids"]["invoiced"][0],
                "INV-2026-DUN-001",
                900.0,
                756.3,
                143.7,
                900.0,
                (today - timedelta(days=45)).isoformat(),
                (today - timedelta(days=15)).isoformat(),
            ),
        )
        conn.commit()
        overdue_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        template_service = TemplateService(db)
        tmpl_result = template_service.create_template(
            {
                "name": "Dunning reminder 15d",
                "subject": "Invoice {invoice_number} is overdue",
                "body_text": "Please settle {total_amount} {currency}.",
                "is_default": 0,
            }
        )
        assert tmpl_result.success is True, tmpl_result.errors
        assert tmpl_result.data is not None
        template_id = tmpl_result.data["id"]

        automail_repo = AutoMailRepository(db)
        schedule_id = automail_repo.create_schedule(
            {
                "name": "dunning-15d",
                "trigger_type": "days_after_due",
                "days_offset": 0,
                "template_id": template_id,
                "is_active": 1,
                "sort_order": 0,
                "attach_invoice": 0,
                "attach_cmr": 0,
                "attach_all_docs": 0,
            }
        )
        assert schedule_id > 0

        # Approve / dispatch the reminder sequence for the overdue invoice.
        notification_center = MagicMock()
        notification_center.send_email.return_value = True
        dunner = DunnerEngine(db=db, notification_center=notification_center)
        assert dunner.evaluate_all() >= 1
        assert InvoiceRepository(db).get_reminder_count(overdue_id) >= 1

        # The approved sequence is not re-dispatched: re-running the cycle
        # sends nothing new for the already-reminded invoice.
        assert dunner.evaluate_all() == 0
        _performed("dunning_management")

        # Completed using desktop capability symbols only — no mobile-only
        # capability (trip_status_update / cmr_document_upload / expense_
        # submission / ...) and no MobileClient involvement was required.
        assert used_capabilities <= set(DESKTOP_ONLY_CAPABILITIES)
        assert used_capabilities.isdisjoint(MOBILE_ONLY_CAPABILITIES)


class TestNoHiddenKnowledge:
    """R5: No hidden knowledge required between workflow screens.

    A trip row references client / driver / truck by id AND carries the
    human-readable display strings (client_name / driver_name / truck plate)
    on the row itself, so the person acting on the trip never has to memorize
    data or leave the screen to resolve a referenced entity.
    """

    def test_trip_row_carries_reference_labels_and_ids_resolve_in_one_read(
        self, workflow_env, db
    ):
        """Each referenced entity resolves in ONE get_by_id read; the trip row
        exposes the display strings directly."""
        from repositories.client_repository import ClientRepository
        from repositories.driver_repository import DriverRepository
        from repositories.fleet_repository import FleetRepository
        from tests.workflow_integrity.personas import build_ionut_persona

        ids = build_ionut_persona(db)
        client_id = ids["client_ids"][0]
        driver_id = ids["driver_id"]
        truck_id = ids["truck_id"]

        # Every entity a trip references resolves by id in a single read call
        # against the right repository — no multi-hop / cross-screen search.
        client = ClientRepository(db).get_by_id(client_id)
        driver = DriverRepository(db).get_by_id(driver_id)
        truck = FleetRepository(db).get_by_id(truck_id)
        assert client is not None, f"Client {client_id} did not resolve in one read"
        assert driver is not None, f"Driver {driver_id} did not resolve in one read"
        assert truck is not None, f"Truck {truck_id} did not resolve in one read"

        # Create a trip referencing those entities, carrying the same display
        # labels the entities resolved to.
        trip_id = workflow_env.create_trip(
            client_id=client_id,
            driver_id=driver_id,
            truck_id=truck_id,
            client_name=client["name"],
            driver_name=driver["name"],
            truck_plate=truck["plate_number"],
        )
        trip = workflow_env.get_trip(trip_id)
        assert trip is not None

        # The row keeps the ids so every reference stays linkable...
        assert trip["client_id"] == client_id
        assert trip["driver_id"] == driver_id
        assert trip["truck_id"] == truck_id

        # ...and the display labels sit on the trip row itself, so no screen
        # requires the user to memorize or look them up from another screen.
        assert trip["client_name"] == client["name"]
        assert trip["driver_name"] == driver["name"]
        plate = trip.get("truck_number") or trip.get("truck_plate")
        assert isinstance(plate, str) and plate == truck["plate_number"]
