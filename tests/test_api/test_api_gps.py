"""Tests for GPS telemetry endpoints."""
from __future__ import annotations

import os
import tempfile

os.environ["OPERION_DB_PATH"] = ":memory:"


import pytest
from fastapi.testclient import TestClient

from backend.dependencies_security import get_current_user, require_admin, require_dispatcher
from backend.main import create_app
from tests.test_api.helpers import create_test_app


@pytest.fixture(autouse=True)
def _reset_redis_url(monkeypatch):
    """Other test modules may pollute OPERION_REDIS_URL — reset to a valid default."""
    monkeypatch.setenv("OPERION_REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture(autouse=True)
def _seed_company_trucks(monkeypatch):
    """Seed companies and trucks in the sandbox DB.

    The module-level ``OPERION_DB_PATH = ":memory:"`` above has NO effect:
    ``config.Config.DB_PATH`` is already frozen when the conftest chain
    imports ``backend.api.v1.fleet`` → ``backend.desktop_config`` →
    ``config``, BEFORE this module body runs.  Without a fix, the suite would
    run against the shared file DB (``data/cashflow.db``) whose
    ``gps_telemetry`` may lack ``company_id`` (stale file / stale
    ``backend.dependencies._db_instance`` singleton), which made
    ``test_gps_history_empty`` fail with ``no such column: company_id``.

    Inject a fresh, fully-migrated temporary-file DatabaseManager into the
    app-lifetime singleton so the sandbox always carries the production
    schema (``company_id`` guaranteed by ``_create_tables_and_indices``),
    and seed real truck rows: trucks 1/2 belong to company 1 (the caller),
    truck 999 belongs to company 2 (foreign — must be rejected).

    A plain ``:memory:`` DatabaseManager would not work here: its
    ConnectionPool hands out a brand-new empty in-memory database per
    thread, while FastAPI runs the ``get_db`` dependency on a different
    thread than the seeding fixture.  A temporary file is shared by all
    threads, so the seeded schema/data are visible to the endpoints.
    """
    from database.db_manager import DatabaseManager
    from backend import dependencies as deps

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = DatabaseManager(tmp.name)
    deps._db_instance = db
    monkeypatch.setattr(deps, "init_db", lambda app=None: db)
    db.execute(
        "INSERT OR IGNORE INTO companies (id, company_name) "
        "VALUES (1, 'Company A'), (2, 'Company B')"
    )
    db.conn.commit()
    db.execute(
        "INSERT OR IGNORE INTO trucks (id, plate_number, company_id) "
        "VALUES (1, 'AB123CD', 1), (2, 'XY789EF', 1), (999, 'ZZ999ZZ', 2)"
    )
    db.conn.commit()
    yield db
    db.close()
    if deps._db_instance is db:
        deps._db_instance = None
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def client():
    app = create_test_app()
    mock_user = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_dispatcher] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
    return TestClient(app)


class TestGpsIngest:
    def test_ingest_single_ping(self, client):
        data = {
            "truck_id": 1,
            "latitude": 44.4268,
            "longitude": 26.1025,
            "speed_kmh": 85.0,
            "heading": 180,
            "timestamp": "2026-07-04T12:00:00Z",
        }
        response = client.post("/api/v1/fleet/gps/ingest", json=data)
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"

    def test_ingest_batch(self, client):
        pings = [
            {
                "truck_id": 1,
                "latitude": 44.4,
                "longitude": 26.1,
                "speed_kmh": 80.0,
                "heading": 90,
                "timestamp": "2026-07-04T12:01:00Z",
            },
            {
                "truck_id": 2,
                "latitude": 44.5,
                "longitude": 26.2,
                "speed_kmh": 60.0,
                "heading": 270,
                "timestamp": "2026-07-04T12:02:00Z",
            },
        ]
        response = client.post("/api/v1/fleet/gps/batch", json=pings)
        assert response.status_code == 202
        assert response.json()["count"] == 2

    def test_live_position_not_found(self, client):
        response = client.get("/api/v1/fleet/gps/live/99999")
        assert response.status_code == 404

    def test_ingest_foreign_truck_returns_404(self, client):
        # Truck 999 belongs to company 2 — the company-1 caller must be rejected.
        data = {
            "truck_id": 999,
            "latitude": 44.4268,
            "longitude": 26.1025,
            "speed_kmh": 85.0,
            "heading": 180,
            "timestamp": "2026-07-04T12:00:00Z",
        }
        response = client.post("/api/v1/fleet/gps/ingest", json=data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Truck not found"

    def test_live_foreign_truck_returns_404(self, client):
        response = client.get("/api/v1/fleet/gps/live/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Truck not found"

    def test_batch_foreign_truck_returns_404(self, client):
        # Truck 999 belongs to company 2 — the whole batch must be rejected
        # before any ping is stored.
        pings = [
            {"truck_id": 1, "latitude": 44.4, "longitude": 26.1,
             "speed_kmh": 80.0, "heading": 90, "timestamp": "2026-07-04T12:01:00Z"},
            {"truck_id": 999, "latitude": 44.5, "longitude": 26.2,
             "speed_kmh": 60.0, "heading": 270, "timestamp": "2026-07-04T12:02:00Z"},
        ]
        response = client.post("/api/v1/fleet/gps/batch", json=pings)
        assert response.status_code == 404
        assert response.json()["detail"] == "Truck not found"

    def test_history_foreign_truck_returns_404(self, client):
        response = client.get("/api/v1/fleet/gps/history/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Truck not found"

    def test_gps_history_empty(self, client):
        response = client.get("/api/v1/fleet/gps/history/1")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
