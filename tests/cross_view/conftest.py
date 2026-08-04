"""Shared fixtures for cross-view integration tests (Phase 13)."""

from __future__ import annotations
from unittest.mock import MagicMock
import pytest


@pytest.fixture
def mock_db():
    """Generic MagicMock for database session."""
    return MagicMock()


@pytest.fixture
def mock_prefs():
    """Mock PreferencesManager."""
    prefs = MagicMock()
    prefs.get_currency.return_value = "EUR"
    return prefs


@pytest.fixture
def mock_ops():
    """Mock OperationsEngine."""
    ops = MagicMock()
    ops.event_bus = MagicMock()
    ops.get_active_alerts.return_value = []
    ops.get_active_alert_count.return_value = 0
    return ops
