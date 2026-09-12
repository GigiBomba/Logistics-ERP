"""ARGO fixtures — deterministic foundation for the §5.1–5.7 autonomous tests.

Everything here builds Co-Pilot objects DIRECTLY from the Pydantic contracts
(``backend.copilot.schemas`` / ``backend.copilot.tools.base``).  It never
routes through ``planner.process_utterance()`` and therefore never invokes an
LLM — same input always yields the same plan/context, which is what the
determinism and adversarial suites need.

API
---
* ``make_step(tool_name, params, level, depends_on)``
    One :class:`ExecutionStep` ready for a plan.  Required schema fields
    (``tool_version``, ``status``, ``step_id``) are filled in so a bare step
    validates immediately.
* ``build_plan(plan_id, steps, intent_name, ...)``
    One validated :class:`ExecutionPlan`.  ``conversation_id`` /
    ``reasoning_graph_id`` / ``raw_utterance`` are defaulted deterministically
    from the plan id when the caller does not supply them.
* ``make_tool_context(db, company_id, user_id, role)``
    One :class:`ToolExecutionContext` mirroring the executor's convention
    (``db`` travels inside ``services`` — the context itself never carries a
    raw session field).  Importable with no Qt on the path.
* ``build_argo_world(db)``
    Seeded database world: the Ana dispatcher persona + one
    CRITICAL-maintenance (dispatch-blocked) truck + 3 canonical delivered
    trips + the shared freight-exchange loads.  Returns a dict of ids.
* ``reset_circuit_breaker()``
    Clears the CircuitBreaker class-level state (and the global singleton),
    mirroring the root ``tests/conftest.reset_singletons`` convention so
    tests that trip a breaker never leak state into later tests.
"""

from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional, Sequence

from backend.copilot.schemas import (
    ConfirmationLevel,
    ExecutionPlan,
    ExecutionStep,
    Intent,
    SessionContext,
)
from backend.copilot.tools.base import ToolExecutionContext

from tests.workflow_integrity.personas.ana_dispatcher import build_ana_persona
from tests.workflow_integrity.personas.fixtures import seed_trip
from tests.workflow_integrity.fixtures.workflow_data import (
    FREIGHT_LOADS,
    KNOWN_VALUES,
    MAINTENANCE_TICKETS,
)

__all__ = [
    "make_step",
    "build_plan",
    "make_tool_context",
    "build_argo_world",
    "reset_circuit_breaker",
    # Re-exported canonical data so tests only need one import site.
    "FREIGHT_LOADS",
    "KNOWN_VALUES",
    "MAINTENANCE_TICKETS",
]

# ── Deterministic id / timestamp constants ────────────────────────────────
# Fixed strings, never clock-derived, so two calls in the same process (or two
# CI runs) produce byte-identical plans and seeded rows.
_ARGO_EPOCH_TS = "2026-07-21T08:00:00"
_DEFAULT_TOOL_VERSION = "1.0.0"

_step_ids = itertools.count(1)


# ── ExecutionStep / ExecutionPlan builders ────────────────────────────────

def make_step(
    tool_name: str,
    params: Dict[str, Any],
    level: ConfirmationLevel = ConfirmationLevel.SAFE,
    depends_on: Optional[Sequence[str]] = None,
    *,
    step_id: Optional[str] = None,
    tool_version: str = _DEFAULT_TOOL_VERSION,
    status: str = "pending",
) -> ExecutionStep:
    """Build one validated :class:`ExecutionStep`.

    Required schema fields without defaults are filled deterministically:
    ``tool_version`` → ``"1.0.0"``, ``status`` → ``"pending"``, and
    ``step_id`` → ``"step-N"`` (a monotonic counter).  Pass ``step_id`` to pin
    an exact id (e.g. when a later step's ``depends_on`` must reference it by
    string).  ``depends_on`` accepts a single id, a list of ids, or ``None``.
    """
    if depends_on is None:
        depends_on = []
    elif isinstance(depends_on, str):
        depends_on = [depends_on]
    else:
        depends_on = list(depends_on)

    return ExecutionStep(
        step_id=step_id or f"step-{next(_step_ids)}",
        tool_name=tool_name,
        tool_version=tool_version,
        parameters=dict(params or {}),
        depends_on=depends_on,
        confirmation_level=level,
        status=status,
    )


def build_plan(
    plan_id: str,
    steps: Sequence[ExecutionStep],
    intent_name: str = "dispatch.create",
    overall_confidence: float = 0.9,
    requires_confirmation: bool = False,
    *,
    conversation_id: Optional[str] = None,
    reasoning_graph_id: Optional[str] = None,
    raw_utterance: Optional[str] = None,
    entities: Optional[List[Dict[str, Any]]] = None,
    **extra: Any,
) -> ExecutionPlan:
    """Build one validated :class:`ExecutionPlan` with every required field.

    ``conversation_id``/``reasoning_graph_id`` default to ``conv-<plan_id>`` /
    ``rg-<plan_id>`` and ``raw_utterance`` to a readable auto string, keeping
    plans deterministic while still allowing full overrides.  ``entities``
    accepts raw dicts (they are coerced by the ``Intent`` schema).  Any extra
    keyword (e.g. ``paused``, ``reasoning_graph_nodes``,
    ``used_llm_tokens``) is forwarded to the ``ExecutionPlan`` constructor.
    """
    return ExecutionPlan(
        plan_id=plan_id,
        conversation_id=conversation_id or f"conv-{plan_id}",
        reasoning_graph_id=reasoning_graph_id or f"rg-{plan_id}",
        intent=Intent(
            name=intent_name,
            raw_utterance=raw_utterance or f"Automated {intent_name} ({plan_id})",
            entities=entities or [],
        ),
        steps=list(steps),
        overall_confidence=overall_confidence,
        requires_confirmation=requires_confirmation,
        **extra,
    )


# ── ToolExecutionContext builder ──────────────────────────────────────────

def make_tool_context(
    db: Any,
    company_id: int = 1,
    user_id: int = 1,
    role: str = "owner",
    *,
    session_context: Optional[SessionContext] = None,
    extra_services: Optional[Dict[str, Any]] = None,
) -> ToolExecutionContext:
    """Build one :class:`ToolExecutionContext`.

    Mirrors the executor's convention: the context itself has no ``db`` field
    (``extra="forbid"``), so ``db`` is carried inside ``services`` along with
    ``company_id``/``user_id``/``role``.  ``extra_services`` can inject
    pre-instantiated service objects (trip_service, fleet_repo, ...).

    Note: ``role`` is schema-free (any string validates).  When the context
    will be used to actually *execute* a plan, pass a role the executor's
    permission gate understands — ``"admin"`` (bypass), ``"manager"`` or
    ``"dispatcher"`` — rather than the default ``"owner"``.
    """
    services: Dict[str, Any] = {
        "db": db,
        "company_id": company_id,
        "user_id": user_id,
        "role": role,
    }
    if extra_services:
        services.update(extra_services)

    return ToolExecutionContext(
        company_id=company_id,
        user_id=user_id,
        role=role,
        session_context=session_context or SessionContext(),
        services=services,
    )


# ── Seeded ARGO world ──────────────────────────────────────────────────────

_MAINT_TRUCK_PLATE = "B-900-ARGO-MNT"
_MAINT_TRUCK = {"manufacturer": "Mercedes", "model": "Actros 1845", "year": 2022, "mileage": 95000.0}


def _client_name(db: Any, client_id: int, fallback: str) -> str:
    row = db.conn.execute("SELECT name FROM clients WHERE id = ?", (client_id,)).fetchone()
    return row["name"] if row else fallback


def _insert_maintenance_truck(db: Any, company_id: int) -> int:
    """Insert a CRITICAL-maintenance truck: status='maintenance', inactive."""
    db.conn.execute(
        "INSERT INTO trucks (plate_number, manufacturer, model, year, mileage, "
        "status, active_status, company_id) VALUES (?, ?, ?, ?, ?, 'maintenance', 0, ?)",
        (_MAINT_TRUCK_PLATE, _MAINT_TRUCK["manufacturer"], _MAINT_TRUCK["model"],
         _MAINT_TRUCK["year"], _MAINT_TRUCK["mileage"], company_id),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _add_maintenance_record(db: Any, truck_id: int, ticket: Dict[str, Any]) -> int:
    """Insert one maintenance_records row from a MAINTENANCE_TICKETS dict."""
    db.conn.execute(
        "INSERT INTO maintenance_records (truck_id, maintenance_type, date, notes, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (truck_id, ticket["maint_type"], ticket["date"], ticket["notes"],
         _ARGO_EPOCH_TS, _ARGO_EPOCH_TS),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def build_argo_world(db: Any) -> Dict[str, Any]:
    """Seed a deterministic ARGO test world and return its ids.

    World contents
    --------------
    1. The full **Ana dispatcher persona** (10 trucks, 12 drivers, 6 clients,
       15 trips across Planned → Paid) — see ``ana_dispatcher.py``.
    2. **One CRITICAL-maintenance truck** (``B-900-ARGO-MNT``,
       ``status='maintenance'``, ``active_status=0``) carrying the canonical
       engine-fault ticket from ``MAINTENANCE_TICKETS`` — dispatch must block
       it.  ``maintenance_truck_id`` / ``healthy_truck_ids`` split the fleet.
    3. **Three delivered trips** using the canonical 450 km / EUR 1350
       financials from ``KNOWN_VALUES``.
    4. The shared **freight-exchange loads** (``FREIGHT_LOADS``) seeded as
       ``Planned`` trips with the load economics, plus a by-reference map.

    Returned dict keys
    ------------------
    ``db``, ``company_id``, ``user_id`` (Ana the dispatcher), ``role``,
    ``user_ids``, ``driver_ids``, ``truck_ids``, ``healthy_truck_ids``,
    ``maintenance_truck_id``, ``maintenance_record_ids``,
    ``maintenance_tickets``, ``client_ids``, ``trip_ids`` (persona),
    ``delivered_trip_ids``, ``freight_trip_ids``, ``freight_loads``
    (each load dict annotated with its ``trip_id``) and
    ``freight_trip_by_reference``.
    """
    ana = build_ana_persona(db)
    company_id = ana["company_id"]
    dispatcher_id = ana["user_ids"]["dispatcher"]
    client_ids = ana["client_ids"]
    driver_ids = ana["driver_ids"]
    truck_ids = ana["truck_ids"]

    # ── CRITICAL-maintenance truck ────────────────────────────────────────
    maint_truck_id = _insert_maintenance_truck(db, company_id)
    critical_ticket = dict(MAINTENANCE_TICKETS[0])  # engine fault, blocks dispatch
    maint_record_id = _add_maintenance_record(db, maint_truck_id, critical_ticket)

    # ── 3 canonical delivered trips ───────────────────────────────────────
    delivered_trip_ids: List[int] = []
    for i in range(3):
        client_id = client_ids[i % len(client_ids)]
        tid = seed_trip(
            db,
            company_id=company_id,
            client_id=client_id,
            client_name=_client_name(db, client_id, f"Client {client_id}"),
            driver_name=f"Driver Ana-{(i % 12) + 1:02d}",
            driver_id=driver_ids[i % len(driver_ids)],
            truck_number=f"B-{301 + i}-ANA",
            truck_id=truck_ids[i % len(truck_ids)],
            distance_km=KNOWN_VALUES["distance_km"],
            total_price_eur=KNOWN_VALUES["total_price_eur"],
            status="Delivered",
            start_date=f"2026-06-{(1 + i):02d}",
            end_date=f"2026-06-{(4 + i):02d}",
            currency=KNOWN_VALUES["currency"],
            fuel_cost=KNOWN_VALUES["fuel_cost"],
            toll_cost=KNOWN_VALUES["toll_cost"],
            salary_cost=KNOWN_VALUES["salary_cost"],
            extra_costs=KNOWN_VALUES["extra_costs"],
            net_profit=KNOWN_VALUES["net_profit"],
            rate_per_km=KNOWN_VALUES["rate_per_km"],
            gross_per_km=KNOWN_VALUES["gross_per_km"],
        )
        delivered_trip_ids.append(tid)

    # ── Freight-exchange loads (seeded as Planned trips) ─────────────────
    freight_trip_ids: List[int] = []
    freight_loads: List[Dict[str, Any]] = []
    freight_trip_by_reference: Dict[str, int] = {}
    for i, load in enumerate(FREIGHT_LOADS):
        client_id = client_ids[i % len(client_ids)]
        distance = float(load["distance_km"])
        price = float(load["price_eur"])
        net = float(load["net_profit"])
        tid = seed_trip(
            db,
            company_id=company_id,
            client_id=client_id,
            client_name=_client_name(db, client_id, f"Client {client_id}"),
            driver_name=f"Driver Ana-{(i % 12) + 1:02d}",
            driver_id=driver_ids[i % len(driver_ids)],
            truck_number=f"B-{301 + (i % 10)}-ANA",
            truck_id=truck_ids[i % len(truck_ids)],
            distance_km=distance,
            total_price_eur=price,
            status=load.get("status", "Planned"),
            start_date=f"2026-07-{(25 + i):02d}",
            end_date=f"2026-07-{(28 + i):02d}",
            currency=load.get("currency", "EUR"),
            fuel_cost=float(load["fuel_cost"]),
            toll_cost=float(load["toll_cost"]),
            salary_cost=float(load["salary_cost"]),
            extra_costs=float(load["extra_costs"]),
            net_profit=net,
            rate_per_km=round(price / distance, 2) if distance else 0.0,
            gross_per_km=round(net / distance, 2) if distance else 0.0,
        )
        freight_trip_ids.append(tid)
        annotated = dict(load)
        annotated["trip_id"] = tid
        freight_loads.append(annotated)
        freight_trip_by_reference[load["reference"]] = tid

    return {
        "db": db,
        "company_id": company_id,
        "user_id": dispatcher_id,
        "role": "dispatcher",
        "user_ids": ana["user_ids"],
        "driver_ids": driver_ids,
        "client_ids": client_ids,
        # The Ana fleet is healthy; the maintenance truck is added separately.
        "truck_ids": truck_ids,
        "healthy_truck_ids": list(truck_ids),
        "maintenance_truck_id": maint_truck_id,
        "maintenance_record_ids": [maint_record_id],
        "maintenance_tickets": [{**critical_ticket, "truck_id": maint_truck_id,
                                 "maintenance_record_id": maint_record_id}],
        # Persona trips (Planned → Paid) — see ana_dispatcher.py for the layout.
        "trip_ids": ana["trip_ids"],
        "delivered_trip_ids": delivered_trip_ids,
        "freight_trip_ids": freight_trip_ids,
        "freight_loads": freight_loads,
        "freight_trip_by_reference": freight_trip_by_reference,
    }


# ── Singleton reset helper ────────────────────────────────────────────────

def reset_circuit_breaker() -> None:
    """Clear CircuitBreaker shared state (class-level + global singleton).

    Mirrors the convention used by ``tests/conftest.reset_singletons`` and
    ``tests/copilot/test_golden_regression.py::_reset_circuit_breaker``:
    ``CircuitBreaker._states`` is a class-level dict shared by every instance,
    and the executor reads the module-global singleton.  Clear both so a test
    that deliberately trips the breaker (adversarial/§5.4 scenarios) can never
    leak a blocked company into the next test.
    """
    from backend.copilot.circuit_breaker import CircuitBreaker, get_circuit_breaker

    CircuitBreaker._states.clear()
    get_circuit_breaker()._states.clear()
