"""Tests for repositories.settings_repository — settings CRUD.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.settings_repository import SettingsRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    from database.tenant_context import set_request_context
    db = InMemoryDB()
    # Seed a company row so FK constraints pass
    db.conn.execute("INSERT OR IGNORE INTO companies (id, company_name) VALUES (1, 'Test Company')")
    db.conn.commit()
    # Simulate a company-scoped user so that repository methods behave
    # like production (company_id is always set in the composite PK).
    set_request_context(1, "")
    return db


@pytest.fixture
def repo(db) -> SettingsRepository:
    return SettingsRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _setting(db: InMemoryDB, key: str, value: str) -> None:
    from database.tenant_context import get_company_id
    cid = get_company_id()
    if cid is not None:
        db.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, company_id) VALUES (?, ?, ?)",
            (key, value, cid),
        )
    else:
        db.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    db.conn.commit()


# ── Get settings by keys ─────────────────────────────────────────────


class TestGetSettingsByKeys:
    def test_returns_requested_keys(self, db, repo):
        _setting(db, "app.name", "Operion")
        _setting(db, "app.version", "1.0")
        result = repo.get_settings_by_keys(["app.name", "app.version"])
        assert result == {"app.name": "Operion", "app.version": "1.0"}

    def test_returns_empty_for_unknown_keys(self, repo):
        result = repo.get_settings_by_keys(["nonexistent.one", "nonexistent.two"])
        assert result == {}


# ── Get by key pattern ───────────────────────────────────────────────


class TestGetSettingsByKeyPattern:
    def test_like_pattern(self, db, repo):
        _setting(db, "ui.theme", "dark")
        _setting(db, "ui.language", "en")
        _setting(db, "app.version", "1.0")
        result = repo.get_settings_by_key_pattern("ui.%")
        assert result == {"ui.theme": "dark", "ui.language": "en"}


# ── Get single value ─────────────────────────────────────────────────


class TestGetSettingValue:
    def test_returns_value(self, db, repo):
        _setting(db, "app.timezone", "UTC")
        assert repo.get_setting_value("app.timezone") == "UTC"

    def test_returns_none_for_missing(self, repo):
        assert repo.get_setting_value("does.not.exist") is None


# ── Upsert ───────────────────────────────────────────────────────────


class TestUpsertSetting:
    def test_inserts_new(self, db, repo):
        repo.upsert_setting("feature.x.enabled", "true")
        row = db.conn.execute(
            "SELECT value FROM settings WHERE key = ?", ("feature.x.enabled",)
        ).fetchone()
        assert row is not None
        assert row["value"] == "true"

    def test_overwrites_existing(self, db, repo):
        _setting(db, "app.debug", "false")
        repo.upsert_setting("app.debug", "true")
        row = db.conn.execute(
            "SELECT value FROM settings WHERE key = ?", ("app.debug",)
        ).fetchone()
        assert row["value"] == "true"


# ── Update ───────────────────────────────────────────────────────────


class TestUpdateSetting:
    def test_updates_value(self, db, repo):
        _setting(db, "app.maintenance", "false")
        repo.update_setting("app.maintenance", "true")
        row = db.conn.execute(
            "SELECT value FROM settings WHERE key = ?", ("app.maintenance",)
        ).fetchone()
        assert row["value"] == "true"
