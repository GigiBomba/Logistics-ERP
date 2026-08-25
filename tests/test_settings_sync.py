"""Tests for Phase D — settings sync (company config + SMTP + preferences).

Covers ``SettingsSyncService``:
- push sends the local curated keys to the fake ApiClient
- machine-local keys (window geometry etc.) are excluded
- per-key error resilience (one bad key never aborts the rest)
- pull writes server keys locally via PreferencesManager
- echo suppression: writing pulled settings creates NO outbox rows
  (settings is not in SYNCABLE_ENTITIES → no capture triggers)
- conflict policy: LWW per key (no updated_at on the settings table),
  pull-priority (push first, then pull overwrites on a tie)
"""
from __future__ import annotations

import os
import tempfile

import pytest

from database.db_manager import DatabaseManager
from services.preferences import PreferencesManager
from services.settings_sync_service import (
    COMPANY_CONFIG_SYNC_KEYS,
    SYNCABLE_KV_SETTING_KEYS,
    SettingsSyncService,
)
from services.sync_outbox_service import SyncOutboxService


class FakeApiClient:
    """Records settings API calls; ``save_setting`` can be made to fail."""

    def __init__(self, saved=None, company_config=None, fail_keys=()):
        self.saved = saved or {}
        self.company_config = company_config or {}
        self.fail_keys = set(fail_keys)
        self.save_calls = []           # (key, value)
        self.bulk_keys = []
        self.company_push_calls = []
        self.company_pull_calls = 0

    def save_setting(self, key, value):
        if key in self.fail_keys:
            raise RuntimeError(f"boom: {key}")
        self.save_calls.append((key, value))
        self.saved[key] = value
        return {"status": "saved"}

    def get_settings_bulk(self, keys):
        self.bulk_keys.append(list(keys))
        return {"values": {k: self.saved.get(k) for k in keys}}

    def save_company_config(self, data):
        self.company_push_calls.append(dict(data))
        self.company_config.update(data)
        return {"status": "saved"}

    def get_company_config(self):
        self.company_pull_calls += 1
        return dict(self.company_config)


@pytest.fixture
def db_path():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def db(db_path):
    _db = DatabaseManager(db_path)
    for cid in range(0, 101):
        _db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
            "VALUES (?, ?, 'starter')",
            (cid, f"Company-{cid}"),
        )
    _db.conn.commit()
    yield _db
    try:
        _db.close()
    except Exception:
        pass


def _save_local_prefs(db, **values):
    prefs = PreferencesManager(db)
    for k, v in values.items():
        prefs.save_setting(k, v)
    return prefs


class TestPush:
    def test_push_sends_local_keys(self, db):
        fake = FakeApiClient()
        _save_local_prefs(
            db,
            smtp_server="smtp.test.com",
            smtp_port="587",
            smtp_user="user@test.com",
            smtp_password="secret",
            alert_email_recipients="ops@test.com",
            pref_language="ro",
            pref_currency="RON",
        )
        svc = SettingsSyncService(db, fake)
        count = svc.push_settings()

        sent = dict(fake.save_calls)
        assert sent.get("smtp_server") == "smtp.test.com"
        assert sent.get("smtp_port") == "587"
        assert sent.get("smtp_user") == "user@test.com"
        assert sent.get("smtp_password") == "secret"
        assert sent.get("alert_email_recipients") == "ops@test.com"
        assert sent.get("pref_language") == "ro"
        assert sent.get("pref_currency") == "RON"
        assert count >= len(SYNCABLE_KV_SETTING_KEYS)

    def test_machine_local_keys_excluded(self, db):
        """Window geometry / last-opened etc. must never be pushed."""
        fake = FakeApiClient()
        _save_local_prefs(
            db,
            smtp_server="smtp.test.com",
            window_geometry="1000x800+10+10",
            theme="dark",
            last_opened_file="C:/secret/path/invoice.pdf",
        )
        svc = SettingsSyncService(db, fake)
        svc.push_settings()

        sent_keys = {k for k, _ in fake.save_calls}
        assert sent_keys == {"smtp_server"}
        assert "window_geometry" not in sent_keys
        assert "theme" not in sent_keys
        assert "last_opened_file" not in sent_keys

    def test_per_key_error_resilience(self, db):
        """A failing key must not abort the rest of the push."""
        fake = FakeApiClient(fail_keys={"smtp_user"})
        _save_local_prefs(
            db,
            smtp_server="smtp.test.com",
            smtp_port="587",
            smtp_user="user@test.com",
            smtp_password="secret",
        )
        svc = SettingsSyncService(db, fake)
        count = svc.push_settings()

        sent = dict(fake.save_calls)
        # smtp_user failed; the others went through.
        assert "smtp_user" not in sent
        assert sent.get("smtp_server") == "smtp.test.com"
        assert sent.get("smtp_password") == "secret"
        assert count >= 3

    def test_push_company_config_filtered_to_syncable_keys(self, db, monkeypatch):
        """Company config push only sends the server-whitelisted syncable keys.

        S3: logo_path/signature_path/stamp_path are MACHINE-LOCAL file paths
        (no binary download exists) — they are NOT synced; the server keeps
        its own copy and each device manages its own branding files.
        """
        fake = FakeApiClient()
        import services.invoicing.config_manager as cm

        monkeypatch.setattr(
            cm,
            "load_company_config",
            lambda: {
                "company_name": "Test SRL",
                "cui": "RO123",
                "reg_number": "J1/1/2000",
                "address": "Str. X",
                "county": "Bucuresti",   # local-only — must be dropped
                "iban": "RO99...",       # local-only — must be dropped
                "phone": "0721",
                "email": "office@test.com",
                "company_color": "#6366f1",
                "logo_path": "C:/data/logo.png",      # machine-local — dropped
                "signature_path": "C:/data/sig.png",  # machine-local — dropped
                "stamp_path": "C:/data/stamp.png",    # machine-local — dropped
            },
        )
        svc = SettingsSyncService(db, fake)
        svc.push_settings()

        assert fake.company_push_calls
        pushed = fake.company_push_calls[0]
        assert pushed.get("company_name") == "Test SRL"
        assert pushed.get("cui") == "RO123"
        assert pushed.get("reg_number") == "J1/1/2000"
        assert pushed.get("phone") == "0721"
        assert pushed.get("email") == "office@test.com"
        assert pushed.get("company_color") == "#6366f1"
        # Machine-local / local-only keys are never pushed.
        assert "county" not in pushed
        assert "iban" not in pushed
        assert "logo_path" not in pushed
        assert "signature_path" not in pushed
        assert "stamp_path" not in pushed
        # Only whitelisted syncable keys are sent.
        assert set(pushed.keys()) <= set(COMPANY_CONFIG_SYNC_KEYS)

    def test_push_company_config_merges_into_server_config(self, db, monkeypatch):
        """S3: the push MERGES syncable keys into the server config — keys the
        device does not send (county/iban/bank, or a key left empty) survive."""
        fake = FakeApiClient(company_config={
            "company_name": "Server SRL",
            "county": "Ilfov",        # server-only — must survive
            "iban": "RO88SERVER",     # server-only — must survive
        })
        import services.invoicing.config_manager as cm

        monkeypatch.setattr(
            cm,
            "load_company_config",
            lambda: {
                "company_name": "Test SRL",   # device value wins
                "cui": "RO123",
                "address": "Str. X",
                "email": "office@test.com",
            },
        )
        svc = SettingsSyncService(db, fake)
        svc.push_settings()

        assert fake.company_push_calls
        pushed = fake.company_push_calls[0]
        assert pushed.get("company_name") == "Test SRL"   # device wins
        assert pushed.get("county") == "Ilfov"            # server-only survived
        assert pushed.get("iban") == "RO88SERVER"         # server-only survived
        assert pushed.get("cui") == "RO123"


class TestPull:
    def test_pull_writes_server_keys_locally(self, db):
        fake = FakeApiClient(
            saved={
                "smtp_server": "smtp.cloud.com",
                "smtp_port": "465",
                "smtp_user": "cloud@test.com",
                "smtp_password": "cloud-secret",
                "pref_language": "en",
                "pref_currency": "EUR",
            },
            company_config={
                "company_name": "Cloud SRL",
                "cui": "RO999",
                "address": "Str. Cloud 1",
                "email": "cloud@test.com",
            },
        )
        svc = SettingsSyncService(db, fake)
        count = svc.pull_settings()

        prefs = PreferencesManager(db)
        assert prefs.get_setting("smtp_server") == "smtp.cloud.com"
        assert prefs.get_setting("smtp_port") == "465"
        assert prefs.get_setting("smtp_user") == "cloud@test.com"
        assert prefs.get_setting("smtp_password") == "cloud-secret"
        assert prefs.get_setting("pref_language") == "en"
        assert count >= 6

        # Company config merged into the local JSON file (atomic write).
        import services.invoicing.config_manager as cm

        local = cm.load_company_config()
        assert local.get("company_name") == "Cloud SRL"
        assert local.get("cui") == "RO999"
        assert local.get("address") == "Str. Cloud 1"
        assert local.get("email") == "cloud@test.com"

    def test_pull_missing_server_keys_do_not_clobber_local(self, db):
        fake = FakeApiClient(saved={"smtp_server": "smtp.cloud.com"})
        _save_local_prefs(db, smtp_user="local-user@test.com")
        svc = SettingsSyncService(db, fake)
        svc.pull_settings()

        prefs = PreferencesManager(db)
        # smtp_server came from the server; smtp_user was not in the server
        # response (None) so the local value survived.
        assert prefs.get_setting("smtp_server") == "smtp.cloud.com"
        assert prefs.get_setting("smtp_user") == "local-user@test.com"

    def test_pull_creates_no_outbox_rows(self, db):
        """Echo suppression: settings writes have no outbox triggers."""
        fake = FakeApiClient(saved={"smtp_server": "smtp.cloud.com"})
        svc = SettingsSyncService(db, fake)
        svc.pull_settings()

        outbox = SyncOutboxService(db)
        assert outbox.pending() == []


class TestEngineWiring:
    def test_engine_skips_settings_phase_without_support(self, db):
        """A fake ApiClient without settings methods must not break sync."""
        from services.sync_engine import SyncEngine
        from services.sync_outbox_service import SyncOutboxService
        from services.sync_pull_service import SyncPullService

        class MinimalFake:
            online = True

            def is_online(self):
                return True

            def post(self, path, json=None):
                return {"results": []}

            def get(self, path, params=None):
                return {"records": [], "next_after_id": 0, "has_more": False}

        fake = MinimalFake()
        outbox = SyncOutboxService(db)
        pull = SyncPullService(db, fake)
        engine = SyncEngine(db, fake, outbox, pull)
        engine.sync_once()  # must not raise (settings/reconcile phases skipped)


# ── B4: server settings endpoints are company-scoped ──────────────────────


class _ServerClient:
    def __init__(self, db, company_id):
        from fastapi.testclient import TestClient
        from backend.dependencies import get_db
        from backend.dependencies_security import get_current_user
        from backend.main import create_app

        app = create_app()

        async def _override_get_db():
            yield db

        app.dependency_overrides[get_db] = _override_get_db

        async def _mock_user():
            return {
                "id": 1, "email": f"u{company_id}@t.com", "role": "admin",
                "is_admin": True, "company_id": company_id,
            }

        app.dependency_overrides[get_current_user] = _mock_user
        self.client = TestClient(app)
        self.company_id = company_id


class TestServerCompanyScoping:
    def test_settings_are_company_scoped(self, db):
        """B4: GET/PATCH /settings/{key} and GET /settings/bulk must only see
        the caller's company — a cross-tenant SMTP leak would expose decrypted
        credentials."""
        c1 = _ServerClient(db, 1)
        c2 = _ServerClient(db, 2)

        # Company 1 sets smtp_server; company 2 sets a DIFFERENT value.
        r = c1.client.patch(
            "/api/v1/settings/smtp_server", json={"value": "smtp.company1.com"},
        )
        assert r.status_code == 200, r.text
        r = c2.client.patch(
            "/api/v1/settings/smtp_server", json={"value": "smtp.company2.com"},
        )
        assert r.status_code == 200, r.text

        # Each company reads back ONLY its own value.
        r1 = c1.client.get("/api/v1/settings/smtp_server")
        assert r1.status_code == 200
        assert r1.json()["value"] == "smtp.company1.com"
        r2 = c2.client.get("/api/v1/settings/smtp_server")
        assert r2.status_code == 200
        assert r2.json()["value"] == "smtp.company2.com"

        # Bulk GET is company-scoped too.
        bulk1 = c1.client.get("/api/v1/settings/bulk", params={"keys": "smtp_server,smtp_user"})
        assert bulk1.json()["values"] == {"smtp_server": "smtp.company1.com", "smtp_user": None}
        bulk2 = c2.client.get("/api/v1/settings/bulk", params={"keys": "smtp_server,smtp_user"})
        assert bulk2.json()["values"] == {"smtp_server": "smtp.company2.com", "smtp_user": None}

        # The settings rows carry each company's id (never NULL).
        rows = db.conn.execute(
            "SELECT key, value, company_id FROM settings WHERE key = 'smtp_server'"
        ).fetchall()
        assert {(r["company_id"], r["value"]) for r in rows} == {
            (1, "smtp.company1.com"), (2, "smtp.company2.com"),
        }
