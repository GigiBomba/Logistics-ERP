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
        """Now emits a warning instead of raising ValueError for non-standard paths."""
        import logging
        unauth_dir = tempfile.mkdtemp()
        try:
            with self.assertLogs("services.invoicing.cmr_generator", level="WARNING") as log_cm:
                self.gen._build_single_copy(
                    self._minimal_trip_data(),
                    output_dir=unauth_dir,
                    suffix="Sender",
                )
            self.assertTrue(
                any("outside standard paths" in msg for msg in log_cm.output),
                "Expected warning about non-standard output path",
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


class TestCMRGeneratorExtended(unittest.TestCase):
    """Extended tests for CMRGenerator — helpers, grid, layout components."""

    def setUp(self):
        self.gen = CMRGenerator()
        self.output_dir = os.path.abspath("data/documents/trips/test_cmr_ext")
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

    # ── _parse_adr ─────────────────────────────────────────────────

    def test_parse_adr_valid_json_returns_list(self):
        data = {'adr_info_json': '[{"un_no": "UN1203", "adr_class": "3"}]'}
        result = self.gen._parse_adr(data)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['un_no'] == 'UN1203'

    def test_parse_adr_empty_returns_empty_list(self):
        assert self.gen._parse_adr({}) == []

    def test_parse_adr_invalid_json_returns_empty_list(self):
        assert self.gen._parse_adr({'adr_info_json': '{broken'}) == []

    def test_parse_adr_non_list_returns_empty_list(self):
        assert self.gen._parse_adr({'adr_info_json': '{"key": "val"}'}) == []

    # ── _gather_context ────────────────────────────────────────────

    def test_gather_context_basic(self):
        data = {
            'trip_id': 99, 'cmr_number': 'CMR-2026-000042',
            'company_name': 'Acme', 'company_address': 'Str. X',
            'client_name': 'Client Z', 'origin': 'Paris', 'destination': 'Lyon',
            'truck_number': 'AB-123-CD', 'start_date': '2026-07-09',
        }
        with patch("services.invoicing.cmr_generator.load_company_config")\
                as mock_cfg:
            mock_cfg.return_value = {'company_name': 'Default'}
            ctx = self.gen._gather_context(data)
        assert ctx['trip_id'] == 99
        assert ctx['cmr_number'] == 'CMR-2026-000042'
        assert ctx['consignor_name'] == 'Acme'
        assert ctx['client_name'] == 'Client Z'

    def test_gather_context_auto_cmr_number(self):
        data = {'trip_id': 1}
        with patch("services.invoicing.cmr_generator.load_company_config")\
                as mock_cfg:
            mock_cfg.return_value = {'company_name': 'C'}
            ctx = self.gen._gather_context(data)
        assert ctx['cmr_number'].startswith('CMR-')

    def test_gather_context_signature_sentinel(self):
        data = {'signature_path': '__NONE__', 'stamp_path': '__NONE__'}
        with patch("services.invoicing.cmr_generator.load_company_config")\
                as mock_cfg:
            mock_cfg.return_value = {'signature_path': '/tmp/sig.png',
                                      'stamp_path': '/tmp/stamp.png'}
            ctx = self.gen._gather_context(data)
        assert ctx['signature_path'] == ''
        assert ctx['stamp_path'] == ''

    def test_gather_context_adr_parsed(self):
        data = {
            'adr_info_json': '[{"un_no":"UN1203"}]',
            'company_name': 'C', 'consignor_name': 'Sender',
            'consignee_name': 'Receiver',
        }
        with patch("services.invoicing.cmr_generator.load_company_config")\
                as mock_cfg:
            mock_cfg.return_value = {'company_name': 'C'}
            ctx = self.gen._gather_context(data)
        assert ctx['has_adr'] is True
        assert len(ctx['adr_items']) == 1

    def test_gather_context_successive_carriers(self):
        data = {
            'successive_carriers': [
                {'carrier_name': 'SubCarrier1', 'carrier_address': 'Addr1'},
            ],
            'company_name': 'C',
        }
        with patch("services.invoicing.cmr_generator.load_company_config")\
                as mock_cfg:
            mock_cfg.return_value = {'company_name': 'C'}
            ctx = self.gen._gather_context(data)
        assert len(ctx['successive_carriers']) == 1

    # ── _party_text ────────────────────────────────────────────────

    def test_party_text_consignor_all_fields(self):
        ctx = {
            'consignor_name': 'Sender Inc',
            'consignor_address': '123 Main St',
            'consignor_vat': 'RO123',
            'consignor_eori': 'EORI456',
            'consignor_phone': '+401234567',
        }
        text = self.gen._party_text(ctx, 'consignor')
        assert 'Sender Inc' in text
        assert 'RO123' in text
        assert 'EORI456' in text
        assert '+401234567' in text

    def test_party_text_consignee_all_fields(self):
        ctx = {
            'client_name': 'Buyer GmbH',
            'client_address': 'Berliner Str 1',
            'consignee_vat': 'DE789',
            'consignee_eori': 'EORI000',
            'consignee_contact': 'Hans Meier',
        }
        text = self.gen._party_text(ctx, 'consignee')
        assert 'Buyer GmbH' in text
        assert 'DE789' in text
        assert 'EORI000' in text
        assert 'Hans Meier' in text

    def test_party_text_consignor_minimal(self):
        ctx = {'consignor_name': 'Solo', 'consignor_address': ''}
        text = self.gen._party_text(ctx, 'consignor')
        assert 'Solo' in text

    # ── _location_text ─────────────────────────────────────────────

    def test_location_text_loading_with_date(self):
        ctx = {
            'place_of_loading': 'Port of Rotterdam',
            'loading_country': 'NL',
            'place_of_loading_date': '2026-07-10',
        }
        text = self.gen._location_text(ctx, 'loading')
        assert 'Rotterdam' in text
        assert 'NL' in text
        assert '2026-07-10' in text

    def test_location_text_delivery(self):
        ctx = {
            'place_of_delivery': 'Milan',
            'delivery_country': 'IT',
        }
        text = self.gen._location_text(ctx, 'delivery')
        assert 'Milan' in text
        assert 'IT' in text

    def test_location_text_empty(self):
        text = self.gen._location_text({}, 'loading')
        # Without place_of_loading, the address is '' (falsy) but parts = ['']
        # which is truthy, so join returns ''. That's acceptable.
        assert text == '' or '—' in text

    # ── _carrier_text ──────────────────────────────────────────────

    def test_carrier_text_all_fields(self):
        ctx = {
            'carrier_name': 'Carrier Ltd',
            'carrier_address': 'Route 66',
            'carrier_phone': '+440000',
            'carrier_email': 'ops@carrier.com',
            'carrier_reg': 'REG001',
            'carrier_insurance': 'INS-987',
        }
        text = self.gen._carrier_text(ctx)
        assert 'Carrier Ltd' in text
        assert '+440000' in text
        assert 'ops@carrier.com' in text
        assert 'REG001' in text
        assert 'INS-987' in text

    def test_carrier_text_minimal(self):
        ctx = {'carrier_name': 'Minimal', 'carrier_address': ''}
        text = self.gen._carrier_text(ctx)
        assert 'Minimal' in text

    # ── _successive_text ───────────────────────────────────────────

    def test_successive_text_empty(self):
        assert self.gen._successive_text({}) == '—'

    def test_successive_text_multiple(self):
        ctx = {
            'successive_carriers': [
                {'carrier_name': 'Sub1', 'carrier_address': 'Addr1',
                 'vehicle_plate': 'B-111', 'from_location': 'Berlin',
                 'to_location': 'Hamburg'},
                {'carrier_name': 'Sub2', 'carrier_country': 'FR',
                 'driver_name': 'Pierre'},
            ],
        }
        text = self.gen._successive_text(ctx)
        assert 'Sub1' in text
        assert 'Sub2' in text
        assert 'Berlin' in text
        assert 'Hamburg' in text
        assert 'Pierre' in text

    # ── _next_cmr_number ───────────────────────────────────────────

    def test_next_cmr_number_with_repo(self):
        import sqlite3, tempfile
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        try:
            conn = sqlite3.connect(tmp.name)
            conn.execute("CREATE TABLE IF NOT EXISTS cmr_counter "
                         "(id INTEGER PRIMARY KEY, year INTEGER, seq INTEGER)")
            conn.execute("INSERT OR IGNORE INTO cmr_counter "
                          "(id, year, seq) VALUES (1, 2025, 42)")
            conn.commit()
            db_wrap = _DbWrapper(conn)
            from repositories.trip_repository import TripRepository
            repo = TripRepository(db_wrap)
            gen = CMRGenerator(db=db_wrap, trip_repo=repo)
            number, seq = gen._next_cmr_number()
            assert isinstance(number, str)
            assert number.startswith('CMR-')
            assert isinstance(seq, int)
            assert seq > 0
        finally:
            conn.close()
            os.unlink(tmp.name)

    # ── generate (single copy) ─────────────────────────────────────

    def test_generate_single_returns_path(self):
        with patch("services.invoicing.cmr_generator.load_company_config")\
                as mock_cfg:
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
            path = self.gen.generate(self._minimal_trip_data(), self.output_dir)
            self.assertIsInstance(path, str)
            self.assertTrue(os.path.isfile(path))
            self.assertIn('CMR', os.path.basename(path))

    # ── _cargo_grid ────────────────────────────────────────────────

    def test_cargo_grid_with_adr(self):
        ctx = {
            'cargo_marks': 'Mark1', 'package_count': 5,
            'package_type': 'Boxes', 'cargo_description': 'Goods',
            'hs_code': '8471', 'gross_weight_kg': 2000, 'volume_m3': 10,
            'has_adr': True,
            'adr_items': [
                {'un_no': 'UN1203', 'adr_class': '3', 'packing_group': 'II',
                 'tunnel_code': 'E', 'quantity': '100L', 'net_weight': '80'},
            ],
            'cmr_number': 'CMR-ADR',
        }
        from reportlab.lib import colors as rl_colors
        from reportlab.lib.units import mm
        tbl = self.gen._cargo_grid(ctx, 112 * mm,
                                    rl_colors.HexColor('#D32F2F'))
        assert tbl is not None

    def test_cargo_grid_no_adr(self):
        ctx = {
            'cargo_marks': '', 'package_count': '',
            'package_type': '', 'cargo_description': 'Widgets',
            'hs_code': '', 'gross_weight_kg': None, 'volume_m3': None,
            'has_adr': False,
            'cmr_number': 'CMR-NOADR',
        }
        from reportlab.lib import colors as rl_colors
        from reportlab.lib.units import mm
        tbl = self.gen._cargo_grid(ctx, 112 * mm,
                                    rl_colors.HexColor('#D32F2F'))
        assert tbl is not None

    # ── _financial_grid ────────────────────────────────────────────

    def test_financial_grid_with_data(self):
        ctx = {
            'financial_grid': {
                'carriage_sender': '500',
                'carriage_consignee': '300',
                'supplementary_sender': '50',
                'supplementary_consignee': '25',
                'customs_sender': '100',
                'customs_consignee': '0',
                'other_sender': '',
                'other_consignee': '',
            },
            'cmr_number': 'CMR-FIN',
        }
        from reportlab.lib import colors as rl_colors
        from reportlab.lib.units import mm
        tbl = self.gen._financial_grid(ctx, 190 * mm,
                                        rl_colors.HexColor('#D32F2F'))
        assert tbl is not None

    def test_financial_grid_empty(self):
        ctx = {'financial_grid': {}, 'cmr_number': 'CMR-FIN2'}
        from reportlab.lib import colors as rl_colors
        from reportlab.lib.units import mm
        tbl = self.gen._financial_grid(ctx, 190 * mm,
                                        rl_colors.HexColor('#D32F2F'))
        assert tbl is not None

    # ── _sig_pad_enhanced ──────────────────────────────────────────

    def test_sig_pad_with_missing_image(self):
        """Signature pad should not raise when image path missing."""
        ctx = {'sig_sender_path': '/nonexistent/sig.png',
               'signature_path': '',
               'cmr_number': 'CMR-SIG'}
        pad = self.gen._sig_pad_enhanced(22, "Sender", "sender", ctx, 60)
        assert len(pad) >= 1  # at least the Paragraph

    # ── _copy_badge ────────────────────────────────────────────────

    def test_copy_badge_creates_table(self):
        badge = self.gen._copy_badge('#D32F2F', 'COPY FOR TEST')
        assert badge is not None

    # ── _header_block ──────────────────────────────────────────────

    def test_header_block(self):
        from reportlab.lib.units import mm
        ctx = {'cmr_number': 'CMR-HDR', 'trip_id': 42,
               'consignor_name': 'Test'}
        block = self.gen._header_block(ctx, '#D32F2F', 190 * mm)
        assert block is not None


if __name__ == "__main__":
    unittest.main()
