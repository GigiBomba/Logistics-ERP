"""API-backed company-config settings service for remote-only client mode.

NOTE (deliberate divergence): the migration doc row for this unit says
"Extend RemotePreferences", but :class:`client.remote_preferences.RemotePreferences`
is a LOCAL JSON-file store by design — user preferences are NOT server-synced,
and preferences (language / currency / theme / SMTP / tracking / automation)
stay local-first.  Rather than bolt an API path onto that local store, this
standalone service backs ONLY the company-config settings (the form fields
collected by the settings view, mirrored by
``services.invoicing.config_manager.DEFAULT_CONFIG``) and is used only by the
settings view.  ``get_setting`` / ``save_setting`` are thin API passthroughs
kept for interface parity; they are NOT the local preferences API.

Usage::

    from client.api_client import ApiClient
    from client.remote_settings import RemoteSettingsService
    api = ApiClient()
    svc = RemoteSettingsService(api)
    config = svc.get_company_config()   # defaults merged for missing keys
    svc.save_company_config(config)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from services.invoicing.config_manager import DEFAULT_CONFIG

logger = logging.getLogger("remote_settings")

# The full company-config key set the settings view collects — the "Company"
# section (11 text fields) plus the "Branding" section (logo_path,
# company_color, signature_path, stamp_path) in
# ``ui/views/settings_view/settings_fields.py``.  Source of truth for the
# save-payload filter; identical to ``DEFAULT_CONFIG``'s key set.
COMPANY_CONFIG_KEYS: tuple[str, ...] = (
    "company_name", "cui", "reg_number", "address", "county", "city",
    "country", "phone", "email", "iban", "bank_name",
    "logo_path", "company_color", "signature_path", "stamp_path",
)


class RemoteSettingsService:
    """API-backed company-config settings service.

    Reads/writes the company-config fields of the settings view through
    ``GET/PUT /api/v1/settings/company`` (see
    :meth:`client.api_client.ApiClient.get_company_config` /
    ``save_company_config``).  A non-dict GET response degrades to the
    defaults-only dict so the form never crashes on an unexpected payload;
    save payloads are filtered to exactly the form's key set so unknown keys
    never reach the server.  Preferences (``RemotePreferences``) remain a
    local-first JSON store and are deliberately NOT routed through this
    service (see module docstring).
    """

    def __init__(self, api_client) -> None:
        self._api = api_client

    # ── Company config (server-synced) ────────────────────────────────

    def get_company_config(self) -> Dict[str, Any]:
        """Return the server-side company config, defaults for missing keys.

        Mirrors the local loader in ``config_manager.load_company_config``:
        start from ``DEFAULT_CONFIG`` and overlay whatever dict fields the
        server returned (only keys inside the form's set are kept).  When the
        GET response is not a dict (or the call fails) a defaults-only dict is
        returned so the settings form degrades gracefully.
        """
        try:
            resp = self._api.get_company_config()
        except Exception as exc:
            logger.warning("Failed to load company config: %s", exc)
            resp = None
        if not isinstance(resp, dict):
            logger.warning(
                "Company config response is not a dict (%r); using defaults",
                type(resp).__name__,
            )
            return dict(DEFAULT_CONFIG)
        config = dict(DEFAULT_CONFIG)
        config.update({k: v for k, v in resp.items() if k in config})
        return config

    def save_company_config(self, data: Dict[str, Any]) -> Any:
        """Persist company config, filtering *data* to the form's key set.

        Unknown keys are dropped before the PUT so the server schema (which
        forbids extra fields) never rejects the payload.  Returns the API
        client's response; API exceptions propagate to the caller.
        """
        filtered = {k: data[k] for k in COMPANY_CONFIG_KEYS if k in data}
        return self._api.save_company_config(filtered)

    # ── Individual settings (thin passthrough, NOT local prefs) ───────

    def get_setting(self, key: str, default: Optional[Any] = None) -> Any:
        """Read a single server setting; a 404 resolves to *default*.

        ``ApiClient`` signals a missing key by raising
        ``httpx.HTTPStatusError`` (404 from ``raise_for_status``), so that is
        translated to *default* here.  Non-404 errors are re-raised.
        """
        try:
            resp = self._api.get_setting(key)
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return default
            raise
        return resp if resp is not None else default

    def save_setting(self, key: str, value: str) -> Any:
        """Persist a single server setting (passthrough)."""
        return self._api.save_setting(key, value)
