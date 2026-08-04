"""Shared fixtures for mutation API tests."""
from __future__ import annotations

import os

# Set test environment BEFORE any backend imports can happen.
os.environ.setdefault("OPERION_ENV", "testing")
os.environ.setdefault("OPERION_JWT_SECRET_KEY", "test-jwt-secret-key-for-testing")
os.environ.setdefault("OPERION_API_KEY", "test-api-key")
os.environ.setdefault("OPERION_API_URL", "http://test")

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


class _DbMock(MagicMock):
    """Mock DatabaseManager that supports repository _fetchone/_fetchall calls."""
    pass


class StrippedMock(MagicMock):
    """MagicMock subclass that strips company_id from all recorded calls."""
    def _increment_mock_call(self, /, *args, **kwargs):
        kwargs.pop("company_id", None)
        return super()._increment_mock_call(*args, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def _set_env():
    """Ensure env vars are set before any mutation test imports backend code."""
    os.environ.setdefault("OPERION_ENV", "testing")
    os.environ.setdefault("OPERION_JWT_SECRET_KEY", "test-jwt-secret-key-for-testing")
    os.environ.setdefault("OPERION_API_KEY", "test-api-key")
    os.environ.setdefault("OPERION_API_URL", "http://test")


@pytest.fixture
def app():
    """Create a minimal FastAPI app with the v1 router."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from backend.api.v1.router import api_v1_router

    app = FastAPI()
    app.include_router(api_v1_router)

    @app.exception_handler(Exception)
    async def generic_json_exception_handler(request, exc):
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "error_code": "INTERNAL_ERROR"})

    @app.exception_handler(StarletteHTTPException)
    async def http_json_exception_handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return app


@pytest.fixture
def mock_trip_service():
    from datetime import date
    from models.common import ServiceResult
    from models.trip_models import TripResult
    svc = StrippedMock()
    svc.get_filtered.return_value = []
    svc.get_by_id.return_value = None
    trip_result = TripResult(id=1, client_id=1, reference="", start_date=date(2000, 1, 1), price_eur=0.0, currency="EUR", status="Planned")
    svc.create.return_value = ServiceResult(success=True, data=trip_result)
    svc.update.return_value = ServiceResult(success=True, data=trip_result)
    return svc


@pytest.fixture
def mock_client_service():
    svc = StrippedMock()
    svc.create.return_value = 1
    svc.get_all.return_value = []
    return svc


@pytest.fixture
def mock_fleet_service():
    svc = StrippedMock()
    return svc


@pytest.fixture
def mock_driver_repo():
    repo = StrippedMock()
    return repo


@pytest.fixture
def mock_document_service():
    svc = StrippedMock()
    svc.upload_document.return_value = MagicMock(success=True, data=MagicMock(model_dump=lambda: {"id": 1, "doc_number": "DOC-2024-0001", "file_name": "test.pdf"}))
    return svc


@pytest.fixture
def mock_analytics_service():
    svc = StrippedMock()
    return svc


@pytest.fixture
def mock_db():
    """Mock DatabaseManager."""
    mock = _DbMock()
    mock.row_to_dict.side_effect = lambda row: None if row is None else dict(row)
    mock.rows_to_dicts.side_effect = lambda rows: [dict(r) for r in (rows or [])]
    return mock


@pytest.fixture
def client_with_mocks(app, mock_trip_service, mock_client_service, mock_fleet_service,
                       mock_driver_repo, mock_document_service, mock_analytics_service, mock_db):
    """TestClient with all service dependencies mocked.

    Yields a tuple ``(client, mocks)`` where ``mocks`` is a dict keyed by
    dependency name (``trip_service``, ``client_service``, ``driver_repo``,
    ``db``, …) for convenient assertion and configuration in tests.
    """
    from backend.dependencies import (
        get_trip_service, get_client_service, get_fleet_service,
        get_driver_repo, get_document_service, get_analytics_service, get_db,
    )
    from backend.dependencies_security import get_current_user, require_dispatcher, require_admin, require_manager

    mock_user = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_trip_service] = lambda: mock_trip_service
    app.dependency_overrides[get_client_service] = lambda: mock_client_service
    app.dependency_overrides[get_fleet_service] = lambda: mock_fleet_service
    app.dependency_overrides[get_driver_repo] = lambda: mock_driver_repo
    app.dependency_overrides[get_document_service] = lambda: mock_document_service
    app.dependency_overrides[get_analytics_service] = lambda: mock_analytics_service
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_dispatcher] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
    app.dependency_overrides[require_manager] = lambda: mock_user

    mocks = {
        "trip_service": mock_trip_service,
        "client_service": mock_client_service,
        "fleet_service": mock_fleet_service,
        "driver_repo": mock_driver_repo,
        "document_service": mock_document_service,
        "analytics_service": mock_analytics_service,
        "db": mock_db,
    }
    yield TestClient(app, raise_server_exceptions=False), mocks
    app.dependency_overrides.clear()
