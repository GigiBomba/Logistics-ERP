"""Platform parity — shared world builder and matrix-coverage helper.

This module is the shared harness for the §4 "Desktop + Mobile Parity Matrix"
tests (:mod:`.desktop_features` / :mod:`.mobile_features`).  It provides:

* :func:`build_harness_services` — the **real** harness services dict under the
  canonical keys the desktop probes understand.  Construction mirrors the
  workflow-integrity conftest (``tests/workflow_integrity/conftest.py``):
  the same classes, the same wiring (EventBus singleton, AlertManager,
  OperationsEngine ``create()`` factory, DispatchService with injected
  dependencies), plus the extended service layer each probe references
  (permission, analytics, route, document, OCR, CMR, receipt, fleet,
  maintenance, freight-exchange search, client, user, preferences,
  copilot, tacho).

* :func:`build_parity_world` — seeds a two-company world in the ana_dispatcher
  style: company A (dispatcher + driver + one trip) and company B (isolated —
  no trips, no drivers).  The returned ``world`` dict also carries the
  harness ``services`` dict and a wired ``MobileClient`` fixture instance so
  probes can run against real objects.

* :func:`assert_matrix_covered` — matrix-driven coverage helper: for every row
  of the §4 matrix, verifies that the platform coverage column is backed by a
  truthful probe (``True``/``"view"`` → probe exists and passes; ``False`` →
  no probe may assert ``True``).  Returns the list of uncovered features
  (empty list == fully covered).
"""

from __future__ import annotations

from typing import Any, Callable

from repositories.driver_repository import DriverRepository
from repositories.fleet_repository import FleetRepository
from services.analytics_service import AnalyticsService
from services.client_service import ClientService
from services.conflict_service import TripConflictService
from services.dispatch_service.dispatch_service import DispatchService
from services.document_automation.ocr_extractor import OcrExtractor
from services.document_service import DocumentService
from services.fleet_service import FleetService
from services.freight_exchange.search import SearchEngineService
from services.invoicing.cmr_generator import CMRGenerator
from services.invoicing.receipt_generator import ReceiptGenerator
from services.invoicing.service import InvoiceService
from services.operations.alert_manager import AlertManager
from services.operations.event_bus import EventBus
from services.operations.maintenance_engine import MaintenanceEngine
from services.operations.operations_engine import OperationsEngine
from services.permission_service import PermissionService
from services.preferences import PreferencesManager
from services.route_service import RouteService
from services.tacho_service import TachoService
from services.trip_service import TripService
from services.user_service import UserService
from tests.workflow_integrity.fixtures.multi_platform_client import MobileClient
from tests.workflow_integrity.personas.fixtures import (
    seed_client,
    seed_company,
    seed_driver,
    seed_trip,
    seed_user,
)

__all__ = [
    "build_harness_services",
    "build_parity_world",
    "assert_matrix_covered",
]


class _CopilotPlanner:
    """Adapter surfacing the real ARGO/CoPilot planner entry points.

    The desktop "ARGO Chat/Actions" surface is backed by the module-level
    async functions ``process_utterance`` / ``compile_execution_plan`` in
    ``backend/copilot/planner.py`` (invoked by ``backend/api/v1/
    copilot_router.py``).  This adapter exposes them as methods so the
    canonical services-dict key ``copilot_planner`` is truthful: the probe
    verifies reachability of the *real* planner API, not a mock.  Imports are
    deferred so world construction stays cheap and side-effect free.
    """

    async def process_utterance(self, *args: Any, **kwargs: Any):
        from backend.copilot.planner import process_utterance

        return await process_utterance(*args, **kwargs)

    async def compile_execution_plan(self, *args: Any, **kwargs: Any):
        from backend.copilot.planner import compile_execution_plan

        return await compile_execution_plan(*args, **kwargs)


def build_harness_services(db) -> dict[str, Any]:
    """Assemble the REAL harness services dict under the canonical probe keys.

    Construction mirrors ``tests/workflow_integrity/conftest.py`` — the same
    classes and wiring (EventBus singleton reset + ``inject_db``, AlertManager
    reset, OperationsEngine ``create()`` factory, DispatchService with the
    conftest dependency order) — then adds the extended service layer the
    desktop probes reference.  Every entry is a real application service
    backed by the same in-memory ``db``; no mocks, no fakes.
    """
    event_bus = EventBus()
    event_bus.reset()
    event_bus.inject_db(db)

    alert_manager = AlertManager(db)
    alert_manager.reset()

    trip_service = TripService(db)
    invoice_service = InvoiceService(db)
    fleet_repo = FleetRepository(db)
    driver_repo = DriverRepository(db)
    conflict_service = TripConflictService(db)

    dispatch_service = DispatchService(
        trip_service=trip_service,
        fleet_repo=fleet_repo,
        driver_repo=driver_repo,
        conflict_service=conflict_service,
        event_bus=event_bus,
        alert_manager=alert_manager,
    )

    operations_engine = OperationsEngine.create(
        db=db,
        event_bus=event_bus,
        alert_mgr=alert_manager,
        trip_service=trip_service,
    )

    return {
        # ── workflow-integrity conftest fixtures ─────────────────────
        "db": db,
        "trip_service": trip_service,
        "invoice_service": invoice_service,
        "fleet_repo": fleet_repo,
        "driver_repo": driver_repo,
        "conflict_service": conflict_service,
        "dispatch_service": dispatch_service,
        "event_bus": event_bus,
        "alert_manager": alert_manager,
        "operations_engine": operations_engine,
        # ── extended service layer (desktop probe keys) ──────────────
        "permission_service": PermissionService(db),
        "analytics_service": AnalyticsService(db),
        "route_service": RouteService(db),
        "document_service": DocumentService(db),
        "ocr_extractor": OcrExtractor(db=db),
        "cmr_generator": CMRGenerator(db=db),
        "receipt_generator": ReceiptGenerator(db=db),
        "fleet_service": FleetService(db),
        "maintenance_engine": MaintenanceEngine(db),
        "search_engine_service": SearchEngineService(db),
        "client_service": ClientService(db),
        "user_service": UserService(db),
        "preferences_manager": PreferencesManager(db),
        "copilot_planner": _CopilotPlanner(),
        "tacho_service": TachoService(db),
    }


def build_parity_world(db) -> dict[str, Any]:
    """Seed a two-company parity world and return it with the harness attached.

    World shape (ana_dispatcher-style, two-company isolation pattern):

    * ``company_a`` — company A with a dispatcher user, a driver and one
      ``Planned`` trip (company-scoped to A);
    * ``company_b`` — company B, isolated: no trips, no drivers;
    * ``services`` — the real harness services dict (see
      :func:`build_harness_services`);
    * ``mobile_client`` — a ``MobileClient`` fixture instance wired to the same
      ``trip_service`` / ``db``.

    The returned dict is the ``world`` argument of :func:`assert_matrix_covered`
    and the source of the conftest-equivalent services the matrix tests probe.
    """
    services = build_harness_services(db)

    company_a = seed_company(
        db, company_name="Parity Alpha SRL", subscription_tier="professional"
    )
    dispatcher_id = seed_user(
        db,
        company_id=company_a,
        email="dispatch@parity-alpha.ro",
        role="dispatcher",
        display_name="Parity Dispatcher",
    )
    driver_id = seed_driver(
        db, company_id=company_a, name="Parity Driver", license_number="RO-PAR-A01"
    )
    client_id = seed_client(db, name="Parity Client A")
    trip_id = seed_trip(
        db,
        company_id=company_a,
        client_id=client_id,
        client_name="Parity Client A",
        driver_id=driver_id,
        driver_name="Parity Driver",
        truck_number="B-PARITY-01",
        status="Planned",
    )

    company_b = seed_company(
        db, company_name="Parity Beta SRL", subscription_tier="starter"
    )

    mobile_client = MobileClient(services["trip_service"], db)

    return {
        "company_a": {
            "company_id": company_a,
            "dispatcher_id": dispatcher_id,
            "driver_id": driver_id,
            "client_id": client_id,
            "trip_id": trip_id,
        },
        "company_b": {"company_id": company_b},
        "services": services,
        "mobile_client": mobile_client,
    }


def assert_matrix_covered(matrix, world: dict[str, Any], probes: dict[str, Callable],
                          *, column: str = "desktop") -> list[str]:
    """Matrix-driven coverage check for one platform column of the §4 matrix.

    For every row of ``matrix`` the coverage in ``column`` is verified against
    the probe inventory ``probes`` and the harness inside ``world``:

    * coverage ``True``   — the feature must have a probe and the probe must
      return ``True`` against the harness target (``world["services"]`` for
      desktop columns, ``world["mobile_client"]`` for mobile columns);
    * coverage ``"view"`` — the feature must have a probe and the probe must
      pass; probe inventories for view coverage verify *read-only accessors*
      (e.g. ``get_trip``), never mutation paths;
    * coverage ``False``  — no probe may assert ``True`` for the feature: it is
      either absent from ``probes`` or its probe returns ``False``.

    Returns the list of features whose coverage is NOT satisfied (empty list
    == every row of that column is backed by a truthful probe).
    """
    services = world.get("services")
    mobile_client = world.get("mobile_client")
    target = mobile_client if column.startswith("mobile") else services

    uncovered: list[str] = []
    for row in matrix:
        coverage = getattr(row, column)
        probe = probes.get(row.feature)
        if coverage is True or coverage == "view":
            if probe is None:
                uncovered.append(
                    f"{row.feature}: {column}={coverage!r} but no probe defined"
                )
            elif not probe(target):
                uncovered.append(
                    f"{row.feature}: probe({column}) returned False against "
                    f"the harness"
                )
        elif coverage is False:
            if probe is not None and probe(target) is True:
                uncovered.append(
                    f"{row.feature}: {column}=False but probe asserts True"
                )
    return uncovered