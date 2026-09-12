"""ARGO-THRESH: §5.7 success-rate thresholds + §5.8 determinism proxies.

Encodes the blueprint's §5.7 encoded success-rate table (the exact minima
copied below as module constants) and verifies the deterministic layers of
the system meet them.  Plans/worlds are built DIRECTLY from the ARGO fixtures
(``build_argo_world`` / ``build_plan`` / ``make_step`` / ``make_tool_context``)
— never through the planner, never an LLM — so the measured rates are
properties of the deterministic executor/tool stack, not of an LLM.

Real tool classes exercised (registry-backed, same code the executor calls):

* ``DispatchCreateTool``     — ``dispatch.create``     (``dispatch_tools.py``)
  wraps ``DispatchService.assign_both`` (test A — determinism proxy).
* ``DispatchBulkAssignTool`` — ``dispatch.bulk_assign`` (``dispatch_tools.py``)
  wraps ``DispatchService.bulk_assign_truck`` (tests B/D — single-step plans).
* ``InvoiceDraftTool``       — ``invoice.draft``       (``invoice_tools.py``)
  wraps the schema-level idempotency guard (test C — invoice total determinism).

Tests
-----
(A) Determinism proxy — the same dispatch request, executed 10 times on a
    fresh identical world each time, selects the same truck + driver (blueprint
    §5.8 "Same dispatch request executed 10 times → same truck + driver").
    ``dispatch.create`` cannot run through the executor (documented Gap 1:
    ``DispatchCreateParams``'s cross-field validator rejects every input), so
    the real tool is exercised directly with ``model_construct`` — the exact
    pattern used by ARGO-DISP (§5.1).
(B) Single-step success — 10/10 single-step ``dispatch.bulk_assign`` plans
    executed through the executor reach ``succeeded``.
(C) Invoice determinism — the same invoice-generation request executed 5 times
    on a fresh world each time yields byte-identical invoice totals
    (blueprint §5.8 "Same invoice generation request executed 5 times →
    identical invoice totals").
(D) Measured-rate assertions — the measured single-step success rate from the
    deterministic sample is asserted against the encoded §5.7 minimum
    (``SINGLE_STEP_PLAN_MIN = 0.95``).  Trivially green for deterministic
    code; fails only on real flakiness.  Verifying the REAL-LLM threshold
    (end-to-end plans routed through the planner) is a Phase 6 concern and is
    intentionally NOT applicable here.

``N`` stays small (10 max per the acceptance criteria) so the whole module
stays comfortably under the 30s budget even under xdist (``--dist=loadscope``
runs the module on a single worker).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Sequence, Tuple
from unittest.mock import patch

import pytest

from backend.copilot.executor import execute_plan
from backend.copilot.tools.dispatch_tools import (
    DispatchCreateParams,
    DispatchCreateTool,
)

from tests.test_helpers import make_db
from tests.workflow_integrity.argo.fixtures import (
    build_argo_world,
    build_plan,
    make_step,
    make_tool_context,
    reset_circuit_breaker,
)
from tests.workflow_integrity.personas.fixtures import seed_trip

pytestmark = pytest.mark.argo

# ═════════════════════════════════════════════════════════════════════════════
# §5.7 encoded success-rate table (exact minima from the blueprint; target /
# stretch columns kept for reference so the encoding is complete)
# ═════════════════════════════════════════════════════════════════════════════

SINGLE_STEP_PLAN_MIN = 0.95        # Single-step plan success rate (95%)
MULTI_STEP_PLAN_MIN = 0.85         # Multi-step plan completion rate (85%)
DISPATCH_ACCURACY_MIN = 0.90       # Autonomous dispatch accuracy (90%)
INVOICE_GENERATION_MIN = 0.95      # Invoice auto-generation accuracy (95%)
HANDOFF_APPROPRIATENESS_MIN = 0.90  # Human handoff appropriateness (90%)
ROLLBACK_SUCCESS_MIN = 0.95        # Plan rollback success (95%)
TOOL_DETERMINISM_MIN = 0.99        # Tool-level determinism (99%)
SAFETY_BOUNDARY_MIN = 1.00         # Safety boundary enforcement (100%)

SUCCESS_RATE_TABLE: Dict[str, Dict[str, float]] = {
    "single_step_plan": {
        "min": SINGLE_STEP_PLAN_MIN, "target": 0.98, "stretch": 0.995,
    },
    "multi_step_plan": {
        "min": MULTI_STEP_PLAN_MIN, "target": 0.92, "stretch": 0.97,
    },
    "autonomous_dispatch": {
        "min": DISPATCH_ACCURACY_MIN, "target": 0.95, "stretch": 0.99,
    },
    "invoice_auto_generation": {
        "min": INVOICE_GENERATION_MIN, "target": 0.98, "stretch": 1.00,
    },
    "human_handoff": {
        "min": HANDOFF_APPROPRIATENESS_MIN, "target": 0.95, "stretch": 0.98,
    },
    "plan_rollback": {
        "min": ROLLBACK_SUCCESS_MIN, "target": 0.98, "stretch": 1.00,
    },
    "tool_determinism": {
        "min": TOOL_DETERMINISM_MIN, "target": 0.999, "stretch": 1.00,
    },
    "safety_boundary": {
        "min": SAFETY_BOUNDARY_MIN, "target": 1.00, "stretch": 1.00,
    },
}

# Iteration counts — kept small (10 max) to bound runtime under xdist.
DISPATCH_DETERMINISM_RUNS = 10  # §5.8: same dispatch request × 10
SINGLE_STEP_SUCCESS_RUNS = 10   # §5.7: single-step success-rate sample
INVOICE_DETERMINISM_RUNS = 5    # §5.8: same invoice request × 5


# ── Autouse hygiene (same discipline as ARGO-DISP §5.1) ──────────────────────

@pytest.fixture(autouse=True)
def _force_inline_execution():
    """Pin the executor's §13 Celery gate off so steps never leave-process."""
    with patch("backend.copilot.executor._is_celery_broker_available", return_value=False):
        yield


@pytest.fixture(autouse=True)
def _reset_circuit_breaker_after():
    """CircuitBreaker state is class-level — never leak into the next test."""
    yield
    reset_circuit_breaker()


# ── Deterministic helpers ────────────────────────────────────────────────────

def _run(coro):
    """Run one async tool/executor call inside a fresh event loop."""
    return asyncio.run(coro)


def _seed_system_user(db: Any) -> None:
    """Insert the system/automation identity (id=0) used by invoice writes.

    Mirrors ``tests/workflow_integrity/conftest.py::_seed_system_user`` (the
    conftest fixture seeds the ``db`` fixture, not the per-iteration DBs this
    module creates with ``make_db()``).  ``PermissionService`` rejects unknown
    users, and ``InvoiceDraftTool``'s permission path needs user 0 to exist.
    """
    db.conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, role, is_active, "
        "display_name, created_at) VALUES (0, 'system@local', 'hash', 'admin', 1, "
        "'System', datetime('now'))"
    )
    db.conn.commit()


def _fresh_world() -> Dict[str, Any]:
    """One fresh, identically-seeded ARGO world on its own in-memory DB.

    Deterministic by construction: ``make_db()`` + the fixed world seed always
    produce the same ids/rows, so an iteration on a fresh world is exactly
    comparable to any other iteration on a fresh world.
    """
    db = make_db()
    _seed_system_user(db)
    return build_argo_world(db)


def _dispatch_ctx(world: Dict[str, Any], *, role: str = "dispatcher"):
    """ToolExecutionContext for the ARGO world (Ana, the dispatcher by default)."""
    return make_tool_context(
        world["db"],
        company_id=world["company_id"],
        user_id=world["user_id"],
        role=role,
    )


def _create_params(trip_id: int, truck_id=None, driver_id=None) -> DispatchCreateParams:
    """Build ``dispatch.create`` params, bypassing the broken cross-field validator.

    Documented Gap 1 (see ARGO-DISP §5.1 module docstring): the real
    ``DispatchCreateParams(...)`` constructor raises on every input, so the
    executor can never run a ``dispatch.create`` step.  ``model_construct``
    skips only that broken validator — the params the tool's real service code
    consumes are otherwise identical.
    """
    return DispatchCreateParams.model_construct(
        trip_id=trip_id, truck_id=truck_id, driver_id=driver_id
    )


def _new_planned_trip(world: Dict[str, Any]) -> int:
    """Insert a fresh, unassigned Planned trip to use as a dispatch target."""
    return seed_trip(
        world["db"],
        company_id=world["company_id"],
        client_id=world["client_ids"][0],
        client_name=f"Client {world['client_ids'][0]}",
        driver_name="",
        driver_id=None,
        truck_number="",
        truck_id=None,
        distance_km=100.0,
        total_price_eur=400.0,
        status="Planned",
        net_profit=200.0,
        rate_per_km=4.0,
        gross_per_km=2.0,
    )


def _dispatch_request(world: Dict[str, Any]) -> Tuple[int, int, int]:
    """The deterministic dispatch request reused across every iteration.

    "Best truck": lowest mileage among the healthy fleet — deterministic
    (the Ana fleet's mileages are unique).  "Best load": highest-margin
    freight load (the same selection rule ARGO-DISP scenario A uses).
    Returns ``(best_truck_id, trip_id, driver_id)``.
    """
    mileages = {
        tid: world["db"].conn.execute(
            "SELECT mileage FROM trucks WHERE id = ?", (tid,)
        ).fetchone()[0]
        for tid in world["healthy_truck_ids"]
    }
    best_truck = min(mileages, key=mileages.get)
    best_load = max(world["freight_loads"], key=lambda load: load["margin_pct"])
    return best_truck, best_load["trip_id"], world["driver_ids"][0]


def _dispatch_selection(world: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """Run the fixed dispatch request on one world; return the chosen assignment.

    Returns ``(requested_truck, requested_driver, row_truck, row_driver)`` — the
    (requested, then persisted) truck/driver pair, so the determinism check
    covers both what the tool reported and what the trip row actually holds.
    """
    best_truck, trip_id, driver_id = _dispatch_request(world)
    result = _run(
        DispatchCreateTool().execute(
            _create_params(trip_id, best_truck, driver_id), _dispatch_ctx(world)
        )
    )
    assert result.status == "success", result
    row = world["db"].conn.execute(
        "SELECT truck_id, driver_id FROM trips WHERE id = ?", (trip_id,)
    ).fetchone()
    return (best_truck, driver_id, row["truck_id"], row["driver_id"])


def _run_single_step_dispatch(world: Dict[str, Any], run_id: int) -> str:
    """Execute one single-step ``dispatch.bulk_assign`` plan; return step status.

    One fresh Planned trip per world gets the fleet's first healthy truck via
    the REAL ``dispatch.bulk_assign`` tool through the executor.  The tool's
    params schema is constructible (unlike ``DispatchCreateParams``), so the
    executor path is the real one end to end.
    """
    trip_id = _new_planned_trip(world)
    plan = build_plan(
        f"threshold-single-{run_id}",
        [
            make_step(
                "dispatch.bulk_assign",
                {
                    "trip_ids": [trip_id],
                    "assign_type": "truck",
                    "assign_id": world["healthy_truck_ids"][0],
                },
            )
        ],
        intent_name="dispatch.bulk_assign",
    )
    executed = _run(
        execute_plan(
            plan,
            services={
                "db": world["db"],
                "company_id": world["company_id"],
                "user_id": world["user_id"],
                "role": "dispatcher",
            },
        )
    )
    step = executed.steps[0]
    if step.status == "succeeded":
        # Pin the real write: one item assigned, zero failures.
        assert step.result is not None
        assert step.result["data"]["total"] == 1
        assert step.result["data"]["success_count"] == 1
    return step.status


def _invoice_signature(world: Dict[str, Any], run_id: int) -> Tuple[Tuple[Any, ...], ...]:
    """Generate the canonical invoices for one world; return their totals.

    One ``invoice.draft`` step per delivered trip (the real batch flow — no
    ``invoice.batch`` tool exists, so ARGO batches by scheduling one draft per
    trip), executed through the executor with the system/automation identity.
    Returns a sorted tuple of invoice total rows — the "invoice totals" whose
    equality across runs the determinism test asserts.
    """
    steps: List[Any] = []
    for i, trip_id in enumerate(world["delivered_trip_ids"]):
        row = world["db"].conn.execute(
            "SELECT client_id, total_price_eur FROM trips WHERE id = ?", (trip_id,)
        ).fetchone()
        steps.append(
            make_step(
                "invoice.draft",
                {
                    "client_id": row["client_id"],
                    "trip_id": trip_id,
                    "amount": float(row["total_price_eur"]),
                },
                step_id=f"threshold-inv-{run_id}-{i}",
            )
        )
    plan = build_plan(
        f"threshold-inv-{run_id}", steps, intent_name="invoice.batch_draft"
    )
    executed = _run(
        execute_plan(
            plan,
            services={
                "db": world["db"],
                "company_id": world["company_id"],
                "user_id": 0,  # seeded system/automation admin identity
                "role": "admin",
            },
        )
    )
    assert all(s.status == "succeeded" for s in executed.steps), [
        (s.status, s.error) for s in executed.steps
    ]
    rows = world["db"].conn.execute(
        "SELECT trip_id, invoice_number, total_amount, total_gross, "
        "subtotal_net, total_vat, currency, status FROM invoices"
    ).fetchall()
    return tuple(sorted(tuple(r) for r in rows))


# ═════════════════════════════════════════════════════════════════════════════
# (A) Dispatch determinism proxy (§5.8 row 1)
# ═════════════════════════════════════════════════════════════════════════════

class TestDispatchDeterminismProxy:
    """ARGO-THRESH-A: same dispatch request × 10 fresh worlds → same truck/driver.

    Proxy for the real-LLM dispatch decision: the deterministic request
    (best truck + best load + first driver) is dispatched through the real
    ``dispatch.create`` tool once per fresh world.  If ANY selection rule,
    fleet ordering, or world build became non-deterministic, the observed
    truck/driver pair would drift across iterations.
    """

    def test_same_dispatch_plan_selects_same_truck_and_driver_every_run(self):
        """10 identical requests on 10 identical worlds → one identical result."""
        selections = [
            _dispatch_selection(_fresh_world()) for _ in range(DISPATCH_DETERMINISM_RUNS)
        ]

        assert len(selections) == DISPATCH_DETERMINISM_RUNS
        assert len(set(selections)) == 1, (
            "dispatch selection drifted across identical worlds: "
            f"{sorted(set(selections))}"
        )

        # And it is exactly the deterministic expectation (best truck, driver 1).
        expected_truck, _, expected_driver = _dispatch_request(_fresh_world())
        truck_id, driver_id, row_truck, row_driver = selections[0]
        assert (truck_id, driver_id) == (expected_truck, expected_driver)
        assert (row_truck, row_driver) == (expected_truck, expected_driver)

    def test_tool_determinism_min_encoded_in_table(self):
        """The §5.7 tool-determinism minimum is encoded (99%) — sanity pin."""
        assert SUCCESS_RATE_TABLE["tool_determinism"]["min"] == TOOL_DETERMINISM_MIN == 0.99
        assert DISPATCH_ACCURACY_MIN == 0.90
        assert INVOICE_GENERATION_MIN == 0.95


# ═════════════════════════════════════════════════════════════════════════════
# (B) Single-step plan success (§5.7 row 1)
# ═════════════════════════════════════════════════════════════════════════════

class TestSingleStepPlanSuccess:
    """ARGO-THRESH-B: 10/10 single-step plans reach ``succeeded``.

    Each iteration is one fresh world and one single-step
    ``dispatch.bulk_assign`` plan through the executor — the real registry
    tool, real service code, real permission gate.  Success is measured by the
    step's terminal status; every failed run lands in the assertion detail.
    """

    def test_all_single_step_plans_succeed(self):
        """A 10-run sample of single-step plans: every step succeeds."""
        statuses = [
            _run_single_step_dispatch(_fresh_world(), i)
            for i in range(SINGLE_STEP_SUCCESS_RUNS)
        ]
        assert len(statuses) == SINGLE_STEP_SUCCESS_RUNS
        assert all(s == "succeeded" for s in statuses), (
            f"failed runs: {[i for i, s in enumerate(statuses) if s != 'succeeded']}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# (C) Invoice total determinism (§5.8 row 2)
# ═════════════════════════════════════════════════════════════════════════════

class TestInvoiceTotalDeterminism:
    """ARGO-THRESH-C: same invoice request × 5 fresh worlds → identical totals.

    The real ``invoice.draft`` batch flow runs once per fresh world; the
    resulting invoice totals (amount, gross, net, VAT, currency, number,
    status) must be byte-identical across all five runs — same trip data can
    never produce different totals.
    """

    def test_invoice_totals_identical_across_runs(self):
        """5 identical generation requests on 5 identical worlds → one signature."""
        signatures = [
            _invoice_signature(_fresh_world(), i) for i in range(INVOICE_DETERMINISM_RUNS)
        ]
        assert len(signatures) == INVOICE_DETERMINISM_RUNS
        assert len(set(signatures)) == 1, (
            "invoice totals drifted across identical worlds"
        )

        # Pin the canonical value so a drift into a *consistent wrong* total is
        # still caught: each canonical trip is EUR 1350 → 1350 * 1.19 gross.
        totals = signatures[0]
        assert len(totals) == 3  # the 3 canonical delivered trips
        for row in totals:
            assert row[3] == row[2] == 1606.5, row  # total_amount == total_gross
            assert row[4] == 1350.0, row             # subtotal_net
            assert row[5] == 256.5, row              # total_vat


# ═════════════════════════════════════════════════════════════════════════════
# (D) Measured-rate assertions (§5.7)
# ═════════════════════════════════════════════════════════════════════════════

class TestMeasuredSuccessRate:
    """ARGO-THRESH-D: measured single-step success ≥ encoded §5.7 minimum.

    The measured success rate over a fresh deterministic sample is asserted
    against ``SINGLE_STEP_PLAN_MIN`` (0.95).  For deterministic fixture-built
    code this is trivially green (10/10); it fails only if real flakiness
    (transient tool errors, leaked singleton state, ordering drift) sneaks in.
    Real-LLM threshold verification — end-to-end plans routed through the
    planner and provider — is a Phase 6 concern and NOT applicable to this
    deterministic suite.
    """

    def test_measured_single_step_success_rate_meets_encoded_minimum(self):
        """measured_success / sample_size >= SINGLE_STEP_PLAN_MIN."""
        statuses = [
            _run_single_step_dispatch(_fresh_world(), i)
            for i in range(SINGLE_STEP_SUCCESS_RUNS)
        ]
        succeeded = sum(1 for s in statuses if s == "succeeded")
        measured = succeeded / len(statuses)

        assert measured >= SINGLE_STEP_PLAN_MIN, (
            f"measured single-step success rate {measured:.2f} "
            f"< encoded minimum {SINGLE_STEP_PLAN_MIN:.2f} "
            f"(succeeded {succeeded}/{len(statuses)})"
        )