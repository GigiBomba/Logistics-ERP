"""Tests for API endpoint conventions and health probes.

Covers PATCH conventions, response format standards, health/liveness/readiness
probes, Prometheus metrics, and the public status page.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# ── Routers under test ────────────────────────────────────────────────
# The production app nests these under ``api_v1_router(prefix="/api/v1")``.
# When we include routers directly in a test app, their own prefixes apply
# (/clients, /health, /trips, …).
from backend.api.v1 import clients, trips, health, analytics
from backend.api.v1.slo import router as slo_router
from backend.api.v1.metrics import router as metrics_router

# ── Dependencies that need overriding ─────────────────────────────────
from backend.dependencies import (
    get_db,
    get_client_service,
    get_trip_service,
    get_analytics_service,
)
from backend.dependencies_security import (
    get_current_user,
    require_admin,
    require_dispatcher,
    require_manager,
)


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════

def _build_app(routers, overrides=None):
    """Build a minimal FastAPI test app with the given routers.

    Parameters
    ----------
    routers : list of APIRouter
        Routers to include in the app.
    overrides : dict, optional
        Mapping of dependency callable → mock instance.
        Callable overrides (lambdas/functions) are used as-is.
    """
    app = FastAPI()
    for router in routers:
        app.include_router(router)
    if overrides:
        for dep, mock in overrides.items():
            if callable(mock) and not isinstance(mock, MagicMock):
                # Already a callable — use directly (e.g. a raising lambda)
                app.dependency_overrides[dep] = mock
            else:
                # Non-callable — wrap in a lambda that returns it
                app.dependency_overrides[dep] = lambda m=mock: m
    return app


# ═══════════════════════════════════════════════════════════════════════
#  Shared mock objects
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.conn.execute.return_value.fetchone.return_value = (1,)
    return db


@pytest.fixture
def mock_db_down():
    db = MagicMock()
    db.execute.side_effect = RuntimeError("Connection refused")
    return db


@pytest.fixture
def admin_user():
    return {"id": 1, "email": "admin@test.com", "role": "admin",
            "is_admin": True, "company_id": 0}


@pytest.fixture
def dispatcher_user():
    return {"id": 2, "email": "disp@test.com", "role": "dispatcher",
            "is_admin": False, "company_id": 1}


@pytest.fixture
def auth_overrides(dispatcher_user):
    """Convenience dict of auth dependency overrides for a dispatcher."""
    return {
        get_current_user: dispatcher_user,
        require_dispatcher: dispatcher_user,
        require_admin: dispatcher_user,
        require_manager: dispatcher_user,
    }


# ═══════════════════════════════════════════════════════════════════════
#  PATCH convention
# ═══════════════════════════════════════════════════════════════════════

class TestPatchConvention:
    """PATCH endpoints should exist, accept partial updates, and return 200."""

    @pytest.fixture
    def app_client(self, mock_db, dispatcher_user):
        """TestClient with mocked auth + services for clients & trips."""
        svc_client = MagicMock()
        svc_client.update.return_value = None

        svc_trip = MagicMock()
        svc_trip.update.return_value = MagicMock(success=True)

        app = _build_app(
            [clients.router, trips.router],
            overrides={
                get_db: mock_db,
                get_current_user: dispatcher_user,
                require_dispatcher: dispatcher_user,
                require_admin: dispatcher_user,
                require_manager: dispatcher_user,
                get_client_service: svc_client,
                get_trip_service: svc_trip,
            },
        )
        return TestClient(app), {"client_service": svc_client, "trip_service": svc_trip}

    # ── PATCH clients ──────────────────────────────────────────────

    def test_patch_client_exists(self, app_client):
        """PATCH /clients/{id} returns 200."""
        client, mocks = app_client
        resp = client.patch("/clients/1", json={"name": "Updated"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}

    def test_put_client_deprecated(self, app_client):
        """PUT /clients/{id} returns 200 with Deprecation header.

        The PUT endpoint is marked ``deprecated=True`` and includes
        ``Deprecation`` and ``Sunset`` response headers.
        """
        client, mocks = app_client
        resp = client.put("/clients/1", json={"name": "Full update"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}
        # Verify deprecation signalling headers
        assert resp.headers.get("deprecation", "").lower() == "true"
        sunset = resp.headers.get("sunset", "")
        assert "2027" in sunset, f"Expected sunset header with year 2027, got: {sunset}"

    # ── PATCH trips ────────────────────────────────────────────────

    def test_patch_trip_exists(self, app_client):
        """PATCH /trips/{id} works and returns 200."""
        client, mocks = app_client
        resp = client.patch("/trips/1", json={"status": "completed"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "updated"}

    def test_patch_endpoints_accept_partial_data(self, app_client):
        """Partial update — endpoint accepts requests with only some fields."""
        client, mocks = app_client

        resp = client.patch("/clients/42", json={"phone": "+49-30-987654"})
        assert resp.status_code == 200

        resp = client.patch("/trips/7", json={"notes": "Please expedite"})
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
#  Response format
# ═══════════════════════════════════════════════════════════════════════

class TestResponseFormat:
    """Response bodies and headers follow documented conventions."""

    def test_paginated_response_structure(self, mock_db, auth_overrides):
        """List endpoints return items/total/page/page_size/total_pages."""
        svc = MagicMock()
        svc.get_all.return_value = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]

        overrides = {get_db: mock_db, get_client_service: svc, **auth_overrides}
        app = _build_app([clients.router], overrides=overrides)
        client = TestClient(app)

        resp = client.get("/clients/")
        assert resp.status_code == 200
        data = resp.json()

        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)

    def test_response_includes_content_type_json(self, mock_db, auth_overrides):
        """Successful responses include Content-Type: application/json."""
        svc = MagicMock()
        svc.get_all.return_value = []

        overrides = {get_db: mock_db, get_client_service: svc, **auth_overrides}
        app = _build_app([clients.router], overrides=overrides)
        client = TestClient(app)

        resp = client.get("/clients/")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct

    def test_error_response_has_error_code(self):
        """Error responses include an error_code field.

        Auth-protected endpoints that raise ``HTTPException`` with a dict
        detail surface ``error_code`` inside the JSON body.
        """
        # Use the SLO report endpoint without overriding auth →
        # ``require_admin`` raises 403 with ``error_code`` in the detail.
        app = _build_app([slo_router])
        client = TestClient(app)

        resp = client.get("/slo/report")
        # Without a valid JWT, ``get_current_user`` returns 401 via the
        # OAuth2PasswordBearer flow.  FastAPI's default 401 body is
        # {"detail": "Not authenticated"} — no error_code.
        #
        # To see the ``error_code`` field we need a non-admin user that
        # passes ``get_current_user`` but fails ``require_admin``.
        non_admin = {"id": 2, "email": "user@test.com", "role": "dispatcher",
                     "is_admin": False, "company_id": 1}

        app2 = _build_app(
            [slo_router],
            overrides={
                get_current_user: non_admin,
                # require_admin is not overridden — it will run the real
                # implementation which checks the user role.
                # But the real require_admin needs a db connection to
                # resolve its own dependency (get_current_user is already
                # overridden, so it receives non_admin).
            },
        )
        client2 = TestClient(app2)
        resp2 = client2.get("/slo/report")
        assert resp2.status_code == 403
        body = resp2.json()
        # The 403 detail dict includes error_code
        detail = body.get("detail", body)
        assert isinstance(detail, dict), f"Expected dict detail, got: {body}"
        assert "error_code" in detail, f"Missing error_code in {body}"

    def test_date_params_standardized(self, mock_db, auth_overrides):
        """Analytics endpoints accept date_from/date_to query parameters."""
        svc = MagicMock()
        svc.get_financial.return_value = {}

        overrides = {get_db: mock_db, get_analytics_service: svc, **auth_overrides}
        app = _build_app([analytics.router], overrides=overrides)
        client = TestClient(app)

        resp = client.get(
            "/analytics/financial",
            params={"date_from": "2025-01-01", "date_to": "2025-12-31"},
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
#  Health probes
# ═══════════════════════════════════════════════════════════════════════

class TestHealthProbes:
    """Liveness, readiness, and legacy health endpoints."""

    @pytest.fixture
    def health_app(self, mock_db):
        return _build_app([health.router], overrides={get_db: mock_db})

    @pytest.fixture
    def health_app_db_down(self, mock_db_down):
        return _build_app([health.router], overrides={get_db: mock_db_down})

    def test_liveness_probe(self):
        """GET /health/live returns 200 with {"status": "alive"}."""
        app = _build_app([health.router])
        client = TestClient(app)
        resp = client.get("/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    def test_readiness_probe(self, health_app):
        """GET /health/ready returns 200 when DB is up."""
        client = TestClient(health_app)
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] == "ok"

    def test_readiness_probe_db_down(self, health_app_db_down):
        """GET /health/ready returns 503 when DB is down."""
        client = TestClient(health_app_db_down)
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "not_ready"
        assert "error" in data["checks"]["database"]

    def test_health_legacy_endpoint(self, health_app):
        """GET /health/ still works (legacy combined endpoint)."""
        client = TestClient(health_app)
        resp = client.get("/health/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"
        assert data["database"] == "connected"

    def test_probes_skip_auth(self):
        """Health endpoints are accessible without any API key or token.

        None of the health endpoints have a ``Depends(get_current_user)``
        so they must return 200 without any auth headers.
        """
        app = _build_app([health.router])
        client = TestClient(app)

        # Live probe — no dependencies at all
        resp = client.get("/health/live")
        assert resp.status_code == 200

        # Ready probe — depends on DB but not auth
        resp = client.get("/health/ready")
        # DB might not be reachable in test, but it should be either 200 or 503
        assert resp.status_code in (200, 503)

        # Legacy health — depends on DB but not auth
        resp = client.get("/health/")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
#  Metrics
# ═══════════════════════════════════════════════════════════════════════

class TestMetrics:
    """Prometheus metrics endpoint (/metrics)."""

    def test_metrics_endpoint(self):
        """GET /metrics returns Prometheus-format text."""
        admin = {"id": 1, "email": "admin@test.com", "role": "admin",
                 "is_admin": True, "company_id": 0}
        app = _build_app([metrics_router], overrides={require_admin: admin})
        client = TestClient(app)
        resp = client.get("/metrics")
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "text/plain" in ct or "application/openmetrics-text" in ct

    def test_metrics_includes_http_counter(self):
        """Metrics output includes the operion_http_requests_total counter."""
        admin = {"id": 1, "email": "admin@test.com", "role": "admin",
                 "is_admin": True, "company_id": 0}
        app = _build_app([metrics_router], overrides={require_admin: admin})
        client = TestClient(app)

        # Issue a request first so the counter is registered
        client.get("/metrics")

        resp = client.get("/metrics")
        text = resp.text
        assert "operion_http_requests_total" in text


# ═══════════════════════════════════════════════════════════════════════
#  Status page & SLO report
# ═══════════════════════════════════════════════════════════════════════

class TestStatusAndSLO:
    """Public status page and admin-only SLO report."""

    def test_status_page_public(self):
        """GET /status returns 200 with a public status format.

        The endpoint has no auth dependency and is publicly accessible.
        The ``get_slo_service()`` dependency is patched to return a mock
        because the stub implementation (``AppState``) lacks
        ``get_status_page()``.
        """
        mock_slo = MagicMock()
        mock_slo.get_status_page.return_value = {"status": "operational"}

        with patch("backend.api.v1.slo.get_slo_service", return_value=mock_slo):
            app = _build_app([slo_router])
            client = TestClient(app)
            resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_slo_report_admin_only(self):
        """GET /slo/report requires admin authentication.

        Without an admin user, the endpoint returns 401 (no token) or
        403 (non-admin token).
        """
        mock_slo = MagicMock()
        mock_slo.get_report.return_value = {"status": "ok", "uptime": 0, "services": {}}

        # -- Scenario 1: no auth at all → 401 --
        with patch("backend.api.v1.slo.get_slo_service", return_value=mock_slo):
            app_no_auth = _build_app([slo_router])
            client = TestClient(app_no_auth)
            resp = client.get("/slo/report")
        assert resp.status_code in (401, 403)

        # -- Scenario 2: non-admin user → 403 --
        non_admin = {"id": 2, "email": "user@test.com", "role": "dispatcher",
                     "is_admin": False, "company_id": 1}
        with patch("backend.api.v1.slo.get_slo_service", return_value=mock_slo):
            app_non_admin = _build_app(
                [slo_router],
                overrides={
                    get_current_user: non_admin,
                    # Keep real require_admin so it checks the role
                },
            )
            client = TestClient(app_non_admin)
            resp = client.get("/slo/report")
            assert resp.status_code == 403
            body = resp.json()
            detail = body.get("detail", body)
            if isinstance(detail, dict):
                assert "error_code" in detail
