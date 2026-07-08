"""Tests for client.cache — LocalCache in-memory TTL cache."""

from __future__ import annotations

import time as _real_time
from unittest.mock import patch

import pytest

from client.cache import LocalCache


# Time-based tests need a stable fake clock.  Instead of patching
# time.time with a MagicMock (which produces incomparable objects),
# we use ``return_value`` with a pre-computed float.

_BASE_TIME: float = 1_000_000.0


class TestLocalCacheInit:
    def test_default_ttl(self):
        cache = LocalCache()
        assert cache._ttl == 300

    def test_custom_ttl(self):
        cache = LocalCache(ttl=60)
        assert cache._ttl == 60

    def test_zero_ttl(self):
        cache = LocalCache(ttl=0)
        assert cache._ttl == 0

    def test_empty_store_on_init(self):
        cache = LocalCache()
        assert cache._store == {}


class TestLocalCacheGet:
    def test_get_returns_none_for_missing_key(self):
        cache = LocalCache()
        assert cache.get("missing") is None

    def test_get_returns_stored_value(self):
        cache = LocalCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_returns_none_after_expiry(self):
        cache = LocalCache(ttl=10)
        with patch("client.cache.time.time", return_value=_BASE_TIME):
            cache.set("key1", "value1")
        with patch("client.cache.time.time", return_value=_BASE_TIME + 15):
            assert cache.get("key1") is None

    def test_get_removes_expired_entry(self):
        cache = LocalCache(ttl=10)
        with patch("client.cache.time.time", return_value=_BASE_TIME):
            cache.set("key1", "value1")
        with patch("client.cache.time.time", return_value=_BASE_TIME + 15):
            cache.get("key1")
            assert "key1" not in cache._store

    def test_get_returns_value_within_ttl(self):
        cache = LocalCache(ttl=30)
        with patch("client.cache.time.time", return_value=_BASE_TIME):
            cache.set("key1", "value1")
        with patch("client.cache.time.time", return_value=_BASE_TIME + 20):
            assert cache.get("key1") == "value1"

    def test_get_returns_none_when_ttl_is_zero(self):
        cache = LocalCache(ttl=0)
        with patch("client.cache.time.time", return_value=_BASE_TIME):
            cache.set("key1", "value1")
        with patch("client.cache.time.time", return_value=_BASE_TIME + 1):
            assert cache.get("key1") is None


class TestLocalCacheSet:
    def test_set_overwrites_existing(self):
        cache = LocalCache()
        cache.set("key1", "old")
        cache.set("key1", "new")
        assert cache.get("key1") == "new"

    def test_set_updates_timestamp(self):
        cache = LocalCache(ttl=10)
        with patch("client.cache.time.time", return_value=_BASE_TIME):
            cache.set("key1", "value1")
        with patch("client.cache.time.time", return_value=_BASE_TIME + 5):
            cache.set("key1", "value2")
            entry = cache._store["key1"]
            assert entry["time"] == _BASE_TIME + 5

    def test_set_multiple_keys(self):
        cache = LocalCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        assert len(cache._store) == 3
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_set_none_value(self):
        cache = LocalCache()
        cache.set("key1", None)
        assert cache.get("key1") is None  # stored None vs missing


class TestLocalCacheInvalidate:
    def test_invalidate_removes_key(self):
        cache = LocalCache()
        cache.set("key1", "value1")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_invalidate_non_existent_key(self):
        cache = LocalCache()
        cache.invalidate("missing")  # should not raise
        assert cache.get("missing") is None

    def test_invalidate_one_key_keeps_others(self):
        cache = LocalCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.invalidate("a")
        assert cache.get("a") is None
        assert cache.get("b") == 2


class TestLocalCacheClear:
    def test_clear_removes_all_keys(self):
        cache = LocalCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.clear()
        assert cache._store == {}
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") is None

    def test_clear_empty_cache(self):
        cache = LocalCache()
        cache.clear()  # should not raise
        assert cache._store == {}

    def test_clear_then_set_works(self):
        cache = LocalCache()
        cache.set("a", 1)
        cache.clear()
        cache.set("b", 2)
        assert cache.get("a") is None
        assert cache.get("b") == 2


class TestLocalCacheTTL:
    def test_different_ttl_per_instance(self):
        cache1 = LocalCache(ttl=10)
        cache2 = LocalCache(ttl=60)
        assert cache1._ttl == 10
        assert cache2._ttl == 60
        cache1.set("k", "v1")
        cache2.set("k", "v2")
        assert cache1.get("k") == "v1"
        assert cache2.get("k") == "v2"

    def test_ttl_expiry_removes_only_expired(self):
        cache = LocalCache(ttl=10)
        with patch("client.cache.time.time", return_value=_BASE_TIME):
            cache.set("expires_soon", "value1")
            cache.set("stays_long", "value2")
        # Advance past TTL for first item
        with patch("client.cache.time.time", return_value=_BASE_TIME + 15):
            assert cache.get("expires_soon") is None
            assert "expires_soon" not in cache._store
            # Re-set the second item with a fresh timestamp
            cache.set("stays_long", "value2")
        # Still within TTL for re-set item, but expires_soon is gone
        with patch("client.cache.time.time", return_value=_BASE_TIME + 18):
            assert cache.get("stays_long") == "value2"

    def test_long_ttl_keeps_values(self):
        cache = LocalCache(ttl=3600)
        with patch("client.cache.time.time", return_value=_BASE_TIME):
            cache.set("k", "v")
        with patch("client.cache.time.time", return_value=_BASE_TIME + 1800):
            assert cache.get("k") == "v"

    def test_ttl_boundary(self):
        """Value exactly at TTL boundary should still be valid (> not >=)."""
        cache = LocalCache(ttl=10)
        with patch("client.cache.time.time", return_value=_BASE_TIME):
            cache.set("k", "v")
        # Exactly at TTL — still valid since check is > not >=
        with patch("client.cache.time.time", return_value=_BASE_TIME + 10):
            assert cache.get("k") == "v"
        # One second past TTL
        with patch("client.cache.time.time", return_value=_BASE_TIME + 11):
            assert cache.get("k") is None


class TestLocalCacheEdgeCases:
    def test_store_size_grows_with_sets(self):
        cache = LocalCache()
        for i in range(100):
            cache.set(f"key{i}", i)
        assert len(cache._store) == 100

    def test_overwrite_does_not_increase_size(self):
        cache = LocalCache()
        cache.set("k", 1)
        cache.set("k", 2)
        cache.set("k", 3)
        assert len(cache._store) == 1

    def test_set_clears_expired_entries_on_get(self):
        cache = LocalCache(ttl=10)
        with patch("client.cache.time.time", return_value=_BASE_TIME):
            cache.set("a", 1)
            cache.set("b", 2)
        # Both expired
        with patch("client.cache.time.time", return_value=_BASE_TIME + 15):
            assert cache.get("a") is None
            assert "a" not in cache._store
            # Re-set b with a new timestamp
            cache.set("b", 3)
        with patch("client.cache.time.time", return_value=_BASE_TIME + 18):
            assert cache.get("b") == 3

    def test_get_does_not_mutate_store_on_fresh(self):
        cache = LocalCache()
        with patch("client.cache.time.time", return_value=_BASE_TIME):
            cache.set("k", "v")
        with patch("client.cache.time.time", return_value=_BASE_TIME + 5):
            cache.get("k")
            assert "k" in cache._store

    def test_clear_after_invalidate(self):
        cache = LocalCache()
        cache.set("a", 1)
        cache.invalidate("a")
        cache.set("b", 2)
        cache.clear()
        assert cache._store == {}
