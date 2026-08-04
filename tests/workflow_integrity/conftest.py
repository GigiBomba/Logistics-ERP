"""Suite-wide fixtures for the Workflow Integrity Test Suite.

Strategy:
    The root ``tests/conftest.py`` already provides an autouse
    ``reset_singletons`` fixture that nulls every singleton before
    each test (EventBus, AlertManager, OperationsEngine, Rules,
    etc.).  This conftest piggy-backs on that — when the fixture
    chain runs, the singleton slates are already wiped.

    Every fixture here creates fresh service instances wired to
    a new in-memory SQLite database, so tests never share state.
"""

from __future__ import annotations

# Expose the autouse singleton-reset from the root conftest so
# that pytest's fixture hierarchy explicitly discovers it for
# this subtree.  (Autouse alone is sufficient, but this prevents
# any edge-case ordering surprises with pytest-xdist users.)
from tests.conftest import reset_singletons  # noqa: F401

import pytest

from repositories.driver_repository import DriverRepository
from repositories.fleet_repository import FleetRepository
from services.conflict_service import TripConflictService
from services.dispatch_service.dispatch_service import DispatchService
from services.invoicing.service import InvoiceService
from services.operations.alert_manager import AlertManager
from services.operations.event_bus import EventBus
from services.operations.operations_engine import OperationsEngine
from services.trip_service import TripService
from tests.test_data.factories import (  # noqa: F401 — re-exported for test convenience
    make_client,
    make_driver,
    make_invoice,
    make_trip,
    make_user,
    make_vehicle,
)
from tests.test_helpers import make_db
from tests.workflow_integrity.fixtures.workflow_environment import WorkflowEnvironment


# ── Pytest marker registration ──────────────────────────────────
def pytest_configure(config):
    """Register workflow-integrity markers so --strict-markers passes."""
    markers = [
        "workflow_integrity: Workflow integrity test",
        "golden_flow: Golden-path workflow test",
        "friction: Friction rule violation test",
        "financial_invariant: Financial invariant assertion test",
        "state_machine: State machine transition test",
        "parity: Cross-platform parity test",
        "argo: ARGO autonomy workflow test",
        "chaos_workflow: Chaos / resilience workflow test",
        "telemetry: Telemetry assertion test",
        "historical: Historical data immutability test",
    ]
    for m in markers:
        config.addinivalue_line("markers", m)


# ── Core fixtures ───────────────────────────────────────────────

@pytest.fixture
def db():
    """In-memory SQLite database with full application schema + indexes."""
    return make_db()


@pytest.fixture
def event_bus(db):
    """EventBus singleton, reset and injected with the test DB.

    ``reset_singletons`` nulled ``EventBus._instance`` before this
    fixture runs, so ``EventBus()`` creates a fresh singleton.
    """
    bus = EventBus()
    bus.reset()  # clear subscribers + history
    bus.inject_db(db)
    return bus


@pytest.fixture
def alert_manager(db, event_bus):
    """AlertManager singleton wired with the test DB.

    Internally obtains the EventBus singleton (already set up by
    the ``event_bus`` fixture) so event publishing is coherent.
    """
    mgr = AlertManager(db)
    mgr.reset()
    return mgr


@pytest.fixture
def trip_service(db):
    """TripService wired with the test database."""
    return TripService(db)


@pytest.fixture
def invoice_service(db):
    """InvoiceService wired with the test database."""
    return InvoiceService(db)


@pytest.fixture
def fleet_repo(db):
    """FleetRepository wired with the test database."""
    return FleetRepository(db)


@pytest.fixture
def driver_repo(db):
    """DriverRepository wired with the test database."""
    return DriverRepository(db)


@pytest.fixture
def conflict_service(db):
    """TripConflictService wired with the test database."""
    return TripConflictService(db)


@pytest.fixture
def dispatch_service(
    trip_service,
    fleet_repo,
    driver_repo,
    conflict_service,
    event_bus,
    alert_manager,
):
    """DispatchService with all required dependencies injected."""
    return DispatchService(
        trip_service=trip_service,
        fleet_repo=fleet_repo,
        driver_repo=driver_repo,
        conflict_service=conflict_service,
        event_bus=event_bus,
        alert_manager=alert_manager,
    )


@pytest.fixture
def operations_engine(db, event_bus, alert_manager, trip_service):
    """OperationsEngine wired with explicit dependencies.

    Uses the ``create()`` factory to bypass singleton locking so
    each test gets a deterministic, isolated engine instance.
    """
    return OperationsEngine.create(
        db=db,
        event_bus=event_bus,
        alert_mgr=alert_manager,
        trip_service=trip_service,
    )


@pytest.fixture
def workflow_env(db, trip_service, invoice_service, event_bus, alert_manager, operations_engine):
    """WorkflowEnvironment wrapping all test services."""
    return WorkflowEnvironment(
        db=db,
        trip_service=trip_service,
        invoice_service=invoice_service,
        event_bus=event_bus,
        alert_manager=alert_manager,
        operations_engine=operations_engine,
    )


@pytest.fixture
def event_monitor(event_bus):
    """EventMonitor wired to the test EventBus singleton."""
    from tests.workflow_integrity.fixtures.event_monitor import EventMonitor
    return EventMonitor(event_bus)


@pytest.fixture(autouse=True)
def _seed_system_user(db):
    """Ensure system user (id=0) exists for permission checks.

    Many services (InvoiceService, DocumentService, etc.) call
    ``PermissionService.is_authenticated(user_id=0)`` internally
    when tests don't pass an explicit user_id.  Without this row,
    the permission check fails with "User not found".
    """
    db.conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, role, is_active, display_name, created_at) "
        "VALUES (0, 'system@local', 'hash', 'admin', 1, 'System', datetime('now'))"
    )
    db.conn.commit()
    yield
    # No cleanup needed — the in-memory DB is discarded after each test.
