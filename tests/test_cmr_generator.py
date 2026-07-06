"""Tests for services.invoicing.cmr_generator."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from services.invoicing.cmr_generator import CMRGenerator


class TestCMRGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = CMRGenerator()
        self.output_dir = os.path.abspath("data/documents/trips/test_cmr")
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def _minimal_trip_data(self):
        return {
            "trip_id": 1,
            "cmr_number": "CMR-001",
            "client_name": "Test Client",
            "client_address": "Str. Test, Nr. 1",
            "origin": "Bucharest",
            "destination": "Constanta",
            "truck_number": "B-123-ABC",
            "distance_km": 200,
        }

    def test_generate_all_copies_returns_dict(self):
        with patch("services.invoicing.cmr_generator.load_company_config") as mock_cfg:
            mock_cfg.return_value = {
                "company_name": "Test Trans SRL",
                "address": "Str. Test, Nr. 10",
                "cui": "RO123456",
                "reg_com": "J12/345/2024",
                "capital": 1000,
                "bank": "BCR",
                "iban": "RO12BCR123456",
                "email": "office@test.ro",
                "phone": "+40123456789",
            }
            result = self.gen.generate_all_copies(
                self._minimal_trip_data(),
                self.output_dir,
                skip_db_update=True,
            )
            self.assertIsInstance(result, dict)
            for key in ("Sender", "Consignee", "Carrier", "Administrative"):
                self.assertIn(key, result)

    def test_generated_pdf_is_valid(self):
        with patch("services.invoicing.cmr_generator.load_company_config") as mock_cfg:
            mock_cfg.return_value = {
                "company_name": "Test Trans SRL",
                "address": "Str. Test, Nr. 10",
                "cui": "RO123456",
                "reg_com": "J12/345/2024",
                "capital": 1000,
                "bank": "BCR",
                "iban": "RO12BCR123456",
                "email": "office@test.ro",
                "phone": "+40123456789",
            }
            copies = self.gen.generate_all_copies(
                self._minimal_trip_data(),
                self.output_dir,
                skip_db_update=True,
            )
            for _, path in copies.items():
                self.assertTrue(os.path.isfile(path), f"PDF not found: {path}")
                self.assertGreater(os.path.getsize(path), 1000, f"PDF too small: {path}")

    def test_output_path_validation(self):
        with self.assertRaises(ValueError):
            unauth_dir = tempfile.mkdtemp()
            try:
                self.gen._build_single_copy(
                    self._minimal_trip_data(),
                    output_dir=unauth_dir,
                    suffix="Sender",
                )
            finally:
                shutil.rmtree(unauth_dir, ignore_errors=True)


class _DbWrapper:
    """Minimal DatabaseManager-like wrapper for a raw sqlite3 connection."""
    def __init__(self, conn):
        self.conn = conn

    def row_to_dict(self, row):
        return dict(row) if row else None

    def rows_to_dicts(self, rows):
        return [dict(r) for r in rows] if rows else []


class TestCMRNumberCounter(unittest.TestCase):
    def setUp(self):
        import sqlite3
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.conn = sqlite3.connect(self._tmp.name)
        self.conn.execute("CREATE TABLE IF NOT EXISTS cmr_counter (id INTEGER PRIMARY KEY, year INTEGER, seq INTEGER)")
        self.conn.execute("INSERT OR IGNORE INTO cmr_counter (id, year, seq) VALUES (1, 2024, 0)")
        self.conn.commit()
        self.db = _DbWrapper(self.conn)

    def tearDown(self):
        self.conn.close()
        os.unlink(self._tmp.name)

    def test_generate_next_cmr_number_returns_string(self):
        gen = CMRGenerator(self.db)
        number, seq = gen._next_cmr_number()
        self.assertIsInstance(number, str)
        self.assertIsInstance(seq, int)
        self.assertGreater(seq, 0)


if __name__ == "__main__":
    unittest.main()
