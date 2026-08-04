"""Comprehensive unit tests for repositories.api_key_repository.

All tests mock the inherited BaseRepository DB methods so that no real
database connection is needed. The plaintext key format (``ok_`` + 48 hex
chars), SHA-256 hashing, expiry checks, company scoping, and soft-delete
revocation are all verified.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from repositories.api_key_repository import ApiKeyRepository


# ── Helpers ──────────────────────────────────────────────────────────


def _make_fake_key(hex_part: str = "a" * 48) -> str:
    """Build a plausible API key string ``ok_<48 hex chars>``."""
    return f"ok_{hex_part}"


def _fake_row(**overrides) -> dict:
    """Return a minimal ``api_keys`` row dict (as returned by ``_fetchone``)."""
    row = {
        "id": 1,
        "key_hash": hashlib.sha256(_make_fake_key().encode()).hexdigest(),
        "key_prefix": "ok_aaaaaaaa",
        "name": "Test Key",
        "partner": "test-partner",
        "scopes": '["read","write"]',
        "is_active": 1,
        "created_by": 42,
        "created_at": "2025-01-01T00:00:00",
        "last_used_at": None,
        "expires_at": None,
        "revoked_at": None,
        "company_id": 1,
    }
    row.update(overrides)
    return row


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_tenant_context():
    """Clear tenant context before each test to prevent cross-test leakage."""
    from database.tenant_context import clear_context
    clear_context()
    yield
    clear_context()


@pytest.fixture
def repo():
    """ApiKeyRepository instance with all DB methods mocked."""
    from database.tenant_context import set_request_context
    set_request_context(1, "")
    db = MagicMock()
    r = ApiKeyRepository(db)
    r._execute_insert = MagicMock(return_value=42)
    r._fetchone = MagicMock(return_value=None)
    r._fetchall = MagicMock(return_value=[])
    r._execute = MagicMock()
    r._execute_with_count = MagicMock(return_value=1)
    r._validate_columns = MagicMock()
    r._company_filter = MagicMock(return_value=" AND company_id = ?")
    r._company_params = MagicMock(return_value=(1,))
    return r


# ══════════════════════════════════════════════════════════════════════
# create_key
# ══════════════════════════════════════════════════════════════════════


class TestCreateKey:
    """Key generation and storage."""

    def test_happy_path(self, repo):
        """Returns ``(plaintext_key, key_id)`` with correct format."""
        plaintext, key_id = repo.create_key(
            name="TIMOCOM Production",
            partner="timocom",
        )

        # Format checks
        assert plaintext.startswith("ok_")
        assert len(plaintext) == 51  # "ok_" + 48 hex chars
        assert isinstance(key_id, int)
        assert key_id == 42

    def test_key_uses_secure_random(self, repo):
        """Each call generates a unique key via ``secrets.token_hex(24)``."""
        with patch("repositories.api_key_repository.secrets.token_hex", return_value="bb" * 24):
            plaintext, _ = repo.create_key(name="N", partner="P")
        assert plaintext == "ok_" + "bb" * 24
        assert len(plaintext) == 51

    def test_sha256_hash_stored_not_plaintext(self, repo):
        """The plaintext key is never stored; only its SHA-256 hash is persisted."""
        with patch("repositories.api_key_repository.secrets.token_hex", return_value="cc" * 24):
            plaintext, _ = repo.create_key(name="N", partner="P")

        expected_hash = hashlib.sha256(plaintext.encode()).hexdigest()

        sql = repo._execute_insert.call_args[0][0]
        params = repo._execute_insert.call_args[0][1]
        stored_hash = params[0]

        assert stored_hash == expected_hash
        assert stored_hash != plaintext  # not plaintext
        assert "INSERT INTO api_keys" in sql

    def test_key_prefix_stored(self, repo):
        """First 12 characters (``ok_`` + 9 hex chars) stored for display."""
        with patch("repositories.api_key_repository.secrets.token_hex", return_value="dd" * 24):
            plaintext, _ = repo.create_key(name="N", partner="P")

        params = repo._execute_insert.call_args[0][1]
        stored_prefix = params[1]

        assert stored_prefix == plaintext[:12]
        assert stored_prefix == "ok_ddddddddd"

    def test_with_scopes(self, repo):
        """Scopes list is JSON-serialised and stored."""
        scopes = ["read:invoices", "write:trips"]
        repo.create_key(name="N", partner="P", scopes=scopes)

        params = repo._execute_insert.call_args[0][1]
        stored_scopes = params[4]  # column index for scopes

        assert stored_scopes == json.dumps(scopes)
        assert "read:invoices" in stored_scopes

    def test_without_scopes_defaults_to_empty_list(self, repo):
        """Omitting scopes stores ``[]`` as JSON."""
        repo.create_key(name="N", partner="P", scopes=None)

        params = repo._execute_insert.call_args[0][1]
        assert params[4] == "[]"

    def test_with_expires_at(self, repo):
        """Expiry timestamp is forwarded to the insert."""
        expires = "2026-12-31T23:59:59"
        repo.create_key(name="N", partner="P", expires_at=expires)

        params = repo._execute_insert.call_args[0][1]
        # expires_at is at index 6 (0:key_hash,1:prefix,2:name,3:partner,4:scopes,5:is_active,6:created_by,7:expires_at,8:company_id)
        assert params[7] == expires

    def test_without_expires_at_stores_none(self, repo):
        """Omitting expires_at stores ``None`` in DB."""
        repo.create_key(name="N", partner="P", expires_at=None)

        params = repo._execute_insert.call_args[0][1]
        assert params[7] is None

    def test_created_by_system(self, repo):
        """``created_by=0`` indicates a system-generated key."""
        repo.create_key(name="N", partner="P", created_by=0)

        params = repo._execute_insert.call_args[0][1]
        assert params[6] == 0

    def test_created_by_custom_user(self, repo):
        """A real user ID can be recorded as the creator."""
        repo.create_key(name="N", partner="P", created_by=99)

        params = repo._execute_insert.call_args[0][1]
        assert params[6] == 99

    def test_is_active_defaults_to_1(self, repo):
        """New keys are created active."""
        repo.create_key(name="N", partner="P")

        params = repo._execute_insert.call_args[0][1]
        assert params[5] == 1  # is_active

    def test_company_id_from_user_company_id(self, repo):
        """Company ID is taken from the current user's context."""
        repo.create_key(name="N", partner="P")

        params = repo._execute_insert.call_args[0][1]
        assert params[8] == 1  # company_id

    def test_company_id_fallback_to_zero(self, repo):
        """When ``_user_company_id`` is ``None``/falsy, company_id becomes 0."""
        from database.tenant_context import clear_context
        clear_context()

        repo.create_key(name="N", partner="P")
        params = repo._execute_insert.call_args[0][1]

        assert params[8] == 0

    def test_validate_columns_called(self, repo):
        """Input data is validated before insert."""
        repo.create_key(name="N", partner="P")
        repo._validate_columns.assert_called_once()

    def test_insert_sql_structure(self, repo):
        """The INSERT statement contains all expected columns."""
        repo.create_key(name="N", partner="P", scopes=["a"], expires_at="2026-01-01")

        sql = repo._execute_insert.call_args[0][0]
        for col in ("key_hash", "key_prefix", "name", "partner", "scopes",
                     "is_active", "created_by", "expires_at", "company_id"):
            assert col in sql

    def test_insert_params_order(self, repo):
        """Parameter order matches the SQL column order."""
        repo.create_key(name="MyKey", partner="my-partner", scopes=["x"], created_by=7, expires_at="2026-06-01")

        sql = repo._execute_insert.call_args[0][0]
        params = repo._execute_insert.call_args[0][1]

        # Verify params match their SQL position
        assert params[2] == "MyKey"   # name
        assert params[3] == "my-partner"  # partner
        assert params[4] == '["x"]'   # scopes
        assert params[6] == 7           # created_by
        assert params[7] == "2026-06-01" # expires_at

    def test_insert_logs_info(self, repo):
        """Info-level log emitted on success."""
        with patch("repositories.api_key_repository.logger.info") as mock_log:
            repo.create_key(name="LogKey", partner="log-partner")
        mock_log.assert_called_once()
        args, _ = mock_log.call_args
        assert "LogKey" in args[1]     # first %s arg
        assert "log-partner" in args[2]  # second %s arg
        assert 42 == args[3]            # %d arg


# ══════════════════════════════════════════════════════════════════════
# validate_key
# ══════════════════════════════════════════════════════════════════════


class TestValidateKey:
    """Key validation, expiry checks, and usage tracking."""

    def test_valid_key_returns_row(self, repo):
        """A valid active key returns its metadata dict."""
        row = _fake_row(name="ValidKey", partner="vp")
        repo._fetchone.return_value = row

        result = repo.validate_key(_make_fake_key())

        assert result is not None
        assert result["name"] == "ValidKey"
        assert result["partner"] == "vp"

    def test_valid_key_updates_last_used_at(self, repo):
        """``last_used_at`` is updated to the current timestamp."""
        repo._fetchone.return_value = _fake_row(id=7)

        repo.validate_key(_make_fake_key())

        repo._execute.assert_called_once()
        sql, params = repo._execute.call_args[0]
        assert "UPDATE" in sql
        assert "last_used_at" in sql
        assert "datetime('now')" in sql
        assert params == (7,)

    def test_returns_dict_copy_not_row_object(self, repo):
        """The returned dict is a plain dict (not the original row)."""
        row = _fake_row()
        repo._fetchone.return_value = row

        result = repo.validate_key(_make_fake_key())

        assert isinstance(result, dict)
        # Modification safety: altering result shouldn't affect original
        result["_test"] = True
        assert "_test" not in row

    def test_hash_lookup_correct(self, repo):
        """The query uses SHA-256 hash of the provided raw key."""
        raw_key = _make_fake_key("ff" * 24)
        repo._fetchone.return_value = _fake_row()

        repo.validate_key(raw_key)

        expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        sql, params = repo._fetchone.call_args[0]
        assert params[0] == expected_hash

    def test_sql_filters_is_active(self, repo):
        """Query includes ``is_active = 1`` filter."""
        repo._fetchone.return_value = _fake_row()

        repo.validate_key(_make_fake_key())

        sql = repo._fetchone.call_args[0][0]
        assert "is_active = 1" in sql

    def test_no_company_filter(self, repo):
        """Key lookup is **not** company-scoped (no ``_company_filter()``)."""
        repo._fetchone.return_value = _fake_row()

        repo.validate_key(_make_fake_key())

        sql = repo._fetchone.call_args[0][0]
        # Should NOT contain company_id filter
        assert "company_id" not in sql

    def test_invalid_hash_returns_none(self, repo):
        """Unknown key hash returns ``None``."""
        repo._fetchone.return_value = None

        result = repo.validate_key(_make_fake_key("be" * 24))

        assert result is None

    def test_inactive_key_returns_none(self, repo):
        """Key with ``is_active=0`` filtered out by query → ``None``."""
        repo._fetchone.return_value = None  # row not returned because is_active=0 in WHERE

        result = repo.validate_key(_make_fake_key())

        assert result is None

    def test_expired_key_returns_none(self, repo):
        """Key with ``expires_at`` in the past is rejected."""
        past = (datetime.now() - timedelta(days=1)).isoformat()
        repo._fetchone.return_value = _fake_row(expires_at=past)

        result = repo.validate_key(_make_fake_key())

        assert result is None

    def test_expired_key_does_not_update_last_used(self, repo):
        """Expired keys do not trigger ``last_used_at`` update."""
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        repo._fetchone.return_value = _fake_row(expires_at=past)

        repo.validate_key(_make_fake_key())

        repo._execute.assert_not_called()

    def test_key_without_expiry_works(self, repo):
        """A key with ``expires_at=None`` never expires."""
        repo._fetchone.return_value = _fake_row(expires_at=None)

        result = repo.validate_key(_make_fake_key())

        assert result is not None

    def test_key_with_future_expiry_works(self, repo):
        """A key with ``expires_at`` in the future is valid."""
        future = (datetime.now() + timedelta(days=30)).isoformat()
        repo._fetchone.return_value = _fake_row(expires_at=future)

        result = repo.validate_key(_make_fake_key())

        assert result is not None

    def test_key_with_edge_expiry_now(self, repo):
        """A key expiring exactly now is still valid (``<`` not ``<=``)."""
        now = datetime.now().isoformat()
        repo._fetchone.return_value = _fake_row(expires_at=now)

        result = repo.validate_key(_make_fake_key())

        # expiry_dt == now is NOT < now, so it passes
        assert result is not None

    def test_unparseable_expires_at_logged_and_returns_key(self, repo):
        """An invalid ``expires_at`` value logs a warning but does **not** reject."""
        repo._fetchone.return_value = _fake_row(expires_at="not-a-date")

        with patch("repositories.api_key_repository.logger.warning") as mock_warn:
            result = repo.validate_key(_make_fake_key())

        assert result is not None
        mock_warn.assert_called_once()
        args, _ = mock_warn.call_args
        assert "unparseable" in args[0]
        assert "not-a-date" in args[2]  # third positional arg after format string

    def test_none_expiry_skips_parsing(self, repo):
        """``None`` expiry does not trigger datetime parsing at all."""
        repo._fetchone.return_value = _fake_row(expires_at=None)

        with patch("repositories.api_key_repository.logger.warning") as mock_warn:
            result = repo.validate_key(_make_fake_key())

        assert result is not None
        mock_warn.assert_not_called()


# ══════════════════════════════════════════════════════════════════════
# revoke_key
# ══════════════════════════════════════════════════════════════════════


class TestRevokeKey:
    """Soft-delete revocation."""

    def test_successful_revoke_returns_true(self, repo):
        """When a row is updated, ``revoke_key`` returns ``True``."""
        repo._execute_with_count.return_value = 1

        result = repo.revoke_key(7)

        assert result is True

    def test_sets_is_active_zero(self, repo):
        """The UPDATE sets ``is_active = 0``."""
        repo.revoke_key(7)

        sql = repo._execute_with_count.call_args[0][0]
        assert "is_active = 0" in sql

    def test_sets_revoked_at(self, repo):
        """The UPDATE sets ``revoked_at = datetime('now')``."""
        repo.revoke_key(7)

        sql = repo._execute_with_count.call_args[0][0]
        assert "revoked_at" in sql
        assert "datetime('now')" in sql

    def test_query_matches_by_id(self, repo):
        """The WHERE clause filters by id."""
        repo.revoke_key(7)

        sql = repo._execute_with_count.call_args[0][0]
        params = repo._execute_with_count.call_args[0][1]
        assert "WHERE id = ?" in sql
        assert params[0] == 7

    def test_company_filter_applied(self, repo):
        """The company filter clause is appended."""
        repo._company_filter.return_value = " AND company_id = ?"
        repo._company_params.return_value = (1,)

        repo.revoke_key(7)

        sql = repo._execute_with_count.call_args[0][0]
        params = repo._execute_with_count.call_args[0][1]
        assert "company_id = ?" in sql
        assert params == (7, 1)

    def test_key_not_found_returns_false(self, repo):
        """When no rows match, returns ``False``."""
        repo._execute_with_count.return_value = 0

        result = repo.revoke_key(999)

        assert result is False

    def test_not_found_logs_warning(self, repo):
        """A warning is logged when no key is found to revoke."""
        repo._execute_with_count.return_value = 0

        with patch("repositories.api_key_repository.logger.warning") as mock_warn:
            repo.revoke_key(999)

        mock_warn.assert_called_once()
        args, _ = mock_warn.call_args
        assert 999 == args[1]  # %d arg

    def test_found_logs_info(self, repo):
        """An info message is logged on successful revocation."""
        repo._execute_with_count.return_value = 1

        with patch("repositories.api_key_repository.logger.info") as mock_info:
            repo.revoke_key(7)

        mock_info.assert_called_once()
        args, _ = mock_info.call_args
        assert 7 == args[1]  # %d arg


# ══════════════════════════════════════════════════════════════════════
# list_keys
# ══════════════════════════════════════════════════════════════════════


class TestListKeys:
    """Listing keys with optional partner filter."""

    def test_no_filter_returns_all(self, repo):
        """Without a partner argument, all keys for the company are returned."""
        repo._fetchall.return_value = [
            _fake_row(id=1, name="Key A"),
            _fake_row(id=2, name="Key B"),
        ]

        result = repo.list_keys()

        assert len(result) == 2
        assert result[0]["name"] == "Key A"
        assert result[1]["name"] == "Key B"

    def test_no_filter_sql(self, repo):
        """Without partner, uses ``WHERE 1=1`` + company filter."""
        repo.list_keys()

        sql = repo._fetchall.call_args[0][0]
        assert "WHERE 1=1" in sql
        assert "company_id = ?" in sql

    def test_no_filter_params(self, repo):
        """Without partner, only company params are passed."""
        repo._company_params.return_value = (1,)

        repo.list_keys()

        params = repo._fetchall.call_args[0][1]
        assert params == (1,)

    def test_with_partner_filter(self, repo):
        """Passing a partner slug filters results."""
        repo._fetchall.return_value = [_fake_row(partner="timocom")]

        result = repo.list_keys(partner="timocom")

        assert len(result) == 1
        assert result[0]["partner"] == "timocom"

    def test_with_partner_sql(self, repo):
        """With partner, query filters by ``partner = ?``."""
        repo.list_keys(partner="acme")

        sql = repo._fetchall.call_args[0][0]
        assert "partner = ?" in sql
        assert "company_id = ?" in sql

    def test_with_partner_params(self, repo):
        """With partner, params include partner slug then company id."""
        repo._company_params.return_value = (1,)

        repo.list_keys(partner="acme")

        params = repo._fetchall.call_args[0][1]
        assert params == ("acme", 1)

    def test_empty_results(self, repo):
        """Returns empty list when no keys match."""
        repo._fetchall.return_value = []

        result = repo.list_keys()

        assert result == []

    def test_empty_results_with_partner(self, repo):
        """Returns empty list when no keys match the partner filter."""
        repo._fetchall.return_value = []

        result = repo.list_keys(partner="nonexistent")

        assert result == []

    def test_ordered_by_created_at_desc(self, repo):
        """Results are ordered newest-first."""
        repo.list_keys()

        sql = repo._fetchall.call_args[0][0]
        assert "ORDER BY created_at DESC" in sql

    def test_select_columns_exclude_key_hash(self, repo):
        """The SELECT list does **not** include ``key_hash`` (security)."""
        repo.list_keys()

        sql = repo._fetchall.call_args[0][0]
        assert "key_hash" not in sql
        # But includes the display-friendly columns
        for col in ("key_prefix", "name", "partner", "scopes", "is_active",
                     "created_by", "created_at", "last_used_at", "expires_at", "revoked_at"):
            assert col in sql


# ══════════════════════════════════════════════════════════════════════
# get_by_id
# ══════════════════════════════════════════════════════════════════════


class TestGetById:
    """Fetch a single key by its primary key."""

    def test_found_returns_dict(self, repo):
        """When the key exists, its row dict is returned."""
        expected = _fake_row(id=5, name="TargetKey")
        repo._fetchone.return_value = expected

        result = repo.get_by_id(5)

        assert result == expected

    def test_not_found_returns_none(self, repo):
        """When no key matches, returns ``None``."""
        repo._fetchone.return_value = None

        result = repo.get_by_id(999)

        assert result is None

    def test_sql_filters_by_id(self, repo):
        """The query filters by ``id = ?``."""
        repo.get_by_id(42)

        sql, params = repo._fetchone.call_args[0]
        assert "WHERE id = ?" in sql
        assert params[0] == 42

    def test_company_filter_applied(self, repo):
        """The query includes the company filter clause."""
        repo._company_filter.return_value = " AND company_id = ?"
        repo._company_params.return_value = (1,)

        repo.get_by_id(7)

        sql, params = repo._fetchone.call_args[0]
        assert "company_id = ?" in sql
        assert params == (7, 1)

    def test_select_all_columns(self, repo):
        """Uses ``SELECT *`` (includes everything, even key_hash)."""
        row = _fake_row()
        repo._fetchone.return_value = row

        repo.get_by_id(1)

        sql = repo._fetchone.call_args[0][0]
        assert "SELECT *" in sql
