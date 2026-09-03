"""API-backed tacho service wrapper for remote-only client mode.

Mirrors ``services.tacho_service.TachoService`` for listing import
history and checking tacho status via the API.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("remote_tacho")


class RemoteTachoService:
    """API-backed substitute for TachoService."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    def get_import_history(self, limit: int = 50) -> list:
        resp = self._api.get_tacho_import_history(limit=limit)
        return resp.get("items", []) if resp else []

    def get_status(self) -> dict:
        return self._api.get_tacho_status()

    def import_ddd_file(self, file_path: str) -> dict:
        """Upload a DDD file for import via the API.

        Routes through ``ApiClient._post`` (retry/backoff + circuit breaker)
        instead of the raw httpx client, matching every other API call.
        """
        import os
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            return self._api._post("/api/v1/tacho/import", files=files)
