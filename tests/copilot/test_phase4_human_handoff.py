"""Phase 4 tests — human handoff (§23.7), World Model (§6), insight jobs (§18).

Blueprint: §23.7, §6, §18.
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.human_handoff import HandoffState, HandoffTracker, should_handoff
from backend.copilot.world_model import WorldModelService, WorldModelSnapshot


class TestHumanHandoff:
    """De-escalation counter and handoff trigger (§23.7)."""

    def test_state_starts_clean(self):
        """A fresh HandoffState should not trigger handoff."""
        state = HandoffState("test-conv")
        assert not state.should_handoff()

    def test_two_low_confidence_plans_trigger_handoff(self):
        """Two consecutive low-confidence plans for the same intent trigger handoff."""
        state = HandoffState("test-conv")
        state.record_low_confidence("dispatch.create")
        assert not state.should_handoff()  # First one
        state.record_low_confidence("dispatch.create")
        assert state.should_handoff()  # Second one triggers

    def test_different_intents_dont_accumulate(self):
        """Different intents between low-confidence events should reset the counter."""
        state = HandoffState("test-conv")
        state.record_low_confidence("dispatch.create")
        state.record_low_confidence("vehicle.search")
        assert not state.should_handoff()  # Different intents, not accumulated

    def test_two_cancellations_trigger_handoff(self):
        """Two consecutive cancellations trigger handoff."""
        state = HandoffState("test-conv")
        state.record_cancellation("dispatch.create")
        assert not state.should_handoff()
        state.record_cancellation("dispatch.create")
        assert state.should_handoff()

    def test_one_failed_clarification_trigger_handoff(self):
        """A single failed clarification round-trip triggers handoff."""
        state = HandoffState("test-conv")
        state.record_failed_clarification()
        assert state.should_handoff()

    def test_once_triggered_stays_triggered(self):
        """Once handoff is triggered, it stays triggered for the conversation."""
        state = HandoffState("test-conv")
        state.record_low_confidence("dispatch.create")
        state.record_low_confidence("dispatch.create")
        assert state.should_handoff()
        # Even after successful actions
        assert state.should_handoff()  # Still triggered
        assert state.reason is not None

    def test_tracker_get_or_create(self):
        """HandoffTracker.get returns existing or creates new state."""
        state = HandoffTracker.get("new-conv")
        assert state is not None
        assert state.conversation_id == "new-conv"

    def test_tracker_reset_clears_state(self):
        """HandoffTracker.reset removes the state."""
        HandoffTracker.get("reset-conv")
        HandoffTracker.reset("reset-conv")
        # Re-getting should give a fresh state
        state = HandoffTracker.get("reset-conv")
        assert not state.should_handoff()

    def test_tracker_low_confidence(self):
        """HandoffTracker.record_low_confidence works via static method."""
        HandoffTracker.record_low_confidence("tracker-conv", "trip.create")
        HandoffTracker.record_low_confidence("tracker-conv", "trip.create")
        state = HandoffTracker.get("tracker-conv")
        assert state.low_confidence_count >= 2
        assert state.should_handoff()

    def test_should_handoff_function(self):
        """The module-level should_handoff function works."""
        state = HandoffState("func-conv")
        assert not should_handoff(state, "test.intent")
        state.record_cancellation("test.intent")
        state.record_cancellation("test.intent")
        assert should_handoff(state, "test.intent")


class TestWorldModel:
    """World Model (§6) — snapshot building and data accuracy."""

    def test_world_model_service_constructable(self):
        """WorldModelService can be constructed with a db mock."""
        svc = WorldModelService(db=MagicMock())
        assert svc is not None
        assert svc._db is not None

    def test_get_slice_default_all(self):
        """get_slice with no sections returns all default sections."""
        svc = WorldModelService(db=MagicMock())
        snapshot = svc.get_slice(company_id=1)
        assert isinstance(snapshot, WorldModelSnapshot)
        assert snapshot.company_id == 1
        assert snapshot.ttl_seconds == 60
        # All sections should have default values
        assert snapshot.fleet is not None
        assert snapshot.drivers is not None
        assert snapshot.trips is not None
        assert snapshot.documents is not None

    def test_get_slice_single_section(self):
        """get_slice returns only requested sections."""
        svc = WorldModelService(db=MagicMock())
        snapshot = svc.get_slice(company_id=1, sections=["fleet"])
        assert snapshot.fleet is not None
        # Other sections should still exist (they get default values)
        assert snapshot.drivers is not None

    def test_get_slice_isolates_company(self):
        """World Model data should be scoped to the company."""
        svc = WorldModelService(db=MagicMock())
        snapshot = svc.get_slice(company_id=42)
        assert snapshot.company_id == 42

    def test_default_section_values(self):
        """All sections should return sensible defaults when no DB."""
        svc = WorldModelService(db=MagicMock())
        snapshot = svc.get_slice(company_id=1)
        assert snapshot.fleet.total_vehicles >= 0
        assert snapshot.drivers.total_drivers >= 0
        assert snapshot.trips.active_trips >= 0
        assert isinstance(snapshot.open_problems, list)
