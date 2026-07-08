"""pytest root configuration for the PySide6 test suite.

This file registers the fixtures defined in ``test_conftest`` so that every
Qt test can use them without explicit imports.

Singleton reset: the ``reset_singletons`` fixture is automatically applied to
every test (via ``pytestmark`` or auto-use) to clear the cross-test state
that the singleton pattern introduces.
"""

import pytest
from unittest.mock import MagicMock

pytest_plugins = ["test_conftest"]


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test.

    This prevents test pollution from state stored in module-level
    singletons (EventBus, AlertManager, ExchangeRateService, etc.)
    that would otherwise persist across test cases.
    """
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
