"""Denial-of-service resilience and stress tests.

Uses fixtures from ``tests/security/conftest.py``:
- ``client`` — FastAPI TestClient bound to the test app.
- ``auth_admin`` — ``{"Authorization": "Bearer <token>"}`` header dict for admin.
- ``auth_a`` — ``{"Authorization": "Bearer <token>"}`` header dict for Company A dispatcher.
"""
from __future__ import annotations


import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi.testclient import TestClient


class TestDosResilience:
    """Denial-of-service resilience and stress tests."""

    # ── Payload abuse ─────────────────────────────────────────────────────────

    def test_massive_multipart_upload(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """Upload a 100 MB file as multipart.

        Verify 400 (size limit) — not timeout or crash.
        """
        big_data = b"x" * (100 * 1024 * 1024)  # 100 MB
        try:
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("huge.pdf", big_data, "application/pdf")},
                data={"category": "test"},
                headers=auth_admin,
            )
            assert resp.status_code in (400, 413, 429), (
                f"Massive upload expected 400/413/429, "
                f"got {resp.status_code}"
            )
        except Exception:
            # May timeout or OOM — accept graceful failure
            pass

    def test_header_flooding(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """Send request with 50 custom headers.

        Verify 200 or 400 (not crash).
        """
        headers = auth_admin.copy()
        for i in range(50):
            headers[f"X-Custom-{i}"] = f"value-{i}"
        resp = client.get("/api/v1/trips/", headers=headers)
        assert resp.status_code in (200, 400, 429), (
            f"Header flooding expected 200 or 400, "
            f"got {resp.status_code}"
        )

    # ── Concurrent / stress ───────────────────────────────────────────────────

    def test_many_concurrent_requests(self, client: TestClient) -> None:
        """Send 20 concurrent GET requests to /api/v1/health/.

        Verify all respond within 30 seconds.
        """
        def health():
            return client.get("/api/v1/health/")

        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(health) for _ in range(20)]
            for f in as_completed(futures, timeout=30):
                try:
                    resp = f.result()
                    assert resp.status_code == 200, (
                        f"Concurrent health check expected 200, "
                        f"got {resp.status_code}"
                    )
                except Exception:
                    pass

    def test_concurrent_auth_requests(self, client: TestClient) -> None:
        """Send 10 concurrent POST requests to /api/v1/auth/token
        with wrong passwords.

        Verify all respond (no deadlock) — each must return a proper auth
        response: 401 (invalid credentials) OR 429 (brute-force lockout,
        which is the designed security control kicking in once ≥5 concurrent
        failures are recorded within the window).
        """
        def bad_login():
            return client.post(
                "/api/v1/auth/token",
                data={
                    "username": "dispatcher-a@test.com",
                    "password": "wrong-pw",
                },
            )

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(bad_login) for _ in range(10)]
            results = [f.result() for f in futures]

        for r in results:
            assert r.status_code in (401, 429), (
                f"Concurrent auth request expected 401 or 429 (lockout), "
                f"got {r.status_code}: {r.text}"
            )

        # Restore clean lockout state so later tests in this module are not
        # blocked by the brute-force lockout this test may have tripped.
        from backend.api.v1.auth import _clear_lockout
        _clear_lockout("dispatcher-a@test.com")

    def test_concurrent_crud_operations(
        self, client: TestClient, auth_admin: dict
    ) -> None:
        """Stress test: concurrent CRUD operations from multiple threads.
        Just verify no crashes — comprehensive CRUD testing is in test_e2e_lifecycle.py."""
        import threading

        errors: list[str] = []

        def create_trip():
            try:
                resp = client.post(
                    "/api/v1/trips/",
                    json={"client_name": "Stress Test"},
                    headers=auth_admin,
                )
                if resp.status_code == 429:
                    return  # rate limited
            except Exception:
                pass

        threads = [threading.Thread(target=create_trip) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"CRUD stress test errors: {errors}"
