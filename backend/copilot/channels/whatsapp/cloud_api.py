"""WhatsApp Business Cloud API provider (graph.facebook.com).

Config follows the established settings pattern (mirrors ``OcrAIProvider``):
DB settings keys ``whatsapp_token``, ``whatsapp_phone_number_id`` and
``whatsapp_api_version`` read via ``SettingsRepository.get_settings_by_keys``,
with the env var ``OPERION_WHATSAPP_TOKEN`` winning over the stored token
(same env-first discipline as ``services.preferences.get_ai_api_key``).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

from backend.copilot.channels.whatsapp.base import WhatsAppProvider
from backend.copilot.channels.whatsapp.registry import register_whatsapp_provider

logger = logging.getLogger(__name__)

DEFAULT_API_VERSION = "v21.0"
DEFAULT_BASE_URL = "https://graph.facebook.com"
_WHATSAPP_SETTING_KEYS = [
    "whatsapp_token",
    "whatsapp_phone_number_id",
    "whatsapp_api_version",
]


@register_whatsapp_provider
class WhatsAppCloudApiProvider(WhatsAppProvider):
    """Send WhatsApp messages through the Meta WhatsApp Business Cloud API.

    POST ``/{api_version}/{phone_number_id}/messages`` with a Bearer token.
    """

    provider_id = "whatsapp_cloud_api"

    def __init__(self) -> None:
        self._token: str = ""
        self._phone_number_id: str = ""
        self._api_version: str = DEFAULT_API_VERSION
        self._base_url: str = DEFAULT_BASE_URL
        self._timeout_s: float = 15.0

    # ── Configuration ───────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """Configured when a token AND a phone-number ID are present."""
        return bool(self._token and self._phone_number_id)

    def reload_settings(self, db: Any = None) -> None:
        """Re-read token / phone-number-id / api-version from DB settings.

        Env var ``OPERION_WHATSAPP_TOKEN`` always wins over the stored token.
        Safe before the settings table exists — keeps current defaults.
        """
        try:
            from repositories.settings_repository import SettingsRepository

            settings: Dict[str, str] = {}
            if db is not None:
                settings = SettingsRepository(db).get_settings_by_keys(
                    _WHATSAPP_SETTING_KEYS
                )
        except Exception as exc:
            logger.warning("WhatsApp settings reload failed: %s", exc)
            settings = {}

        token = os.environ.get("OPERION_WHATSAPP_TOKEN") or settings.get("whatsapp_token") or ""
        if token:
            self._token = token
        if settings.get("whatsapp_phone_number_id"):
            self._phone_number_id = settings["whatsapp_phone_number_id"]
        if settings.get("whatsapp_api_version"):
            self._api_version = settings["whatsapp_api_version"]
        logger.info(
            "WhatsApp Cloud API config: phone_number_id=%s version=%s available=%s",
            self._phone_number_id or "(none)",
            self._api_version,
            self.available,
        )

    # ── HTTP ───────────────────────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        """Return a fresh AsyncClient bound to the current event loop."""
        return httpx.AsyncClient(timeout=httpx.Timeout(self._timeout_s))

    async def _post_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url}/{self._api_version}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        async with self._get_client() as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    # ── WhatsAppProvider interface ─────────────────────────────────────

    async def send_text(self, recipient: str, body: str) -> Dict[str, Any]:
        """Send a plain-text message to *recipient* (E.164 phone number)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": body},
        }
        return await self._post_message(payload)

    async def health(self) -> str:
        """``"healthy"`` when configured (no live call), else ``"down"``."""
        if not self.available:
            return "down"
        return "healthy"