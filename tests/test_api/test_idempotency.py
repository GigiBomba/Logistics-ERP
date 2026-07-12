"""Integration tests for the idempotency store inspection endpoints.

GET  /api/v1/idempotency/stats  — idempotency store statistics (admin only)
POST /api/v1/idempotency/clear  — clear both stores (admin only)

NOTE: The ``idempotency`` router is **not** included in the main
``api_v1_router``, so we build a minimal test app that mounts the
idempotency router directly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.idempotency import router as idempotency_router
from backend.dependencies_security import get_current_user, require_admin

BASE = "/api/v1/idempotency"
MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}


def _make_client(extra_overrides=None):
    """Build a TestClient with auth overrides and the idempotency router."""
    app = FastAPI()
    app.include_router(idempotency_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[require_admin] = lambda: MOCK_USER
    if extra_overrides:
        app.dependency_overrides.update(extra_overrides)
    return TestClient(app)


class TestIdempotencyStats:
    """GET /api/v1/idempotency/stats"""

    def test_stats_returns_memory_store(self):
        """Returns 200 with in-memory store statistics."""
        mock_redis = MagicMock()
        mock_redis.available = False

        client = _make_client()
        with (
            patch("backend.api.v1.idempotency.get_redis_store", return_value=mock_redis),
            patch("backend.api.v1.idempotency._idempotency_store", new={"key1": (9999999999, 200, "application/json", "{}")}),
        ):
            resp = client.get(f"{BASE}/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "memory" in data
            assert data["memory"]["active_keys"] == 1
            assert len(data["memory"]["keys"]) == 1

    def test_stats_returns_redis_store_when_available(self):
        """Includes Redis store stats when Redis is available."""
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.count.return_value = 3
        mock_redis.keys_with_ttl.return_value = [
            {"hash": "abc123...", "expires_in": 3600},
        ]

        client = _make_client()
        with (
            patch("backend.api.v1.idempotency.get_redis_store", return_value=mock_redis),
            patch("backend.api.v1.idempotency._idempotency_store", new={}),
        ):
            resp = client.get(f"{BASE}/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "redis" in data
            assert data["redis"]["active_keys"] == 3
            assert len(data["redis"]["keys"]) == 1

    def test_stats_empty_stores(self):
        """Returns zero active keys when both stores are empty."""
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.count.return_value = 0
        mock_redis.keys_with_ttl.return_value = []

        client = _make_client()
        with (
            patch("backend.api.v1.idempotency.get_redis_store", return_value=mock_redis),
            patch("backend.api.v1.idempotency._idempotency_store", new={}),
        ):
            resp = client.get(f"{BASE}/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["memory"]["active_keys"] == 0
            assert data["memory"]["keys"] == []
            assert data["redis"]["active_keys"] == 0

    def test_stats_truncates_keys_at_100(self):
        """Only returns up to 100 keys per store."""
        mock_memory = {
            f"key{i}": (9999999999, 200, "application/json", "{}")
            for i in range(150)
        }
        # Simulate keys_with_ttl respecting the limit=100 parameter
        all_redis_keys = [{"hash": f"hash{i}...", "expires_in": 100} for i in range(150)]
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.count.return_value = 150
        mock_redis.keys_with_ttl.side_effect = lambda limit=100: all_redis_keys[:limit]

        client = _make_client()
        with (
            patch("backend.api.v1.idempotency.get_redis_store", return_value=mock_redis),
            patch("backend.api.v1.idempotency._idempotency_store", new=mock_memory),
        ):
            resp = client.get(f"{BASE}/stats")
            data = resp.json()
            assert len(data["memory"]["keys"]) == 100
            assert len(data["redis"]["keys"]) == 100

    def test_stats_requires_auth(self):
        """Without auth token, returns 401."""
        app = FastAPI()
        app.include_router(idempotency_router, prefix="/api/v1")
        raw_client = TestClient(app)
        resp = raw_client.get(f"{BASE}/stats")
        assert resp.status_code == 401


class TestIdempotencyClear:
    """POST /api/v1/idempotency/clear"""

    def test_clear_removes_memory_keys(self):
        """Clears in-memory store and returns count."""
        mock_redis = MagicMock()
        mock_redis.available = False

        memory = {"key1": (9999999999, 200, "text/plain", "ok")}

        client = _make_client()
        with (
            patch("backend.api.v1.idempotency.get_redis_store", return_value=mock_redis),
            patch("backend.api.v1.idempotency._idempotency_store", new=memory),
        ):
            resp = client.post(f"{BASE}/clear")
            assert resp.status_code == 200
            data = resp.json()
            assert data["cleared"] is True
            assert data["memory_keys_removed"] == 1
            assert data["redis_keys_removed"] == 0

    def test_clear_removes_redis_keys_when_available(self):
        """Clears both stores and returns counts."""
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.clear.return_value = 5

        memory = {"k1": (9999999999, 200, "text/plain", "a"), "k2": (9999999999, 200, "text/plain", "b")}

        client = _make_client()
        with (
            patch("backend.api.v1.idempotency.get_redis_store", return_value=mock_redis),
            patch("backend.api.v1.idempotency._idempotency_store", new=memory),
        ):
            resp = client.post(f"{BASE}/clear")
            assert resp.status_code == 200
            data = resp.json()
            assert data["cleared"] is True
            assert data["memory_keys_removed"] == 2
            assert data["redis_keys_removed"] == 5

    def test_clear_empty_stores(self):
        """Returns zero counts when both stores are already empty."""
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.clear.return_value = 0

        client = _make_client()
        with (
            patch("backend.api.v1.idempotency.get_redis_store", return_value=mock_redis),
            patch("backend.api.v1.idempotency._idempotency_store", new={}),
        ):
            resp = client.post(f"{BASE}/clear")
            assert resp.status_code == 200
            data = resp.json()
            assert data["cleared"] is True
            assert data["memory_keys_removed"] == 0
            assert data["redis_keys_removed"] == 0

    def test_clear_requires_auth(self):
        """Without auth token, returns 401."""
        app = FastAPI()
        app.include_router(idempotency_router, prefix="/api/v1")
        raw_client = TestClient(app)
        resp = raw_client.post(f"{BASE}/clear")
        assert resp.status_code == 401
