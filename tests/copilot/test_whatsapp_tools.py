"""WhatsApp automation tool tests (§21 Ph.4 item 3).

Covers: registration + flags, graceful unconfigured error, configured send
success/failure with the correct provider payload, validation, and i18n key
presence in all 22 language files.
"""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock

import pytest

from backend.copilot.schemas import ConfirmationLevel, SessionContext
from backend.copilot.tools.base import ToolExecutionContext


def _ctx():
    return ToolExecutionContext(
        company_id=1,
        user_id=1,
        role="manager",
        session_context=SessionContext(),
        services={},
    )


def _params(**overrides):
    from backend.copilot.tools.whatsapp_tools import SendMessageParams

    base = {
        "recipient": "+40712345678",
        "body": "Hello from Operion",
        "confirmation_phrase": "CONFIRM",
    }
    base.update(overrides)
    return SendMessageParams(**base)


class _FakeProvider:
    """Configured provider stand-in recording send_text calls."""

    provider_id = "whatsapp_cloud_api"
    available = True

    def __init__(self, response=None, error=None):
        self.response = response or {"messages": [{"id": "wamid.test.1"}]}
        self.error = error
        self.calls = []

    async def send_text(self, recipient, body):
        self.calls.append((recipient, body))
        if self.error:
            raise self.error
        return self.response


class TestWhatsAppSendMessageTool:
    def test_tool_registered_with_correct_flags(self):
        from backend.copilot.tools.registry import get_tool

        tool = get_tool("whatsapp.send_message")
        assert tool is not None
        assert tool.description == "Send a WhatsApp message to a recipient phone number"
        assert tool.required_permission == "whatsapp:send"
        assert tool.confirmation_level == ConfirmationLevel.DESTRUCTIVE
        assert tool.supports_undo is False
        assert tool.supports_pause is False
        assert tool.supports_resume is False
        assert tool.long_running is False

    @pytest.mark.asyncio
    async def test_unconfigured_provider_returns_graceful_key(self, monkeypatch):
        from backend.copilot.tools.registry import get_tool
        from backend.copilot.tools.whatsapp_tools import WhatsAppSendMessageTool

        class _Unconfigured:
            provider_id = "whatsapp_cloud_api"
            available = False

        monkeypatch.setattr(
            "backend.copilot.channels.whatsapp.registry.get_whatsapp_provider",
            lambda *a, **k: _Unconfigured(),
        )
        tool = get_tool("whatsapp.send_message")
        result = await tool.execute(_params(), _ctx())
        assert result.status == "unavailable"
        assert result.message_key == "copilot.whatsapp.error.not_configured"
        assert result.data is None  # never a crash, no provider side-effect

    @pytest.mark.asyncio
    async def test_no_provider_registered_returns_graceful_key(self, monkeypatch):
        from backend.copilot.tools.registry import get_tool

        monkeypatch.setattr(
            "backend.copilot.channels.whatsapp.registry.get_whatsapp_provider",
            lambda *a, **k: None,
        )
        tool = get_tool("whatsapp.send_message")
        result = await tool.execute(_params(), _ctx())
        assert result.status == "unavailable"
        assert result.message_key == "copilot.whatsapp.error.not_configured"

    @pytest.mark.asyncio
    async def test_configured_send_success(self, monkeypatch):
        from backend.copilot.tools.registry import get_tool

        provider = _FakeProvider()
        monkeypatch.setattr(
            "backend.copilot.channels.whatsapp.registry.get_whatsapp_provider",
            lambda *a, **k: provider,
        )
        tool = get_tool("whatsapp.send_message")
        result = await tool.execute(_params(), _ctx())

        assert result.status == "success"
        assert result.message_key == "copilot.tool.whatsapp.send_ok"
        assert result.message_params == {"recipient": "+40712345678"}
        assert result.data["provider_message_id"] == "wamid.test.1"
        assert provider.calls == [("+40712345678", "Hello from Operion")]

    @pytest.mark.asyncio
    async def test_send_failure_returns_failed_key(self, monkeypatch):
        from backend.copilot.tools.registry import get_tool

        provider = _FakeProvider(error=RuntimeError("provider boom"))
        monkeypatch.setattr(
            "backend.copilot.channels.whatsapp.registry.get_whatsapp_provider",
            lambda *a, **k: provider,
        )
        tool = get_tool("whatsapp.send_message")
        result = await tool.execute(_params(), _ctx())

        assert result.status == "failed"
        assert result.message_key == "copilot.tool.whatsapp.send_failed"
        assert result.data == {"recipient": "+40712345678", "status": "failed"}

    @pytest.mark.asyncio
    async def test_configured_send_uses_sanitized_body(self, monkeypatch):
        from backend.copilot.tools.registry import get_tool

        provider = _FakeProvider()
        monkeypatch.setattr(
            "backend.copilot.channels.whatsapp.registry.get_whatsapp_provider",
            lambda *a, **k: provider,
        )
        tool = get_tool("whatsapp.send_message")
        await tool.execute(_params(body="  Hello   world  "), _ctx())
        # sanitize_free_text collapses whitespace / strips control chars.
        sent_body = provider.calls[0][1]
        assert "<script>" not in sent_body
        assert "  " not in sent_body

    @pytest.mark.asyncio
    async def test_validate_invalid_phone(self):
        from backend.copilot.tools.whatsapp_tools import WhatsAppSendMessageTool

        tool = WhatsAppSendMessageTool()
        errors = await tool.validate(_params(recipient="not-a-phone"), _ctx())
        assert len(errors) == 1
        assert "Invalid phone number" in errors[0]

    @pytest.mark.asyncio
    async def test_validate_valid_phone_and_body(self):
        from backend.copilot.tools.whatsapp_tools import WhatsAppSendMessageTool

        tool = WhatsAppSendMessageTool()
        errors = await tool.validate(_params(), _ctx())
        assert errors == []


class TestWhatsAppI18n:
    """The new message keys exist in ALL 22 language files with matching
    placeholders (the translation-integrity suite enforces this globally; these
    tests pin the whatsapp keys specifically)."""

    TRANSLATIONS_DIR = os.path.join(
        os.path.dirname(__file__), "..", "..", "data", "translations"
    )
    REQUIRED_KEYS = {
        "copilot.whatsapp.error.not_configured",
        "copilot.tool.whatsapp.send_ok",
        "copilot.tool.whatsapp.send_failed",
        "copilot.tool.progress.validating",
        "copilot.tool.progress.executing",
        "copilot.tool.progress.succeeded",
        "copilot.tool.progress.failed",
    }

    @staticmethod
    def _flatten(d, prefix=""):
        items = {}
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(TestWhatsAppI18n._flatten(v, key))
            else:
                items[key] = v
        return items

    def test_keys_present_in_all_language_files(self):
        special = {"de_translation_map.json", "missing_translations.json"}
        files = sorted(
            f for f in os.listdir(self.TRANSLATIONS_DIR)
            if f.endswith(".json") and f not in special
        )
        assert len(files) >= 22
        for fname in files:
            with open(os.path.join(self.TRANSLATIONS_DIR, fname), encoding="utf-8-sig") as f:
                flat = self._flatten(json.load(f))
            missing = self.REQUIRED_KEYS - set(flat.keys())
            assert not missing, f"{fname} missing: {missing}"
            empty = [k for k in self.REQUIRED_KEYS if not str(flat[k]).strip()]
            assert not empty, f"{fname} empty values: {empty}"

    def test_placeholders_consistent(self):
        special = {"de_translation_map.json", "missing_translations.json"}
        with open(os.path.join(self.TRANSLATIONS_DIR, "en.json"), encoding="utf-8-sig") as f:
            en_flat = self._flatten(json.load(f))
        for fname in sorted(os.listdir(self.TRANSLATIONS_DIR)):
            if not fname.endswith(".json") or fname in special:
                continue
            with open(os.path.join(self.TRANSLATIONS_DIR, fname), encoding="utf-8-sig") as f:
                flat = self._flatten(json.load(f))
            for key in self.REQUIRED_KEYS:
                import re
                en_ph = set(re.findall(r"\{[^}]*\}", str(en_flat.get(key, ""))))
                lang_ph = set(re.findall(r"\{[^}]*\}", str(flat.get(key, ""))))
                assert lang_ph == en_ph, f"{fname} {key}: placeholders {lang_ph} != {en_ph}"