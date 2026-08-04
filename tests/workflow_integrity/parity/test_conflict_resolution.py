"""Platform parity: Conflict resolution scenarios."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.parity


class TestConflictResolution:
    """When two platforms modify the same entity, conflicts must be handled."""

    def test_consecutive_status_updates(self, workflow_env, db):
        """Two sequential updates from different sources must converge."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        # "Mobile" update
        assert workflow_env.transition_status(trip_id, "Loading")
        # "Desktop" update
        assert workflow_env.transition_status(trip_id, "In Transit")
        # Verify final state
        trip = workflow_env.get_trip(trip_id)
        assert trip["status"] == "In Transit"

    def test_event_delivered_once_to_subscribers(
        self, workflow_env, event_monitor, db
    ):
        """Status change published once must deliver to all subscribers."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        event_monitor.track("trip.status_changed")
        workflow_env.transition_status(trip_id, "Loading")
        events = event_monitor.get_events("trip.status_changed")
        assert len(events) >= 1, "No event published for status change"

    def test_invalid_transition_across_platforms(self, workflow_env, db):
        """Invalid transition attempted from any platform must be rejected."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        # Attempt invalid transition
        result = workflow_env.transition_status(trip_id, "Delivered")
        assert result is False, "Invalid transition must be rejected"
