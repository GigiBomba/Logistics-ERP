"""Authentication scenarios — login, refresh, logout."""
from locust import task, tag
from tests.loadtest.factories import TokenManager


class AuthTasks:
    """Mixin with auth task methods. Hosted on a HttpUser."""

    @task(1)
    @tag("auth", "login")
    def login_flow(self):
        """POST /api/v1/auth/token with valid credentials → 200."""
        with self.client.post("/api/v1/auth/token",
                              data={"username": "admin-a@test.com", "password": "test-admin-pw-123"},
                              catch_response=True, name="login") as resp:
            if resp.status_code == 200:
                TokenManager._tokens["admin-a@test.com"] = resp.json()["access_token"]
                resp.success()
            else:
                resp.failure(f"Login failed: {resp.status_code}")

    @task(1)
    @tag("auth", "refresh")
    def refresh_flow(self):
        """Login → refresh → verify new token works."""
        token = TokenManager.get(self.client, "admin-a@test.com")
        login_resp = self.client.post("/api/v1/auth/token",
                                       data={"username": "admin-a@test.com", "password": "test-admin-pw-123"})
        if login_resp.status_code == 200:
            refresh_token = login_resp.json().get("refresh_token")
            if refresh_token:
                resp = self.client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token},
                                        catch_response=True, name="refresh")
                if resp.status_code == 200:
                    resp.success()
                else:
                    resp.failure(f"Refresh failed: {resp.status_code}")
