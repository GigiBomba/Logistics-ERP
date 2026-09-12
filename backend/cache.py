from __future__ import annotations

import json
import os
import threading
import uuid
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

    @property
    def is_enabled(self) -> bool:
        """True when the underlying Redis connection is live and usable."""
        return self._enabled and self._redis is not None

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

    def llen(self, key: str) -> int:
        """Return the length of a Redis list (0 when unavailable/absent)."""
        if not self._enabled or self._redis is None:
            return 0
        try:
            return int(self._redis.llen(key) or 0)
        except Exception:
            return 0

    def expire(self, key: str, ttl: int) -> bool:
        """Set a TTL on *key* (best-effort; used to bound list keys)."""
        if not self._enabled or self._redis is None:
            return False
        try:
            return bool(self._redis.expire(key, ttl))
        except Exception:
            return False

    def acquire_lock(self, key: str, ttl: int) -> Optional[str]:
        """Try to acquire a non-blocking distributed lock (SET NX EX).

        Returns the lock token on success, or ``None`` when the lock is
        already held / Redis is unavailable.  Callers MUST tenant-scope
        *key* (embed ``company_id``) — no shared cross-tenant lock keys.
        The lock auto-expires after ``ttl`` seconds (a crashed holder can
        never block forever).
        """
        if not self._enabled or self._redis is None:
            return None
        try:
            token = f"{os.getpid()}-{uuid.uuid4().hex}"
            if self._redis.set(key, token, nx=True, ex=ttl):
                return token
            return None
        except Exception:
            return None

    def release_lock(self, key: str, token: str) -> bool:
        """Release a lock previously acquired with :meth:`acquire_lock`.

        Only deletes the key when it still holds *token*, so a stale holder
        (whose lock already expired and was re-acquired by another worker)
        can never delete another worker's live lock.
        """
        if not self._enabled or self._redis is None:
            return False
        try:
            script = """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            else
                return 0
            end
            """
            return bool(self._redis.eval(script, 1, key, token))
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
