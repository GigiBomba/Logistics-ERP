"""ARGO-INV: Autonomous invoice tests (blueprint §5.2, §8 scenario 7, §8.5.8).

Exercises the REAL invoice tools from ``backend/copilot/tools/invoice_tools.py``:

* ``InvoiceDraftTool``       (``invoice.draft``)       — one draft per trip
* ``InvoiceFinalizeTool``    (``invoice.finalize``)    — lock the fiscal number
* ``InvoiceGeneratePdfTool`` (``invoice.generate_pdf``) — wraps ``InvoiceService.generate_pdf``

Plans are built DETERMINISTICALLY through the ARGO fixtures (``make_step`` /
``build_plan`` / ``build_argo_world``) and executed through the executor
(``execute_plan``) — no LLM, no planner.

Real-world facts this suite pins down:

* **Idempotency mechanism (§8 scenario 7 / §5.2 row 1).**  The tools do NOT
  pre-check for an existing invoice.  The real uniqueness guard is the
  schema-level ``UNIQUE`` constraint on ``invoices.trip_id``
  (``database/schema.py``): a second draft for the same trip fails the insert,
  the tool surfaces ``copilot.error.internal`` with the
  ``UNIQUE constraint failed: invoices.trip_id`` detail, and no duplicate row
  is ever written.  The batch-draft plan therefore yields exactly 3 drafts on
  a fresh world and still 3 on a re-run.
* **PDF generation is NOT part of ``invoice.finalize``.**  The generator
  (``services.invoicing.generator.InvoiceGenerator``) writes real files; every
  test here patches that seam with ``unittest.mock`` so no real PDF ever hits
  disk.  ``invoice.generate_pdf`` never mutates invoice status — a crash leaves
  the invoice exactly where it was (draft or finalized).
* **Missing client VAT is NOT blocked.**  The ``clients`` table has no
  ``vat_rate`` column and ``InvoiceDraftTool`` never reads client VAT — the
  line item falls back to the ``InvoiceLineItem`` default ``19.0``.  That is a
  documented gap against blueprint §5.2 row 3 / §7.5.3 ("ARGO must block when
  the VAT rate is missing").
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence
from unittest.mock import patch

import pytest

from backend.copilot.executor import execute_plan
from backend.copilot.schemas import ExecutionStep
from backend.copilot.tools.invoice_tools import (
    InvoiceDraftTool,
    InvoiceFinalizeTool,
    InvoiceGeneratePdfTool,
)

from tests.workflow_integrity.argo.fixtures import (
    KNOWN_VALUES,
    build_argo_world,
    build_plan,
    make_step,
)

pytestmark = [pytest.mark.argo, pytest.mark.asyncio]


# ── Shared helpers ──────────────────────────────────────────────────────────

def _exec_services(world: Dict[str, Any]) -> Dict[str, Any]:
    """Services dict for ``execute_plan``.

    ``user_id=0`` is the seeded system/automation admin identity — the ONLY
    identity ``PermissionService.can_create_invoice`` accepts for a successful
    invoice write (it allows admin/manager only; every persona user is a
    dispatcher).  ``role="admin"`` clears the executor's permission gate the
    same way.
    """
    return {
        "db": world["db"],
        "company_id": world["company_id"],
        "user_id": 0,
        "role": "admin",
    }


def _draft_batch_plan(
    world: Dict[str, Any], plan_id: str, trip_ids: Sequence[int]
) -> Any:
    """One deterministic batch-draft plan — one ``invoice.draft`` step per trip.

    The real batch "tool" is a multi-step plan: no ``invoice.batch`` tool
    exists in the registry, so ARGO drafts a batch by scheduling one
    ``invoice.draft`` call per delivered trip.
    """
    db = world["db"]
    steps: List[ExecutionStep] = []
    for i, trip_id in enumerate(trip_ids):
        row = db.conn.execute(
            "SELECT client_id, total_price_eur FROM trips WHERE id = ?",
            (trip_id,),
        ).fetchone()
        steps.append(
            make_step(
                "invoice.draft",
                {
                    "client_id": row["client_id"],
                    "trip_id": trip_id,
                    "amount": float(row["total_price_eur"]),
                },
                step_id=f"{plan_id}-draft-{i + 1}",
            )
        )
    return build_plan(plan_id, steps, intent_name="invoice.batch_draft")


def _invoice_count(db: Any) -> int:
    return db.conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]


def _invoice_row(db: Any, invoice_id: int) -> Dict[str, Any]:
    row = db.conn.execute(
        "SELECT id, trip_id, status, pdf_path, line_items_json "
        "FROM invoices WHERE id = ?",
        (invoice_id,),
    ).fetchone()
    assert row is not None
    return dict(row)


def _first_invoice_id(db: Any) -> int:
    """ID of the first invoice row (tests create exactly one before reading)."""
    row = db.conn.execute("SELECT id FROM invoices LIMIT 1").fetchone()
    assert row is not None
    return int(row[0])


# ── A. Batch draft idempotency (§5.2 row 1 + §8 scenario 7) ────────────────

class TestBatchDraftIdempotency:
    """ARGO-INV-01: batch draft creates 3 drafts and never duplicates them."""

    async def test_batch_draft_plan_creates_exactly_three_drafts(
        self, workflow_env, db
    ):
        """One batch-draft plan over the 3 delivered trips → 3 draft invoices."""
        world = build_argo_world(db)
        assert _invoice_count(db) == 0

        plan = _draft_batch_plan(world, "argo-inv-batch-1", world["delivered_trip_ids"])
        executed = await execute_plan(plan, services=_exec_services(world))

        assert [s.status for s in executed.steps] == ["succeeded"] * 3
        for step in executed.steps:
            assert step.result is not None
            assert step.result["status"] == "success"
        assert _invoice_count(db) == 3

        statuses = {
            r["status"]
            for r in db.conn.execute("SELECT status FROM invoices").fetchall()
        }
        assert statuses == {"draft"}

    async def test_each_delivered_trip_has_exactly_one_invoice(self, workflow_env, db):
        """Every delivered trip maps to exactly one invoice row (schema guard)."""
        world = build_argo_world(db)
        await execute_plan(
            _draft_batch_plan(world, "argo-inv-batch-2", world["delivered_trip_ids"]),
            services=_exec_services(world),
        )

        # No trip_id repeats and none is missing — the UNIQUE constraint held.
        rows = db.conn.execute(
            "SELECT trip_id, COUNT(*) AS n FROM invoices GROUP BY trip_id"
        ).fetchall()
        assert len(rows) == 3
        for row in rows:
            assert row["n"] == 1
        assert {r["trip_id"] for r in rows} == set(world["delivered_trip_ids"])

    async def test_batch_draft_rerun_is_idempotent(self, workflow_env, db):
        """Re-running the batch plan does not create duplicates.

        The real uniqueness mechanism is the schema UNIQUE constraint on
        ``invoices.trip_id`` — there is no tool-level pre-check.  The second
        run's steps fail with ``copilot.error.internal`` and the constraint
        message, and the invoice count stays 3 (no silent duplicate, no
        partial failure).
        """
        world = build_argo_world(db)
        trip_ids = world["delivered_trip_ids"]

        first = await execute_plan(
            _draft_batch_plan(world, "argo-inv-batch-3", trip_ids),
            services=_exec_services(world),
        )
        assert [s.status for s in first.steps] == ["succeeded"] * 3
        assert _invoice_count(db) == 3

        # Re-run the SAME batch over the same trips.
        second = await execute_plan(
            _draft_batch_plan(world, "argo-inv-batch-3-rerun", trip_ids),
            services=_exec_services(world),
        )

        assert _invoice_count(db) == 3
        for step in second.steps:
            assert step.status == "failed"
            assert step.error == "copilot.error.internal"
            assert step.result is not None
            # The schema-level guard, surfaced through the tool:
            assert "UNIQUE constraint failed: invoices.trip_id" in step.result[
                "message_params"
            ]["error"]


# ── B. Finalize + PDF failure (§5.2 row 2 + §8.5.8) ─────────────────────────

class TestFinalizePdfFailure:
    """ARGO-INV-02: PDF-generation crashes are surfaced, never silent."""

    async def test_pdf_failure_leaves_invoice_draft(self, workflow_env, db):
        """PDF generator crash → step fails, invoice stays draft (unchanged)."""
        world = build_argo_world(db)
        await execute_plan(
            _draft_batch_plan(world, "argo-inv-b-1", world["delivered_trip_ids"]),
            services=_exec_services(world),
        )
        invoice_id = _first_invoice_id(db)
        before = _invoice_row(db, invoice_id)
        assert before["status"] == "draft"
        assert not before["pdf_path"]

        pdf_plan = build_plan(
            "argo-inv-b-1-pdf",
            [make_step("invoice.generate_pdf", {"invoice_id": invoice_id},
                       step_id="b-1-pdf")],
            intent_name="invoice.finalize",
        )
        # Patch the real file-writing seam: InvoiceGenerator.generate raises.
        with patch(
            "services.invoicing.generator.InvoiceGenerator.generate",
            side_effect=RuntimeError("pdf generator crash"),
        ):
            executed = await execute_plan(pdf_plan, services=_exec_services(world))

        assert executed.steps[0].status == "failed"
        assert executed.steps[0].error == "copilot.error.service_error"

        after = _invoice_row(db, invoice_id)
        assert after["status"] == "draft"       # status unchanged
        assert not after["pdf_path"]            # no partial artifact

    async def test_pdf_retry_after_recovery_succeeds(self, workflow_env, db):
        """After the crash is cleared, the same generate_pdf step succeeds.

        The generator seam is stubbed (returns a path, writes nothing) so the
        test never places a real PDF on disk.  ``invoice.generate_pdf`` does
        not mutate status, so the invoice stays a draft with a stored pdf_path.
        """
        world = build_argo_world(db)
        await execute_plan(
            _draft_batch_plan(world, "argo-inv-b-2", world["delivered_trip_ids"]),
            services=_exec_services(world),
        )
        invoice_id = _invoice_row(db, db.conn.execute(
            "SELECT id FROM invoices LIMIT 1"
        ).fetchone()[0])["id"]
        assert _invoice_row(db, invoice_id)["status"] == "draft"

        pdf_plan = build_plan(
            "argo-inv-b-2-pdf",
            [make_step("invoice.generate_pdf", {"invoice_id": invoice_id},
                       step_id="b-2-pdf")],
            intent_name="invoice.finalize",
        )
        with patch(
            "services.invoicing.generator.InvoiceGenerator.generate",
            return_value="invoices/argo_test_no_real_write.pdf",
        ) as gen:
            executed = await execute_plan(pdf_plan, services=_exec_services(world))

        assert executed.steps[0].status == "succeeded"
        gen.assert_called_once()
        after = _invoice_row(db, invoice_id)
        assert after["pdf_path"] == "invoices/argo_test_no_real_write.pdf"
        assert after["status"] == "draft"       # pdf step never changes status

    async def test_finalize_locks_invoice_pdf_failure_keeps_it_locked(
        self, workflow_env, db
    ):
        """Real finalize behavior + §8.5.8 PDF crash on a finalized invoice.

        Documents the implementation gap vs §3.5 ("On finalize: PDF
        auto-generated"): ``invoice.finalize`` does NOT generate a PDF.  When
        the PDF step then crashes, the failure is surfaced and the locked
        (finalized) status is left unchanged — no silent partial state.
        """
        world = build_argo_world(db)
        await execute_plan(
            _draft_batch_plan(world, "argo-inv-b-3", world["delivered_trip_ids"]),
            services=_exec_services(world),
        )
        invoice_id = _invoice_row(db, db.conn.execute(
            "SELECT id FROM invoices LIMIT 1"
        ).fetchone()[0])["id"]

        fin_plan = build_plan(
            "argo-inv-b-3-finalize",
            [make_step("invoice.finalize", {"invoice_id": invoice_id},
                       step_id="b-3-finalize")],
            intent_name="invoice.finalize",
        )
        finalized = await execute_plan(fin_plan, services=_exec_services(world))
        assert finalized.steps[0].status == "succeeded"
        assert _invoice_row(db, invoice_id)["status"] == "finalized"

        pdf_plan = build_plan(
            "argo-inv-b-3-pdf",
            [make_step("invoice.generate_pdf", {"invoice_id": invoice_id},
                       step_id="b-3-pdf")],
            intent_name="invoice.finalize",
        )
        with patch(
            "services.invoicing.generator.InvoiceGenerator.generate",
            side_effect=RuntimeError("pdf generator crash"),
        ):
            failed = await execute_plan(pdf_plan, services=_exec_services(world))

        assert failed.steps[0].status == "failed"
        assert _invoice_row(db, invoice_id)["status"] == "finalized"  # unchanged


# ── C. Missing-VAT probe (§5.2 row 3) ───────────────────────────────────────

class TestMissingClientVat:
    """ARGO-INV-03: what actually happens when a client has no VAT data.

    GAP-DOC-§5.2-C: blueprint §5.2 row 3 expects ARGO to detect a missing VAT
    rate and block invoice creation.  The real implementation does NOT:
    ``clients`` has no ``vat_rate`` column, ``InvoiceDraftTool`` never reads
    client VAT, and ``InvoiceLineItem`` defaults ``vat_rate`` to 19.0.  These
    tests pin the ACTUAL behavior so the gap is visible and documented.
    """

    async def test_missing_client_vat_rate_defaults_to_19_not_blocked(
        self, workflow_env, db
    ):
        """A VAT-less client's trip drafts successfully with the default 19%."""
        world = build_argo_world(db)

        # The clients schema has no vat_rate column at all.
        client_cols = [r["name"] for r in db.conn.execute("PRAGMA table_info(clients)")]
        assert "vat_rate" not in client_cols

        # Client row with NO VAT data (no vat_number, no anything).
        db.conn.execute(
            "INSERT INTO clients (name, email, is_active, created_at, updated_at) "
            "VALUES (?, ?, 1, datetime('now'), datetime('now'))",
            ("NoVAT Logistics", "novat@example.com"),
        )
        db.conn.commit()
        vatless_client_id = db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        from tests.workflow_integrity.personas.fixtures import seed_trip

        trip_id = seed_trip(
            db,
            company_id=world["company_id"],
            client_id=vatless_client_id,
            client_name="NoVAT Logistics",
            status="Delivered",
            distance_km=KNOWN_VALUES["distance_km"],
            total_price_eur=KNOWN_VALUES["total_price_eur"],
            currency=KNOWN_VALUES["currency"],
            fuel_cost=KNOWN_VALUES["fuel_cost"],
            toll_cost=KNOWN_VALUES["toll_cost"],
            salary_cost=KNOWN_VALUES["salary_cost"],
            extra_costs=KNOWN_VALUES["extra_costs"],
            net_profit=KNOWN_VALUES["net_profit"],
            rate_per_km=KNOWN_VALUES["rate_per_km"],
            gross_per_km=KNOWN_VALUES["gross_per_km"],
        )

        plan = build_plan(
            "argo-inv-c-1",
            [make_step(
                "invoice.draft",
                {
                    "client_id": vatless_client_id,
                    "trip_id": trip_id,
                    "amount": float(KNOWN_VALUES["total_price_eur"]),
                },
                step_id="c-1-draft",
            )],
            intent_name="invoice.draft",
        )
        executed = await execute_plan(plan, services=_exec_services(world))

        # NOT blocked — the draft succeeds (this is the documented gap).
        assert executed.steps[0].status == "succeeded"
        assert executed.steps[0].result is not None
        assert executed.steps[0].result["message_key"] == "copilot.invoice.draft.success"

        row = db.conn.execute(
            "SELECT id, status, line_items_json FROM invoices WHERE trip_id = ?",
            (trip_id,),
        ).fetchone()
        assert row is not None
        assert row["status"] == "draft"
        line_items = json.loads(row["line_items_json"])
        # model_dump(mode="json") serializes the Decimal as the string "19.0".
        assert float(line_items[0]["vat_rate"]) == 19.0  # InvoiceLineItem default

    async def test_draft_failure_never_references_vat(self, workflow_env, db):
        """No failure path of invoice.draft mentions VAT for a VAT-less client.

        Even when the SAME trip is drafted twice (schema UNIQUE guard fires),
        the surfaced error is the constraint — never a VAT validation, because
        no VAT check exists.
        """
        world = build_argo_world(db)
        # VAT-less client + trip (minimal reuse of the canonical trip row).
        db.conn.execute(
            "INSERT INTO clients (name, email, is_active, created_at, updated_at) "
            "VALUES (?, ?, 1, datetime('now'), datetime('now'))",
            ("NoVAT Two", "novat2@example.com"),
        )
        db.conn.commit()
        vatless_client_id = db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        from tests.workflow_integrity.personas.fixtures import seed_trip

        trip_id = seed_trip(
            db,
            company_id=world["company_id"],
            client_id=vatless_client_id,
            client_name="NoVAT Two",
            status="Delivered",
            total_price_eur=KNOWN_VALUES["total_price_eur"],
        )

        services = _exec_services(world)
        await execute_plan(
            build_plan(
                "argo-inv-c-2a",
                [make_step("invoice.draft", {
                    "client_id": vatless_client_id, "trip_id": trip_id,
                    "amount": float(KNOWN_VALUES["total_price_eur"])},
                    step_id="c-2a")],
                intent_name="invoice.draft",
            ),
            services=services,
        )
        rerun = await execute_plan(
            build_plan(
                "argo-inv-c-2b",
                [make_step("invoice.draft", {
                    "client_id": vatless_client_id, "trip_id": trip_id,
                    "amount": float(KNOWN_VALUES["total_price_eur"])},
                    step_id="c-2b")],
                intent_name="invoice.draft",
            ),
            services=services,
        )
        assert rerun.steps[0].status == "failed"
        assert rerun.steps[0].error == "copilot.error.internal"
        assert rerun.steps[0].result is not None
        assert "vat" not in rerun.steps[0].error.lower()
        assert "vat" not in rerun.steps[0].result["message_params"]["error"].lower()