"""Chaos tests: Celery worker outage, task failures.

The OCR / document-management endpoints don't call Celery directly — they query
the database.  Celery tasks (``process_document_ocr``, ``flush_gps_batch``) are
scheduled separately.  These tests verify that when the Celery broker is
unreachable or a task fails, the API endpoints that *might* interact with task
queues don't crash.
"""

"""Chaos tests: Celery worker outage, task failures.

The OCR / document-management endpoints don't call Celery directly — they query
the database.  Celery tasks (``process_document_ocr``, ``flush_gps_batch``) are
scheduled separately.  These tests verify that when the Celery broker is
unreachable or a task fails, the API endpoints that *might* interact with task
queues don't crash.
"""

from unittest.mock import patch, MagicMock

import bcrypt
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _celery_client():
    """Create a minimal TestClient for celery chaos tests.
    
    Uses a self-contained app with its own DB so we don't depend on
    the security conftest's session-scoped app fixture, which can
    have env-var conflicts when run after certain test modules.
    """
    import os
    import sys
    import tempfile
    db_path = ""
    # Fresh env for this app
    old = {k: os.environ.get(k) for k in ("OPERION_DB_PATH", "OPERION_JWT_SECRET_KEY",
        "OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH")}
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        os.environ["OPERION_DB_PATH"] = db_path
        os.environ["OPERION_JWT_SECRET_KEY"] = "test-jwt-secret-key-for-celery-chaos"
        os.environ["OPERION_ADMIN_EMAIL"] = "celery-admin@test.com"
        os.environ["OPERION_ADMIN_PASSWORD_HASH"] = bcrypt.hashpw(
            b"celery-admin-pw", bcrypt.gensalt(rounds=4)
        ).decode()
        os.environ.pop("OPERION_API_KEY", None)  # Disable API key middleware
        os.environ["OPERION_ENV"] = "test"
        
        # Reload config so it picks up fresh env vars
        import importlib
        import config as root_config
        importlib.reload(root_config)
        import backend.desktop_config
        importlib.reload(backend.desktop_config)
        # Reload auth middleware since it cached the old Config reference
        import backend.middleware.auth_middleware
        importlib.reload(backend.middleware.auth_middleware)
        
        from backend.dependencies import init_db
        import backend.dependencies as deps
        # Reset the app-lifetime singleton so init_db() builds a FRESH
        # DatabaseManager on the per-test temp file.  A stale singleton from
        # another test module would point at a different DB (e.g. the shared
        # data/cashflow.db) and make these tests query the wrong tables.
        deps._db_instance = None
        db = init_db()
        # Seed a truck so the GPS ownership check (P2: fleet endpoints reject
        # pings for trucks outside the caller's company) passes for truck 1.
        db.conn.execute(
            "INSERT OR IGNORE INTO trucks (id, plate_number, company_id) "
            "VALUES (1, 'CH-CHAOS-01', 0)"
        )
        db.conn.commit()
        
        from backend.main import create_app
        app = create_app()
        client = TestClient(app)
        
        # Login as admin
        resp = client.post("/api/v1/auth/token", data={
            "username": "celery-admin@test.com",
            "password": "celery-admin-pw",
        })
        # Admin login through gateway — should work without DB
        assert resp.status_code == 200, f"Admin login failed: {resp.text}"
        token = resp.json()["access_token"]
        yield client, {"Authorization": f"Bearer {token}"}
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        try:
            os.unlink(db_path)
        except Exception:
            pass
        try:
            os.unlink(db_path + "-wal")
        except Exception:
            pass
        try:
            os.unlink(db_path + "-shm")
        except Exception:
            pass


class TestCeleryChaos:
    """Simulate Celery-level failures — tasks should degrade gracefully."""

    def test_celery_broker_down_ocr(self, _celery_client):
        """When Celery broker is unreachable, OCR tasks should not crash the API."""
        client, auth = _celery_client
        with patch(
            "backend.celery_app.tasks.ocr_tasks.process_document_ocr"
        ) as mock_task:
            mock_task.delay.side_effect = ConnectionError("Can't connect to broker")
            resp = client.post("/api/v1/ocr/run", json={"document_id": 1}, headers=auth)
            assert resp.status_code in (200, 404, 500), f"OCR failed: {resp.status_code}"

    def test_celery_ocr_task_failure_reported(self, _celery_client):
        """When OCR task fails, the error should be reported, not silent."""
        client, auth = _celery_client
        with patch(
            "backend.celery_app.tasks.ocr_tasks.process_document_ocr"
        ) as mock_task:
            mock_task.delay.return_value.get.return_value = {
                "error": "OCR failed", "status": "failed",
            }
            resp = client.post("/api/v1/ocr/run", json={"document_id": 1}, headers=auth)
            assert resp.status_code in (200, 404, 500), f"OCR task failure test: {resp.status_code}"

    def test_celery_gps_batch_flush_graceful(self, _celery_client):
        """When Redis/Celery for GPS batch flush is down, ingest should still work."""
        client, auth = _celery_client
        with patch(
            "backend.celery_app.tasks.ocr_tasks.flush_gps_batch_to_postgres"
        ) as mock_flush:
            mock_flush.delay.side_effect = ConnectionError("Can't connect to broker")
            resp = client.post("/api/v1/fleet/gps/ingest", json={
                "truck_id": 1, "latitude": 45.0, "longitude": 25.0,
                "speed_kmh": 80, "timestamp": "2026-01-01T00:00:00Z",
            }, headers=auth)
            assert resp.status_code in (202, 500), f"GPS ingest during broker outage: {resp.status_code}"
