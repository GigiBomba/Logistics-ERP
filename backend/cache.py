import json
import threading
from typing import Any, Optional

import redis

from backend.config import BackendSettings

class RedisCache:
    def __init__(self, settings: BackendSettings):
        self._redis: Optional[redis.Redis] = None
        self._settings = settings
        self._enabled = False

    def connect(self) -> None:
        try:
            self._redis = redis.Redis.from_url(
                self._settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            self._redis.ping()
            self._enabled = True
        except (redis.ConnectionError, redis.TimeoutError, ValueError):
            self._enabled = False

    def get(self, key: str) -> Optional[Any]:
        if not self._enabled or self._redis is None:
            return None
        try:
            value = self._redis.get(key)
            return json.loads(value) if value else None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not self._enabled or self._redis is None:
            return False
        try:
            ttl = ttl or self._settings.redis_cache_ttl
            self._redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        if not self._enabled or self._redis is None:
            return False
        try:
            self._redis.delete(key)
            return True
        except Exception:
            return False

    def flush_pattern(self, pattern: str) -> int:
        if not self._enabled or self._redis is None:
            return 0
        try:
            keys = list(self._redis.scan_iter(match=pattern))
            if keys:
                return self._redis.delete(*keys)
            return 0
        except Exception:
            return 0

    def rpush(self, key: str, value: str) -> bool:
        if not self._enabled or self._redis is None:
            return False
        try:
            self._redis.rpush(key, value)
            return True
        except Exception:
            return False

    def lpop(self, key: str) -> Optional[str]:
        if not self._enabled or self._redis is None:
            return None
        try:
            return self._redis.lpop(key)
        except Exception:
            return None

    def lrange(self, key: str, start: int = 0, end: int = -1) -> list:
        """Return a slice of a Redis list (used by the GPS batch flush)."""
        if not self._enabled or self._redis is None:
            return []
        try:
            return self._redis.lrange(key, start, end)
        except Exception:
            return []

    def ltrim(self, key: str, start: int, end: int) -> bool:
        if not self._enabled or self._redis is None:
            return False
        try:
            self._redis.ltrim(key, start, end)
            return True
        except Exception:
            return False


_cache_instance: Optional[RedisCache] = None
_cache_lock = threading.Lock()


def get_cache() -> RedisCache:
    global _cache_instance
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:  # double-checked locking
                _cache_instance = RedisCache(BackendSettings())
                _cache_instance.connect()
    return _cache_instance
