"""F1 — process-global ``BackendSettings`` cache tests.

``backend.config.get_settings`` caches the first :class:`BackendSettings`
instance so request hot paths (auth / mfa / admin / support / security
dependencies) don't re-parse ``.env`` + OPERION_* env vars on every call.
These tests pin that contract and prove ``reload_settings`` lets
env-mutation tests refresh the cache.

The root ``tests/conftest.py`` ``reset_singletons`` autouse fixture calls
``reload_settings()`` before every test, so a test that mutated env vars
cannot poison the cache for a later test.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.config import get_settings, reload_settings
# Imported at module scope so ``backend.main`` binds the ORIGINAL
# ``BackendSettings`` class at collection time (its module-level
# ``app = create_app()`` must not pick up a per-test patch).
from backend.main import create_app

# Mirror of the credentials used by tests/test_api/test_api_auth.py
_TEST_ADMIN_EMAIL = "bonjourlol444@gmail.com"
_TEST_ADMIN_PASSWORD = "test-admin-password"
_TEST_ADMIN_HASH = "$2b$04$zcZO4.5yiIgHbo0advffsOPRpRh0hdHygnejWNc6tFpyIw0t1tg0y"


class TestSettingsCache:
    def test_get_settings_returns_same_instance(self):
        """get_settings() must return the same cached instance repeatedly."""
        reload_settings()
        assert get_settings() is get_settings()

    def test_reload_settings_refreshes_env(self, monkeypatch):
        """Env changes propagate via the fingerprint-based cache invalidation.

        ``get_settings()`` fingerprints every ``OPERION_*`` env var on each
        call and rebuilds the cached instance when the fingerprint changes, so
        a mutated env var is picked up WITHOUT an explicit reload.  The
        explicit ``reload_settings()`` path still works as before.
        """
        monkeypatch.setenv("OPERION_API_PORT", "9000")
        reload_settings()
        assert get_settings().api_port == 9000

        # The auto-invalidation fingerprint notices the env change and
        # rebuilds the cache on the next get_settings() — no reload needed.
        monkeypatch.setenv("OPERION_API_PORT", "8000")
        assert get_settings().api_port == 8000

        # reload_settings() is the explicit invalidation path and still works.
        reload_settings()
        assert get_settings().api_port == 8000

    def test_settings_constructed_at_most_once_per_request_chain(self, monkeypatch):
        """A login request touches the settings accessor 4+ times (login
        handler, _issue_tokens, _set_refresh_cookie, _store_refresh) — the
        cache must collapse those into ≤1 BackendSettings() construction.

        We patch ``backend.config.BackendSettings`` (the class the cached
        accessor instantiates) but NOT ``backend.security``'s import-by-value
        reference, so direct constructions outside the cached accessor are
        not counted — isolating the behaviour F1 is meant to change.
        """
        import backend.config as config_module
        from backend.config import BackendSettings

        monkeypatch.setenv("OPERION_ADMIN_EMAIL", _TEST_ADMIN_EMAIL)
        monkeypatch.setenv("OPERION_ADMIN_PASSWORD_HASH", _TEST_ADMIN_HASH)
        monkeypatch.setenv("OPERION_JWT_SECRET_KEY", "test-jwt-secret-key-for-testing!!")

        reload_settings()

        counter = {"n": 0}

        class _CountingSettings(BackendSettings):
            def __init__(self, *args, **kwargs):
                counter["n"] += 1
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(config_module, "BackendSettings", _CountingSettings)
        # Clear the cache so the request's first get_settings() constructs
        # through the counting class; ignore the reload() construction above.
        config_module._settings_cache = None
        counter["n"] = 0

        client = TestClient(create_app())
        resp = client.post("/api/v1/auth/token", data={
            "username": _TEST_ADMIN_EMAIL,
            "password": _TEST_ADMIN_PASSWORD,
        })
        assert resp.status_code == 200, resp.text
        assert counter["n"] <= 1, (
            f"Expected ≤1 BackendSettings() construction across the request "
            f"chain, got {counter['n']}"
        )

        # Leave a clean cache for subsequent tests (monkeypatch restores the
        # class; reload replaces any _CountingSettings instance with a real one).
        reload_settings()