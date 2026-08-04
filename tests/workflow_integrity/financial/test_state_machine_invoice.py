"""Invoice state machine: Draft → Finalized → XML Generated → Submitted → Queued → Submitting → Accepted → Paid.

Also supports: Draft → Cancelled, Finalized → Cancelled, and reversion paths
(xml_generated → draft, rejected → draft/manual_review, etc.).
"""

from __future__ import annotations

from datetime import date

import pytest

from models.invoice_models import (
    INVOICE_STATUS_TRANSITIONS,
    InvoiceCreate,
    InvoiceFinalizeRequest,
    InvoiceLineItem,
)
from services.invoicing.service import InvoiceService

pytestmark = pytest.mark.state_machine


def _all_valid_pairs() -> list[tuple[str, str]]:
    """Derive every (from, to) pair from INVOICE_STATUS_TRANSITIONS."""
    pairs: list[tuple[str, str]] = []
    for from_status, to_list in INVOICE_STATUS_TRANSITIONS.items():
        for to_status in to_list:
            pairs.append((from_status, to_status))
    return pairs


VALID_PAIRS = _all_valid_pairs()


def _find_path(
    start: str, target: str, transitions: dict[str, list[str]]
) -> list[str] | None:
    """BFS from *start* to *target* through the transition graph.

    Returns the full path (including start and target) or None if
    no route exists.
    """
    if start == target:
        return [start]
    visited: set[str] = {start}
    queue: list[tuple[str, list[str]]] = [(start, [start])]
    while queue:
        current, path = queue.pop(0)
        for nxt in transitions.get(current, []):
            if nxt == target:
                return path + [nxt]
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [nxt]))
    return None

# Core simplified subset used by standard workflows (draft → finalized → paid).
CORE_TRANSITIONS = [
    ("draft", "finalized"),
    ("finalized", "paid"),
    ("draft", "cancelled"),
    ("finalized", "cancelled"),
]


class TestInvoiceValidTransitions:
    """Core invoice transitions via InvoiceService.set_status()."""

    @pytest.mark.parametrize("from_status,to_status", CORE_TRANSITIONS)
    def test_core_valid_transition(
        self, from_status, to_status, invoice_service, db
    ):
        """Core transitions (draft ↔ finalized ↔ paid) must succeed."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        inv_result = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                invoice_date=date(2026, 7, 21),
                due_date=date(2026, 8, 20),
                currency="EUR",
                line_items=[
                    InvoiceLineItem(
                        description="Transport services",
                        quantity=1,
                        unit_price=1000.0,
                        vat_rate=19.0,
                    ),
                ],
            ),
        )
        assert inv_result.success is True
        invoice = inv_result.data
        assert invoice is not None
        invoice_id = invoice.id

        # If starting from something other than "draft", transition there first
        current = invoice.status
        if current != from_status:
            r = invoice_service.set_status(invoice_id, from_status, user_id=0)
            assert r.success is True, f"Pre-transition to {from_status} failed: {r.errors}"

        result = invoice_service.set_status(invoice_id, to_status, user_id=0)
        assert result.success is True, (
            f"{from_status} -> {to_status} failed: {result.errors}"
        )
        updated = result.data
        assert updated is not None
        assert updated.status == to_status, (
            f"Expected {to_status}, got {updated.status}"
        )

    def test_finalize_via_dedicated_method(self, invoice_service, db):
        """InvoiceService.finalize() must succeed on draft invoices."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        inv_result = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                invoice_date=date(2026, 7, 21),
                due_date=date(2026, 8, 20),
                currency="EUR",
            ),
        )
        assert inv_result.success is True
        invoice = inv_result.data
        assert invoice is not None

        result = invoice_service.finalize(
            InvoiceFinalizeRequest(invoice_id=invoice.id),
            user_id=0,
        )
        assert result.success is True, f"finalize() failed: {result.errors}"
        assert result.data is not None
        assert result.data.status == "finalized"

    def test_cancel_via_dedicated_method(self, invoice_service, db):
        """InvoiceService.cancel() must succeed on draft invoices."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        inv_result = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                invoice_date=date(2026, 7, 21),
                due_date=date(2026, 8, 20),
                currency="EUR",
            ),
        )
        assert inv_result.success is True
        invoice = inv_result.data

        result = invoice_service.cancel(invoice.id, user_id=0)
        assert result.success is True, f"cancel() failed: {result.errors}"
        assert result.data is not None
        assert result.data.status == "cancelled"


class TestInvoiceInvalidTransitions:
    """Illegal invoice transitions must be rejected."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("draft", "paid"),             # skip finalization
            ("draft", "accepted"),         # skip finalized + xml + submit + accept
            ("paid", "draft"),             # no backward from terminal
            ("paid", "finalized"),         # no backward from terminal
            ("paid", "cancelled"),         # terminal → no transition
            ("cancelled", "draft"),        # terminal → no transition
            ("cancelled", "finalized"),    # terminal → no transition
            ("accepted", "draft"),         # accepted only → paid
            ("accepted", "finalized"),     # accepted only → paid
            ("accepted", "cancelled"),     # accepted only → paid
        ],
    )
    def test_invalid_transition_rejected(
        self, from_status, to_status, invoice_service, db
    ):
        """Illegal transition must fail and leave status unchanged."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        inv_result = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                invoice_date=date(2026, 7, 21),
                due_date=date(2026, 8, 20),
                currency="EUR",
            ),
        )
        assert inv_result.success is True
        invoice = inv_result.data
        assert invoice is not None
        invoice_id = invoice.id

        # Walk from 'draft' to *from_status* through valid transitions (BFS)
        path = _find_path("draft", from_status, INVOICE_STATUS_TRANSITIONS)
        if path is None:
            # No valid path from draft to from_status — this means the
            # transition doesn't need testing (unreachable pair)
            return

        # Execute each intermediate transition
        for status in path[1:]:
            r = invoice_service.set_status(invoice_id, status, user_id=0)
            assert r.success is True, f"Setup transition to {status} failed: {r.errors}"

        result = invoice_service.set_status(invoice_id, to_status, user_id=0)
        assert result.success is False, (
            f"{from_status} -> {to_status} should be rejected, "
            f"got success={result.success}"
        )

        # Verify status unchanged
        get_result = invoice_service.get(invoice_id)
        assert get_result.success is True
        assert get_result.data is not None
        assert get_result.data.status == from_status, (
            f"Status changed from {from_status} to {get_result.data.status}"
        )


class TestInvoiceComprehensiveTransitions:
    """Test every valid transition pair from INVOICE_STATUS_TRANSITIONS."""

    @pytest.mark.parametrize("from_status,to_status", VALID_PAIRS)
    def test_all_valid_transitions(
        self, from_status, to_status, invoice_service, db
    ):
        """Every pair in INVOICE_STATUS_TRANSITIONS must be accepted."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        inv_result = invoice_service.create(
            InvoiceCreate(
                client_id=ids["client_ids"][0],
                invoice_date=date(2026, 7, 21),
                due_date=date(2026, 8, 20),
                currency="EUR",
            ),
        )
        assert inv_result.success is True
        invoice = inv_result.data
        assert invoice is not None
        invoice_id = invoice.id

        # Walk from 'draft' to *from_status* through valid transitions (BFS)
        path = _find_path("draft", from_status, INVOICE_STATUS_TRANSITIONS)
        if path is None:
            # No valid path from draft to from_status — skip this pair
            return

        # Execute each intermediate transition
        for status in path[1:]:
            r = invoice_service.set_status(invoice_id, status, user_id=0)
            assert r.success is True, f"Setup transition to {status} failed: {r.errors}"

        result = invoice_service.set_status(invoice_id, to_status, user_id=0)
        assert result.success is True, (
            f"{from_status} -> {to_status} failed: {result.errors}"
        )
        assert result.data is not None
        assert result.data.status == to_status
