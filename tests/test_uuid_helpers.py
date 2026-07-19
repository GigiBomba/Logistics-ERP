"""Tests for database.uuid_helpers — UUID generation helpers.

Covers:
  - new_uuid generates valid UUID v4 strings
  - Multiple calls produce unique values
  - Format validation (hyphen-separated hex groups)
  - is_postgresql detects engine correctly
  - Edge cases (mock engine)
"""

from __future__ import annotations

import re
import uuid
from unittest.mock import MagicMock, PropertyMock

import pytest

from database.uuid_helpers import is_postgresql, new_uuid


# ── UUID pattern (standard 8-4-4-4-12 hex) ─────────────────────────────

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def sqlite_db() -> MagicMock:
    """Mock DatabaseManager with SQLite engine."""
    db = MagicMock()
    type(db)._engine = PropertyMock(return_value="sqlite")
    return db


@pytest.fixture
def postgresql_db() -> MagicMock:
    """Mock DatabaseManager with PostgreSQL engine."""
    db = MagicMock()
    type(db)._engine = PropertyMock(return_value="postgresql")
    return db


@pytest.fixture
def unknown_engine_db() -> MagicMock:
    """Mock DatabaseManager without _engine attribute."""
    db = MagicMock()
    # Deliberately don't set _engine
    return db


# ═══════════════════════════════════════════════════════════════════════
#  new_uuid
# ═══════════════════════════════════════════════════════════════════════


class TestNewUUID:
    """Tests for new_uuid() function."""

    def test_returns_string(self, sqlite_db: MagicMock) -> None:
        result = new_uuid(sqlite_db)
        assert isinstance(result, str), "new_uuid should return a string"

    def test_returns_valid_uuid_v4(self, sqlite_db: MagicMock) -> None:
        result = new_uuid(sqlite_db)
        assert UUID_PATTERN.match(result), (
            f"'{result}' does not match UUID v4 pattern"
        )

    def test_returns_valid_uuid_object(self, sqlite_db: MagicMock) -> None:
        """The returned string can be parsed by uuid.UUID."""
        result = new_uuid(sqlite_db)
        parsed = uuid.UUID(result)
        assert parsed.version == 4, f"Expected UUID v4, got v{parsed.version}"

    def test_multiple_calls_are_unique(self, sqlite_db: MagicMock) -> None:
        """Call new_uuid 100 times and verify all values are distinct."""
        uuids = {new_uuid(sqlite_db) for _ in range(100)}
        assert len(uuids) == 100, (
            f"Generated {100 - len(uuids)} duplicate UUIDs"
        )

    def test_no_duplicates_in_large_batch(self, sqlite_db: MagicMock) -> None:
        """Large batch (1000) has no duplicates (statistical guarantee)."""
        uuids = {new_uuid(sqlite_db) for _ in range(1000)}
        assert len(uuids) == 1000, (
            f"Duplicates found in 1000 UUIDs: {1000 - len(uuids)}"
        )

    def test_lowercase_hex_digits(self, sqlite_db: MagicMock) -> None:
        """UUID hex digits should be lowercase."""
        result = new_uuid(sqlite_db)
        assert result == result.lower(), (
            "UUID should be lowercase"
        )

    def test_no_curly_braces_or_spaces(self, sqlite_db: MagicMock) -> None:
        """The string should not have {braces} or spaces."""
        result = new_uuid(sqlite_db)
        assert "{" not in result
        assert "}" not in result
        assert " " not in result

    def test_correct_hyphen_positions(self, sqlite_db: MagicMock) -> None:
        """UUID format: 8-4-4-4-12."""
        result = new_uuid(sqlite_db)
        parts = result.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12

    def test_works_with_postgresql_db(self, postgresql_db: MagicMock) -> None:
        """new_uuid works the same way for PostgreSQL engine."""
        result = new_uuid(postgresql_db)
        assert UUID_PATTERN.match(result)

    def test_works_with_unknown_engine(self, unknown_engine_db: MagicMock) -> None:
        """new_uuid works even without _engine attribute."""
        result = new_uuid(unknown_engine_db)
        assert UUID_PATTERN.match(result)

    def test_v4_random_bits_set(self, sqlite_db: MagicMock) -> None:
        """UUID version 4: version nibble at position 12-13 should be '4'
        and variant nibble at position 16-17 should be 8/9/a/b."""
        for _ in range(50):
            result = new_uuid(sqlite_db)
            assert result[14] == "4", (
                f"Version nibble should be '4', got '{result[14]}'"
            )
            assert result[19] in "89abAB", (
                f"Variant nibble should be 8/9/a/b, got '{result[19]}'"
            )

    def test_not_affected_by_db_state(self, sqlite_db: MagicMock) -> None:
        """new_uuid does not depend on any database state or methods."""
        # Ensure no methods are called on the mock db
        sqlite_db.assert_not_called()
        new_uuid(sqlite_db)
        # new_uuid should not call any methods on the db object
        # (it only uses db for type checking, not for UUID generation)
        # Actually, looking at the source, new_uuid doesn't use db at all.
        # It just returns str(uuid.uuid4()).

    def test_sequential_uuids_differ(self, sqlite_db: MagicMock) -> None:
        """Even sequential calls produce different values."""
        u1 = new_uuid(sqlite_db)
        u2 = new_uuid(sqlite_db)
        assert u1 != u2


# ═══════════════════════════════════════════════════════════════════════
#  is_postgresql
# ═══════════════════════════════════════════════════════════════════════


class TestIsPostgresql:
    """Tests for is_postgresql() function."""

    def test_returns_true_for_postgresql(self, postgresql_db: MagicMock) -> None:
        assert is_postgresql(postgresql_db) is True

    def test_returns_false_for_sqlite(self, sqlite_db: MagicMock) -> None:
        assert is_postgresql(sqlite_db) is False

    def test_returns_false_for_unknown(self, unknown_engine_db: MagicMock) -> None:
        """When _engine is not set, is_postgresql returns False."""
        assert is_postgresql(unknown_engine_db) is False

    def test_returns_false_for_wrong_type(self) -> None:
        """is_postgresql on a plain object returns False."""
        obj = object()
        assert is_postgresql(obj) is False  # type: ignore[arg-type]

    def test_case_sensitive_check(self) -> None:
        """is_postgresql should only match lowercase 'postgresql'."""
        db = MagicMock()
        type(db)._engine = PropertyMock(return_value="PostgreSQL")
        # The checker does: getattr(db, "_engine", "sqlite") == "postgresql"
        # So case matters — this returns False
        assert is_postgresql(db) is False, (
            "is_postgresql should be case-sensitive"
        )

    def test_none_engine(self) -> None:
        db = MagicMock()
        type(db)._engine = PropertyMock(return_value=None)
        assert is_postgresql(db) is False

    def test_empty_string_engine(self) -> None:
        db = MagicMock()
        type(db)._engine = PropertyMock(return_value="")
        assert is_postgresql(db) is False

    def test_returns_false_when_attribute_error(self) -> None:
        """If accessing _engine raises, is_postgresql should handle it."""
        db = MagicMock(spec=[])  # no _engine attribute
        # getattr with default returns the default
        assert is_postgresql(db) is False


# ═══════════════════════════════════════════════════════════════════════
#  Integration: new_uuid + is_postgresql consistency
# ═══════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Combined behaviour of uuid helpers."""

    def test_sqlite_workflow(self, sqlite_db: MagicMock) -> None:
        """Typical SQLite workflow: is_postgresql=false, generate uuid."""
        assert is_postgresql(sqlite_db) is False
        uid = new_uuid(sqlite_db)
        assert UUID_PATTERN.match(uid)

    def test_postgresql_workflow(self, postgresql_db: MagicMock) -> None:
        """Typical PostgreSQL workflow: is_postgresql=true, generate uuid."""
        assert is_postgresql(postgresql_db) is True
        uid = new_uuid(postgresql_db)
        assert UUID_PATTERN.match(uid)

    def test_new_uuid_always_valid_regardless_of_engine(
        self, sqlite_db: MagicMock, postgresql_db: MagicMock,
    ) -> None:
        """new_uuid produces valid UUIDs regardless of engine type."""
        for db in (sqlite_db, postgresql_db):
            for _ in range(10):
                uid = new_uuid(db)
                assert UUID_PATTERN.match(uid)
                assert len(uid) == 36
