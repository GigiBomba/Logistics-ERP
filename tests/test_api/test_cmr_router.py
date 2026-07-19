"""Tests for the CMR API router (``/api/v1/cmr``)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/cmr"


class TestCmrRouter:
    """CMR document generation endpoint."""

    # ── generate ───────────────────────────────────────────────────────────

    @patch("services.invoicing.cmr_generator.CMRGenerator")
    def test_generate_cmr_returns_pdf(
        self, mock_gen_cls, client_with_mocks, tmp_path
    ):
        client, mocks = client_with_mocks
        pdf_file = tmp_path / "cmr_001.pdf"
        pdf_file.write_text("fake-pdf-content")
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.generate_all_copies.return_value = str(pdf_file)

        payload = {"trip_data": {"id": 1, "client_name": "Acme Corp"}}
        resp = client.post(f"{BASE}/generate", json=payload)
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers.get("content-type", "")

    # ── validation: missing trip_data ──────────────────────────────────────

    def test_generate_cmr_returns_400_without_trip_data(self, client_with_mocks):
        client, mocks = client_with_mocks

        # Send empty trip_data so Pydantic validates but the endpoint returns 400
        resp = client.post(f"{BASE}/generate", json={"trip_data": {}})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "trip_data is required"

    # ── edge: dict result with no valid file ───────────────────────────────

    @patch("os.path.isfile", return_value=False)
    @patch("services.invoicing.cmr_generator.CMRGenerator")
    def test_generate_cmr_returns_500_when_no_valid_file(
        self, mock_gen_cls, mock_isfile, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        # Returns a dict with only None/empty values
        mock_gen.generate_all_copies.return_value = {"copy1": None, "copy2": ""}

        resp = client.post(f"{BASE}/generate", json={"trip_data": {"id": 1}})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "CMR generation produced no files"

    # ── edge: string result with missing file ──────────────────────────────

    @patch("os.path.isfile", return_value=False)
    @patch("services.invoicing.cmr_generator.CMRGenerator")
    def test_generate_cmr_returns_500_when_string_path_missing(
        self, mock_gen_cls, mock_isfile, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.generate_all_copies.return_value = "/tmp/cmr/missing.pdf"

        resp = client.post(f"{BASE}/generate", json={"trip_data": {"id": 1}})
        assert resp.status_code == 500
        assert "CMR generation failed" in resp.json()["detail"]

    # ── error handling ────────────────────────────────────────────────────

    @patch("services.invoicing.cmr_generator.CMRGenerator")
    def test_service_exception_propagates(
        self, mock_gen_cls, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen
        mock_gen.generate_all_copies.side_effect = RuntimeError("Generator broke")

        resp = client.post(f"{BASE}/generate", json={"trip_data": {"id": 1}})
        assert resp.status_code == 500

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.post(f"{BASE}/generate", json={"trip_data": {}})
        assert resp.status_code == 401
