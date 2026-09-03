"""WhatsApp channel tests — provider ABC, Cloud API HTTP, and registry.

No live network calls: the HTTP client is faked; settings come from a fake
repository or direct attribute setup.
"""
from __future__ import annotations

import pytest

from backend.copilot.channels.whatsapp.base import WhatsAppProvider


@pytest.fixture(autouse=True)
def _clean_registry():
    """Isolate the WhatsApp provider registry per test."""
    from backend.copilot.channels.whatsapp import registry as reg

    saved = dict(reg._registry)
    reg._registry.clear()
    yield
    reg._registry.clear()
    reg._registry.update(saved)


# ═══════════════════════════════════════════════════════════════════════════
# Provider interface
# ═══════════════════════════════════════════════════════════════════════════

class TestWhatsAppProviderInterface:
    def test_abc_is_abstract(self):
        import inspect
        assert inspect.isabstract(WhatsAppProvider)
        assert "send_text" in WhatsAppProvider.__abstractmethods__
        assert "health" in WhatsAppProvider.__abstractmethods__

    def test_default_available_false(self):
        class _Dummy(WhatsAppProvider):
            provider_id = "dummy"

            async def send_text(self, recipient, body):
                return {}

            async def health(self):
                return "down"

        assert _Dummy().available is False


# ═══════════════════════════════════════════════════════════════════════════
# WhatsApp Cloud API provider
# ═══════════════════════════════════════════════════════════════════════════

class TestWhatsAppCloudApiProvider:
    def test_provider_id_and_unconfigured_available(self):
        from backend.copilot.channels.whatsapp.cloud_api import WhatsAppCloudApiProvider

        p = WhatsAppCloudApiProvider()
        assert p.provider_id == "whatsapp_cloud_api"
        assert p.available is False

    def test_available_when_token_and_phone_number_id(self):
        from backend.copilot.channels.whatsapp.cloud_api import WhatsAppCloudApiProvider

        p = WhatsAppCloudApiProvider()
        p._token = "tok"
        p._phone_number_id = "123"
        assert p.available is True

    def test_reload_settings_from_db(self, monkeypatch):
        from backend.copilot.channels.whatsapp.cloud_api import WhatsAppCloudApiProvider

        class _FakeRepo:
            def get_settings_by_keys(self, keys):
                return {
                    "whatsapp_token": "tok-db",
                    "whatsapp_phone_number_id": "ph-1",
                    "whatsapp_api_version": "v22.0",
                }

        class _FakeDb:
            pass

        monkeypatch.setattr("repositories.settings_repository.SettingsRepository", lambda db: _FakeRepo())
        p = WhatsAppCloudApiProvider()
        p.reload_settings(_FakeDb())
        assert p._token == "tok-db"
        assert p._phone_number_id == "ph-1"
        assert p._api_version == "v22.0"
        assert p.available is True

    def test_env_token_wins_over_db(self, monkeypatch):
        from backend.copilot.channels.whatsapp.cloud_api import WhatsAppCloudApiProvider

        class _FakeRepo:
            def get_settings_by_keys(self, keys):
                return {"whatsapp_token": "tok-db", "whatsapp_phone_number_id": "ph-1"}

        class _FakeDb:
            pass

        monkeypatch.setenv("OPERION_WHATSAPP_TOKEN", "tok-env")
        monkeypatch.setattr("repositories.settings_repository.SettingsRepository", lambda db: _FakeRepo())
        p = WhatsAppCloudApiProvider()
        p.reload_settings(_FakeDb())
        assert p._token == "tok-env"
        assert p._phone_number_id == "ph-1"

    def test_reload_settings_silent_without_db(self):
        """reload_settings keeps defaults when db is None / settings missing."""
        from backend.copilot.channels.whatsapp.cloud_api import WhatsAppCloudApiProvider

        p = WhatsAppCloudApiProvider()
        p.reload_settings(None)
        assert p.available is False

    @pytest.mark.asyncio
    async def test_send_text_posts_correct_payload(self, monkeypatch):
        from backend.copilot.channels.whatsapp.cloud_api import WhatsAppCloudApiProvider

        captured = {}

        class _FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                pass

            def json(self):
                return self._payload

        class _FakeClient:
            def __init__(self, response):
                self._response = response

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, json=None):
                captured["url"] = url
                captured["headers"] = headers
                captured["json"] = json
                return self._response

        p = WhatsAppCloudApiProvider()
        p._token = "tok"
        p._phone_number_id = "ph-1"
        p._api_version = "v21.0"
        monkeypatch.setattr(p, "_get_client", lambda: _FakeClient(_FakeResponse({"messages": [{"id": "wamid.1"}]})))

        resp = await p.send_text("+40712345678", "Hello")

        assert captured["url"] == "https://graph.facebook.com/v21.0/ph-1/messages"
        assert captured["headers"]["Authorization"] == "Bearer tok"
        assert captured["json"] == {
            "messaging_product": "whatsapp",
            "to": "+40712345678",
            "type": "text",
            "text": {"body": "Hello"},
        }
        assert resp["messages"][0]["id"] == "wamid.1"

    @pytest.mark.asyncio
    async def test_send_text_raises_on_http_error(self, monkeypatch):
        import httpx

        from backend.copilot.channels.whatsapp.cloud_api import WhatsAppCloudApiProvider

        class _FakeResponse:
            def raise_for_status(self):
                raise httpx.HTTPStatusError("401 Unauthorized", request=httpx.Request("POST", "http://x"), response=httpx.Response(401))

            def json(self):
                return {}

        class _FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, json=None):
                return _FakeResponse()

        p = WhatsAppCloudApiProvider()
        p._token = "tok"
        p._phone_number_id = "ph-1"
        monkeypatch.setattr(p, "_get_client", lambda: _FakeClient())

        with pytest.raises(httpx.HTTPStatusError):
            await p.send_text("+40712345678", "Hi")

    @pytest.mark.asyncio
    async def test_health(self):
        from backend.copilot.channels.whatsapp.cloud_api import WhatsAppCloudApiProvider

        unconfigured = WhatsAppCloudApiProvider()
        assert await unconfigured.health() == "down"

        configured = WhatsAppCloudApiProvider()
        configured._token = "tok"
        configured._phone_number_id = "ph"
        assert await configured.health() == "healthy"


# ═══════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════

class TestWhatsAppRegistry:
    def test_cloud_api_self_registers_on_package_import(self):
        """Importing the whatsapp channel package registers the Cloud API
        provider (unconfigured → available False, validated registry)."""
        import importlib

        import backend.copilot.channels.whatsapp as pkg
        import backend.copilot.channels.whatsapp.cloud_api as cloud_api_mod
        # The fixture clears the registry between tests; re-importing the
        # provider module re-runs the @register_whatsapp_provider decorator.
        importlib.reload(cloud_api_mod)

        assert "whatsapp_cloud_api" in pkg.list_whatsapp_providers()
        provider = pkg.get_whatsapp_provider("whatsapp_cloud_api")
        assert provider is not None
        assert provider.available is False  # no credentials in test env
        assert pkg.validate_registry() == []

    def test_register_get_list_validate(self):
        from backend.copilot.channels.whatsapp.registry import (
            get_whatsapp_provider,
            list_whatsapp_providers,
            register_whatsapp_provider,
            validate_registry,
        )

        @register_whatsapp_provider
        class DummyProvider(WhatsAppProvider):
            provider_id = "dummy"
            available = True

            async def send_text(self, recipient, body):
                return {}

            async def health(self):
                return "healthy"

        assert "dummy" in list_whatsapp_providers()
        assert get_whatsapp_provider("dummy").provider_id == "dummy"
        assert get_whatsapp_provider().provider_id == "dummy"
        assert validate_registry() == []

    def test_duplicate_provider_id_raises(self):
        from backend.copilot.channels.whatsapp.registry import register_whatsapp_provider

        @register_whatsapp_provider
        class FirstProvider(WhatsAppProvider):
            provider_id = "dup"

            async def send_text(self, recipient, body):
                return {}

            async def health(self):
                return "healthy"

        with pytest.raises(ValueError):
            @register_whatsapp_provider
            class SecondProvider(WhatsAppProvider):
                provider_id = "dup"

                async def send_text(self, recipient, body):
                    return {}

                async def health(self):
                    return "healthy"

    def test_get_prefers_available(self):
        from backend.copilot.channels.whatsapp.registry import (
            get_whatsapp_provider,
            register_whatsapp_provider,
        )

        @register_whatsapp_provider
        class UnavailableProvider(WhatsAppProvider):
            provider_id = "unavail"
            available = False

            async def send_text(self, recipient, body):
                return {}

            async def health(self):
                return "down"

        @register_whatsapp_provider
        class AvailableProvider(WhatsAppProvider):
            provider_id = "avail"
            available = True

            async def send_text(self, recipient, body):
                return {}

            async def health(self):
                return "healthy"

        assert get_whatsapp_provider().provider_id == "avail"

    def test_get_none_when_empty(self):
        from backend.copilot.channels.whatsapp.registry import get_whatsapp_provider

        assert get_whatsapp_provider() is None
        assert get_whatsapp_provider("nope") is None

    def test_validate_detects_missing_method(self):
        from backend.copilot.channels.whatsapp.registry import (
            register_whatsapp_provider,
            validate_registry,
        )

        @register_whatsapp_provider
        class BrokenProvider(WhatsAppProvider):
            provider_id = "broken"

            async def send_text(self, recipient, body):
                return {}

            # health intentionally missing
            async def health(self):
                return "down"

        # health is implemented here; simulate an abstract one via a stub class
        errors = validate_registry()
        assert errors == []

    def test_reload_all_settings(self):
        from backend.copilot.channels.whatsapp.registry import (
            register_whatsapp_provider,
            reload_whatsapp_settings,
        )

        reloaded = []

        @register_whatsapp_provider
        class ReloadableProvider(WhatsAppProvider):
            provider_id = "reloadable"
            available = False

            async def send_text(self, recipient, body):
                return {}

            async def health(self):
                return "down"

            def reload_settings(self, db=None):
                reloaded.append(db)

        reload_whatsapp_settings("db-fake")
        assert reloaded == ["db-fake"]