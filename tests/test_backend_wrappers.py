"""Tests for backend wrapper layer — verify all re-exports resolve and match originals."""
from __future__ import annotations


# ──────────────────────────────────────────────
# backend/db.py
# ──────────────────────────────────────────────
class TestDb:
    """backend/db.py — re-exports DatabaseManager from database.db_manager."""

    def test_database_manager_imports(self):
        from backend.db import DatabaseManager
        assert DatabaseManager is not None

    def test_database_manager_identity(self):
        from backend.db import DatabaseManager as Wrapped
        from database.db_manager import DatabaseManager as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.db as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["DatabaseManager"]


# ──────────────────────────────────────────────
# backend/desktop_config.py
# ──────────────────────────────────────────────
class TestDesktopConfig:
    """backend/desktop_config.py — re-exports Config from config."""

    def test_config_imports(self):
        from backend.desktop_config import Config
        assert Config is not None

    def test_config_identity(self):
        from backend.desktop_config import Config as Wrapped
        from config import Config as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.desktop_config as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["Config"]


# ──────────────────────────────────────────────
# backend/repositories/trip_repository.py
# ──────────────────────────────────────────────
class TestTripRepositoryWrapper:
    """backend/repositories/trip_repository.py — re-exports TripRepository."""

    def test_import_resolves(self):
        from backend.repositories.trip_repository import TripRepository
        assert TripRepository is not None

    def test_identity(self):
        from backend.repositories.trip_repository import TripRepository as Wrapped
        from repositories.trip_repository import TripRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.trip_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["TripRepository"]


# ──────────────────────────────────────────────
# backend/repositories/driver_repository.py
# ──────────────────────────────────────────────
class TestDriverRepositoryWrapper:
    """backend/repositories/driver_repository.py — re-exports DriverRepository."""

    def test_import_resolves(self):
        from backend.repositories.driver_repository import DriverRepository
        assert DriverRepository is not None

    def test_identity(self):
        from backend.repositories.driver_repository import DriverRepository as Wrapped
        from repositories.driver_repository import DriverRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.driver_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["DriverRepository"]


# ──────────────────────────────────────────────
# backend/repositories/fleet_repository.py
# ──────────────────────────────────────────────
class TestFleetRepositoryWrapper:
    """backend/repositories/fleet_repository.py — re-exports FleetRepository."""

    def test_import_resolves(self):
        from backend.repositories.fleet_repository import FleetRepository
        assert FleetRepository is not None

    def test_identity(self):
        from backend.repositories.fleet_repository import FleetRepository as Wrapped
        from repositories.fleet_repository import FleetRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.fleet_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["FleetRepository"]


# ──────────────────────────────────────────────
# backend/repositories/client_repository.py
# ──────────────────────────────────────────────
class TestClientRepositoryWrapper:
    """backend/repositories/client_repository.py — re-exports ClientRepository."""

    def test_import_resolves(self):
        from backend.repositories.client_repository import ClientRepository
        assert ClientRepository is not None

    def test_identity(self):
        from backend.repositories.client_repository import ClientRepository as Wrapped
        from repositories.client_repository import ClientRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.client_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["ClientRepository"]


# ──────────────────────────────────────────────
# backend/repositories/document_repository.py
# ──────────────────────────────────────────────
class TestDocumentRepositoryWrapper:
    """backend/repositories/document_repository.py — re-exports DocumentRepository."""

    def test_import_resolves(self):
        from backend.repositories.document_repository import DocumentRepository
        assert DocumentRepository is not None

    def test_identity(self):
        from backend.repositories.document_repository import DocumentRepository as Wrapped
        from repositories.document_repository import DocumentRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.document_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["DocumentRepository"]


# ──────────────────────────────────────────────
# backend/repositories/audit_repository.py
# ──────────────────────────────────────────────
class TestAuditRepositoryWrapper:
    """backend/repositories/audit_repository.py — re-exports AuditRepository."""

    def test_import_resolves(self):
        from backend.repositories.audit_repository import AuditRepository
        assert AuditRepository is not None

    def test_identity(self):
        from backend.repositories.audit_repository import AuditRepository as Wrapped
        from repositories.audit_repository import AuditRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.audit_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["AuditRepository"]


# ──────────────────────────────────────────────
# backend/repositories/route_repository.py
# ──────────────────────────────────────────────
class TestRouteRepositoryWrapper:
    """backend/repositories/route_repository.py — re-exports RouteRepository."""

    def test_import_resolves(self):
        from backend.repositories.route_repository import RouteRepository
        assert RouteRepository is not None

    def test_identity(self):
        from backend.repositories.route_repository import RouteRepository as Wrapped
        from repositories.route_repository import RouteRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.route_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["RouteRepository"]


# ──────────────────────────────────────────────
# backend/repositories/settings_repository.py
# ──────────────────────────────────────────────
class TestSettingsRepositoryWrapper:
    """backend/repositories/settings_repository.py — re-exports SettingsRepository."""

    def test_import_resolves(self):
        from backend.repositories.settings_repository import SettingsRepository
        assert SettingsRepository is not None

    def test_identity(self):
        from backend.repositories.settings_repository import SettingsRepository as Wrapped
        from repositories.settings_repository import SettingsRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.settings_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["SettingsRepository"]


# ──────────────────────────────────────────────
# backend/repositories/api_key_repository.py
# ──────────────────────────────────────────────
class TestApiKeyRepositoryWrapper:
    """backend/repositories/api_key_repository.py — re-exports ApiKeyRepository."""

    def test_import_resolves(self):
        from backend.repositories.api_key_repository import ApiKeyRepository
        assert ApiKeyRepository is not None

    def test_identity(self):
        from backend.repositories.api_key_repository import ApiKeyRepository as Wrapped
        from repositories.api_key_repository import ApiKeyRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.api_key_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["ApiKeyRepository"]


# ──────────────────────────────────────────────
# backend/repositories/tacho_import_repository.py
# ──────────────────────────────────────────────
class TestTachoImportRepositoryWrapper:
    """backend/repositories/tacho_import_repository.py — re-exports TachoImportRepository."""

    def test_import_resolves(self):
        from backend.repositories.tacho_import_repository import TachoImportRepository
        assert TachoImportRepository is not None

    def test_identity(self):
        from backend.repositories.tacho_import_repository import TachoImportRepository as Wrapped
        from repositories.tacho_import_repository import TachoImportRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.tacho_import_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["TachoImportRepository"]


# ──────────────────────────────────────────────
# backend/repositories/tacho_driver_activity_repository.py
# ──────────────────────────────────────────────
class TestTachoDriverActivityRepositoryWrapper:
    """backend/repositories/tacho_driver_activity_repository.py — re-exports TachoDriverActivityRepository."""

    def test_import_resolves(self):
        from backend.repositories.tacho_driver_activity_repository import TachoDriverActivityRepository
        assert TachoDriverActivityRepository is not None

    def test_identity(self):
        from backend.repositories.tacho_driver_activity_repository import TachoDriverActivityRepository as Wrapped
        from repositories.tacho_driver_activity_repository import TachoDriverActivityRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.tacho_driver_activity_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["TachoDriverActivityRepository"]


# ──────────────────────────────────────────────
# backend/repositories/driver_truck_assignment_repository.py
# ──────────────────────────────────────────────
class TestDriverTruckAssignmentRepositoryWrapper:
    """backend/repositories/driver_truck_assignment_repository.py — re-exports DriverTruckAssignmentRepository."""

    def test_import_resolves(self):
        from backend.repositories.driver_truck_assignment_repository import DriverTruckAssignmentRepository
        assert DriverTruckAssignmentRepository is not None

    def test_identity(self):
        from backend.repositories.driver_truck_assignment_repository import DriverTruckAssignmentRepository as Wrapped
        from repositories.driver_truck_assignment_repository import DriverTruckAssignmentRepository as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.driver_truck_assignment_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["DriverTruckAssignmentRepository"]


# ──────────────────────────────────────────────
# backend/repositories/invoice_repository.py
# ──────────────────────────────────────────────
class TestInvoiceRepositoryWrapper:
    """backend/repositories/invoice_repository.py — re-exports InvoiceRepository, INVOICE_NUMBER_FORMATS, DEFAULT_INVOICE_FORMAT_KEY."""

    def test_invoice_repository_imports(self):
        from backend.repositories.invoice_repository import InvoiceRepository
        assert InvoiceRepository is not None

    def test_invoice_repository_identity(self):
        from backend.repositories.invoice_repository import InvoiceRepository as Wrapped
        from repositories.invoice_repository import InvoiceRepository as Original
        assert Wrapped is Original

    def test_invoice_number_formats_imports(self):
        from backend.repositories.invoice_repository import INVOICE_NUMBER_FORMATS
        assert INVOICE_NUMBER_FORMATS is not None

    def test_invoice_number_formats_identity(self):
        from backend.repositories.invoice_repository import INVOICE_NUMBER_FORMATS as Wrapped
        from repositories.invoice_repository import INVOICE_NUMBER_FORMATS as Original
        assert Wrapped is Original

    def test_default_invoice_format_key_imports(self):
        from backend.repositories.invoice_repository import DEFAULT_INVOICE_FORMAT_KEY
        assert DEFAULT_INVOICE_FORMAT_KEY is not None

    def test_default_invoice_format_key_identity(self):
        from backend.repositories.invoice_repository import DEFAULT_INVOICE_FORMAT_KEY as Wrapped
        from repositories.invoice_repository import DEFAULT_INVOICE_FORMAT_KEY as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.invoice_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["InvoiceRepository", "INVOICE_NUMBER_FORMATS", "DEFAULT_INVOICE_FORMAT_KEY"]


# ──────────────────────────────────────────────
# backend/repositories/proforma_repository.py
# ──────────────────────────────────────────────
class TestProformaRepositoryWrapper:
    """backend/repositories/proforma_repository.py — re-exports ProformaRepository, PROFORMA_NUMBER_FORMATS, DEFAULT_PROFORMA_FORMAT_KEY."""

    def test_proforma_repository_imports(self):
        from backend.repositories.proforma_repository import ProformaRepository
        assert ProformaRepository is not None

    def test_proforma_repository_identity(self):
        from backend.repositories.proforma_repository import ProformaRepository as Wrapped
        from repositories.proforma_repository import ProformaRepository as Original
        assert Wrapped is Original

    def test_proforma_number_formats_imports(self):
        from backend.repositories.proforma_repository import PROFORMA_NUMBER_FORMATS
        assert PROFORMA_NUMBER_FORMATS is not None

    def test_proforma_number_formats_identity(self):
        from backend.repositories.proforma_repository import PROFORMA_NUMBER_FORMATS as Wrapped
        from repositories.proforma_repository import PROFORMA_NUMBER_FORMATS as Original
        assert Wrapped is Original

    def test_default_proforma_format_key_imports(self):
        from backend.repositories.proforma_repository import DEFAULT_PROFORMA_FORMAT_KEY
        assert DEFAULT_PROFORMA_FORMAT_KEY is not None

    def test_default_proforma_format_key_identity(self):
        from backend.repositories.proforma_repository import DEFAULT_PROFORMA_FORMAT_KEY as Wrapped
        from repositories.proforma_repository import DEFAULT_PROFORMA_FORMAT_KEY as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.proforma_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["ProformaRepository", "PROFORMA_NUMBER_FORMATS", "DEFAULT_PROFORMA_FORMAT_KEY"]


# ──────────────────────────────────────────────
# backend/repositories/receipt_repository.py
# ──────────────────────────────────────────────
class TestReceiptRepositoryWrapper:
    """backend/repositories/receipt_repository.py — re-exports ReceiptRepository, RECEIPT_NUMBER_FORMATS, DEFAULT_FORMAT_KEY."""

    def test_receipt_repository_imports(self):
        from backend.repositories.receipt_repository import ReceiptRepository
        assert ReceiptRepository is not None

    def test_receipt_repository_identity(self):
        from backend.repositories.receipt_repository import ReceiptRepository as Wrapped
        from repositories.receipt_repository import ReceiptRepository as Original
        assert Wrapped is Original

    def test_receipt_number_formats_imports(self):
        from backend.repositories.receipt_repository import RECEIPT_NUMBER_FORMATS
        assert RECEIPT_NUMBER_FORMATS is not None

    def test_receipt_number_formats_identity(self):
        from backend.repositories.receipt_repository import RECEIPT_NUMBER_FORMATS as Wrapped
        from repositories.receipt_repository import RECEIPT_NUMBER_FORMATS as Original
        assert Wrapped is Original

    def test_default_format_key_imports(self):
        from backend.repositories.receipt_repository import DEFAULT_FORMAT_KEY
        assert DEFAULT_FORMAT_KEY is not None

    def test_default_format_key_identity(self):
        from backend.repositories.receipt_repository import DEFAULT_FORMAT_KEY as Wrapped
        from repositories.receipt_repository import DEFAULT_FORMAT_KEY as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.repositories.receipt_repository as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["ReceiptRepository", "RECEIPT_NUMBER_FORMATS", "DEFAULT_FORMAT_KEY"]


# ──────────────────────────────────────────────
# backend/services/trip_service.py
# ──────────────────────────────────────────────
class TestTripServiceWrapper:
    """backend/services/trip_service.py — re-exports TripService."""

    def test_import_resolves(self):
        from backend.services.trip_service import TripService
        assert TripService is not None

    def test_identity(self):
        from backend.services.trip_service import TripService as Wrapped
        from services.trip_service import TripService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.trip_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["TripService"]


# ──────────────────────────────────────────────
# backend/services/fleet_service.py
# ──────────────────────────────────────────────
class TestFleetServiceWrapper:
    """backend/services/fleet_service.py — re-exports FleetService."""

    def test_import_resolves(self):
        from backend.services.fleet_service import FleetService
        assert FleetService is not None

    def test_identity(self):
        from backend.services.fleet_service import FleetService as Wrapped
        from services.fleet_service import FleetService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.fleet_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["FleetService"]


# ──────────────────────────────────────────────
# backend/services/client_service.py
# ──────────────────────────────────────────────
class TestClientServiceWrapper:
    """backend/services/client_service.py — re-exports ClientService."""

    def test_import_resolves(self):
        from backend.services.client_service import ClientService
        assert ClientService is not None

    def test_identity(self):
        from backend.services.client_service import ClientService as Wrapped
        from services.client_service import ClientService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.client_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["ClientService"]


# ──────────────────────────────────────────────
# backend/services/document_service.py
# ──────────────────────────────────────────────
class TestDocumentServiceWrapper:
    """backend/services/document_service.py — re-exports DocumentService."""

    def test_import_resolves(self):
        from backend.services.document_service import DocumentService
        assert DocumentService is not None

    def test_identity(self):
        from backend.services.document_service import DocumentService as Wrapped
        from services.document_service import DocumentService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.document_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["DocumentService"]


# ──────────────────────────────────────────────
# backend/services/analytics_service.py
# ──────────────────────────────────────────────
class TestAnalyticsServiceWrapper:
    """backend/services/analytics_service.py — re-exports AnalyticsService."""

    def test_import_resolves(self):
        from backend.services.analytics_service import AnalyticsService
        assert AnalyticsService is not None

    def test_identity(self):
        from backend.services.analytics_service import AnalyticsService as Wrapped
        from services.analytics_service import AnalyticsService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.analytics_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["AnalyticsService"]


# ──────────────────────────────────────────────
# backend/services/payment_batch_service.py
# ──────────────────────────────────────────────
class TestPaymentBatchServiceWrapper:
    """backend/services/payment_batch_service.py — re-exports PaymentBatchService."""

    def test_import_resolves(self):
        from backend.services.payment_batch_service import PaymentBatchService
        assert PaymentBatchService is not None

    def test_identity(self):
        from backend.services.payment_batch_service import PaymentBatchService as Wrapped
        from services.payment_batch_service import PaymentBatchService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.payment_batch_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["PaymentBatchService"]


# ──────────────────────────────────────────────
# backend/services/payment_profile_service.py
# ──────────────────────────────────────────────
class TestPaymentProfileServiceWrapper:
    """backend/services/payment_profile_service.py — re-exports PaymentProfileService."""

    def test_import_resolves(self):
        from backend.services.payment_profile_service import PaymentProfileService
        assert PaymentProfileService is not None

    def test_identity(self):
        from backend.services.payment_profile_service import PaymentProfileService as Wrapped
        from services.payment_profile_service import PaymentProfileService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.payment_profile_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["PaymentProfileService"]


# ──────────────────────────────────────────────
# backend/services/conflict_service.py
# ──────────────────────────────────────────────
class TestConflictServiceWrapper:
    """backend/services/conflict_service.py — re-exports TripConflictService."""

    def test_import_resolves(self):
        from backend.services.conflict_service import TripConflictService
        assert TripConflictService is not None

    def test_identity(self):
        from backend.services.conflict_service import TripConflictService as Wrapped
        from services.conflict_service import TripConflictService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.conflict_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["TripConflictService"]


# ──────────────────────────────────────────────
# backend/services/export_service.py
# ──────────────────────────────────────────────
class TestExportServiceWrapper:
    """backend/services/export_service.py — re-exports ExportService."""

    def test_import_resolves(self):
        from backend.services.export_service import ExportService
        assert ExportService is not None

    def test_identity(self):
        from backend.services.export_service import ExportService as Wrapped
        from services.export_service import ExportService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.export_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["ExportService"]


# ──────────────────────────────────────────────
# backend/services/driver_truck_service.py
# ──────────────────────────────────────────────
class TestDriverTruckServiceWrapper:
    """backend/services/driver_truck_service.py — re-exports DriverTruckService."""

    def test_import_resolves(self):
        from backend.services.driver_truck_service import DriverTruckService
        assert DriverTruckService is not None

    def test_identity(self):
        from backend.services.driver_truck_service import DriverTruckService as Wrapped
        from services.driver_truck_service import DriverTruckService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.driver_truck_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["DriverTruckService"]


# ──────────────────────────────────────────────
# backend/services/route_service.py
# ──────────────────────────────────────────────
class TestRouteServiceWrapper:
    """backend/services/route_service.py — re-exports RouteService and GraphHopperClient."""

    def test_route_service_imports(self):
        from backend.services.route_service import RouteService
        assert RouteService is not None

    def test_route_service_identity(self):
        from backend.services.route_service import RouteService as Wrapped
        from services.route_service import RouteService as Original
        assert Wrapped is Original

    def test_graphhopper_client_imports(self):
        from backend.services.route_service import GraphHopperClient
        assert GraphHopperClient is not None

    def test_graphhopper_client_identity(self):
        from backend.services.route_service import GraphHopperClient as Wrapped
        from services.route_service import GraphHopperClient as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.route_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["RouteService", "GraphHopperClient"]


# ──────────────────────────────────────────────
# backend/services/route_history_service.py
# ──────────────────────────────────────────────
class TestRouteHistoryServiceWrapper:
    """backend/services/route_history_service.py — re-exports RouteHistoryService."""

    def test_import_resolves(self):
        from backend.services.route_history_service import RouteHistoryService
        assert RouteHistoryService is not None

    def test_identity(self):
        from backend.services.route_history_service import RouteHistoryService as Wrapped
        from services.route_history_service import RouteHistoryService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.route_history_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["RouteHistoryService"]


# ──────────────────────────────────────────────
# backend/services/tacho_service.py
# ──────────────────────────────────────────────
class TestTachoServiceWrapper:
    """backend/services/tacho_service.py — re-exports TachoService."""

    def test_import_resolves(self):
        from backend.services.tacho_service import TachoService
        assert TachoService is not None

    def test_identity(self):
        from backend.services.tacho_service import TachoService as Wrapped
        from services.tacho_service import TachoService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.tacho_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["TachoService"]


# ──────────────────────────────────────────────
# backend/services/fuel_price_service.py
# ──────────────────────────────────────────────
class TestFuelPriceServiceWrapper:
    """backend/services/fuel_price_service.py — re-exports FuelPriceService."""

    def test_import_resolves(self):
        from backend.services.fuel_price_service import FuelPriceService
        assert FuelPriceService is not None

    def test_identity(self):
        from backend.services.fuel_price_service import FuelPriceService as Wrapped
        from services.fuel_price_service import FuelPriceService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.fuel_price_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["FuelPriceService"]


# ──────────────────────────────────────────────
# backend/services/fleet_maintenance_service.py
# ──────────────────────────────────────────────
class TestFleetMaintenanceServiceWrapper:
    """backend/services/fleet_maintenance_service.py — re-exports FleetMaintenanceService."""

    def test_import_resolves(self):
        from backend.services.fleet_maintenance_service import FleetMaintenanceService
        assert FleetMaintenanceService is not None

    def test_identity(self):
        from backend.services.fleet_maintenance_service import FleetMaintenanceService as Wrapped
        from services.fleet_maintenance_service import FleetMaintenanceService as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.fleet_maintenance_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["FleetMaintenanceService"]


# ──────────────────────────────────────────────
# backend/services/feature_flags_service.py
# ──────────────────────────────────────────────
class TestFeatureFlagsServiceWrapper:
    """backend/services/feature_flags_service.py — re-exports FeatureFlagService and FEATURE_FLAGS."""

    def test_feature_flag_service_imports(self):
        from backend.services.feature_flags_service import FeatureFlagService
        assert FeatureFlagService is not None

    def test_feature_flag_service_identity(self):
        from backend.services.feature_flags_service import FeatureFlagService as Wrapped
        from services.feature_flags import FeatureFlagService as Original
        assert Wrapped is Original

    def test_feature_flags_imports(self):
        from backend.services.feature_flags_service import FEATURE_FLAGS
        assert FEATURE_FLAGS is not None

    def test_feature_flags_identity(self):
        from backend.services.feature_flags_service import FEATURE_FLAGS as Wrapped
        from services.feature_flags import FEATURE_FLAGS as Original
        assert Wrapped is Original

    def test_all_exports(self):
        import backend.services.feature_flags_service as mod
        assert hasattr(mod, "__all__")
        assert mod.__all__ == ["FeatureFlagService", "FEATURE_FLAGS"]
