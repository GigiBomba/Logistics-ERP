"""Local staging integration smoke (deferred-item 4: staging harness).

Marked ``@pytest.mark.staging`` so it never runs in the default suite.
Two paths (the fixture reports which one ran):

- LIVE: against a running staging server (``OPERION_STAGING_BASE_URL``,
  default http://127.0.0.1:8010) started via ``scripts/start_staging.bat``.
- FALLBACK: in-process ``create_app()`` with the staging env + seeded DB when
  the server is unreachable.

Happy-path chain: login(driver) -> trip-overview -> route-share ->
login(dispatcher) -> manifest -> ocr/process (Idempotency-Key) -> copilot/chat.
Each step asserts the contract shape from ``tests/contracts/``.
"""
from __future__ import annotations


import os
import subprocess
import sys
import uuid

import httpx
import pytest

STAGING_BASE = os.environ.get("OPERION_STAGING_BASE_URL", "http://127.0.0.1:8010")
# Mirrors the real mobile client: the API-key middleware (backend/desktop_config
# Config.API_KEY) validates X-API-Key on every non-public path. The staging
# harness overrides OPERION_API_KEY in its env so the real .env key is never used.
STAGING_API_KEY = os.environ.get(
    "OPERION_STAGING_API_KEY",
    "staging-dev-only-api-key-0000000000000000000000000000",
)
REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DRIVER_CREDS = {"username": "driver@staging.local", "password": "staging-pass"}
DISPATCHER_CREDS = {"username": "dispatcher@staging.local", "password": "staging-pass"}

pytestmark = pytest.mark.staging

TRIP_OVERVIEW_KEYS = {
    "transport_id", "load_info", "origin", "destination",
    "status", "status_since", "eta", "eta_confidence",
}
MANIFEST_ENTRY_KEYS = {"record_id", "filename", "size_bytes", "download_url", "url_expires_at"}

# 1x1 transparent PNG (valid magic + minimal chunk); accepted by the OCR
# endpoint's type/size validation (never decoded synchronously).
_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
)


def _server_up() -> bool:
    try:
        httpx.get(f"{STAGING_BASE}/docs", timeout=2)
        return True
    except Exception:
        return False


def _seed_db() -> None:
    subprocess.run(
        [sys.executable, "scripts/seed_staging_users.py"],
        cwd=REPO_ROOT, check=True, capture_output=True,
    )


@pytest.fixture(scope="module")
def ctx():
    """(client, path, driver_token, dispatcher_token)."""
    if _server_up():
        client = httpx.Client(base_url=STAGING_BASE, timeout=30)
        path = "live"
    else:
        os.environ.setdefault("OPERION_DB_ENGINE", "sqlite")
        # Unconditional (not setdefault): the root conftest pins a per-worker
        # temp OPERION_DB_PATH; this suite must own its staging DB so the
        # in-process app reads the same data/staging.db that
        # scripts/seed_staging_users.py seeds.
        os.environ["OPERION_DB_PATH"] = "data/staging.db"
        os.environ.setdefault(
            "OPERION_JWT_SECRET_KEY",
            "staging-dev-only-secret-0000000000000000000000000000",
        )
        # The backend DB singleton (backend.dependencies.init_db) resolves the
        # SQLite path from Config.DB_PATH, not the OPERION_DB_PATH env var —
        # rebind it so the in-process app queries the seeded staging DB.
        from config import Config
        Config.DB_PATH = "data/staging.db"
        # The API-key middleware freezes Config.API_KEY at app creation (from
        # the real .env key) — rebind it to the staging key the harness sends,
        # so protected endpoints validate instead of 403-ing.
        Config.API_KEY = STAGING_API_KEY
        _seed_db()
        from backend.main import create_app
        from fastapi.testclient import TestClient

        client = TestClient(create_app())
        path = "in-process"

    def _login(creds: dict) -> str:
        resp = client.post("/api/v1/auth/token", data=creds)
        assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
        return resp.json()["access_token"]

    driver_token = _login(DRIVER_CREDS)
    dispatcher_token = _login(DISPATCHER_CREDS)
    yield client, path, driver_token, dispatcher_token
    client.close()


def _auth(token: str) -> dict:
    """Bearer auth, plus X-API-Key only when a staging key is configured (the
    middleware is in open mode when OPERION_API_KEY is unset — the header is
    then harmless but should not be assumed)."""
    headers = {"Authorization": f"Bearer {token}"}
    if STAGING_API_KEY:
        headers["X-API-Key"] = STAGING_API_KEY
    return headers


def test_smoke_reports_its_path(ctx) -> None:
    """The harness must state which path it ran (live vs in-process)."""
    _, path, _, _ = ctx
    assert path in ("live", "in-process")
    print(f"\nSTAGING SMOKE PATH: {path} -> {STAGING_BASE}")


def test_driver_trip_overview(ctx) -> None:
    client, _, driver_token, _ = ctx
    resp = client.get(
        "/api/v1/mobile/driver/trip-overview",
        headers=_auth(driver_token),
    )
    assert resp.status_code == 200, f"trip-overview: {resp.status_code} {resp.text}"
    body = resp.json()
    assert set(body) == TRIP_OVERVIEW_KEYS, body.keys()


def test_driver_route_share(ctx) -> None:
    """No transport assigned -> clean 404 (JWT endpoint contract); with one ->
    RouteShareResponse shape."""
    client, _, driver_token, _ = ctx
    resp = client.get("/api/v1/mobile/driver/route-share", headers=_auth(driver_token))
    if resp.status_code == 404:
        return  # documented no-transport state
    assert resp.status_code == 200, f"route-share: {resp.status_code} {resp.text}"
    body = resp.json()
    for key in ("points", "total_distance_meters", "total_duration_seconds", "ttl_seconds"):
        assert key in body, body.keys()


def test_dispatcher_manifest(ctx) -> None:
    client, _, _, dispatcher_token = ctx
    resp = client.post(
        "/api/v1/mobile/company/export/manifest",
        json={"category": "documents"},
        headers=_auth(dispatcher_token),
    )
    assert resp.status_code == 200, f"manifest: {resp.status_code} {resp.text}"
    entries = resp.json()
    assert isinstance(entries, list)
    for entry in entries:
        assert set(entry) >= MANIFEST_ENTRY_KEYS, entry.keys()


def test_ocr_process(ctx) -> None:
    client, _, _, dispatcher_token = ctx
    key = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/ocr/process",
        files={"file": ("staging-receipt.png", _TINY_PNG, "image/png")},
        headers={**_auth(dispatcher_token), "Idempotency-Key": key},
    )
    assert resp.status_code == 201, f"ocr/process: {resp.status_code} {resp.text}"
    body = resp.json()
    assert body["status"] in ("queued", "processing"), body
    assert body["idempotency_key"] == key, body


def test_copilot_chat(ctx) -> None:
    client, _, _, dispatcher_token = ctx
    resp = client.post(
        "/api/v1/copilot/chat",
        json={"utterance": "show me today's overview"},
        headers=_auth(dispatcher_token),
    )
    assert resp.status_code == 200, f"copilot/chat: {resp.status_code} {resp.text}"
    body = resp.json()
    assert "timeline" in body or "clarification_question_key" in body, body.keys()
