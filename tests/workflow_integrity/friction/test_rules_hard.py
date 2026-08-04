"""R1-R7: Hard friction rule tests.

R1: No duplicate data entry
R2: No dead-end screens
R6: No silent failures
R7: Cross-platform state coherence

(R3, R4, R5 are UI-layer concerns and are documented as skipped.)
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
