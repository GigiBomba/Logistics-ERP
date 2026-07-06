"""pytest root configuration for the PySide6 test suite.

This file registers the fixtures defined in ``test_conftest`` so that every
Qt test can use them without explicit imports.

Singleton reset: the ``reset_singletons`` fixture is automatically applied to
every test (via ``pytestmark`` or auto-use) to clear the cross-test state
that the singleton pattern introduces.
"""

import pytest

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

    yield
