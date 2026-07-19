"""Tests for the freight exchange API router (``/api/v1/freight``).

Covers all 14 endpoints across provider management, search, saved searches,
and load operations — happy paths, auth failures, validation errors, 404s,
and service-layer error propagation.
"""
from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.test_api.conftest import StrippedMock

BASE = "/api/v1/freight"


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_provider_list() -> list[dict]:
    return [
        {
            "connection_id": "c-1",
            "provider_id": "timocom",
            "status": "connected",
            "connected_at": "2026-01-01T00:00:00+00:00",
            "last_health_check_at": None,
            "last_health_check_status": None,
            "session_expires_at": None,
            "capabilities": None,
        },
    ]


def _make_search_body() -> dict:
    return {
        "origin_location": "Berlin",
        "destination_location": "Paris",
        "pickup_date_from": "2026-07-10",
        "pickup_date_to": "2026-07-20",
    }


def _make_save_search_body() -> dict:
    return {
        "label": "My Search",
        "filters": {
            "pickup_date_from": "2026-07-10",
            "pickup_date_to": "2026-07-20",
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# Provider Management (6 endpoints)
# ═════════════════════════════════════════════════════════════════════════════


class TestListProviders:
    """GET /freight/providers"""

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_happy_path_returns_providers_list(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.list_connected_providers.return_value = _make_provider_list()
        mock_conn_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/providers")

        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)
        assert data["providers"][0]["provider_id"] == "timocom"

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.get(f"{BASE}/providers")
        assert resp.status_code == 401

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_service_error_returns_500(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.list_connected_providers.side_effect = RuntimeError("DB down")
        mock_conn_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/providers")
        assert resp.status_code == 500


class TestConnectProvider:
    """POST /freight/providers/connect"""

    CONNECT_BODY = {
        "provider_id": "timocom",
        "client_id": "my-client",
        "client_secret": "s3cret",
    }

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_happy_path_returns_connection(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.connect_provider = AsyncMock(
            return_value={"connection_id": "c-1", "status": "connected"},
        )
        mock_conn_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/providers/connect", json=self.CONNECT_BODY)

        assert resp.status_code == 200
        data = resp.json()
        assert data["connection_id"] == "c-1"
        assert data["status"] == "connected"

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.post(f"{BASE}/providers/connect", json=self.CONNECT_BODY)
        assert resp.status_code == 401

    def test_missing_required_fields_returns_422(self, client_with_mocks: tuple) -> None:
        client, _mocks = client_with_mocks
        resp = client.post(
            f"{BASE}/providers/connect",
            json={"provider_id": "timocom"},  # missing client_id + client_secret
        )
        assert resp.status_code == 422

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_value_error_returns_400(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.connect_provider = AsyncMock(
            side_effect=ValueError("Unknown provider"),
        )
        mock_conn_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/providers/connect", json=self.CONNECT_BODY)
        assert resp.status_code == 400
        assert "Unknown provider" in resp.json()["detail"]

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_unexpected_error_returns_500(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.connect_provider = AsyncMock(
            side_effect=RuntimeError("Network failure"),
        )
        mock_conn_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/providers/connect", json=self.CONNECT_BODY)
        assert resp.status_code == 500


class TestDisconnectProvider:
    """POST /freight/providers/{provider_id}/disconnect"""

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_happy_path_returns_disconnected(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.disconnect_provider = AsyncMock(return_value=None)
        mock_conn_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/providers/timocom/disconnect")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"
        assert data["provider_id"] == "timocom"

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.post(f"{BASE}/providers/timocom/disconnect")
        assert resp.status_code == 401

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_service_error_returns_500(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.disconnect_provider = AsyncMock(
            side_effect=RuntimeError("DB error"),
        )
        mock_conn_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/providers/timocom/disconnect")
        assert resp.status_code == 500


class TestTestProviderConnection:
    """POST /freight/providers/{provider_id}/test"""

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_happy_path_returns_health(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        now = datetime.now(timezone.utc)
        health = StrippedMock()
        health.provider_id = "timocom"
        health.status = "healthy"
        health.latency_ms = 120
        health.checked_at = now
        health.error = None
        health.model_dump.return_value = {
            "provider_id": "timocom",
            "status": "healthy",
            "latency_ms": 120,
            "checked_at": now.isoformat(),
            "error": None,
        }

        mock_instance = StrippedMock()
        mock_instance.test_connection = AsyncMock(return_value=health)
        mock_conn_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/providers/timocom/test")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["provider_id"] == "timocom"

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.post(f"{BASE}/providers/timocom/test")
        assert resp.status_code == 401

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_no_active_connection_returns_404(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.test_connection = AsyncMock(return_value=None)
        mock_conn_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/providers/timocom/test")
        assert resp.status_code == 404
        assert "No active connection found" in resp.json()["detail"]

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_service_error_returns_500(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.test_connection = AsyncMock(
            side_effect=RuntimeError("Provider unreachable"),
        )
        mock_conn_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/providers/timocom/test")
        assert resp.status_code == 500


class TestConnectTransEu:
    """POST /freight/providers/connect_trans_eu"""

    TRANSEU_BODY = {
        "authorization_code": "auth-code-123",
        "redirect_uri": "https://app.operion.com/oauth/callback",
    }

    @patch("backend.config.BackendSettings")
    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_happy_path_returns_connected(
        self,
        mock_conn_cls: MagicMock,
        mock_settings_cls: MagicMock,
        client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        # Add user_id to the mock user (needed by this endpoint)
        from backend.dependencies_security import require_dispatcher
        client.app.dependency_overrides[require_dispatcher] = lambda: {
            "id": 1, "user_id": 1, "company_id": 1,
            "email": "test@test.com", "role": "admin", "is_admin": True,
        }
        mock_settings = StrippedMock()
        mock_settings.trans_eu_client_id = "client-123"
        mock_settings.trans_eu_client_secret = "secret"
        mock_settings.trans_eu_api_key = "api-key-456"
        mock_settings_cls.return_value = mock_settings

        session = StrippedMock()
        session.expires_at = datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)
        session.user_id = None

        mock_instance = StrippedMock()
        mock_instance.connect_trans_eu_user = AsyncMock(return_value=session)
        mock_conn_cls.return_value = mock_instance

        resp = client.post(
            f"{BASE}/providers/connect_trans_eu",
            json=self.TRANSEU_BODY,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert data["provider_id"] == "trans_eu"

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.post(
            f"{BASE}/providers/connect_trans_eu",
            json=self.TRANSEU_BODY,
        )
        assert resp.status_code == 401

    def test_missing_required_fields_returns_422(self, client_with_mocks: tuple) -> None:
        client, _mocks = client_with_mocks
        resp = client.post(
            f"{BASE}/providers/connect_trans_eu",
            json={},  # missing authorization_code and redirect_uri
        )
        assert resp.status_code == 422

    @patch("backend.config.BackendSettings")
    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_value_error_returns_400(
        self,
        mock_conn_cls: MagicMock,
        mock_settings_cls: MagicMock,
        client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        from backend.dependencies_security import require_dispatcher
        client.app.dependency_overrides[require_dispatcher] = lambda: {
            "id": 1, "user_id": 1, "company_id": 1,
            "email": "test@test.com", "role": "admin", "is_admin": True,
        }
        mock_settings = StrippedMock()
        mock_settings.trans_eu_client_id = "client-123"
        mock_settings.trans_eu_client_secret = "secret"
        mock_settings.trans_eu_api_key = "api-key-456"
        mock_settings_cls.return_value = mock_settings

        mock_instance = StrippedMock()
        mock_instance.connect_trans_eu_user = AsyncMock(
            side_effect=ValueError("Invalid authorization code"),
        )
        mock_conn_cls.return_value = mock_instance

        resp = client.post(
            f"{BASE}/providers/connect_trans_eu",
            json=self.TRANSEU_BODY,
        )
        assert resp.status_code == 400
        assert "Invalid authorization code" in resp.json()["detail"]

    @patch("backend.config.BackendSettings")
    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_unexpected_error_returns_500(
        self,
        mock_conn_cls: MagicMock,
        mock_settings_cls: MagicMock,
        client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        from backend.dependencies_security import require_dispatcher
        client.app.dependency_overrides[require_dispatcher] = lambda: {
            "id": 1, "user_id": 1, "company_id": 1,
            "email": "test@test.com", "role": "admin", "is_admin": True,
        }
        mock_settings = StrippedMock()
        mock_settings.trans_eu_client_id = "client-123"
        mock_settings.trans_eu_client_secret = "secret"
        mock_settings.trans_eu_api_key = "api-key-456"
        mock_settings_cls.return_value = mock_settings

        mock_instance = StrippedMock()
        mock_instance.connect_trans_eu_user = AsyncMock(
            side_effect=RuntimeError("OAuth provider timeout"),
        )
        mock_conn_cls.return_value = mock_instance

        resp = client.post(
            f"{BASE}/providers/connect_trans_eu",
            json=self.TRANSEU_BODY,
        )
        assert resp.status_code == 500


class TestGetTransEuStatus:
    """GET /freight/providers/trans_eu/status"""

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_happy_path_connected(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        from backend.dependencies_security import require_dispatcher
        client.app.dependency_overrides[require_dispatcher] = lambda: {
            "id": 1, "user_id": 1, "company_id": 1,
            "email": "test@test.com", "role": "admin", "is_admin": True,
        }
        session = StrippedMock()
        session.expires_at = datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)

        mock_instance = StrippedMock()
        mock_instance.get_trans_eu_session_for_user.return_value = session
        mock_conn_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/providers/trans_eu/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_id"] == "trans_eu"
        assert data["status"] == "connected"
        assert data["ttl_seconds"] > 0

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_disconnected_returns_status_disconnected(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        from backend.dependencies_security import require_dispatcher
        client.app.dependency_overrides[require_dispatcher] = lambda: {
            "id": 1, "user_id": 1, "company_id": 1,
            "email": "test@test.com", "role": "admin", "is_admin": True,
        }
        mock_instance = StrippedMock()
        mock_instance.get_trans_eu_session_for_user.return_value = None
        mock_conn_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/providers/trans_eu/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"
        assert data["provider_id"] == "trans_eu"

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.get(f"{BASE}/providers/trans_eu/status")
        assert resp.status_code == 401

    @patch("backend.api.v1.freight_exchange.ConnectionManagerService")
    def test_service_error_returns_500(
        self, mock_conn_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        from backend.dependencies_security import require_dispatcher
        client.app.dependency_overrides[require_dispatcher] = lambda: {
            "id": 1, "user_id": 1, "company_id": 1,
            "email": "test@test.com", "role": "admin", "is_admin": True,
        }
        mock_instance = StrippedMock()
        mock_instance.get_trans_eu_session_for_user.side_effect = RuntimeError("DB error")
        mock_conn_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/providers/trans_eu/status")
        assert resp.status_code == 500


# ═════════════════════════════════════════════════════════════════════════════
# Search (1 endpoint)
# ═════════════════════════════════════════════════════════════════════════════


class TestSearchLoads:
    """POST /freight/search"""

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_happy_path_returns_results(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        now = datetime.now(timezone.utc)

        result_set = StrippedMock()
        result_set.results = [
            StrippedMock(
                result_id="r-1",
                provider_id="timocom",
                provider_load_id="TL-001",
                origin="Berlin",
                destination="Paris",
                pickup_window=(now, now),
                delivery_window=(now, now),
                price=StrippedMock(amount=1500.0, currency="EUR"),
                distance_km=1200.0,
                trailer_type="standard",
                adr=False,
            ),
        ]
        for r in result_set.results:
            r.model_dump.return_value = {
                "result_id": "r-1",
                "provider_id": "timocom",
                "provider_load_id": "TL-001",
                "origin": "Berlin",
                "destination": "Paris",
                "pickup_window": [now.isoformat(), now.isoformat()],
                "delivery_window": [now.isoformat(), now.isoformat()],
                "price": {"amount": 1500.0, "currency": "EUR"},
                "distance_km": 1200.0,
                "trailer_type": "standard",
                "adr": False,
            }

        result_set.total_providers_queried = 1
        result_set.total_providers_skipped = 0
        result_set.provider_statuses = [
            StrippedMock(
                provider_id="timocom",
                status="ok",
                error="",
            ),
        ]
        for ps in result_set.provider_statuses:
            ps.model_dump = lambda mode="json": {  # type: ignore[method-assign]
                "provider_id": ps.provider_id,
                "status": ps.status,
                "error": ps.error,
            }

        mock_instance = StrippedMock()
        mock_instance.search_loads = AsyncMock(return_value=result_set)
        mock_search_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/search", json=_make_search_body())

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 1
        assert data["providers_queried"] == 1
        assert data["providers_skipped"] == 0
        assert isinstance(data["provider_statuses"], list)

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.post(f"{BASE}/search", json=_make_search_body())
        assert resp.status_code == 401

    def test_missing_required_fields_returns_422(self, client_with_mocks: tuple) -> None:
        client, _mocks = client_with_mocks
        resp = client.post(f"{BASE}/search", json={})
        assert resp.status_code == 422

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_service_error_returns_500(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.search_loads = AsyncMock(
            side_effect=RuntimeError("Search engine down"),
        )
        mock_search_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/search", json=_make_search_body())
        assert resp.status_code == 500


# ═════════════════════════════════════════════════════════════════════════════
# Saved Searches (3 endpoints)
# ═════════════════════════════════════════════════════════════════════════════


class TestGetRecentSearches:
    """GET /freight/searches"""

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_happy_path_returns_searches(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        now = datetime.now(timezone.utc)
        saved = StrippedMock()
        saved.saved_search_id = "ss-001"
        saved.label = "Test Search"
        saved.created_at = now
        saved.last_refreshed_at = None
        saved.model_dump.return_value = {
            "saved_search_id": "ss-001",
            "label": "Test Search",
            "created_at": now.isoformat(),
            "last_refreshed_at": None,
        }

        mock_instance = StrippedMock()
        mock_instance.get_recent_searches = AsyncMock(return_value=[saved])
        mock_search_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/searches")

        assert resp.status_code == 200
        data = resp.json()
        assert "searches" in data
        assert len(data["searches"]) == 1
        assert data["searches"][0]["saved_search_id"] == "ss-001"

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.get(f"{BASE}/searches")
        assert resp.status_code == 401

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_passes_limit_param(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.get_recent_searches = AsyncMock(return_value=[])
        mock_search_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/searches?limit=5")

        assert resp.status_code == 200
        # limit is the 3rd positional argument (company_id, user_id, limit)
        args = mock_instance.get_recent_searches.call_args[0]
        assert args[2] == 5

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_service_error_returns_500(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.get_recent_searches = AsyncMock(
            side_effect=RuntimeError("Search service unavailable"),
        )
        mock_search_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/searches")
        assert resp.status_code == 500


class TestSaveSearch:
    """POST /freight/searches"""

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_happy_path_returns_saved_search(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        now = datetime.now(timezone.utc)
        saved = StrippedMock()
        saved.saved_search_id = "ss-001"
        saved.label = "My Search"
        saved.created_at = now
        saved.last_refreshed_at = None
        saved.model_dump.return_value = {
            "saved_search_id": "ss-001",
            "label": "My Search",
            "created_at": now.isoformat(),
            "last_refreshed_at": None,
        }

        mock_instance = StrippedMock()
        mock_instance.save_search = AsyncMock(return_value=saved)
        mock_search_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/searches", json=_make_save_search_body())

        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_search_id"] == "ss-001"
        assert data["label"] == "My Search"

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.post(f"{BASE}/searches", json=_make_save_search_body())
        assert resp.status_code == 401

    def test_missing_required_fields_returns_422(self, client_with_mocks: tuple) -> None:
        client, _mocks = client_with_mocks
        resp = client.post(f"{BASE}/searches", json={})
        assert resp.status_code == 422

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_service_error_returns_500(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.save_search = AsyncMock(
            side_effect=RuntimeError("Save failed"),
        )
        mock_search_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/searches", json=_make_save_search_body())
        assert resp.status_code == 500


class TestRefreshSearch:
    """POST /freight/searches/{search_id}/refresh"""

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_happy_path_returns_results(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        now = datetime.now(timezone.utc)

        result_set = StrippedMock()
        result_set.results = []
        result_set.total_providers_queried = 1
        result_set.total_providers_skipped = 0
        result_set.provider_statuses = []

        mock_instance = StrippedMock()
        mock_instance.refresh_search = AsyncMock(return_value=result_set)
        mock_search_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/searches/ss-001/refresh")

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert data["providers_queried"] == 1

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.post(f"{BASE}/searches/ss-001/refresh")
        assert resp.status_code == 401

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_search_not_found_returns_404(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.refresh_search = AsyncMock(
            side_effect=ValueError("Saved search not found: ss-999"),
        )
        mock_search_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/searches/ss-999/refresh")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_service_error_returns_500(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.refresh_search = AsyncMock(
            side_effect=RuntimeError("Search failed"),
        )
        mock_search_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/searches/ss-001/refresh")
        assert resp.status_code == 500


# ═════════════════════════════════════════════════════════════════════════════
# Load Operations (4 endpoints)
# ═════════════════════════════════════════════════════════════════════════════


class TestGetLoad:
    """GET /freight/loads/{provider_id}/{load_id}"""

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_happy_path_returns_load(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        now = datetime.now(timezone.utc)
        load = StrippedMock()
        load.result_id = "TL-001"
        load.provider_id = "timocom"
        load.provider_load_id = "TL-001"
        load.origin = "Berlin"
        load.destination = "Paris"
        load.pickup_window = (now, now)
        load.delivery_window = (now, now)
        load.price = StrippedMock(amount=1500.0, currency="EUR")
        load.distance_km = 1200.0
        load.trailer_type = "standard"
        load.adr = False
        load.model_dump.return_value = {
            "result_id": "TL-001",
            "provider_id": "timocom",
            "provider_load_id": "TL-001",
            "origin": "Berlin",
            "destination": "Paris",
            "pickup_window": [now.isoformat(), now.isoformat()],
            "delivery_window": [now.isoformat(), now.isoformat()],
            "price": {"amount": 1500.0, "currency": "EUR"},
            "distance_km": 1200.0,
            "trailer_type": "standard",
            "adr": False,
        }

        mock_instance = StrippedMock()
        mock_instance.get_load = AsyncMock(return_value=load)
        mock_search_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/TL-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["result_id"] == "TL-001"
        assert data["provider_id"] == "timocom"

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.get(f"{BASE}/loads/timocom/TL-001")
        assert resp.status_code == 401

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_load_not_found_returns_404(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.get_load = AsyncMock(return_value=None)
        mock_search_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/nonexistent-999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_service_error_returns_500(
        self, mock_search_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.get_load = AsyncMock(
            side_effect=RuntimeError("Provider unreachable"),
        )
        mock_search_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/TL-001")
        assert resp.status_code == 500


class TestImportLoad:
    """POST /freight/loads/{provider_id}/{load_id}/import"""

    @patch("backend.api.v1.freight_exchange.ImportPipelineService")
    def test_happy_path_returns_import_result(
        self, mock_import_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        now = datetime.now(timezone.utc)
        result = StrippedMock()
        result.trip_id = 42
        result.source = "freight_exchange"
        result.source_provider_id = "timocom"
        result.source_reference_id = "TL-001"
        result.imported_at = now
        result.imported_by_user_id = 1
        result.model_dump.return_value = {
            "trip_id": 42,
            "source": "freight_exchange",
            "source_provider_id": "timocom",
            "source_reference_id": "TL-001",
            "imported_at": now.isoformat(),
            "imported_by_user_id": 1,
        }

        mock_instance = StrippedMock()
        mock_instance.import_load = AsyncMock(return_value=result)
        mock_import_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/loads/timocom/TL-001/import")

        assert resp.status_code == 200
        data = resp.json()
        assert data["trip_id"] == 42
        assert data["source"] == "freight_exchange"

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.post(f"{BASE}/loads/timocom/TL-001/import")
        assert resp.status_code == 401

    @patch("backend.api.v1.freight_exchange.ImportPipelineService")
    def test_import_error_returns_409(
        self, mock_import_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        from services.freight_exchange.import_pipeline import ImportError

        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.import_load = AsyncMock(
            side_effect=ImportError("Load already imported"),
        )
        mock_import_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/loads/timocom/TL-001/import")
        assert resp.status_code == 409
        assert "already imported" in resp.json()["detail"].lower()

    @patch("backend.api.v1.freight_exchange.ImportPipelineService")
    def test_unexpected_error_returns_500(
        self, mock_import_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.import_load = AsyncMock(
            side_effect=RuntimeError("Import pipeline crashed"),
        )
        mock_import_cls.return_value = mock_instance

        resp = client.post(f"{BASE}/loads/timocom/TL-001/import")
        assert resp.status_code == 500


class TestEvaluateLoad:
    """GET /freight/loads/{provider_id}/{load_id}/evaluate"""

    @patch("backend.api.v1.freight_exchange.EvaluationEngineService")
    def test_happy_path_returns_evaluation(
        self, mock_eval_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        now = datetime.now(timezone.utc)
        evaluation = StrippedMock()
        evaluation.provider_id = "timocom"
        evaluation.provider_load_id = "TL-001"
        evaluation.estimated_revenue = StrippedMock(amount=1500.0, currency="EUR")
        evaluation.fuel_cost = StrippedMock(amount=420.0, currency="EUR")
        evaluation.toll_cost = StrippedMock(amount=96.0, currency="EUR")
        evaluation.driver_salary = StrippedMock(amount=144.0, currency="EUR")
        evaluation.deadhead_distance_km = 0.0
        evaluation.expected_profit = StrippedMock(amount=840.0, currency="EUR")
        evaluation.profit_margin_pct = 56.0
        evaluation.estimated_duration_hours = 20.0
        evaluation.risk_score = 0.25
        evaluation.vehicle_compatibility = []
        evaluation.driver_compatibility = []
        evaluation.evaluated_at = now
        evaluation.model_dump.return_value = {
            "provider_id": "timocom",
            "provider_load_id": "TL-001",
            "estimated_revenue": {"amount": 1500.0, "currency": "EUR"},
            "fuel_cost": {"amount": 420.0, "currency": "EUR"},
            "toll_cost": {"amount": 96.0, "currency": "EUR"},
            "driver_salary": {"amount": 144.0, "currency": "EUR"},
            "deadhead_distance_km": 0.0,
            "expected_profit": {"amount": 840.0, "currency": "EUR"},
            "profit_margin_pct": 56.0,
            "estimated_duration_hours": 20.0,
            "risk_score": 0.25,
            "vehicle_compatibility": [],
            "driver_compatibility": [],
            "evaluated_at": now.isoformat(),
        }

        mock_instance = StrippedMock()
        mock_instance.evaluate_load = AsyncMock(return_value=evaluation)
        mock_eval_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/TL-001/evaluate")

        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_id"] == "timocom"
        assert data["estimated_revenue"]["amount"] == 1500.0

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.get(f"{BASE}/loads/timocom/TL-001/evaluate")
        assert resp.status_code == 401

    @patch("backend.api.v1.freight_exchange.EvaluationEngineService")
    def test_load_not_found_returns_404(
        self, mock_eval_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.evaluate_load = AsyncMock(
            side_effect=ValueError("Load not found: provider=timocom load_id=nonexistent-999"),
        )
        mock_eval_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/nonexistent-999/evaluate")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @patch("backend.api.v1.freight_exchange.EvaluationEngineService")
    def test_service_error_returns_500(
        self, mock_eval_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.evaluate_load = AsyncMock(
            side_effect=RuntimeError("Evaluation engine crashed"),
        )
        mock_eval_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/TL-001/evaluate")
        assert resp.status_code == 500


class TestMatchTrucks:
    """GET /freight/loads/{provider_id}/{load_id}/match"""

    @patch("backend.api.v1.freight_exchange.FleetMatcherService")
    def test_happy_path_returns_matches(
        self, mock_matcher_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        match = StrippedMock()
        match.vehicle_id = 10
        match.driver_id = 5
        match.score = 85.0
        match.rank = 1
        match.reasons = ["freight.match_reason.closest_vehicle"]
        match.distance_to_pickup_km = 0.0
        match.expected_deadhead_km = 0.0
        match.expected_profit = StrippedMock(amount=840.0, currency="EUR")
        match.driver_hours_remaining = 8.0
        match.maintenance_status = "good"
        match.trailer_compatible = True
        match.model_dump.return_value = {
            "vehicle_id": 10,
            "driver_id": 5,
            "score": 85.0,
            "rank": 1,
            "reasons": ["freight.match_reason.closest_vehicle"],
            "distance_to_pickup_km": 0.0,
            "expected_deadhead_km": 0.0,
            "expected_profit": {"amount": 840.0, "currency": "EUR"},
            "driver_hours_remaining": 8.0,
            "maintenance_status": "good",
            "trailer_compatible": True,
        }

        mock_instance = StrippedMock()
        mock_instance.find_best_trucks = AsyncMock(return_value=[match])
        mock_matcher_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/TL-001/match")

        assert resp.status_code == 200
        data = resp.json()
        assert "matches" in data
        assert len(data["matches"]) == 1
        assert data["matches"][0]["vehicle_id"] == 10
        assert data["matches"][0]["score"] == 85.0

    def test_unauthorized_without_token(self, app) -> None:
        client = TestClient(app)
        resp = client.get(f"{BASE}/loads/timocom/TL-001/match")
        assert resp.status_code == 401

    @patch("backend.api.v1.freight_exchange.FleetMatcherService")
    def test_load_not_found_returns_404(
        self, mock_matcher_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.find_best_trucks = AsyncMock(
            side_effect=ValueError("Load not found: provider=timocom load_id=nonexistent-999"),
        )
        mock_matcher_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/nonexistent-999/match")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @patch("backend.api.v1.freight_exchange.FleetMatcherService")
    def test_empty_fleet_returns_empty_matches(
        self, mock_matcher_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.find_best_trucks = AsyncMock(return_value=[])
        mock_matcher_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/TL-001/match")

        assert resp.status_code == 200
        data = resp.json()
        assert data["matches"] == []

    @patch("backend.api.v1.freight_exchange.FleetMatcherService")
    def test_respects_top_n_query_param(
        self, mock_matcher_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.find_best_trucks = AsyncMock(return_value=[])
        mock_matcher_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/TL-001/match?top_n=3")

        assert resp.status_code == 200
        # Verify top_n was passed to the service
        call_kwargs = mock_instance.find_best_trucks.call_args.kwargs
        assert call_kwargs["top_n"] == 3

    @patch("backend.api.v1.freight_exchange.FleetMatcherService")
    def test_service_error_returns_500(
        self, mock_matcher_cls: MagicMock, client_with_mocks: tuple,
    ) -> None:
        client, _mocks = client_with_mocks
        mock_instance = StrippedMock()
        mock_instance.find_best_trucks = AsyncMock(
            side_effect=RuntimeError("Matching engine failed"),
        )
        mock_matcher_cls.return_value = mock_instance

        resp = client.get(f"{BASE}/loads/timocom/TL-001/match")
        assert resp.status_code == 500


# ═════════════════════════════════════════════════════════════════════════════
# Cross-cutting auth tests (applies to all endpoints)
# ═════════════════════════════════════════════════════════════════════════════


class TestAuthAcrossAllEndpoints:
    """Each endpoint returns 401 without valid authentication."""

    ENDPOINTS: list[tuple[str, str, dict | None]] = [
        ("GET", "/providers", None),
        ("POST", "/providers/connect", {"provider_id": "t", "client_id": "c", "client_secret": "s"}),
        ("POST", "/providers/timocom/disconnect", None),
        ("POST", "/providers/timocom/test", None),
        ("POST", "/providers/connect_trans_eu", {"authorization_code": "a", "redirect_uri": "u"}),
        ("GET", "/providers/trans_eu/status", None),
        ("POST", "/search", _make_search_body()),
        ("GET", "/searches", None),
        ("POST", "/searches", _make_save_search_body()),
        ("POST", "/searches/ss-001/refresh", None),
        ("GET", "/loads/timocom/TL-001", None),
        ("POST", "/loads/timocom/TL-001/import", None),
        ("GET", "/loads/timocom/TL-001/evaluate", None),
        ("GET", "/loads/timocom/TL-001/match", None),
    ]

    @pytest.mark.parametrize("method,path,body", ENDPOINTS)
    def test_endpoint_returns_401_without_auth(
        self, method: str, path: str, body: dict | None, app,
    ) -> None:
        client = TestClient(app)
        url = f"{BASE}{path}"
        if method == "GET":
            resp = client.get(url)
        else:
            resp = client.post(url, json=body or {})
        assert resp.status_code == 401, (
            f"Expected 401 for {method} {url}, got {resp.status_code}"
        )
