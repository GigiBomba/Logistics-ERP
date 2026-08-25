"""Token management and test data factories for Locust tests."""
from __future__ import annotations

import time


class TokenManager:
    """Caches auth tokens per user to avoid redundant login requests."""
    _tokens = {}
    _token_expiry = {}

    @classmethod
    def get(cls, client, username="admin-a@test.com", password="test-admin-pw-123"):
        """Return a cached token or login to get a fresh one."""
        if username in cls._tokens:
            expiry = cls._token_expiry.get(username, 0)
            if time.time() < expiry - 60:  # Refresh if < 1 min before expiry
                return cls._tokens[username]
        resp = client.post("/api/v1/auth/token", data={"username": username, "password": password})
        if resp.status_code == 200:
            body = resp.json()
            cls._tokens[username] = body["access_token"]
            cls._token_expiry[username] = time.time() + body.get("expires_in", 900)
            return cls._tokens[username]
        return None
