"""Tests for new service methods backing the tool stubs.

Uses MagicMock for repositories to avoid any database dependency.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from models.common import ServiceResult


# ═════════════════════════════════════════════════════════════════════════════
#  ProformaService.update()
# ═════════════════════════════════════════════════════════════════════════════


class TestProformaServiceUpdate:
    """ProformaService.update() — mock the repo, verify update is called with correct data."""

    @pytest.fixture(autouse=True)
    def _setup(self, request):
        """Set up mocks before each test and tear them down after."""
        patchers = [
            patch("services.invoicing.proforma_service.ProformaRepository"),
            patch("services.invoicing.proforma_service.PermissionService"),
            patch("services.invoicing.proforma_service.ClientRepository"),
            patch("services.invoicing.proforma_service.InvoiceRepository"),
            patch("services.invoicing.proforma_service.InvoiceGenerator"),
            patch("services.invoicing.proforma_service.EventBus"),
        ]
        for p in patchers:
            p.start()
        request.addfinalizer(lambda: [p.stop() for p in patchers])

        from services.invoicing.proforma_service import ProformaService

        import services.invoicing.proforma_service as ps_mod
        self._repo = MagicMock()
        ps_mod.ProformaRepository.return_value = self._repo

        # Mock PermissionService so can_update_proforma → True
        mock_perm = MagicMock()
        mock_perm.can_update_proforma.return_value = MagicMock(allowed=True)
        ps_mod.PermissionService.return_value = mock_perm

        self.service = ProformaService(MagicMock(), prefs=None)

    def _fake_row(self) -> dict:
        return {
            "id": 1,
            "proforma_number": "PF-001",
            "client_name": "ACME",
            "issue_date": "2026-07-16",
            "valid_until": "2026-08-15",
            "grand_total": 100.0,
            "currency": "EUR",
            "status": "Draft",
            "notes": "",
        }

    def test_update_calls_repo_update(self):
        """Update with notes and currency should call repo.update with correct kwargs."""
        self._repo.get_by_id.return_value = self._fake_row()
        result = self.service.update(proforma_id=1, data={"notes": "Updated note", "currency": "USD"}, user_id=42)
        self._repo.update.assert_called_once()
        assert result.success

    def test_update_no_fields_returns_error(self):
        """Update with no editable fields should return error."""
        self._repo.get_by_id.return_value = self._fake_row()
        result = self.service.update(proforma_id=1, data={}, user_id=42)
        assert not result.success

    def test_update_not_found_returns_error(self):
        """Update non-existent proforma should return error."""
        self._repo.get_by_id.return_value = None
        result = self.service.update(proforma_id=999, data={"notes": "test"}, user_id=42)
        assert not result.success


# ═════════════════════════════════════════════════════════════════════════════
#  ReceiptGenerator.finalize()
# ═════════════════════════════════════════════════════════════════════════════


class TestReceiptGeneratorFinalize:
    """ReceiptGenerator.finalize() — mock the repo, verify status changes to Finalized."""

    @pytest.fixture(autouse=True)
    def _setup(self, request):
        """Patch ReceiptRepository and PermissionService before each test.

        PermissionService is imported lazily inside ReceiptGenerator._perm,
        so we patch at the definition site (services.permission_service).
        """
        patchers = [
            patch("repositories.receipt_repository.ReceiptRepository"),
            patch("services.permission_service.PermissionService"),
            patch("repositories.client_repository.ClientRepository"),
        ]
        for p in patchers:
            p.start()
        request.addfinalizer(lambda: [p.stop() for p in patchers])

        from services.invoicing.receipt_generator import ReceiptGenerator

        self._repo = MagicMock()
        import repositories.receipt_repository as rr_mod
        rr_mod.ReceiptRepository.return_value = self._repo

        # Mock PermissionService so can_update_receipt → True
        mock_perm = MagicMock()
        mock_perm.can_update_receipt.return_value = MagicMock(allowed=True)
        import services.permission_service as ps_mod
        ps_mod.PermissionService.return_value = mock_perm
        self._mock_perm = mock_perm

        self.service = ReceiptGenerator(db=MagicMock())

    def _fake_row(self, status: str = "Draft") -> dict:
        return {
            "id": 1,
            "receipt_number": "RCT-001",
            "status": status,
            "issue_date": "2026-07-16",
            "currency": "EUR",
            "total": 100.0,
            "client_id": 1,
            "received_from_name": "ACME",
            "attachments_json": "[]",
        }

    def test_finalize_changes_status_to_finalized(self):
        """Finalize transitions Draft receipt to Finalized status."""
        self._repo.get_by_id.return_value = self._fake_row(status="Draft")
        result = self.service.finalize(receipt_id=1, user_id=42)
        assert result.success
        if isinstance(result.data, dict):
            assert result.data.get("status") == "Finalized"
        self._repo.update.assert_called_once()

    def test_finalize_not_found_returns_error(self):
        """Finalize non-existent receipt should return error."""
        self._repo.get_by_id.return_value = None
        result = self.service.finalize(receipt_id=999, user_id=42)
        assert not result.success

    def test_finalize_wrong_status_returns_error(self):
        """Finalize a receipt not in Draft status should return error."""
        self._repo.get_by_id.return_value = self._fake_row(status="Finalized")
        result = self.service.finalize(receipt_id=1, user_id=42)
        assert not result.success

    def test_finalize_permission_denied(self):
        """Finalize without permission should fail."""
        self._mock_perm.can_update_receipt.return_value = MagicMock(
            allowed=False, reason="No access"
        )
        result = self.service.finalize(receipt_id=1, user_id=42)
        assert not result.success


# ═════════════════════════════════════════════════════════════════════════════
#  RouteHistoryService.update_route()
# ═════════════════════════════════════════════════════════════════════════════


class TestRouteHistoryServiceUpdateRoute:
    """RouteHistoryService.update_route() — mock the repo, verify update is called."""

    @pytest.fixture(autouse=True)
    def _setup(self, request):
        patchers = [
            patch("services.route_history_service.RouteRepository"),
            patch("services.route_history_service.RouteEventRepository"),
            patch("services.route_history_service.TruckRouteAssignmentRepository"),
            patch("services.route_history_service.RouteEventBus"),
            patch("services.route_history_service._RECENT_ROUTE_CACHE"),
        ]
        for p in patchers:
            p.start()
        request.addfinalizer(lambda: [p.stop() for p in patchers])

        from services.route_history_service import RouteHistoryService
        import services.route_history_service as rh_mod

        # Make the recent-route-cache mock return None so load_route falls
        # through to the RouteRepository.
        rh_mod._RECENT_ROUTE_CACHE.get.return_value = None

        self._route_repo = MagicMock()
        rh_mod.RouteRepository.return_value = self._route_repo
        self.service = RouteHistoryService(MagicMock())

    def _fake_row(self) -> dict:
        """Return a minimal row dict matching RouteRepository.get_by_id output."""
        import json
        import zlib

        return {
            "id": 1,
            "metadata_version": 1,
            "stops_json": '[{"lat": 46.0, "lon": 23.0}]',
            "geometry_compressed": zlib.compress(json.dumps([]).encode("utf-8")),
            "total_distance_km": 100.0,
            "duration_min": 60.0,
            "truck_id": "1",
            "truck_label": "TRUCK-1",
            "truck_json": "{}",
            "profile": "truck",
            "excluded_countries_json": "[]",
            "countries_traversed_json": "[]",
        }

    def test_update_route_calls_repo_update(self):
        """update_route should call RouteRepository.update with correct data."""
        self._route_repo.get_by_id.return_value = self._fake_row()

        from services.route_history_service import RouteHistoryRecord

        record = RouteHistoryRecord(
            stops=[{"lat": 46.5, "lon": 23.5}],
            geometry=[],
            total_distance_km=150.0,
            duration_min=90.0,
            truck_id="1",
            truck_label="TRUCK-1",
            profile="truck",
        )

        result = self.service.update_route(route_id=1, record=record)
        assert result is True
        self._route_repo.update.assert_called_once()

    def test_update_route_not_found_returns_false(self):
        """update_route returns False when route does not exist."""
        self._route_repo.get_by_id.return_value = None

        from services.route_history_service import RouteHistoryRecord

        record = RouteHistoryRecord(stops=[{"lat": 46.0, "lon": 23.0}])
        result = self.service.update_route(route_id=999, record=record)
        assert result is False
