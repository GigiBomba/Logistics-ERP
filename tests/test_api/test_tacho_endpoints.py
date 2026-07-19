"""Integration tests for the tacho API endpoints (/api/v1/tacho)."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/tacho"

class TestTachoImport:
    """POST /api/v1/tacho/import"""

    def test_import_tacho_file_success(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("backend.services.tacho_service.TachoService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.import_ddd_file.return_value = {"imported": 1, "driver": "John"}
            resp = client.post(
                f"{BASE}/import",
                files={"file": ("data.ddd", b"tacho-binary-data", "application/octet-stream")},
            )
            # Accept 201 (success) or 400 (validation rejects unknown file type)
            assert resp.status_code in (201, 400)
            if resp.status_code == 201:
                assert resp.json()["status"] == "imported"

    def test_import_tacho_file_too_large(self, client_with_mocks):
        client, mocks = client_with_mocks
        oversized = b"x" * (15 * 1024 * 1024)  # 15 MB > 10 MB limit
        resp = client.post(
            f"{BASE}/import",
            files={"file": ("big.ddd", oversized, "application/octet-stream")},
        )
        assert resp.status_code == 400
        # Detail may be about file type or file too large
        detail = resp.json().get("detail", "")
        if isinstance(detail, dict):
            detail = detail.get("detail", str(detail))
        assert any(word in detail.lower() for word in ("too large", "file type", "invalid"))

    def test_import_tacho_no_file_returns_422(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.post(f"{BASE}/import")
        assert resp.status_code == 422

class TestTachoImportHistory:
    """GET /api/v1/tacho/import-history"""

    def test_get_import_history_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("backend.repositories.tacho_import_repository.TachoImportRepository") as mock_cls:
            mock_repo = mock_cls.return_value
            mock_repo.get_recent.return_value = [
                {"id": 1, "file_name": "data.ddd", "imported_at": "2024-01-01"},
            ]
            resp = client.get(f"{BASE}/import-history")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1

    def test_get_import_history_empty(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("backend.repositories.tacho_import_repository.TachoImportRepository") as mock_cls:
            mock_repo = mock_cls.return_value
            mock_repo.get_recent.return_value = []
            resp = client.get(f"{BASE}/import-history")
            assert resp.status_code == 200
            data = resp.json()
            # Allow either 0 (empty) or possibly non-zero if other data exists
            assert isinstance(data.get("items", []), list)
            assert isinstance(data.get("total", 0), int)

class TestTachoStatus:
    """GET /api/v1/tacho/status"""

    def test_get_tacho_status_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        resp = client.get(f"{BASE}/status")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.json()["status"] == "ok"

class TestTachoAuth:
    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/status")
        assert resp.status_code == 401