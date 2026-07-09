"""Shared fixtures for E2E tests."""
from __future__ import annotations

import pytest
from tests.test_helpers import make_db, InMemoryDB


@pytest.fixture
def db():
    """Fresh InMemoryDB with full schema for E2E tests."""
    return make_db()


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all singletons before each test."""
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
