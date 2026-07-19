"""Tests for the alerts API router (``/api/v1/alerts``)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.test_api.conftest import StrippedMock

BASE = "/api/v1/alerts"


class TestAlertsRouter:
    """Alert listing, counting, and resolution endpoints."""

    # ── list ───────────────────────────────────────────────────────────────

    @patch("services.operations.operations_engine.OperationsEngine")
    @patch("services.preferences.PreferencesManager")
    def test_list_alerts_returns_200_with_items(
        self, mock_prefs_cls, mock_ops_cls, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_ops = StrippedMock()
        mock_ops_cls.return_value = mock_ops

        fake_alerts = [
            StrippedMock(id="alert-1", alert_type="maintenance",
                         message="Oil change due", status="active"),
            StrippedMock(id="alert-2", alert_type="insurance",
                         message="Insurance expires soon", status="active"),
        ]
        mock_ops.get_active_alerts.return_value = fake_alerts

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["items"][0]["id"] == "alert-1"
        assert data["items"][1]["type"] == "insurance"
        mock_ops.get_active_alerts.assert_called_once_with(limit=50)

    @patch("services.operations.operations_engine.OperationsEngine")
    @patch("services.preferences.PreferencesManager")
    def test_list_alerts_passes_limit_param(
        self, mock_prefs_cls, mock_ops_cls, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_ops = StrippedMock()
        mock_ops_cls.return_value = mock_ops
        mock_ops.get_active_alerts.return_value = []

        resp = client.get(f"{BASE}/?page_size=10")
        assert resp.status_code == 200
        mock_ops.get_active_alerts.assert_called_once_with(limit=10)

    # ── count ──────────────────────────────────────────────────────────────

    @patch("services.operations.operations_engine.OperationsEngine")
    @patch("services.preferences.PreferencesManager")
    def test_get_alert_count_returns_200(
        self, mock_prefs_cls, mock_ops_cls, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_ops = StrippedMock()
        mock_ops_cls.return_value = mock_ops
        mock_ops.get_active_alert_count.return_value = 7

        resp = client.get(f"{BASE}/count")
        assert resp.status_code == 200
        assert resp.json() == {"count": 7}

    # ── resolve ────────────────────────────────────────────────────────────

    @patch("services.operations.operations_engine.OperationsEngine")
    @patch("services.preferences.PreferencesManager")
    def test_resolve_alert_returns_200(
        self, mock_prefs_cls, mock_ops_cls, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_ops = StrippedMock()
        mock_ops_cls.return_value = mock_ops
        mock_ops.resolve_alert.return_value = StrippedMock()

        resp = client.post(f"{BASE}/alert-1/resolve")
        assert resp.status_code == 200
        assert resp.json() == {"status": "resolved"}
        mock_ops.resolve_alert.assert_called_once_with("alert-1")

    @patch("services.operations.operations_engine.OperationsEngine")
    @patch("services.preferences.PreferencesManager")
    def test_resolve_alert_returns_404_when_not_found(
        self, mock_prefs_cls, mock_ops_cls, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_ops = StrippedMock()
        mock_ops_cls.return_value = mock_ops
        mock_ops.resolve_alert.return_value = None

        resp = client.post(f"{BASE}/unknown-alert/resolve")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Alert not found"

    # ── error handling ─────────────────────────────────────────────────────

    @patch("services.operations.operations_engine.OperationsEngine")
    @patch("services.preferences.PreferencesManager")
    def test_service_exception_propagates(
        self, mock_prefs_cls, mock_ops_cls, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_ops = StrippedMock()
        mock_ops_cls.return_value = mock_ops
        mock_ops.get_active_alerts.side_effect = RuntimeError("Engine failure")

        resp = client.get(f"{BASE}/")
        assert resp.status_code == 500

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/")
        assert resp.status_code == 401
