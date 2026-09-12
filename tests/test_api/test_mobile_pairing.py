"""Tests for the mobile QR pairing-token endpoints (blueprint §5.3).

POST /api/v1/mobile/pairing-token          — issue a short-lived pairing token.
GET  /api/v1/mobile/pairing-token/validate — validate (and consume) a token.

The pairing store mirrors the refresh-token store in ``auth.py``: Redis when
configured, in-memory otherwise.  These tests force the in-memory fallback so
they never depend on a running Redis instance.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/mobile/pairing-token"


@pytest.fixture(autouse=True)
def _isolate_pairing_store(monkeypatch):
    """Force the in-memory store and clear it around every test."""
    from backend.api.v1 import mobile_pairing

    monkeypatch.setattr(mobile_pairing, "_get_redis", lambda: None)
    mobile_pairing._pairing_store.clear()
    yield
    mobile_pairing._pairing_store.clear()


class TestCreatePairingToken:
    """POST /api/v1/mobile/pairing-token"""

    def test_create_token_returns_qr_and_ttl(self, client):
        resp = client.post(BASE)
        assert resp.status_code == 200

        data = resp.json()
        token = data["pairing_token"]
        assert isinstance(token, str) and token

        # qr_data must embed the token and the authenticated user's company.
        assert data["qr_data"] == f"operion://pair?token={token}&company=1"

        # expires_at is an ISO-8601 UTC timestamp ~300s in the future.
        expires_at = datetime.fromisoformat(data["expires_at"])
        delta = (expires_at - datetime.now(timezone.utc)).total_seconds()
        assert 250 < delta <= 300

    def test_create_token_stores_payload_with_ttl(self, client):
        from backend.api.v1 import mobile_pairing

        data = client.post(BASE).json()
        token_hash = mobile_pairing._hash_token(data["pairing_token"])
        payload = mobile_pairing._pairing_store[token_hash]

        assert payload["user_id"] == 1
        assert payload["company_id"] == 1
        assert 250 < payload["expires_at"] - time.time() <= 300

    def test_create_token_unauthenticated_returns_401(self, app):
        unauth_client = TestClient(app)
        resp = unauth_client.post(BASE)
        assert resp.status_code == 401


class TestValidatePairingToken:
    """GET /api/v1/mobile/pairing-token/validate"""

    def test_validate_valid_token_is_single_use(self, client):
        token = client.post(BASE).json()["pairing_token"]

        first = client.get(f"{BASE}/validate", params={"token": token})
        assert first.status_code == 200
        body = first.json()
        assert body["valid"] is True
        assert body["user_id"] == 1
        assert body["company_id"] == 1
        assert 0 <= body["expires_in"] <= 300

        # Second use must fail — the token was consumed.
        second = client.get(f"{BASE}/validate", params={"token": token})
        assert second.status_code == 404
        detail = second.json()["detail"]
        assert detail["detail"] == "Pairing token invalid or expired"
        assert "error_code" in detail

    def test_validate_unknown_token_returns_404(self, client):
        resp = client.get(f"{BASE}/validate", params={"token": "not-a-real-token"})
        assert resp.status_code == 404
        assert resp.json()["detail"]["detail"] == "Pairing token invalid or expired"

    def test_validate_expired_token_returns_404(self, client):
        from backend.api.v1 import mobile_pairing

        token = "expired-pairing-token"
        token_hash = mobile_pairing._hash_token(token)
        mobile_pairing._pairing_store[token_hash] = {
            "user_id": 1,
            "company_id": 1,
            "created_at": time.time() - 400,
            "expires_at": time.time() - 100,
        }

        resp = client.get(f"{BASE}/validate", params={"token": token})
        assert resp.status_code == 404
        assert resp.json()["detail"]["detail"] == "Pairing token invalid or expired"
        # Expired records are purged on access.
        assert token_hash not in mobile_pairing._pairing_store
