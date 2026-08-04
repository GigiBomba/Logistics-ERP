"""Shared fixtures for load/stress tests."""
from __future__ import annotations

import concurrent.futures
import time
import pytest
from unittest.mock import MagicMock, patch

from tests.test_helpers import make_db, InMemoryDB

# ``client``/``app``/mock fixtures from tests.test_api.conftest are already
# re-exported by the ROOT conftest (tests/conftest.py).  Declaring
# ``pytest_plugins`` in a non-top-level conftest is an error on pytest 8+
# and breaks collecting the whole ``tests/`` tree in one invocation.


@pytest.fixture
def inmemory_db():
    """Fresh InMemoryDB with full schema."""
    return make_db()


def run_concurrent(func, n_threads, *args):
    """Run func n_threads times concurrently, return (results, timings, errors, elapsed)."""
    timings = []
    errors = []
    results = []
    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as executor:
        futures = {executor.submit(func, *args): i for i in range(n_threads)}
        for future in concurrent.futures.as_completed(futures):
            try:
                t0 = time.monotonic()
                result = future.result()
                timings.append(time.monotonic() - t0)
                results.append(result)
            except Exception as e:
                errors.append(e)
    elapsed = time.monotonic() - start
    return results, timings, errors, elapsed


@pytest.fixture
def mock_redis_success():
    """Mock RedisCache to simulate Redis being available."""
    with patch("backend.cache.get_cache") as mock_get_cache:
        mock_cache = MagicMock()
        mock_cache._enabled = True
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        mock_cache.rpush.return_value = True
        mock_cache.delete.return_value = True
        mock_cache.flush_pattern.return_value = 0
        mock_get_cache.return_value = mock_cache
        yield mock_cache


@pytest.fixture
def mock_redis_unavailable():
    """Mock RedisCache to simulate Redis being unavailable."""
    with patch("backend.cache.get_cache") as mock_get_cache:
        mock_cache = MagicMock()
        mock_cache._enabled = False
        mock_cache.get.return_value = None
        mock_cache.set.return_value = False
        mock_cache.rpush.return_value = False
        mock_cache.delete.return_value = False
        mock_cache.flush_pattern.return_value = 0
        mock_get_cache.return_value = mock_cache
        yield mock_cache
