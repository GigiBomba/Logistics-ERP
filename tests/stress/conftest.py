"""Shared fixtures for stress tests."""
from __future__ import annotations

# Import API test fixtures so tests in this directory can use client_with_mocks etc.
from tests.test_api.conftest import (  # noqa: F401
    app,
    client,
    mock_trip_service,
    mock_client_service,
    mock_fleet_service,
    mock_driver_repo,
    mock_document_service,
    mock_analytics_service,
    mock_db,
    client_with_mocks,
)
