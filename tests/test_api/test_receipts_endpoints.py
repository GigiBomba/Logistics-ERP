"""Integration tests for the receipts API endpoints (/api/v1/receipts)."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/receipts"

class TestReceiptsGenerate:
    """POST /api/v1/receipts/generate"""

    @patch("services.invoicing.receipt_generator.ReceiptGenerator")
    def test_generate_receipt_returns_pdf(self, mock_gen_cls, client_with_mocks, tmp_path):
        client, mocks = client_with_mocks
        pdf_file = tmp_path / "receipt_001.pdf"
        pdf_file.write_text("fake-pdf-content")
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.generate.return_value = str(pdf_file)
        payload = {"receipt_data": {"id": 1, "amount": 500.0}}
        resp = client.post(f"{BASE}/generate", json=payload)
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers.get("content-type", "")

    def test_generate_receipt_uses_data_directly(self, client_with_mocks, tmp_path):
        """When receipt_data is missing, the full payload is used."""
        client, mocks = client_with_mocks
        with patch("services.invoicing.receipt_generator.ReceiptGenerator") as mock_gen_cls:
            pdf_file = tmp_path / "receipt_002.pdf"
            pdf_file.write_text("fake-pdf-content")
            mock_gen = MagicMock()
            mock_gen_cls.return_value = mock_gen
            mock_gen.generate.return_value = str(pdf_file)
            resp = client.post(f"{BASE}/generate", json={"amount": 500.0, "receipt_type": "payment"})
            assert resp.status_code == 200

    @patch("os.path.isfile", return_value=False)
    @patch("services.invoicing.receipt_generator.ReceiptGenerator")
    def test_generate_receipt_returns_500_when_file_missing(self, mock_gen_cls, mock_isfile, client_with_mocks):
        client, mocks = client_with_mocks
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.generate.return_value = "/tmp/missing.pdf"
        resp = client.post(f"{BASE}/generate", json={"receipt_data": {"id": 1}})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Receipt generation failed"

    @patch("services.invoicing.receipt_generator.ReceiptGenerator")
    def test_generate_receipt_returns_500_on_exception(self, mock_gen_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.generate.side_effect = RuntimeError("Generation failed")
        resp = client.post(f"{BASE}/generate", json={"receipt_data": {"id": 1}})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Receipt generation failed"

class TestReceiptsAuth:
    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.post(f"{BASE}/generate", json={"receipt_data": {}})
        assert resp.status_code == 401