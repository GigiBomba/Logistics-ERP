"""Chaos: multi-service cascade failure — dispatch commit dies, downstream steps blocked, recovery.

Blueprint §8.5.10 / P5-U5: a database failure during the **Dispatch** step must
leave the system observably correct — the whole dispatch rolls back to the
pre-dispatch state, later cascade steps (delivery / invoice draft) are blocked
while the trip never reached ``Delivered``, and once the DB is restored a retry
of the same dispatch succeeds without phantom invoices or analytics rows.

Real seams exercised (all synchronous, no ``time.sleep``):

* **Transaction boundary** — ``BaseRepository.transaction()`` /
  ``commit_transaction()`` (``repositories/__init__.py``).  ``commit_transaction``
  is the exact wrapper around ``db.conn.commit()``; making it raise once is the
  commit-failure injection point.  ``rollback_transaction`` then runs the real
  ``sqlite3`` rollback, so nothing leaks from the aborted transaction.
* **Dispatch path** — ``DispatchService.assign_both`` → real ``assign_truck`` /
  ``assign_driver`` → ``TripService.update`` → ``TripRepository.update``
  (D-INV-04/D-INV-05 all-or-nothing intent).
* **Downstream guards** — the real trip state machine
  (``VALID_TRANSITIONS``: a still-Planned trip can only go ``Loading`` /
  ``Cancelled`` — never straight to ``Delivered``) and the schema-level
  ``UNIQUE invoices.trip_id`` guard against duplicate/phantom drafts.

All assertions read state back through the repository layer
(``TripRepository.get_by_id`` / raw counts) so they verify what actually
persisted, not what the services returned in memory.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from unittest.mock import patch

import pytest

from repositories.trip_repository import TripRepository
from services.dispatch_service.errors import InvalidStatusTransitionError
from services.operations.event_bus import VALID_TRANSITIONS
from tests.workflow_integrity.personas.fixtures import (
    seed_client,
    seed_company,
    seed_driver,
    seed_trip,
    seed_truck,
)

pytestmark = pytest.mark.chaos_workflow


# ── Shared helpers ────────────────────────────────────────────────────────────

def _seed_dispatch_target(db) -> dict:
    """Seed an isolated dispatch target: company + client + free truck/driver + an
    unassigned Planned trip (nothing else in the world references the resources)."""
    company_id = seed_company(db, company_name="Cascade Chaos SRL",
                              subscription_tier="professional")
    client_id = seed_client(db, name="Cascade Chaos Client")
    driver_id = seed_driver(db, company_id=company_id, name="Cascade Driver",
                            license_number="RO-CASCADE-001")
    truck_id = seed_truck(db, plate_number="B-777-CAS", company_id=company_id)
    trip_id = seed_trip(
        db,
        company_id=company_id,
        client_id=client_id,
        client_name="Cascade Chaos Client",
        status="Planned",
        driver_name="",
        driver_id=None,
        truck_number="",
        truck_id=None,
        distance_km=500.0,
        total_price_eur=1500.0,
    )
    return {
        "company_id": company_id,
        "client_id": client_id,
        "driver_id": driver_id,
        "driver_name": "Cascade Driver",
        "truck_id": truck_id,
        "trip_id": trip_id,
    }


def _count(db, sql: str, params: tuple = ()) -> int:
    """Run a scalar COUNT and return the integer."""
    return int(db.conn.execute(sql, params).fetchone()[0])


def _trip_row(db, trip_id: int) -> dict:
    """Read the persisted trip row back through the repository layer."""
    row = TripRepository(db).get_by_id(trip_id)
    if row is None:
        raise AssertionError(f"trip #{trip_id} not found in repository")
    return row


def _run_failing_dispatch(db, ids: dict) -> None:
    """Run one atomic dispatch whose DB commit fails once (rolls back).

    The dispatch body runs through the real service path inside the repository
    transaction boundary; ``commit_transaction`` (the wrapper around
    ``db.conn.commit()``) raises like a DB drop at the commit point.  The
    context manager rolls the whole dispatch back and re-raises.
    """
    trip_repo = TripRepository(db)
    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        with patch.object(
            trip_repo,
            "commit_transaction",
            side_effect=sqlite3.OperationalError("database is locked"),
        ):
            with trip_repo.transaction():
                result = ids["dispatch_service"].assign_both(
                    ids["trip_id"],
                    truck_id=ids["truck_id"],
                    driver_id=ids["driver_id"],
                )
                assert result.success is True


# ── Scenario 1 — commit failure mid-dispatch → atomic rollback ──────────────

class TestCommitFailureMidDispatch:
    """§8.5.10 / 8.5.10-1: a dispatch whose commit fails leaves NO trace.

    The trip stays ``Planned`` with truck/driver unassigned, and no phantom
    assignment, history, or invoice rows are written anywhere.
    """

    def test_commit_failure_mid_dispatch_rolls_back_to_planned(
        self, db, dispatch_service
    ):
        ids = _seed_dispatch_target(db)
        ids["dispatch_service"] = dispatch_service
        trip_id = ids["trip_id"]
        invoice_count_before = _count(db, "SELECT COUNT(*) FROM invoices")
        history_before = _count(
            db,
            "SELECT COUNT(*) FROM trip_status_history WHERE trip_id = ?",
            (trip_id,),
        )

        _run_failing_dispatch(db, ids)

        # The persisted trip is back to the exact pre-dispatch state: Planned,
        # truck and driver unassigned (verified through the repository).
        row = _trip_row(db, trip_id)
        assert row["status"] == "Planned"
        assert row["truck_id"] is None
        assert row["driver_id"] is None
        assert (row.get("truck_number") or "") == ""
        assert (row.get("driver_name") or "") == ""

        # No phantom assignment rows: no trip anywhere references the truck or
        # the driver that the aborted dispatch tried to assign.
        assert _count(
            db, "SELECT COUNT(*) FROM trips WHERE truck_id = ?", (ids["truck_id"],)
        ) == 0
        assert _count(
            db, "SELECT COUNT(*) FROM trips WHERE driver_id = ?", (ids["driver_id"],)
        ) == 0

        # No phantom downstream rows appeared during the failure window.
        assert _count(db, "SELECT COUNT(*) FROM invoices") == invoice_count_before
        assert _count(
            db,
            "SELECT COUNT(*) FROM trip_status_history WHERE trip_id = ?",
            (trip_id,),
        ) == history_before


# ── Scenario 2 — dependent cascade steps stay blocked ────────────────────────

class TestDependentStepsBlocked:
    """§8.5.10 / 8.5.10-2: nothing downstream runs for a trip that never
    reached ``Delivered``.

    After the interrupted dispatch the trip is still Planned, so the real trip
    state machine refuses the delivery step that is the invoice step's
    precondition — and no invoice draft row exists for the trip.  When the same
    cascade is later completed legally (dispatch → Loading → In Transit →
    Delivered), the invoice step produces exactly one draft — the schema-level
    ``UNIQUE invoices.trip_id`` guard rejects a duplicate as a phantom.
    """

    def test_delivery_and_invoice_steps_blocked_until_trip_is_delivered(
        self, db, dispatch_service, invoice_service
    ):
        ids = _seed_dispatch_target(db)
        ids["dispatch_service"] = dispatch_service
        trip_id = ids["trip_id"]

        # Reproduce the chaos window: the dispatch commit fails and rolls back.
        _run_failing_dispatch(db, ids)
        row = _trip_row(db, trip_id)
        assert row["status"] == "Planned"

        # Dependent step 1 — delivery.  The real transition path refuses to
        # rush a never-dispatched Planned trip straight to Delivered; the trip
        # stays exactly where the failed dispatch left it.
        with pytest.raises(InvalidStatusTransitionError):
            dispatch_service.complete_trip(trip_id)
        assert _trip_row(db, trip_id)["status"] == "Planned"
        # The state machine's forward edges out of Planned are the real guard:
        # Delivered (the invoice step's precondition) is not reachable from here.
        assert "Delivered" not in VALID_TRANSITIONS["Planned"]

        # Dependent step 2 — invoice draft.  No draft row for a trip that never
        # reached Delivered: zero phantom invoices during the failure window.
        assert _count(
            db, "SELECT COUNT(*) FROM invoices WHERE trip_id = ?", (trip_id,)
        ) == 0

        # Recovery path: the DB is restored, the dispatch retry succeeds, and
        # the cascade is completed legally (Planned → Loading → In Transit →
        # Delivered).  The real invoice step now produces exactly one draft.
        retry = dispatch_service.assign_both(
            trip_id, truck_id=ids["truck_id"], driver_id=ids["driver_id"]
        )
        assert retry.success is True
        for status in ("Loading", "In Transit", "Delivered"):
            assert dispatch_service.transition_status(trip_id, status).success is True

        from models.invoice_models import InvoiceCreate

        def _draft() -> object:
            return invoice_service.create(
                InvoiceCreate(
                    client_id=ids["client_id"],
                    trip_id=trip_id,
                    invoice_date=date(2026, 9, 1),
                    due_date=date(2026, 10, 1),
                    currency="EUR",
                )
            )

        first = _draft()
        assert first.success is True
        assert _count(
            db, "SELECT COUNT(*) FROM invoices WHERE trip_id = ?", (trip_id,)
        ) == 1
        # A second draft for the same (now Delivered) trip is a phantom: the
        # schema's UNIQUE trip_id guard rejects it — no duplicate invoice row.
        try:
            _draft()
        except sqlite3.IntegrityError:
            pass  # expected — duplicate trip_id rejected by the schema
        assert _count(
            db, "SELECT COUNT(*) FROM invoices WHERE trip_id = ?", (trip_id,)
        ) == 1


# ── Scenario 3 — recovery: retry after the commit is restored ────────────────

class TestRecoveryAfterCommitRestored:
    """§8.5.10 / 8.5.10-3: once the DB commit works again, retrying the same
    dispatch succeeds and no phantom invoice/analytics rows appeared during the
    failure window.
    """

    def test_retry_dispatch_succeeds_cleanly_after_commit_restored(
        self, db, dispatch_service
    ):
        ids = _seed_dispatch_target(db)
        ids["dispatch_service"] = dispatch_service
        trip_id = ids["trip_id"]

        # Failure window: one atomic dispatch attempt whose commit dies.
        _run_failing_dispatch(db, ids)
        assert _trip_row(db, trip_id)["truck_id"] is None
        # No phantom rows while the DB was down.
        assert _count(
            db, "SELECT COUNT(*) FROM invoices WHERE trip_id = ?", (trip_id,)
        ) == 0
        assert _count(
            db,
            "SELECT COUNT(*) FROM trip_status_history WHERE trip_id = ?",
            (trip_id,),
        ) == 0

        # DB restored (the failing commit seam is gone): the retry of the exact
        # same dispatch succeeds and persists truck + driver on the trip.
        result = dispatch_service.assign_both(
            trip_id, truck_id=ids["truck_id"], driver_id=ids["driver_id"]
        )
        assert result.success is True

        row = _trip_row(db, trip_id)
        assert row["status"] == "Planned"  # legal, non-terminal dispatch state
        assert row["truck_id"] == ids["truck_id"]
        assert row["driver_id"] == ids["driver_id"]
        assert row["driver_name"] == ids["driver_name"]
        assert row["truck_number"]  # plate is persisted on the trip row

        # The retried dispatch is the only assignment of the resources — the
        # truck/driver are referenced exactly once, and no invoice or history
        # phantom leaked in during the earlier failure window.
        assert _count(
            db, "SELECT COUNT(*) FROM trips WHERE truck_id = ?", (ids["truck_id"],)
        ) == 1
        assert _count(
            db, "SELECT COUNT(*) FROM trips WHERE driver_id = ?", (ids["driver_id"],)
        ) == 1
        assert _count(db, "SELECT COUNT(*) FROM invoices") == 0
        assert _count(
            db,
            "SELECT COUNT(*) FROM trip_status_history WHERE trip_id = ?",
            (trip_id,),
        ) == 0
