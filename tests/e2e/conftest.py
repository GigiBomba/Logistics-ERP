"""Shared fixtures for E2E test modules.

Makes ``client_with_mocks`` etc. available by importing from
``tests.test_api.conftest``.
"""
from __future__ import annotations

import pytest
from tests.test_helpers import make_db

pytest_plugins = ("tests.test_api.conftest",)


@pytest.fixture
def db():
    """In-memory SQLite database with full application schema."""
    return make_db()
