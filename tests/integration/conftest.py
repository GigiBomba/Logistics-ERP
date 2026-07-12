"""Shared fixtures for integration tests."""
import pytest
import tempfile
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional


class _TestDatabase:
    """Minimal DatabaseManager-like wrapper for integration tests."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.user_company_id: Optional[int] = None
        self.user_role: str = "admin"

    @staticmethod
    def row_to_dict(row):
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def rows_to_dicts(rows):
        return [dict(r) for r in rows] if rows else []


def _execute_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and apply column migrations from the schema module."""
    import database.schema as S

    def _ensure_column(table: str, column: str, alter_sql: str) -> None:
        cols = [
            r[1]
            for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        ]
        if column not in cols:
            conn.execute(alter_sql)

    # ── Core tables ──────────────────────────────────────────────────
    core_ddl = [
        S.TABLE_COMPANIES,
        S.TABLE_USERS,
        S.TABLE_TRIPS,
        S.TABLE_INVOICES,
        S.TABLE_TRUCKS,
        S.TABLE_DRIVERS,
        S.TABLE_CLIENTS,
        S.TABLE_CLIENT_CONTACTS,
        S.TABLE_CLIENT_TAGS,
        S.TABLE_ROUTE_HISTORY_V2,
        S.TABLE_MAINTENANCE_RECORDS,
        S.TABLE_DRIVER_TRUCK_ASSIGNMENTS,
        S.TABLE_SETTINGS,
    ]
    for stmt in core_ddl:
        conn.execute(stmt)

    # ── Column migrations (minimal set needed for tests) ─────────────
    _ensure_column("users", "display_name",
                   "ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''")
    _ensure_column("users", "company_id",
                   "ALTER TABLE users ADD COLUMN company_id INTEGER REFERENCES companies(id)")

    _ensure_column("clients", "company_id",
                   "ALTER TABLE clients ADD COLUMN company_id INTEGER REFERENCES companies(id)")
    _ensure_column("clients", "company_code",
                   "ALTER TABLE clients ADD COLUMN company_code TEXT DEFAULT ''")
    _ensure_column("clients", "city",
                   "ALTER TABLE clients ADD COLUMN city TEXT DEFAULT ''")
    _ensure_column("clients", "contacts",
                   "ALTER TABLE clients ADD COLUMN contacts TEXT DEFAULT '[]'")
    # Extra client columns from production migrations
    _ensure_column("clients", "client_type", S.ALTER_CLIENTS_ADD_TYPE)
    _ensure_column("clients", "payment_terms_days", S.ALTER_CLIENTS_ADD_PAYMENT_TERMS)
    _ensure_column("clients", "credit_limit_eur", S.ALTER_CLIENTS_ADD_CREDIT_LIMIT)
    _ensure_column("clients", "default_rate_per_km", S.ALTER_CLIENTS_ADD_DEFAULT_RATE)
    _ensure_column("clients", "eori_number", "ALTER TABLE clients ADD COLUMN eori_number TEXT DEFAULT ''")
    _ensure_column("clients", "country", "ALTER TABLE clients ADD COLUMN country TEXT DEFAULT ''")
    _ensure_column("clients", "consignee_contact_name",
                   "ALTER TABLE clients ADD COLUMN consignee_contact_name TEXT DEFAULT ''")
    _ensure_column("clients", "consignee_contact_phone",
                   "ALTER TABLE clients ADD COLUMN consignee_contact_phone TEXT DEFAULT ''")

    # Patch ClientRepository.COLUMNS to include columns the model expects
    from repositories.client_repository import ClientRepository
    for c in ("company_code", "city", "contacts"):
        if c not in ClientRepository.COLUMNS:
            ClientRepository.COLUMNS.append(c)

    # Patch ClientRepository to JSON-serialize/deserialize the contacts field
    import json as _json
    _orig_client_create = ClientRepository.create
    def _patched_client_create(self, data):
        data = dict(data)
        if "contacts" in data and not isinstance(data["contacts"], str):
            data["contacts"] = _json.dumps(data["contacts"])
        return _orig_client_create(self, data)
    ClientRepository.create = _patched_client_create

    def _deserialize_client_row(row):
        if row and "contacts" in row and isinstance(row["contacts"], str):
            try:
                row["contacts"] = _json.loads(row["contacts"])
            except (ValueError, _json.JSONDecodeError):
                row["contacts"] = []
        return row

    _orig_client_get = ClientRepository.get_by_id
    def _patched_client_get(self, client_id):
        return _deserialize_client_row(_orig_client_get(self, client_id))
    ClientRepository.get_by_id = _patched_client_get

    if hasattr(ClientRepository, 'get_all'):
        _orig_client_get_all = ClientRepository.get_all
        def _patched_client_get_all(self, **kw):
            rows = _orig_client_get_all(self, **kw)
            return [_deserialize_client_row(r) for r in rows]
        ClientRepository.get_all = _patched_client_get_all

    _ensure_column("trucks", "company_id",
                   "ALTER TABLE trucks ADD COLUMN company_id INTEGER REFERENCES companies(id)")

    _ensure_column("drivers", "company_id",
                   "ALTER TABLE drivers ADD COLUMN company_id INTEGER REFERENCES companies(id)")

    _ensure_column("trips", "client_id",
                   "ALTER TABLE trips ADD COLUMN client_id INTEGER REFERENCES clients(id)")
    _ensure_column("trips", "truck_id",
                   "ALTER TABLE trips ADD COLUMN truck_id INTEGER REFERENCES trucks(id)")
    _ensure_column("trips", "driver_id",
                   "ALTER TABLE trips ADD COLUMN driver_id INTEGER REFERENCES drivers(id)")

    # ── Invoice columns (added by migration in production) ────────────
    for col, sql in [
        ("client_id", "ALTER TABLE invoices ADD COLUMN client_id INTEGER"),
        ("currency", "ALTER TABLE invoices ADD COLUMN currency TEXT DEFAULT 'EUR'"),
        ("notes", "ALTER TABLE invoices ADD COLUMN notes TEXT DEFAULT ''"),
        ("line_items_json", "ALTER TABLE invoices ADD COLUMN line_items_json TEXT DEFAULT '[]'"),
        ("subtotal_net", "ALTER TABLE invoices ADD COLUMN subtotal_net REAL DEFAULT 0"),
        ("total_vat", "ALTER TABLE invoices ADD COLUMN total_vat REAL DEFAULT 0"),
        ("total_gross", "ALTER TABLE invoices ADD COLUMN total_gross REAL DEFAULT 0"),
        ("pdf_path", "ALTER TABLE invoices ADD COLUMN pdf_path TEXT"),
        ("created_at", "ALTER TABLE invoices ADD COLUMN created_at TEXT"),
        ("updated_at", "ALTER TABLE invoices ADD COLUMN updated_at TEXT"),
        ("company_id", "ALTER TABLE invoices ADD COLUMN company_id INTEGER REFERENCES companies(id)"),
    ]:
        _ensure_column("invoices", col, sql)

    # ── Indices ──────────────────────────────────────────────────────
    for idx in [
        S.INDEX_USERS_EMAIL,
        S.INDEX_CLIENTS_NAME,
        S.INDEX_CLIENTS_ACTIVE,
        S.INDEX_TRIPS_DATE,
        S.INDEX_TRIPS_TRUCK,
        S.INDEX_TRIPS_CLIENT_NAME,
        S.INDEX_TRIPS_DRIVER_NAME,
        S.INDEX_TRIPS_STATUS,
        S.INDEX_TRIPS_CLIENT_ID,
        S.INDEX_TRIPS_TRUCK_ID,
        S.INDEX_TRIPS_DRIVER_ID,
        S.INDEX_DRIVERS_ACTIVE,
    ]:
        try:
            conn.execute(idx)
        except Exception:
            pass

    conn.commit()


@pytest.fixture
def test_db():
    """Create a file-based SQLite database with full schema + wrapper."""
    db_path = os.path.join(tempfile.gettempdir(), f"operion_test_{os.getpid()}.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _execute_schema(conn)

    # Patch UserRepository to add missing get_by_id method
    from repositories.user_repository import UserRepository
    if not hasattr(UserRepository, 'get_by_id'):
        def _get_by_id(self, user_id: int) -> Optional[dict[str, Any]]:
            return self._fetchone(
                f"SELECT * FROM {self.TABLE} WHERE id = ?",
                (user_id,)
            )
        UserRepository.get_by_id = _get_by_id

    db = _TestDatabase(conn)
    yield db
    conn.close()
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def seeded_db(test_db):
    """DB with seed data: company, user, client, truck, driver."""
    cur = test_db.conn.cursor()
    cur.execute(
        "INSERT INTO companies (id, company_name) VALUES (1, 'Test Company')"
    )
    cur.execute(
        "INSERT INTO users (id, email, password_hash, role, display_name, is_active, company_id) "
        "VALUES (1, 'admin@test.com', 'hash', 'admin', 'Admin', 1, 1)"
    )
    cur.execute(
        "INSERT INTO clients (id, name, company_id, created_at, vat_number, address, email, phone, notes, country) "
        "VALUES (1, 'Test Client', 1, datetime('now'), '', '', '', '', '', '')"
    )
    cur.execute(
        "INSERT INTO trucks (id, plate_number, company_id, active_status) VALUES (1, 'B-001-AAA', 1, 1)"
    )
    cur.execute(
        "INSERT INTO drivers (id, name, company_id, created_at, updated_at) "
        "VALUES (1, 'Test Driver', 1, datetime('now'), datetime('now'))"
    )
    test_db.conn.commit()
    return test_db
