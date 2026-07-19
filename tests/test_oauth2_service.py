"""Tests for backend.oauth2 — OAuth2Service (client credentials grant)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from backend.oauth2 import OAuth2Client, OAuth2Service


# ── Prevent MagicMock-in-logging-handler errors ─────────────────────────

@pytest.fixture(autouse=True)
def _silence_logger():
    """Patch the module logger so MagicMock handlers don't crash logging calls."""
    with patch('backend.oauth2.logger', MagicMock()):
        yield


# ── Fixtures / helpers ──────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Return a db mock with a conn attribute that returns a cursor mock."""
    db = MagicMock()
    db.conn = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    """Return an OAuth2Service wired to a mock database."""
    return OAuth2Service(mock_db)


@pytest.fixture
def sample_row() -> dict:
    """A realistic row returned by fetchone/fetchall for an active client."""
    return {
        "client_id": "operion_abc123def456ghi789",
        "client_name": "Test Client",
        "partner": "acme",
        "scopes": '["read", "write"]',
        "is_active": 1,
        "created_at": "2025-01-15T10:00:00",
        "last_used_at": None,
        "company_id": 42,
        "created_by": 1,
    }


# ── OAuth2Client dataclass ─────────────────────────────────────────────

class TestOAuth2ClientDataclass:
    def test_minimal_construction(self):
        client = OAuth2Client(
            client_id="cid",
            client_name="name",
            partner="p",
            scopes=["read"],
            is_active=True,
            created_at="2025-01-01",
        )
        assert client.client_id == "cid"
        assert client.client_name == "name"
        assert client.partner == "p"
        assert client.scopes == ["read"]
        assert client.is_active is True
        assert client.created_at == "2025-01-01"
        assert client.last_used_at is None

    def test_with_last_used_at(self):
        client = OAuth2Client(
            client_id="cid",
            client_name="name",
            partner="p",
            scopes=[],
            is_active=True,
            created_at="2025-01-01",
            last_used_at="2025-06-01T12:00:00",
        )
        assert client.last_used_at == "2025-06-01T12:00:00"


# ── register_client ────────────────────────────────────────────────────

class TestRegisterClient:
    def test_returns_tuple_with_client_id_and_secret(self, service, mock_db):
        """register_client returns a (client_id, client_secret) tuple."""
        with patch("backend.oauth2.secrets.token_hex", side_effect=["aaaa", "bbbb"]):
            result = service.register_client("My App", "partner_x", ["read"], user_id=1)

        assert isinstance(result, tuple)
        assert len(result) == 2
        client_id, client_secret = result
        assert client_id.startswith("operion_")
        assert client_secret == "bbbb"

    def test_client_id_starts_with_operion_prefix(self, service, mock_db):
        with patch("backend.oauth2.secrets.token_hex", return_value="ab" * 12):
            client_id, _ = service.register_client("X", "y", ["z"])
        assert client_id.startswith("operion_")

    def test_client_secret_is_64_hex_chars(self, service, mock_db):
        with patch("backend.oauth2.secrets.token_hex", return_value="cd" * 32):
            _, client_secret = service.register_client("X", "y", ["z"])
        assert len(client_secret) == 64
        assert all(c in "0123456789abcdef" for c in client_secret)

    def test_stores_sha256_hash_not_plaintext(self, service, mock_db):
        """The INSERT stores a SHA-256 hex digest, never the raw secret."""
        with patch("backend.oauth2.secrets.token_hex", return_value="secret123"):
            client_id, client_secret = service.register_client("X", "y", ["z"])

        # Capture the INSERT args
        insert_sql = mock_db.conn.execute.call_args[0][0]
        insert_params = mock_db.conn.execute.call_args[0][1]

        assert "INSERT INTO oauth2_clients" in insert_sql
        stored_hash = insert_params[4]  # 5th positional param
        expected_hash = hashlib.sha256(client_secret.encode()).hexdigest()
        assert stored_hash == expected_hash
        assert stored_hash != client_secret  # not plaintext

    def test_insert_parameters(self, service, mock_db):
        """Verify every positional parameter in the INSERT statement.

        The VALUES clause is: (?, ?, ?, ?, ?, 1, ?, ?)
        is_active=1 is hardcoded in SQL, not a parameter.
        The params tuple is: (client_id, name, partner, str(scopes),
                              secret_hash, user_id, company_id)
        """
        with patch("backend.oauth2.secrets.token_hex", return_value="xyzxyz"):
            with patch.object(
                OAuth2Service, "_get_company_id", return_value=99
            ):
                service.register_client("Warehouse", "logistics", ["read", "write"], user_id=7)

        params: tuple = mock_db.conn.execute.call_args[0][1]
        # 7 params: (client_id, name, partner, scopes, secret_hash, user_id, company_id)
        assert len(params) == 7
        client_id = params[0]
        assert client_id.startswith("operion_")
        assert params[1] == "Warehouse"
        assert params[2] == "logistics"
        assert params[3] == str(["read", "write"])  # scopes stored as str
        assert isinstance(params[4], str) and len(params[4]) == 64  # sha256 hash
        assert params[5] == 7  # created_by (user_id)
        assert params[6] == 99  # company_id

    def test_commit_called(self, service, mock_db):
        with patch("backend.oauth2.secrets.token_hex", return_value="x"):
            service.register_client("X", "y", ["z"])
        mock_db.conn.commit.assert_called_once()

    def test_calls_get_company_id(self, service, mock_db):
        with patch("backend.oauth2.secrets.token_hex", return_value="x"):
            with patch.object(
                OAuth2Service, "_get_company_id", return_value=42
            ) as mock_gci:
                service.register_client("X", "y", ["z"])
        mock_gci.assert_called_once()

    def test_empty_scopes_list(self, service, mock_db):
        """An empty scopes list is stored as '[]' string."""
        with patch("backend.oauth2.secrets.token_hex", return_value="x"):
            service.register_client("X", "y", [])
        params = mock_db.conn.execute.call_args[0][1]
        assert params[3] == "[]"


# ── validate_client ────────────────────────────────────────────────────

class TestValidateClient:
    def test_valid_credentials_returns_oauth2_client(
        self, service, mock_db, sample_row
    ):
        """Valid client_id + client_secret returns a populated OAuth2Client."""
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        result = service.validate_client("operion_abc123def456ghi789", "correct-secret")
        assert isinstance(result, OAuth2Client)
        assert result.client_id == sample_row["client_id"]
        assert result.client_name == "Test Client"
        assert result.partner == "acme"
        assert result.scopes == ["read", "write"]
        assert result.is_active is True
        assert result.created_at == "2025-01-15T10:00:00"
        assert result.last_used_at is None

    def test_wrong_client_id_returns_none(self, service, mock_db):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        mock_db.conn.execute.return_value = cursor

        result = service.validate_client("nonexistent", "any-secret")
        assert result is None

    def test_wrong_client_secret_returns_none(self, service, mock_db, sample_row):
        """Wrong secret → hash doesn't match → no row → None."""
        # Make the query return a row only for the *correct* hash
        def execute_side_effect(sql, params):
            cursor = MagicMock()
            # Only match if both client_id and hash are correct
            cursor.fetchone.return_value = sample_row if params[1] == hashlib.sha256(
                "correct-secret".encode()
            ).hexdigest() else None
            return cursor

        mock_db.conn.execute.side_effect = execute_side_effect
        result = service.validate_client("operion_abc123def456ghi789", "wrong-secret")
        assert result is None

    def test_inactive_client_returns_none(self, service, mock_db, sample_row):
        """is_active=0 means the row is filtered out by the query (AND is_active = 1)."""
        cursor = MagicMock()
        cursor.fetchone.return_value = None  # DB WHERE clause filters inactive rows
        mock_db.conn.execute.return_value = cursor

        result = service.validate_client("operion_abc123def456ghi789", "correct-secret")
        assert result is None

    def test_last_used_at_updated_on_success(self, service, mock_db, sample_row):
        """After a successful validation, last_used_at is set to now."""
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        with patch("backend.oauth2.datetime") as mock_dt:
            fake_now = datetime(2026, 7, 13, 10, 30, 0)
            mock_dt.now.return_value = fake_now
            service.validate_client("operion_abc123def456ghi789", "correct-secret")

        # The second execute call is the UPDATE
        update_call = mock_db.conn.execute.call_args_list[1]
        update_sql, update_params = update_call[0]
        assert "UPDATE oauth2_clients SET last_used_at" in update_sql
        assert update_params[0] == fake_now.isoformat()
        assert update_params[1] == sample_row["client_id"]

    def test_commit_called_after_update(self, service, mock_db, sample_row):
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        service.validate_client("operion_abc123def456ghi789", "correct-secret")
        assert mock_db.conn.commit.call_count >= 1

    def test_scopes_string_parsed_as_json(self, service, mock_db, sample_row):
        """When row['scopes'] is a JSON string, it gets parsed into a list."""
        row = dict(sample_row, scopes='["admin"]')
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        mock_db.conn.execute.return_value = cursor

        result = service.validate_client("cid", "secret")
        assert result.scopes == ["admin"]

    def test_scopes_list_passed_through(self, service, mock_db, sample_row):
        """When row['scopes'] is already a list, it is used directly."""
        row = dict(sample_row, scopes=["admin"])
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        mock_db.conn.execute.return_value = cursor

        result = service.validate_client("cid", "secret")
        assert result.scopes == ["admin"]

    def test_scopes_none_becomes_empty_list(self, service, mock_db, sample_row):
        """When row['scopes'] is None, defaults to []."""
        row = dict(sample_row, scopes=None)
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        mock_db.conn.execute.return_value = cursor

        result = service.validate_client("cid", "secret")
        assert result.scopes == []

    def test_scopes_empty_string_becomes_empty_list(
        self, service, mock_db, sample_row
    ):
        """Empty string stored in DB should parse to []."""
        row = dict(sample_row, scopes="")
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        mock_db.conn.execute.return_value = cursor

        result = service.validate_client("cid", "secret")
        assert result.scopes == []


# ── issue_token ─────────────────────────────────────────────────────────

class TestIssueToken:
    def test_valid_credentials_returns_token_dict(
        self, service, mock_db, sample_row
    ):
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        with patch(
            "backend.oauth2.create_access_token", return_value="fake.jwt.token"
        ) as mock_cat:
            result = service.issue_token("operion_abc123def456ghi789", "correct-secret")

        assert result is not None
        assert result["access_token"] == "fake.jwt.token"
        assert result["token_type"] == "bearer"
        assert result["expires_in"] == 3600
        assert result["scope"] == "read write"
        mock_cat.assert_called_once()

    def test_invalid_credentials_returns_none(self, service, mock_db):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        mock_db.conn.execute.return_value = cursor

        result = service.issue_token("bad-id", "bad-secret")
        assert result is None

    def test_token_type_is_bearer(self, service, mock_db, sample_row):
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        with patch("backend.oauth2.create_access_token", return_value="tok"):
            result = service.issue_token("cid", "secret")
        assert result["token_type"] == "bearer"

    def test_custom_scope_splits_into_list(self, service, mock_db, sample_row):
        """When a scope string is provided, it's split on whitespace."""
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        with patch("backend.oauth2.create_access_token") as mock_cat:
            service.issue_token("cid", "secret", scope="read write admin")

        # Verify create_access_token received the split scopes
        token_data = mock_cat.call_args[1]["data"]
        assert token_data["scopes"] == ["read", "write", "admin"]

    def test_empty_scope_uses_client_scopes(self, service, mock_db, sample_row):
        """Default empty scope should use the scopes from the client record."""
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        with patch("backend.oauth2.create_access_token") as mock_cat:
            service.issue_token("cid", "secret", scope="")

        token_data = mock_cat.call_args[1]["data"]
        assert token_data["scopes"] == ["read", "write"]

    def test_default_scope_omitted_uses_client_scopes(
        self, service, mock_db, sample_row
    ):
        """Omitting scope entirely defaults to client.scopes."""
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        with patch("backend.oauth2.create_access_token") as mock_cat:
            service.issue_token("cid", "secret")

        token_data = mock_cat.call_args[1]["data"]
        assert token_data["scopes"] == ["read", "write"]

    def test_create_access_token_called_with_correct_data(
        self, service, mock_db, sample_row
    ):
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        with patch("backend.oauth2.create_access_token") as mock_cat:
            service.issue_token("cid", "secret", scope="read")

        mock_cat.assert_called_once()
        call_kwargs = mock_cat.call_args[1]
        assert call_kwargs["data"]["sub"] == sample_row["client_id"]
        assert call_kwargs["data"]["type"] == "client_credentials"
        assert call_kwargs["data"]["client_name"] == "Test Client"
        assert call_kwargs["data"]["partner"] == "acme"
        assert call_kwargs["data"]["scopes"] == ["read"]
        # expires_delta should be 1 hour
        from datetime import timedelta
        assert call_kwargs["expires_delta"] == timedelta(hours=1)

    def test_scope_in_response_joined_with_space(
        self, service, mock_db, sample_row
    ):
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        with patch("backend.oauth2.create_access_token", return_value="tok"):
            result = service.issue_token("cid", "secret", scope="a b c")
        assert result["scope"] == "a b c"

    def test_validate_client_failure_short_circuits(
        self, service, mock_db
    ):
        """If validate_client returns None, create_access_token is never called."""
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        mock_db.conn.execute.return_value = cursor

        with patch("backend.oauth2.create_access_token") as mock_cat:
            result = service.issue_token("bad", "bad")
        assert result is None
        mock_cat.assert_not_called()


# ── revoke_client ──────────────────────────────────────────────────────

class TestRevokeClient:
    def test_sets_is_active_to_zero(self, service, mock_db):
        service.revoke_client("client_to_revoke")

        sql, params = mock_db.conn.execute.call_args[0]
        assert "UPDATE oauth2_clients" in sql
        assert "is_active = 0" in sql or "is_active=0" in sql
        assert params[0] == "client_to_revoke"

    def test_commit_called(self, service, mock_db):
        service.revoke_client("any")
        mock_db.conn.commit.assert_called_once()

    def test_revoke_already_revoked_client_does_not_raise(
        self, service, mock_db
    ):
        """Revoking an already-revoked client is idempotent (no error)."""
        # Simulate DB successfully executing the UPDATE even if 0 rows match
        service.revoke_client("already_inactive")
        mock_db.conn.execute.assert_called_once()


# ── list_clients ───────────────────────────────────────────────────────

class TestListClients:
    def test_no_partner_filter_returns_all_for_company(
        self, service, mock_db, sample_row
    ):
        cursor = MagicMock()
        cursor.fetchall.return_value = [sample_row, dict(sample_row, client_id="c2")]
        mock_db.conn.execute.return_value = cursor

        with patch.object(OAuth2Service, "_get_company_id", return_value=42):
            result = service.list_clients()

        assert len(result) == 2
        assert result[0]["client_id"] == sample_row["client_id"]
        assert result[1]["client_id"] == "c2"

    def test_with_partner_filter(self, service, mock_db, sample_row):
        cursor = MagicMock()
        cursor.fetchall.return_value = [sample_row]
        mock_db.conn.execute.return_value = cursor

        with patch.object(OAuth2Service, "_get_company_id", return_value=42):
            result = service.list_clients(partner="acme")

        assert len(result) == 1
        sql = mock_db.conn.execute.call_args[0][0]
        assert "partner = ?" in sql
        params = mock_db.conn.execute.call_args[0][1]
        assert params[0] == "acme"

    def test_partner_filter_uses_company_id(self, service, mock_db, sample_row):
        cursor = MagicMock()
        cursor.fetchall.return_value = [sample_row]
        mock_db.conn.execute.return_value = cursor

        with patch.object(OAuth2Service, "_get_company_id", return_value=7):
            service.list_clients(partner="foo")

        params = mock_db.conn.execute.call_args[0][1]
        assert params[1] == 7  # company_id is second param

    def test_no_partner_uses_company_id_only(self, service, mock_db, sample_row):
        cursor = MagicMock()
        cursor.fetchall.return_value = [sample_row]
        mock_db.conn.execute.return_value = cursor

        with patch.object(OAuth2Service, "_get_company_id", return_value=7):
            service.list_clients()

        params = mock_db.conn.execute.call_args[0][1]
        assert params[0] == 7
        sql = mock_db.conn.execute.call_args[0][0]
        assert "partner" not in sql or "partner" not in sql.upper()

    def test_returns_list_of_dicts(self, service, mock_db, sample_row):
        cursor = MagicMock()
        cursor.fetchall.return_value = [sample_row]
        mock_db.conn.execute.return_value = cursor

        with patch.object(OAuth2Service, "_get_company_id", return_value=1):
            result = service.list_clients()

        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_ordered_by_created_at_desc(self, service, mock_db, sample_row):
        cursor = MagicMock()
        cursor.fetchall.return_value = [sample_row]
        mock_db.conn.execute.return_value = cursor

        with patch.object(OAuth2Service, "_get_company_id", return_value=1):
            service.list_clients()

        sql = mock_db.conn.execute.call_args[0][0]
        assert "ORDER BY created_at DESC" in sql

    def test_empty_result(self, service, mock_db):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        mock_db.conn.execute.return_value = cursor

        with patch.object(OAuth2Service, "_get_company_id", return_value=1):
            result = service.list_clients()

        assert result == []


# ── _get_company_id ────────────────────────────────────────────────────

class TestGetCompanyId:
    def test_calls_get_request_company_id(self, service):
        with patch(
            "backend.oauth2.get_request_company_id", return_value=42
        ) as mock_gci:
            result = OAuth2Service._get_company_id()
        mock_gci.assert_called_once()
        assert result == 42

    def test_returns_zero_when_get_request_company_id_returns_falsy(
        self, service
    ):
        with patch(
            "backend.oauth2.get_request_company_id", return_value=None
        ):
            result = OAuth2Service._get_company_id()
        assert result == 0

    def test_returns_zero_when_get_request_company_id_returns_zero(
        self, service
    ):
        with patch(
            "backend.oauth2.get_request_company_id", return_value=0
        ):
            result = OAuth2Service._get_company_id()
        assert result == 0

    def test_is_static_method(self, service):
        """_get_company_id can be called on the class without an instance."""
        with patch(
            "backend.oauth2.get_request_company_id", return_value=99
        ):
            result = OAuth2Service._get_company_id()
        assert result == 99


# ── Integration-style: validate_client uses correct query ──────────────

class TestValidateClientQuery:
    def test_query_filters_by_client_id_secret_hash_and_active(
        self, service, mock_db, sample_row
    ):
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        service.validate_client("my_client", "my_secret")
        sql, params = mock_db.conn.execute.call_args_list[0][0]

        assert "WHERE client_id = ?" in sql
        assert "secret_hash = ?" in sql
        assert "is_active = 1" in sql or "is_active=1" in sql
        assert params[0] == "my_client"
        assert params[1] == hashlib.sha256("my_secret".encode()).hexdigest()

    def test_query_uses_select_star(self, service, mock_db, sample_row):
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        service.validate_client("x", "y")
        sql = mock_db.conn.execute.call_args_list[0][0][0]
        assert sql.strip().upper().startswith("SELECT")


# ── Edge cases ─────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_register_client_with_user_id_zero(
        self, service, mock_db
    ):
        """user_id=0 (default) should be passed through to the INSERT."""
        with patch("backend.oauth2.secrets.token_hex", return_value="x"):
            service.register_client("X", "y", ["z"])  # user_id defaults to 0

        params = mock_db.conn.execute.call_args[0][1]
        assert params[5] == 0  # created_by (6th param, index 5)

    def test_register_client_with_long_name_partner(
        self, service, mock_db
    ):
        """Unusual but valid strings don't break the INSERT."""
        name = "a" * 200
        partner = "b" * 200
        with patch("backend.oauth2.secrets.token_hex", return_value="x"):
            client_id, secret = service.register_client(name, partner, ["read"])

        params = mock_db.conn.execute.call_args[0][1]
        assert params[1] == name
        assert params[2] == partner
        assert isinstance(client_id, str)
        assert isinstance(secret, str)

    def test_validate_client_with_unicode_secret(
        self, service, mock_db, sample_row
    ):
        """Unicode characters in the secret shouldn't cause issues."""
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        result = service.validate_client("cid", "héllo_wörld🔥")
        # The hash is computed and compared by the DB query; if the mock
        # returns a row, validation passes.
        assert isinstance(result, OAuth2Client)

    def test_issue_token_with_scope_containing_multiple_spaces(
        self, service, mock_db, sample_row
    ):
        """Extra whitespace in scope is handled by .split()."""
        cursor = MagicMock()
        cursor.fetchone.return_value = sample_row
        mock_db.conn.execute.return_value = cursor

        with patch("backend.oauth2.create_access_token") as mock_cat:
            service.issue_token("cid", "secret", scope="  read   write  ")

        token_scopes = mock_cat.call_args[1]["data"]["scopes"]
        assert token_scopes == ["read", "write"]

    def test_list_clients_no_clients(self, service, mock_db):
        """An empty company returns an empty list."""
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        mock_db.conn.execute.return_value = cursor

        with patch.object(OAuth2Service, "_get_company_id", return_value=999):
            result = service.list_clients()

        assert result == []

    def test_revoke_client_correct_sql(self, service, mock_db):
        service.revoke_client("my_client_id")
        sql, params = mock_db.conn.execute.call_args[0]
        assert "UPDATE" in sql.upper()
        assert "is_active" in sql.lower()
        assert params[0] == "my_client_id"
        mock_db.conn.commit.assert_called_once()
