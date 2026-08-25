"""API-backed fleet tracking configuration for remote-only client mode.

``RemotePreferences`` is JSON-file based and has no API path, so this small
client exposes the new ``GET/PUT /api/v1/settings/tracking`` endpoints.  It
lets the fleet tracking service configure and run GPS tracking against the
server without a local database.

Usage::

    from client.api_client import ApiClient
    from client.remote_tracking_config import RemoteTrackingConfig
    cfg = RemoteTrackingConfig(ApiClient())
    config = cfg.get_config()       # {platform, tokens, interval_seconds, enabled}
    cfg.save_config({...})
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("remote_tracking_config")

# ``tokens`` payload keys of GET/PUT /settings/tracking (flat setting name =
# ``tracking.<key>``). Must mirror ``backend/api/v1/settings.py``.
TRACKING_TOKEN_KEYS = (
    "token", "host", "username", "password", "account",
    "positions_path", "lat_field", "lng_field", "id_field",
)


class RemoteTrackingConfig:
    """Read/write fleet-tracking settings through the API."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    # ── API-backed config ──────────────────────────────────────────────

    def get_config(self) -> Dict[str, Any]:
        """Return the server-side tracking config dict.

        Shape: ``{"platform": str, "tokens": {…}, "interval_seconds": int,
        "enabled": bool}``.  On any API error an empty-shaped ``{}`` is
        returned so callers degrade to the "not configured" state gracefully
        instead of crashing.
        """
        try:
            config = self._api._get("/api/v1/settings/tracking")
            return config if isinstance(config, dict) else {}
        except Exception as exc:
            logger.warning("Failed to load tracking config: %s", exc)
            return {}

    def save_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Persist a tracking config dict via ``PUT /settings/tracking``.

        Raises the API client's exception on failure so the caller can
        surface the error (e.g. in a settings dialog).
        """
        return self._api._put("/api/v1/settings/tracking", json_data=config)

    # ── Helpers (flat settings-table shape) ────────────────────────────

    @classmethod
    def to_settings_dict(cls, config: Dict[str, Any]) -> Dict[str, str]:
        """Flatten an API config dict into ``tracking.*`` settings keys."""
        cfg = config or {}
        tokens = cfg.get("tokens") or {}
        if not isinstance(tokens, dict):
            tokens = {}
        flat: Dict[str, str] = {"tracking.platform": str(cfg.get("platform") or "")}
        for key in TRACKING_TOKEN_KEYS:
            flat[f"tracking.{key}"] = str(tokens.get(key) or "")
        flat["tracking.interval"] = str(cfg.get("interval_seconds", 30) or 30)
        flat["tracking.enabled"] = "1" if cfg.get("enabled", True) else "0"
        return flat

    @classmethod
    def from_settings_dict(cls, settings: Dict[str, str]) -> Dict[str, Any]:
        """Expand flat ``tracking.*`` keys back into an API config dict."""
        s = settings or {}
        tokens: Dict[str, str] = {
            key: str(s.get(f"tracking.{key}") or "") for key in TRACKING_TOKEN_KEYS
        }
        try:
            interval = max(5, int(str(s.get("tracking.interval", "30") or 30)))
        except (TypeError, ValueError):
            interval = 30
        enabled_raw = str(s.get("tracking.enabled", "1") or "1").strip().lower()
        return {
            "platform": str(s.get("tracking.platform") or ""),
            "tokens": tokens,
            "interval_seconds": interval,
            "enabled": enabled_raw in ("1", "true", "yes", "on"),
        }
