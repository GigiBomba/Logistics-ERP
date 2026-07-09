"""Shared test infrastructure: in-memory SQLite database with full schema."""
import sqlite3
import threading
from typing import Any, Dict, Optional


class _ThreadSafeConnection:
    """A proxy around ``sqlite3.Connection`` that serialises all calls with an RLock.

    This lets concurrency tests share a single in-memory database across
    threads without SQLite's ``cannot start a transaction within a transaction``
    or ``SQLite objects created in a thread can only be used in that same thread``
    errors.  Each individual ``execute``, ``executemany``, and ``commit`` call
    is serialised — this is sufficient to prevent SQLite-level thread safety
    errors in test scenarios.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._lock = threading.RLock()

    def __getattr__(self, name):
        """Delegate attribute access to the underlying connection."""
        return getattr(self._conn, name)

    def execute(self, sql, parameters=()):
        with self._lock:
            return self._conn.execute(sql, parameters)

    def commit(self):
        with self._lock:
            return self._conn.commit()

    def executemany(self, sql, parameters):
        with self._lock:
            return self._conn.executemany(sql, parameters)


class InMemoryDB:
    """Lightweight in-memory database that mimics DatabaseManager's interface.

    Thread-safe: uses a reentrant lock via ``_ThreadSafeConnection`` so that
    tests can safely share a single ``InMemoryDB`` across threads.
    """

    def __init__(self):
        raw_conn = sqlite3.connect(":memory:", check_same_thread=False)
        raw_conn.row_factory = sqlite3.Row
        raw_conn.execute("PRAGMA journal_mode=WAL")
        self.conn = _ThreadSafeConnection(raw_conn)
        self._init_schema()

    def _init_schema(self):
        from database.schema import (
            TABLE_TRIPS, TABLE_TRUCKS, TABLE_DRIVERS, TABLE_CLIENTS,
            TABLE_INVOICES, TABLE_ALERTS, TABLE_ROUTE_HISTORY_V2,
            TABLE_ROUTE_EVENTS, TABLE_TRUCK_ROUTE_ASSIGNMENTS,
            TABLE_SETTINGS, TABLE_EMAIL_LOGS, TABLE_TRIP_STATUS_HISTORY,
            TABLE_OPERATION_EVENTS, TABLE_DRIVER_TRUCK_ASSIGNMENTS,
            TABLE_MAINTENANCE_RECORDS, TABLE_MAINTENANCE_SCHEDULES,
            TABLE_TRUCK_HEALTH_SCORES,
            TABLE_TACHO_IMPORTS, TABLE_TACHO_DRIVER_ACTIVITY,
            TABLE_TACHO_VEHICLE_DATA,
            TABLE_CLIENT_CONTACTS, TABLE_CLIENT_TAGS,
            TABLE_PROFORMA_INVOICES, TABLE_INVOICE_REMINDERS,
            TABLE_ROUTES, TABLE_ROUTE_HISTORY,
            TABLE_DOCUMENTS, TABLE_DOCUMENT_LINKS, TABLE_DOCUMENT_VERSIONS,
            TABLE_CONTRACTS, TABLE_DOCUMENT_TEMPLATES,
            TABLE_CMR_COUNTER, TABLE_SUCCESSIVE_CARRIERS, TABLE_CMR_AUDIT_LOG,
            TABLE_DOCUMENT_PIPELINE_RUNS, TABLE_DOCUMENT_PACKAGE,
            TABLE_DOCUMENT_PACKAGE_ITEMS,
            TABLE_RECEIPTS,
            TABLE_AUTOMAIL_TEMPLATES, TABLE_AUTOMAIL_SCHEDULES,
            TABLE_AUTOMAIL_CLIENT_OVERRIDES, TABLE_AUTOMAIL_SETTINGS,
            TABLE_COMPANIES, TABLE_USERS, TABLE_GPS_TELEMETRY,
            TABLE_MAINTENANCE,
            ALTER_TRIPS_ADD_DRIVER_ID, ALTER_TRIPS_ADD_TRUCK_ID,
            ALTER_CLIENTS_ADD_TYPE, ALTER_CLIENTS_ADD_PAYMENT_TERMS,
            ALTER_CLIENTS_ADD_CREDIT_LIMIT, ALTER_CLIENTS_ADD_DEFAULT_RATE,
            ALTER_CLIENTS_ADD_RATING,
            ALTER_TRIPS_ADD_CMR_NUMBER, ALTER_TRIPS_ADD_CMR_SEQUENCE,
            ALTER_CLIENTS_ADD_EORI_NUMBER, ALTER_CLIENTS_ADD_COUNTRY,
            ALTER_CLIENTS_ADD_CONSIGNEE_CONTACT_NAME,
            ALTER_CLIENTS_ADD_CONSIGNEE_CONTACT_PHONE,
            ALTER_TRUCKS_ADD_TRAILER_PLATE, ALTER_TRUCKS_ADD_MAX_PAYLOAD_KG,
            ALTER_TRUCKS_ADD_CMR_INSURANCE, ALTER_TRUCKS_ADD_CMR_INSURANCE_EXPIRY,
            ALTER_TRUCKS_ADD_TACHOGRAPH, ALTER_TRUCKS_ADD_TRACKING_DEVICE_ID,
            ALTER_DRIVERS_ADD_PASSPORT_NUMBER, ALTER_DRIVERS_ADD_PASSPORT_EXPIRY,
            ALTER_DRIVERS_ADD_ADR_CERTIFICATE, ALTER_DRIVERS_ADD_ADR_CERTIFICATE_EXPIRY,
            ALTER_DRIVERS_ADD_CARD_NUMBER,
            ALTER_DOCUMENTS_ADD_TEXT_CONTENT, ALTER_DOCUMENTS_ADD_EXPIRY_DATE,
            ALTER_DOCUMENTS_ADD_SIGNED_BY, ALTER_DOCUMENTS_ADD_SIGNED_AT,
            ALTER_DOCUMENTS_ADD_COPY_TYPE, ALTER_DOCUMENTS_ADD_CMR_NUMBER,
            ALTER_DOCUMENTS_ADD_CMR_METADATA, ALTER_DOCUMENTS_ADD_IS_SIGNED,
            ALTER_DOCUMENTS_ADD_EXTRACTED_DATA, ALTER_DOCUMENTS_ADD_AUTOMATION_TAGS,
            ALTER_DOCUMENTS_ADD_OCR_TEXT, ALTER_DOCUMENTS_ADD_OCR_RUN_AT,
            ALTER_DOCUMENTS_ADD_OCR_ENGINE,
        )
        self.conn.execute(TABLE_TRIPS)
        self.conn.execute(TABLE_TRUCKS)
        self.conn.execute(TABLE_DRIVERS)
        self.conn.execute(TABLE_CLIENTS)
        self.conn.execute(TABLE_INVOICES)
        self.conn.execute(TABLE_ALERTS)
        self.conn.execute(TABLE_ROUTE_HISTORY_V2)
        self.conn.execute(TABLE_ROUTE_EVENTS)
        self.conn.execute(TABLE_TRUCK_ROUTE_ASSIGNMENTS)
        self.conn.execute(TABLE_SETTINGS)
        self.conn.execute(TABLE_EMAIL_LOGS)
        self.conn.execute(TABLE_TRIP_STATUS_HISTORY)
        self.conn.execute(TABLE_OPERATION_EVENTS)
        self.conn.execute(TABLE_DRIVER_TRUCK_ASSIGNMENTS)
        self.conn.execute(TABLE_MAINTENANCE_RECORDS)
        self.conn.execute(TABLE_MAINTENANCE_SCHEDULES)
        self.conn.execute(TABLE_TRUCK_HEALTH_SCORES)
        self.conn.execute(TABLE_TACHO_IMPORTS)
        self.conn.execute(TABLE_TACHO_DRIVER_ACTIVITY)
        self.conn.execute(TABLE_TACHO_VEHICLE_DATA)
        self.conn.execute(TABLE_CLIENT_CONTACTS)
        self.conn.execute(TABLE_CLIENT_TAGS)
        self.conn.execute(TABLE_PROFORMA_INVOICES)
        self.conn.execute(TABLE_INVOICE_REMINDERS)
        self.conn.execute(TABLE_ROUTES)
        self.conn.execute(TABLE_ROUTE_HISTORY)
        self.conn.execute(TABLE_DOCUMENTS)
        self.conn.execute(TABLE_DOCUMENT_LINKS)
        self.conn.execute(TABLE_DOCUMENT_VERSIONS)
        self.conn.execute(TABLE_CONTRACTS)
        self.conn.execute(TABLE_DOCUMENT_TEMPLATES)
        self.conn.execute(TABLE_CMR_COUNTER)
        self.conn.execute(TABLE_SUCCESSIVE_CARRIERS)
        self.conn.execute(TABLE_CMR_AUDIT_LOG)
        self.conn.execute(TABLE_DOCUMENT_PIPELINE_RUNS)
        self.conn.execute(TABLE_DOCUMENT_PACKAGE)
        self.conn.execute(TABLE_DOCUMENT_PACKAGE_ITEMS)
        self.conn.execute(TABLE_RECEIPTS)
        self.conn.execute(TABLE_AUTOMAIL_TEMPLATES)
        self.conn.execute(TABLE_AUTOMAIL_SCHEDULES)
        self.conn.execute(TABLE_AUTOMAIL_CLIENT_OVERRIDES)
        self.conn.execute(TABLE_AUTOMAIL_SETTINGS)
        self.conn.execute(TABLE_COMPANIES)
        self.conn.execute(TABLE_USERS)
        self.conn.execute(TABLE_GPS_TELEMETRY)
        self.conn.execute(TABLE_MAINTENANCE)
        # Apply migrations (columns added after initial schema).
        # Some may already exist if the CREATE TABLE was updated — ignore duplicates.
        for alter_sql in [
            ALTER_TRIPS_ADD_DRIVER_ID,
            ALTER_TRIPS_ADD_TRUCK_ID,
            "ALTER TABLE trips ADD COLUMN client_id INTEGER REFERENCES clients(id)",
            "ALTER TABLE trips ADD COLUMN context_json TEXT",
            "ALTER TABLE trips ADD COLUMN route_history_v2_id INTEGER REFERENCES route_history_v2(id)",
            "ALTER TABLE trips ADD COLUMN truck_consumption_l_per_100km REAL",
            ALTER_CLIENTS_ADD_TYPE,
            ALTER_CLIENTS_ADD_PAYMENT_TERMS,
            ALTER_CLIENTS_ADD_CREDIT_LIMIT,
            ALTER_CLIENTS_ADD_DEFAULT_RATE,
            ALTER_CLIENTS_ADD_RATING,
            "ALTER TABLE trips ADD COLUMN loading_country TEXT",
            "ALTER TABLE trips ADD COLUMN delivery_country TEXT",
            "ALTER TABLE trips ADD COLUMN hs_code TEXT",
            "ALTER TABLE trips ADD COLUMN carrier_instructions TEXT",
            "ALTER TABLE trips ADD COLUMN carrier_reservations TEXT",
            "ALTER TABLE trips ADD COLUMN special_agreements TEXT",
            "ALTER TABLE trips ADD COLUMN carriage_payer TEXT",
            "ALTER TABLE trips ADD COLUMN documents_attached TEXT",
            "ALTER TABLE trips ADD COLUMN place_of_loading TEXT",
            "ALTER TABLE trips ADD COLUMN place_of_loading_date TEXT",
            "ALTER TABLE trips ADD COLUMN adr_info_json TEXT",
            "ALTER TABLE trips ADD COLUMN cmr_status TEXT DEFAULT 'draft'",
            "ALTER TABLE trips ADD COLUMN cmr_remarks TEXT",
            "ALTER TABLE trips ADD COLUMN vat_percent REAL DEFAULT 0",
            "ALTER TABLE trips ADD COLUMN price_pre_vat REAL DEFAULT 0",
            "ALTER TABLE trips ADD COLUMN cargo_description TEXT",
            "ALTER TABLE trips ADD COLUMN cargo_marks TEXT",
            "ALTER TABLE trips ADD COLUMN package_count INTEGER",
            "ALTER TABLE trips ADD COLUMN package_type TEXT",
            "ALTER TABLE trips ADD COLUMN gross_weight_kg REAL",
            "ALTER TABLE trips ADD COLUMN volume_m3 REAL",
            ALTER_TRIPS_ADD_CMR_NUMBER,
            ALTER_TRIPS_ADD_CMR_SEQUENCE,
            ALTER_CLIENTS_ADD_EORI_NUMBER,
            ALTER_CLIENTS_ADD_COUNTRY,
            ALTER_CLIENTS_ADD_CONSIGNEE_CONTACT_NAME,
            ALTER_CLIENTS_ADD_CONSIGNEE_CONTACT_PHONE,
            ALTER_TRUCKS_ADD_TRAILER_PLATE,
            ALTER_TRUCKS_ADD_MAX_PAYLOAD_KG,
            ALTER_TRUCKS_ADD_CMR_INSURANCE,
            ALTER_TRUCKS_ADD_CMR_INSURANCE_EXPIRY,
            ALTER_TRUCKS_ADD_TACHOGRAPH,
            ALTER_TRUCKS_ADD_TRACKING_DEVICE_ID,
            ALTER_DRIVERS_ADD_PASSPORT_NUMBER,
            ALTER_DRIVERS_ADD_PASSPORT_EXPIRY,
            ALTER_DRIVERS_ADD_ADR_CERTIFICATE,
            ALTER_DRIVERS_ADD_ADR_CERTIFICATE_EXPIRY,
            ALTER_DRIVERS_ADD_CARD_NUMBER,
            ALTER_DOCUMENTS_ADD_TEXT_CONTENT,
            ALTER_DOCUMENTS_ADD_EXPIRY_DATE,
            ALTER_DOCUMENTS_ADD_SIGNED_BY,
            ALTER_DOCUMENTS_ADD_SIGNED_AT,
            ALTER_DOCUMENTS_ADD_COPY_TYPE,
            ALTER_DOCUMENTS_ADD_CMR_NUMBER,
            ALTER_DOCUMENTS_ADD_CMR_METADATA,
            ALTER_DOCUMENTS_ADD_IS_SIGNED,
            ALTER_DOCUMENTS_ADD_EXTRACTED_DATA,
            ALTER_DOCUMENTS_ADD_AUTOMATION_TAGS,
            ALTER_DOCUMENTS_ADD_OCR_TEXT,
            ALTER_DOCUMENTS_ADD_OCR_RUN_AT,
            ALTER_DOCUMENTS_ADD_OCR_ENGINE,
            "ALTER TABLE trucks ADD COLUMN odometer_km REAL",
        ]:
            try:
                self.conn.execute(alter_sql)
            except Exception:
                pass
        self.conn.commit()

    @staticmethod
    def row_to_dict(row) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def rows_to_dicts(rows) -> list:
        return [dict(r) for r in rows] if rows else []

    def get_trip_by_id(self, trip_id: int) -> Optional[Dict[str, Any]]:
        return self.row_to_dict(
            self.conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
        )

    def get_all_trips(self, limit: int = 500):
        return self.rows_to_dicts(
            self.conn.execute("SELECT * FROM trips ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        )

    def get_filtered_trips(self, search="", truck="", status="", limit: int = 200):
        query = "SELECT * FROM trips WHERE 1=1"
        params = []
        if search:
            query += " AND (client_name LIKE ? OR driver_name LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if truck:
            query += " AND truck_number = ?"
            params.append(truck)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self.rows_to_dicts(self.conn.execute(query, params).fetchall())

    def get_all_trucks(self, active_only=False):
        """Mirror DatabaseManager.get_all_trucks for in-memory tests."""
        query = "SELECT * FROM trucks"
        params = []
        if active_only:
            query += " WHERE active_status = 1 OR active_status IS NULL"
        query += " ORDER BY id"
        return self.rows_to_dicts(self.conn.execute(query, params).fetchall())

    def get_truck_by_id(self, truck_id: int):
        """Mirror DatabaseManager.get_truck_by_id for in-memory tests."""
        return self.row_to_dict(
            self.conn.execute("SELECT * FROM trucks WHERE id = ?", (truck_id,)).fetchone()
        )

    def create_invoice_record(self, trip_id, inv_number, amount, due_date):
        from datetime import datetime
        try:
            self.conn.execute(
                "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status) "
                "VALUES (?, ?, ?, ?, ?, 'Unpaid')",
                (trip_id, inv_number, datetime.now().strftime("%Y-%m-%d"), due_date, amount),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass


def make_db() -> InMemoryDB:
    return InMemoryDB()
