"""Tests for services.payment_batch_service — recipient resolution, CSV export, validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from services.payment_batch_service import PaymentBatchService, BANK_CSV_COLUMNS
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    imdb = InMemoryDB()
    _ensure_tables(imdb)
    return imdb


@pytest.fixture
def svc(db) -> PaymentBatchService:
    return PaymentBatchService(db)


def _ensure_tables(db: InMemoryDB):
    """Create required tables and seed test data."""
    db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, phone TEXT, email TEXT, is_active INTEGER DEFAULT 1,
            bank_name TEXT DEFAULT '', bank_account TEXT DEFAULT '',
            bank_code TEXT DEFAULT '', bank_bic TEXT DEFAULT '', iban TEXT DEFAULT '',
            payment_reference TEXT DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, phone TEXT, email TEXT, is_active INTEGER DEFAULT 1,
            bank_account TEXT DEFAULT '', bank_code TEXT DEFAULT '',
            bank_bic TEXT DEFAULT '', iban TEXT DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, license_number TEXT
        );
        CREATE TABLE IF NOT EXISTS payment_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_name TEXT NOT NULL,
            recipient_type TEXT NOT NULL DEFAULT 'custom',
            bank_name TEXT DEFAULT '', bank_account TEXT DEFAULT '',
            bank_code TEXT DEFAULT '', bank_bic TEXT DEFAULT '', iban TEXT DEFAULT '',
            payment_reference TEXT DEFAULT '',
            contact_name TEXT DEFAULT '', contact_email TEXT DEFAULT '',
            contact_phone TEXT DEFAULT '', notes TEXT DEFAULT '', is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, company_id INTEGER
        );
    """)


def _seed_client(db: InMemoryDB, name: str, bank_account: str = "", iban: str = ""):
    now = datetime.utcnow().isoformat()
    db.conn.execute(
        "INSERT INTO clients (name, bank_account, bank_bic, bank_code, iban, created_at, updated_at, is_active) "
        "VALUES (?, ?, 'BIC1', 'CODE1', ?, ?, ?, 1)",
        (name, bank_account, iban, now, now),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _seed_driver(db: InMemoryDB, name: str, bank_account: str = "", iban: str = ""):
    now = datetime.utcnow().isoformat()
    db.conn.execute(
        "INSERT INTO drivers (name, bank_account, bank_code, bank_bic, iban, created_at, updated_at, is_active, license_number) "
        "VALUES (?, ?, 'DRV-CODE', 'DRVBIC', ?, ?, ?, 1, 'LIC')",
        (name, bank_account, iban, now, now),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _seed_profile(db: InMemoryDB, name: str, bank_account: str = "",
                  iban: str = "", recipient_type: str = "custom"):
    now = datetime.utcnow().isoformat()
    db.conn.execute(
        "INSERT INTO payment_profiles (profile_name, recipient_type, bank_name, "
        "bank_account, bank_code, bank_bic, iban, created_at, updated_at, is_active) "
        "VALUES (?, ?, 'TestBank', ?, 'PROF-CODE', 'PROFBIC', ?, ?, ?, 1)",
        (name, recipient_type, bank_account, iban, now, now),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Recipient Resolution ─────────────────────────────────────────────


class TestGetAllRecipients:
    def test_returns_clients_with_bank_info(self, db, svc):
        _seed_client(db, "Client A", bank_account="12345")
        _seed_client(db, "Client B", bank_account="")  # no bank info, should be skipped
        recipients = svc.get_all_recipients()
        names = [r["recipient_name"] for r in recipients]
        assert "Client A" in names
        assert "Client B" not in names

    def test_returns_drivers_with_bank_info(self, db, svc):
        _seed_driver(db, "Driver X", bank_account="67890")
        recipients = svc.get_all_recipients()
        names = [r["recipient_name"] for r in recipients]
        assert "Driver X" in names

    def test_returns_profiles_with_bank_info(self, db, svc):
        _seed_profile(db, "Custom Payee", bank_account="11111")
        recipients = svc.get_all_recipients()
        names = [r["recipient_name"] for r in recipients]
        assert "Custom Payee" in names

    def test_skips_without_bank_or_iban(self, db, svc):
        _seed_client(db, "No Payment", bank_account="", iban="")
        recipients = svc.get_all_recipients()
        names = [r["recipient_name"] for r in recipients]
        assert "No Payment" not in names

    def test_includes_iban_only(self, db, svc):
        _seed_client(db, "IBAN Only", iban="DE89370400440532013000")
        recipients = svc.get_all_recipients()
        names = [r["recipient_name"] for r in recipients]
        assert "IBAN Only" in names

    def test_filters_by_query(self, db, svc):
        _seed_client(db, "Alpha Corp", bank_account="123")
        _seed_client(db, "Beta LLC", bank_account="456")
        recipients = svc.get_all_recipients(query="Alpha")
        assert len(recipients) == 1
        assert recipients[0]["recipient_name"] == "Alpha Corp"

    def test_filters_by_query_case_insensitive(self, db, svc):
        _seed_driver(db, "John Driver", bank_account="789")
        recipients = svc.get_all_recipients(query="john")
        assert len(recipients) == 1


# ── CSV Export ─────────────────────────────────────────────────────


class TestBuildBatchCSV:
    def test_generates_header(self, svc):
        csv_str = svc.build_batch_csv([])
        assert csv_str.startswith('"recipient_name"')

    def test_generates_row(self, svc):
        items = [{
            "recipient_name": "Test Payee",
            "bank_name": "Test Bank",
            "bank_account": "123456",
            "bank_code": "SORT-01",
            "bank_bic": "BIC123",
            "iban": "GB29NWBK60161331926819",
            "amount": 1500.50,
            "currency": "EUR",
            "payment_reference": "INV-001",
            "recipient_type": "client",
        }]
        csv_str = svc.build_batch_csv(items)
        assert "Test Payee" in csv_str
        assert "1500.5" in csv_str
        assert "EUR" in csv_str

    def test_multiple_rows(self, svc):
        items = [
            {"recipient_name": "A", "amount": 100, "recipient_type": "client"},
            {"recipient_name": "B", "amount": 200, "recipient_type": "driver"},
        ]
        csv_str = svc.build_batch_csv(items)
        lines = csv_str.strip().split("\r\n")
        # header + 2 data rows
        assert len(lines) == 3


class TestBuildBatchCSVFromRequest:
    def test_resolves_client_bank_info(self, db, svc):
        cid = _seed_client(db, "Resolved Client", bank_account="CLIENT-ACC", iban="CLIENT-IBAN")
        items = [{
            "recipient_id": cid,
            "recipient_type": "client",
            "amount": 500.0,
            "currency": "EUR",
            "payment_reference": "REF001",
        }]
        csv_str = svc.build_batch_csv_from_request(items)
        assert "Resolved Client" in csv_str
        assert "CLIENT-ACC" in csv_str
        assert "CLIENT-IBAN" in csv_str

    def test_resolves_driver_bank_info(self, db, svc):
        did = _seed_driver(db, "Resolved Driver", bank_account="DRV-ACC")
        items = [{
            "recipient_id": did,
            "recipient_type": "driver",
            "amount": 300.0,
            "currency": "RON",
        }]
        csv_str = svc.build_batch_csv_from_request(items)
        assert "Resolved Driver" in csv_str
        assert "DRV-ACC" in csv_str

    def test_resolves_profile_bank_info(self, db, svc):
        pid = _seed_profile(db, "Resolved Profile", bank_account="PROF-ACC", recipient_type="government")
        items = [{
            "recipient_id": pid,
            "recipient_type": "government",
            "amount": 1000.0,
            "currency": "EUR",
        }]
        csv_str = svc.build_batch_csv_from_request(items)
        assert "Resolved Profile" in csv_str
        assert "PROF-ACC" in csv_str

    def test_unknown_recipient_handled(self, db, svc):
        items = [{
            "recipient_id": 99999,
            "recipient_type": "client",
            "amount": 100.0,
            "currency": "EUR",
        }]
        # should not crash on unknown recipient
        csv_str = svc.build_batch_csv_from_request(items)
        assert csv_str is not None


# ── Validation ──────────────────────────────────────────────────────


class TestValidateRecipient:
    def test_valid_client(self, db, svc):
        cid = _seed_client(db, "Valid Client", bank_account="12345")
        errors = svc.validate_recipient_payment_info(cid, "client")
        assert errors == []

    def test_missing_bank_info(self, db, svc):
        cid = _seed_client(db, "No Info Client", bank_account="", iban="")
        errors = svc.validate_recipient_payment_info(cid, "client")
        assert len(errors) >= 1

    def test_unknown_recipient(self, svc):
        errors = svc.validate_recipient_payment_info(99999, "client")
        assert len(errors) >= 1

    def test_invalid_type(self, svc):
        errors = svc.validate_recipient_payment_info(1, "invalid_type")
        assert len(errors) >= 1


# ── Constants ───────────────────────────────────────────────────────


class TestConstants:
    def test_csv_columns(self):
        assert "recipient_name" in BANK_CSV_COLUMNS
        assert "bank_account" in BANK_CSV_COLUMNS
        assert "iban" in BANK_CSV_COLUMNS
        assert "amount" in BANK_CSV_COLUMNS
        assert "currency" in BANK_CSV_COLUMNS
