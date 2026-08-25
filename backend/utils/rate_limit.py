"""Shared per-endpoint rate limiter (Redis-backed, in-memory fallback).

The global middleware limiter and the login brute-force limiter are already
Redis-backed; this helper gives the same cross-worker semantics to the
per-endpoint limiters (contact, registration, waitlist, invite-accept).

Semantics: a fixed window per (scope, key). Returns True when the request is
allowed, False when over the limit. Redis is preferred; when unavailable the
limiter degrades to a per-process in-memory window (single-worker behaviour,
same as the previous implementation — never crashes).
"""
from __future__ import annotations


import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_redis_client: Optional[Any] = None

# In-memory fallback (single-worker only) — used when Redis is unavailable.
_fallback: Dict[str, List[float]] = {}


def _get_redis():
    """Return a shared Redis client, or None if unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = os.environ.get("OPERION_REDIS_URL", "")
    redis_password = os.environ.get("OPERION_REDIS_PASSWORD", "")
    if not redis_url:
        return None
    try:
        import redis as _redis
        client = _redis.Redis.from_url(redis_url, socket_timeout=2, password=redis_password or None)
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None
    return _redis_client


def check_rate_limit(scope: str, key: str, limit: int, window_seconds: int) -> bool:
    """Return True if the request is allowed, False if over the limit."""
    redis_key = f"rl:{scope}:{key}"
    client = _get_redis()
    if client is not None:
        try:
            count = int(client.incr(redis_key))
            if count == 1:
                client.expire(redis_key, window_seconds)
            return count <= limit
        except Exception as exc:
            logger.error(
                "Redis rate-limit check failed for scope=%s — allowing via fallback: %s",
                scope, exc,
            )

    # In-memory fallback
    now = time.time()
    attempts = [t for t in _fallback.get(redis_key, []) if now - t < window_seconds]
    if len(attempts) >= limit:
        _fallback[redis_key] = attempts
        return False
    attempts.append(now)
    _fallback[redis_key] = attempts
    return True
