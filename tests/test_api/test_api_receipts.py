"""Tests for the receipts API router (``/api/v1/receipts``)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/receipts"


class TestReceiptsRouter:
    """Receipt generation endpoint."""

    # ── generate ───────────────────────────────────────────────────────────

    @patch("services.invoicing.receipt_generator.ReceiptGenerator")
    def test_generate_receipt_returns_pdf(
        self, mock_gen_cls, client_with_mocks, tmp_path
    ):
        client, mocks = client_with_mocks
        pdf_file = tmp_path / "REC-001.pdf"
        pdf_file.write_text("fake-pdf-content")

        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.generate.return_value = str(pdf_file)

        payload = {"receipt_data": {"client": "Acme Corp", "amount": 1500.00}}
        resp = client.post(f"{BASE}/generate", json=payload)
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers.get("content-type", "")
        # Server-side sequence numbering: when the request supplies no
        # receipt_number, the endpoint injects the assigned sequence number
        # into the payload before rendering the PDF and surfaces it in the
        # response header.
        call_args = mock_gen.generate.call_args
        sent = call_args[0][0]
        assert sent["client"] == "Acme Corp"
        assert sent["amount"] == 1500.00
        assert sent["receipt_number"].startswith("RCT-")
        assert resp.headers.get("X-Receipt-Number") == sent["receipt_number"]

    @patch("services.invoicing.receipt_generator.ReceiptGenerator")
    def test_generate_receipt_empty_data(self, mock_gen_cls, client_with_mocks):
        """Empty dict body → receipt_data falls back to data → generator
        returns a path that is not a real file → 500."""
        client, mocks = client_with_mocks
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.generate.return_value = "/tmp/nonexistent.pdf"

        resp = client.post(f"{BASE}/generate", json={})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Receipt generation failed"

    @patch("services.invoicing.receipt_generator.ReceiptGenerator")
    def test_generate_receipt_generation_failed(
        self, mock_gen_cls, client_with_mocks
    ):
        """Generator returns a path that does not exist → 500."""
        client, mocks = client_with_mocks
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.generate.return_value = "/bad/path.pdf"

        resp = client.post(
            f"{BASE}/generate",
            json={"receipt_data": {"client": "Acme"}},
        )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Receipt generation failed"

    @patch("services.invoicing.receipt_generator.ReceiptGenerator")
    def test_generate_receipt_service_exception(
        self, mock_gen_cls, client_with_mocks
    ):
        """Generator raises an exception → propagates as 500."""
        client, mocks = client_with_mocks
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.generate.side_effect = Exception("generator error")

        resp = client.post(
            f"{BASE}/generate",
            json={"receipt_data": {"client": "Acme"}},
        )
        assert resp.status_code == 500

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.post(f"{BASE}/generate", json={})
        assert resp.status_code == 401
