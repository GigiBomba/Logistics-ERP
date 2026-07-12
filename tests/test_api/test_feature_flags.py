"""Integration tests for the feature flag endpoints (/api/v1/feature-flags/).

GET    /api/v1/feature-flags/              — list all flags
GET    /api/v1/feature-flags/{flag_key}     — get one flag status
POST   /api/v1/feature-flags/{flag_key}/enable  — enable a flag
POST   /api/v1/feature-flags/{flag_key}/disable — disable a flag
"""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

from fastapi.testclient import TestClient

BASE = "/api/v1/feature-flags"

# A minimal FeatureFlag-like object for tests
FAKE_FLAGS = {
    "test_flag": type("FakeFlag", (), {
        "key": "test_flag",
        "description": "A test flag",
        "default": False,
        "scope": "global",
        "metadata": {},
    })(),
    "always_on": type("FakeFlag", (), {
        "key": "always_on",
        "description": "Always enabled",
        "default": True,
        "scope": "global",
        "metadata": {},
    })(),
}


class TestListFeatureFlags:
    """GET /api/v1/feature-flags/"""

    def test_list_flags_returns_flag_list(self, client):
        """Returns 200 with a list of all feature flags."""
        with patch("backend.api.v1.feature_flags.FeatureFlagService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_flags.return_value = [
                {"key": "flag_a", "description": "Flag A", "default": False, "scope": "global", "current": False},
                {"key": "flag_b", "description": "Flag B", "default": True, "scope": "company", "current": True},
            ]
            mock_svc_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/")
            assert resp.status_code == 200
            data = resp.json()
            assert "flags" in data
            assert len(data["flags"]) == 2
            assert data["flags"][0]["key"] == "flag_a"

    def test_list_flags_empty_when_no_flags(self, client):
        """Returns empty flags list when no flags are registered."""
        with patch("backend.api.v1.feature_flags.FeatureFlagService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.list_flags.return_value = []
            mock_svc_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/")
            assert resp.status_code == 200
            assert resp.json()["flags"] == []


class TestGetFeatureFlag:
    """GET /api/v1/feature-flags/{flag_key}"""

    def test_get_known_flag_returns_details(self, client):
        """Returns 200 with flag details when flag_key exists."""
        with (
            patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS),
            patch("backend.api.v1.feature_flags.FeatureFlagService") as mock_svc_cls,
        ):
            mock_svc = MagicMock()
            mock_svc.is_enabled.return_value = True
            mock_svc_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/test_flag")
            assert resp.status_code == 200
            data = resp.json()
            assert data["key"] == "test_flag"
            assert data["enabled"] is True
            assert data["description"] == "A test flag"

    def test_get_known_flag_disabled(self, client):
        """Returns enabled=False for a disabled flag."""
        with (
            patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS),
            patch("backend.api.v1.feature_flags.FeatureFlagService") as mock_svc_cls,
        ):
            mock_svc = MagicMock()
            mock_svc.is_enabled.return_value = False
            mock_svc_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/test_flag")
            assert resp.status_code == 200
            assert resp.json()["enabled"] is False

    def test_get_unknown_flag_returns_404(self, client):
        """Returns 404 when flag_key does not exist."""
        with patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS):
            resp = client.get(f"{BASE}/nonexistent_flag")
            assert resp.status_code == 404
            assert "Unknown flag" in resp.json()["detail"]

    def test_get_flag_with_company_id(self, client):
        """Passes company_id query param to is_enabled."""
        with (
            patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS),
            patch("backend.api.v1.feature_flags.FeatureFlagService") as mock_svc_cls,
        ):
            mock_svc = MagicMock()
            mock_svc.is_enabled.return_value = True
            mock_svc_cls.return_value = mock_svc

            resp = client.get(f"{BASE}/test_flag?company_id=5")
            assert resp.status_code == 200
            mock_svc.is_enabled.assert_called_once_with("test_flag", company_id=5)

    def test_get_flag_default_company_id_zero(self, client):
        """Defaults company_id=0 when not provided."""
        with (
            patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS),
            patch("backend.api.v1.feature_flags.FeatureFlagService") as mock_svc_cls,
        ):
            mock_svc = MagicMock()
            mock_svc.is_enabled.return_value = False
            mock_svc_cls.return_value = mock_svc

            client.get(f"{BASE}/test_flag")
            mock_svc.is_enabled.assert_called_once_with("test_flag", company_id=0)


class TestEnableFeatureFlag:
    """POST /api/v1/feature-flags/{flag_key}/enable"""

    def test_enable_known_flag_returns_200(self, client):
        """Returns 200 with status 'enabled' for a known flag."""
        with (
            patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS),
            patch("backend.api.v1.feature_flags.FeatureFlagService") as mock_svc_cls,
        ):
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc

            resp = client.post(f"{BASE}/test_flag/enable")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "enabled"
            assert data["flag"] == "test_flag"
            assert data["company_id"] == 0

    def test_enable_unknown_flag_returns_404(self, client):
        """Returns 404 when flag_key does not exist."""
        with patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS):
            resp = client.post(f"{BASE}/nonexistent/enable")
            assert resp.status_code == 404
            assert "Unknown flag" in resp.json()["detail"]

    def test_enable_with_company_id(self, client):
        """Passes company_id to set_override."""
        with (
            patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS),
            patch("backend.api.v1.feature_flags.FeatureFlagService") as mock_svc_cls,
        ):
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc

            resp = client.post(f"{BASE}/test_flag/enable?company_id=10")
            assert resp.status_code == 200
            mock_svc.set_override.assert_called_once_with("test_flag", True, company_id=10)
            assert resp.json()["company_id"] == 10


class TestDisableFeatureFlag:
    """POST /api/v1/feature-flags/{flag_key}/disable"""

    def test_disable_known_flag_returns_200(self, client):
        """Returns 200 with status 'disabled' for a known flag."""
        with (
            patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS),
            patch("backend.api.v1.feature_flags.FeatureFlagService") as mock_svc_cls,
        ):
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc

            resp = client.post(f"{BASE}/test_flag/disable")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "disabled"
            assert data["flag"] == "test_flag"
            assert data["company_id"] == 0

    def test_disable_unknown_flag_returns_404(self, client):
        """Returns 404 when flag_key does not exist."""
        with patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS):
            resp = client.post(f"{BASE}/nonexistent/disable")
            assert resp.status_code == 404
            assert "Unknown flag" in resp.json()["detail"]

    def test_disable_with_company_id(self, client):
        """Passes company_id to set_override."""
        with (
            patch("backend.api.v1.feature_flags.FEATURE_FLAGS", FAKE_FLAGS),
            patch("backend.api.v1.feature_flags.FeatureFlagService") as mock_svc_cls,
        ):
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc

            resp = client.post(f"{BASE}/test_flag/disable?company_id=3")
            assert resp.status_code == 200
            mock_svc.set_override.assert_called_once_with("test_flag", False, company_id=3)
            assert resp.json()["company_id"] == 3


class TestFeatureFlagAuth:
    """All feature-flag endpoints require admin auth."""

    ENDPOINTS = [
        ("GET", f"{BASE}/"),
        ("GET", f"{BASE}/test_flag"),
        ("POST", f"{BASE}/test_flag/enable"),
        ("POST", f"{BASE}/test_flag/disable"),
    ]

    def test_endpoint_returns_401_without_token(self, app):
        """All feature-flag endpoints are gated by require_admin."""
        raw_client = TestClient(app)
        for method, path in self.ENDPOINTS:
            if method == "GET":
                resp = raw_client.get(path)
            else:
                resp = raw_client.post(path)
            assert resp.status_code == 401, f"{method} {path} should return 401"
