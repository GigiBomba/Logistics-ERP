"""Remote Co-Pilot API wrapper with WebSocket support."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RemoteCopilotService:
    """API-backed substitute for Co-Pilot backend."""

    def __init__(self, api_client, auth_token: str = "") -> None:
        self._api = api_client
        self._auth_token = auth_token

    # ── Chat / Voice ──────────────────────────────────────────────────

    def chat(self, utterance: str, conversation_id: str = None,
             language: str = "en") -> dict:
        body: Dict[str, Any] = {
            "utterance": utterance,
            "language": language,
        }
        if conversation_id:
            body["conversation_id"] = conversation_id
        return self._api._post("/api/v1/copilot/chat", json_data=body)

    def voice_input(self, utterance: str, conversation_id: str = None,
                    language: str = "en") -> dict:
        body: Dict[str, Any] = {
            "utterance": utterance,
            "language": language,
        }
        if conversation_id:
            body["conversation_id"] = conversation_id
        return self._api._post("/api/v1/copilot/voice", json_data=body)

    # ── Plans ─────────────────────────────────────────────────────────

    def get_plan(self, plan_id: str) -> dict:
        return self._api._get(f"/api/v1/copilot/plans/{plan_id}")

    def confirm_plan(self, plan_id: str) -> dict:
        return self._api._post(f"/api/v1/copilot/plans/{plan_id}/confirm")

    def cancel_plan(self, plan_id: str) -> dict:
        return self._api._post(f"/api/v1/copilot/plans/{plan_id}/cancel")

    def undo_plan(self, plan_id: str) -> dict:
        return self._api._post(f"/api/v1/copilot/plans/{plan_id}/undo")

    # ── Conversations ─────────────────────────────────────────────────

    def list_conversations(self, limit: int = 20, cursor: str = None) -> list:
        params: dict = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = self._api._get("/api/v1/copilot/conversations", params=params)
        return resp.get("items", []) if resp else []

    def get_conversation(self, conversation_id: str) -> dict:
        return self._api._get(f"/api/v1/copilot/conversations/{conversation_id}")

    # ── Insights ──────────────────────────────────────────────────────

    def list_insights(self, limit: int = 20, status_filter: str = None) -> list:
        params: dict = {"limit": limit}
        if status_filter:
            params["status_filter"] = status_filter
        resp = self._api._get("/api/v1/copilot/insights", params=params)
        return resp.get("items", []) if resp else []

    # ── WebSocket ─────────────────────────────────────────────────────

    def ws_url(self, conversation_id: str) -> str:
        """Build WebSocket URL for timeline updates.

        The desktop app must use a Qt-compatible WebSocket client
        to connect to this URL, passing the JWT as a query parameter.
        """
        base = self._api._base_url.rstrip("/")
        ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
        return f"{ws_base}/api/v1/copilot/ws/{conversation_id}?token={self._auth_token}"
