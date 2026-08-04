"""Shared fixtures for E2E test modules.

``client_with_mocks`` etc. are already re-exported by the ROOT conftest
(``tests/conftest.py``) from ``tests.test_api.conftest``, so no
``pytest_plugins`` declaration is needed here (declaring ``pytest_plugins``
in a non-top-level conftest is an error on pytest 8+ and breaks collecting
the whole ``tests/`` tree in one invocation).
"""
from __future__ import annotations

import pytest
from tests.test_helpers import make_db


@pytest.fixture
def db():
    """In-memory SQLite database with full application schema."""
    return make_db()
