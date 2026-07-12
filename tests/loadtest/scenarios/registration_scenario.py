"""Locust scenarios for registration and auth load testing.

Usage:
    cd tests/loadtest
    locust -f locustfile.py --headless -u 100 -r 10 -t 60s
"""

import time
import random
import string

from locust import HttpUser, task, between
from tests.loadtest.factories import TokenManager


def random_email():
    ts = int(time.time() * 1000)
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    return f"loadtest-{ts}-{suffix}@test.com"


class WebsiteRegistrationUser(HttpUser):
    """Simulates a user visiting the Operion website and registering."""

    wait_time = between(1, 3)

    def on_start(self):
        """Each simulated user registers first."""
        self.email = random_email()
        self.password = "LoadTestPass123!"
        self.display_name = f"Load Test User {random.randint(1, 9999)}"
        self.company_name = f"Load Test Corp {random.randint(1, 9999)}"

        resp = self.client.post("/api/v1/registration/register", json={
            "email": self.email,
            "password": self.password,
            "display_name": self.display_name,
            "company_name": self.company_name,
        })

        if resp.status_code == 201:
            data = resp.json()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.headers = {"Authorization": f"Bearer {self.access_token}"}
        else:
            self.access_token = None
            self.refresh_token = None
            self.headers = {}

    @task(3)
    def browse_users(self):
        """List users in the company."""
        if self.access_token:
            self.client.get("/api/v1/users/", headers=self.headers)

    @task(2)
    def refresh_token(self):
        """Refresh the access token."""
        if self.refresh_token:
            resp = self.client.post("/api/v1/auth/refresh", json={
                "refresh_token": self.refresh_token,
            })
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                self.headers = {"Authorization": f"Bearer {self.access_token}"}

    @task(1)
    def check_health(self):
        """Health endpoint."""
        self.client.get("/api/v1/health")

    @task(1)
    def create_dispatcher(self):
        """Create a dispatcher user."""
        if self.access_token:
            email = random_email()
            self.client.post("/api/v1/users/", json={
                "email": email,
                "password": "DispatchPass123!",
                "role": "dispatcher",
                "display_name": f"Dispatcher {random.randint(1, 9999)}",
            }, headers=self.headers)


class AuthLoadUser(HttpUser):
    """Simulates login/logout/refresh cycles."""

    wait_time = between(0.5, 2)

    def on_start(self):
        """Register and get tokens."""
        self.email = random_email()
        self.password = "AuthLoadPass123!"
        resp = self.client.post("/api/v1/registration/register", json={
            "email": self.email,
            "password": self.password,
            "display_name": "Auth Load User",
            "company_name": "Auth Load Corp",
        })
        if resp.status_code == 201:
            self.refresh_token = resp.json()["refresh_token"]

    @task(5)
    def login(self):
        """Login with credentials."""
        self.client.post("/api/v1/auth/token", data={
            "username": self.email,
            "password": self.password,
        })

    @task(2)
    def forgot_password(self):
        """Request password reset."""
        self.client.post("/api/v1/auth/forgot-password", json={
            "email": self.email,
        })

    @task(1)
    def logout(self):
        """Logout and re-register."""
        if self.refresh_token:
            self.client.post("/api/v1/auth/logout", json={
                "refresh_token": self.refresh_token,
            })
        # Re-register for next cycle
        self.on_start()
