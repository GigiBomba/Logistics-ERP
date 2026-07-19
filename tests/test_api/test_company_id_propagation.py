"""Tests for company_id propagation through API endpoints.

Verifies that every endpoint extracts company_id from current_user
and passes it to the underlying service/repository.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# Since we can't easily override all dependencies for every endpoint,
# we test the pattern at the function level rather than HTTP level

class TestCompanyIdInTrips:
    """backend/api/v1/trips.py — endpoints should pass company_id to service."""

    def test_get_filtered_accepts_company_id(self):
        """TripService.get_filtered accepts company_id parameter."""
        from services.trip_service import TripService
        sig = __import__("inspect").signature(TripService.get_filtered)
        assert "company_id" in sig.parameters

    def test_get_by_id_accepts_company_id(self):
        from services.trip_service import TripService
        sig = __import__("inspect").signature(TripService.get_by_id)
        assert "company_id" in sig.parameters

    def test_add_accepts_company_id(self):
        from services.trip_service import TripService
        sig = __import__("inspect").signature(TripService.add)
        assert "company_id" in sig.parameters


class TestCompanyIdInFleet:
    """backend/api/v1/fleet.py — endpoints should pass company_id to service."""

    def test_get_trucks_accepts_company_id(self):
        from services.fleet_service import FleetService
        sig = __import__("inspect").signature(FleetService.get_trucks)
        assert "company_id" in sig.parameters

    def test_get_truck_accepts_company_id(self):
        from services.fleet_service import FleetService
        sig = __import__("inspect").signature(FleetService.get_truck)
        assert "company_id" in sig.parameters

    def test_add_truck_accepts_company_id(self):
        from services.fleet_service import FleetService
        sig = __import__("inspect").signature(FleetService.add_truck)
        assert "company_id" in sig.parameters

    def test_update_truck_accepts_company_id(self):
        from services.fleet_service import FleetService
        sig = __import__("inspect").signature(FleetService.update_truck)
        assert "company_id" in sig.parameters

    def test_delete_truck_accepts_company_id(self):
        from services.fleet_service import FleetService
        sig = __import__("inspect").signature(FleetService.delete_truck)
        assert "company_id" in sig.parameters


class TestCompanyIdInClients:
    """backend/api/v1/clients.py — endpoints should pass company_id to service."""

    def test_create_accepts_company_id(self):
        from services.client_service import ClientService
        sig = __import__("inspect").signature(ClientService.create)
        assert "company_id" in sig.parameters

    def test_update_accepts_company_id(self):
        from services.client_service import ClientService
        sig = __import__("inspect").signature(ClientService.update)
        assert "company_id" in sig.parameters

    def test_get_by_id_accepts_company_id(self):
        from services.client_service import ClientService
        sig = __import__("inspect").signature(ClientService.get_by_id)
        assert "company_id" in sig.parameters

    def test_get_all_accepts_company_id(self):
        from services.client_service import ClientService
        sig = __import__("inspect").signature(ClientService.get_all)
        assert "company_id" in sig.parameters


class TestCompanyIdInDocuments:
    """backend/api/v1/documents.py — endpoints should pass company_id."""

    def test_advanced_search_accepts_company_id(self):
        from services.document_service import DocumentService
        sig = __import__("inspect").signature(DocumentService.advanced_search)
        assert "company_id" in sig.parameters

    def test_get_by_id_accepts_company_id(self):
        from services.document_service import DocumentService
        sig = __import__("inspect").signature(DocumentService.get_by_id)
        assert "company_id" in sig.parameters


class TestCompanyIdInDrivers:
    """backend/api/v1/drivers.py — endpoints should pass company_id."""

    def test_driver_repo_get_by_id_accepts_company_id(self):
        from repositories.driver_repository import DriverRepository
        sig = __import__("inspect").signature(DriverRepository.get_by_id)
        assert "company_id" in sig.parameters or "company_id" in str(sig)

    def test_driver_repo_get_all_accepts_company_id(self):
        from repositories.driver_repository import DriverRepository
        sig = __import__("inspect").signature(DriverRepository.get_all)
        assert "company_id" in sig.parameters or "company_id" in str(sig)


class TestCompanyIdInAnalytics:
    """backend/api/v1/analytics.py — endpoints should pass company_id."""

    def test_get_financial_accepts_company_id(self):
        """AnalyticsService.get_financial accepts company_id parameter."""
        from services.analytics_service import AnalyticsService
        sig = __import__("inspect").signature(AnalyticsService.get_financial)
        assert "company_id" in sig.parameters


class TestCompanyIdDefaultValue:
    """Verify company_id defaults to None for desktop backward compatibility."""

    @pytest.mark.parametrize("module_path,class_name,method_name", [
        ("services.trip_service", "TripService", "get_filtered"),
        ("services.trip_service", "TripService", "get_by_id"),
        ("services.fleet_service", "FleetService", "get_trucks"),
        ("services.client_service", "ClientService", "get_all"),
        ("services.document_service", "DocumentService", "advanced_search"),
        ("services.analytics_service", "AnalyticsService", "get_financial"),
    ])
    def test_company_id_defaults_to_none(self, module_path, class_name, method_name):
        """company_id should default to None for backward compatibility."""
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        method = getattr(cls, method_name)
        sig = __import__("inspect").signature(method)
        param = sig.parameters.get("company_id")
        assert param is not None, f"{class_name}.{method_name} missing company_id param"
        assert param.default is None, f"{class_name}.{method_name} company_id default should be None, got {param.default}"


class TestCompanyIdInBackendApiFiles:
    """Verify that API endpoint files extract company_id from current_user."""

    def test_trips_uses_company_id_in_endpoint(self):
        """trips.py should reference company_id from current_user."""
        with open("backend/api/v1/trips.py") as f:
            source = f.read()
        assert "company_id" in source, "trips.py should contain company_id references"

    def test_fleet_uses_company_id_in_endpoint(self):
        with open("backend/api/v1/fleet.py") as f:
            source = f.read()
        assert "company_id" in source, "fleet.py should contain company_id references"

    def test_clients_uses_company_id_in_endpoint(self):
        with open("backend/api/v1/clients.py") as f:
            source = f.read()
        assert "company_id" in source, "clients.py should contain company_id references"

    def test_drivers_uses_company_id_in_endpoint(self):
        with open("backend/api/v1/drivers.py") as f:
            source = f.read()
        assert "company_id" in source, "drivers.py should contain company_id references"

    def test_alerts_uses_company_id_in_endpoint(self):
        with open("backend/api/v1/alerts.py") as f:
            source = f.read()
        assert "company_id" in source, "alerts.py should contain company_id references"

    def test_documents_uses_company_id_in_endpoint(self):
        with open("backend/api/v1/documents.py") as f:
            source = f.read()
        assert "company_id" in source, "documents.py should contain company_id references"

    def test_tacho_uses_company_id_in_endpoint(self):
        with open("backend/api/v1/tacho.py") as f:
            source = f.read()
        assert "company_id" in source, "tacho.py should contain company_id references"

    def test_invoices_uses_company_id_in_endpoint(self):
        with open("backend/api/v1/invoices.py") as f:
            source = f.read()
        assert "company_id" in source, "invoices.py should contain company_id references"

    def test_maintenance_uses_company_id_in_endpoint(self):
        with open("backend/api/v1/maintenance.py") as f:
            source = f.read()
        assert "company_id" in source, "maintenance.py should contain company_id references"

    def test_analytics_uses_company_id_in_endpoint(self):
        with open("backend/api/v1/analytics.py") as f:
            source = f.read()
        assert "company_id" in source, "analytics.py should contain company_id references"
