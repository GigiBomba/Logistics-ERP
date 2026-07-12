"""Integration tests for the invoices API endpoints (``/api/v1/invoices``)."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/invoices"

class TestInvoicesGenerate:
    """POST /api/v1/invoices/generate"""

    @patch("services.invoicing.service.InvoiceService")
    def test_generate_invoice_returns_pdf(self, mock_svc_cls, client_with_mocks, tmp_path):
        client, mocks = client_with_mocks
        pdf_file = tmp_path / "INV-2024-0001.pdf"
        pdf_file.write_text("fake-pdf-content")
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        mock_svc.generate_and_record.return_value = str(pdf_file)
        payload = {"id": 1, "client_name": "Acme Corp", "total_price_eur": 1500.00, "mode": "client"}
        resp = client.post(f"{BASE}/generate", json=payload)
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers.get("content-type", "")
        mock_svc.generate_and_record.assert_called_once_with(payload, mode="client")

    @patch("os.path.isfile", return_value=False)
    @patch("services.invoicing.service.InvoiceService")
    def test_generate_invoice_returns_500_when_file_missing(self, mock_svc_cls, mock_isfile, client_with_mocks):
        client, mocks = client_with_mocks
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        mock_svc.generate_and_record.return_value = "/tmp/missing.pdf"
        resp = client.post(f"{BASE}/generate", json={"id": 1})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Invoice generation failed"

class TestInvoicesSend:
    """POST /api/v1/invoices/{invoice_id}/send"""

    @patch("services.invoicing.service.InvoiceService")
    def test_send_invoice_email_returns_sent(self, mock_svc_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        mock_svc.send_invoice_email.return_value = True
        payload = {"recipient": "client@example.com", "trip_id": 1, "trip_data": {"client_name": "Acme"}, "mode": "client"}
        resp = client.post(f"{BASE}/1/send", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "sent", "recipient": "client@example.com"}

    @patch("services.invoicing.service.InvoiceService")
    def test_send_invoice_email_returns_400_without_recipient(self, mock_svc_cls, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/1/send", json={})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Recipient email is required"

    @patch("services.invoicing.service.InvoiceService")
    def test_send_invoice_email_returns_400_on_value_error(self, mock_svc_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        mock_svc.send_invoice_email.side_effect = ValueError("SMTP not configured")
        payload = {"recipient": "client@example.com", "trip_data": {}}
        resp = client.post(f"{BASE}/1/send", json=payload)
        assert resp.status_code == 400
        assert "SMTP" in resp.json()["detail"]

    @patch("services.invoicing.service.InvoiceService")
    def test_send_invoice_email_returns_failed_when_not_ok(self, mock_svc_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        mock_svc.send_invoice_email.return_value = False
        payload = {"recipient": "client@example.com", "trip_data": {}}
        resp = client.post(f"{BASE}/1/send", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "failed", "detail": "Email sending failed"}

class TestInvoicesAuth:
    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.post(f"{BASE}/generate", json={})
        assert resp.status_code == 401