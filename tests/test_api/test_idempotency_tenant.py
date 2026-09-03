"""Tests for idempotency middleware tenant scoping (R1) and async/atomic
Redis claim (R5).

Covers:
- Same raw idempotency key under two tenants → distinct tenant-scoped keys,
  no cross-tenant replay.
- Requests whose tenant cannot be derived (no JWT) skip caching entirely.
- The atomic claim: cached → replay; claimed → execute + store; in_progress →
  409 with NO underlying mutation.
"""
from __future__ import annotations

import asyncio
import hashlib
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.middleware.idempotency_middleware as idem_mw
from backend.middleware.idempotency_middleware import IdempotencyMiddleware
from backend.security import create_access_token

RAW_KEY = "shared-raw-key"
KEY_HASH = hashlib.sha256(RAW_KEY.encode()).hexdigest()


def _token(company_id: int) -> str:
    """Signed JWT carrying the given company_id (conftest JWT secret)."""
    return create_access_token({"sub": "u@x.com", "role": "admin", "company_id": company_id})


class FakeRedisStore:
    """Async store stub recording keys; per-key aclaim outcomes configurable."""

    def __init__(self, results=None):
        self.available = True
        self.results = results or {}  # full key -> (outcome, payload)
        self.aclaim_calls = []
        self.aset_calls = []

    async def aclaim(self, key):
        self.aclaim_calls.append(key)
        return self.results.get(key, ("claimed", None))

    async def aset(self, key, status, content_type, body):
        self.aset_calls.append((key, status, content_type, body))


@pytest.fixture(autouse=True)
def _fresh_memory_state(monkeypatch):
    """Isolate module-level in-memory bookkeeping + loop-bound lock per test."""
    monkeypatch.setattr(idem_mw, "_idempotency_store", {})
    monkeypatch.setattr(idem_mw, "_key_locks", {})
    monkeypatch.setattr(idem_mw, "_store_lock", asyncio.Lock())


def _make_client(store, executed: list = None):
    """Build a TestClient wrapping IdempotencyMiddleware with a fake store."""
    app = FastAPI()

    if executed is not None:
        @app.post("/mutate")
        async def mutate():
            executed.append(1)
            return {"ok": True}
    else:
        @app.post("/mutate")
        async def mutate():
            return {"ok": True}

    with patch(
        "backend.middleware.idempotency_middleware.get_redis_store",
        return_value=store,
    ):
        mw = IdempotencyMiddleware(app)
    return TestClient(mw, raise_server_exceptions=False)


def _post(client, company_id=None, raw_key=RAW_KEY):
    headers = {}
    if company_id is not None:
        headers["Authorization"] = f"Bearer {_token(company_id)}"
    headers["Idempotency-Key"] = raw_key
    return client.post("/mutate", headers=headers)


# ── R1: tenant scoping ────────────────────────────────────────────────────


class TestTenantScoping:
    def test_same_key_different_tenants_use_distinct_keys(self):
        store = FakeRedisStore()
        client = _make_client(store)

        r1 = _post(client, company_id=1)
        r2 = _post(client, company_id=2)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert store.aclaim_calls == [f"idem:1:{KEY_HASH}", f"idem:2:{KEY_HASH}"]
        assert len(store.aset_calls) == 2
        assert store.aset_calls[0][0] == f"idem:1:{KEY_HASH}"
        assert store.aset_calls[1][0] == f"idem:2:{KEY_HASH}"
        # In-memory bookkeeping is tenant-scoped too.
        assert f"idem:1:{KEY_HASH}" in idem_mw._idempotency_store
        assert f"idem:2:{KEY_HASH}" in idem_mw._idempotency_store

    def test_no_replay_across_tenants(self):
        executed = []
        store = FakeRedisStore(results={
            f"idem:1:{KEY_HASH}": (
                "cached", (200, "application/json", '{"from":"tenant1"}'),
            ),
        })
        client = _make_client(store, executed=executed)

        # Tenant 1 replays its own cached response.
        r1 = _post(client, company_id=1)
        assert r1.status_code == 200
        assert r1.json() == {"from": "tenant1"}
        assert executed == []

        # Tenant 2 with the SAME raw key must NOT replay tenant 1's response —
        # it executes its own mutation.
        r2 = _post(client, company_id=2)
        assert r2.status_code == 200
        assert r2.json() == {"ok": True}
        assert executed == [1]
        assert store.aclaim_calls == [f"idem:1:{KEY_HASH}", f"idem:2:{KEY_HASH}"]

    def test_no_tenant_skips_caching(self):
        store = FakeRedisStore()
        client = _make_client(store)

        resp = _post(client, company_id=None)
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert store.aclaim_calls == []
        assert store.aset_calls == []
        assert idem_mw._idempotency_store == {}

    def test_invalid_jwt_skips_caching(self):
        store = FakeRedisStore()
        client = _make_client(store)

        resp = client.post(
            "/mutate",
            headers={
                "Authorization": "Bearer not-a-valid-jwt",
                "Idempotency-Key": RAW_KEY,
            },
        )
        assert resp.status_code == 200
        assert store.aclaim_calls == []
        assert store.aset_calls == []


# ── R5: async atomic claim behaviour ──────────────────────────────────────


class TestAtomicClaim:
    def test_cached_claim_replays_without_executing(self):
        executed = []
        store = FakeRedisStore(results={
            f"idem:1:{KEY_HASH}": (
                "cached", (200, "application/json", '{"replayed":true}'),
            ),
        })
        client = _make_client(store, executed=executed)

        resp = _post(client, company_id=1)
        assert resp.status_code == 200
        assert resp.json() == {"replayed": True}
        assert executed == []

    def test_claimed_executes_and_stores(self):
        executed = []
        store = FakeRedisStore()
        client = _make_client(store, executed=executed)

        resp = _post(client, company_id=1)
        assert resp.status_code == 200
        assert executed == [1]
        assert len(store.aset_calls) == 1
        assert store.aset_calls[0][0] == f"idem:1:{KEY_HASH}"
        # In-memory mirror holds the tenant-scoped key.
        assert f"idem:1:{KEY_HASH}" in idem_mw._idempotency_store

    def test_in_progress_returns_409_and_does_not_execute(self):
        executed = []
        store = FakeRedisStore(results={
            f"idem:1:{KEY_HASH}": ("in_progress", None),
        })
        client = _make_client(store, executed=executed)

        resp = _post(client, company_id=1)
        assert resp.status_code == 409
        assert executed == []  # the mutation MUST NOT run twice

    def test_redis_unavailable_falls_back_to_in_memory(self):
        executed = []
        store = FakeRedisStore(results={
            f"idem:1:{KEY_HASH}": ("unavailable", None),
        })
        client = _make_client(store, executed=executed)

        r1 = _post(client, company_id=1)
        assert r1.status_code == 200
        assert executed == [1]
        assert f"idem:1:{KEY_HASH}" in idem_mw._idempotency_store

        # Second request from the same tenant replays the in-memory entry.
        r2 = _post(client, company_id=1)
        assert r2.status_code == 200
        assert r2.json() == {"ok": True}
        assert executed == [1]  # still only ONE execution