"""API-backed freight exchange wrapper for remote-only client mode."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RemoteFreightExchangeService:
    """API-backed substitute for local freight exchange services."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    # ── Provider Management ────────────────────────────────────────────

    def list_providers(self) -> list:
        resp = self._api._get("/api/v1/freight/providers")
        return resp.get("providers", []) if resp else []

    def connect_provider(self, provider_id: str, client_id: str,
                         client_secret: str, scope: list = None) -> dict:
        return self._api._post("/api/v1/freight/providers/connect", json_data={
            "provider_id": provider_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope or [],
        })

    def disconnect_provider(self, provider_id: str) -> dict:
        return self._api._post(f"/api/v1/freight/providers/{provider_id}/disconnect")

    def test_provider(self, provider_id: str) -> dict:
        return self._api._post(f"/api/v1/freight/providers/{provider_id}/test")

    # ── Search ─────────────────────────────────────────────────────────

    def search_loads(self, **kwargs) -> dict:
        body: Dict[str, Any] = {
            k: v for k, v in kwargs.items() if v is not None
        }
        return self._api._post("/api/v1/freight/search", json_data=body)

    def get_recent_searches(self, limit: int = 20) -> list:
        resp = self._api._get("/api/v1/freight/searches", params={"limit": limit})
        return resp.get("searches", []) if resp else []

    def save_search(self, label: str, filters: dict, provider_ids: list = None) -> dict:
        return self._api._post("/api/v1/freight/searches", json_data={
            "label": label,
            "filters": filters,
            "provider_ids": provider_ids,
        })

    def refresh_search(self, search_id: str) -> dict:
        return self._api._post(f"/api/v1/freight/searches/{search_id}/refresh")

    # ── Load Operations ────────────────────────────────────────────────

    def get_load(self, provider_id: str, load_id: str) -> dict:
        return self._api._get(f"/api/v1/freight/loads/{provider_id}/{load_id}")

    def import_load(self, provider_id: str, load_id: str) -> dict:
        return self._api._post(f"/api/v1/freight/loads/{provider_id}/{load_id}/import")

    def evaluate_load(self, provider_id: str, load_id: str,
                      candidate_vehicle_id: int = None) -> dict:
        params = {}
        if candidate_vehicle_id is not None:
            params["candidate_vehicle_id"] = candidate_vehicle_id
        return self._api._get(
            f"/api/v1/freight/loads/{provider_id}/{load_id}/evaluate",
            params=params)

    def match_trucks(self, provider_id: str, load_id: str, top_n: int = 5) -> list:
        resp = self._api._get(
            f"/api/v1/freight/loads/{provider_id}/{load_id}/match",
            params={"top_n": top_n})
        return resp.get("matches", []) if resp else []

    # ── Trans.eu Connection ──────────────────────────────────────────

    def connect_trans_eu(self, authorization_code: str, redirect_uri: str) -> dict:
        """Exchange OAuth authorization_code for Trans.eu tokens.

        Sends the authorization code to the backend which exchanges it
        for access + refresh tokens via the Trans.eu OAuth endpoint.
        """
        return self._api._post(
            "/api/v1/freight/providers/connect_trans_eu",
            {
                "authorization_code": authorization_code,
                "redirect_uri": redirect_uri,
            },
        )

    def get_trans_eu_status(self) -> dict:
        """Get Trans.eu connection status for the current user.

        Returns a dict with provider_id, status, user_id, expires_at,
        ttl_seconds, and needs_refresh.
        """
        return self._api._get("/api/v1/freight/providers/trans_eu/status")
