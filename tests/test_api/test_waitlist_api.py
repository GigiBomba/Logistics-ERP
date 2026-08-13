"""Comprehensive tests for the waitlist API.

Covers:
- Public POST /api/v1/waitlist/join (signup, honeypot, rate-limit, duplicates)
- Admin GET    /api/v1/waitlist/admin/entries    (list, filter, paginate)
- Admin PATCH  /api/v1/waitlist/admin/entries/{id} (status update, state machine)
- Admin DELETE /api/v1/waitlist/admin/entries/{id}
- Admin GET    /api/v1/waitlist/admin/export.csv
- Admin GET    /api/v1/waitlist/admin/stats
- Admin POST   /api/v1/waitlist/admin/campaign
- Auth gate (403 without admin token)
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Import the helpers for creating a test app
from tests.test_api.helpers import create_test_app

BASE = "/api/v1/waitlist"


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module", autouse=True)
def _set_env():
    """Set test environment variables before any test.

    Uses a temporary file for the database so read-only connections
    work correctly.  ``Config.DB_PATH`` is rebound explicitly because
    ``config`` is imported at collection time (before fixtures run), so
    setting ``OPERION_DB_PATH`` alone would not redirect the app DB.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    os.environ["OPERION_DB_PATH"] = tmp.name
    os.environ["OPERION_JWT_SECRET_KEY"] = "test-jwt-secret-for-waitlist-tests"
    os.environ["OPERION_ENV"] = "development"
    os.environ["OPERION_API_KEY"] = "test-api-key"
    from config import Config
    previous_db_path = Config.DB_PATH
    previous_db_engine = Config.DB_ENGINE
    previous_db_engine_env = os.environ.get("OPERION_DB_ENGINE")
    # Force SQLite even on the CI PostgreSQL shard: the module temp-SQLite
    # rebind (Config.DB_PATH) alone does not override OPERION_DB_ENGINE
    # = postgresql, so the app would connect through the PG DSN instead of
    # this per-test temp file.  init_db() reads the env var at call time, so
    # this must be set before the first create_test_app() in the module.
    os.environ["OPERION_DB_ENGINE"] = "sqlite"
    Config.DB_ENGINE = "sqlite"
    Config.DB_PATH = tmp.name
    # The app DB is a process-global singleton (backend.dependencies.init_db).
    # Under `-n auto` another test module in the same xdist worker may have
    # already bound it to the shared CI DB, which would make the waitlist
    # endpoints read/write the wrong database (cross-test pollution such as
    # ``assert 11 == 0`` or ``assert 201 == 409``).  Drop the singleton so
    # init_db() rebuilds it against this module's per-test temp file.
    from backend import dependencies as _deps
    if _deps._db_instance is not None:
        try:
            _deps._db_instance.close()
        except Exception:
            pass
        _deps._db_instance = None
    yield
    for k in ("OPERION_DB_PATH", "OPERION_JWT_SECRET_KEY", "OPERION_ENV", "OPERION_API_KEY"):
        os.environ.pop(k, None)
    # Restore the engine env var (only if it was previously set) and the
    # Config.DB_ENGINE rebind so the module leaves no global state behind.
    if previous_db_engine_env is None:
        os.environ.pop("OPERION_DB_ENGINE", None)
    else:
        os.environ["OPERION_DB_ENGINE"] = previous_db_engine_env
    Config.DB_ENGINE = previous_db_engine
    # Restore Config.DB_PATH so the module leaves no global state behind.
    Config.DB_PATH = previous_db_path
    # Release the singleton so later modules re-init against their own DB.
    if _deps._db_instance is not None:
        try:
            _deps._db_instance.close()
        except Exception:
            pass
        _deps._db_instance = None
    try:
        os.unlink(tmp.name)
    except Exception:
        pass


@pytest.fixture
def app():
    """Create a test app with auth overrides."""
    return create_test_app()


@pytest.fixture
def client(app):
    """TestClient with real DB — auth is mocked to admin."""
    from backend.dependencies_security import get_current_user, require_admin
    mock_user = {"id": 1, "email": "admin@test.com", "role": "admin", "is_admin": True, "company_id": 0}
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clean_db():
    """Ensure a clean waitlist_entries table before each test.

    The truncation goes through the app's ACTIVE singleton connection
    (``backend.dependencies.init_db``) — never a fresh connection to a
    different file — so it always targets the same database the endpoints
    read.  This gives true per-test isolation even when the worker process
    has previously bound the singleton to the shared CI DB.
    """
    # Reset rate-limit state (Redis-backed limiter with in-memory fallback)
    from backend.utils.rate_limit import _fallback
    _fallback.clear()

    from backend.dependencies import init_db
    try:
        db = init_db()
        db.conn.execute("DELETE FROM waitlist_entries")
        db.conn.commit()
    except Exception:
        pass
    yield


def _seed_entry(db, **overrides):
    """Insert a waitlist entry and return its id."""
    data = {
        "company_name": "Test Corp",
        "contact_name": None,
        "email": "test@example.com",
        "fleet_size": None,
        "company_size": None,
        "country": None,
        "source": "landing_page",
        "referral_code": "TESTCODE",
        "ip_hash": None,
        "user_agent": None,
    }
    data.update(overrides)
    db.conn.execute(
        """INSERT INTO waitlist_entries
           (company_name, contact_name, email, fleet_size, company_size,
            country, source, referral_code, ip_hash, user_agent)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data["company_name"], data["contact_name"], data["email"],
         data["fleet_size"], data["company_size"], data["country"],
         data["source"], data["referral_code"], data["ip_hash"], data["user_agent"]),
    )
    db.conn.commit()
    row = db.conn.execute("SELECT id FROM waitlist_entries WHERE referral_code = ?",
                          (data["referral_code"],)).fetchone()
    return row["id"] if row else None


@pytest.fixture
def db():
    """Return a DatabaseManager instance for test seeding."""
    from backend.db import DatabaseManager
    from backend.desktop_config import Config
    return DatabaseManager(Config.DB_PATH, pool_min=1, pool_max=2)


# ═══════════════════════════════════════════════════════════════════════
# Auth Gate
# ═══════════════════════════════════════════════════════════════════════


class TestWaitlistAuthGate:
    """Admin endpoints must return 401/403 without admin auth."""

    ADMIN_ROUTES = [
        ("GET", f"{BASE}/admin/entries"),
        ("PATCH", f"{BASE}/admin/entries/1"),
        ("DELETE", f"{BASE}/admin/entries/1"),
        ("GET", f"{BASE}/admin/export.csv"),
        ("GET", f"{BASE}/admin/stats"),
        ("POST", f"{BASE}/admin/campaign"),
    ]

    def test_public_join_no_auth_required(self, app):
        """POST /waitlist/join is public — no auth needed."""
        client = TestClient(app)
        resp = client.post(f"{BASE}/join", json={
            "company_name": "Public Co",
            "email": "public@test.com",
        })
        assert resp.status_code == 201

    @pytest.mark.parametrize("method,path", ADMIN_ROUTES)
    def test_admin_endpoint_returns_401_without_token(self, app, method, path):
        """Admin endpoints return 401 when no token is provided."""
        # Create a clean app without auth overrides
        from backend.api.v1.router import api_v1_router
        from fastapi import FastAPI
        clean_app = FastAPI()
        clean_app.include_router(api_v1_router)

        client = TestClient(clean_app)
        body = {}
        if method == "PATCH":
            body = json.dumps({"status": "invited"})
        if method == "POST":
            body = json.dumps({"subject": "Test", "body": "Hello", "segment": "all"})

        if method == "GET":
            resp = client.get(path)
        elif method == "PATCH":
            resp = client.patch(path, content=body, headers={"Content-Type": "application/json"})
        elif method == "DELETE":
            resp = client.delete(path)
        else:
            resp = client.post(path, content=body, headers={"Content-Type": "application/json"})

        assert resp.status_code in (401, 403), (
            f"{method} {path} expected 401/403, got {resp.status_code}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Public Join
# ═══════════════════════════════════════════════════════════════════════


class TestPublicJoin:
    """POST /api/v1/waitlist/join"""

    def test_successful_join_returns_201_and_referral_code(self, client):
        resp = client.post(f"{BASE}/join", json={
            "company_name": "Acme Logistics",
            "email": "hello@acme.com",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "joined"
        assert len(data["referral_code"]) >= 6

    def test_join_with_all_fields(self, client):
        resp = client.post(f"{BASE}/join", json={
            "company_name": "Full Fields Corp",
            "contact_name": "John Doe",
            "email": "john@fullfields.com",
            "fleet_size": "6-20",
            "company_size": "11-50",
            "country": "DE",
            "source": "google_ads",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "joined"

    def test_duplicate_email_returns_409(self, client, db):
        # Seed the entry
        _seed_entry(db, email="dup@test.com", referral_code="DUP12345")
        # Try to join with same email
        resp = client.post(f"{BASE}/join", json={
            "company_name": "Duplicate",
            "email": "dup@test.com",
        })
        assert resp.status_code == 409
        assert "already on the list" in resp.json()["detail"].lower()

    def test_duplicate_email_case_insensitive(self, client, db):
        _seed_entry(db, email="Case@Test.com", referral_code="CASE1234")
        resp = client.post(f"{BASE}/join", json={
            "company_name": "Case",
            "email": "case@test.com",
        })
        assert resp.status_code == 409

    def test_honeypot_returns_fake_success(self, client):
        """Honeypot field filled → fake success, no DB insert."""
        resp = client.post(f"{BASE}/join", json={
            "company_name": "Bot",
            "email": "bot-hp@evil.com",
            "hp_field": "I am a bot",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "joined"
        assert data["referral_code"].startswith("WLCM-")

        # Verify not in DB — same email can be registered for real
        resp2 = client.post(f"{BASE}/join", json={
            "company_name": "Bot",
            "email": "bot-hp@evil.com",
        })
        assert resp2.status_code == 201  # not duplicate, so it succeeded

    def test_rate_limit_exceeded(self, client):
        """After 5 rapid signups from same IP, 6th is rate-limited."""
        for i in range(5):
            resp = client.post(f"{BASE}/join", json={
                "company_name": f"Rate {i}",
                "email": f"rl{i}@test.com",
            })
            assert resp.status_code == 201, f"Signup {i} failed: {resp.text}"

        # 6th attempt
        resp = client.post(f"{BASE}/join", json={
            "company_name": "Rate Limit",
            "email": "rl-last@test.com",
        })
        assert resp.status_code == 429

    def test_missing_required_fields(self, client):
        resp = client.post(f"{BASE}/join", json={"email": "missing@name.com"})
        assert resp.status_code == 422

        resp = client.post(f"{BASE}/join", json={"company_name": "No Email"})
        assert resp.status_code == 422

    def test_missing_email(self, client):
        resp = client.post(f"{BASE}/join", json={
            "company_name": "No Email",
        })
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Admin: List Entries
# ═══════════════════════════════════════════════════════════════════════


class TestAdminListEntries:
    """GET /api/v1/waitlist/admin/entries"""

    def test_empty_list(self, client):
        resp = client.get(f"{BASE}/admin/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["entries"] == []

    def test_list_with_entries(self, client, db):
        _seed_entry(db, company_name="Alpha", email="alpha@test.com", referral_code="AAA111")
        _seed_entry(db, company_name="Beta", email="beta@test.com", referral_code="BBB222")

        resp = client.get(f"{BASE}/admin/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["entries"]) == 2

    def test_search_filter(self, client, db):
        _seed_entry(db, company_name="SearchCorp", email="find@test.com", referral_code="SRC001")
        _seed_entry(db, company_name="Other Inc", email="other@test.com", referral_code="OTH002")

        resp = client.get(f"{BASE}/admin/entries?search=SearchCorp")
        data = resp.json()
        assert data["total"] == 1
        assert data["entries"][0]["company_name"] == "SearchCorp"

        resp = client.get(f"{BASE}/admin/entries?search=find@")
        data = resp.json()
        assert data["total"] == 1

    def test_status_filter(self, client, db):
        _seed_entry(db, company_name="Joined Co", email="joined@test.com", referral_code="JND001")
        _seed_entry(db, company_name="Invited Co", email="invited@test.com", referral_code="INV002")

        # Manually update second to invited
        from backend.db import DatabaseManager
        from backend.desktop_config import Config
        d = DatabaseManager(Config.DB_PATH, pool_min=1, pool_max=2)
        d.conn.execute("UPDATE waitlist_entries SET status = 'invited', invited_at = datetime('now') WHERE referral_code = 'INV002'")
        d.conn.commit()
        d.close()

        resp = client.get(f"{BASE}/admin/entries?status=invited")
        data = resp.json()
        assert data["total"] == 1
        assert data["entries"][0]["referral_code"] == "INV002"

    def test_pagination(self, client, db):
        for i in range(5):
            _seed_entry(db, company_name=f"Page {i}", email=f"page{i}@test.com",
                        referral_code=f"PAG{i:03d}")

        resp = client.get(f"{BASE}/admin/entries?page=1&page_size=2")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["entries"]) == 2
        assert data["page"] == 1

        resp = client.get(f"{BASE}/admin/entries?page=3&page_size=2")
        data = resp.json()
        assert len(data["entries"]) == 1

    def test_date_filter(self, client, db):
        _seed_entry(db, company_name="Old", email="old@test.com", referral_code="OLD001")

        resp = client.get(f"{BASE}/admin/entries?date_from=2099-01-01")
        data = resp.json()
        assert data["total"] == 0


# ═══════════════════════════════════════════════════════════════════════
# Admin: Update Entry
# ═══════════════════════════════════════════════════════════════════════


class TestAdminUpdateEntry:
    """PATCH /api/v1/waitlist/admin/entries/{id}"""

    def test_update_status(self, client, db):
        eid = _seed_entry(db, company_name="Updatable", email="update@test.com", referral_code="UPD001")

        resp = client.patch(f"{BASE}/admin/entries/{eid}", json={"status": "invited"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "invited"
        assert data["invited_at"] is not None

    def test_update_notes(self, client, db):
        eid = _seed_entry(db, company_name="Notes", email="notes@test.com", referral_code="NTS001")

        resp = client.patch(f"{BASE}/admin/entries/{eid}", json={"notes": "Internal note"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Internal note"

    def test_invalid_transition_rejected(self, client, db):
        eid = _seed_entry(db, company_name="Bad Transition", email="bad@test.com", referral_code="BTR001")

        # joined → converted is invalid
        resp = client.patch(f"{BASE}/admin/entries/{eid}", json={"status": "converted"})
        assert resp.status_code == 422

    def test_admin_override_skips_state_machine(self, client, db):
        eid = _seed_entry(db, company_name="Override", email="override@test.com", referral_code="OVR001")

        resp = client.patch(f"{BASE}/admin/entries/{eid}", json={
            "status": "converted",
            "admin_override": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "converted"

    def test_status_timestamps(self, client, db):
        eid = _seed_entry(db, company_name="Timestamps", email="ts@test.com", referral_code="TSP001")

        # joined → invited → activated → converted
        resp = client.patch(f"{BASE}/admin/entries/{eid}", json={"status": "invited"})
        assert resp.json()["invited_at"] is not None

        resp = client.patch(f"{BASE}/admin/entries/{eid}", json={"status": "activated"})
        assert resp.json()["activated_at"] is not None

        resp = client.patch(f"{BASE}/admin/entries/{eid}", json={"status": "converted"})
        assert resp.json()["converted_at"] is not None

    def test_unsubscribe_sets_unsubscribed_at(self, client, db):
        eid = _seed_entry(db, company_name="Unsub", email="unsub@test.com", referral_code="UNS001")

        resp = client.patch(f"{BASE}/admin/entries/{eid}", json={"status": "unsubscribed"})
        assert resp.status_code == 200
        assert resp.json()["unsubscribed_at"] is not None

    def test_update_nonexistent_entry(self, client):
        resp = client.patch(f"{BASE}/admin/entries/99999", json={"status": "invited"})
        assert resp.status_code == 404

    def test_empty_update_noop(self, client, db):
        eid = _seed_entry(db, company_name="Noop", email="noop@test.com", referral_code="NOP001")
        resp = client.patch(f"{BASE}/admin/entries/{eid}", json={})
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# Admin: Delete Entry
# ═══════════════════════════════════════════════════════════════════════


class TestAdminDeleteEntry:
    """DELETE /api/v1/waitlist/admin/entries/{id}"""

    def test_delete_entry(self, client, db):
        eid = _seed_entry(db, company_name="Delete Me", email="delete@test.com", referral_code="DEL001")

        resp = client.delete(f"{BASE}/admin/entries/{eid}")
        assert resp.status_code == 204

        # Verify gone
        resp = client.get(f"{BASE}/admin/entries")
        assert resp.json()["total"] == 0

    def test_delete_nonexistent(self, client):
        resp = client.delete(f"{BASE}/admin/entries/99999")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Admin: Export CSV
# ═══════════════════════════════════════════════════════════════════════


class TestAdminExportCsv:
    """GET /api/v1/waitlist/admin/export.csv"""

    def test_export_empty(self, client):
        resp = client.get(f"{BASE}/admin/export.csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 1  # header only

    def test_export_with_data(self, client, db):
        _seed_entry(db, company_name="CSV Corp", email="csv@test.com", referral_code="CSV001")
        _seed_entry(db, company_name="Data Inc", email="data@test.com", referral_code="DAT002")

        resp = client.get(f"{BASE}/admin/export.csv")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 3  # header + 2 data rows
        assert rows[0][1] == "company_name"
        # Order is by joined_at DESC — both entries may have same timestamp
        names = {rows[1][1], rows[2][1]}
        assert "CSV Corp" in names
        assert "Data Inc" in names

    def test_export_respects_filters(self, client, db):
        _seed_entry(db, company_name="Keep", email="keep@test.com", referral_code="KEP001")
        _seed_entry(db, company_name="Skip", email="skip@test.com", referral_code="SKP002")

        resp = client.get(f"{BASE}/admin/export.csv?search=Keep")
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 2  # header + 1 data


# ═══════════════════════════════════════════════════════════════════════
# Admin: Stats
# ═══════════════════════════════════════════════════════════════════════


class TestAdminStats:
    """GET /api/v1/waitlist/admin/stats"""

    def test_stats_empty(self, client):
        resp = client.get(f"{BASE}/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["conversion_rate"] == 0.0
        assert data["by_status"] == {}

    def test_stats_with_data(self, client, db):
        _seed_entry(db, company_name="A", email="a@test.com", referral_code="STA001")
        _seed_entry(db, company_name="B", email="b@test.com", referral_code="STB002")
        _seed_entry(db, company_name="C", email="c@test.com", referral_code="STC003", source="referral")

        resp = client.get(f"{BASE}/admin/stats")
        data = resp.json()
        assert data["total"] == 3
        assert data["by_status"]["joined"] == 3
        assert "landing_page" in data["by_source"]

    def test_stats_conversion_rate(self, client, db):
        _seed_entry(db, company_name="C1", email="c1@test.com", referral_code="CON001")
        _seed_entry(db, company_name="C2", email="c2@test.com", referral_code="CON002")
        _seed_entry(db, company_name="C3", email="c3@test.com", referral_code="CON003")

        from backend.db import DatabaseManager
        from backend.desktop_config import Config
        d = DatabaseManager(Config.DB_PATH, pool_min=1, pool_max=2)
        d.conn.execute("UPDATE waitlist_entries SET status = 'converted', converted_at = datetime('now') WHERE referral_code = 'CON001'")
        d.conn.commit()
        d.close()

        resp = client.get(f"{BASE}/admin/stats")
        data = resp.json()
        assert data["total"] == 3
        assert data["by_status"]["converted"] == 1
        assert data["conversion_rate"] == pytest.approx(1 / 3)

    def test_stats_structure(self, client, db):
        _seed_entry(db, company_name="Stats", email="stats@test.com", referral_code="STS001",
                    country="US", company_size="11-50", fleet_size="6-20")

        resp = client.get(f"{BASE}/admin/stats")
        data = resp.json()
        assert "total" in data
        assert "by_status" in data
        assert "by_country" in data
        assert "by_company_size" in data
        assert "by_fleet_size" in data
        assert "by_source" in data
        assert "growth_daily" in data
        assert "conversion_rate" in data
        assert data["by_country"].get("US") == 1
        assert data["by_company_size"].get("11-50") == 1
        assert data["by_fleet_size"].get("6-20") == 1


# ═══════════════════════════════════════════════════════════════════════
# Admin: Campaign
# ═══════════════════════════════════════════════════════════════════════


class TestAdminCampaign:
    """POST /api/v1/waitlist/admin/campaign"""

    def test_campaign_no_recipients(self, client):
        resp = client.post(f"{BASE}/admin/campaign", json={
            "subject": "Test",
            "body": "Hello",
            "segment": "all",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "no_recipients"
        assert data["count"] == 0

    def test_campaign_sends_to_segment(self, client, db):
        _seed_entry(db, company_name="Campaign", email="campaign@test.com", referral_code="CAM001")

        resp = client.post(f"{BASE}/admin/campaign", json={
            "subject": "Welcome to Operion",
            "body": "Thank you for joining!",
            "segment": "all",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sent"
        assert data["count"] == 1

    def test_campaign_respects_segment_filter(self, client, db):
        _seed_entry(db, company_name="One", email="one@test.com", referral_code="SEG001")
        _seed_entry(db, company_name="Two", email="two@test.com", referral_code="SEG002")

        from backend.db import DatabaseManager
        from backend.desktop_config import Config
        d = DatabaseManager(Config.DB_PATH, pool_min=1, pool_max=2)
        d.conn.execute("UPDATE waitlist_entries SET status = 'invited', invited_at = datetime('now') WHERE referral_code = 'SEG002'")
        d.conn.commit()
        d.close()

        # Only send to 'invited' segment
        resp = client.post(f"{BASE}/admin/campaign", json={
            "subject": "Invite",
            "body": "You're invited!",
            "segment": "invited",
        })
        data = resp.json()
        assert data["count"] == 1
        assert data["total_recipients"] == 1

    def test_campaign_unsubscribed_excluded(self, client, db):
        _seed_entry(db, company_name="Active", email="active@test.com", referral_code="ACT001")
        _seed_entry(db, company_name="Unsub", email="unsub@test.com", referral_code="USB002")

        from backend.db import DatabaseManager
        from backend.desktop_config import Config
        d = DatabaseManager(Config.DB_PATH, pool_min=1, pool_max=2)
        d.conn.execute("UPDATE waitlist_entries SET status = 'unsubscribed', unsubscribed_at = datetime('now') WHERE referral_code = 'USB002'")
        d.conn.commit()
        d.close()

        resp = client.post(f"{BASE}/admin/campaign", json={
            "subject": "Test",
            "body": "Body",
            "segment": "all",
        })
        data = resp.json()
        assert data["count"] == 1  # Only the active entry

    def test_campaign_invalid_segment(self, client):
        resp = client.post(f"{BASE}/admin/campaign", json={
            "subject": "Test",
            "body": "Body",
            "segment": "nonexistent",
        })
        assert resp.status_code == 422

    def test_campaign_missing_subject(self, client):
        resp = client.post(f"{BASE}/admin/campaign", json={
            "body": "Body",
        })
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# Public: Unsubscribe
# ═══════════════════════════════════════════════════════════════════════


class TestUnsubscribe:
    """GET /api/v1/waitlist/unsubscribe/{token}"""

    def test_unsubscribe_stub(self, client):
        resp = client.get(f"{BASE}/unsubscribe/test-token-123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "unsubscribed"


# ═══════════════════════════════════════════════════════════════════════
# Public: Live Counter
# ═══════════════════════════════════════════════════════════════════════


class TestWaitlistCount:
    """GET /api/v1/waitlist/count — blueprint §11.4 live counter."""

    @pytest.fixture(autouse=True)
    def _reset_count_cache(self):
        from backend.api.v1.waitlist import _count_cache
        _count_cache["count"] = 0
        _count_cache["cached_at"] = None
        yield
        _count_cache["count"] = 0
        _count_cache["cached_at"] = None

    def test_count_zero_when_empty(self, client):
        resp = client.get(f"{BASE}/count")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["cached_at"] is not None

    def test_count_counts_real_signups(self, client):
        for i in range(3):
            r = client.post(f"{BASE}/join", json={
                "company_name": f"Count {i}",
                "email": f"count{i}@test.com",
            })
            assert r.status_code == 201

        resp = client.get(f"{BASE}/count")
        assert resp.status_code == 200
        assert resp.json()["count"] == 3

    def test_count_excludes_churned_and_unsubscribed(self, client, db):
        _seed_entry(db, company_name="Active", email="active@test.com", referral_code="ACC001")
        _seed_entry(db, company_name="Gone", email="gone@test.com", referral_code="GON002")
        db.conn.execute("UPDATE waitlist_entries SET status = 'churned' WHERE referral_code = 'GON002'")
        db.conn.commit()

        resp = client.get(f"{BASE}/count")
        data = resp.json()
        assert data["count"] == 1

    def test_count_is_cached_within_ttl(self, client, db):
        _seed_entry(db, company_name="Cached", email="cached@test.com", referral_code="CAC001")
        resp = client.get(f"{BASE}/count")
        assert resp.json()["count"] == 1

        # Change the underlying data directly — cached answer must be served.
        db.conn.execute("DELETE FROM waitlist_entries")
        db.conn.commit()
        resp = client.get(f"{BASE}/count")
        assert resp.json()["count"] == 1  # still the cached value

    def test_count_refreshes_after_join(self, client):
        r = client.post(f"{BASE}/join", json={
            "company_name": "Fresh",
            "email": "fresh@test.com",
        })
        assert r.status_code == 201
        resp = client.get(f"{BASE}/count")
        assert resp.json()["count"] == 1


# ═══════════════════════════════════════════════════════════════════════
# Referral fraud prevention (blueprint §18b.2)
# ═══════════════════════════════════════════════════════════════════════


class TestReferralFraud:
    """Self-referral rejection + per-code daily redemption rate limit."""

    @pytest.fixture(autouse=True)
    def _reset_referral_state(self):
        from backend.api.v1.waitlist import _referral_redemptions
        from backend.utils.rate_limit import _fallback
        _referral_redemptions.clear()
        _fallback.clear()
        yield
        _referral_redemptions.clear()
        _fallback.clear()

    def _join(self, client, email, referred_by=None):
        payload = {"company_name": "Referral Co", "email": email}
        if referred_by:
            payload["referred_by"] = referred_by
        return client.post(f"{BASE}/join", json=payload)

    def test_self_referral_rejected(self, client):
        resp = self._join(client, "self.test@example.com")
        assert resp.status_code == 201
        code = resp.json()["referral_code"]

        # Same person, Gmail-style normalized email (dots ignored).
        resp = self._join(client, "selftest@example.com", referred_by=code)
        assert resp.status_code == 400
        assert resp.json()["detail"]["error_code"] == "referral/self-referral"

    def test_self_referral_exact_same_email_blocked_by_duplicate(self, client):
        resp = self._join(client, "self2@example.com")
        code = resp.json()["referral_code"]
        resp = self._join(client, "self2@example.com", referred_by=code)
        # Exact duplicate email is caught earlier by the 409 duplicate check.
        assert resp.status_code == 409

    def test_unknown_referral_code_rejected(self, client):
        resp = self._join(client, "nobody@example.com", referred_by="NOPE1234")
        assert resp.status_code == 400
        assert resp.json()["detail"]["error_code"] == "referral/invalid-code"

    def test_valid_referral_is_redeemed_and_logged(self, client):
        resp = self._join(client, "ref.redeem@example.com")
        assert resp.status_code == 201
        code = resp.json()["referral_code"]

        resp = self._join(client, "redeemer@example.com", referred_by=code)
        assert resp.status_code == 201
        assert resp.json()["referral_code"] != code

    def test_redemption_rate_limit_429(self, client):
        resp = self._join(client, "referrer@example.com")
        code = resp.json()["referral_code"]

        # 10 redemptions allowed per code per day…
        for i in range(10):
            from backend.utils.rate_limit import _fallback
            _fallback.clear()
            r = self._join(client, f"redeem{i}@example.com", referred_by=code)
            assert r.status_code == 201, f"redemption {i} failed: {r.text}"

        # …the 11th is rate-limited.
        from backend.utils.rate_limit import _fallback
        _fallback.clear()
        r = self._join(client, "redeem-last@example.com", referred_by=code)
        assert r.status_code == 429
        assert r.json()["detail"]["error_code"] == "rate-limited"

    def test_referral_does_not_consume_without_code(self, client):
        resp = self._join(client, "nocode@example.com")
        assert resp.status_code == 201
