import logging
import os
import sqlite3
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_emitted_warnings: set = set()


def _deprecated(msg: str) -> None:
    if msg not in _emitted_warnings:
        _emitted_warnings.add(msg)
        warnings.warn(msg, DeprecationWarning, stacklevel=3)


from database import schema as _schema
from database.connection_pool import ConnectionPool

class DatabaseManager:
    def __init__(self, db_path: str, engine: str = ""):
        self._engine = engine or os.environ.get("OPERION_DB_ENGINE", "sqlite")
        self._pg_conn: Any = None
        if self._engine == "postgresql":
            self._init_pg(db_path)
        else:
            self._pool = ConnectionPool(db_path, timeout=30)
        self._init_db()

    def _init_pg(self, dsn: str) -> None:
        import psycopg2
        import psycopg2.extras
        self._pg_conn = psycopg2.connect(dsn)
        self._pg_conn.autocommit = True
        self._pg_conn.cursor_factory = psycopg2.extras.RealDictCursor

    @property
    def conn(self):
        if self._engine == "postgresql":
            return self._pg_conn
        return self._pool.conn

    def close(self):
        if self._engine == "postgresql":
            if self._pg_conn:
                self._pg_conn.close()
        else:
            self._pool.close_all()

    @staticmethod
    def row_to_dict(row):
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def rows_to_dicts(rows):
        return [dict(r) for r in rows] if rows else []

    # ── Read-only connection (engine-level sandbox) ───────────────────

    @staticmethod
    def open_readonly_connection(db_path: str) -> sqlite3.Connection:
        """Open a **read-only** SQLite connection to *db_path*.

        The connection is opened with ``uri=True&mode=ro``, which tells
        the SQLite engine to reject any write operation (INSERT, UPDATE,
        DELETE, DROP, etc.) at the file-system + engine level.  This is
        the primary sandbox for the ``POST /admin/db/query`` endpoint.

        For ``:memory:`` databases (testing), falls back to a normal
        connection — the engine-level sandbox cannot be applied, but
        string filtering still protects the endpoint.

        The caller is responsible for calling ``.close()`` on the
        returned connection.

        Raises:
            sqlite3.OperationalError: If the database file cannot be
                opened in read-only mode (e.g. missing file).
        """
        if db_path == ":memory:":
            # In-memory databases cannot use URI read-only mode.
            conn = sqlite3.connect(":memory:", timeout=10, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn

        uri = f"file:{os.path.abspath(db_path)}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creează tabelele și indecșii necesari."""
        self.conn.execute("BEGIN")
        self._create_tables_and_indices()
        self.conn.commit()
        self._run_column_migrations()
        self._migrate_legacy_data()

    def _create_tables_and_indices(self):
        """Execute all CREATE TABLE and CREATE INDEX statements."""
        S = _schema
        exec_stmts = [
            # Core tables
            S.TABLE_TRIPS, S.TABLE_INVOICES, S.TABLE_TRUCKS,
            S.TABLE_ROUTE_HISTORY_V2,
            S.INDEX_ROUTE_HISTORY_V2_CREATED, S.INDEX_ROUTE_HISTORY_V2_LAST_CALCULATED,
            S.INDEX_ROUTE_HISTORY_V2_TRUCK, S.INDEX_ROUTE_HISTORY_V2_PROFILE,
            S.INDEX_ROUTE_HISTORY_V2_FINGERPRINT,
            S.TABLE_ROUTE_EVENTS, S.TABLE_TRUCK_ROUTE_ASSIGNMENTS,
            S.INDEX_ROUTE_EVENTS_ROUTE, S.INDEX_ROUTE_EVENTS_TYPE,
            S.INDEX_TRUCK_ROUTE_ASSIGNMENTS_TRUCK, S.INDEX_TRUCK_ROUTE_ASSIGNMENTS_ROUTE,
            S.INDEX_TRUCK_ROUTE_ASSIGNMENTS_STATUS,
            S.INDEX_TRIPS_DATE, S.INDEX_TRIPS_TRUCK, S.INDEX_TRIPS_CLIENT_NAME,
            S.INDEX_TRIPS_DRIVER_NAME, S.INDEX_TRIPS_STATUS, S.INDEX_TRIPS_CLIENT_STATUS,
            S.INDEX_TRIPS_START_DATE, S.INDEX_TRIPS_DELIVERY_COUNTRY,
            S.INDEX_TRIPS_LOADING_COUNTRY, S.INDEX_TRIPS_DRIVER_ID,
            S.TABLE_SETTINGS, S.TABLE_EMAIL_LOGS,
            # Dunner / Invoice Reminders
            S.TABLE_INVOICE_REMINDERS, S.INDEX_INVOICE_REMINDERS_LOOKUP,
            # Operations Engine
            S.TABLE_ALERTS, S.TABLE_OPERATION_EVENTS, S.TABLE_TRIP_STATUS_HISTORY,
            S.INDEX_ALERTS_TYPE, S.INDEX_ALERTS_TRUCK, S.INDEX_ALERTS_RESOLVED,
            S.INDEX_OPERATION_EVENTS_TYPE, S.INDEX_TRIP_STATUS_HISTORY_TRIP,
            # Fleet Maintenance
            S.TABLE_MAINTENANCE_RECORDS, S.TABLE_MAINTENANCE_SCHEDULES,
            S.TABLE_TRUCK_HEALTH_SCORES,
            S.INDEX_MAINTENANCE_RECORDS_TRUCK, S.INDEX_MAINTENANCE_RECORDS_TYPE,
            S.INDEX_MAINTENANCE_RECORDS_DATE, S.INDEX_MAINTENANCE_SCHEDULES_TRUCK,
            S.INDEX_MAINTENANCE_SCHEDULES_ACTIVE,
            # Drivers
            S.TABLE_DRIVERS, S.INDEX_DRIVERS_ACTIVE, S.TABLE_DRIVER_TRUCK_ASSIGNMENTS,
            S.INDEX_DTA_DRIVER, S.INDEX_DTA_TRUCK,
            # Tachograph
            S.TABLE_TACHO_IMPORTS, S.TABLE_TACHO_DRIVER_ACTIVITY,
            S.TABLE_TACHO_VEHICLE_DATA,
            S.INDEX_TACHO_DRIVER_DATE, S.INDEX_TACHO_VEHICLE_TRUCK, S.INDEX_TACHO_IMPORTS_HASH,
            # Clients
            S.TABLE_CLIENTS, S.INDEX_CLIENTS_NAME, S.INDEX_CLIENTS_ACTIVE,
            S.TABLE_CLIENT_CONTACTS, S.INDEX_CONTACTS_CLIENT,
            S.TABLE_CLIENT_TAGS, S.INDEX_TAGS_CLIENT,
            # Document Center
            S.TABLE_DOCUMENTS, S.TABLE_DOCUMENT_LINKS,
            S.INDEX_DOCUMENTS_CATEGORY, S.INDEX_DOCUMENTS_ENTITY,
            S.INDEX_DOCUMENTS_HASH, S.INDEX_DOCUMENTS_NUMBER,
            S.INDEX_DOCUMENTS_EXPIRY_DATE,
            S.INDEX_DOC_LINKS_DOCUMENT, S.INDEX_DOC_LINKS_ENTITY,
            S.TABLE_DOCUMENT_VERSIONS, S.INDEX_VERSIONS_DOCUMENT,
            S.TABLE_CONTRACTS, S.INDEX_CONTRACTS_CLIENT, S.INDEX_CONTRACTS_STATUS,
            S.INDEX_CONTRACTS_END_DATE,
            S.TABLE_DOCUMENT_TEMPLATES,
            # CMR
            S.TABLE_CMR_COUNTER, S.TABLE_SUCCESSIVE_CARRIERS,
            S.INDEX_SUCCESSIVE_CARRIERS_TRIP, S.TABLE_CMR_AUDIT_LOG,
            S.INDEX_CMR_AUDIT_TRIP, S.INDEX_CMR_AUDIT_NUMBER,
            # Document Automation Pipeline
            S.TABLE_DOCUMENT_PIPELINE_RUNS,
            S.INDEX_PIPELINE_RUNS_UUID, S.INDEX_PIPELINE_RUNS_STATUS,
            S.INDEX_PIPELINE_RUNS_TRIP, S.INDEX_PIPELINE_RUNS_HASH,
            S.TABLE_DOCUMENT_PACKAGE, S.INDEX_PACKAGE_TRIP,
            S.INDEX_PACKAGE_UUID, S.INDEX_PACKAGE_STATUS,
            S.TABLE_DOCUMENT_PACKAGE_ITEMS, S.INDEX_PACKAGE_ITEMS_PACKAGE,
            S.INDEX_PACKAGE_ITEMS_DOCUMENT,
            S.TRIGGER_PIPELINE_RUNS_STAGE_CHECK, S.TRIGGER_PIPELINE_RUNS_STAGE_UPDATE,
            S.TRIGGER_PIPELINE_RUNS_STATUS_CHECK, S.TRIGGER_PIPELINE_RUNS_STATUS_UPDATE,
            # Proforma Invoices
            S.TABLE_PROFORMA_INVOICES,
            S.INDEX_PROFORMA_NUMBER, S.INDEX_PROFORMA_CLIENT, S.INDEX_PROFORMA_STATUS,
            # Receipts
            S.TABLE_RECEIPTS,
            S.INDEX_RECEIPT_NUMBER, S.INDEX_RECEIPT_TYPE,
            S.INDEX_RECEIPT_STATUS, S.INDEX_RECEIPT_TRIP, S.INDEX_RECEIPT_DRIVER,
            # AutoMail / Dunner
            S.TABLE_AUTOMAIL_TEMPLATES, S.TABLE_AUTOMAIL_SCHEDULES,
            S.TABLE_AUTOMAIL_CLIENT_OVERRIDES, S.TABLE_AUTOMAIL_SETTINGS,
            S.TABLE_GPS_TELEMETRY,
            # Companies (multi-tenant)
            S.TABLE_COMPANIES,
            S.INDEX_COMPANIES_NAME,
            # Users (authentication)
            S.TABLE_USERS,
            S.INDEX_USERS_EMAIL,
            S.INDEX_USERS_COMPANY,
            S.INDEX_AUTOMAIL_SCHEDULES_TEMPLATE,
            S.INDEX_AUTOMAIL_SCHEDULES_ACTIVE_SORT,
            S.INDEX_AUTOMAIL_CLIENT_OVERRIDES_CLIENT,
            S.INDEX_GPS_TRUCK, S.INDEX_GPS_RECORDED,
        ]
        for stmt in exec_stmts:
            try:
                self.conn.execute(stmt)
            except Exception as e:
                logger.warning("Schema statement failed (may be harmless): %s", e)
        try:
            self.conn.execute(S.INDEX_TRIPS_MONTH)
        except Exception:
            pass
        try:
            self.conn.execute(S.INDEX_TRIPS_START_DATE)
        except Exception:
            pass
        try:
            self.conn.execute(S.INDEX_TRIPS_DELIVERY_COUNTRY)
        except Exception:
            pass
        try:
            self.conn.execute(S.INDEX_TRIPS_LOADING_COUNTRY)
        except Exception:
            pass
        try:
            self.conn.execute(S.INDEX_TRIPS_DRIVER_ID)
        except Exception:
            pass
        try:
            self.conn.execute(S.INDEX_DOCUMENTS_EXPIRY_DATE)
        except Exception:
            pass
        try:
            self.conn.execute(S.INDEX_CONTRACTS_END_DATE)
        except Exception:
            pass
        # Document Center P2 (FTS5 is best-effort)
        # Drop old V1 FTS table if upgrading — V2 adds cmr_number + extracted_data_json columns.
        try:
            self.conn.execute(S.MIGRATION_DOCUMENTS_FTS_V2)
        except Exception as e:
            logger.warning("FTS migration (drop old table) failed: %s", e)
        for stmt in (S.TABLE_DOCUMENTS_FTS, S.TRIGGER_DOCUMENTS_FTS_INSERT,
                     S.TRIGGER_DOCUMENTS_FTS_DELETE, S.TRIGGER_DOCUMENTS_FTS_UPDATE):
            try:
                self.conn.execute(stmt)
            except Exception as e:
                logger.warning("Migration step failed: %s", e)

    def _ensure_column(self, table: str, column: str, alter_sql: str) -> None:
        """Add a column if it doesn't already exist in the table."""
        try:
            cols = [r[1] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if column not in cols:
                self.conn.execute(alter_sql)
        except Exception as e:
            logger.warning("Migration step failed: %s", e)

    def _ensure_columns(self, table: str, migrations: list) -> None:
        """Add multiple columns to a table if they don't exist."""
        try:
            cols = [r[1] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            for column, alter_sql in migrations:
                if column not in cols:
                    try:
                        self.conn.execute(alter_sql)
                    except Exception as e:
                        logger.warning("Migration step failed for %s.%s: %s", table, column, e)
        except Exception as e:
            logger.warning("Migration step failed for table %s: %s", table, e)

    def _run_column_migrations(self):
        """Apply all schema migrations — add columns, indices that may be missing."""
        S = _schema
        self._ensure_columns("documents", [
            ("text_content", S.ALTER_DOCUMENTS_ADD_TEXT_CONTENT),
            ("expiry_date", S.ALTER_DOCUMENTS_ADD_EXPIRY_DATE),
            ("signed_by", S.ALTER_DOCUMENTS_ADD_SIGNED_BY),
            ("signed_at", S.ALTER_DOCUMENTS_ADD_SIGNED_AT),
            ("copy_type", "ALTER TABLE documents ADD COLUMN copy_type TEXT DEFAULT ''"),
            ("cmr_number", "ALTER TABLE documents ADD COLUMN cmr_number TEXT DEFAULT ''"),
            ("cmr_metadata_json", "ALTER TABLE documents ADD COLUMN cmr_metadata_json TEXT DEFAULT '{}'"),
            ("is_signed", "ALTER TABLE documents ADD COLUMN is_signed INTEGER DEFAULT 0"),
            ("extracted_data_json", S.ALTER_DOCUMENTS_ADD_EXTRACTED_DATA),
            ("automation_tags", S.ALTER_DOCUMENTS_ADD_AUTOMATION_TAGS),
            ("ocr_text", S.ALTER_DOCUMENTS_ADD_OCR_TEXT),
            ("ocr_run_at", S.ALTER_DOCUMENTS_ADD_OCR_RUN_AT),
            ("ocr_engine", S.ALTER_DOCUMENTS_ADD_OCR_ENGINE),
        ])
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_copy_type ON documents(copy_type)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_cmr_number ON documents(cmr_number)")
        except Exception as e:
            logger.warning("Migration step failed: %s", e)

        self._ensure_columns("trips", [
            ("context_json", "ALTER TABLE trips ADD COLUMN context_json TEXT"),
            ("route_history_v2_id", "ALTER TABLE trips ADD COLUMN route_history_v2_id INTEGER REFERENCES route_history_v2(id)"),
            ("truck_consumption_l_per_100km", "ALTER TABLE trips ADD COLUMN truck_consumption_l_per_100km REAL"),
            ("client_id", "ALTER TABLE trips ADD COLUMN client_id INTEGER REFERENCES clients(id)"),
            ("driver_id", "ALTER TABLE trips ADD COLUMN driver_id INTEGER REFERENCES drivers(id)"),
            ("truck_id", S.ALTER_TRIPS_ADD_TRUCK_ID),
            ("price_pre_vat", "ALTER TABLE trips ADD COLUMN price_pre_vat REAL DEFAULT 0"),
            ("vat_percent", "ALTER TABLE trips ADD COLUMN vat_percent REAL DEFAULT 0"),
            ("cmr_number", "ALTER TABLE trips ADD COLUMN cmr_number TEXT"),
            ("cmr_sequence", "ALTER TABLE trips ADD COLUMN cmr_sequence INTEGER"),
            ("cargo_description", "ALTER TABLE trips ADD COLUMN cargo_description TEXT"),
            ("cargo_marks", "ALTER TABLE trips ADD COLUMN cargo_marks TEXT"),
            ("package_count", "ALTER TABLE trips ADD COLUMN package_count INTEGER"),
            ("package_type", "ALTER TABLE trips ADD COLUMN package_type TEXT"),
            ("gross_weight_kg", "ALTER TABLE trips ADD COLUMN gross_weight_kg REAL"),
            ("volume_m3", "ALTER TABLE trips ADD COLUMN volume_m3 REAL"),
            ("hs_code", "ALTER TABLE trips ADD COLUMN hs_code TEXT"),
            ("carrier_instructions", "ALTER TABLE trips ADD COLUMN carrier_instructions TEXT"),
            ("carrier_reservations", "ALTER TABLE trips ADD COLUMN carrier_reservations TEXT"),
            ("special_agreements", "ALTER TABLE trips ADD COLUMN special_agreements TEXT"),
            ("carriage_payer", "ALTER TABLE trips ADD COLUMN carriage_payer TEXT"),
            ("documents_attached", "ALTER TABLE trips ADD COLUMN documents_attached TEXT"),
            ("place_of_loading", "ALTER TABLE trips ADD COLUMN place_of_loading TEXT"),
            ("place_of_loading_date", "ALTER TABLE trips ADD COLUMN place_of_loading_date TEXT"),
            ("loading_country", "ALTER TABLE trips ADD COLUMN loading_country TEXT"),
            ("delivery_country", "ALTER TABLE trips ADD COLUMN delivery_country TEXT"),
            ("adr_info_json", "ALTER TABLE trips ADD COLUMN adr_info_json TEXT"),
            ("cmr_status", "ALTER TABLE trips ADD COLUMN cmr_status TEXT DEFAULT 'draft'"),
            ("cmr_remarks", "ALTER TABLE trips ADD COLUMN cmr_remarks TEXT"),
        ])
        try:
            self.conn.execute(S.INDEX_TRIPS_TRUCK_ID)
        except Exception as e:
            logger.warning("Migration step failed: %s", e)
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_trips_cmr_status ON trips(cmr_status)")
        except Exception as e:
            logger.warning("Migration step failed: %s", e)
        try:
            self._ensure_column("trips", "month", S.ALTER_TRIPS_ADD_MONTH)
        except Exception as e:
            logger.warning(
                "Could not add month generated column (SQLite < 3.31 or unsupported): %s", e
            )

        self._ensure_column("trucks", "tachograph_expiry", "ALTER TABLE trucks ADD COLUMN tachograph_expiry TEXT")
        self._ensure_column("trucks", "tracking_device_id", S.ALTER_TRUCKS_ADD_TRACKING_DEVICE_ID)
        self._ensure_columns("trucks", [
            ("trailer_plate", "ALTER TABLE trucks ADD COLUMN trailer_plate TEXT DEFAULT ''"),
            ("max_payload_kg", "ALTER TABLE trucks ADD COLUMN max_payload_kg REAL DEFAULT 0"),
            ("cmr_insurance_number", "ALTER TABLE trucks ADD COLUMN cmr_insurance_number TEXT DEFAULT ''"),
            ("cmr_insurance_expiry", "ALTER TABLE trucks ADD COLUMN cmr_insurance_expiry TEXT DEFAULT ''"),
        ])

        self._ensure_columns("drivers", [
            ("passport_number", "ALTER TABLE drivers ADD COLUMN passport_number TEXT DEFAULT ''"),
            ("passport_expiry", "ALTER TABLE drivers ADD COLUMN passport_expiry TEXT DEFAULT ''"),
            ("adr_certificate", "ALTER TABLE drivers ADD COLUMN adr_certificate TEXT DEFAULT ''"),
            ("adr_certificate_expiry", "ALTER TABLE drivers ADD COLUMN adr_certificate_expiry TEXT DEFAULT ''"),
            ("driver_card_number", "ALTER TABLE drivers ADD COLUMN driver_card_number TEXT DEFAULT ''"),
        ])

        self._ensure_columns("clients", [
            ("client_type", S.ALTER_CLIENTS_ADD_TYPE),
            ("payment_terms_days", S.ALTER_CLIENTS_ADD_PAYMENT_TERMS),
            ("credit_limit_eur", S.ALTER_CLIENTS_ADD_CREDIT_LIMIT),
            ("default_rate_per_km", S.ALTER_CLIENTS_ADD_DEFAULT_RATE),
            ("rating", S.ALTER_CLIENTS_ADD_RATING),
            ("eori_number", "ALTER TABLE clients ADD COLUMN eori_number TEXT DEFAULT ''"),
            ("country", "ALTER TABLE clients ADD COLUMN country TEXT DEFAULT ''"),
            ("consignee_contact_name", "ALTER TABLE clients ADD COLUMN consignee_contact_name TEXT DEFAULT ''"),
            ("consignee_contact_phone", "ALTER TABLE clients ADD COLUMN consignee_contact_phone TEXT DEFAULT ''"),
        ])

        # ── Migration: make document_package.trip_id nullable ────────────
        try:
            cols = [r[1] for r in self.conn.execute(
                "PRAGMA table_info(document_package)"
            ).fetchall()]
            if "trip_id" in cols:
                # Check if trip_id is still NOT NULL
                info = self.conn.execute(
                    "PRAGMA table_info(document_package)"
                ).fetchall()
                for col in info:
                    if col[1] == "trip_id" and col[3] == 1:  # 1 = NOT NULL
                        fk_was_on = self.conn.execute(
                            "PRAGMA foreign_keys"
                        ).fetchone()[0]
                        if fk_was_on:
                            self.conn.execute("PRAGMA foreign_keys=OFF")
                        self.conn.execute("BEGIN IMMEDIATE")
                        self.conn.execute("""
                            CREATE TABLE document_package_new (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                trip_id INTEGER,
                                package_uuid TEXT UNIQUE NOT NULL,
                                status TEXT NOT NULL DEFAULT 'draft',
                                recipient_email TEXT DEFAULT '',
                                subject TEXT DEFAULT '',
                                body TEXT DEFAULT '',
                                email_message_id TEXT DEFAULT '',
                                sent_at TEXT,
                                error_message TEXT DEFAULT '',
                                created_at TEXT NOT NULL,
                                updated_at TEXT NOT NULL
                            )
                        """)
                        self.conn.execute("""
                            INSERT INTO document_package_new
                            SELECT * FROM document_package
                        """)
                        self.conn.execute("DROP TABLE document_package")
                        self.conn.execute(
                            "ALTER TABLE document_package_new "
                            "RENAME TO document_package"
                        )
                        self.conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_package_trip "
                            "ON document_package(trip_id)"
                        )
                        self.conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_package_uuid "
                            "ON document_package(package_uuid)"
                        )
                        self.conn.execute(
                            "CREATE INDEX IF NOT EXISTS idx_package_status "
                            "ON document_package(status)"
                        )
                        self.conn.commit()
                        if fk_was_on:
                            self.conn.execute("PRAGMA foreign_keys=ON")
                        logger.info(
                            "Migrated document_package.trip_id to nullable"
                        )
                        break
        except Exception as e:
            logger.warning(
                "Migration of document_package.trip_id failed: %s", e
            )
            try:
                self.conn.rollback()
            except Exception:
                pass

        # ── Migration: update status triggers to include "processed" ──
        try:
            self.conn.execute(
                "DROP TRIGGER IF EXISTS trg_pipeline_runs_status_check"
            )
            self.conn.execute(
                "DROP TRIGGER IF EXISTS trg_pipeline_runs_status_check_upd"
            )
            self.conn.execute(S.TRIGGER_PIPELINE_RUNS_STATUS_CHECK)
            self.conn.execute(S.TRIGGER_PIPELINE_RUNS_STATUS_UPDATE)
            logger.info("Recreated status triggers with 'processed' value")
        except Exception as e:
            logger.warning("Migration of status triggers failed: %s", e)

        # ── Users: add company_id (multi-tenant migration) ──────────────
        self._ensure_column(
            "users", "company_id",
            "ALTER TABLE users ADD COLUMN company_id "
            "INTEGER REFERENCES companies(id)",
        )
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id)")
        except Exception as e:
            logger.warning("Migration step failed: %s", e)

        try:
            self.conn.commit()
        except Exception as e:
            logger.warning("Migration step failed: %s", e)

    def _migrate_legacy_data(self):
        """One-off data migrations (legacy maintenance table, etc.)."""
        try:
            has_legacy = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance'"
            ).fetchone()
            has_records = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_records'"
            ).fetchone()
            if has_legacy and has_records:
                migrated = self.conn.execute("""
                    INSERT OR IGNORE INTO maintenance_records
                    (truck_id, maintenance_type, date, km, cost, notes, created_at)
                    SELECT truck_id, type, date, km_at_service, cost, description,
                           COALESCE(date, datetime('now'))
                    FROM maintenance
                """).rowcount
                if migrated > 0:
                    self.conn.execute("DROP TABLE maintenance")
                    self.conn.commit()
                    logger.info("Migrated %d legacy maintenance records and dropped old table", migrated)
        except Exception as e:
            logger.warning("Migration step failed: %s", e)
        self._seed_automail_defaults()

    def _seed_automail_defaults(self):
        """Seed default AutoMail templates, schedules, and settings if empty.

        This runs once on first database init to ensure the system is
        immediately usable with sensible defaults mirroring the original
        hardcoded DunnerEngine behavior.
        """
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        try:
            # ── Seed templates if empty ──────────────────────────────────
            count = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM automail_templates"
            ).fetchone()["cnt"]
            if count == 0:
                templates = [
                    (
                        "Default",
                        "Payment Notice: Invoice {invoice_number} / {company_name}",
                        "Dear Accounts Payable Team,\n\n"
                        "This is an automated notification regarding invoice {invoice_number} "
                        "({total_amount} {currency}), due on {due_date}.\n\n"
                        "Please find the relevant documents attached.\n\n"
                        "Thank you for your prompt attention.\n\n"
                        "Best regards,\n{company_name}\n\nGenerated via Operion ERP",
                        "<p>Dear Accounts Payable Team,</p>"
                        "<p>This is an automated notification regarding invoice "
                        "<strong>{invoice_number}</strong> ({total_amount} {currency}), "
                        "due on <strong>{due_date}</strong>.</p>"
                        "<p>Please find the relevant documents attached.</p>"
                        "<p>Thank you for your prompt attention.</p>"
                        "<p>Best regards,<br>{company_name}</p>"
                        "<hr><small>Generated via Operion ERP</small>",
                        1,
                    ),
                    (
                        "Friendly",
                        "Upcoming Payment: Invoice {invoice_number} / {company_name}",
                        "Dear Accounts Payable Team,\n\n"
                        "This is a friendly reminder that invoice {invoice_number} "
                        "({total_amount} {currency}) is due on {due_date}.\n\n"
                        "Please let us know if you require any additional information.\n\n"
                        "Thank you for your continued partnership.\n\n"
                        "Best regards,\n{company_name}",
                        "<p>Dear Accounts Payable Team,</p>"
                        "<p>This is a friendly reminder that invoice "
                        "<strong>{invoice_number}</strong> ({total_amount} {currency}) "
                        "is due on <strong>{due_date}</strong>.</p>"
                        "<p>Please let us know if you require any additional information.</p>"
                        "<p>Thank you for your continued partnership.</p>"
                        "<p>Best regards,<br>{company_name}</p>",
                        0,
                    ),
                    (
                        "Professional",
                        "Invoice {invoice_number} — Payment Reminder / {company_name}",
                        "Dear Accounts Payable Team,\n\n"
                        "This is a professional reminder that invoice {invoice_number} "
                        "({total_amount} {currency}) is scheduled for payment on {due_date}.\n\n"
                        "Kindly ensure the payment is processed by the due date. "
                        "If already executed, please disregard this message.\n\n"
                        "Sincerely,\n{company_name}",
                        "<p>Dear Accounts Payable Team,</p>"
                        "<p>This is a professional reminder that invoice "
                        "<strong>{invoice_number}</strong> ({total_amount} {currency}) "
                        "is scheduled for payment on <strong>{due_date}</strong>.</p>"
                        "<p>Kindly ensure the payment is processed by the due date. "
                        "If already executed, please disregard this message.</p>"
                        "<p>Sincerely,<br>{company_name}</p>",
                        0,
                    ),
                    (
                        "Strict",
                        "URGENT: Invoice {invoice_number} / {company_name}",
                        "Dear Accounts Payable Team,\n\n"
                        "This is an urgent notification regarding invoice {invoice_number} "
                        "({total_amount} {currency}), originally due on {due_date}.\n\n"
                        "We must insist on immediate payment to avoid any disruption of services. "
                        "Please confirm the transfer date at your earliest convenience.\n\n"
                        "Regards,\n{company_name}",
                        "<p>Dear Accounts Payable Team,</p>"
                        "<p>This is an urgent notification regarding invoice "
                        "<strong>{invoice_number}</strong> ({total_amount} {currency}), "
                        "originally due on <strong>{due_date}</strong>.</p>"
                        "<p>We must insist on immediate payment to avoid any disruption "
                        "of services. Please confirm the transfer date at your earliest "
                        "convenience.</p>"
                        "<p>Regards,<br>{company_name}</p>",
                        0,
                    ),
                ]
                self.conn.executemany(
                    "INSERT INTO automail_templates "
                    "(name, subject, body_text, body_html, is_default, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [(t[0], t[1], t[2], t[3], t[4], now, now) for t in templates],
                )
                logger.info("Seeded %d default automail templates", len(templates))
            else:
                logger.debug("automail_templates already populated, skipping seed")

            # ── Seed schedules if empty ─────────────────────────────────
            count = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM automail_schedules"
            ).fetchone()["cnt"]
            if count == 0:
                default_tpl = self.conn.execute(
                    "SELECT id FROM automail_templates WHERE is_default = 1 LIMIT 1"
                ).fetchone()
                tpl_id = default_tpl["id"] if default_tpl else 1
                schedules = [
                    ("Day 27 Reminder",    "days_before_due", 3, tpl_id, 1, 0),
                    ("Due Date Notice",    "on_due_date",     0, tpl_id, 1, 1),
                    ("Day 33 Follow-Up",   "days_after_due",  3, tpl_id, 1, 2),
                ]
                self.conn.executemany(
                    "INSERT INTO automail_schedules "
                    "(name, trigger_type, days_offset, template_id, is_active, sort_order, "
                    " created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [(s[0], s[1], s[2], s[3], s[4], s[5], now, now) for s in schedules],
                )
                logger.info("Seeded %d default automail schedules", len(schedules))
            else:
                logger.debug("automail_schedules already populated, skipping seed")

            # ── Seed settings if empty ───────────────────────────────────
            count = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM automail_settings"
            ).fetchone()["cnt"]
            if count == 0:
                settings = [
                    ("enabled",                   "0"),
                    ("max_reminders_per_invoice",  "5"),
                    ("retry_attempts",             "3"),
                    ("business_hours_start",       "08:00"),
                    ("business_hours_end",         "18:00"),
                    ("skip_weekends",              "1"),
                ]
                self.conn.executemany(
                    "INSERT INTO automail_settings (key, value) VALUES (?, ?)",
                    settings,
                )
                logger.info("Seeded %d default automail settings", len(settings))
            else:
                logger.debug("automail_settings already populated, skipping seed")

            self.conn.commit()
        except Exception as e:
            logger.exception("Failed to seed automail defaults: %s", e)
            try:
                self.conn.execute("ROLLBACK")
            except Exception:
                pass

    # ── SETTINGS (canonical API, not deprecated) ─────────────────────

    def get_settings(self, keys: List[str]) -> Dict[str, str]:
        rows = self.conn.execute(
            f"SELECT key, value FROM settings WHERE key IN ({','.join('?' * len(keys))})",
            keys,
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def save_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        self.conn.commit()

    def get_setting(self, key: str) -> Optional[str]:
        res = self.get_settings([key])
        return res.get(key) if res else None

    # ── DEPRECATED DELEGATION METHODS ─────────────────────────────────
    # These exist only for backward compatibility.
    # New code should use the proper Service / Repository classes.
    # Each method logs a DeprecationWarning on first call.

    _schema_cache: dict = {}

    def _valid_columns(self, table: str) -> set:
        if table not in self._schema_cache:
            rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            DatabaseManager._schema_cache[table] = {r[1] for r in rows}
        return DatabaseManager._schema_cache[table]

    def _validate_column_keys(self, data: dict, table: str) -> None:
        valid = self._valid_columns(table)
        invalid = set(data.keys()) - valid
        if invalid:
            raise ValueError(
                f"Invalid column(s) for {table}: {', '.join(sorted(invalid))}"
            )

    # ── Trip CRUD (deprecated — use TripRepository) ──────────────────

    def _trip_repo(self):
        from repositories.trip_repository import TripRepository
        return TripRepository(self)

    def add_trip(self, data: dict):
        _deprecated("DatabaseManager.add_trip — use TripRepository.create()")
        return self._trip_repo().create(data)

    def update_trip(self, trip_id, data: dict):
        _deprecated("DatabaseManager.update_trip — use TripRepository.update()")
        self._trip_repo().update(trip_id, data)

    def update_status(self, trip_id, status):
        _deprecated("DatabaseManager.update_status — use TripRepository.update()")
        self._trip_repo().update(trip_id, {"status": status})

    def delete_trip(self, trip_id):
        _deprecated("DatabaseManager.delete_trip — use TripRepository.delete()")
        self._trip_repo().delete(trip_id)

    def get_all_trips(self, limit: int = 500):
        _deprecated("DatabaseManager.get_all_trips — use TripRepository.get_all()")
        return self._trip_repo().get_all(limit=limit)

    def get_trip_by_id(self, trip_id):
        _deprecated("DatabaseManager.get_trip_by_id — use TripRepository.get_by_id()")
        return self._trip_repo().get_by_id(trip_id)

    def get_filtered_trips(self, search="", truck="", status="", limit: int = 200):
        _deprecated("DatabaseManager.get_filtered_trips — use TripRepository methods")
        return self._trip_repo().get_filtered(search=search, truck=truck, status=status, limit=limit)

    def get_unique_lists(self):
        _deprecated("DatabaseManager.get_unique_lists — query directly")
        trucks = [r[0] for r in self.conn.execute(
            "SELECT DISTINCT COALESCE(t.plate_number, trips.truck_number) "
            "FROM trips LEFT JOIN trucks t ON trips.truck_id = t.id "
            "WHERE trips.truck_number IS NOT NULL OR trips.truck_id IS NOT NULL"
        ).fetchall()]
        drivers = [r[0] for r in self.conn.execute("SELECT DISTINCT driver_name FROM trips WHERE driver_name IS NOT NULL").fetchall()]
        return trucks, drivers

    # ── Invoice linking (deprecated — use InvoiceRepository) ─────────

    def _invoice_repo(self):
        from repositories.invoice_repository import InvoiceRepository
        return InvoiceRepository(self)

    def create_invoice_record(self, trip_id, inv_number, amount, due_date):
        _deprecated("DatabaseManager.create_invoice_record — use InvoiceRepository.create()")
        from datetime import datetime as dt
        try:
            self.conn.execute("""
                INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, status)
                VALUES (?, ?, ?, ?, ?, 'Unpaid')
            """, (trip_id, inv_number, dt.now().strftime("%Y-%m-%d"), due_date, amount))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    def mark_invoice_as_paid(self, trip_id):
        _deprecated("DatabaseManager.mark_invoice_as_paid — use InvoiceRepository.mark_paid()")
        self.conn.execute("UPDATE invoices SET status = 'Paid' WHERE trip_id = ?", (trip_id,))
        self.conn.commit()

    def _proforma_repo(self):
        from repositories.proforma_repository import ProformaRepository
        return ProformaRepository(self)

    def create_proforma_record(
        self,
        proforma_number: str = "",
        issue_date: str = "",
        valid_until: str = "",
        client_name: str = "",
        client_address: str = "",
        client_vat: str = "",
        client_phone: str = "",
        client_email: str = "",
        description: str = "",
        notes: str = "",
        line_items_json: str = "[]",
        subtotal: float = 0,
        discount_type: str = "",
        discount_value: float = 0,
        discount_amount: float = 0,
        tax_rate: float = 0,
        tax_amount: float = 0,
        grand_total: float = 0,
        currency: str = "EUR",
        mode: str = "client",
        status: str = "Draft",
        logo_path: str = "",
        signature_path: str = "",
        stamp_path: str = "",
        company_color: str = "#6366f1",
    ) -> Optional[int]:
        """Insert a proforma invoice record. Returns the new row id or None on failure."""
        repo = self._proforma_repo()
        import json
        return repo.create(
            proforma_number=proforma_number,
            issue_date=issue_date,
            valid_until=valid_until,
            client_name=client_name,
            client_address=client_address,
            client_vat=client_vat,
            client_phone=client_phone,
            client_email=client_email,
            description=description,
            notes=notes,
            line_items=json.loads(line_items_json) if line_items_json else [],
            subtotal=subtotal,
            discount_type=discount_type,
            discount_value=discount_value,
            discount_amount=discount_amount,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            grand_total=grand_total,
            currency=currency,
            mode=mode,
            status=status,
            logo_path=logo_path,
            signature_path=signature_path,
            stamp_path=stamp_path,
            company_color=company_color,
        )

    def update_proforma(self, proforma_id: int, **kwargs) -> bool:
        """Update proforma invoice fields by id. Returns True on success."""
        repo = self._proforma_repo()
        return repo.update(proforma_id, **kwargs)

    # ── Truck CRUD (deprecated — use FleetRepository) ────────────────

    def _fleet_repo(self):
        from repositories.fleet_repository import FleetRepository
        return FleetRepository(self)

    def get_all_trucks(self, active_only=False):
        _deprecated("DatabaseManager.get_all_trucks — use FleetRepository.get_all()")
        if active_only:
            return self._fleet_repo().get_active_trucks()
        return self._fleet_repo().get_all()

    def get_truck_by_id(self, truck_id):
        _deprecated("DatabaseManager.get_truck_by_id — use FleetRepository.get_by_id()")
        return self._fleet_repo().get_by_id(truck_id)

    def add_truck(self, data: dict):
        _deprecated("DatabaseManager.add_truck — use FleetRepository.create()")
        return self._fleet_repo().create(data)

    def update_truck(self, truck_id, data: dict):
        _deprecated("DatabaseManager.update_truck — use FleetRepository.update()")
        self._fleet_repo().update(truck_id, data)

    def delete_truck(self, truck_id):
        _deprecated("DatabaseManager.delete_truck — use FleetRepository.delete()")
        self._fleet_repo().delete(truck_id)

    # ── Truck routes (deprecated — use TruckRouteAssignmentRepository) ─

    def get_truck_routes(self, truck_id, status=None):
        _deprecated("DatabaseManager.get_truck_routes — use TruckRouteAssignmentRepository")
        from repositories.truck_route_assignment_repository import TruckRouteAssignmentRepository
        repo = TruckRouteAssignmentRepository(self)
        return repo.get_by_truck(truck_id, status=status)

    # ── Expenses CRUD (deprecated — no dedicated repo yet) ────────────

    def ensure_expenses_table(self):
        _deprecated("DatabaseManager.ensure_expenses_table — create table directly")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                truck_id INTEGER,
                date TEXT,
                category TEXT,
                description TEXT,
                amount REAL
            );
        """)
        self.conn.commit()

    def get_expenses(self, truck_id):
        _deprecated("DatabaseManager.get_expenses — query expenses table directly")
        return self.rows_to_dicts(self.conn.execute(
            "SELECT id, date, category, amount, description FROM expenses WHERE truck_id = ? ORDER BY date DESC",
            (truck_id,),
        ).fetchall())

    def add_expense(self, truck_id, date, category, description, amount):
        _deprecated("DatabaseManager.add_expense — insert into expenses table directly")
        cursor = self.conn.execute(
            "INSERT INTO expenses (truck_id, date, category, description, amount) VALUES (?,?,?,?,?)",
            (truck_id, date, category, description, amount),
        )
        self.conn.commit()
        return cursor.lastrowid

