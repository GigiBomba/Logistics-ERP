"""Shared fixtures for concurrency tests."""
from __future__ import annotations

import os
import tempfile
import pytest
from database.db_manager import DatabaseManager


@pytest.fixture
def db():
    """File-based SQLite so each thread gets its own connection to the same DB.
    
    In-memory databases (``:memory:``) create a separate database per thread,
    causing "no such table" errors in concurrent test scenarios.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    dbu = DatabaseManager(db_path)
    yield dbu
    dbu.close()
    try:
        os.unlink(db_path)
        os.unlink(db_path + "-wal")
    except Exception:
        pass
    try:
        os.unlink(db_path + "-shm")
    except Exception:
        pass


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
