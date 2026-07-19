"""Remote feature flag service for subscription-tier gating."""
from __future__ import annotations
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class RemoteFeatureFlagService:
    """API-backed feature flag checks for remote mode."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    def list_flags(self) -> list:
        resp = self._api._get("/api/v1/feature-flags/")
        return resp.get("flags", []) if resp else []

    def is_enabled(self, flag_key: str, company_id: int = 0) -> bool:
        try:
            resp = self._api._get(
                f"/api/v1/feature-flags/{flag_key}",
                params={"company_id": company_id})
            return resp.get("enabled", False) if resp else False
        except Exception:
            return False

    def set_enabled(self, flag_key: str, enabled: bool,
                    company_id: int = 0) -> dict:
        action = "enable" if enabled else "disable"
        return self._api._post(
            f"/api/v1/feature-flags/{flag_key}/{action}",
            json_data={"company_id": company_id})

    def are_all_enabled(self, flag_keys: List[str],
                        company_id: int = 0) -> bool:
        return all(self.is_enabled(k, company_id) for k in flag_keys)
