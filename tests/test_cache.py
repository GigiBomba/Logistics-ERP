"""Tests for RedisCache (graceful degradation when Redis is unavailable)."""


from backend.cache import RedisCache, get_cache
from backend.config import BackendSettings

class TestRedisCache:
    def test_cache_disabled_when_redis_unavailable(self):
        settings = BackendSettings(redis_url="redis://127.0.0.1:1/0")
        cache = RedisCache(settings)
        cache.connect()
        assert cache._enabled is False

    def test_get_returns_none_when_disabled(self):
        settings = BackendSettings()
        cache = RedisCache(settings)
        cache._enabled = False
        result = cache.get("test_key")
        assert result is None

    def test_set_returns_false_when_disabled(self):
        settings = BackendSettings()
        cache = RedisCache(settings)
        cache._enabled = False
        result = cache.set("test_key", "value")
        assert result is False

    def test_delete_returns_false_when_disabled(self):
        settings = BackendSettings()
        cache = RedisCache(settings)
        cache._enabled = False
        result = cache.delete("test_key")
        assert result is False

    def test_flush_pattern_returns_zero_when_disabled(self):
        settings = BackendSettings()
        cache = RedisCache(settings)
        cache._enabled = False
        result = cache.flush_pattern("doc:*")
        assert result == 0

    def test_get_cache_singleton(self):
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2
