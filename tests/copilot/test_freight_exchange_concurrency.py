"""Freight accept idempotency — exactly-once semantics.

Proves that ``POST /api/v1/freight/loads/{provider_id}/{load_id}/import``
honors the ``Idempotency-Key`` header end-to-end:

* two accepts with the SAME key → exactly one mutation executes; the second
  gets a deduplicated replay response (``Idempotency-Replayed: true``) and
  produces no double side effect;
* two accepts with DIFFERENT keys → both proceed per business rules (each
  creates its own trip).

The deterministic core is the sequential same-key dedupe (the middleware
persists the cached response in ``_idempotency_store`` keyed by the SHA-256
of the key).  A best-effort concurrency check fires both requests
simultaneously over ``ASGITransport`` on the same event loop; the
middleware's per-key lock serializes them so exactly one executes the
pipeline and the other replays.

Storage note (Gate-3 review): without ``OPERION_REDIS_URL`` the middleware
falls back to its in-memory store, which is per-process.  Within a single
process (as exercised here) the per-key lock + in-memory store provide
exactly-once.  Multi-worker deployments require the Redis backend — see
``backend/middleware/idempotency_middleware.py``.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.main import create_app
from backend.middleware.idempotency_middleware import (
    _idempotency_store,
    _key_locks,
)
from models.freight_exchange_models import ImportResult
from tests.test_helpers import InMemoryDB

IMPORT_URL = "/api/v1/freight/loads/timocom/TL-001/import"


# ═══════════════════════════════════════════════════════════════════════
# Test data helpers
# ═══════════════════════════════════════════════════════════════════════


def _make_import_result(trip_id: int = 1000) -> ImportResult:
    return ImportResult(
        trip_id=trip_id,
        source="freight_exchange",
        source_provider_id="timocom",
        source_reference_id="TL-001",
        imported_at=datetime.now(timezone.utc),
        imported_by_user_id=1,
    )


def _build_app(db: InMemoryDB):
    """App with mocked get_db + a dispatcher user (company_id=1)."""
    app = create_app()

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    async def _mock_dispatcher() -> Dict[str, Any]:
        return {
            "id": 1,
            "email": "dispatcher@test.com",
            "role": "dispatcher",
            "is_admin": False,
            "company_id": 1,
        }

    app.dependency_overrides[require_dispatcher] = _mock_dispatcher
    return app


@pytest.fixture
def db() -> InMemoryDB:
    """Fresh in-memory SQLite database for each test."""
    return InMemoryDB()


@pytest.fixture
def client(db: InMemoryDB) -> TestClient:
    """TestClient with mocked get_db and require_dispatcher."""
    return TestClient(_build_app(db))


@pytest.fixture(autouse=True)
def _clear_idempotency_state():
    """Reset the module-level idempotency stores between tests.

    Both stores are process-global singletons shared by every middleware
    instance — without a reset, a key cached by one test would be replayed
    by the next.
    """
    _idempotency_store.clear()
    _key_locks.clear()
    yield
    _idempotency_store.clear()
    _key_locks.clear()


def _mock_import_pipeline(mock_cls: MagicMock, counter: dict) -> MagicMock:
    """Wire an AsyncMock that counts pipeline executions and returns a trip."""
    async def _import_side_effect(**kwargs):
        counter["n"] += 1
        return _make_import_result(trip_id=1000 + counter["n"])

    instance = MagicMock()
    instance.import_load = AsyncMock(side_effect=_import_side_effect)
    mock_cls.return_value = instance
    return instance


# ═══════════════════════════════════════════════════════════════════════
# Deterministic core — sequential same-key dedupe
# ═══════════════════════════════════════════════════════════════════════


class TestSequentialDedupe:
    """Sequential replay of the same key must not re-run the mutation."""

    @patch("backend.api.v1.freight_exchange.ImportPipelineService")
    def test_same_key_twice_executes_mutation_exactly_once(
        self, mock_cls: MagicMock, client: TestClient,
    ) -> None:
        counter = {"n": 0}
        _mock_import_pipeline(mock_cls, counter)
        key = "accept-tl-001-retry"

        # First request — cache miss, mutation runs.
        resp1 = client.post(IMPORT_URL, headers={"Idempotency-Key": key})
        assert resp1.status_code == 200
        assert resp1.headers.get("Idempotency-Replayed") is None
        assert counter["n"] == 1
        assert resp1.json()["trip_id"] == 1001

        # Second request, same key — replay, mutation does NOT run again.
        resp2 = client.post(IMPORT_URL, headers={"Idempotency-Key": key})
        assert resp2.status_code == 200
        assert resp2.headers.get("Idempotency-Replayed") == "true"
        assert counter["n"] == 1, (
            "Second accept with the same Idempotency-Key must not re-execute "
            "the import pipeline (no double side effect)"
        )

    @patch("backend.api.v1.freight_exchange.ImportPipelineService")
    def test_different_keys_both_proceed(
        self, mock_cls: MagicMock, client: TestClient,
    ) -> None:
        counter = {"n": 0}
        _mock_import_pipeline(mock_cls, counter)

        resp1 = client.post(
            IMPORT_URL, headers={"Idempotency-Key": "accept-tl-001-op-a"},
        )
        resp2 = client.post(
            IMPORT_URL, headers={"Idempotency-Key": "accept-tl-001-op-b"},
        )

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert counter["n"] == 2, "Distinct keys must each proceed"
        assert resp1.headers.get("Idempotency-Replayed") is None
        assert resp2.headers.get("Idempotency-Replayed") is None
        assert resp1.json()["trip_id"] != resp2.json()["trip_id"]


# ═══════════════════════════════════════════════════════════════════════
# Best-effort concurrency — two simultaneous accepts
# ═══════════════════════════════════════════════════════════════════════


class TestConcurrentAccepts:
    """Two simultaneous accepts — same key ⇒ one mutation, different keys ⇒ two."""

    @pytest.mark.asyncio
    async def test_concurrent_same_key_exactly_one_mutation(self, db: InMemoryDB) -> None:
        """Same key fired concurrently → exactly one pipeline execution.

        The middleware's per-key lock serializes the two requests on the
        event loop: the second one observes the cached response and replays
        it instead of re-running the mutation.
        """
        import httpx

        app = _build_app(db)
        counter = {"n": 0}

        async def _import_side_effect(**kwargs):
            counter["n"] += 1
            await asyncio.sleep(0.05)  # widen the race window
            return _make_import_result(trip_id=3000 + counter["n"])

        with patch("backend.api.v1.freight_exchange.ImportPipelineService") as mock_cls:
            instance = MagicMock()
            instance.import_load = AsyncMock(side_effect=_import_side_effect)
            mock_cls.return_value = instance

            key = "concurrent-accept-tl-001"
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as ac:
                resp1, resp2 = await asyncio.gather(
                    ac.post(IMPORT_URL, headers={"Idempotency-Key": key}),
                    ac.post(IMPORT_URL, headers={"Idempotency-Key": key}),
                )

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert counter["n"] == 1, (
            "Two concurrent accepts with the same key must execute the "
            f"mutation exactly once, got {counter['n']}"
        )

        replayed = [
            r for r in (resp1, resp2)
            if r.headers.get("Idempotency-Replayed") == "true"
        ]
        fresh = [
            r for r in (resp1, resp2)
            if r.headers.get("Idempotency-Replayed") is None
        ]
        assert len(fresh) == 1, "Exactly one request should execute the mutation"
        assert len(replayed) == 1, "Exactly one request should be deduplicated"

    @pytest.mark.asyncio
    async def test_concurrent_different_keys_both_proceed(self, db: InMemoryDB) -> None:
        """Different keys fired concurrently → both proceed per business rules."""
        import httpx

        app = _build_app(db)
        counter = {"n": 0}

        async def _import_side_effect(**kwargs):
            counter["n"] += 1
            await asyncio.sleep(0.02)
            return _make_import_result(trip_id=4000 + counter["n"])

        with patch("backend.api.v1.freight_exchange.ImportPipelineService") as mock_cls:
            instance = MagicMock()
            instance.import_load = AsyncMock(side_effect=_import_side_effect)
            mock_cls.return_value = instance

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as ac:
                resp1, resp2 = await asyncio.gather(
                    ac.post(IMPORT_URL, headers={"Idempotency-Key": "accept-a"}),
                    ac.post(IMPORT_URL, headers={"Idempotency-Key": "accept-b"}),
                )

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert counter["n"] == 2, "Distinct keys must each proceed concurrently"
        assert resp1.headers.get("Idempotency-Replayed") is None
        assert resp2.headers.get("Idempotency-Replayed") is None
