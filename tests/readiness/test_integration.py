"""Tests for ExternalHttpClient, IntegrationHealthService, and integration endpoints.

Uses ``unittest.mock.patch`` for HTTP requests and FastAPI ``TestClient``
for endpoint verification.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from services.exceptions import ExternalServiceError
from services.http_client import ExternalHttpClient, HttpClientConfig
from services.integration_health_service import (
    IntegrationHealthService,
    IntegrationStatus,
)


# ======================================================================
# ExternalHttpClient
# ======================================================================


class TestExternalHttpClient:
    """Unit tests for ``ExternalHttpClient``."""

    # ── Initialisation ──────────────────────────────────────────────

    def test_client_initialization(self):
        """HttpClientConfig + ExternalHttpClient creates a session with headers."""
        config = HttpClientConfig(
            base_url="https://api.example.com",
            timeout=15.0,
            max_retries=5,
            default_headers={"X-Api-Key": "test-key", "User-Agent": "operion-test"},
        )
        client = ExternalHttpClient(config)

        assert client.config.base_url == "https://api.example.com"
        assert client.config.timeout == 15.0
        assert client.config.max_retries == 5
        assert client._session is not None
        # Default headers from config are propagated to the session
        assert client._session.headers.get("X-Api-Key") == "test-key"
        assert client._session.headers.get("User-Agent") == "operion-test"

    # ── Request behaviour ───────────────────────────────────────────

    def test_get_request(self):
        """GET request constructs URL from ``base_url + path``."""
        config = HttpClientConfig(base_url="https://api.example.com")
        client = ExternalHttpClient(config)

        mock_resp = Mock(status_code=200, spec=requests.Response)
        with patch.object(client._session, "request", return_value=mock_resp) as mock_request:
            response = client.get("/v1/health")

        assert response.status_code == 200
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "GET", "HTTP method must be GET"
        assert args[1] == "https://api.example.com/v1/health", (
            "URL must combine base_url and path"
        )

    def test_headers_propagated(self):
        """Custom headers passed via ``get(…, headers=…)`` are sent with the request."""
        config = HttpClientConfig(base_url="https://api.example.com")
        client = ExternalHttpClient(config)

        mock_resp = Mock(status_code=200, spec=requests.Response)
        with patch.object(client._session, "request", return_value=mock_resp) as mock_request:
            client.get("/test", headers={"X-Custom": "value123"})

        _, kwargs = mock_request.call_args
        assert kwargs.get("headers") is not None
        assert kwargs["headers"]["X-Custom"] == "value123"

    # ── Retry / backoff ─────────────────────────────────────────────

    def test_retry_on_transient_error(self):
        """HTTP 503 triggers retry up to ``max_retries``, then succeeds."""
        config = HttpClientConfig(base_url="https://api.example.com", max_retries=3)
        client = ExternalHttpClient(config)

        responses = [
            Mock(status_code=503, spec=requests.Response),
            Mock(status_code=503, spec=requests.Response),
            Mock(status_code=200, spec=requests.Response),
        ]
        mock_request = Mock(side_effect=responses)
        with patch.object(client._session, "request", mock_request), \
             patch("time.sleep"):  # no real delay
            response = client.get("/test")

        assert response.status_code == 200
        # 1 initial attempt + 2 retries = 3 calls (3rd attempt succeeds)
        assert mock_request.call_count == 3

    def test_retry_on_connection_error(self):
        """ConnectionError triggers retry; succeeds on the final attempt."""
        config = HttpClientConfig(base_url="https://api.example.com", max_retries=2)
        client = ExternalHttpClient(config)

        mock_request = Mock(side_effect=[
            requests.exceptions.ConnectionError("first fail"),
            requests.exceptions.ConnectionError("second fail"),
            Mock(status_code=200, spec=requests.Response),
        ])
        with patch.object(client._session, "request", mock_request), \
             patch("time.sleep"):
            response = client.get("/test")

        assert response.status_code == 200
        assert mock_request.call_count == 3  # 1 initial + 2 retries

    def test_no_retry_on_4xx(self):
        """HTTP 400 / 404 does **not** trigger a retry."""
        config = HttpClientConfig(base_url="https://api.example.com", max_retries=3)
        client = ExternalHttpClient(config)

        mock_request = Mock(return_value=Mock(status_code=400, spec=requests.Response))
        with patch.object(client._session, "request", mock_request):
            response = client.get("/test")

        assert response.status_code == 400
        assert mock_request.call_count == 1, "Must not retry on 4xx"

    def test_timeout_handling(self):
        """Request timeout raises ``ExternalServiceError`` after exhausting retries."""
        config = HttpClientConfig(base_url="https://api.example.com", max_retries=2)
        client = ExternalHttpClient(config)

        mock_request = Mock(side_effect=requests.exceptions.Timeout("timed out"))
        with patch.object(client._session, "request", mock_request), \
             patch("time.sleep"):
            with pytest.raises(ExternalServiceError, match="External API call failed"):
                client.get("/test")
        # 1 initial + 2 retries = 3 calls
        assert mock_request.call_count == 3

    def test_final_failure_raises(self):
        """All retries exhausted (ConnectionError) → ``ExternalServiceError``."""
        config = HttpClientConfig(base_url="https://api.example.com", max_retries=2)
        client = ExternalHttpClient(config)

        mock_request = Mock(side_effect=requests.exceptions.ConnectionError("connection refused"))
        with patch.object(client._session, "request", mock_request), \
             patch("time.sleep"):
            with pytest.raises(ExternalServiceError, match="External API call failed"):
                client.get("/test")
        assert mock_request.call_count == 3


# ======================================================================
# IntegrationHealthService
# ======================================================================


class TestIntegrationHealthService:
    """Unit tests for ``IntegrationHealthService``."""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_status(
        name: str,
        connected: bool = True,
        error: str | None = None,
        latency: float | None = None,
    ) -> IntegrationStatus:
        now = datetime.now()
        return IntegrationStatus(
            name=name,
            connected=connected,
            last_check=now,
            last_success=now if connected else None,
            last_error=error,
            latency_ms=latency,
        )

    # ------------------------------------------------------------------
    # get_all_statuses / healthy_count
    # ------------------------------------------------------------------

    def test_get_all_statuses(self):
        """``get_all_statuses`` returns a dict keyed by every registered integration."""
        service = IntegrationHealthService(MagicMock())

        def fake_check(name: str, info: dict) -> IntegrationStatus:
            return self._make_status(info["display_name"], connected=True, latency=10.0)

        with patch.object(service, "_check_integration", side_effect=fake_check):
            result = service.get_all_statuses()

        assert "integrations" in result
        assert "healthy_count" in result
        assert "total_count" in result
        assert result["total_count"] == len(IntegrationHealthService._REGISTERED_INTEGRATIONS)
        for name in IntegrationHealthService._REGISTERED_INTEGRATIONS:
            assert name in result["integrations"], f"Missing integration: {name}"

    def test_healthy_count(self):
        """``healthy_count`` correctly reflects the number of connected integrations."""
        service = IntegrationHealthService(MagicMock())
        connected = {"graphhopper", "nominatim"}

        def fake_check(name: str, info: dict) -> IntegrationStatus:
            ok = name in connected
            return self._make_status(
                info["display_name"],
                connected=ok,
                error=None if ok else "Not available",
            )

        with patch.object(service, "_check_integration", side_effect=fake_check):
            result = service.get_all_statuses()

        assert result["healthy_count"] == 2
        assert result["total_count"] == 5

    # ------------------------------------------------------------------
    # disabled integration
    # ------------------------------------------------------------------

    def test_disabled_integration(self):
        """Integration with ``enabled=0`` in settings returns ``connected=False``."""
        service = IntegrationHealthService(MagicMock())

        with patch.object(service, "_get_setting", return_value="0"):
            result = service.get_status("graphhopper")

        assert result["connected"] is False
        assert result["last_error"] == "Integration disabled in settings"

    # ------------------------------------------------------------------
    # caching
    # ------------------------------------------------------------------

    def test_cache_works(self):
        """Second call within TTL returns the cached result without re-checking."""
        service = IntegrationHealthService(MagicMock())
        status = self._make_status("GraphHopper Routing", connected=True)

        # First call — populates the cache
        with patch.object(service, "_check_integration", return_value=status) as mock_check:
            r1 = service.get_status("graphhopper")
            mock_check.assert_called_once()
            assert r1["connected"] is True

        # Second call — should hit cache
        with patch.object(service, "_check_integration") as mock_check:
            r2 = service.get_status("graphhopper")
            mock_check.assert_not_called()
            assert r2["connected"] is True

    def test_check_now_forces_refresh(self):
        """``check_now`` bypasses the cache and performs a fresh check."""
        service = IntegrationHealthService(MagicMock())
        status = self._make_status("GraphHopper Routing", connected=True)

        # Populate the cache via normal ``get_status``
        with patch.object(service, "_check_integration", return_value=status):
            service.get_status("graphhopper")

        # ``check_now`` must call ``_check_integration`` again
        updated = self._make_status("GraphHopper Routing", connected=True, latency=99.0)
        with patch.object(service, "_check_integration", return_value=updated) as mock_check:
            result = service.check_now("graphhopper")
            mock_check.assert_called_once()
            assert result["latency_ms"] == 99.0, "Must reflect fresh check data"


# ======================================================================
# Integration API endpoints
# ======================================================================


class TestIntegrationEndpoints:
    """Tests for the ``/api/v1/integrations/…`` endpoint group."""

    @pytest.fixture
    def app(self):
        from backend.api.v1.integrations import router
        from backend.dependencies import get_db
        from backend.dependencies_security import (
            get_current_user,
            require_admin,
            require_dispatcher,
        )

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        # Override DB dependency with a mock so we never hit a real
        # database during endpoint tests.
        mock_db = MagicMock()
        app.dependency_overrides[get_db] = lambda: mock_db

        # Override auth so endpoint tests succeed without real tokens.
        mock_user = {
            "id": 1, "email": "admin@test.com", "role": "admin",
            "is_admin": True, "company_id": 1,
        }
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[require_dispatcher] = lambda: mock_user
        app.dependency_overrides[require_admin] = lambda: mock_user

        yield app
        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    # ------------------------------------------------------------------
    # GET /api/v1/integrations/status
    # ------------------------------------------------------------------

    def test_get_status_endpoint(self, client):
        """GET ``/api/v1/integrations/status`` returns 200 with all integrations."""
        with patch.object(IntegrationHealthService, "_check_integration") as mock_check:
            now = datetime.now()

            def fake_check(_name, info):
                return IntegrationStatus(
                    name=info["display_name"],
                    connected=True,
                    last_check=now,
                    last_success=now,
                )

            mock_check.side_effect = fake_check

            response = client.get("/api/v1/integrations/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "integrations" in data
        assert data["total_count"] == 5
        assert data["healthy_count"] == 5

    # ------------------------------------------------------------------
    # GET /api/v1/integrations/status/{name}
    # ------------------------------------------------------------------

    def test_get_single_status(self, client):
        """GET ``/api/v1/integrations/status/graphhopper`` returns 200."""
        with patch.object(IntegrationHealthService, "_check_integration") as mock_check:
            now = datetime.now()
            mock_check.return_value = IntegrationStatus(
                name="GraphHopper Routing",
                connected=True,
                last_check=now,
                last_success=now,
            )

            response = client.get("/api/v1/integrations/status/graphhopper")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "GraphHopper Routing"
        assert data["connected"] is True

    # ------------------------------------------------------------------
    # POST /api/v1/integrations/status/{name}/check  (auth)
    # ------------------------------------------------------------------

    def test_check_requires_admin(self):
        """POST ``…/check`` returns 401 when no auth token is provided."""
        from backend.api.v1.integrations import router
        from backend.dependencies import get_db

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        mock_db = MagicMock()
        app.dependency_overrides[get_db] = lambda: mock_db
        # No auth overrides → should fail with 401
        response = TestClient(app).post(
            "/api/v1/integrations/status/graphhopper/check",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
