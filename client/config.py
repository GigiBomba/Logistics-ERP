"""Client-side configuration gateway.

Resolves the API base URL and environment mode from ``OPERION_ENV``
and ``OPERION_API_URL`` environment variables.  In *production* mode
SSL verification is enforced; for *development* the client falls back
to ``https://api.operionerp.xyz`` with relaxed verification.

Usage::

    from client.config import ClientConfig
    cfg = ClientConfig()
    api = ApiClient(cfg.base_url, verify_ssl=cfg.verify_ssl)
"""
from __future__ import annotations


import os
from typing import Optional

_CONFIG: Optional["ClientConfig"] = None


class ClientConfig:
    PRODUCTION_DOMAIN = "https://api.operionerp.xyz"

    def __init__(self) -> None:
        self._env = os.environ.get("OPERION_ENV", "development").strip().lower()
        self._api_url = os.environ.get("OPERION_API_URL", "").strip()
        self._resolve()

    def _resolve(self) -> None:
        if self._env == "production":
            self.base_url: str = self._api_url or self.PRODUCTION_DOMAIN
            self.verify_ssl: bool = True
        else:
            self.base_url = self._api_url or self._read_fallback()
            self.verify_ssl = False
        self.api_key: str = os.environ.get("OPERION_API_KEY", "")
        self.admin_email: str = os.environ.get("OPERION_ADMIN_EMAIL", "")
        self.admin_password_hash: str = os.environ.get("OPERION_ADMIN_PASSWORD_HASH", "")

    @staticmethod
    def _read_fallback() -> str:
        try:
            from config import Config
            return getattr(Config, "API_BASE_URL", "https://api.operionerp.xyz")
        except Exception:
            return "https://api.operionerp.xyz"

    @property
    def env(self) -> str:
        return self._env

    @property
    def is_production(self) -> bool:
        return self._env == "production"

    @property
    def api_url(self) -> str:
        return self.base_url


def get_client_config() -> ClientConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = ClientConfig()
    return _CONFIG
