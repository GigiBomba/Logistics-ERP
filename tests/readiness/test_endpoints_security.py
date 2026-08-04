"""End-to-end tests for webhook receiver, GDPR, OAuth2, feature flags,
and idempotency endpoints — security gating, payload validation, and
happy-path execution.

Uses FastAPI ``TestClient`` with dependency overrides to simulate
authentication and database access without a real backend.
"""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.router import api_v1_router
from database.db_manager import DatabaseManager

BASE = "/api/v1"

# Known secret used for HMAC webhook signature tests
_TEST_WEBHOOK_SECRET = "test-webhook-secret-abc123"


# ── App / client helpers ─────────────────────────────────────────────────


def _make_app() -> FastAPI:
    """Build a minimal FastAPI with all v1 routes mounted."""
    app = FastAPI()
    app.include_router(api_v1_router)
    return app


def _inject_admin(app: FastAPI) -> None:
    """Override auth dependencies so every endpoint passes as admin."""
    from backend.dependencies_security import (
        get_current_user,
        require_admin,
        require_dispatcher,
        require_manager,
    )

    mock_user = {
        "id": 1,
        "email": "admin@test.com",
        "role": "admin",
        "is_admin": True,
        "company_id": 1,
    }
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
    app.dependency_overrides[require_manager] = lambda: mock_user
    app.dependency_overrides[require_dispatcher] = lambda: mock_user


def _inject_db(app: FastAPI, **attrs) -> MagicMock:
    """Override ``get_db`` with a fresh ``MagicMock``.

    Any extra *attrs* are set on the returned mock (convenience for
    ``lastrowid``, ``fetchone`` return values, etc.).
    """
    from backend.dependencies import get_db

    mock_db = MagicMock()
    for k, v in attrs.items():
        setattr(mock_db, k, v)
    app.dependency_overrides[get_db] = lambda: mock_db
    return mock_db


def _admin_client(app: FastAPI, **db_attrs) -> TestClient:
    """Return a ``TestClient`` with admin auth + optional db mock."""
    _inject_admin(app)
    if db_attrs:
        _inject_db(app, **db_attrs)
    return TestClient(app)


def _unauth_client(app: FastAPI) -> TestClient:
    """Return a ``TestClient`` with **no** auth overrides (expect 401)."""
    return TestClient(app)


def _compute_hmac(payload: dict, secret: str) -> str:
    """Compute ``sha256=<hex>`` signature matching the webhook middleware."""
    body = json.dumps(payload).encode()
    dig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={dig}"


# ═════════════════════════════════════════════════════════════════════════
# Webhook endpoints
# ═════════════════════════════════════════════════════════════════════════


class TestWebhookReceiver:
    """POST /api/v1/webhooks/{partner} — event ingestion."""

    WEBHOOK_PATH = f"{BASE}/webhooks/timocom"
    PAYLOAD = {"event": "shipment.created", "company_id": 1}

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Create a fresh app + client with admin auth and a mock db per test."""
        self.app = _make_app()
        _inject_admin(self.app)
        self.mock_db = _inject_db(self.app)
        self.mock_cursor = MagicMock()
        self.mock_cursor.lastrowid = 42
        self.mock_db.execute.return_value = self.mock_cursor
        # By default no webhook secret is configured so signature verification
        # is skipped.  Tests that verify signature behaviour override this.
        self._webhook_secret_patch = patch(
            "backend.api.v1.webhooks._get_webhook_secret",
            return_value="",
        )
        self._webhook_secret_patch.start()
        # Enable the timocom_integration feature flag so webhook dispatch
        # does not skip processing.  FeatureFlagService is imported locally
        # inside _handle_timocom_webhook, so patch at its definition site.
        self._ff_patch = patch(
            "backend.services.feature_flags_service.FeatureFlagService.is_enabled",
            return_value=True,
        )
        self._ff_patch.start()
        self.client = TestClient(self.app)
        yield
        self._ff_patch.stop()
        self._webhook_secret_patch.stop()
        self.app.dependency_overrides.clear()

    # ── Happy path ───────────────────────────────────────────────────

    def test_webhook_receives_event(self):
        """POST /webhooks/timocom with valid JSON returns 200 + event_id."""
        resp = self.client.post(self.WEBHOOK_PATH, json=self.PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["received"] is True
        assert data["event_id"] == 42
        assert data["partner"] == "timocom"
        assert data["event_type"] == "shipment.created"

    def test_webhook_invalid_json(self):
        """POST with malformed JSON body returns 400."""
        resp = self.client.post(
            self.WEBHOOK_PATH,
            content=b"not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["detail"]

    def test_webhook_payload_must_be_object(self):
        """POST with a JSON array instead of object returns 400."""
        resp = self.client.post(
            self.WEBHOOK_PATH,
            content=b'["array", "not", "object"]',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert "Payload must be a JSON object" in resp.json()["detail"]

    # ── Signature verification ───────────────────────────────────────

    def test_webhook_signature_correct_hmac_passes(self):
        """Correct HMAC-SHA256 header → request succeeds."""
        with patch(
            "backend.api.v1.webhooks._get_webhook_secret",
            return_value=_TEST_WEBHOOK_SECRET,
        ):
            sig = _compute_hmac(self.PAYLOAD, _TEST_WEBHOOK_SECRET)
            resp = self.client.post(
                self.WEBHOOK_PATH,
                content=json.dumps(self.PAYLOAD).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": sig,
                },
            )
        assert resp.status_code == 200
        assert resp.json()["received"] is True

    def test_webhook_signature_wrong_hmac_rejected(self):
        """Wrong HMAC-SHA256 header → 403."""
        with patch(
            "backend.api.v1.webhooks._get_webhook_secret",
            return_value=_TEST_WEBHOOK_SECRET,
        ):
            resp = self.client.post(
                self.WEBHOOK_PATH,
                content=json.dumps(self.PAYLOAD).encode(),
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": "sha256=" + "0" * 64,
                },
            )
        assert resp.status_code == 403
        assert "Invalid webhook signature" in resp.json()["detail"]

    def test_webhook_missing_signature_header_when_secret_configured(self):
        """Missing signature header while secret is configured → 403."""
        with patch(
            "backend.api.v1.webhooks._get_webhook_secret",
            return_value=_TEST_WEBHOOK_SECRET,
        ):
            resp = self.client.post(
                self.WEBHOOK_PATH,
                content=json.dumps(self.PAYLOAD).encode(),
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 403
        assert "Invalid webhook signature" in resp.json()["detail"]

    def test_webhook_no_secret_skips_verification(self):
        """When no secret is configured, requests pass without signature."""
        # _get_webhook_secret returns "" by default on a mock
        resp = self.client.post(self.WEBHOOK_PATH, json=self.PAYLOAD)
        assert resp.status_code == 200

    # ── Event persistence ────────────────────────────────────────────

    def test_webhook_event_persisted(self):
        """Event is inserted into webhook_events table."""
        self.client.post(self.WEBHOOK_PATH, json=self.PAYLOAD)

        # Verify an INSERT was performed on webhook_events
        insert_calls = [
            c
            for c in self.mock_db.execute.call_args_list
            if "INSERT INTO webhook_events" in str(c)
        ]
        assert len(insert_calls) >= 1

        # Verify the payload json was included
        args, _ = insert_calls[0]
        assert "webhook_events" in args[0]
        assert self.PAYLOAD["event"] in str(args)

    def test_webhook_event_updated_after_processing(self):
        """Processing status is updated via an UPDATE after dispatch."""
        self.client.post(self.WEBHOOK_PATH, json=self.PAYLOAD)

        update_calls = [
            c
            for c in self.mock_db.execute.call_args_list
            if "UPDATE webhook_events" in str(c)
        ]
        assert len(update_calls) >= 1

    # ── Admin events listing ─────────────────────────────────────────

    def test_webhook_events_listing_requires_admin(self):
        """GET /webhooks/events returns 401 without authentication."""
        app = _make_app()
        client = _unauth_client(app)
        resp = client.get(f"{BASE}/webhooks/events")
        assert resp.status_code == 401

    def test_webhook_events_listing_as_admin(self):
        """GET /webhooks/events returns 200 for admin users."""
        app = _make_app()
        client = _admin_client(app)
        mock_db = _inject_db(app)
        mock_db.conn.execute.return_value.fetchall.return_value = []
        resp = client.get(f"{BASE}/webhooks/events")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "total" in data


# ═════════════════════════════════════════════════════════════════════════
# GDPR endpoints
# ═════════════════════════════════════════════════════════════════════════


class TestGdprEndpoints:
    """GDPR compliance endpoints — data export, deletion, inventory."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.app = _make_app()
        _inject_admin(self.app)
        self.mock_db = _inject_db(self.app)
        # Seed a user row for user-export tests
        self.mock_user_row = {"id": 1, "email": "user@test.com",
                              "role": "driver", "company_id": 1,
                              "is_active": 1}
        self.mock_db.conn.execute.return_value.fetchone.return_value = \
            self.mock_user_row
        # Wire the real row_to_dict so the repo layer gets correct None-vs-dict
        self.mock_db.row_to_dict.side_effect = DatabaseManager.row_to_dict
        self.client = TestClient(self.app)
        yield
        self.app.dependency_overrides.clear()

    # ── Data export ──────────────────────────────────────────────────

    def test_export_company_data(self):
        """POST /gdpr/export/company/{id} returns JSON file."""
        resp = self.client.post(f"{BASE}/gdpr/export/company/1")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"
        assert "gdpr_export" in resp.headers.get("content-disposition", "")

    def test_export_user_data(self):
        """POST /gdpr/export/user/{id} returns JSON file."""
        resp = self.client.post(f"{BASE}/gdpr/export/user/1")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"
        assert "gdpr_export" in resp.headers.get("content-disposition", "")

    def test_export_user_not_found(self):
        """POST /gdpr/export/user/{id} returns 404 for unknown user."""
        self.mock_db.conn.execute.return_value.fetchone.return_value = None
        resp = self.client.post(f"{BASE}/gdpr/export/user/999")
        assert resp.status_code == 404

    # ── Data deletion ────────────────────────────────────────────────

    def test_delete_company_requires_confirmation(self):
        """Without ?confirm=DELETE the endpoint returns 400."""
        resp = self.client.post(f"{BASE}/gdpr/delete/company/1")
        assert resp.status_code == 400
        assert "confirm" in resp.json()["detail"].lower() or \
               "DELETE" in resp.json()["detail"]

    def test_delete_company_with_confirmation(self):
        """With ?confirm=DELETE the endpoint performs a soft delete."""
        resp = self.client.post(
            f"{BASE}/gdpr/delete/company/1?confirm=DELETE",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["company_id"] == 1

    def test_delete_user(self):
        """POST /gdpr/delete/user/{id} deactivates the user."""
        resp = self.client.post(f"{BASE}/gdpr/delete/user/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deactivated"
        assert data["user_id"] == 1

    def test_delete_user_calls_update(self):
        """User deactivation executes an UPDATE on the users table."""
        self.client.post(f"{BASE}/gdpr/delete/user/1")
        update_calls = [
            c
            for c in self.mock_db.conn.execute.call_args_list
            if "UPDATE users SET is_active" in str(c)
        ]
        assert len(update_calls) >= 1

    # ── Data inventory ───────────────────────────────────────────────

    def test_data_inventory_returns_categories(self):
        """GET /gdpr/data-inventory returns data categories."""
        resp = self.client.get(f"{BASE}/gdpr/data-inventory")
        assert resp.status_code == 200
        data = resp.json()
        assert "data_categories" in data
        assert len(data["data_categories"]) > 0
        assert "data_subject_rights" in data
        assert "processing_purposes" in data

    def test_data_inventory_requires_admin(self):
        """GET /gdpr/data-inventory returns 401 without auth."""
        app = _make_app()
        client = _unauth_client(app)
        resp = client.get(f"{BASE}/gdpr/data-inventory")
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════════════
# OAuth2 endpoints
# ═════════════════════════════════════════════════════════════════════════


class TestOAuth2Endpoints:
    """OAuth2 client management and token issuance."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.app = _make_app()
        _inject_admin(self.app)
        self.mock_db = _inject_db(self.app)
        self.client = TestClient(self.app)
        yield
        self.app.dependency_overrides.clear()

    # ── Client registration ──────────────────────────────────────────

    def test_register_client(self):
        """POST /oauth2/clients returns client_id and client_secret."""
        # Mock OAuth2Service.register_client
        with patch(
            "backend.api.v1.oauth2.OAuth2Service",
        ) as MockService:
            instance = MockService.return_value
            instance.register_client.return_value = (
                "operion_test123",
                "secret-abc-def-456",
            )
            resp = self.client.post(
                f"{BASE}/oauth2/clients",
                json={"name": "Test Client", "partner": "timocom",
                       "scopes": ["read"]},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["client_id"] == "operion_test123"
        assert data["client_secret"] == "secret-abc-def-456"
        assert "warning" in data

    def test_register_client_requires_name(self):
        """Omitting 'name' returns 400."""
        resp = self.client.post(
            f"{BASE}/oauth2/clients",
            json={"partner": "timocom"},
        )
        assert resp.status_code == 400

    def test_register_client_requires_partner(self):
        """Omitting 'partner' returns 400."""
        resp = self.client.post(
            f"{BASE}/oauth2/clients",
            json={"name": "No Partner"},
        )
        assert resp.status_code == 400

    # ── List clients (admin gate) ────────────────────────────────────

    def test_list_clients_requires_admin(self):
        """GET /oauth2/clients returns 401 without auth."""
        app = _make_app()
        client = _unauth_client(app)
        resp = client.get(f"{BASE}/oauth2/clients")
        assert resp.status_code == 401

    def test_list_clients_as_admin(self):
        """GET /oauth2/clients returns 200 for admin."""
        with patch(
            "backend.api.v1.oauth2.OAuth2Service",
        ) as MockService:
            instance = MockService.return_value
            instance.list_clients.return_value = [
                {"client_id": "c1", "client_name": "C1"},
            ]
            resp = self.client.get(f"{BASE}/oauth2/clients")
        assert resp.status_code == 200
        data = resp.json()
        assert "clients" in data
        assert len(data["clients"]) == 1

    # ── Client-credentials token ─────────────────────────────────────

    def test_client_credentials_token(self):
        """POST /auth/token/client-credentials returns access_token."""
        app = _make_app()
        mock_db = _inject_db(app)
        client = TestClient(app)

        with patch(
            "backend.oauth2.OAuth2Service",
        ) as MockService:
            instance = MockService.return_value
            instance.issue_token.return_value = {
                "access_token": "jwt-abc-123",
                "token_type": "bearer",
                "expires_in": 3600,
            }
            resp = client.post(
                f"{BASE}/auth/token/client-credentials",
                data={"client_id": "operion_test", "client_secret": "sec"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "jwt-abc-123"
        assert data["token_type"] == "bearer"

    def test_client_credentials_invalid_returns_401(self):
        """Invalid client credentials return 401."""
        app = _make_app()
        mock_db = _inject_db(app)
        client = TestClient(app)

        with patch(
            "backend.oauth2.OAuth2Service",
        ) as MockService:
            instance = MockService.return_value
            instance.issue_token.return_value = None
            resp = client.post(
                f"{BASE}/auth/token/client-credentials",
                data={"client_id": "bad", "client_secret": "bad"},
            )
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════════════
# Feature flags endpoints
# ═════════════════════════════════════════════════════════════════════════


class TestFeatureFlagEndpoints:
    """Feature flag management — listing, toggling, admin gating."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.app = _make_app()
        _inject_admin(self.app)
        self.mock_db = _inject_db(self.app)
        self.client = TestClient(self.app)
        yield
        self.app.dependency_overrides.clear()

    # ── List flags ───────────────────────────────────────────────────

    def test_list_flags(self):
        """GET /feature-flags/ returns a list of flags."""
        with patch(
            "backend.api.v1.feature_flags.FeatureFlagService",
        ) as MockService:
            instance = MockService.return_value
            instance.list_flags.return_value = [
                {"key": "test_flag", "enabled": True},
            ]
            resp = self.client.get(f"{BASE}/feature-flags/")
        assert resp.status_code == 200
        data = resp.json()
        assert "flags" in data

    # ── Enable flag ──────────────────────────────────────────────────

    def test_enable_flag(self):
        """POST /feature-flags/{key}/enable sets the flag."""
        with patch(
            "backend.api.v1.feature_flags.FeatureFlagService",
        ) as MockService:
            instance = MockService.return_value
            # Ensure set_override is a no-op (should not raise)
            instance.set_override.return_value = None
            resp = self.client.post(
                f"{BASE}/feature-flags/timocom_integration/enable",
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "enabled"
        assert data["flag"] == "timocom_integration"

    def test_disable_flag(self):
        """POST /feature-flags/{key}/disable disables the flag."""
        with patch(
            "backend.api.v1.feature_flags.FeatureFlagService",
        ) as MockService:
            instance = MockService.return_value
            instance.set_override.return_value = None
            resp = self.client.post(
                f"{BASE}/feature-flags/timocom_integration/disable",
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disabled"

    def test_unknown_flag_returns_404(self):
        """POST on a non-existent flag key returns 404."""
        resp = self.client.post(
            f"{BASE}/feature-flags/nonexistent_flag/enable",
        )
        assert resp.status_code == 404

    # ── Admin gate ───────────────────────────────────────────────────

    def test_list_flags_requires_admin(self):
        """GET /feature-flags/ returns 401 without auth."""
        app = _make_app()
        client = _unauth_client(app)
        resp = client.get(f"{BASE}/feature-flags/")
        assert resp.status_code == 401

    def test_enable_flag_requires_admin(self):
        """POST /feature-flags/{key}/enable returns 401 without auth."""
        app = _make_app()
        client = _unauth_client(app)
        resp = client.post(f"{BASE}/feature-flags/test/enable")
        assert resp.status_code == 401

    def test_disable_flag_requires_admin(self):
        """POST /feature-flags/{key}/disable returns 401 without auth."""
        app = _make_app()
        client = _unauth_client(app)
        resp = client.post(f"{BASE}/feature-flags/test/disable")
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════════════
# Idempotency endpoints
# ═════════════════════════════════════════════════════════════════════════


class TestIdempotencyEndpoints:
    """Idempotency store inspection — stats and clear.

    Note: The idempotency router is **not** mounted on ``api_v1_router``
    (it is only added in ``main.create_app`` along with the middleware).
    These tests mount it explicitly on a standalone app.
    """

    @pytest.fixture(autouse=True)
    def _clear_store(self):
        """Ensure a fresh in-memory store before each test."""
        from backend.middleware.idempotency_middleware import (
            _idempotency_store,
        )
        _idempotency_store.clear()

    @staticmethod
    def _app_with_idempotency() -> FastAPI:
        """Build an app that includes the idempotency router."""
        from backend.api.v1.idempotency import router as idempotency_router

        app = FastAPI()
        app.include_router(api_v1_router)
        app.include_router(idempotency_router, prefix="/api/v1")
        return app

    # ── Stats ────────────────────────────────────────────────────────

    def test_idempotency_stats_requires_admin(self):
        """GET /idempotency/stats returns 401 without auth."""
        app = self._app_with_idempotency()
        client = _unauth_client(app)
        resp = client.get(f"{BASE}/idempotency/stats")
        assert resp.status_code == 401

    def test_idempotency_stats_as_admin(self):
        """GET /idempotency/stats returns store statistics."""
        app = self._app_with_idempotency()
        _inject_admin(app)
        client = TestClient(app)
        resp = client.get(f"{BASE}/idempotency/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "memory" in data
        assert "active_keys" in data["memory"]

    # ── Clear ────────────────────────────────────────────────────────

    def test_idempotency_clear_requires_admin(self):
        """POST /idempotency/clear returns 401 without auth."""
        app = self._app_with_idempotency()
        client = _unauth_client(app)
        resp = client.post(f"{BASE}/idempotency/clear")
        assert resp.status_code == 401

    def test_idempotency_clear_as_admin(self):
        """POST /idempotency/clear clears stores and returns counts."""
        app = self._app_with_idempotency()
        _inject_admin(app)
        # Seed a couple of keys
        from backend.middleware.idempotency_middleware import (
            _idempotency_store,
        )
        import time
        _idempotency_store["key1"] = (
            time.time() + 300, 200, "application/json", '{"ok":true}',
        )
        _idempotency_store["key2"] = (
            time.time() + 300, 200, "application/json", '{"ok":true}',
        )

        client = TestClient(app)
        resp = client.post(f"{BASE}/idempotency/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cleared"] is True
        assert data["memory_keys_removed"] >= 2
        # Store should be empty now
        assert len(_idempotency_store) == 0
