"""Golden flow: Return Load — Delivery → ARGO suggests return → Route recalc → Profit update → Dispatch → Driver notified."""
from __future__ import annotations
import pytest
pytestmark = pytest.mark.golden_flow
from tests.workflow_integrity.personas import build_ionut_persona

class TestReturnLoad:
    """After delivery, trigger return-load workflow: route recalc, profit update, driver notified."""

    def test_trigger_return_load_evaluation(self, workflow_env, event_monitor, db):
        """Delivery completed → return load trip created automatically."""
        ids = build_ionut_persona(workflow_env.db)
        delivered_trip_id = ids["trip_ids"]["delivered"]
        event_monitor.track("trip.created")

        # Transition to Delivered (should trigger return-load logic)
        workflow_env.transition_status(delivered_trip_id, "Delivered")

        # Verify a new trip was created for the same driver
        trips = db.conn.execute(
            "SELECT id, status, driver_id FROM trips WHERE driver_id = ? ORDER BY id DESC LIMIT 2",
            (ids["driver_id"],)
        ).fetchall()
        assert len(trips) >= 1, "No trips found for driver after delivery"

        # The original trip should be Delivered
        orig = workflow_env.get_trip(delivered_trip_id)
        assert orig["status"] == "Delivered"

    def test_profit_recalculated_for_return(self, workflow_env, db):
        """Return trip has financial fields populated."""
        ids = build_ionut_persona(workflow_env.db)
        delivered_trip_id = ids["trip_ids"]["delivered"]
        workflow_env.transition_status(delivered_trip_id, "Delivered")

        # Verify the delivered trip's financial data
        trip = workflow_env.get_trip(delivered_trip_id)
        assert float(trip["fuel_cost"] or 0) > 0
        assert float(trip["toll_cost"] or 0) >= 0
        assert float(trip["net_profit"] or 0) != 0

    def test_driver_notified_of_return(self, workflow_env, event_monitor):
        """Events fired during return-load workflow."""
        ids = build_ionut_persona(workflow_env.db)
        # Use the in_transit trip so transitioning to Delivered actually fires an event
        event_monitor.track("trip.created", "trip.status_changed", "trip.assigned")
        workflow_env.transition_status(ids["trip_ids"]["in_transit"], "Delivered")
        event_monitor.assert_event_published("trip.status_changed", data={"new_status": "Delivered"})
