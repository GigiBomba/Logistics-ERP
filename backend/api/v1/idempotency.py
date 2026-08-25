"""Idempotency store inspection (admin only).

Provides insight into both the Redis-backed and in-memory idempotency
stores so administrators can observe and clear cached responses across
all gunicorn workers.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from backend.dependencies_security import require_admin
from backend.middleware.idempotency_middleware import (
    _idempotency_store,
    cleanup_expired_entries,
    get_redis_store,
)

router = APIRouter(prefix="/idempotency", tags=["idempotency"])


@router.get("/stats")
async def idempotency_stats(_=Depends(require_admin)):
    """Get idempotency store statistics from both Redis and in-memory stores.

    Returns the number of active keys and a sample of upcoming expirations
    (up to 100 entries per store).
    """
    cleanup_expired_entries()

    redis_store = get_redis_store()

    result = {
        "memory": {
            "active_keys": len(_idempotency_store),
            "keys": [
                {"hash": k[:16] + "...", "expires_in": int(expiry - time.time())}
                for k, (expiry, _, _, _) in _idempotency_store.items()
            ][:100],  # Show at most 100
        },
    }

    if redis_store.available:
        result["redis"] = {
            "active_keys": redis_store.count(),
            "keys": redis_store.keys_with_ttl(limit=100),
        }

    return result


@router.post("/clear")
async def clear_idempotency_store(_=Depends(require_admin)):
    """Clear both the Redis and in-memory idempotency stores (admin only)."""
    redis_store = get_redis_store()
    redis_cleared = redis_store.clear() if redis_store.available else 0
    mem_cleared = len(_idempotency_store)
    _idempotency_store.clear()
    return {
        "cleared": True,
        "memory_keys_removed": mem_cleared,
        "redis_keys_removed": redis_cleared,
    }
