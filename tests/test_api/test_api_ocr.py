"""Tests for the OCR API router (``/api/v1/ocr``)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/ocr"


class TestOcrRouter:
    """OCR run, status, and batch endpoints."""

    # ── run ────────────────────────────────────────────────────────────────

    def test_run_ocr_returns_result(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = {
            "ocr_text": "extracted invoice text",
            "ocr_engine": "tesseract",
            "extracted_data_json": {"total": "1500.00"},
            "ocr_run_at": "2026-07-02T10:00:00Z",
        }

        resp = client.post(f"{BASE}/run", json={"document_id": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == 1
        assert data["ocr_text"] == "extracted invoice text"
        assert data["engine_used"] == "tesseract"
        assert data["extracted_fields"] == {"total": "1500.00"}
        assert data["status"] == "done"
        assert "error" in data and data["error"] is None

    def test_run_ocr_document_not_found(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = None

        resp = client.post(f"{BASE}/run", json={"document_id": 999})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Document not found"

    # ── status ─────────────────────────────────────────────────────────────

    def test_get_ocr_status_returns_result(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = {
            "ocr_text": "status text",
            "ocr_engine": "tesseract",
            "extracted_data_json": {"field": "value"},
            "ocr_run_at": "2026-07-02T10:00:00Z",
        }

        resp = client.get(f"{BASE}/status/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == 1
        assert data["ocr_text"] == "status text"
        assert data["status"] == "done"

    def test_get_ocr_status_pending_when_not_started(self, client_with_mocks):
        """No ocr_run_at → derived status 'pending' (not started / queued)."""
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = {
            "ocr_text": "",
            "ocr_engine": "none",
            "extracted_data_json": {},
        }

        resp = client.get(f"{BASE}/status/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["error"] is None

    def test_get_ocr_status_empty_when_ran_but_no_text(self, client_with_mocks):
        """ocr_run_at set but no text → derived status 'empty' (ran but empty)."""
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = {
            "ocr_text": "",
            "ocr_engine": "tesseract",
            "extracted_data_json": {},
            "ocr_run_at": "2026-07-02T10:00:00Z",
        }

        resp = client.get(f"{BASE}/status/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "empty"

    def test_get_ocr_status_not_found(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = None

        resp = client.get(f"{BASE}/status/999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Document not found"

    # ── batch ──────────────────────────────────────────────────────────────

    def test_run_ocr_batch_returns_list(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.side_effect = [
            {"ocr_text": "doc1", "ocr_engine": "tesseract", "extracted_data_json": {}},
            {"ocr_text": "doc2", "ocr_engine": "tesseract", "extracted_data_json": {}},
        ]

        resp = client.post(f"{BASE}/batch", json=[1, 2])
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["ocr_text"] == "doc1"
        assert data[1]["ocr_text"] == "doc2"
        assert data[0]["status"] == "pending"

    def test_run_ocr_batch_empty_list(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.post(f"{BASE}/batch", json=[])
        assert resp.status_code == 200
        assert resp.json() == []

    def test_run_ocr_batch_partial_matches(self, client_with_mocks):
        """No documents match the given IDs → empty list returned."""
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.return_value = None

        resp = client.post(f"{BASE}/batch", json=[999, 998])
        assert resp.status_code == 200
        assert resp.json() == []

    # ── exceptions ─────────────────────────────────────────────────────────

    def test_service_exception_propagates(self, client_with_mocks):
        """Service.get_by_id raises → propagates as 500."""
        client, mocks = client_with_mocks
        mocks["document_service"].get_by_id.side_effect = Exception("DB error")

        resp = client.post(f"{BASE}/run", json={"document_id": 1})
        assert resp.status_code == 500

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.post(f"{BASE}/run", json={"document_id": 1})
        assert resp.status_code == 401
