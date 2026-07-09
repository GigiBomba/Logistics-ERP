"""Shared fixtures for concurrency tests."""
from __future__ import annotations

import pytest
from tests.test_helpers import make_db, InMemoryDB


@pytest.fixture
def db():
    return make_db()


@pytest.fixture(autouse=True)
def _reset_singletons():
    from services.operations.event_bus import EventBus
    from services.operations.alert_manager import AlertManager
    from services.operations.rules import Rules
    EventBus._instance = None
    AlertManager._instance = None
    Rules._instance = None
    yield
    EventBus._instance = None
    AlertManager._instance = None
    Rules._instance = None
