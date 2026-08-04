"""Shared fixtures for the freight-exchange test suite.

Several freight-exchange test modules clear the module-level provider
registry (``services.freight_exchange.registry._registry``) as part of
their isolation discipline.  When such a module runs in the same worker
*before* a test that asserts the real TIMOCOM / Trans.eu adapters are
registered (e.g. ``test_provider_agnostic_swap`` or ``test_import_parity``),
the registry is left empty and those tests fail spuriously.

The autouse fixture below re-registers the real adapters before and after
every test so the registry can never be observed empty, without interfering
with tests that deliberately clear/replace it mid-test (their assertions
run before this fixture's teardown).
"""
from __future__ import annotations

import pytest

from services.freight_exchange import registry


def _ensure_real_adapters() -> None:
    """Re-register the real freight adapters if they are missing."""
    try:
        from services.freight_exchange.adapters.trans_eu import TransEuAdapter
        from services.freight_exchange.adapters.timocom import TimocomAdapter
    except ImportError:  # adapters module layout changed — nothing to restore
        return
    if "timocom" not in registry._registry:
        registry._registry["timocom"] = TimocomAdapter()
    if "trans_eu" not in registry._registry:
        registry._registry["trans_eu"] = TransEuAdapter()


@pytest.fixture(autouse=True)
def _restore_real_freight_adapters():
    """Guarantee the real freight adapters stay registered across tests."""
    _ensure_real_adapters()
    yield
    _ensure_real_adapters()
