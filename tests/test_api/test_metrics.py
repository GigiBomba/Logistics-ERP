"""Integration tests for the Prometheus metrics endpoint.

GET /api/v1/metrics — Prometheus metrics (admin only)

NOTE: The ``metrics`` router is **not** included in the main ``api_v1_router``,
so we build a minimal test app that mounts the metrics router directly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.metrics import router as metrics_router
from backend.dependencies_security import get_current_user, require_admin

MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}

from fastapi import Response as FastapiResponse

SAMPLE_METRICS_BODY = """# HELP operion_http_requests_total Total HTTP requests
# TYPE operion_http_requests_total counter
operion_http_requests_total{method="GET",endpoint="/api/v1/health",status="200"} 42.0
"""


def _make_client(extra_overrides=None):
    """Build a TestClient with auth overrides and the metrics router."""
    app = FastAPI()
    app.include_router(metrics_router, prefix="/api/v1")
    app.debug = False  # ensure errors are caught and return 500
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[require_admin] = lambda: MOCK_USER
    if extra_overrides:
        app.dependency_overrides.update(extra_overrides)
    return TestClient(app)


class TestMetricsEndpoint:
    """GET /api/v1/metrics"""

    def test_metrics_returns_prometheus_text(self):
        """Returns 200 with Prometheus-formatted text."""
        client = _make_client()
        metrics_response = FastapiResponse(
            content=SAMPLE_METRICS_BODY,
            media_type="text/plain; charset=utf-8",
        )
        with patch("backend.api.v1.metrics.get_metrics_response", return_value=metrics_response):
            resp = client.get("/api/v1/metrics")
            assert resp.status_code == 200
            assert "operion_http_requests_total" in resp.text

    def test_metrics_content_type(self):
        """Response has the correct Prometheus content type."""
        client = _make_client()
        metrics_response = FastapiResponse(
            content=SAMPLE_METRICS_BODY,
            media_type="text/plain; charset=utf-8",
        )
        with patch("backend.api.v1.metrics.get_metrics_response", return_value=metrics_response):
            resp = client.get("/api/v1/metrics")
            assert resp.headers.get("content-type", "").startswith("text/plain")

    def test_metrics_includes_multiple_metric_families(self):
        """Response includes common Prometheus metric families."""
        multi_metrics = FastapiResponse(
            content="""# HELP operion_http_requests_total Total HTTP requests
# TYPE operion_http_requests_total counter
operion_http_requests_total{method="GET",endpoint="/health",status="200"} 100.0
# HELP operion_trips_created_total Total trips created
# TYPE operion_trips_created_total counter
operion_trips_created_total 50.0
# HELP operion_db_connections Number of active database connections
# TYPE operion_db_connections gauge
operion_db_connections 5.0
""",
            media_type="text/plain; charset=utf-8",
        )
        client = _make_client()
        with patch("backend.api.v1.metrics.get_metrics_response", return_value=multi_metrics):
            resp = client.get("/api/v1/metrics")
            assert "operion_http_requests_total" in resp.text
            assert "operion_trips_created_total" in resp.text
            assert "operion_db_connections" in resp.text

    def test_metrics_returns_500_when_generation_fails(self):
        """Propagates errors from get_metrics_response."""
        import pytest
        client = _make_client()
        with patch("backend.api.v1.metrics.get_metrics_response", side_effect=RuntimeError("Metrics generation failed")):
            with pytest.raises(RuntimeError, match="Metrics generation failed"):
                client.get("/api/v1/metrics")

    def test_metrics_empty_response(self):
        """Returns empty Prometheus output when no data collected."""
        client = _make_client()
        empty_metrics = FastapiResponse(content="", media_type="text/plain; charset=utf-8")
        with patch("backend.api.v1.metrics.get_metrics_response", return_value=empty_metrics):
            resp = client.get("/api/v1/metrics")
            assert resp.status_code == 200
            assert resp.text == ""

    def test_metrics_requires_auth(self):
        """Without auth token, returns 401."""
        app = FastAPI()
        app.include_router(metrics_router, prefix="/api/v1")
        raw_client = TestClient(app)
        resp = raw_client.get("/api/v1/metrics")
        assert resp.status_code == 401
