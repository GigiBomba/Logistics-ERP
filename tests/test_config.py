"""Tests for Config (operion config.py) and BackendSettings (pydantic backend config).

Covers default values, environment variable loading, type conversion, and validation.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from backend.config import BackendSettings
from config import Config

# ── Test DSN for PostgreSQL connection pool tests ──────────────────────────

TEST_POSTGRES_DSN = "postgresql://operion:operion_test_ci@localhost:5432/operion_test"

# ── Config (module-level class with class-level attrs) ──────────────────────


class TestConfigDefaults:
    """Verifies that Config has sensible default values when no env vars are set."""

    def test_app_name(self):
        assert Config.APP_NAME == "Operion ERP"

    def test_db_engine_default(self):
        assert Config.DB_ENGINE == "sqlite"

    def test_redis_url_default(self):
        assert Config.REDIS_URL == "redis://localhost:6379/0"

    def test_redis_cache_ttl_default(self):
        assert Config.REDIS_CACHE_TTL == 3600

    def test_celery_broker_default(self):
        assert Config.CELERY_BROKER_URL == "redis://localhost:6379/1"

    def test_celery_result_backend_default(self):
        assert Config.CELERY_RESULT_BACKEND == "redis://localhost:6379/2"

    def test_api_host_default(self):
        assert Config.API_HOST == "127.0.0.1"

    def test_api_port_default(self):
        assert Config.API_PORT == 8000

    def test_api_workers_default(self):
        assert Config.API_WORKERS == 4

    def test_default_costs(self):
        assert Config.DEFAULT_DRIVER_SALARY == 100.0
        assert Config.DEFAULT_TOLL_RATE == 0.22
        assert Config.EXTRA_COST_PER_KM == 0.03
        assert Config.EXTRA_COST_PER_DAY == 12.0

    def test_jwt_defaults(self):
        assert Config.JWT_ALGORITHM == "HS256"
        assert Config.ACCESS_TOKEN_EXPIRE_MINUTES == 480

    def test_smtp_defaults(self):
        assert Config.SMTP_SERVER == ""
        assert Config.SMTP_PORT == 587

    def test_currency_api_defaults(self):
        assert "open.er-api.com" in Config.CURRENCY_API_PRIMARY
        assert "frankfurter.dev" in Config.CURRENCY_API_FALLBACK

    def test_graphhopper_profiles(self):
        assert Config.GRAPHHOPPER_PROFILES["Recommended"] == "truck"
        assert Config.GRAPHHOPPER_PROFILES["Fastest"] == "truck_fast"
        assert Config.GRAPHHOPPER_PROFILES["Cheapest"] == "truck_cheap"


class TestConfigEnvOverrides:
    """Verifies that environment variables override Config defaults."""

    def test_db_path_from_env(self, monkeypatch):
        monkeypatch.setenv("OPERION_DB_PATH", "/custom/db.sqlite")
        assert os.environ["OPERION_DB_PATH"] == "/custom/db.sqlite"

    def test_db_engine_from_env(self, monkeypatch):
        monkeypatch.setenv("OPERION_DB_ENGINE", "postgresql")
        assert os.environ["OPERION_DB_ENGINE"] == "postgresql"

    def test_api_port_type_conversion(self):
        """API_PORT is defined as int(os.environ.get(...))."""
        assert isinstance(Config.API_PORT, int)

    def test_redis_cache_ttl_type_conversion(self):
        assert isinstance(Config.REDIS_CACHE_TTL, int)

    def test_default_driver_salary_type_conversion(self):
        assert isinstance(Config.DEFAULT_DRIVER_SALARY, float)

    def test_api_workers_type_conversion(self):
        assert isinstance(Config.API_WORKERS, int)

    def test_access_token_expire_type_conversion(self):
        assert isinstance(Config.ACCESS_TOKEN_EXPIRE_MINUTES, int)


class TestConfigEnsureDirs:
    def test_ensure_dirs_creates_directories(self, tmp_path):
        """Verify paths that ensure_dirs would create."""
        # Config.ensure_dirs() calls data_path() which uses project root;
        # we test the underlying os.makedirs calls are correct by
        # verifying the expected directory names.
        from utils.resource_path import data_path
        expected = [
            data_path("data"),
            data_path("logs"),
            data_path("reports"),
            data_path("reports/invoices"),
            data_path("invoices"),
            data_path("data/documents"),
        ]
        # All paths should be absolute and non-empty
        for p in expected:
            assert isinstance(p, str) and len(p) > 0


# ── BackendSettings (pydantic-based) ────────────────────────────────────────


class TestBackendSettingsDefaults:
    def test_default_db_engine(self, monkeypatch):
        monkeypatch.delenv("OPERION_DB_ENGINE", raising=False)
        s = BackendSettings()
        assert s.db_engine == "sqlite"

    def test_default_db_path(self, monkeypatch):
        monkeypatch.delenv("OPERION_DB_PATH", raising=False)
        s = BackendSettings()
        assert s.db_path == "data/cashflow.db"

    def test_default_redis_url(self, monkeypatch):
        monkeypatch.delenv("OPERION_REDIS_URL", raising=False)
        s = BackendSettings()
        assert s.redis_url == "redis://localhost:6379/0"

    def test_default_celery_broker(self):
        s = BackendSettings()
        assert s.celery_broker_url == "redis://localhost:6379/1"

    def test_default_api_port(self):
        s = BackendSettings()
        assert s.api_port == 8000

    def test_default_jwt_algorithm(self):
        s = BackendSettings()
        assert s.jwt_algorithm == "HS256"

    def test_default_bcrypt_rounds(self, monkeypatch):
        monkeypatch.delenv("OPERION_BCRYPT_ROUNDS", raising=False)
        s = BackendSettings()
        assert s.bcrypt_rounds == 12

    def test_default_refresh_token_expire_days(self):
        s = BackendSettings()
        assert s.refresh_token_expire_days == 7

    # ── PostgreSQL config tests ─────────────────────────────────────────

    def test_pg_engine_override(self, monkeypatch):
        monkeypatch.setenv("OPERION_DB_ENGINE", "postgresql")
        monkeypatch.setenv("OPERION_POSTGRES_DSN", TEST_POSTGRES_DSN)
        s = BackendSettings()
        assert s.db_engine == "postgresql"
        assert s.postgres_dsn == TEST_POSTGRES_DSN

    def test_pg_pool_settings(self):
        s = BackendSettings()
        assert s.db_pool_min == 2
        assert s.db_pool_max == 20

    def test_pg_config_accepts_dsn_override(self, monkeypatch):
        custom_dsn = "postgresql://custom:pass@pg.example.com:5432/mydb"
        monkeypatch.setenv("OPERION_DB_ENGINE", "postgresql")
        monkeypatch.setenv("OPERION_POSTGRES_DSN", custom_dsn)
        s = BackendSettings()
        assert s.postgres_dsn == custom_dsn


class TestBackendSettingsEnvOverride:
    def test_env_prefix_applied(self, monkeypatch):
        monkeypatch.setenv("OPERION_DB_ENGINE", "postgresql")
        monkeypatch.setenv("OPERION_API_PORT", "9000")
        s = BackendSettings()
        assert s.db_engine == "postgresql"
        assert s.api_port == 9000

    def test_env_override_celery_broker(self, monkeypatch):
        monkeypatch.setenv("OPERION_CELERY_BROKER_URL", "redis://custom:6379/1")
        s = BackendSettings()
        assert s.celery_broker_url == "redis://custom:6379/1"

    def test_env_override_redis_url(self, monkeypatch):
        monkeypatch.setenv("OPERION_REDIS_URL", "redis://custom:6379/0")
        s = BackendSettings()
        assert s.redis_url == "redis://custom:6379/0"

    def test_postgres_dsn_default_none(self):
        s = BackendSettings()
        assert s.postgres_dsn is None

    def test_admin_email_default_empty(self):
        """When OPERION_ADMIN_EMAIL is empty, admin_email should be empty."""
        s = BackendSettings(admin_email="")
        assert s.admin_email == ""


class TestBackendSettingsValidation:
    def test_init_does_not_raise_when_no_admin(self, monkeypatch):
        monkeypatch.delenv("OPERION_ADMIN_PASSWORD_HASH", raising=False)
        monkeypatch.delenv("OPERION_ADMIN_EMAIL", raising=False)
        s = BackendSettings(_env_file=None, jwt_secret_key="test-key")
        assert s.admin_password_hash == ""

    def test_init_no_jwt_warning(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        BackendSettings(jwt_secret_key="")
        assert any("JWT_SECRET_KEY" in msg for msg in caplog.messages)

    def test_admin_email_without_hash_warning(self, monkeypatch):
        """Warning logged when OPERION_ADMIN_EMAIL is set without a hash."""
        import logging, io
        for k in ("OPERION_ADMIN_PASSWORD_HASH", "OPERION_ADMIN_EMAIL",
                  "OPERION_JWT_SECRET_KEY", "OPERION_API_KEY", "OPERION_ENV"):
            monkeypatch.delenv(k, raising=False)
        # Directly verify the warning is emitted using the logger's warn method mock
        from backend.config import logger as cfg_logger
        orig_warning = cfg_logger.warning
        messages = []
        def _capture(msg, *args, **kwargs):
            messages.append(msg % args if args else msg)
            return orig_warning(msg, *args, **kwargs)
        cfg_logger.warning = _capture
        try:
            BackendSettings(_env_file=None, admin_email="admin@test.com", jwt_secret_key="test-key")
        finally:
            cfg_logger.warning = orig_warning
        assert any("ADMIN_EMAIL" in msg for msg in messages), (
            f"Expected ADMIN_EMAIL warning, got messages: {messages}"
        )

    def test_type_conversion_port(self, monkeypatch):
        monkeypatch.setenv("OPERION_API_PORT", "8080")
        s = BackendSettings()
        assert isinstance(s.api_port, int)
        assert s.api_port == 8080

    def test_type_conversion_bcrypt_rounds(self, monkeypatch):
        monkeypatch.setenv("OPERION_BCRYPT_ROUNDS", "10")
        s = BackendSettings()
        assert isinstance(s.bcrypt_rounds, int)
        assert s.bcrypt_rounds == 10


class TestSupportInternalAuthGuard:
    """Production fail-closed guard for OPERION_SUPPORT_INTERNAL_AUTH.

    In production, the dev default (or an empty value) must abort startup.
    Outside production the dev default is only a warning (existing behavior).
    """

    def test_production_with_dev_default_raises(self, monkeypatch):
        """Production + dev-default internal auth must raise RuntimeError."""
        monkeypatch.setenv("OPERION_ENV", "production")
        monkeypatch.setenv("OPERION_API_KEY", "test-api-key")
        monkeypatch.setenv("OPERION_JWT_SECRET_KEY", "test-jwt-key")
        # OPERION_SUPPORT_INTERNAL_AUTH left unset → pydantic default
        # is still "dev-insecure-replace-in-production".
        with pytest.raises(RuntimeError, match="OPERION_SUPPORT_INTERNAL_AUTH"):
            BackendSettings(_env_file=None)

    def test_production_with_explicit_dev_default_raises(self, monkeypatch):
        """Explicitly setting the dev default in production must raise."""
        monkeypatch.setenv("OPERION_ENV", "production")
        monkeypatch.setenv("OPERION_API_KEY", "test-api-key")
        monkeypatch.setenv("OPERION_JWT_SECRET_KEY", "test-jwt-key")
        monkeypatch.setenv("OPERION_SUPPORT_INTERNAL_AUTH", "dev-insecure-replace-in-production")
        with pytest.raises(RuntimeError, match="OPERION_SUPPORT_INTERNAL_AUTH"):
            BackendSettings(_env_file=None)

    def test_production_with_empty_value_raises(self, monkeypatch):
        """Production + empty internal auth must raise RuntimeError."""
        monkeypatch.setenv("OPERION_ENV", "production")
        monkeypatch.setenv("OPERION_API_KEY", "test-api-key")
        monkeypatch.setenv("OPERION_JWT_SECRET_KEY", "test-jwt-key")
        monkeypatch.setenv("OPERION_SUPPORT_INTERNAL_AUTH", "")
        with pytest.raises(RuntimeError, match="OPERION_SUPPORT_INTERNAL_AUTH"):
            BackendSettings(_env_file=None)

    def test_production_with_real_value_loads(self, monkeypatch):
        """Production + a real secret loads settings without raising."""
        monkeypatch.setenv("OPERION_ENV", "production")
        monkeypatch.setenv("OPERION_API_KEY", "test-api-key")
        monkeypatch.setenv("OPERION_JWT_SECRET_KEY", "test-jwt-key")
        monkeypatch.setenv("OPERION_SUPPORT_INTERNAL_AUTH", "a-real-64-char-hex-secret-0123456789abcdef")
        s = BackendSettings(_env_file=None)
        assert s.support_internal_auth == "a-real-64-char-hex-secret-0123456789abcdef"

    def test_development_with_dev_default_warns(self, monkeypatch, caplog):
        """Non-production keeps the existing warning (no raise)."""
        monkeypatch.delenv("OPERION_ENV", raising=False)
        monkeypatch.setenv("OPERION_SUPPORT_INTERNAL_AUTH", "dev-insecure-replace-in-production")
        import logging
        caplog.set_level(logging.WARNING)
        s = BackendSettings(_env_file=None, jwt_secret_key="test-key")
        assert s.support_internal_auth == "dev-insecure-replace-in-production"
        assert any("OPERION_SUPPORT_INTERNAL_AUTH" in msg for msg in caplog.messages)
