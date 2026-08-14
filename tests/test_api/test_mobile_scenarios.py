"""Comprehensive scenario tests for the Mobile API.

Covers offline mode, sync, push notification, pagination, and concurrency
scenarios that are not tested by the endpoint-level or data-flow tests.

Test matrix:
  - OfflineModeScenarios (3): request queuing detection, retry safety,
    conflict detection
  - SyncScenarios (4): cursor-based sync, concurrent cursor conflicts,
    partial sync resume, invalid cursor handling
  - PushNotificationEdgeCases (3): token lifecycle, delivery failure,
    update existing token
  - PaginationAndPerformance (3): large transport lists, message pagination,
    concurrent driver connections
  - TransportSyncEdgeCases (2): delta sync after create, full sync
    returns all

Usage:
    pytest tests/test_api/test_mobile_scenarios.py -v --tb=long
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, PropertyMock, call

import bcrypt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── Env setup before project imports ──────────────────────────────────
_TEST_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_TEST_DB_PATH = os.path.join(
    _TEST_DB_DIR, f"test_mobile_scenarios_{uuid.uuid4().hex[:12]}.db"
)
# Unconditional (not setdefault): this suite must own its DB path even when
# an earlier-imported conftest on the same xdist worker already set it.
os.environ["OPERION_DB_PATH"] = _TEST_DB_PATH
os.environ["OPERION_JWT_SECRET_KEY"] = os.environ.get(
    "OPERION_TEST_JWT_SECRET", "scenarios-test-jwt-secret-change-me"
)
os.environ["OPERION_RATE_LIMIT"] = "10000"

import bcrypt
import pytest
from fastapi.testclient import TestClient
from tests.test_api.helpers import create_test_app, MOCK_USER

# ── Test credentials ──────────────────────────────────────────────────
_COMPANY_NAME = "Scenario Test Company"
_DRIVER_EMAIL = "scenario-driver@test.xyz"
_DISPATCHER_EMAIL = "scenario-dispatcher@test.xyz"
_PASSWORD = "scenario-pass-123!"


# ═══════════════════════════════════════════════════════════════════════
#  Database helpers
# ═══════════════════════════════════════════════════════════════════════


def _db_select(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute a read-only SELECT and return rows as dicts."""
    import sqlite3

    conn = sqlite3.connect(_TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _db_execute(sql: str, params: tuple = ()) -> None:
    """Execute a write statement and commit."""
    import sqlite3

    conn = sqlite3.connect(_TEST_DB_PATH)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _reset_db_singleton() -> None:
    """Reset the module-level DatabaseManager singleton."""
    import backend.dependencies as deps

    if deps._db_instance is not None:  # type: ignore[attr-defined]
        try:
            deps._db_instance.close()
        except Exception:
            pass
        deps._db_instance = None


# ═══════════════════════════════════════════════════════════════════════
#  Seed helpers
# ═══════════════════════════════════════════════════════════════════════


def _patch_missing_columns(db) -> None:
    """Add schema columns missing from production migrations."""
    for col, col_def in (
        ("cmr_number", "TEXT DEFAULT ''"),
        ("place_of_loading", "TEXT DEFAULT ''"),
        ("updated_at", "TEXT"),
    ):
        try:
            db.execute(f"ALTER TABLE trips ADD COLUMN {col} {col_def}")
        except Exception:
            pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN name TEXT")
    except Exception:
        pass


def _seed_database() -> int:
    """Create test DB, populate seed data, return the company_id."""
    from database.db_manager import DatabaseManager

    db = DatabaseManager(_TEST_DB_PATH)
    _patch_missing_columns(db)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Company
    db.execute(
        "INSERT INTO companies (company_name, is_active, created_at, updated_at) "
        "VALUES (?, 1, ?, ?)",
        (_COMPANY_NAME, now, now),
    )
    db.commit()
    cid = db.execute(
        "SELECT id FROM companies WHERE company_name = ?", (_COMPANY_NAME,)
    ).fetchone()["id"]

    # Users
    pw_hash = bcrypt.hashpw(
        _PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=4)
    ).decode("utf-8")

    db.execute(
        "INSERT INTO users (email, password_hash, role, company_id, is_active, "
        "display_name, created_at) VALUES (?, ?, 'driver', ?, 1, 'Scenario Driver', ?)",
        (_DRIVER_EMAIL, pw_hash, cid, now),
    )
    db.commit()
    uid_driver = db.execute(
        "SELECT id FROM users WHERE email = ?", (_DRIVER_EMAIL,)
    ).fetchone()["id"]

    db.execute(
        "INSERT INTO users (email, password_hash, role, company_id, is_active, "
        "display_name, created_at) VALUES (?, ?, 'dispatcher', ?, 1, 'Scenario Dispatcher', ?)",
        (_DISPATCHER_EMAIL, pw_hash, cid, now),
    )
    db.commit()

    # Drivers
    db.execute(
        "INSERT INTO drivers (name, email, company_id, is_active, created_at, updated_at) "
        "VALUES ('Scenario Driver', ?, ?, 1, ?, ?)",
        (_DRIVER_EMAIL, cid, now, now),
    )
    db.commit()
    did = db.execute(
        "SELECT id FROM drivers WHERE email = ? AND company_id = ?",
        (_DRIVER_EMAIL, cid),
    ).fetchone()["id"]
    db.execute("UPDATE users SET driver_id = ? WHERE id = ?", (did, uid_driver))
    db.commit()

    # Populate name from display_name for messages
    db.execute("UPDATE users SET name = display_name WHERE name IS NULL")
    db.commit()

    # Trucks
    db.execute(
        "INSERT OR IGNORE INTO trucks (id, plate_number, manufacturer, model, "
        "status, company_id) VALUES (100, 'SCN-100', 'ScenarioBrand', 'ScenarioModel', "
        "'active', ?)",
        (cid,),
    )
    db.commit()

    # Driver-truck assignment
    db.execute(
        "INSERT OR IGNORE INTO driver_truck_assignments (driver_id, truck_id, assigned_at) "
        "VALUES (?, 100, ?)",
        (did, now),
    )
    db.commit()

    # Seed some trips
    for i in range(5):
        ref = f"SCN-TRP-{100 + i}"
        db.execute(
            """INSERT OR IGNORE INTO trips
               (id, cmr_number, place_of_loading, delivery_country, status,
                driver_id, driver_name, truck_number,
                start_date, created_at, updated_at, company_id)
               VALUES (?, ?, ?, ?, 'Planned', ?, 'Scenario Driver', 'SCN-100',
                       ?, ?, ?, ?)""",
            (1000 + i, ref, f"Origin-{i}", f"Dest-{i}",
             did, now, now, now, cid),
        )
    db.commit()

    db.close()
    return cid


_initialized = False


def _ensure_test_db() -> int:
    """Idempotent module-level initialisation of the test database."""
    global _initialized
    if _initialized:
        # Return company_id from DB
        rows = _db_select(
            "SELECT id FROM companies WHERE company_name = ?", (_COMPANY_NAME,)
        )
        return rows[0]["id"] if rows else 1
    os.makedirs(_TEST_DB_DIR, exist_ok=True)

    from config import Config as _cfg

    _cfg.DB_PATH = _TEST_DB_PATH
    _reset_db_singleton()
    cid = _seed_database()
    _initialized = True
    return cid


def _cleanup_test_db() -> None:
    """Remove this worker's own test database files.

    Only the exact ``_TEST_DB_PATH`` is removed.  Under pytest-xdist the
    same module runs in several worker processes, each with its own
    UUID-based DB file; globbing the module prefix would delete the DB
    file another worker is actively using (spurious "unknown user"
    login failures).
    """
    for suffix in ("", "-wal", "-shm"):
        p = _TEST_DB_PATH + suffix
        try:
            os.remove(p)
        except (PermissionError, FileNotFoundError):
            pass


def _get_token(
    client: TestClient, email: str = _DRIVER_EMAIL, password: str = _PASSWORD
) -> str:
    """Login via /api/v1/auth/token and return the JWT access token."""
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": password},
    )
    if resp.status_code != 200:
        pytest.fail(f"Login failed ({resp.status_code}): {resp.text[:300]}")
    body = resp.json()
    assert "access_token" in body, f"Missing access_token: {body}"
    return body["access_token"]


# ═══════════════════════════════════════════════════════════════════════
#  Module-level fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module", autouse=True)
def _module_db():
    """Seed the test database once per module and clean up when done."""
    _ensure_test_db()
    yield
    _cleanup_test_db()


@pytest.fixture
def client():
    """Return a fresh TestClient with auth overrides (mock user)."""
    _reset_db_singleton()
    return TestClient(create_test_app())


@pytest.fixture
def real_client():
    """Return a TestClient with real JWT auth (no overrides)."""
    from config import Config

    Config.DB_PATH = _TEST_DB_PATH
    _reset_db_singleton()
    from backend.main import create_app

    return TestClient(create_app())


@pytest.fixture
def auth_headers(client) -> Dict[str, str]:
    """Authorization header using the mock user (auth overrides are active)."""
    return {"Authorization": "Bearer mock-token"}


@pytest.fixture
def driver_headers(real_client) -> Dict[str, str]:
    """Real JWT for the driver user."""
    token = _get_token(real_client, _DRIVER_EMAIL, _PASSWORD)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def dispatcher_headers(real_client) -> Dict[str, str]:
    """Real JWT for the dispatcher user."""
    token = _get_token(real_client, _DISPATCHER_EMAIL, _PASSWORD)
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════
#  Mock-based fixtures (for offline / DB-failure scenarios)
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    """Return a MagicMock that acts as a DatabaseManager."""
    mock = MagicMock()
    # By default, make the cursor return no rows for SELECT
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    cursor.lastrowid = 999
    mock.execute.return_value = cursor
    return mock


@pytest.fixture
def app_with_mock_db(mock_db):
    """FastAPI app with get_db overridden to return a mock DatabaseManager."""
    app = FastAPI()
    from backend.api.v1.router import api_v1_router
    from backend.dependencies import get_db
    from backend.dependencies_security import (
        get_current_user,
        require_dispatcher,
        require_admin,
        require_manager,
    )

    app.include_router(api_v1_router)
    # Override auth + db
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[require_dispatcher] = lambda: MOCK_USER
    app.dependency_overrides[require_admin] = lambda: MOCK_USER
    app.dependency_overrides[require_manager] = lambda: MOCK_USER
    app.dependency_overrides[get_db] = lambda: mock_db
    return app


@pytest.fixture
def mock_client(app_with_mock_db) -> TestClient:
    """TestClient with all dependencies mocked (auth + DB)."""
    return TestClient(app_with_mock_db, raise_server_exceptions=False)


# ═══════════════════════════════════════════════════════════════════════
#  OFFLINE MODE SCENARIOS
# ═══════════════════════════════════════════════════════════════════════


class TestOfflineModeScenarios:
    """Offline-mode behaviours: queuing, retry, conflict detection.

    These tests verify the API's contract for how a mobile client should
    handle offline scenarios.  The actual queuing mechanism lives on the
    client; the API provides the HTTP-level signals (status codes,
    idempotency) that enable it.
    """

    def test_request_queuing_detection(
        self, mock_client: TestClient, mock_db: MagicMock
    ):
        """Client can detect when a request should be queued (503/5xx).

        When the database is unavailable, the endpoint should return a
        server error, signalling the mobile client to queue the request
        for later retry.
        """
        # Make the mock DB raise an OperationalError (simulating DB down)
        mock_db.execute.side_effect = Exception("database is locked")

        # Attempt a status update — should fail with 5xx
        resp = mock_client.patch(
            "/api/v1/mobile/transports/1/status",
            json={"status": "In Transit"},
        )
        # The client should see a 500-series error and queue the request
        assert resp.status_code in (
            500, 503,
        ), (
            f"Expected 500/503 for offline DB, got {resp.status_code}: "
            f"{resp.text[:200]}"
        )

        # Verify the mock was actually called (the endpoint tried to use DB)
        assert mock_db.execute.called, (
            "The endpoint should have attempted a DB query"
        )

    def test_retry_safety_on_reconnect(
        self, real_client: TestClient, dispatcher_headers: Dict[str, str]
    ):
        """Retrying the same POST request is safe (idempotent creation).

        The mobile client, upon reconnecting, retries queued requests.
        The API should handle this gracefully — at minimum it should not
        crash or return a 5xx on duplicate creation attempts.
        """
        ref = f"RETRY-{uuid.uuid4().hex[:8].upper()}"

        # First attempt — should succeed
        r1 = real_client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": ref,
                "loading_city": "Retry Origin",
                "delivery_city": "Retry Dest",
            },
            headers=dispatcher_headers,
        )
        assert r1.status_code in (201, 200), (
            f"First create failed: {r1.status_code} {r1.text[:200]}"
        )

        # Second attempt (retry) — same payload, should not crash
        r2 = real_client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": ref,
                "loading_city": "Retry Origin",
                "delivery_city": "Retry Dest",
            },
            headers=dispatcher_headers,
        )
        # Accept 201 (new row), 200 (idempotent), 400/409 (duplicate detected)
        assert r2.status_code in (200, 201, 400, 409, 422), (
            f"Retry gave unexpected status: {r2.status_code} {r2.text[:200]}"
        )

        # Verify no corruption: both rows (if both succeeded) are valid
        rows = _db_select(
            "SELECT id, company_id FROM trips WHERE cmr_number = ?", (ref,)
        )
        assert len(rows) >= 1, "At least one row should exist"
        # If two rows exist, they should have the same company_id
        if len(rows) > 1:
            cids = {r["company_id"] for r in rows}
            assert len(cids) == 1, (
                f"Duplicate rows belong to different companies: {cids}"
            )

    def test_sync_conflict_detection_when_stale(
        self, real_client: TestClient, dispatcher_headers: Dict[str, str]
    ):
        """Sync with a stale cursor returns records that the client missed.

        Verifies the conflict-detection primitive: if the client provides
        a cursor older than existing records, the server returns those
        records so the client can detect and resolve conflicts.
        """
        # Get a current cursor via full sync
        r1 = real_client.get(
            "/api/v1/mobile/sync?entity=transport&full=true",
            headers=dispatcher_headers,
        )
        assert r1.status_code == 200
        body1 = r1.json()

        # Create a new transport to simulate a change the "stale" client missed
        create_resp = real_client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": "CONFLICT-TEST",
                "loading_city": "Conflict Origin",
                "delivery_city": "Conflict Dest",
            },
            headers=dispatcher_headers,
        )
        assert create_resp.status_code == 201
        new_id = create_resp.json()["id"]

        # Now sync with an old/expired cursor — should return the new record
        old_cursor = "1970-01-01T00:00:00"
        r2 = real_client.get(
            f"/api/v1/mobile/sync?entity=transport&since={old_cursor}",
            headers=dispatcher_headers,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert isinstance(body2.get("records"), list), (
            "Sync response should contain a records list"
        )
        # The old-cursor sync should include the newly created transport
        record_ids = [r["id"] for r in body2["records"]]
        assert new_id in record_ids, (
            f"New transport {new_id} not in sync results with stale cursor. "
            f"Records: {record_ids}"
        )


# ═══════════════════════════════════════════════════════════════════════
#  SYNC SCENARIOS
# ═══════════════════════════════════════════════════════════════════════


class TestSyncScenarios:
    """Cursor-based sync protocol: new records, conflicts, resume, errors."""

    def test_cursor_based_sync_returns_new_records_since_last_sync(
        self, real_client: TestClient, dispatcher_headers: Dict[str, str]
    ):
        """Cursor-based delta sync returns only records newer than the cursor.

        This is the core sync protocol: the client provides a cursor
        (timestamp) and the server returns only records updated after
        that point.
        """
        # Full sync to get a baseline cursor
        r1 = real_client.get(
            "/api/v1/mobile/sync?entity=transport&full=true",
            headers=dispatcher_headers,
        )
        assert r1.status_code == 200
        body1 = r1.json()
        cursor1 = body1.get("cursor")
        assert cursor1, "Full sync should return a cursor"
        initial_count = len(body1.get("records", []))

        # Create a new transport
        create_resp = real_client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": "DELTA-TEST",
                "loading_city": "Delta Origin",
                "delivery_city": "Delta Dest",
            },
            headers=dispatcher_headers,
        )
        assert create_resp.status_code == 201
        new_id = create_resp.json()["id"]

        # Delta sync with the cursor from the full sync
        r2 = real_client.get(
            f"/api/v1/mobile/sync?entity=transport&since={cursor1}",
            headers=dispatcher_headers,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        delta_records = body2.get("records", [])
        delta_ids = [r["id"] for r in delta_records]

        # The delta should include the new transport but not necessarily all old ones
        assert new_id in delta_ids, (
            f"New transport {new_id} missing from delta sync. "
            f"Delta records: {delta_ids}"
        )
        # The delta count should be <= what a full sync would return
        assert len(delta_records) <= initial_count + 1, (
            f"Delta sync returned {len(delta_records)} records, "
            f"expected at most {initial_count + 1}"
        )

    def test_cursor_conflict_two_devices_same_cursor(
        self, real_client: TestClient, dispatcher_headers: Dict[str, str]
    ):
        """Two devices syncing with the same cursor both get consistent data.

        When two devices (e.g., phone and tablet) sync with the same
        cursor, both should receive the same set of records.  This is
        the foundation for conflict-free sync.
        """
        # Device A syncs
        r_a = real_client.get(
            "/api/v1/mobile/sync?entity=transport&full=true",
            headers=dispatcher_headers,
        )
        assert r_a.status_code == 200
        body_a = r_a.json()
        cursor_a = body_a.get("cursor")
        records_a = body_a.get("records", [])

        # Device B syncs with the same cursor (full sync)
        r_b = real_client.get(
            "/api/v1/mobile/sync?entity=transport&full=true",
            headers=dispatcher_headers,
        )
        assert r_b.status_code == 200
        body_b = r_b.json()
        records_b = body_b.get("records", [])

        # Both devices should see the same data (same cursor can be full sync)
        ids_a = {r["id"] for r in records_a}
        ids_b = {r["id"] for r in records_b}
        assert ids_a == ids_b, (
            f"Two devices with same cursor see different records.\n"
            f"Device A ids: {ids_a}\nDevice B ids: {ids_b}"
        )

        # Now test delta sync: both devices use the same cursor for delta
        old_cursor = body_a.get("cursor", "")
        r_delta_a = real_client.get(
            f"/api/v1/mobile/sync?entity=transport&since={old_cursor}",
            headers=dispatcher_headers,
        )
        r_delta_b = real_client.get(
            f"/api/v1/mobile/sync?entity=transport&since={old_cursor}",
            headers=dispatcher_headers,
        )
        assert r_delta_a.status_code == 200
        assert r_delta_b.status_code == 200
        delta_a = {r["id"] for r in r_delta_a.json().get("records", [])}
        delta_b = {r["id"] for r in r_delta_b.json().get("records", [])}
        assert delta_a == delta_b, (
            f"Delta sync from same cursor differs between devices.\n"
            f"Device A: {delta_a}\nDevice B: {delta_b}"
        )

    def test_partial_sync_resume(
        self, real_client: TestClient, dispatcher_headers: Dict[str, str]
    ):
        """Sync interrupted mid-stream can resume from last cursor.

        Simulates: client does a full sync, gets cursor C1.  New data
        arrives.  Client tries delta sync but network fails.  Client
        retries delta sync with same cursor — should get the same
        (or superset) of records.
        """
        # Step 1: full sync to get baseline cursor
        r1 = real_client.get(
            "/api/v1/mobile/sync?entity=transport&full=true",
            headers=dispatcher_headers,
        )
        assert r1.status_code == 200
        cursor1 = r1.json().get("cursor", "")

        # Step 2: create some new data
        for i in range(3):
            real_client.post(
                "/api/v1/mobile/dispatcher/transports",
                json={
                    "reference": f"RESUME-{i}",
                    "loading_city": f"Resume Origin {i}",
                    "delivery_city": f"Resume Dest {i}",
                },
                headers=dispatcher_headers,
            )

        # Step 3: first delta sync (simulate "interrupted" — we just do it)
        r2 = real_client.get(
            f"/api/v1/mobile/sync?entity=transport&since={cursor1}",
            headers=dispatcher_headers,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        cursor2 = body2.get("cursor", "")
        records2 = {r["id"] for r in body2.get("records", [])}

        # Step 4: resume from the same cursor (simulating retry after interruption)
        r3 = real_client.get(
            f"/api/v1/mobile/sync?entity=transport&since={cursor1}",
            headers=dispatcher_headers,
        )
        assert r3.status_code == 200
        body3 = r3.json()
        records3 = {r["id"] for r in body3.get("records", [])}

        # Both attempts should see at least the same records
        # (records2 is a subset of records3, or they are equal)
        missing_in_retry = records2 - records3
        assert not missing_in_retry, (
            f"Records seen in first delta sync missing from retry: "
            f"{missing_in_retry}"
        )

        # Step 5: resume from cursor2 (the middle cursor) — should get nothing new
        r4 = real_client.get(
            f"/api/v1/mobile/sync?entity=transport&since={cursor2}",
            headers=dispatcher_headers,
        )
        assert r4.status_code == 200
        body4 = r4.json()
        records4 = body4.get("records", [])
        # After the point where we last saw changes, there should be few/no new records
        assert len(records4) < len(records2) + 5, (
            f"Resume from cursor2 returned {len(records4)} records, "
            f"expected less than {len(records2) + 5}"
        )

    def test_invalid_cursor_handling(
        self, real_client: TestClient, dispatcher_headers: Dict[str, str]
    ):
        """Malformed cursor values are handled gracefully.

        The sync endpoint should not crash when given an invalid,
        malformed, or empty cursor.  It should return a 200 with empty
        records or a client-error status.
        """
        invalid_cursors = [
            "",
            "not-a-date",
            "null",
            "undefined",
            "../../etc/passwd",
            "<script>alert(1)</script>",
        ]

        for bad_cursor in invalid_cursors:
            resp = real_client.get(
                f"/api/v1/mobile/sync?entity=transport&since={bad_cursor}",
                headers=dispatcher_headers,
            )
            # Accept 200 (graceful handling) or 400/422 (explicit rejection)
            assert resp.status_code in (200, 400, 422), (
                f"Invalid cursor {bad_cursor!r} gave {resp.status_code}: "
                f"{resp.text[:200]}"
            )
            if resp.status_code == 200:
                body = resp.json()
                assert "records" in body, (
                    f"Sync response missing 'records' for bad cursor "
                    f"{bad_cursor!r}: {body}"
                )


# ═══════════════════════════════════════════════════════════════════════
#  PUSH NOTIFICATION EDGE CASES
# ═══════════════════════════════════════════════════════════════════════


class TestPushNotificationEdgeCases:
    """Push notification token lifecycle and delivery edge cases."""

    def test_device_token_lifecycle_full(
        self, real_client: TestClient, driver_headers: Dict[str, str]
    ):
        """Full lifecycle: register → verify → update → unregister → verify inactive.

        This tests the complete push notification token management flow
        that a mobile client performs.
        """
        device_id = f"lifecycle-{uuid.uuid4().hex[:12]}"

        # ── 1. Register ──────────────────────────────────────────────
        r1 = real_client.post(
            "/api/v1/mobile/devices/register",
            json={
                "token": f"fcm-{device_id}",
                "platform": "android",
                "device_id": device_id,
                "device_name": "Pixel 7",
            },
            headers=driver_headers,
        )
        assert r1.status_code == 200, f"Register failed: {r1.text[:200]}"
        assert r1.json().get("status") == "registered"

        # Verify in DB
        rows = _db_select(
            "SELECT token, platform, is_active, device_name "
            "FROM mobile_devices WHERE device_id = ?",
            (device_id,),
        )
        assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
        assert rows[0]["is_active"] == 1
        assert rows[0]["platform"] == "android"
        assert rows[0]["device_name"] == "Pixel 7"

        # ── 2. Update token ───────────────────────────────────────────
        r2 = real_client.post(
            "/api/v1/mobile/devices/register",
            json={
                "token": f"fcm-updated-{device_id}",
                "platform": "ios",
                "device_id": device_id,
                "device_name": "iPhone 15",
            },
            headers=driver_headers,
        )
        assert r2.status_code == 200, f"Update failed: {r2.text[:200]}"
        assert r2.json().get("status") == "registered"

        # Verify updated in DB (DELETE+INSERT means same device_id, new token)
        rows = _db_select(
            "SELECT token, platform, is_active, device_name "
            "FROM mobile_devices WHERE device_id = ?",
            (device_id,),
        )
        assert len(rows) == 1, (
            f"After update, expected 1 row, got {len(rows)}"
        )
        assert rows[0]["token"] == f"fcm-updated-{device_id}", (
            f"Token not updated: {rows[0]['token']}"
        )
        assert rows[0]["platform"] == "ios"
        assert rows[0]["device_name"] == "iPhone 15"

        # ── 3. Unregister ─────────────────────────────────────────────
        r3 = real_client.delete(
            "/api/v1/mobile/devices/register",
            headers=driver_headers,
        )
        assert r3.status_code == 200, f"Unregister failed: {r3.text[:200]}"
        assert r3.json().get("status") == "unregistered"

        # Verify inactive in DB
        rows = _db_select(
            "SELECT is_active FROM mobile_devices WHERE device_id = ?",
            (device_id,),
        )
        assert len(rows) == 1
        assert rows[0]["is_active"] == 0, (
            "Device should be inactive after unregister"
        )

        # ── 4. Register again (re-registration after unregister) ──────
        r4 = real_client.post(
            "/api/v1/mobile/devices/register",
            json={
                "token": f"fcm-rereg-{device_id}",
                "platform": "android",
                "device_id": device_id,
                "device_name": "Pixel 7 (re-registered)",
            },
            headers=driver_headers,
        )
        assert r4.status_code == 200, f"Re-register failed: {r4.text[:200]}"
        assert r4.json().get("status") == "registered"

        # Verify DB: old row was replaced, or new active row exists
        rows = _db_select(
            "SELECT token, is_active FROM mobile_devices WHERE device_id = ?",
            (device_id,),
        )
        assert len(rows) == 1
        assert rows[0]["is_active"] == 1, (
            "Device should be active after re-registration"
        )
        assert rows[0]["token"] == f"fcm-rereg-{device_id}"

    def test_notification_delivery_failure_handling(
        self, real_client: TestClient, driver_headers: Dict[str, str],
        dispatcher_headers: Dict[str, str]
    ):
        """Device registration survives and endpoint remains functional
        even after registering an invalid/expired push token.

        Push notification delivery failures are typically handled by the
        push service (FCM/APNs), not the API.  But the API must remain
        functional when clients register tokens that may later become
        invalid.
        """
        invalid_tokens = [
            "",                          # empty
            "invalid-token",             # malformed
            "!" * 500,                   # excessively long
            "token-that-will-expire-later",
        ]

        for bad_token in invalid_tokens:
            device_id = f"fail-{uuid.uuid4().hex[:12]}"
            resp = real_client.post(
                "/api/v1/mobile/devices/register",
                json={
                    "token": bad_token,
                    "platform": "android",
                    "device_id": device_id,
                },
                headers=driver_headers,
            )
            # Should accept any token (server does not validate with FCM)
            assert resp.status_code == 200, (
                f"Token {bad_token!r} gave {resp.status_code}: "
                f"{resp.text[:200]}"
            )
            # Verify it was stored
            rows = _db_select(
                "SELECT token, is_active FROM mobile_devices WHERE device_id = ?",
                (device_id,),
            )
            assert len(rows) == 1
            assert rows[0]["is_active"] == 1

        # After registering invalid tokens, the rest of the API still works
        overview = real_client.get(
            "/api/v1/mobile/dispatcher/overview",
            headers=dispatcher_headers,
        )
        assert overview.status_code == 200, (
            f"Overview after bad tokens: {overview.status_code}"
        )

    def test_device_register_update_same_user_multiple_devices(
        self, real_client: TestClient, driver_headers: Dict[str, str]
    ):
        """A single user can register multiple devices with different IDs.

        The same driver may use multiple devices (phone + tablet).
        Each should have its own registration.
        """
        device_ids = []
        for i in range(3):
            dev_id = f"multi-{i}-{uuid.uuid4().hex[:8]}"
            device_ids.append(dev_id)
            resp = real_client.post(
                "/api/v1/mobile/devices/register",
                json={
                    "token": f"fcm-{dev_id}",
                    "platform": "android" if i % 2 == 0 else "ios",
                    "device_id": dev_id,
                    "device_name": f"Device {i}",
                },
                headers=driver_headers,
            )
            assert resp.status_code == 200, (
                f"Register device {i} failed: {resp.text[:200]}"
            )

        # Each device_id should have its own row
        for dev_id in device_ids:
            rows = _db_select(
                "SELECT token, platform, is_active, device_name "
                "FROM mobile_devices WHERE device_id = ?",
                (dev_id,),
            )
            assert len(rows) == 1, (
                f"Expected 1 row for {dev_id}, got {len(rows)}"
            )
            assert rows[0]["is_active"] == 1


# ═══════════════════════════════════════════════════════════════════════
#  PAGINATION AND PERFORMANCE SCENARIOS
# ═══════════════════════════════════════════════════════════════════════


class TestPaginationAndPerformance:
    """Large data sets, pagination limits, and concurrent access."""

    def test_large_transport_list_pagination(
        self, real_client: TestClient, dispatcher_headers: Dict[str, str]
    ):
        """Driver transports list correctly returns up to 100 items.

        The endpoint uses LIMIT 100.  Ensure it returns items without
        crashing and enforces the limit correctly.
        """
        # Ensure there are at least a few transports
        existing = _db_select(
            "SELECT COUNT(*) AS cnt FROM trips WHERE company_id = "
            "(SELECT id FROM companies WHERE company_name = ?)",
            (_COMPANY_NAME,),
        )
        existing_count = existing[0]["cnt"] if existing else 0

        # Create additional transports to reach a known count
        target_count = max(existing_count, 3)
        for i in range(target_count, target_count + 5):
            _db_execute(
                "INSERT INTO trips (cmr_number, place_of_loading, "
                "delivery_country, status, company_id, created_at, updated_at) "
                "VALUES (?, ?, ?, 'Planned', ?, datetime('now'), datetime('now'))",
                (
                    f"BULK-{i}",
                    f"Bulk Origin {i}",
                    f"Bulk Dest {i}",
                    _db_select(
                        "SELECT id FROM companies WHERE company_name = ?",
                        (_COMPANY_NAME,),
                    )[0]["id"],
                ),
            )

        # Fetch dispatcher jobs (LIMIT 200 in SQL)
        resp = real_client.get(
            "/api/v1/mobile/dispatcher/jobs",
            headers=dispatcher_headers,
        )
        assert resp.status_code == 200, (
            f"Jobs list failed: {resp.status_code} {resp.text[:200]}"
        )
        jobs = resp.json()
        assert isinstance(jobs, list), "Jobs should be a list"
        assert len(jobs) >= 1, "Should have at least 1 job"

        # Fetch driver transports (LIMIT 100 in SQL)
        resp2 = real_client.get(
            "/api/v1/mobile/driver/transports",
            headers=_get_headers_for_driver(real_client),
        )
        assert resp2.status_code == 200, (
            f"Transports list failed: {resp2.status_code} {resp2.text[:200]}"
        )
        transports = resp2.json()
        assert isinstance(transports, list)
        # The limit is 100; we should not exceed it
        assert len(transports) <= 100, (
            f"Transport list returned {len(transports)} items, "
            f"expected ≤100"
        )

    def test_message_pagination_count(
        self, real_client: TestClient, dispatcher_headers: Dict[str, str]
    ):
        """Message list returns up to 100 messages (LIMIT 100).

        Verify that the endpoint enforces a reasonable limit and does
        not return unbounded results.
        """
        # Send several messages
        sent_ids = []
        for i in range(5):
            resp = real_client.post(
                "/api/v1/mobile/messages",
                json={
                    "receiver_id": 1,  # Will be mapped to current user
                    "text": f"Pagination message {i}",
                },
                headers=dispatcher_headers,
            )
            if resp.status_code == 201:
                sent_ids.append(resp.json()["id"])

        # List messages
        resp = real_client.get(
            "/api/v1/mobile/messages",
            headers=dispatcher_headers,
        )
        assert resp.status_code == 200, (
            f"Messages list: {resp.status_code} {resp.text[:200]}"
        )
        msgs = resp.json()
        assert isinstance(msgs, list)
        # Verify sent messages appear in the list
        msg_ids = {m["id"] for m in msgs}
        for sid in sent_ids:
            assert sid in msg_ids, (
                f"Sent message {sid} not found in messages list"
            )
        # Verify limit is respected (≤100)
        assert len(msgs) <= 100, (
            f"Message list returned {len(msgs)} items, expected ≤100"
        )

    def test_concurrent_driver_connections(
        self, real_client: TestClient, driver_headers: Dict[str, str]
    ):
        """Multiple concurrent API calls from the same driver are handled.

        Simulates a driver's device sending multiple requests in quick
        succession (e.g., my-day + transports + vehicle + messages).
        Each should succeed independently.
        """
        import concurrent.futures
        import threading

        endpoints = [
            ("GET", "/api/v1/mobile/driver/my-day"),
            ("GET", "/api/v1/mobile/driver/transports"),
            ("GET", "/api/v1/mobile/driver/vehicle"),
            ("GET", "/api/v1/mobile/messages"),
            ("GET", "/api/v1/mobile/user/profile"),
        ]

        errors: List[str] = []
        lock = threading.Lock()

        def call_endpoint(method: str, path: str) -> None:
            try:
                if method == "GET":
                    resp = real_client.get(path, headers=driver_headers)
                else:
                    return
                if resp.status_code not in (200, 201):
                    with lock:
                        errors.append(
                            f"{path}: status={resp.status_code} {resp.text[:100]}"
                        )
            except Exception as e:
                with lock:
                    errors.append(f"{path}: exception={e}")

        # Fire all endpoints concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = []
            for _ in range(3):  # 3 concurrent rounds
                for method, path in endpoints:
                    futures.append(pool.submit(call_endpoint, method, path))
            concurrent.futures.wait(futures)

        assert not errors, (
            f"Concurrent requests produced errors:\n" + "\n".join(errors)
        )


# ═══════════════════════════════════════════════════════════════════════
#  TRANSPORT SYNC EDGE CASES
# ═══════════════════════════════════════════════════════════════════════


class TestTransportSyncEdgeCases:
    """Edge cases specific to transport sync behaviour."""

    def test_delta_sync_after_create_returns_new_transport(
        self, real_client: TestClient, dispatcher_headers: Dict[str, str]
    ):
        """Creating a transport then delta-syncing returns that transport.

        End-to-end: POST transport → GET delta sync → verify the new
        transport appears in the delta results.
        """
        # Full sync first to get a cursor
        r1 = real_client.get(
            "/api/v1/mobile/sync?entity=transport&full=true",
            headers=dispatcher_headers,
        )
        assert r1.status_code == 200
        cursor1 = r1.json().get("cursor", "")

        # Create a new transport
        ref = f"SYNC-E2E-{uuid.uuid4().hex[:8].upper()}"
        create_resp = real_client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": ref,
                "loading_city": "Sync E2E Origin",
                "delivery_city": "Sync E2E Dest",
            },
            headers=dispatcher_headers,
        )
        assert create_resp.status_code == 201
        new_id = create_resp.json()["id"]

        # Delta sync
        r2 = real_client.get(
            f"/api/v1/mobile/sync?entity=transport&since={cursor1}",
            headers=dispatcher_headers,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        delta_ids = [r["id"] for r in body2.get("records", [])]

        assert new_id in delta_ids, (
            f"New transport {new_id} missing from delta sync. "
            f"Delta ids: {delta_ids}"
        )

    def test_full_sync_returns_all_transports(
        self, real_client: TestClient, dispatcher_headers: Dict[str, str]
    ):
        """Full sync (without since cursor or with full=true) returns all transports."""
        # Full sync
        r1 = real_client.get(
            "/api/v1/mobile/sync?entity=transport&full=true",
            headers=dispatcher_headers,
        )
        assert r1.status_code == 200
        body1 = r1.json()
        full_ids = {r["id"] for r in body1.get("records", [])}

        # Full sync again should return the same set (possibly more if new ones were created)
        r2 = real_client.get(
            "/api/v1/mobile/sync?entity=transport&full=true",
            headers=dispatcher_headers,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        full2_ids = {r["id"] for r in body2.get("records", [])}

        # All records from the first full sync should still be present
        missing = full_ids - full2_ids
        assert not missing, (
            f"Full sync returned different records on second call. "
            f"Missing: {missing}"
        )

        # Sync without params (no entity, no since) should return empty
        r3 = real_client.get(
            "/api/v1/mobile/sync",
            headers=dispatcher_headers,
        )
        assert r3.status_code == 200
        body3 = r3.json()
        assert body3.get("records") == [], (
            f"Sync without entity should return empty, got {len(body3.get('records', []))} records"
        )
        assert body3.get("cursor"), "Sync without entity should still return a cursor"


# ═══════════════════════════════════════════════════════════════════════
#  Helper
# ═══════════════════════════════════════════════════════════════════════


def _get_headers_for_driver(real_client: TestClient) -> Dict[str, str]:
    """Return auth headers for the driver user (used in pagination test)."""
    token = _get_token(real_client, _DRIVER_EMAIL, _PASSWORD)
    return {"Authorization": f"Bearer {token}"}
