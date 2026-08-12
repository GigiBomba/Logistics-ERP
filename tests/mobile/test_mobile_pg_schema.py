"""Schema validation — PostgreSQL DDL covers the mobile tables (Gate-31).

Parses ``database/schema_pg.sql`` (no live PostgreSQL connection needed) and
asserts that the three mobile tables and their key columns are present, so a
DDL regression that drops a mobile table is caught in CI.
"""
from __future__ import annotations

import os

import pytest

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "database",
    "schema_pg.sql",
)


@pytest.fixture(scope="module")
def pg_schema_text() -> str:
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return fh.read()


def _table_ddl(text: str, table: str) -> str:
    """Return the CREATE TABLE block for *table* ('' when missing)."""
    marker = f"CREATE TABLE IF NOT EXISTS {table} ("
    start = text.find(marker)
    if start == -1:
        return ""
    end = text.find("\n);", start)
    if end == -1:
        end = len(text)
    return text[start:end]


def _assert_columns(ddl: str, table: str, columns: list[str]) -> None:
    for col in columns:
        assert f"\n    {col} " in ddl or f"\n    {col}  " in ddl, (
            f"{table} is missing column {col}"
        )


# ── mobile_devices ───────────────────────────────────────────────────────

def test_mobile_devices_table_present(pg_schema_text):
    assert "CREATE TABLE IF NOT EXISTS mobile_devices (" in pg_schema_text


def test_mobile_devices_key_columns_and_types(pg_schema_text):
    ddl = _table_ddl(pg_schema_text, "mobile_devices")
    _assert_columns(ddl, "mobile_devices", [
        "id", "user_id", "company_id", "device_id", "device_name",
        "token", "platform", "is_active", "last_seen", "ip_address", "created_at",
    ])
    assert "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY" in ddl
    assert "is_active   BOOLEAN NOT NULL DEFAULT TRUE" in ddl
    assert "created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()" in ddl
    assert "UNIQUE (company_id, device_id)" in ddl


# ── mobile_messages ──────────────────────────────────────────────────────

def test_mobile_messages_table_present(pg_schema_text):
    assert "CREATE TABLE IF NOT EXISTS mobile_messages (" in pg_schema_text


def test_mobile_messages_key_columns(pg_schema_text):
    ddl = _table_ddl(pg_schema_text, "mobile_messages")
    _assert_columns(ddl, "mobile_messages", [
        "id", "company_id", "sender_id", "receiver_id", "text",
        "transport_id", "is_read", "created_at",
    ])
    assert "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY" in ddl
    assert "is_read       INTEGER NOT NULL DEFAULT 0" in ddl


# ── sync_cursors ─────────────────────────────────────────────────────────

def test_sync_cursors_table_present(pg_schema_text):
    assert "CREATE TABLE IF NOT EXISTS sync_cursors (" in pg_schema_text


def test_sync_cursors_key_columns_and_pk(pg_schema_text):
    ddl = _table_ddl(pg_schema_text, "sync_cursors")
    _assert_columns(ddl, "sync_cursors", [
        "user_id", "company_id", "entity_type", "cursor", "updated_at",
    ])
    assert "PRIMARY KEY (user_id, company_id, entity_type)" in ddl
    assert "updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()" in ddl
