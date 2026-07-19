"""Tests for client.config — ClientConfig singleton and API URL resolution."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from client.config import ClientConfig, get_client_config


@pytest.fixture(autouse=True)
def _reset_global_config():
    """Reset the module-level _CONFIG singleton before each test."""
    import client.config as _cfg_mod
    _cfg_mod._CONFIG = None
    yield


# ── Singleton behavior ─────────────────────────────────────────────────


class TestClientConfigSingleton:
    def test_get_client_config_returns_instance(self):
        cfg = get_client_config()
        assert isinstance(cfg, ClientConfig)

    def test_get_client_config_returns_same_instance(self):
        cfg1 = get_client_config()
        cfg2 = get_client_config()
        assert cfg1 is cfg2

    def test_get_client_config_creates_new_after_reset(self):
        import client.config as _cfg_mod
        cfg1 = get_client_config()
        _cfg_mod._CONFIG = None
        cfg2 = get_client_config()
        assert cfg1 is not cfg2
        assert isinstance(cfg2, ClientConfig)

    def test_constructor_creates_independent_instances(self):
        """ClientConfig is not a singleton — only get_clientConfig enforces one."""
        cfg1 = ClientConfig()
        cfg2 = ClientConfig()
        assert cfg1 is not cfg2


# ── Environment resolution ──────────────────────────────────────────────


class TestClientConfigEnvironment:
    def test_default_env_is_development(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = ClientConfig()
            assert cfg.env == "development"
            assert cfg.is_production is False

    def test_production_env(self):
        with patch.dict(os.environ, {"OPERION_ENV": "production"}, clear=True):
            cfg = ClientConfig()
            assert cfg.env == "production"
            assert cfg.is_production is True

    def test_custom_env(self):
        with patch.dict(os.environ, {"OPERION_ENV": "staging"}, clear=True):
            cfg = ClientConfig()
            assert cfg.env == "staging"
            assert cfg.is_production is False

    def test_env_is_lowercased(self):
        with patch.dict(os.environ, {"OPERION_ENV": "Production"}, clear=True):
            cfg = ClientConfig()
            assert cfg.env == "production"

    def test_env_is_stripped(self):
        with patch.dict(os.environ, {"OPERION_ENV": "  development  "}, clear=True):
            cfg = ClientConfig()
            assert cfg.env == "development"


# ── API URL resolution ──────────────────────────────────────────────────


class TestClientConfigAPIURL:
    def test_development_env_var_takes_priority(self):
        with patch.dict(os.environ, {
            "OPERION_ENV": "development",
            "OPERION_API_URL": "https://custom.api.com",
        }, clear=True):
            cfg = ClientConfig()
            assert cfg.base_url == "https://custom.api.com"

    def test_development_fallback_to_production_domain(self):
        with patch.dict(os.environ, {
            "OPERION_ENV": "development",
            "OPERION_API_URL": "",
        }, clear=True):
            cfg = ClientConfig()
            # _read_fallback tries to import config.Config; if it fails it
            # returns PRODUCTION_DOMAIN
            assert cfg.base_url == "https://api.operionerp.xyz"

    def test_production_default_domain(self):
        with patch.dict(os.environ, {"OPERION_ENV": "production"}, clear=True):
            cfg = ClientConfig()
            assert cfg.base_url == ClientConfig.PRODUCTION_DOMAIN
            assert cfg.base_url == "https://api.operionerp.xyz"

    def test_production_env_var_overrides_default(self):
        with patch.dict(os.environ, {
            "OPERION_ENV": "production",
            "OPERION_API_URL": "https://prod.custom.com",
        }, clear=True):
            cfg = ClientConfig()
            assert cfg.base_url == "https://prod.custom.com"

    def test_api_url_property_matches_base_url(self):
        with patch.dict(os.environ, {"OPERION_API_URL": "https://api.test.com"}, clear=True):
            cfg = ClientConfig()
            assert cfg.api_url == "https://api.test.com"
            assert cfg.api_url is cfg.base_url


# ── SSL verification ────────────────────────────────────────────────────


class TestClientConfigSSL:
    def test_ssl_verify_false_in_development(self):
        with patch.dict(os.environ, {"OPERION_ENV": "development"}, clear=True):
            cfg = ClientConfig()
            assert cfg.verify_ssl is False

    def test_ssl_verify_true_in_production(self):
        with patch.dict(os.environ, {"OPERION_ENV": "production"}, clear=True):
            cfg = ClientConfig()
            assert cfg.verify_ssl is True

    def test_ssl_verify_false_for_staging(self):
        with patch.dict(os.environ, {"OPERION_ENV": "staging"}, clear=True):
            cfg = ClientConfig()
            assert cfg.verify_ssl is False

    def test_ssl_verify_false_when_env_blank(self):
        with patch.dict(os.environ, {"OPERION_ENV": ""}, clear=True):
            cfg = ClientConfig()
            assert cfg.verify_ssl is False


# ── Credentials from environment ────────────────────────────────────────


class TestClientConfigCredentials:
    def test_api_key_empty_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = ClientConfig()
            assert cfg.api_key == ""

    def test_api_key_from_env(self):
        with patch.dict(os.environ, {"OPERION_API_KEY": "sk-1234"}, clear=True):
            cfg = ClientConfig()
            assert cfg.api_key == "sk-1234"

    def test_admin_email_from_env(self):
        with patch.dict(os.environ, {"OPERION_ADMIN_EMAIL": "admin@example.com"}, clear=True):
            cfg = ClientConfig()
            assert cfg.admin_email == "admin@example.com"

    def test_admin_password_hash_from_env(self):
        with patch.dict(os.environ, {"OPERION_ADMIN_PASSWORD_HASH": "abc123def"}, clear=True):
            cfg = ClientConfig()
            assert cfg.admin_password_hash == "abc123def"


# ── Edge cases ──────────────────────────────────────────────────────────


class TestClientConfigEdgeCases:
    def test_all_env_vars_blank(self):
        with patch.dict(os.environ, {
            "OPERION_ENV": "",
            "OPERION_API_URL": "",
            "OPERION_API_KEY": "",
        }, clear=True):
            cfg = ClientConfig()
            assert cfg.api_key == ""
            assert cfg.base_url is not None

    def test_no_env_vars_set(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = ClientConfig()
            assert cfg.env == "development"
            assert cfg.is_production is False
            assert cfg.verify_ssl is False
            assert cfg.api_key == ""

    def test_reset_singleton_rereads_env(self):
        """After resetting _CONFIG, get_client_config() picks up new env values."""
        import client.config as _cfg_mod

        with patch.dict(os.environ, {
            "OPERION_API_URL": "https://first.url",
        }, clear=True):
            cfg1 = get_client_config()
            assert cfg1.base_url == "https://first.url"

        # Reset singleton
        _cfg_mod._CONFIG = None

        with patch.dict(os.environ, {
            "OPERION_API_URL": "https://second.url",
        }, clear=True):
            cfg2 = get_client_config()
            assert cfg2.base_url == "https://second.url"
            assert cfg2 is not cfg1

    def test_production_with_api_key(self):
        with patch.dict(os.environ, {
            "OPERION_ENV": "production",
            "OPERION_API_URL": "https://prod.example.com",
            "OPERION_API_KEY": "prod-key",
        }, clear=True):
            cfg = ClientConfig()
            assert cfg.is_production is True
            assert cfg.verify_ssl is True
            assert cfg.base_url == "https://prod.example.com"
            assert cfg.api_key == "prod-key"
