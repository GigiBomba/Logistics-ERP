"""Settings sync service (Phase D — sync completeness).

Syncs the curated set of company-scoped settings so a second device sees the
same company configuration (company profile, SMTP, default preferences).

Two channels:

* **Company config** — the desktop keeps its legal identity in
  ``data/company_config.json`` (``services.invoicing.config_manager``); the
  server mirrors it via ``GET/PUT /api/v1/settings/company``.  Only the keys
  the server whitelists are exchanged (county/city/country/iban/bank_name
  stay local).
* **Key-value settings** — ``smtp_*``, ``alert_email_recipients`` and the
  default preferences (``pref_language``, ``pref_currency``), stored in the
  ``settings`` table and exchanged via ``GET /api/v1/settings/bulk`` +
  ``PUT /api/v1/settings/{key}``.  Sensitive values (``smtp_password``) are
  encrypted at rest on both sides by the shared ``encryption_service``.

Conflict policy: last-write-wins on each key.  The ``settings`` table has no
``updated_at``, so a per-key timestamp comparison is impossible.  The sync
cycle pushes local changes first, then pulls the server state — so the last
cycle's writer wins on both sides (pull-priority on a tie).

Echo suppression: ``settings`` is NOT in ``SYNCABLE_ENTITIES`` → it has no
outbox capture triggers → writing pulled settings locally never creates an
outbox row (inherently safe — verified by tests).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.preferences import PreferencesManager

logger = logging.getLogger(__name__)

# Settings whose values are pushed/pulled as key→value rows.  These are the
# machine-INDEPENDENT keys PreferencesManager manages; window geometry, theme,
# last-opened files and other machine-local state stay on the device.
SYNCABLE_KV_SETTING_KEYS: tuple = (
    # SMTP + alerts
    "smtp_server",
    "smtp_port",
    "smtp_user",
    "smtp_password",
    "alert_email_recipients",
    # Default preferences (language/currency apply per-install, but the
    # company's default should converge across devices).
    "pref_language",
    "pref_currency",
)

# Company-config keys the server whitelists (CompanyConfigUpdateRequest).
# county/city/country/iban/bank_name are NOT exchanged — the server rejects
# unknown keys (extra="forbid").
# S3: logo_path/signature_path/stamp_path are NOT exchanged either — they are
# MACHINE-LOCAL file paths (no binary download exists for them).  Device B
# would get device A's paths and its own logo would be clobbered.  The server
# keeps its own copy; each device manages its own branding files.
COMPANY_CONFIG_SYNC_KEYS: tuple = (
    "company_name",
    "cui",
    "reg_number",
    "address",
    "phone",
    "email",
    "company_color",
)


class SettingsSyncService:
    """Push/pull the curated company-scoped settings via the cloud API."""

    def __init__(self, db, api_client) -> None:
        self._db = db
        self._api_client = api_client

    # ── Push ──────────────────────────────────────────────────────────

    def push_settings(self) -> int:
        """Push local settings to the server.  Returns the number of keys pushed.

        Per-key try/except so one bad key never aborts the sync cycle.
        """
        pushed = 0

        # Company config (JSON file channel).
        try:
            from services.invoicing.config_manager import load_company_config

            local = load_company_config() or {}
            # S3: MERGE the syncable keys into the SERVER's current config
            # instead of replacing it — the server keeps its own copy of
            # county/iban/bank_name and any key a device left empty; a blind
            # PUT would drop them.
            try:
                remote = self._api_client.get_company_config() or {}
                merged = dict(remote) if isinstance(remote, dict) else {}
            except Exception as exc:
                logger.debug(
                    "settings sync: company config pre-read failed, "
                    "pushing local-only: %s", exc,
                )
                merged = {}
            for k in COMPANY_CONFIG_SYNC_KEYS:
                v = local.get(k)
                if v not in (None, ""):
                    merged[k] = v
            if merged:
                self._api_client.save_company_config(merged)
                pushed += len(merged)
        except Exception as exc:
            logger.warning("settings sync: company config push failed: %s", exc)

        # Key-value settings.
        prefs = PreferencesManager(self._db)
        for key in SYNCABLE_KV_SETTING_KEYS:
            try:
                value = prefs.get_setting(key)
                if value is None:
                    continue
                self._api_client.save_setting(key, value)
                pushed += 1
            except Exception as exc:
                logger.warning("settings sync: push %s failed: %s", key, exc)
        return pushed

    # ── Pull ──────────────────────────────────────────────────────────

    def pull_settings(self) -> int:
        """Pull server settings and write them locally.  Returns keys applied.

        Per-key try/except so one bad key never aborts the sync cycle.
        """
        pulled = 0

        # Key-value settings (bulk GET, one round-trip).
        try:
            resp = self._api_client.get_settings_bulk(SYNCABLE_KV_SETTING_KEYS) or {}
            values = resp.get("values") or {}
            prefs = PreferencesManager(self._db)
            for key, value in values.items():
                if value is None:
                    continue  # not configured server-side — leave local as-is
                prefs.save_setting(key, str(value))
                pulled += 1
        except Exception as exc:
            logger.warning("settings sync: key-value pull failed: %s", exc)

        # Company config (JSON file channel).
        try:
            from services.invoicing.config_manager import (
                load_company_config,
                save_company_config,
            )

            remote = self._api_client.get_company_config() or {}
            if not isinstance(remote, dict) or not remote:
                return pulled
            local = dict(load_company_config() or {})
            # Merge only the syncable keys — never clobber local-only fields.
            for key in COMPANY_CONFIG_SYNC_KEYS:
                if key in remote and remote.get(key) not in (None, ""):
                    local[key] = remote[key]
            save_company_config(local)
            pulled += 1
        except Exception as exc:
            logger.warning("settings sync: company config pull failed: %s", exc)
        return pulled
