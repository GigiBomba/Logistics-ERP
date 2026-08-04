"""Platform parity: Feature inventory verification."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.parity


class TestFeatureInventory:
    """Core operations available via service API regardless of platform."""

    def test_trip_read_write_available(self, trip_service):
        """Trip creation and querying are available."""
        assert callable(trip_service.create)
        assert callable(trip_service.update)
        assert callable(trip_service.get_by_id)

    def test_invoice_read_write_available(self, invoice_service):
        """Invoice operations are available."""
        assert callable(invoice_service.create)
        assert callable(invoice_service.finalize)
        assert callable(invoice_service.set_status)

    def test_fleet_read_available(self, fleet_repo):
        """Fleet repository querying is available."""
        assert callable(fleet_repo.get_by_id)

    def test_driver_read_available(self, driver_repo):
        """Driver repository querying is available."""
        assert callable(driver_repo.get_by_id)
