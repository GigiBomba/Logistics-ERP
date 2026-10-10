"""pytest root configuration for the PySide6 test suite.

This file registers the fixtures defined in ``test_conftest`` so that every
Qt test can use them without explicit imports.

Singleton reset: the ``reset_singletons`` fixture is automatically applied to
every test (via ``pytestmark`` or auto-use) to clear the cross-test state
that the singleton pattern introduces.
"""
from __future__ import annotations


import os
# Set test environment BEFORE any backend imports can happen.
# The .env file has OPERION_ENV=production which causes RuntimeErrors
# in BackendSettings._check_admin_config and AuthMiddleware.__init__.
os.environ.setdefault("OPERION_ENV", "testing")
os.environ.setdefault("OPERION_JWT_SECRET_KEY", "test-jwt-secret-key-for-testing!!")

# Per-worker isolated test database: each pytest-xdist worker gets its own
# temp SQLite file so suites that rely on the default DB path never inherit
# a stale OPERION_DB_PATH left by another suite that ran earlier on the same
# worker.  Suites that explicitly isolate themselves (mobile, waitlist,
# security) override this at their own module import.
import tempfile as _tempfile
import uuid as _uuid
_WORKER_DB_PATH = os.path.join(
    _tempfile.gettempdir(), f"operion_test_worker_{_uuid.uuid4().hex[:8]}.db",
)
os.environ.setdefault("OPERION_DB_PATH", _WORKER_DB_PATH)
os.environ.setdefault("OPERION_DB_ENGINE", "sqlite")

# --- Chrome containment guard (see fixture/hook at end of file) ---------------
# The suite must never launch or interact with the user's installed Chrome.
# Real-browser tests (chart-export _SilentChromium / window suppressor /
# choreographer launches) are disabled unless explicitly opted in via
# OPERION_ALLOW_REAL_CHROME=1 (dedicated CI machines only).  BROWSER_PATH is
# pointed at a non-existent binary so any accidental real launch fails fast
# instead of starting system Chrome.
_BLOCKED_CHROME_PATH = os.path.join(
    _tempfile.gettempdir(), "operion-test-browser-blocked", "chrome.exe",
)
if os.environ.get("OPERION_ALLOW_REAL_CHROME") != "1":
    os.environ["BROWSER_PATH"] = _BLOCKED_CHROME_PATH
try:
    from config import Config as _Config
    _Config.DB_PATH = _WORKER_DB_PATH
except Exception:
    pass

# Business invariant environment — satisfy AUTH invariants
os.environ.setdefault("JWT_SECRET", "a" * 64)
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("BF_ENABLED", "true")
os.environ.setdefault("BF_MAX_ATTEMPTS", "5")
os.environ.setdefault("BF_WINDOW_MINUTES", "5")
os.environ.setdefault("BF_LOCKOUT_MINUTES", "15")

import logging
import sys

import pytest
from unittest.mock import MagicMock

pytest_plugins = ["tests.test_conftest"]

# ── Shared API fixtures ──────────────────────────────────────────────────
# pytest fails to register fixtures from a subdirectory conftest when test
# files at different directory depths are interleaved on the command line
# (e.g. ``pytest tests/test_api/a.py tests/x.py tests/test_api/b.py`` — the
# second ``tests/test_api`` batch can't see ``client_with_mocks`` etc.).
# Re-exporting the fixtures from the ROOT conftest registers them
# unconditionally, so the affected suites resolve them regardless of
# collection order (same pattern as ``tests/stress/conftest.py``).
from tests.test_api.conftest import (  # noqa: F401
    StrippedMock,
    app,
    client,
    client_with_mocks,
    mock_analytics_service,
    mock_client_service,
    mock_db,
    mock_document_service,
    mock_driver_repo,
    mock_fleet_service,
    mock_trip_service,
)


# ── pytest-xdist `--dist=loadscope` crash-deadlock workaround ─────────────
# Vendored copy of the fix merged upstream in pytest-xdist PR #1324 (issues
# #1323 / #1378), unreleased as of pytest-xdist 3.8.0. After a worker crash,
# ``LoadScopeScheduling.remove_node`` re-queued the crashed worker's workload
# *including completed scopes*; assigning such an empty work unit sends
# ``send_runtest_some([])``, the replacement worker blocks forever in
# ``torun.get()`` and the controller blocks in ``dsession.loop_once`` — the
# run hangs at 98-99% and never prints a summary (observed on Windows with Qt
# native worker crashes). The fix filters the re-queue to scopes that still
# have pending items and guards ``_assign_work_unit`` against empty
# assignments. Feature-detected: applies only while the buggy
# ``self.workqueue.update(workload)`` line is present, so a future upstream
# release supersedes it automatically. Disable with OPERION_XDIST_WEDGE_FIX=0.
def _apply_xdist_loadscope_wedge_fix() -> None:  # pragma: no cover - infra shim
    import inspect
    import os as _os

    if _os.environ.get("OPERION_XDIST_WEDGE_FIX", "1") == "0":
        return
    try:
        from xdist.scheduler.loadscope import LoadScopeScheduling
    except Exception:
        return
    try:
        buggy_source = inspect.getsource(LoadScopeScheduling.remove_node)
    except (OSError, TypeError):
        return
    if "self.workqueue.update(workload)" not in buggy_source:
        return  # already fixed upstream

    def remove_node(self, node):
        """xdist 3.8.0 ``remove_node`` + PR #1324 pending-only re-queue."""
        workload = self.assigned_work.pop(node)
        if not self._pending_of(workload):
            return None

        # The node crashed, identify test that crashed
        for work_unit in workload.values():
            for nodeid, completed in work_unit.items():
                if not completed:
                    crashitem = nodeid
                    break
            else:
                continue
            break
        else:
            raise RuntimeError(
                "Unable to identify crashitem on a workload with pending items"
            )

        # Make uncompleted work units available again
        for scope, work_unit in workload.items():
            if any(not completed for completed in work_unit.values()):
                self.workqueue[scope] = work_unit

        for other in self.assigned_work:
            self._reschedule(other)

        return crashitem

    def _assign_work_unit(self, node):
        """xdist 3.8.0 ``_assign_work_unit`` + PR #1324 empty-unit guard."""
        assert self.workqueue

        # Grab a unit of work
        scope, work_unit = self.workqueue.popitem(last=False)

        # Keep track of the assigned work
        assigned_to_node = self.assigned_work.setdefault(node, {})
        assigned_to_node[scope] = work_unit

        # Ask the node to execute the workload
        worker_collection = self.registered_collections[node]
        nodeids_indexes = [
            worker_collection.index(nodeid)
            for nodeid, completed in work_unit.items()
            if not completed
        ]
        if not nodeids_indexes:
            # Internal error that would otherwise hang the worker (#1323/#1378)
            raise RuntimeError(
                "Trying to assign a work unit with no pending items to a node"
            )

        node.send_runtest_some(nodeids_indexes)

    LoadScopeScheduling.remove_node = remove_node
    LoadScopeScheduling._assign_work_unit = _assign_work_unit


_apply_xdist_loadscope_wedge_fix()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test.

    This prevents test pollution from state stored in module-level
    singletons (EventBus, AlertManager, ExchangeRateService, etc.)
    that would otherwise persist across test cases.
    """
    # Clear all logger handlers to prevent MagicMock handlers
    # installed by `mock_file_handler` in test_logger.py from
    # polluting subsequent tests in the same process.
    logging.root.handlers.clear()
    logging.root.propagate = True
    logging.root.setLevel(logging.NOTSET)
    # Undo any module-level `logging.disable(...)` (e.g. some e2e suites
    # call logging.disable(logging.CRITICAL) at import time) so later
    # tests that assert on log emission are not silently suppressed.
    logging.disable(logging.NOTSET)
    for name in list(logging.root.manager.loggerDict.keys()):
        log = logging.getLogger(name)
        log.handlers.clear()
        log.propagate = True
        log.setLevel(logging.NOTSET)

    # Tenant context (contextvars) — a test that set a company/role scope and
    # didn't reset it would leak scoped SQL (`AND company_id = ?`) into later
    # tests in the same process and break unscoped repository fixtures.
    # Gate on import: if the module was never imported, the context is already
    # the default empty one, so clearing it would be a no-op anyway.
    if "database.tenant_context" in sys.modules:
        from database.tenant_context import clear_context
        clear_context()

    # EventBus
    # ``services.operations`` has a heavy __init__ (imports all engine
    # modules), so find_spec on a leaf would trigger it — use sys.modules.
    if "services.operations.event_bus" in sys.modules:
        from services.operations.event_bus import EventBus
        EventBus._instance = None

    # AlertManager
    if "services.operations.alert_manager" in sys.modules:
        from services.operations.alert_manager import AlertManager
        AlertManager._instance = None

    # ExchangeRateService
    if "services.exchange_rate_service" in sys.modules:
        from services.exchange_rate_service import ExchangeRateService
        ExchangeRateService._instance = None

    # FuelPriceService
    if "services.fuel_price_service" in sys.modules:
        from services.fuel_price_service import FuelPriceService
        FuelPriceService._instance = None

    # OperationsEngine
    if "services.operations.operations_engine" in sys.modules:
        from services.operations.operations_engine import OperationsEngine
        OperationsEngine._instance = None

    # TripContextService
    if "services.trip_context" in sys.modules:
        from services.trip_context import TripContextService
        TripContextService._instance = None

    # Rules singleton
    if "services.operations.rules" in sys.modules:
        from services.operations.rules import Rules
        Rules._instance = None

    # FleetTrackingService
    if "services.fleet_tracking_service" in sys.modules:
        from services.fleet_tracking_service import FleetTrackingService
        FleetTrackingService._instance = None

    # AppState
    if "services.app_state" in sys.modules:
        from services.app_state import AppState
        AppState._instance = None

    # RouteStateManager (dict of instances)
    if "services.route_state" in sys.modules:
        from services.route_state import RouteStateManager
        RouteStateManager._instances = {}

    # i18n module-level globals
    if "services.i18n" in sys.modules:
        import services.i18n as _i18n
        _i18n._translations = {}
        _i18n._current_lang = "en"
        # Reload translations from disk (same entry point main.py uses via
        # init_language) so t() resolves real strings instead of falling back
        # to raw keys for the rest of the test.
        _i18n.load_translations()

    # Auth manager
    if "client.auth_manager" in sys.modules:
        import client.auth_manager as _auth_mgr
        _auth_mgr._auth_instance = None

    # Backend cache
    if "backend.cache" in sys.modules:
        import backend.cache as _backend_cache
        _backend_cache._cache_instance = None

    # CircuitBreaker — class-level shared state across instances
    if "backend.copilot.circuit_breaker" in sys.modules:
        from backend.copilot.circuit_breaker import CircuitBreaker
        CircuitBreaker._states.clear()

    # BackendSettings process-global cache (F1).  ``get_settings()`` caches
    # the first BackendSettings parse; tests that mutate OPERION_* env vars
    # (module-scoped ``_set_env`` fixtures, monkeypatch.setenv) must not see
    # a stale cached copy.  Reset the cache before every test so the first
    # ``get_settings()`` call of each test re-reads the current environment.
    # Gate on import: if ``backend.config`` was never imported, there is no
    # cached copy to invalidate and the first get_settings() reads fresh env.
    if "backend.config" in sys.modules:
        from backend.config import reload_settings
        reload_settings()

    # ── Chart-export engine (Choreographer/Chrome) ────────────────
    # Replace with a mock so that async QThreadPool render workers
    # from any test never try to boot real Chrome during test runs.
    import utils.chart_export as _ce
    _mock_ce = MagicMock(spec=_ce._RenderEngine)
    _mock_ce.submit.return_value = b"<svg>mock</svg>"
    with _ce._ENGINE_LOCK:
        _saved_ce = _ce._ENGINE
        _ce._ENGINE = _mock_ce

    # QtTheme cached stylesheet.  Gate on import: if ``ui.theme_engine`` was
    # never imported, there is no cached stylesheet to reset (first import
    # builds a fresh one).
    if "ui.theme_engine" in sys.modules:
        from ui.theme_engine import QtTheme
        QtTheme._style_sheet = None

    yield

    # ── Teardown ─────────────────────────────────────────────────
    # Drain any in-flight QThreadPool renders (from PlotlyChartWidget
    # instances created during the test) so their workers don't
    # outlive the fixture and create a real Chrome engine after we
    # restore _ENGINE.
    try:
        from ui.plotly_renderer import get_render_manager
        get_render_manager().wait_for_done(msec=5000)
    except Exception:
        pass

    # Restore the chart_export engine singleton so subsequent tests
    # start clean.
    with _ce._ENGINE_LOCK:
        _ce._ENGINE = _saved_ce


@pytest.fixture(scope="session", autouse=True)
def _session_chart_engine_mock():
    """Session-long guard: ``utils.chart_export._ENGINE`` never reverts to
    ``None`` (or a real engine) while the worker lives.

    ``reset_singletons`` swaps a mock in per test and restores whatever was
    there before.  Before this guard, that "before" was ``None`` after the
    first test — so any QThreadPool render worker that outlived its test
    (teardown drains only wait 5 s) and called ``_get_engine()`` in the gap
    would create a REAL ``_RenderEngine`` and start headless Chrome.

    That is exactly what full-run evidence shows (full_diag.err:
    "Choreographer browser failed to start … retrying in 16s" storms +
    mass E-at-setup blocks): Chrome cannot reliably launch here (both
    xdist workers share the same persistent ``operion_chrome_profile``
    user-data dir, so the second instance exits immediately), and every
    real launch attempt costs 30–100 s of blocking waits.

    With this guard, ``_ENGINE`` is a mock from the first test until the
    worker's session ends — no test or leftover render can ever boot real
    Chrome.  If a test still swaps in a real ``_RenderEngine`` (e.g. the
    chart-export unit tests), it is shut down at session teardown.
    """
    import utils.chart_export as _ce

    with _ce._ENGINE_LOCK:
        original = _ce._ENGINE
        mock = MagicMock(spec=_ce._RenderEngine)
        mock.submit.return_value = b"<svg>mock</svg>"
        _ce._ENGINE = mock
    yield
    with _ce._ENGINE_LOCK:
        final = _ce._ENGINE
        _ce._ENGINE = original
    # A test replaced the session mock with a real engine → stop its
    # background thread (bounded: shutdown waits ≤ 15 s + join ≤ 5 s).
    if isinstance(final, _ce._RenderEngine):
        try:
            final.shutdown()
        except Exception:
            pass


# ── Shared test JWT secret ────────────────────────────────────────────
# All API tests use this secret so they agree on signed tokens.
# Tests that intentionally test wrong-secret rejection override via
# os.environ / monkeypatch.setenv locally.
import os
OPERION_TEST_JWT_SECRET = os.environ.get("OPERION_TEST_JWT_SECRET", "test-jwt-secret-change-me-in-production")


# --- Chrome containment (guard block near top of file) -----------------------
@pytest.fixture(autouse=True)
def _reassert_chrome_block():
    """Re-assert the blocked ``BROWSER_PATH`` before every test.

    A few tests legitimately clear ``BROWSER_PATH`` (exercising
    ``configure_choreographer_export(None)``); without this, later accidentals
    could auto-detect the system Chrome.  No-op when the explicit opt-in
    ``OPERION_ALLOW_REAL_CHROME=1`` is set.
    """
    if os.environ.get("OPERION_ALLOW_REAL_CHROME") != "1":
        os.environ.setdefault("BROWSER_PATH", _BLOCKED_CHROME_PATH)


def pytest_collection_modifyitems(config, items):
    """Skip tests that drive the real installed Chrome unless opted in.

    ``tests/test_silent_chromium.py`` exercises the real _SilentChromium
    window suppressor, which launches and manipulates chrome.exe.  It is
    disabled by default so the user's browser session is never touched; opt
    in with ``OPERION_ALLOW_REAL_CHROME=1`` on dedicated machines.
    """
    if os.environ.get("OPERION_ALLOW_REAL_CHROME") == "1":
        return
    skip_marker = pytest.mark.skip(
        reason="real-Chrome test disabled by default; set OPERION_ALLOW_REAL_CHROME=1 to enable",
    )
    for item in items:
        if item.nodeid.startswith("tests/test_silent_chromium.py"):
            item.add_marker(skip_marker)
