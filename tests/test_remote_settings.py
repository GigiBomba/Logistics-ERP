"""Tests for RemoteSettingsService (client/remote_settings.py).

Mirrors the MagicMock-api pattern of tests/test_remote_wrappers.py: a fake
``api_client`` MagicMock is injected and the service methods are asserted to
pass arguments straight through to the corresponding ``ApiClient`` methods.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from client.remote_settings import (
    COMPANY_CONFIG_KEYS,
    RemoteSettingsService,
)
from services.invoicing.config_manager import DEFAULT_CONFIG


def _http_error(status_code: int, message: str | None = None) -> httpx.HTTPStatusError:
    """Build a real ``httpx.HTTPStatusError`` for the given status code."""
    request = httpx.Request("GET", "http://test.local/api/v1/settings/key")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        message or f"{status_code} Server Error",
        request=request,
        response=response,
    )


class TestRemoteSettingsService:
    @pytest.fixture
    def api(self):
        return MagicMock()

    @pytest.fixture
    def service(self, api):
        return RemoteSettingsService(api)

    # ── save_setting (thin passthrough) ─────────────────────────────

    def test_save_setting_passes_key_and_value(self, service, api):
        api.save_setting.return_value = {"status": "ok"}
        result = service.save_setting("theme", "dark")
        assert result == {"status": "ok"}
        api.save_setting.assert_called_once_with("theme", "dark")

    def test_save_setting_returns_api_response_unchanged(self, service, api):
        api.save_setting.return_value = {"value": "dark", "saved": True}
        result = service.save_setting("theme", "dark")
        assert result == {"value": "dark", "saved": True}
        api.save_setting.assert_called_once_with("theme", "dark")

    # ── get_setting (thin passthrough) ──────────────────────────────

    def test_get_setting_passes_key(self, service, api):
        api.get_setting.return_value = {"value": "dark"}
        result = service.get_setting("theme")
        assert result == {"value": "dark"}
        api.get_setting.assert_called_once_with("theme")

    def test_get_setting_returns_default_when_response_is_none(self, service, api):
        api.get_setting.return_value = None
        result = service.get_setting("theme", default="light")
        assert result == "light"
        api.get_setting.assert_called_once_with("theme")

    def test_get_setting_404_returns_default(self, service, api):
        api.get_setting.side_effect = _http_error(404)
        result = service.get_setting("missing.key", default="fallback")
        assert result == "fallback"
        api.get_setting.assert_called_once_with("missing.key")

    def test_get_setting_404_with_no_explicit_default_returns_none(self, service, api):
        api.get_setting.side_effect = _http_error(404)
        assert service.get_setting("missing.key") is None
        api.get_setting.assert_called_once_with("missing.key")

    def test_get_setting_non_404_error_propagates(self, service, api):
        api.get_setting.side_effect = _http_error(500)
        with pytest.raises(httpx.HTTPStatusError):
            service.get_setting("theme")
        api.get_setting.assert_called_once_with("theme")

    # ── get_company_config (defaults merge) ─────────────────────────

    def test_get_company_config_merges_defaults_and_filters_unknown(self, service, api):
        api.get_company_config.return_value = {
            "company_name": "ACME SRL",
            "phone": "0722000111",
            "unexpected_key": "zzz",  # not part of COMPANY_CONFIG_KEYS
        }
        result = service.get_company_config()

        expected = dict(DEFAULT_CONFIG)
        expected.update({"company_name": "ACME SRL", "phone": "0722000111"})
        assert result == expected
        # Missing server keys were filled from DEFAULT_CONFIG...
        assert result["cui"] == DEFAULT_CONFIG["cui"]
        assert result["country"] == DEFAULT_CONFIG["country"]
        # ...and unknown server keys were dropped.
        assert "unexpected_key" not in result
        assert set(result) == set(COMPANY_CONFIG_KEYS)
        api.get_company_config.assert_called_once_with()

    def test_get_company_config_returns_defaults_when_full_key_set_returned(
        self, service, api,
    ):
        server = {k: f"v{i}" for i, k in enumerate(COMPANY_CONFIG_KEYS)}
        api.get_company_config.return_value = server
        assert service.get_company_config() == server
        api.get_company_config.assert_called_once_with()

    @pytest.mark.parametrize(
        "bad_response", [None, "not-a-dict", ["company_name", "ACME"], 42],
    )
    def test_get_company_config_non_dict_response_returns_defaults(
        self, service, api, bad_response,
    ):
        api.get_company_config.return_value = bad_response
        result = service.get_company_config()
        assert result == dict(DEFAULT_CONFIG)
        assert set(result) == set(COMPANY_CONFIG_KEYS)
        api.get_company_config.assert_called_once_with()

    def test_get_company_config_returns_defaults_on_api_error(self, service, api):
        api.get_company_config.side_effect = RuntimeError("API unreachable")
        result = service.get_company_config()
        assert result == dict(DEFAULT_CONFIG)
        api.get_company_config.assert_called_once_with()

    # ── save_company_config (unknown-key filtering) ─────────────────

    def test_save_company_config_filters_payload_to_known_keys(self, service, api):
        payload = {k: f"value-{i}" for i, k in enumerate(COMPANY_CONFIG_KEYS)}
        payload["unexpected_key"] = "zzz"
        payload["another_unknown"] = {"nested": True}
        service.save_company_config(payload)

        expected = {k: f"value-{i}" for i, k in enumerate(COMPANY_CONFIG_KEYS)}
        api.save_company_config.assert_called_once_with(expected)

    def test_save_company_config_returns_api_response(self, service, api):
        api.save_company_config.return_value = {"saved": True}
        result = service.save_company_config({"company_name": "ACME SRL"})
        assert result == {"saved": True}
        api.save_company_config.assert_called_once_with({"company_name": "ACME SRL"})
