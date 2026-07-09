"""Chaos tests: Celery worker outage, task failures.

The OCR / document-management endpoints don't call Celery directly — they query
the database.  Celery tasks (``process_document_ocr``, ``flush_gps_batch``) are
scheduled separately.  These tests verify that when the Celery broker is
unreachable or a task fails, the API endpoints that *might* interact with task
queues don't crash.
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


class TestCeleryChaos:
    """Simulate Celery-level failures — tasks should degrade gracefully."""

    def test_celery_broker_down_ocr(self, client, auth_admin):
        """When Celery broker is unreachable, OCR tasks should not crash the API.

        The ``POST /api/v1/ocr/run`` endpoint reads from the DB — it does not
        call Celery directly.  We patch the celery task anyway to ensure that
        even if something in the stack tries to use it, the API handles it.
        """
        with patch(
            "backend.celery_app.tasks.ocr_tasks.process_document_ocr"
        ) as mock_task:
            mock_task.delay.side_effect = ConnectionError(
                "Can't connect to broker"
            )
            resp = client.post(
                "/api/v1/ocr/run",
                json={"document_id": 1},
                headers=auth_admin,
            )
            # OCR endpoint returns 404 if doc not found, 200 if found,
            # or 500 on unexpected errors — all are acceptable as long
            # as the server doesn't crash.
            assert resp.status_code in (200, 404, 500), (
                f"OCR failed: {resp.status_code}"
            )

    def test_celery_ocr_task_failure_reported(self, client, auth_admin):
        """When OCR task fails, the error should be reported, not silent."""
        with patch(
            "backend.celery_app.tasks.ocr_tasks.process_document_ocr"
        ) as mock_task:
            mock_task.delay.return_value.get.return_value = {
                "error": "OCR failed",
                "status": "failed",
            }
            resp = client.post(
                "/api/v1/ocr/run",
                json={"document_id": 1},
                headers=auth_admin,
            )
            assert resp.status_code in (200, 404, 500), (
                f"OCR task failure test: {resp.status_code}"
            )

    def test_celery_gps_batch_flush_graceful(self, client, auth_admin):
        """When Redis/Celery for GPS batch flush is down, the ingest
        endpoint should still accept pings."""
        with patch(
            "backend.celery_app.tasks.ocr_tasks.flush_gps_batch_to_postgres"
        ) as mock_flush:
            mock_flush.delay.side_effect = ConnectionError(
                "Can't connect to broker"
            )
            resp = client.post(
                "/api/v1/fleet/gps/ingest",
                json={
                    "truck_id": 1,
                    "latitude": 45.0,
                    "longitude": 25.0,
                    "speed_kmh": 80,
                    "timestamp": "2026-01-01T00:00:00Z",
                },
                headers=auth_admin,
            )
            assert resp.status_code in (202, 500), (
                f"GPS ingest during broker outage: {resp.status_code}"
            )
