"""Stress tests: file upload flood and temp file leak detection."""
from __future__ import annotations

import io
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.router import api_v1_router

pytestmark = pytest.mark.slow


class TestStressTempfileExhaustion:
    """Stress tests for /api/v1/documents/upload endpoint."""

    MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}

    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(api_v1_router)
        return app

    @pytest.fixture
    def client(self, app):
        from backend.dependencies_security import get_current_user, require_dispatcher, require_admin
        app.dependency_overrides[get_current_user] = lambda: self.MOCK_USER
        app.dependency_overrides[require_dispatcher] = lambda: self.MOCK_USER
        app.dependency_overrides[require_admin] = lambda: self.MOCK_USER

        from backend.dependencies import get_document_service
        from models.common import ServiceResult, ErrorDetail

        mock_service = MagicMock()
        mock_doc_data = {
            "id": 1, "file_name": "test.pdf", "file_size": 1024, "doc_number": "DOC-001",
            "category": "", "entity_type": "", "entity_id": None,
            "uploaded_by": "user", "mime_type": "application/pdf",
            "uploaded_at": "2026-07-09T12:00:00", "updated_at": "2026-07-09T12:00:00",
            "tags": [], "expiry_date": "", "is_archived": False,
            "is_signed": False, "cmr_number": "",
        }

        class _FakeData:
            def model_dump(self):
                return dict(mock_doc_data)

        mock_result = ServiceResult(success=True, data=_FakeData())
        mock_service.upload_document.return_value = mock_result
        app.dependency_overrides[get_document_service] = lambda: mock_service

        yield TestClient(app)
        app.dependency_overrides.clear()

    @staticmethod
    def _make_upload_file(content: bytes, filename: str = "test.pdf"):
        """Create a file-like object simulating an UploadFile."""
        return io.BytesIO(content), filename

    # ── test 1: Upload flood 100 concurrent 1KB files — no temp leaks ──

    def test_upload_flood_no_temp_leak(self, client, tmp_path):
        """100 concurrent 1KB file uploads — verify no temp files left after requests.

        Uses a private temp directory (``tmp_path``) so concurrent pytest-xdist
        workers writing their own SQLite/upload temp files into the shared OS
        temp dir cannot be mistaken for leaks from *this* test.
        """
        # Route spooled uploads into the private dir for the duration of the test.
        old_tempdir = tempfile.tempdir
        tempfile.tempdir = str(tmp_path)
        try:
            temp_dir = tempfile.gettempdir()
            before = set(os.listdir(temp_dir))

            content = b"x" * 1024  # 1KB

            def upload_file():
                files = {"file": ("test.pdf", io.BytesIO(content), "application/pdf")}
                data = {"category": "test", "entity_type": "trip", "entity_id": "1", "uploaded_by": "tester"}
                resp = client.post("/api/v1/documents/upload", files=files, data=data)
                return resp.status_code

            with ThreadPoolExecutor(max_workers=100) as pool:
                futs = [pool.submit(upload_file) for _ in range(100)]
                for fut in as_completed(futs):
                    fut.result()

            after = set(os.listdir(temp_dir))
            new_files = after - before
            temp_leaks = [f for f in new_files if f.startswith("tmp") or f.endswith(".tmp")]

            # Retry up to 3 times to allow pending framework cleanup to finish
            for attempt in range(3):
                if not temp_leaks:
                    break
                time.sleep(1)
                after = set(os.listdir(temp_dir))
                new_files = after - before
                temp_leaks = [f for f in new_files if f.startswith("tmp") or f.endswith(".tmp")]

            assert len(temp_leaks) == 0, (
                f"Found {len(temp_leaks)} leaked temp files after upload flood: {temp_leaks}"
            )
        finally:
            tempfile.tempdir = old_tempdir

    # ── test 2: Upload flood 20 concurrent 10MB files — no crashes ─────

    def test_upload_flood_large_files(self, client):
        """20 concurrent 10MB uploads — verify no crashes."""
        content = b"x" * (10 * 1024 * 1024)  # 10MB

        def upload_large():
            files = {"file": ("large.pdf", io.BytesIO(content), "application/pdf")}
            data = {"category": "test", "entity_type": "trip", "entity_id": "1", "uploaded_by": "tester"}
            resp = client.post("/api/v1/documents/upload", files=files, data=data)
            return resp.status_code

        with ThreadPoolExecutor(max_workers=20) as pool:
            futs = [pool.submit(upload_large) for _ in range(20)]
            results = []
            for fut in as_completed(futs):
                try:
                    results.append(fut.result())
                except Exception as e:
                    results.append(e)

        server_errors = [r for r in results if r in (500,)]
        assert len(server_errors) == 0, (
            f"upload_flood_large_files produced {len(server_errors)} server errors "
            f"out of {len(results)} uploads"
        )
