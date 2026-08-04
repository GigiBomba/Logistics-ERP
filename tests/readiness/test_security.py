"""Tests for encryption service, API key management, and OAuth2 client credentials.

Tests use in-memory SQLite databases and mock environment variables to
avoid depending on external configuration.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from typing import Any, Dict, Optional

import pytest

from services.encryption_service import EncryptionService
from repositories.api_key_repository import ApiKeyRepository
from backend.oauth2 import OAuth2Service, OAuth2Client


# ── Helpers ──────────────────────────────────────────────────────────────


def _dict_row(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Row factory that returns plain dicts (supports ``.get()``)."""
    columns = [d[0] for d in cursor.description]
    return dict(zip(columns, row))


class _InMemoryDB:
    """Minimal in-memory SQLite database for repository tests.

    Mimics the subset of ``DatabaseManager`` used by ``BaseRepository``
    (``conn``, ``row_to_dict``, ``rows_to_dicts``).

    Rows are returned as dicts (supporting ``.get()``) so that code
    like ``backend.oauth2.OAuth2Service`` works without changes.
    """

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = _dict_row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT NOT NULL UNIQUE,
                key_prefix TEXT NOT NULL,
                name TEXT NOT NULL,
                partner TEXT NOT NULL,
                scopes TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                last_used_at TEXT,
                expires_at TEXT,
                revoked_at TEXT,
                company_id INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_api_keys_partner
                ON api_keys(partner);
            CREATE INDEX IF NOT EXISTS idx_api_keys_active
                ON api_keys(is_active);

            CREATE TABLE IF NOT EXISTS oauth2_clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL UNIQUE,
                client_name TEXT NOT NULL,
                partner TEXT NOT NULL,
                scopes TEXT DEFAULT '[]',
                secret_hash TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                last_used_at TEXT,
                company_id INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_oauth2_clients_id
                ON oauth2_clients(client_id);
            CREATE INDEX IF NOT EXISTS idx_oauth2_clients_partner
                ON oauth2_clients(partner);
        """)
        self.conn.commit()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a SQL statement, matching DatabaseManager.execute() interface."""
        return self.conn.execute(query, params)

    def commit(self) -> None:
        """Commit the current transaction."""
        self.conn.commit()

    @staticmethod
    def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(r) for r in rows]


# ── EncryptionService Tests ──────────────────────────────────────────────


class TestEncryptionService:
    """EncryptionService: encrypt/decrypt roundtrip and fallback behaviour."""

    # ── Fixtures ─────────────────────────────────────────────────────

    @pytest.fixture
    def encryption_key(self) -> str:
        return "test-master-key-32bytes!"

    @pytest.fixture
    def service(self, encryption_key: str) -> EncryptionService:
        return EncryptionService(master_key=encryption_key)

    @pytest.fixture
    def service_no_key(self, monkeypatch) -> EncryptionService:
        """Service initialised without a master key."""
        monkeypatch.delenv("OPERION_ENCRYPTION_KEY", raising=False)
        return EncryptionService(master_key="")

    # ── Tests ────────────────────────────────────────────────────────

    def test_encrypt_decrypt_roundtrip(self, service: EncryptionService) -> None:
        """Encrypting a value and then decrypting it returns the original."""
        plaintext = "smtp_password_super_secret_123!"
        ciphertext = service.encrypt(plaintext)
        assert ciphertext != plaintext
        assert service.decrypt(ciphertext) == plaintext

    def test_encrypt_produces_different_output(self, service: EncryptionService) -> None:
        """Same plaintext encrypted twice yields different ciphertexts (salt)."""
        plaintext = "same_value"
        c1 = service.encrypt(plaintext)
        c2 = service.encrypt(plaintext)
        assert c1 != c2

    def test_encrypt_with_no_key_falls_back(self, service_no_key: EncryptionService) -> None:
        """With no OPERION_ENCRYPTION_KEY, encrypt returns plaintext."""
        plaintext = "sensitive_setting"
        assert service_no_key.encrypt(plaintext) == plaintext

    def test_decrypt_with_no_key_falls_back(self, service_no_key: EncryptionService) -> None:
        """With no OPERION_ENCRYPTION_KEY, decrypt returns input."""
        data = "some_ciphertext_or_plaintext"
        assert service_no_key.decrypt(data) == data

    def test_decrypt_legacy_plaintext(self, service: EncryptionService) -> None:
        """Decrypt on a non-encrypted (plaintext) string returns it as-is."""
        legacy = "legacy_plaintext_setting"
        result = service.decrypt(legacy)
        assert result == legacy

    def test_encrypt_empty_string(self, service: EncryptionService) -> None:
        """Encrypting an empty string works and decrypt roundtrips."""
        ciphertext = service.encrypt("")
        assert isinstance(ciphertext, str)
        assert len(ciphertext) > 0
        assert service.decrypt(ciphertext) == ""

    def test_encrypt_empty_string_no_key(self, service_no_key: EncryptionService) -> None:
        """With no key, encrypt on empty string returns empty string."""
        assert service_no_key.encrypt("") == ""

    def test_decrypt_empty_string(self, service: EncryptionService) -> None:
        """Decrypting an empty string returns empty (no crash)."""
        assert service.decrypt("") == ""

    # ── Fernet heuristic / corrupt-data path ──────────────────────────

    def test_looks_encrypted_rejects_legacy_plaintext(
        self, service: EncryptionService
    ) -> None:
        """A legacy plaintext value is not mistaken for Fernet ciphertext."""
        assert service._looks_encrypted("legacy_plaintext_setting") is False
        assert service._looks_encrypted("") is False

    def test_looks_encrypted_accepts_real_fernet_token(
        self, service: EncryptionService
    ) -> None:
        """A correctly-padded Fernet token is recognised as encrypted."""
        token = service.encrypt("sensitive_value")
        assert len(token) % 4 == 0  # correctly base64-padded
        assert service._looks_encrypted(token) is True

    def test_correctly_padded_fernet_token_decrypts(
        self, service: EncryptionService
    ) -> None:
        """Primary decrypt path works for a correctly-padded token."""
        plaintext = "padding_check_secret_123"
        token = service.encrypt(plaintext)
        assert service.decrypt(token) == plaintext

    def test_corrupted_fernet_token_warns_and_returns_raw(
        self, service: EncryptionService, caplog
    ) -> None:
        """A corrupt Fernet token reaches the warning path and returns as-is."""
        token = service.encrypt("sensitive_value")
        corrupted = token[:-5] + ("A" if token[-5] != "A" else "B") + token[-4:]
        assert service._looks_encrypted(corrupted) is True
        with caplog.at_level("WARNING", logger="services.encryption_service"):
            result = service.decrypt(corrupted)
        assert result == corrupted
        assert "Failed to decrypt Fernet ciphertext" in caplog.text


# ── ApiKeyRepository Tests ──────────────────────────────────────────────


class TestApiKeyRepository:
    """ApiKeyRepository: key lifecycle — create, validate, revoke, list."""

    # ── Fixtures ─────────────────────────────────────────────────────

    @pytest.fixture
    def db(self) -> _InMemoryDB:
        return _InMemoryDB()

    @pytest.fixture
    def repo(self, db: _InMemoryDB) -> ApiKeyRepository:
        return ApiKeyRepository(db)

    # ── Tests ────────────────────────────────────────────────────────

    def test_create_key_returns_raw_key(self, repo: ApiKeyRepository, db: _InMemoryDB) -> None:
        """create_key returns a (raw_key, key_id) tuple."""
        raw_key, key_id = repo.create_key(
            name="TIMOCOM Production",
            partner="timocom",
            scopes=["read:trips", "write:status"],
        )
        assert isinstance(raw_key, str)
        assert raw_key.startswith("ok_")
        # "ok_" prefix (3 chars) + 48 hex chars = 51
        assert len(raw_key) == 3 + 48
        assert isinstance(key_id, int)
        assert key_id > 0

    def test_create_key_stores_hash_only(self, repo: ApiKeyRepository, db: _InMemoryDB) -> None:
        """The raw key is NOT stored directly; only its SHA-256 hash persists."""
        raw_key, key_id = repo.create_key(
            name="TIMOCOM Production",
            partner="timocom",
        )
        expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        row = db.conn.execute(
            "SELECT key_hash, key_prefix FROM api_keys WHERE id = ?",
            (key_id,),
        ).fetchone()
        assert row is not None
        # The database holds the hash, never the plaintext key
        assert row["key_hash"] == expected_hash
        assert row["key_hash"] != raw_key
        # The prefix matches the first 12 characters of the raw key
        assert row["key_prefix"] == raw_key[:12]

    def test_validate_valid_key(self, repo: ApiKeyRepository, db: _InMemoryDB) -> None:
        """A valid raw key passes validation and returns metadata."""
        raw_key, key_id = repo.create_key(
            name="TIMOCOM Production",
            partner="timocom",
            scopes=["read:trips"],
        )
        result = repo.validate_key(raw_key)
        assert result is not None
        assert result["name"] == "TIMOCOM Production"
        assert result["partner"] == "timocom"
        assert result["is_active"] == 1
        assert result["id"] == key_id
        # last_used_at is updated after the fetch in validate_key,
        # so it's NOT expected in the returned metadata; verify
        # instead that the DB row was updated.
        row_after = db.conn.execute(
            "SELECT last_used_at FROM api_keys WHERE id = ?", (key_id,),
        ).fetchone()
        assert row_after is not None
        assert row_after["last_used_at"] is not None

    def test_validate_invalid_key(self, repo: ApiKeyRepository) -> None:
        """A wrong/unknown key returns None."""
        repo.create_key(name="TIMOCOM", partner="timocom")
        result = repo.validate_key("ok_" + "a" * 48)
        assert result is None

    def test_validate_revoked_key(self, repo: ApiKeyRepository) -> None:
        """A key that has been revoked returns None."""
        raw_key, key_id = repo.create_key(
            name="TIMOCOM Production",
            partner="timocom",
        )
        # Revoke it
        repo.revoke_key(key_id)
        # Validation should now fail
        result = repo.validate_key(raw_key)
        assert result is None

    def test_validate_expired_key(self, repo: ApiKeyRepository) -> None:
        """An expired key returns None."""
        from datetime import datetime, timedelta
        past = (datetime.now() - timedelta(days=1)).isoformat()
        raw_key, key_id = repo.create_key(
            name="Expired Key",
            partner="timocom",
            expires_at=past,
        )
        result = repo.validate_key(raw_key)
        assert result is None

    def test_revoke_key(self, repo: ApiKeyRepository, db: _InMemoryDB) -> None:
        """revoke_key sets is_active=0 and revoked_at."""
        raw_key, key_id = repo.create_key(
            name="TIMOCOM Production",
            partner="timocom",
        )
        assert repo.revoke_key(key_id) is True

        row = db.conn.execute(
            "SELECT is_active, revoked_at FROM api_keys WHERE id = ?",
            (key_id,),
        ).fetchone()
        assert row["is_active"] == 0
        assert row["revoked_at"] is not None

        # Second revocation still returns True (row exists, UPDATE matches)
        # because SQLite rowcount reflects matching rows, not changed values.
        assert repo.revoke_key(key_id) is True

    def test_list_keys_returns_all(self, repo: ApiKeyRepository) -> None:
        """list_keys returns all keys when no partner filter is applied."""
        repo.create_key(name="Key A", partner="timocom")
        repo.create_key(name="Key B", partner="transporeon")
        repo.create_key(name="Key C", partner="timocom")

        keys = repo.list_keys()
        assert len(keys) >= 3
        partners = {k["partner"] for k in keys}
        assert partners == {"timocom", "transporeon"}

    def test_list_keys_filters_by_partner(self, repo: ApiKeyRepository) -> None:
        """list_keys(partner="timocom") only returns timocom keys."""
        repo.create_key(name="Key A", partner="timocom")
        repo.create_key(name="Key B", partner="transporeon")
        repo.create_key(name="Key C", partner="timocom")

        keys = repo.list_keys(partner="timocom")
        assert all(k["partner"] == "timocom" for k in keys)
        assert len(keys) == 2
        # Verify transporeon key is not included
        assert all(k["name"] != "Key B" for k in keys)

    def test_list_keys_empty_set(self, repo: ApiKeyRepository) -> None:
        """list_keys for a partner with no keys returns empty list."""
        repo.create_key(name="Key A", partner="timocom")
        keys = repo.list_keys(partner="nonexistent_partner")
        assert keys == []


# ── OAuth2Service Tests ─────────────────────────────────────────────────


class TestOAuth2Service:
    """OAuth2Service: client registration, validation, revocation."""

    # ── Fixtures ─────────────────────────────────────────────────────

    @pytest.fixture
    def db(self) -> _InMemoryDB:
        return _InMemoryDB()

    @pytest.fixture
    def service(self, db: _InMemoryDB) -> OAuth2Service:
        return OAuth2Service(db)

    # ── Tests ────────────────────────────────────────────────────────

    def test_register_client(self, service: OAuth2Service, db: _InMemoryDB) -> None:
        """register_client returns (client_id, client_secret)."""
        client_id, client_secret = service.register_client(
            name="TIMOCOM Integration",
            partner="timocom",
            scopes=["read:trips", "write:status"],
        )
        assert isinstance(client_id, str)
        assert client_id.startswith("operion_")
        # "operion_" (8 chars) + 24 hex chars = 32
        assert len(client_id) == 8 + 24
        assert isinstance(client_secret, str)
        assert len(client_secret) == 64  # 32 bytes as hex

        # Verify it is persisted
        row = db.conn.execute(
            "SELECT client_id, client_name, partner, secret_hash FROM oauth2_clients WHERE client_id = ?",
            (client_id,),
        ).fetchone()
        assert row is not None
        assert row["client_name"] == "TIMOCOM Integration"
        assert row["partner"] == "timocom"
        # Secret is hashed, not stored in plaintext
        expected_hash = hashlib.sha256(client_secret.encode()).hexdigest()
        assert row["secret_hash"] == expected_hash
        assert row["secret_hash"] != client_secret

    def test_validate_client_credentials(self, service: OAuth2Service) -> None:
        """Correct client_id + client_secret validates and returns OAuth2Client."""
        client_id, client_secret = service.register_client(
            name="TIMOCOM Integration",
            partner="timocom",
            scopes=["read:trips"],
        )
        client = service.validate_client(client_id, client_secret)
        assert client is not None
        assert isinstance(client, OAuth2Client)
        assert client.client_id == client_id
        assert client.client_name == "TIMOCOM Integration"
        assert client.partner == "timocom"
        assert client.scopes == ["read:trips"]
        assert client.is_active is True

    def test_validate_wrong_secret(self, service: OAuth2Service) -> None:
        """Wrong client_secret returns None."""
        client_id, client_secret = service.register_client(
            name="TIMOCOM Integration",
            partner="timocom",
            scopes=["read"],
        )
        result = service.validate_client(client_id, "wrong_secret_that_is_64_chars_long_xxxxxxxxxxxx")
        assert result is None

    def test_validate_wrong_client_id(self, service: OAuth2Service) -> None:
        """Non-existent client_id returns None."""
        _, client_secret = service.register_client(
            name="TIMOCOM Integration",
            partner="timocom",
            scopes=["read"],
        )
        result = service.validate_client("operion_nonexistent_client_id_here", client_secret)
        assert result is None

    def test_revoke_client(self, service: OAuth2Service) -> None:
        """After revoke_client, validation fails."""
        client_id, client_secret = service.register_client(
            name="TIMOCOM Integration",
            partner="timocom",
            scopes=["read"],
        )
        # Revoke
        service.revoke_client(client_id)
        # Validation should fail
        result = service.validate_client(client_id, client_secret)
        assert result is None

    def test_revoke_client_idempotent(self, service: OAuth2Service) -> None:
        """revoke_client can be called multiple times without error."""
        client_id, client_secret = service.register_client(
            name="TIMOCOM Integration",
            partner="timocom",
            scopes=["read"],
        )
        service.revoke_client(client_id)
        service.revoke_client(client_id)  # second call should not raise

    def test_list_clients(self, service: OAuth2Service) -> None:
        """list_clients returns all registered clients."""
        service.register_client(name="Client A", partner="timocom", scopes=["read"])
        service.register_client(name="Client B", partner="transporeon", scopes=["write"])
        service.register_client(name="Client C", partner="timocom", scopes=["read", "write"])

        clients = service.list_clients()
        assert len(clients) >= 3
        partners = {c["partner"] for c in clients}
        assert partners == {"timocom", "transporeon"}

    def test_list_clients_filters_by_partner(self, service: OAuth2Service) -> None:
        """list_clients(partner="timocom") only returns matching clients."""
        service.register_client(name="Client A", partner="timocom", scopes=["read"])
        service.register_client(name="Client B", partner="transporeon", scopes=["write"])
        service.register_client(name="Client C", partner="timocom", scopes=["read"])

        clients = service.list_clients(partner="timocom")
        assert all(c["partner"] == "timocom" for c in clients)
        assert len(clients) == 2
        assert all(c["client_name"] != "Client B" for c in clients)

    def test_list_clients_empty(self, service: OAuth2Service) -> None:
        """list_clients with no matching partner returns empty list."""
        service.register_client(name="Client A", partner="timocom", scopes=["read"])
        clients = service.list_clients(partner="nonexistent")
        assert clients == []
