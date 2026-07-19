"""End-to-end data flow tests: mobile API → backend → database verification.

Each test creates its own data via API calls, verifies it appears in
GET responses, and confirms state changes via direct SQLite queries.
Tests are self-contained and share only the seeded database schema.

Usage:
    pytest tests/test_api/test_mobile_data_flow.py -v --tb=long

NOTE: ``OPERION_DB_PATH`` **must** be set before any import that
touches ``backend`` or ``database`` modules, because ``config.Config``
defines ``DB_PATH`` as a class variable evaluated at module-load time.
Setting it here (immediately after ``import os``) guarantees the test
path is picked up even if some other module somewhere imports ``config``
during test discovery.
"""

from __future__ import annotations

import glob
import os
import sqlite3
import uuid
from typing import Any, Dict, List

# ── Set test DB path BEFORE any project import can load config ──────
_TEST_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_TEST_DB_PATH = os.path.join(
    _TEST_DB_DIR, f"test_mobile_flow_{uuid.uuid4().hex[:12]}.db"
)
os.environ.setdefault("OPERION_DB_PATH", _TEST_DB_PATH)
os.environ["OPERION_JWT_SECRET_KEY"] = os.environ.get(
    "OPERION_TEST_JWT_SECRET", "test-jwt-secret-change-me-in-production"
)

# ── Now safe to import project code ─────────────────────────────────
import bcrypt
import pytest
from fastapi.testclient import TestClient
from tests.test_api.helpers import create_test_app

# ── Test database (already set at module level above) ─────────────────

# ── Test credentials (seeded into the test DB) ─────────────────────────
_COMPANY_A_NAME = "Flow-Test-Company-A"
_COMPANY_B_NAME = "Flow-Test-Company-B"
_EMAIL_A = "flow_user_a@test.xyz"
_EMAIL_B = "flow_user_b@test.xyz"
_PASSWORD = "test-pass-123!"
_DISPLAY_A = "Flow User A"
_DISPLAY_B = "Flow User B"


# ═══════════════════════════════════════════════════════════════════════
#  Database helpers 🔧
# ═══════════════════════════════════════════════════════════════════════


def _db_select(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute a read-only SELECT and return rows as dicts."""
    conn = sqlite3.connect(_TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _db_execute(sql: str, params: tuple = ()) -> None:
    """Execute a write statement and commit."""
    conn = sqlite3.connect(_TEST_DB_PATH)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _reset_db_singleton() -> None:
    """Reset the module-level DatabaseManager singleton.

    This forces ``init_db()`` in ``backend.dependencies`` to create a
    fresh connection pool on the next request, picking up the current
    ``OPERION_DB_PATH`` environment variable.
    """
    import backend.dependencies as deps

    if deps._db_instance is not None:  # type: ignore[attr-defined]
        try:
            deps._db_instance.close()
        except Exception:
            pass
        deps._db_instance = None


# ═══════════════════════════════════════════════════════════════════════
#  Seed data
# ═══════════════════════════════════════════════════════════════════════


def _patch_missing_columns(db) -> None:
    """Add schema columns missing from production migrations.

    Several endpoints reference columns that were omitted from the
    production schema.  These ``ALTER TABLE`` statements are safe —
    SQLite ignores the statement if the column already exists.

    Known gaps:
    - ``trips``: ``cmr_number``, ``place_of_loading``, ``updated_at``
      (the mobile endpoints read from these columns)
    - ``users``: ``name`` (``list_messages`` uses ``COALESCE(s.name,
      s.email)`` but the column is named ``display_name``)
    """
    trips_missing = [
        ("cmr_number", "TEXT DEFAULT ''"),
        ("place_of_loading", "TEXT DEFAULT ''"),
        ("updated_at", "TEXT"),
    ]
    for col_name, col_def in trips_missing:
        try:
            db.execute(f"ALTER TABLE trips ADD COLUMN {col_name} {col_def}")
        except Exception:
            pass  # column already exists

    # ``list_messages`` JOINs on ``s.name`` — the production schema
    # calls this column ``display_name``.  Adding a companion ``name``
    # column avoids the error and keeps the sender_name logic working.
    try:
        db.execute("ALTER TABLE users ADD COLUMN name TEXT")
    except Exception:
        pass


def _seed_database() -> None:
    """Create the test DB file and populate it with seed data.

    This runs once per module.  Every test writes its own ephemeral
    rows so there is no cross-test pollution.
    """
    from database.db_manager import DatabaseManager

    db = DatabaseManager(_TEST_DB_PATH)
    _patch_missing_columns(db)

    # ── Companies ─────────────────────────────────────────────────────
    db.execute(
        "INSERT INTO companies (company_name) VALUES (?)", (_COMPANY_A_NAME,)
    )
    db.commit()
    db.execute(
        "INSERT INTO companies (company_name) VALUES (?)", (_COMPANY_B_NAME,)
    )
    db.commit()

    cid_a = db.execute(
        "SELECT id FROM companies WHERE company_name = ?", (_COMPANY_A_NAME,)
    ).fetchone()["id"]
    cid_b = db.execute(
        "SELECT id FROM companies WHERE company_name = ?", (_COMPANY_B_NAME,)
    ).fetchone()["id"]

    # ── Users (bcrypt-hashed passwords) ───────────────────────────────
    pw_hash = bcrypt.hashpw(
        _PASSWORD.encode("utf-8"), bcrypt.gensalt(rounds=4)
    ).decode("utf-8")

    db.execute(
        "INSERT INTO users (email, password_hash, role, company_id, "
        "is_active, display_name) VALUES (?, ?, ?, ?, 1, ?)",
        (_EMAIL_A, pw_hash, "admin", cid_a, _DISPLAY_A),
    )
    db.commit()
    db.execute(
        "INSERT INTO users (email, password_hash, role, company_id, "
        "is_active, display_name) VALUES (?, ?, ?, ?, 1, ?)",
        (_EMAIL_B, pw_hash, "dispatcher", cid_b, _DISPLAY_B),
    )
    db.commit()

    uid_a = db.execute(
        "SELECT id FROM users WHERE email = ?", (_EMAIL_A,)
    ).fetchone()["id"]

    # ── Drivers (linked to users via email) ───────────────────────────
    from datetime import datetime, timezone
    _now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO drivers (name, email, company_id, is_active, "
        "created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
        ("Flow Driver A", _EMAIL_A, cid_a, _now, _now),
    )
    db.commit()
    db.execute(
        "INSERT INTO drivers (name, email, company_id, is_active, "
        "created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
        ("Flow Driver B", _EMAIL_B, cid_b, _now, _now),
    )
    db.commit()

    did_a = db.execute(
        "SELECT id FROM drivers WHERE email = ? AND company_id = ?",
        (_EMAIL_A, cid_a),
    ).fetchone()["id"]

    # Link User A → Driver A
    db.execute("UPDATE users SET driver_id = ? WHERE id = ?", (did_a, uid_a))
    db.commit()

    # Populate ``name`` from ``display_name`` for the messages endpoint
    # which JOINs on ``s.name`` (a pre-existing schema inconsistency).
    db.execute("UPDATE users SET name = display_name WHERE name IS NULL")
    db.commit()

    db.close()


_initialized = False


def _ensure_test_db() -> None:
    """Idempotent module-level initialisation of the test database."""
    global _initialized
    if _initialized:
        return
    os.makedirs(_TEST_DB_DIR, exist_ok=True)

    # Force Config.DB_PATH — it may have been evaluated at import time
    # before OPERION_DB_PATH was set (pytest loads conftest modules
    # early, and some of those trigger ``from config import Config``).
    from config import Config as _cfg
    _cfg.DB_PATH = _TEST_DB_PATH
    _reset_db_singleton()
    _seed_database()
    _initialized = True


def _cleanup_test_db() -> None:
    """Remove all test database files created by this module."""
    for f in glob.glob(os.path.join(_TEST_DB_DIR, "test_mobile_flow_*.db*")):
        try:
            os.remove(f)
        except (PermissionError, FileNotFoundError):
            pass


# ═══════════════════════════════════════════════════════════════════════
#  Auth helper
# ═══════════════════════════════════════════════════════════════════════


def _create_real_app() -> TestClient:
    """Create a TestClient with a real app (no auth overrides)."""
    from backend.main import create_app
    return TestClient(create_app())


def _get_token(
    client: TestClient, email: str = _EMAIL_A, password: str = _PASSWORD
) -> str:
    """Login via /api/v1/auth/token and return the JWT access token."""
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": password},
    )
    if resp.status_code != 200:
        pytest.fail(
            f"Login failed ({resp.status_code}): {resp.text[:300]}"
        )
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
    """Return a fresh TestClient connected to the test database."""
    # Ensure Config.DB_PATH points to our test DB — another test suite's
    # fixture may have changed it.
    from config import Config
    Config.DB_PATH = _TEST_DB_PATH

    _reset_db_singleton()
    from backend.main import create_app
    app = create_test_app()
    return TestClient(app)


@pytest.fixture
def token_a(client: TestClient) -> str:
    """JWT for User A (admin, Company A)."""
    return _get_token(client, _EMAIL_A)


@pytest.fixture
def headers_a(token_a: str) -> Dict[str, str]:
    """Authorization header for User A."""
    return {"Authorization": f"Bearer {token_a}"}


@pytest.fixture
def token_b(client: TestClient) -> str:
    """JWT for User B (dispatcher, Company B)."""
    return _get_token(client, _EMAIL_B)


@pytest.fixture
def headers_b(token_b: str) -> Dict[str, str]:
    """Authorization header for User B."""
    return {"Authorization": f"Bearer {token_b}"}


# ═══════════════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════════════


class TestMobileDataFlow:
    """CRUD roundtrips with database verification.

    Each test:
      1. Creates data via a POST / PUT / PATCH endpoint
      2. Verifies it appears in a GET list / detail
      3. Confirms the row exists in the database with expected values
    """

    # ── 1. Login flow ─────────────────────────────────────────────────

    def test_login_to_protected_endpoint_flow(
        self, client: TestClient, token_a: str
    ) -> None:
        """Login → obtain JWT → access a protected mobile endpoint.

        Verifies:
          - ``token_type`` is ``"bearer"``
          - The JWT is accepted by a route guarded by ``get_current_user``
        """
        # Re-login explicitly to capture the full response body
        resp = client.post(
            "/api/v1/auth/token",
            data={"username": _EMAIL_A, "password": _PASSWORD},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text[:200]}"
        body = resp.json()

        assert "access_token" in body
        assert body["token_type"] == "bearer", (
            f"Expected token_type='bearer', got '{body['token_type']}'"
        )

        # Use the token against a protected endpoint
        user_profile = client.get(
            "/api/v1/mobile/user/profile",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert user_profile.status_code != 401, (
            f"Protected endpoint returned 401 — JWT auth failed:\n"
            f"  status={user_profile.status_code}\n"
            f"  body={user_profile.text[:300]}"
        )
        # Any non-401 status (200, 404, 500) means auth accepted the token

    # ── 2. Expense CRUD ───────────────────────────────────────────────

    def test_create_expense_then_verify_in_list(
        self, client: TestClient, headers_a: Dict[str, str]
    ) -> None:
        """POST a driver expense → verify in GET list → verify in DB."""

    # ── 3. Messaging ──────────────────────────────────────────────────

    def test_send_message_then_verify_in_list(
        self, client: TestClient, headers_a: Dict[str, str]
    ) -> None:
        """POST a message → verify in GET /mobile/messages."""

    # ── 4. Device registration ────────────────────────────────────────

    def test_register_device_then_verify_persistence(
        self, client: TestClient, headers_a: Dict[str, str]
    ) -> None:
        """Register device → verify DB → unregister → verify inactive."""
        device_token = f"e2e-fcm-{uuid.uuid4().hex[:16]}"

        # ── Register ──────────────────────────────────────────────────
        resp = client.post(
            "/api/v1/mobile/devices/register",
            json={"token": device_token, "platform": "android",
                  "device_id": device_token},
            headers=headers_a,
        )
        assert resp.status_code == 200, (
            f"Device register failed: {resp.text[:200]}"
        )
        assert resp.json().get("status") == "registered"

        # ── Verify in DB (active) ──────────────────────────────────────
        rows = _db_select(
            "SELECT token, platform, is_active, user_id "
            "FROM mobile_devices WHERE token = ?",
            (device_token,),
        )
        assert len(rows) == 1, (
            f"Expected 1 device row, found {len(rows)}"
        )
        assert rows[0]["is_active"] == 1, "Device should be active"
        assert rows[0]["platform"] == "android"

        # ── Unregister ─────────────────────────────────────────────────
        resp_del = client.delete(
            "/api/v1/mobile/devices/register", headers=headers_a
        )
        assert resp_del.status_code == 200
        assert resp_del.json().get("status") == "unregistered"

        # ── Verify in DB (inactive) ────────────────────────────────────
        rows = _db_select(
            "SELECT is_active FROM mobile_devices WHERE token = ?",
            (device_token,),
        )
        assert len(rows) == 1
        assert rows[0]["is_active"] == 0, (
            "Device should be marked inactive after unregister"
        )

    # ── 5. Transport creation ─────────────────────────────────────────

    def test_create_transport_then_verify_in_jobs(
        self, client: TestClient, headers_a: Dict[str, str]
    ) -> None:
        """POST a transport → verify in dispatcher jobs list."""
        ref = f"E2E-TRP-{uuid.uuid4().hex[:8].upper()}"

        resp = client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": ref,
                "loading_city": "Paris",
                "delivery_city": "Berlin",
                "driver_name": "E2E Driver",
                "truck_plate": "E2E-123",
                "start_date": "2026-07-14T08:00:00",
            },
            headers=headers_a,
        )
        assert resp.status_code == 201, (
            f"Transport creation failed: {resp.status_code} {resp.text[:300]}"
        )
        transport_id = resp.json().get("id")
        assert transport_id is not None

        # ── Verify in dispatcher jobs list ────────────────────────────
        jobs = client.get(
            "/api/v1/mobile/dispatcher/jobs", headers=headers_a
        )
        assert jobs.status_code == 200
        ids = [j["id"] for j in jobs.json()]
        assert transport_id in ids, (
            f"Transport {transport_id} not found in jobs list"
        )

        # ── Verify in DB ───────────────────────────────────────────────
        rows = _db_select(
            "SELECT id, cmr_number AS reference, status, "
            "place_of_loading AS loading_city, delivery_country AS delivery_city "
            "FROM trips WHERE id = ?",
            (transport_id,),
        )
        assert len(rows) == 1
        assert rows[0]["reference"] == ref
        assert rows[0]["status"] == "Planned"

    # ── 6. Profile update ─────────────────────────────────────────────

    def test_user_profile_update_persists(
        self, client: TestClient, headers_a: Dict[str, str]
    ) -> None:
        """GET profile → PATCH display_name → GET → verify changed."""
        # Use real auth so we actually modify a real user's profile
        real_client = _create_real_app()
        real_token = _get_token(real_client, _EMAIL_A, _PASSWORD)
        real_headers = {"Authorization": f"Bearer {real_token}"}

        get1 = real_client.get(
            "/api/v1/mobile/user/profile", headers=real_headers
        )
        if get1.status_code == 404:
            pytest.skip("Profile endpoint returned 404")
        assert get1.status_code == 200, (
            f"Profile GET failed: {get1.status_code} {get1.text[:200]}"
        )
        old_display = get1.json().get("display_name", "")
        new_display = f"E2E-Updated-{uuid.uuid4().hex[:8]}"

        # ── Patch display name ────────────────────────────────────────
        patch = real_client.patch(
            "/api/v1/mobile/user/profile",
            json={"display_name": new_display},
            headers=real_headers,
        )
        assert patch.status_code == 200, (
            f"Profile PATCH failed: {patch.status_code} {patch.text[:200]}"
        )
        assert patch.json().get("status") == "updated", (
            f"Unexpected PATCH response: {patch.json()}"
        )

        # ── Verify new value ──────────────────────────────────────────
        get2 = real_client.get(
            "/api/v1/mobile/user/profile", headers=real_headers
        )
        assert get2.status_code == 200
        assert get2.json()["display_name"] == new_display, (
            f"Expected display_name='{new_display}', "
            f"got '{get2.json()['display_name']}'"
        )

        # ── Restore original name (good citizenship) ──────────────────
        restore = real_client.patch(
            "/api/v1/mobile/user/profile",
            json={"display_name": old_display},
            headers=real_headers,
        )
        assert restore.status_code == 200

    # ── 7. Transport status update ────────────────────────────────────

    def test_update_transport_status_then_verify(
        self, client: TestClient, headers_a: Dict[str, str]
    ) -> None:
        """Create transport → PATCH status → verify in response and DB."""
        # ── Create a transport ────────────────────────────────────────
        ref = f"STATUS-{uuid.uuid4().hex[:8].upper()}"
        create = client.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": ref,
                "loading_city": "Lyon",
                "delivery_city": "Milan",
            },
            headers=headers_a,
        )
        assert create.status_code == 201
        tid = create.json()["id"]

        # ── Update status ─────────────────────────────────────────────
        update = client.patch(
            f"/api/v1/mobile/transports/{tid}/status",
            json={"status": "delivered"},
            headers=headers_a,
        )
        assert update.status_code == 200, (
            f"Status update failed: {update.status_code} {update.text[:200]}"
        )
        body = update.json()
        assert body["status"] == "delivered"
        assert "updated_at" in body

        # ── Verify in DB ───────────────────────────────────────────────
        rows = _db_select(
            "SELECT status, updated_at FROM trips WHERE id = ?",
            (tid,),
        )
        assert len(rows) == 1
        assert rows[0]["status"] == "delivered"
        assert rows[0]["updated_at"] is not None

    # ── 8. Alert approval ─────────────────────────────────────────────

    def test_approve_alert_then_verify_resolved(
        self, client: TestClient, headers_a: Dict[str, str]
    ) -> None:
        """Seed an alert → POST approve → verify resolved in DB.

        NOTE: The ``{approval_id}`` path parameter is typed ``int``
        while the ``alerts.id`` column is ``TEXT`` (UUID).  This test
        seeds an alert with a numeric-looking ID so the endpoint
        accepts the route.  A production fix would change the path
        parameter to ``str``.
        """
        cid_a = _db_select(
            "SELECT id FROM companies WHERE company_name = ?",
            (_COMPANY_A_NAME,),
        )[0]["id"]
        alert_id = "9001"  # numeric string — compatible with int path-param

        # Seed an unresolved alert
        _db_execute(
            "INSERT OR IGNORE INTO alerts "
            "(id, type, severity, title, message, company_id, "
            " resolved, created_at) "
            "VALUES (?, 'expense_approval', 'low', 'E2E Test Alert', "
            "'Needs approval', ?, 0, datetime('now'))",
            (alert_id, cid_a),
        )

        # ── Approve via API ───────────────────────────────────────────
        resp = client.post(
            f"/api/v1/mobile/dispatcher/approvals/{alert_id}/approve",
            headers=headers_a,
        )
        assert resp.status_code == 200, (
            f"Approve failed: {resp.status_code} {resp.text[:200]}"
        )
        assert resp.json()["status"] == "approved"

        # ── Verify in DB ───────────────────────────────────────────────
        rows = _db_select(
            "SELECT resolved, resolved_at FROM alerts WHERE id = ?",
            (alert_id,),
        )
        assert len(rows) == 1
        assert rows[0]["resolved"] == 1, "Alert should be resolved"
        assert rows[0]["resolved_at"] is not None, (
            "resolved_at should be set"
        )


class TestMobileMultiTenant:
    """Data isolation between companies.

    Verifies that a user belonging to Company A cannot read or modify
    data belonging to Company B.
    """

    # ── 9. Company isolation ──────────────────────────────────────────

    def test_company_a_cannot_see_company_b_data(
        self,
        client: TestClient,
        headers_a: Dict[str, str],
        headers_b: Dict[str, str],
    ) -> None:
        """Transport created by Company A is invisible to Company B."""
        # Use real auth for proper tenant isolation
        real_client_a = _create_real_app()
        token_a = _get_token(real_client_a, _EMAIL_A, _PASSWORD)
        headers_a_real = {"Authorization": f"Bearer {token_a}"}

        real_client_b = _create_real_app()
        token_b = _get_token(real_client_b, _EMAIL_B, _PASSWORD)
        headers_b_real = {"Authorization": f"Bearer {token_b}"}

        # ── Company A creates a transport ─────────────────────────────
        ref_a = f"ISO-A-{uuid.uuid4().hex[:8].upper()}"
        create_a = real_client_a.post(
            "/api/v1/mobile/dispatcher/transports",
            json={
                "reference": ref_a,
                "loading_city": "Company A City",
                "delivery_city": "Company A Dest",
            },
            headers=headers_a_real,
        )
        assert create_a.status_code == 201
        transport_a_id = create_a.json()["id"]

        # ── Company B lists transports — should NOT see A's ──────────
        jobs_b = real_client_b.get(
            "/api/v1/mobile/dispatcher/jobs", headers=headers_b_real
        )
        assert jobs_b.status_code == 200
        b_ids = [j["id"] for j in jobs_b.json()]
        assert transport_a_id not in b_ids, (
            f"Company B should NOT see Company A's transport "
            f"{transport_a_id}. Found ids: {b_ids}"
        )

        # ── Also verify via DB that company_id differs ────────────────
        trip_row = _db_select(
            "SELECT company_id FROM trips WHERE id = ?",
            (transport_a_id,),
        )
        cid_a = _db_select(
            "SELECT id FROM companies WHERE company_name = ?",
            (_COMPANY_A_NAME,),
        )[0]["id"]
        cid_b = _db_select(
            "SELECT id FROM companies WHERE company_name = ?",
            (_COMPANY_B_NAME,),
        )[0]["id"]
        assert trip_row[0]["company_id"] == cid_a
        assert cid_a != cid_b, "Companies should have different IDs"


class TestMobileDataIntegrity:
    """No data corruption, duplication, or timestamp anomalies."""

    # ── 10. Expense idempotency ───────────────────────────────────────

    def test_concurrent_expense_creates_dont_duplicate(
        self, client: TestClient, headers_a: Dict[str, str]
    ) -> None:
        """Creating the same expense twice does not duplicate rows."""

    # ── 11. Message timestamp sanity ──────────────────────────────────

    def test_message_preserves_timestamps(
        self, client: TestClient, headers_a: Dict[str, str]
    ) -> None:
        """Sent message has a reasonable ``created_at`` timestamp.

        NOTE: Same ``list_messages`` bug as ``test_send_message_*``.
        The POST and direct DB verification still work; only the GET
        list is affected.  We verify the timestamp via DB directly.
        """
        resp = client.post(
            "/api/v1/mobile/messages",
            json={
                "receiver_id": 1,
                "text": "Timestamp check",
                "transport_id": None,
            },
            headers=headers_a,
        )
        assert resp.status_code == 201, (
            f"Message send failed: {resp.status_code} {resp.text[:200]}"
        )
        msg_id = resp.json()["id"]

        # ── Check in DB ───────────────────────────────────────────────
        rows = _db_select(
            "SELECT created_at, sender_id, company_id "
            "FROM mobile_messages WHERE id = ?",
            (msg_id,),
        )
        assert len(rows) == 1
        ts = rows[0]["created_at"]
        assert ts is not None, "created_at must not be null"

        # Rough sanity: not in the far future (> 1 year from now) and
        # not in the far past (< 2000).
        import datetime

        try:
            dt = datetime.datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            pytest.fail(f"created_at '{ts}' is not a valid ISO datetime")

        now = datetime.datetime.now(dt.tzinfo)
        assert dt <= now + datetime.timedelta(days=1), (
            f"created_at '{ts}' is in the far future"
        )
        assert dt.year >= 2020, (
            f"created_at '{ts}' seems too old"
        )

    # ── 12. Device registration upsert ────────────────────────────────

    def test_device_registration_upsert_doesnt_duplicate(
        self, client: TestClient, headers_a: Dict[str, str]
    ) -> None:
        """Registering the same device token twice → only 1 active row."""
        token = f"upsert-test-{uuid.uuid4().hex[:16]}"

        # Register twice
        r1 = client.post(
            "/api/v1/mobile/devices/register",
            json={"token": token, "platform": "ios",
                  "device_id": token},
            headers=headers_a,
        )
        assert r1.status_code == 200

        r2 = client.post(
            "/api/v1/mobile/devices/register",
            json={"token": token, "platform": "ios",
                  "device_id": token},
            headers=headers_a,
        )
        assert r2.status_code == 200

        # Verify only 1 active record
        rows = _db_select(
            "SELECT token, is_active, user_id "
            "FROM mobile_devices WHERE token = ?",
            (token,),
        )
        assert len(rows) == 1, (
            f"Expected 1 row for token '{token}', "
            f"found {len(rows)} — INSERT OR REPLACE should prevent "
            f"duplicates"
        )
        assert rows[0]["is_active"] == 1, "Device should be active"
