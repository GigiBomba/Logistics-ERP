"""Shared fixtures for backend API tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


class _DbMock(MagicMock):
    """Mock DatabaseManager that supports repository _fetchone/_fetchall calls."""
    pass


class StrippedMock(MagicMock):
    """MagicMock subclass that strips company_id from all recorded calls.

    Route handlers inject company_id for multi-tenant isolation, but test
    assertions were written before this parameter existed.  This mock
    transparently removes company_id from every recorded call so existing
    ``assert_called_once_with(...)`` assertions continue to pass without
    needing to add ``company_id=ANY`` to each one.

    Child mocks are also ``StrippedMock`` instances because ``MagicMock``
    creates children using ``type(self)``.
    """

    def _increment_mock_call(self, /, *args, **kwargs):
        kwargs.pop("company_id", None)
        return super()._increment_mock_call(*args, **kwargs)

# Import the main FastAPI app
# The app is created in backend/main.py or similar — read the file to find the app instance.
# If there's no single app factory, create one from the router:

from backend.api.v1.router import api_v1_router
from fastapi import FastAPI

# Re-export create_test_app for convenience
from tests.test_api.helpers import create_test_app  # noqa: F401


@pytest.fixture
def app():
    """Create a FastAPI app with the v1 router for testing."""
    app = FastAPI()
    app.include_router(api_v1_router)

    # Register JSON exception handlers so 500 errors return JSON, not plain text.
    # (Starlette's default ServerErrorMiddleware returns plain text.)
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(Exception)
    async def generic_json_exception_handler(request, exc):
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "error_code": "INTERNAL_ERROR"})

    @app.exception_handler(StarletteHTTPException)
    async def http_json_exception_handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return app


@pytest.fixture
def client(app):
    """TestClient with mocked authentication."""
    # Override the auth dependency to bypass JWT
    from backend.dependencies_security import get_current_user, require_dispatcher, require_admin, require_manager
    mock_user = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_dispatcher] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
    app.dependency_overrides[require_manager] = lambda: mock_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


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
