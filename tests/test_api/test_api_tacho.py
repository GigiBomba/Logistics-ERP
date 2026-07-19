"""Tests for the tacho API router (``/api/v1/tacho``)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.test_api.conftest import StrippedMock

BASE = "/api/v1/tacho"


class TestTachoRouter:
    """Tacho file import, import-history, and status endpoints."""

    # ── import ─────────────────────────────────────────────────────────────

    @patch("backend.services.tacho_service.TachoService")
    def test_import_tacho_file_success(self, mock_svc_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_svc = StrippedMock()
        mock_svc_cls.return_value = mock_svc
        mock_svc.import_ddd_file.return_value = {"imported": 5}

        resp = client.post(
            f"{BASE}/import",
            files={"file": ("test.ddd", b"valid tacho data", "application/x-ddd")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "imported"

    @patch("backend.services.tacho_service.TachoService")
    def test_import_tacho_file_too_large(self, mock_svc_cls, client_with_mocks):
        """11 MB file exceeds the 10 MB limit → 400."""
        client, mocks = client_with_mocks
        large_content = b"x" * (11 * 1024 * 1024)

        resp = client.post(
            f"{BASE}/import",
            files={"file": ("large.ddd", large_content, "application/x-ddd")},
        )
        assert resp.status_code == 400
        assert "too large" in resp.json()["detail"].lower()

    @patch("backend.services.tacho_service.TachoService")
    def test_import_tacho_file_service_error(self, mock_svc_cls, client_with_mocks):
        """Service raises an exception → 500."""
        client, mocks = client_with_mocks
        mock_svc = StrippedMock()
        mock_svc_cls.return_value = mock_svc
        mock_svc.import_ddd_file.side_effect = Exception("import error")

        resp = client.post(
            f"{BASE}/import",
            files={"file": ("test.ddd", b"data", "application/x-ddd")},
        )
        assert resp.status_code == 500

    def test_import_tacho_file_no_file(self, client_with_mocks):
        """Missing required file field → 422."""
        client, mocks = client_with_mocks

        resp = client.post(f"{BASE}/import")
        assert resp.status_code == 422

    # ── import-history ─────────────────────────────────────────────────────

    @patch("backend.repositories.tacho_import_repository.TachoImportRepository")
    def test_get_import_history_returns_items(
        self, mock_repo_cls, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_repo = StrippedMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_recent.return_value = [
            {"id": 1, "filename": "tacho1.ddd", "imported_at": "2024-01-01"},
            {"id": 2, "filename": "tacho2.ddd", "imported_at": "2024-01-02"},
        ]

        resp = client.get(f"{BASE}/import-history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @patch("backend.repositories.tacho_import_repository.TachoImportRepository")
    def test_get_import_history_default_limit(
        self, mock_repo_cls, client_with_mocks
    ):
        """No limit query parameter → defaults to 50."""
        client, mocks = client_with_mocks
        mock_repo = StrippedMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_recent.return_value = []

        resp = client.get(f"{BASE}/import-history")
        assert resp.status_code == 200
        mock_repo.get_recent.assert_called_once_with(limit=50)

    # ── status ─────────────────────────────────────────────────────────────

    @patch("services.tacho_service.TachoService")
    def test_get_tacho_status_returns_ok(self, mock_svc_cls, client_with_mocks):
        client, mocks = client_with_mocks
        mock_svc = StrippedMock()
        mock_svc_cls.return_value = mock_svc

        resp = client.get(f"{BASE}/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    @patch("services.tacho_service.TachoService")
    def test_get_tacho_status_error(self, mock_svc_cls, client_with_mocks):
        """TachoService constructor raises → propagates."""
        client, mocks = client_with_mocks
        mock_svc_cls.side_effect = Exception("service init error")

        resp = client.get(f"{BASE}/status")
        assert resp.status_code == 500

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.post(
            f"{BASE}/import",
            files={"file": ("test.ddd", b"data", "application/octet-stream")},
        )
        assert resp.status_code == 401
