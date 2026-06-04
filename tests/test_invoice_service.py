"""Unit tests for InvoiceService: generation, recording, email workflow edge cases."""
import os
import unittest
from unittest import mock
from datetime import datetime

from services.invoicing.generator import InvoiceGenerator
from services.invoicing.service import InvoiceService


class TestInvoiceGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = InvoiceGenerator()

    def test_generate_creates_pdf_file(self):
        trip = {
            "id": 1,
            "truck_number": "B-100-TST",
            "driver_name": "John",
            "client_name": "TestClient",
            "distance_km": 500.0,
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
            "total_price_eur": 1000.0,
            "fuel_cost": 100.0,
            "toll_cost": 50.0,
            "salary_cost": 50.0,
            "extra_costs": 0,
            "net_profit": 800.0,
            "currency": "EUR",
        }
        path = self.generator.generate(trip, mode="client")
        self.assertTrue(os.path.exists(path), f"PDF not found at {path}")
        self.assertTrue(path.endswith(".pdf"))

    def test_generate_internal_mode_creates_pdf(self):
        trip = {
            "id": 2,
            "truck_number": "B-200-TST",
            "driver_name": "Alice",
            "client_name": "InternalCorp",
            "distance_km": 300.0,
            "start_date": "2025-02-01",
            "end_date": "2025-02-02",
            "total_price_eur": 600.0,
            "fuel_cost": 80.0,
            "toll_cost": 20.0,
            "salary_cost": 40.0,
            "extra_costs": 0,
            "net_profit": 460.0,
            "currency": "EUR",
        }
        path = self.generator.generate(trip, mode="internal")
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".pdf"))

    def test_generate_with_special_characters_in_name(self):
        trip = {
            "id": 3,
            "truck_number": "B-300-TST",
            "driver_name": "Francois",
            "client_name": "Café GmbH",
            "distance_km": 200.0,
            "start_date": "2025-03-01",
            "end_date": "2025-03-02",
            "total_price_eur": 400.0,
            "fuel_cost": 50.0,
            "toll_cost": 10.0,
            "salary_cost": 30.0,
            "extra_costs": 0,
            "net_profit": 310.0,
            "currency": "EUR",
        }
        path = self.generator.generate(trip, mode="client")
        self.assertTrue(os.path.exists(path))

    def test_generate_with_missing_optional_fields(self):
        trip = {
            "id": 4,
            "truck_number": "",
            "driver_name": "",
            "client_name": "MinimalClient",
            "distance_km": 0.0,
            "start_date": "",
            "end_date": "",
            "total_price_eur": 0.0,
            "fuel_cost": 0.0,
            "toll_cost": 0.0,
            "salary_cost": 0.0,
            "extra_costs": 0,
            "net_profit": 0.0,
            "currency": "EUR",
        }
        path = self.generator.generate(trip, mode="client")
        self.assertTrue(os.path.exists(path))


class TestInvoiceServiceRecord(unittest.TestCase):
    def setUp(self):
        from tests.test_helpers import make_db
        self.db = make_db()
        self.svc = InvoiceService(self.db)

    def test_create_record_persists(self):
        self.svc.create_record(
            trip_id=1,
            inv_number="INV-2025-0001",
            amount=1500.0,
            due_date="2025-02-15",
        )
        row = self.db.conn.execute(
            "SELECT * FROM invoices WHERE invoice_number = ?", ("INV-2025-0001",)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "Unpaid")
        self.assertEqual(row["total_amount"], 1500.0)

    def test_create_record_duplicate_trip_id_is_silent(self):
        self.svc.create_record(1, "INV-A", 100.0, "2025-01-01")
        # Second call with same trip_id should not raise (UNIQUE constraint)
        self.svc.create_record(1, "INV-B", 200.0, "2025-01-02")

    def test_generate_and_record_creates_record(self):
        trip = {"id": 10, "total_price_eur": 900.0}
        self.svc.generate_and_record(trip, mode="client")
        row = self.db.conn.execute(
            "SELECT * FROM invoices WHERE trip_id = 10"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "Unpaid")

    def test_generate_and_record_internal_mode_skips_record(self):
        trip = {"id": 11, "total_price_eur": 900.0}
        self.svc.generate_and_record(trip, mode="internal")
        row = self.db.conn.execute(
            "SELECT * FROM invoices WHERE trip_id = 11"
        ).fetchone()
        self.assertIsNone(row)


class TestInvoiceServiceEmailValidation(unittest.TestCase):
    def setUp(self):
        from tests.test_helpers import make_db
        self.db = make_db()
        self.svc = InvoiceService(self.db)

    def test_send_email_requires_recipient(self):
        with self.assertRaises(ValueError) as ctx:
            self.svc.send_invoice_email(
                trip_id=1,
                recipient="",
                trip_data={"id": 1},
            )
        self.assertIn("Recipient", str(ctx.exception))

    def test_send_email_requires_smtp_config(self):
        with self.assertRaises(ValueError) as ctx:
            self.svc.send_invoice_email(
                trip_id=1,
                recipient="test@example.com",
                smtp_config={},
                trip_data={"id": 1},
            )
        self.assertIn("SMTP", str(ctx.exception))

    def test_send_email_without_smtp_server_raises(self):
        with self.assertRaises(ValueError):
            self.svc.send_invoice_email(
                trip_id=1,
                recipient="test@example.com",
                smtp_config={"smtp_server": "", "smtp_user": "u", "smtp_password": "p"},
                trip_data={"id": 1},
            )

    @mock.patch.object(InvoiceService, "generate_and_record")
    @mock.patch("services.invoicing.service.NotificationCenter")
    @mock.patch("services.invoicing.service.load_company_config")
    @mock.patch("os.path.exists", return_value=True)
    def test_send_email_success_returns_true(
        self, mock_exists, mock_config, mock_nc, mock_generate
    ):
        mock_config.return_value = {"company_name": "TestCo", "email": "co@test.com"}
        mock_center = mock.MagicMock()
        mock_center.send_email.return_value = True
        mock_nc.return_value = mock_center
        mock_generate.return_value = "/fake/path.pdf"

        result = self.svc.send_invoice_email(
            trip_id=1,
            recipient="client@example.com",
            smtp_config={
                "smtp_server": "smtp.test.com",
                "smtp_port": "587",
                "smtp_user": "user",
                "smtp_password": "pass",
            },
            trip_data={"id": 1, "client_name": "ClientCo"},
        )
        self.assertTrue(result)

    @mock.patch.object(InvoiceService, "generate_and_record")
    @mock.patch("services.invoicing.service.NotificationCenter")
    @mock.patch("services.invoicing.service.load_company_config")
    @mock.patch("os.path.exists", return_value=True)
    def test_send_email_failure_returns_false(
        self, mock_exists, mock_config, mock_nc, mock_generate
    ):
        mock_config.return_value = {"company_name": "TestCo", "email": "co@test.com"}
        mock_center = mock.MagicMock()
        mock_center.send_email.return_value = False
        mock_nc.return_value = mock_center
        mock_generate.return_value = "/fake/path.pdf"

        result = self.svc.send_invoice_email(
            trip_id=1,
            recipient="client@example.com",
            smtp_config={
                "smtp_server": "smtp.test.com",
                "smtp_port": "587",
                "smtp_user": "user",
                "smtp_password": "pass",
            },
            trip_data={"id": 1, "client_name": "ClientCo"},
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
