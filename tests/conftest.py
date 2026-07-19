"""pytest root configuration for the PySide6 test suite.

This file registers the fixtures defined in ``test_conftest`` so that every
Qt test can use them without explicit imports.

Singleton reset: the ``reset_singletons`` fixture is automatically applied to
every test (via ``pytestmark`` or auto-use) to clear the cross-test state
that the singleton pattern introduces.
"""

import os
# Set test environment BEFORE any backend imports can happen.
# The .env file has OPERION_ENV=production which causes RuntimeErrors
# in BackendSettings._check_admin_config and AuthMiddleware.__init__.
os.environ.setdefault("OPERION_ENV", "testing")
os.environ.setdefault("OPERION_JWT_SECRET_KEY", "test-jwt-secret-key-for-testing")

import logging
import pytest
from unittest.mock import MagicMock

pytest_plugins = ["tests.test_conftest"]


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
    for name in list(logging.root.manager.loggerDict.keys()):
        log = logging.getLogger(name)
        log.handlers.clear()
        log.propagate = True
        log.setLevel(logging.NOTSET)

    # EventBus
    from services.operations.event_bus import EventBus
    EventBus._instance = None

    # AlertManager
    from services.operations.alert_manager import AlertManager
    AlertManager._instance = None

    # ExchangeRateService
    from services.exchange_rate_service import ExchangeRateService
    ExchangeRateService._instance = None

    # FuelPriceService
    from services.fuel_price_service import FuelPriceService
    FuelPriceService._instance = None

    # OperationsEngine
    from services.operations.operations_engine import OperationsEngine
    OperationsEngine._instance = None

    # TripContextService
    from services.trip_context import TripContextService
    TripContextService._instance = None

    # Rules singleton
    from services.operations.rules import Rules
    Rules._instance = None

    # FleetTrackingService
    from services.fleet_tracking_service import FleetTrackingService
    FleetTrackingService._instance = None

    # AppState
    from services.app_state import AppState
    AppState._instance = None

    # RouteStateManager (dict of instances)
    from services.route_state import RouteStateManager
    RouteStateManager._instances = {}

    # i18n module-level globals
    import services.i18n as _i18n
    _i18n._translations = {}
    _i18n._current_lang = "en"

    # Auth manager
    import client.auth_manager as _auth_mgr
    _auth_mgr._auth_instance = None

    # Backend cache
    import backend.cache as _backend_cache
    _backend_cache._cache_instance = None

    # ── Chart-export engine (Choreographer/Chrome) ────────────────
    # Replace with a mock so that async QThreadPool render workers
    # from any test never try to boot real Chrome during test runs.
    import utils.chart_export as _ce
    _mock_ce = MagicMock(spec=_ce._RenderEngine)
    _mock_ce.submit.return_value = b"<svg>mock</svg>"
    with _ce._ENGINE_LOCK:
        _saved_ce = _ce._ENGINE
        _ce._ENGINE = _mock_ce

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


# ── Shared test JWT secret ────────────────────────────────────────────
# All API tests use this secret so they agree on signed tokens.
# Tests that intentionally test wrong-secret rejection override via
# os.environ / monkeypatch.setenv locally.
import os
OPERION_TEST_JWT_SECRET = os.environ.get("OPERION_TEST_JWT_SECRET", "test-jwt-secret-change-me-in-production")
