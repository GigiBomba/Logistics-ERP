"""Tests for DatabaseManager schema creation and column migration logic."""
from __future__ import annotations

import os
import tempfile
import unittest

from database.db_manager import DatabaseManager


class TestDatabaseMigrations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

    def tearDown(self):
        try:
            if hasattr(self, 'db') and self.db:
                self.db.close()
        except Exception:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_init_creates_all_tables(self):
        self.db = DatabaseManager(self.db_path)
        tables = self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {r[0] for r in tables}
        for required in ("trips", "trucks", "drivers", "clients",
                         "invoices", "alerts", "settings",
                         "maintenance_records", "route_history_v2",
                         "documents", "document_links"):
            self.assertIn(required, table_names, f"Missing table: {required}")

    def test_init_creates_indexes(self):
        self.db = DatabaseManager(self.db_path)
        indexes = self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        ).fetchall()
        index_names = {r[0] for r in indexes}
        self.assertIn("idx_trips_status", index_names)
        # trucks table has a UNIQUE constraint on plate_number, which
        # creates an auto-index named sqlite_autoindex_trucks_1
        self.assertTrue(
            any("trucks" in idx for idx in index_names),
            f"No index found for trucks table in {index_names}"
        )

    def test_column_migration_adds_missing_column(self):
        self.db = DatabaseManager(self.db_path)
        cols = [r[1] for r in self.db.conn.execute("PRAGMA table_info(trips)").fetchall()]
        self.assertIn("context_json", cols)
        self.assertIn("route_history_v2_id", cols)
        self.assertIn("cmr_number", cols)

    def test_column_migration_is_idempotent(self):
        self.db = DatabaseManager(self.db_path)
        self.db.close()
        self.db = DatabaseManager(self.db_path)
        cols = [r[1] for r in self.db.conn.execute("PRAGMA table_info(trips)").fetchall()]
        self.assertIn("cmr_number", cols)

    def test_legacy_maintenance_migration_skipped_when_no_old_table(self):
        self.db = DatabaseManager(self.db_path)
        self.db._migrate_legacy_data()

    def test_settings_table_created(self):
        self.db = DatabaseManager(self.db_path)
        self.db.save_setting("test_key", "test_value")
        val = self.db.get_setting("test_key")
        self.assertEqual(val, "test_value")

    def test_document_tables_created(self):
        self.db = DatabaseManager(self.db_path)
        tables = {r[0] for r in self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("documents", tables)
        self.assertIn("document_versions", tables)
        self.assertIn("document_templates", tables)

    def test_pipeline_tables_created(self):
        self.db = DatabaseManager(self.db_path)
        tables = {r[0] for r in self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("document_pipeline_runs", tables)
        self.assertIn("document_package", tables)

    def test_cmr_tables_created(self):
        self.db = DatabaseManager(self.db_path)
        tables = {r[0] for r in self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("cmr_counter", tables)
        self.assertIn("successive_carriers", tables)

    def test_second_init_clean_on_existing_db(self):
        self.db = DatabaseManager(self.db_path)
        self.db.close()
        self.db = DatabaseManager(self.db_path)

    def test_truck_column_migration(self):
        self.db = DatabaseManager(self.db_path)
        cols = {r[1] for r in self.db.conn.execute("PRAGMA table_info(trucks)").fetchall()}
        for col in ("trailer_plate", "max_payload_kg", "cmr_insurance_number",
                    "cmr_insurance_expiry", "tachograph_expiry", "tracking_device_id"):
            self.assertIn(col, cols, f"Missing truck column: {col}")

    def test_driver_column_migration(self):
        self.db = DatabaseManager(self.db_path)
        cols = {r[1] for r in self.db.conn.execute("PRAGMA table_info(drivers)").fetchall()}
        for col in ("passport_number", "passport_expiry", "adr_certificate",
                    "adr_certificate_expiry", "driver_card_number"):
            self.assertIn(col, cols, f"Missing driver column: {col}")


if __name__ == "__main__":
    unittest.main()
