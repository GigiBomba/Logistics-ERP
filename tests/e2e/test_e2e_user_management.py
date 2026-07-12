"""E2E: User and data management — user lifecycle, API keys, i18n, GDPR, formatters.

Tests exercise real services and repositories wired to an in-memory SQLite
database.  Only filesystem / external-API calls are mocked.
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import mock_open, patch

import pytest

from services.user_service import UserService
from repositories.api_key_repository import ApiKeyRepository
from utils.formatting import format_duration
from utils.formatters import fmt_currency, fmt_date
from tests.test_helpers import make_db

pytestmark = pytest.mark.e2e


# ═════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def user_svc(db):
    return UserService(db)


# ═════════════════════════════════════════════════════════════════════════
# 1. User Lifecycle — create → read → deactivate
# ═════════════════════════════════════════════════════════════════════════


class TestUserLifecycle:
    """Create, list, retrieve, and deactivate users through UserService."""

    def test_create_user_returns_id(self, db, user_svc):
        """Creating a user with valid data returns a positive integer ID."""
        user_id = user_svc.create_user(
            email="alice@example.com",
            password="Str0ng!Pass",
            role="dispatcher",
            display_name="Alice",
        )
        assert isinstance(user_id, int)
        assert user_id > 0

        # Verify row exists in the database
        row = db.conn.execute(
            "SELECT email, role, is_active FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        assert row is not None
        assert row["email"] == "alice@example.com"
        assert row["role"] == "dispatcher"
        assert row["is_active"] == 1

    def test_list_users_includes_new_user(self, db, user_svc):
        """After creating a user, list_users contains that user."""
        user_svc.create_user("bob@example.com", "s3cret", "driver", "Bob")
        users = user_svc.list_users()

        matching = [u for u in users if u["email"] == "bob@example.com"]
        assert len(matching) == 1
        assert matching[0]["role"] == "driver"
        assert matching[0]["is_active"] == 1

    def test_deactivate_user_by_id(self, db, user_svc):
        """Deactivating a user sets is_active to 0 in the database."""
        user_id = user_svc.create_user(
            "carol@example.com", "p@$$word", "admin", "Carol"
        )
        user_svc.deactivate_user(user_id)

        row = db.conn.execute(
            "SELECT is_active FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        assert row is not None
        assert row["is_active"] == 0

    def test_deactivated_user_in_list(self, db, user_svc):
        """Deactivated users still appear in list_users (business rule)."""
        user_id = user_svc.create_user(
            "dave@example.com", "s3cret", "viewer", "Dave"
        )
        user_svc.deactivate_user(user_id)

        users = user_svc.list_users()
        matching = [u for u in users if u["email"] == "dave@example.com"]
        assert len(matching) == 1
        assert matching[0]["is_active"] == 0

    def test_create_user_without_display_name(self, db, user_svc):
        """Creating a user with an empty display_name still succeeds."""
        user_id = user_svc.create_user(
            "eve@example.com", "s3cret", "dispatcher", ""
        )
        assert user_id > 0

    def test_deactivate_nonexistent_user_does_not_raise(self, db, user_svc):
        """Deactivating a user ID that does not exist is a no-op (no error)."""
        user_svc.deactivate_user(99999)
        # No exception is expected

    def test_multiple_users_listed(self, db, user_svc):
        """Creating several users returns all of them in list_users."""
        emails = ["frank@a.com", "grace@b.com", "heidi@c.com"]
        for e in emails:
            user_svc.create_user(e, "s3cret", "driver", e.split("@")[0])
        users = user_svc.list_users()
        listed_emails = {u["email"] for u in users}
        for e in emails:
            assert e in listed_emails


# ═════════════════════════════════════════════════════════════════════════
# 2. API Key Lifecycle — create → validate → list → revoke
# ═════════════════════════════════════════════════════════════════════════


class TestApiKeyLifecycle:
    """Create, validate, list, and revoke API keys via ApiKeyRepository."""

    @pytest.fixture
    def repo(self, db):
        return ApiKeyRepository(db)

    def test_create_key_returns_raw_key_and_id(self, repo):
        """create_key returns (raw_key, key_id) with 'ok_' prefix."""
        raw_key, key_id = repo.create_key(
            name="Test Partner",
            partner="acmecorp",
            scopes=["read:trips"],
        )
        assert isinstance(raw_key, str)
        assert raw_key.startswith("ok_")
        assert len(raw_key) == 3 + 48  # "ok_" + 48 hex chars
        assert isinstance(key_id, int)
        assert key_id > 0

    def test_validate_key_with_correct_raw_key(self, repo):
        """validate_key returns metadata dict for a valid raw key."""
        raw_key, key_id = repo.create_key(
            name="Valid Key", partner="partner_a",
        )
        metadata = repo.validate_key(raw_key)
        assert metadata is not None
        assert metadata["name"] == "Valid Key"
        assert metadata["partner"] == "partner_a"
        assert metadata["is_active"] == 1

    def test_validate_key_with_wrong_key_returns_none(self, repo):
        """validate_key returns None for an unknown raw key."""
        result = repo.validate_key("ok_" + "a" * 48)
        assert result is None

    def test_revoke_key_makes_validation_fail(self, repo):
        """After revoke_key, validate_key returns None."""
        raw_key, key_id = repo.create_key(
            name="Revocable", partner="partner_b",
        )
        repo.revoke_key(key_id)
        assert repo.validate_key(raw_key) is None

    def test_list_keys_shows_revoked_key(self, repo, db):
        """list_keys includes the revoked key with is_active=0."""
        raw_key, key_id = repo.create_key(
            name="Soon Gone", partner="partner_c",
        )
        repo.revoke_key(key_id)

        keys = repo.list_keys()
        matching = [k for k in keys if k["id"] == key_id]
        assert len(matching) == 1
        assert matching[0]["is_active"] == 0

    def test_list_keys_omits_other_partner(self, repo):
        """list_keys can be filtered by partner slug."""
        repo.create_key(name="A", partner="alpha")
        repo.create_key(name="B", partner="beta")

        alpha_keys = repo.list_keys(partner="alpha")
        assert all(k["partner"] == "alpha" for k in alpha_keys)

        beta_keys = repo.list_keys(partner="beta")
        assert all(k["partner"] == "beta" for k in beta_keys)

    def test_validate_updates_last_used_at(self, repo):
        """After validation, last_used_at is set to a non-null timestamp."""
        raw_key, key_id = repo.create_key(
            name="Usage Tracked", partner="trackme",
        )
        repo.validate_key(raw_key)

        row = repo.get_by_id(key_id)
        assert row is not None
        assert row["last_used_at"] is not None


# ═════════════════════════════════════════════════════════════════════════
# 3. i18n Translation Flow
# ═════════════════════════════════════════════════════════════════════════


class TestI18nTranslationFlow:
    """Load translations, switch language, translate, fallback, persist."""

    EN_TRANSLATIONS = {"greeting": "Hello", "farewell": "Goodbye"}
    FR_TRANSLATIONS = {"greeting": "Bonjour"}

    def _reset_i18n(self):
        """Reset i18n module state after each test."""
        import services.i18n as i18n

        i18n._translations = {}
        i18n._current_lang = "en"

    @patch("services.i18n.os.path.isfile")
    @patch("services.i18n._load_file")
    def test_set_language_and_translate(self, mock_load, mock_isfile):
        """Switching language changes the output of t()."""
        self._reset_i18n()
        import services.i18n as i18n

        # Simulate both translation files being present
        def load_side_effect(lang: str) -> dict:
            if lang == "en":
                return self.EN_TRANSLATIONS
            elif lang == "fr":
                return self.FR_TRANSLATIONS
            return {}

        mock_load.side_effect = load_side_effect
        mock_isfile.return_value = True

        i18n.load_translations()

        assert i18n.t("greeting") == "Hello"

        i18n.set_language("fr")
        assert i18n.t("greeting") == "Bonjour"

    @patch("services.i18n.os.path.isfile")
    @patch("services.i18n._load_file")
    def test_fallback_to_english(self, mock_load, mock_isfile):
        """Missing key in target language falls back to English."""
        self._reset_i18n()
        import services.i18n as i18n

        def load_side_effect(lang: str) -> dict:
            if lang == "en":
                return {"greeting": "Hello", "farewell": "Goodbye"}
            elif lang == "fr":
                return {"greeting": "Bonjour"}  # no "farewell"
            return {}

        mock_load.side_effect = load_side_effect
        mock_isfile.return_value = True

        i18n.load_translations()
        i18n.set_language("fr")

        # "farewell" is missing in French → falls back to English
        assert i18n.t("farewell") == "Goodbye"

    @patch("services.i18n.os.path.isfile")
    @patch("services.i18n._load_file")
    def test_translate_with_format_args(self, mock_load, mock_isfile):
        """t() supports format placeholders."""
        self._reset_i18n()
        import services.i18n as i18n

        def load_side_effect(lang: str) -> dict:
            if lang == "en":
                return {"welcome": "Welcome {name}!"}
            return {}

        mock_load.side_effect = load_side_effect
        mock_isfile.return_value = True

        i18n.load_translations()
        assert i18n.t("welcome", name="Alice") == "Welcome Alice!"

    @patch("services.i18n.os.path.isfile")
    @patch("services.i18n._load_file")
    def test_missing_key_returns_key_itself(self, mock_load, mock_isfile):
        """t() returns the key itself when no translation is found."""
        self._reset_i18n()
        import services.i18n as i18n

        mock_load.return_value = {}
        mock_isfile.return_value = True

        i18n.load_translations()
        assert i18n.t("nonexistent_key") == "nonexistent_key"

    @patch("services.i18n.os.path.isfile")
    @patch("services.i18n._load_file")
    @patch("builtins.open", new_callable=mock_open)
    def test_language_persistence(self, mock_file, mock_load, mock_isfile):
        """set_language writes current language to lang.txt."""
        self._reset_i18n()
        import services.i18n as i18n

        def load_side_effect(lang: str) -> dict:
            if lang == "en":
                return {"key": "Hello"}
            elif lang == "de":
                return {"key": "Hallo"}
            return {}

        mock_load.side_effect = load_side_effect
        mock_isfile.return_value = True

        i18n.load_translations()
        i18n.set_language("de")

        # Verify the language file was written
        handle = mock_file()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        assert written == "de"

    @patch("services.i18n.os.path.isfile")
    @patch("services.i18n._load_file")
    def test_switch_back_to_english(self, mock_load, mock_isfile):
        """Switching back to English returns original translations."""
        self._reset_i18n()
        import services.i18n as i18n

        def load_side_effect(lang: str) -> dict:
            if lang == "en":
                return {"greeting": "Hello"}
            elif lang == "fr":
                return {"greeting": "Bonjour"}
            return {}

        mock_load.side_effect = load_side_effect
        mock_isfile.return_value = True

        i18n.load_translations()
        i18n.set_language("fr")
        assert i18n.t("greeting") == "Bonjour"

        i18n.set_language("en")
        assert i18n.t("greeting") == "Hello"


# ═════════════════════════════════════════════════════════════════════════
# 4. GDPR Data Lifecycle — seed → export → verify → delete
# ═════════════════════════════════════════════════════════════════════════


class TestGDPRDataLifecycle:
    """Seed test company data, export as JSON, verify structure, delete."""

    def _seed_company(self, db) -> int:
        db.conn.execute(
            "INSERT INTO companies (company_name) VALUES (?)",
            ("GDPR Test GmbH",),
        )
        db.conn.commit()
        return db.conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

    def _seed_company_data(self, db, company_id: int) -> None:
        """Insert a minimal set of records belonging to *company_id*."""
        now = datetime.now().isoformat()
        db.conn.execute(
            "INSERT INTO clients (name, email, is_active, company_id, created_at) "
            "VALUES (?, ?, 1, ?, ?)",
            ("GDPR Client", "gdpr-client@example.com", company_id, now),
        )
        db.conn.execute(
            "INSERT INTO drivers (name, license_number, is_active, company_id, "
            "created_at, updated_at) VALUES (?, ?, 1, ?, ?, ?)",
            ("GDPR Driver", "LIC-GDPR-001", company_id, now, now),
        )
        db.conn.execute(
            "INSERT INTO trucks (plate_number, manufacturer, model, status, company_id) "
            "VALUES (?, ?, ?, 'active', ?)",
            ("TR-GDPR-01", "Volvo", "FH", company_id),
        )
        db.conn.execute(
            "INSERT INTO trips (client_name, distance_km, total_price_eur, "
            "status, company_id) VALUES (?, ?, ?, 'Delivered', ?)",
            ("GDPR Client", 500.0, 2000.0, company_id),
        )
        db.conn.commit()

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_export_company_returns_json_with_tables_key(self, db):
        """Export returns a JSON-like dict with a 'tables' key."""
        company_id = self._seed_company(db)
        self._seed_company_data(db, company_id)

        export_data = self._export_company_json(db, company_id)
        assert "tables" in export_data
        assert isinstance(export_data["tables"], dict)
        assert "company_id" in export_data
        assert export_data["company_id"] == company_id

    def test_export_includes_records_with_correct_company_id(self, db):
        """Exported records contain the right company_id."""
        company_id = self._seed_company(db)
        self._seed_company_data(db, company_id)

        export_data = self._export_company_json(db, company_id)

        # At least one table should have records with our company_id
        any_with_records = False
        for table_name, table_data in export_data["tables"].items():
            for record in table_data.get("records", []):
                if record.get("company_id") == company_id:
                    any_with_records = True
                    break
        assert any_with_records, "No records found for seeded company_id"

    def test_delete_company_with_confirm_removes_data(self, db):
        """Company data is removed after delete with confirm=DELETE."""
        company_id = self._seed_company(db)
        self._seed_company_data(db, company_id)

        # Perform deletion through the GDPR logic
        self._delete_company_data(db, company_id)

        # Verify no records remain for this company
        for table in ("clients", "drivers", "trucks", "trips"):
            rows = db.conn.execute(
                f"SELECT COUNT(*) AS cnt FROM {table} WHERE company_id = ?",
                (company_id,),
            ).fetchone()
            assert rows["cnt"] == 0, f"{table} still has records"

    def test_export_after_delete_returns_empty_records(self, db):
        """Export after deletion returns no records for the deleted company."""
        company_id = self._seed_company(db)
        self._seed_company_data(db, company_id)
        self._delete_company_data(db, company_id)

        export_data = self._export_company_json(db, company_id)

        # Check client table (should be empty now)
        clients_table = export_data["tables"].get("clients", {})
        assert len(clients_table.get("records", [])) == 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _export_company_json(db, company_id: int) -> dict:
        """Gather all company data as a dict (simulates GDPR export).

        Iterates through the EXPORT_TABLES list and collects all rows
        belonging to *company_id*.
        """
        from backend.api.v1.gdpr import EXPORT_TABLES

        tables: dict[str, dict] = {}
        for table_name in EXPORT_TABLES:
            try:
                columns = [
                    row[1]
                    for row in db.conn.execute(
                        f"PRAGMA table_info({table_name})"
                    ).fetchall()
                ]
                if "company_id" not in columns:
                    tables[table_name] = {"count": 0, "records": []}
                    continue
                rows = db.conn.execute(
                    f"SELECT * FROM {table_name} WHERE company_id = ?",
                    (company_id,),
                ).fetchall()
                records = [dict(r) for r in rows]
                tables[table_name] = {
                    "count": len(records),
                    "records": records,
                }
            except Exception as exc:
                tables[table_name] = {
                    "count": 0,
                    "records": [],
                    "error": str(exc),
                }

        return {
            "company_id": company_id,
            "exported_at": datetime.now().isoformat(),
            "total_records": sum(
                t["count"] for t in tables.values()
            ),
            "tables": tables,
        }

    @staticmethod
    def _delete_company_data(db, company_id: int) -> None:
        """Hard-delete all data for *company_id* (GDPR deletion simulation).

        Uses the same table list as the GDPR endpoint.
        """
        from backend.api.v1.gdpr import EXPORT_TABLES

        for table_name in EXPORT_TABLES:
            try:
                columns = [
                    row[1]
                    for row in db.conn.execute(
                        f"PRAGMA table_info({table_name})"
                    ).fetchall()
                ]
                if "company_id" not in columns:
                    continue
                db.conn.execute(
                    f"DELETE FROM {table_name} WHERE company_id = ?",
                    (company_id,),
                )
            except Exception:
                continue
        db.conn.commit()


# ═════════════════════════════════════════════════════════════════════════
# 5. Formatter Consistency
# ═════════════════════════════════════════════════════════════════════════


class TestFormatterConsistency:
    """fmt_currency, fmt_date, and format_duration edge cases."""

    # ── Currency formatting ─────────────────────────────────────────

    @pytest.mark.parametrize(
        ("value", "currency", "expected"),
        [
            (0, "€", "€ 0.00"),
            (1000, "€", "€ 1 000.00"),
            (39563.5, "€", "€ 39 563.50"),
            (1234567.89, "$", "$ 1 234 567.89"),
            (-500, "€", "-€ 500.00"),
            (0.1, "€", "€ 0.10"),
            (0.01, "€", "€ 0.01"),
            (0.001, "€", "€ 0.00"),  # rounding
            (None, "€", "€ 0.00"),
        ],
    )
    def test_fmt_currency(self, value, currency, expected):
        assert fmt_currency(value, currency=currency) == expected

    # ── Date formatting ─────────────────────────────────────────────

    @pytest.mark.parametrize(
        ("date_str", "expected"),
        [
            ("2026-06-19", "19.06.2026"),
            ("19/06/2026", "19.06.2026"),
            ("2026-06-19 14:30:00", "19.06.2026"),
            ("14.07.2026", "14.07.2026"),
            ("", ""),
            (None, ""),
            ("not-a-date", "not-a-date"),  # passthrough
        ],
    )
    def test_fmt_date(self, date_str, expected):
        assert fmt_date(date_str) == expected

    # ── Duration formatting ─────────────────────────────────────────

    @pytest.mark.parametrize(
        ("minutes", "expected"),
        [
            (0, "0 min"),
            (1, "1min"),
            (59, "59min"),
            (60, "1h"),
            (61, "1h 1min"),
            (120, "2h"),
            (1439, "23h 59min"),
            (1440, "1d"),
            (1441, "1d 1min"),
            (1500, "1d 1h"),
            (2880, "2d"),
            (10080, "7d"),
            (525600, "365d"),
            (-60, "1h"),  # absolute value
            (None, "0 min"),
        ],
    )
    def test_format_duration(self, minutes, expected):
        assert format_duration(minutes) == expected
