"""Integration tests for the SLO/SLA endpoints.

GET /api/v1/slo/report  — detailed SLO report (admin only)
GET /api/v1/status      — public status page (no auth)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

SLO_REPORT = {
    "uptime_hours": 720.0,
    "uptime_since": "2026-01-01T00:00:00",
    "slo_metrics": {
        "api_availability": {
            "name": "api_availability",
            "target_pct": 99.9,
            "current_pct": 99.95,
            "within_target": True,
            "total_events": 10000,
            "good_events": 9995,
            "window_hours": 720,
        },
    },
    "overall_status": "healthy",
}

STATUS_PAGE = {
    "status": "healthy",
    "uptime_percentage": "99.95%",
    "services": {
        "api": {"status": "operational", "slo": "99.95% (target: 99.9%)"},
        "webhooks": {"status": "operational", "slo": "99.5%"},
        "routing": {"status": "operational", "slo": "95.0%"},
    },
    "updated_at": "2026-07-13T12:00:00",
}


class TestSloReport:
    """GET /api/v1/slo/report — admin only."""

    def test_slo_report_returns_report(self, client):
        """Returns 200 with full SLO report."""
        with patch("backend.api.v1.slo.get_slo_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.get_report.return_value = SLO_REPORT
            mock_get.return_value = mock_svc

            resp = client.get("/api/v1/slo/report")
            assert resp.status_code == 200
            data = resp.json()
            assert data["uptime_hours"] == 720.0
            assert data["overall_status"] == "healthy"
            assert "slo_metrics" in data

    def test_slo_report_degraded_status(self, client):
        """Returns 'degraded' overall_status when targets are not met."""
        degraded_report = dict(SLO_REPORT)
        degraded_report["overall_status"] = "degraded"
        degraded_report["slo_metrics"]["api_availability"]["within_target"] = False

        with patch("backend.api.v1.slo.get_slo_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.get_report.return_value = degraded_report
            mock_get.return_value = mock_svc

            resp = client.get("/api/v1/slo/report")
            assert resp.status_code == 200
            assert resp.json()["overall_status"] == "degraded"

    def test_slo_report_requires_auth(self, app):
        """Without auth token, returns 401."""
        raw_client = TestClient(app)
        resp = raw_client.get("/api/v1/slo/report")
        assert resp.status_code == 401

    def test_slo_report_empty_metrics(self, client):
        """Returns report with zero events when no data recorded."""
        empty_report = {
            "uptime_hours": 0.0,
            "uptime_since": "2026-07-13T00:00:00",
            "slo_metrics": {},
            "overall_status": "healthy",
        }
        with patch("backend.api.v1.slo.get_slo_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.get_report.return_value = empty_report
            mock_get.return_value = mock_svc

            resp = client.get("/api/v1/slo/report")
            assert resp.status_code == 200
            assert resp.json()["slo_metrics"] == {}


class TestPublicStatus:
    """GET /api/v1/status — public, no auth required."""

    def test_public_status_returns_status_page(self, client):
        """Returns 200 with public status page."""
        with patch("backend.api.v1.slo.get_slo_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.get_status_page.return_value = STATUS_PAGE
            mock_get.return_value = mock_svc

            resp = client.get("/api/v1/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert "uptime_percentage" in data
            assert "services" in data

    def test_public_status_degraded(self, client):
        """Returns degraded status page when appropriate."""
        degraded_page = dict(STATUS_PAGE)
        degraded_page["status"] = "degraded"
        degraded_page["services"]["api"]["status"] = "degraded"

        with patch("backend.api.v1.slo.get_slo_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.get_status_page.return_value = degraded_page
            mock_get.return_value = mock_svc

            resp = client.get("/api/v1/status")
            assert resp.status_code == 200
            assert resp.json()["status"] == "degraded"

    def test_public_status_no_auth_required(self, app):
        """Public status endpoint works without any authentication."""
        with patch("backend.api.v1.slo.get_slo_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.get_status_page.return_value = STATUS_PAGE
            mock_get.return_value = mock_svc
            raw_client = TestClient(app)
            resp = raw_client.get("/api/v1/status")
            assert resp.status_code == 200

    def test_public_status_response_shape(self, client):
        """Response contains expected top-level keys."""
        with patch("backend.api.v1.slo.get_slo_service") as mock_get:
            mock_svc = MagicMock()
            mock_svc.get_status_page.return_value = STATUS_PAGE
            mock_get.return_value = mock_svc

            resp = client.get("/api/v1/status")
            data = resp.json()
            assert set(data.keys()) == {"status", "uptime_percentage", "services", "updated_at"}
