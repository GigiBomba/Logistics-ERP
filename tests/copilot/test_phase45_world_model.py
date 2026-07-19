"""Tests for Phase 4 World Model — data accuracy and tenant isolation.

Blueprint: §6 — World Model.
"""

import pytest
from unittest.mock import MagicMock, patch

from backend.copilot.world_model import (
    WorldModelService, WorldModelSnapshot, FleetSummary,
)


class TestWorldModelService:
    """World Model snapshot building."""

    def test_service_constructable(self):
        """WorldModelService can be constructed with a db mock."""
        svc = WorldModelService(db=MagicMock())
        assert svc is not None

    def test_get_slice_returns_snapshot(self):
        """get_slice returns a WorldModelSnapshot with all defaults."""
        svc = WorldModelService(db=MagicMock())
        snapshot = svc.get_slice(company_id=1)
        assert isinstance(snapshot, WorldModelSnapshot)
        assert snapshot.company_id == 1

    def test_get_slice_sections_resilient_to_errors(self):
        """Individual section failures should not crash the whole snapshot."""
        svc = WorldModelService(db=MagicMock())
        snapshot = svc.get_slice(company_id=1, sections=["fleet", "financial"])
        assert snapshot.fleet is not None
        assert snapshot.financial is not None

    @patch("backend.copilot.world_model.WorldModelService._build_fleet_summary")
    def test_get_slice_calls_section_builder(self, mock_builder):
        """Requested sections should call the appropriate builder."""
        mock_builder.return_value = FleetSummary(total_vehicles=5)
        svc = WorldModelService(db=MagicMock())
        snapshot = svc.get_slice(company_id=1, sections=["fleet"])
        assert mock_builder.called
        assert snapshot.fleet.total_vehicles == 5
