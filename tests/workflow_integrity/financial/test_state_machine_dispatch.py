"""Dispatch state machine: resource assignment lifecycle.

The dispatch service manages assignment of trucks and drivers to trips.
While the underlying trip status follows its own state machine, the
*dispatch* state tracks resource allocation:

  - **Not Dispatched**: trip created, no truck/driver assigned
  - **Truck Assigned**: truck linked to trip (driver may be unassigned)
  - **Driver Assigned**: driver linked to trip (truck may be unassigned)
  - **Fully Dispatched**: both truck and driver assigned
  - **Dispatched → In Transit**: trip progresses via status transitions

Dispatch also offers transition_status as a semantic alias for trip
status changes, and semantic aliases cancel_trip / complete_trip.
"""

from __future__ import annotations

import pytest

from services.dispatch_service.dispatch_service import DispatchService

pytestmark = pytest.mark.state_machine


class TestDispatchAssignmentStates:
    """Resource assignment lifecycle: unassigned → assigned truck/driver → both."""

    def test_not_dispatched_initially(self, db, workflow_env):
        """A freshly created trip has no truck or driver assigned."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        trip = workflow_env.get_trip(trip_id)
        assert trip is not None
        truck_id = trip.get("truck_id")
        driver_id = trip.get("driver_id")
        assert truck_id is None or truck_id == 0, (
            f"Expected no truck, got {truck_id}"
        )
        assert driver_id is None or driver_id == 0, (
            f"Expected no driver, got {driver_id}"
        )

    def test_assign_truck(self, dispatch_service, workflow_env, db):
        """Assigning a truck transitions dispatch to Truck-Assigned state."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        truck_id = ids["truck_ids"][0]

        result = dispatch_service.assign_truck(trip_id, truck_id)
        assert result.success is True, f"assign_truck failed: {result.message}"

        trip = workflow_env.get_trip(trip_id)
        assert trip is not None
        assert trip.get("truck_id") == truck_id

    def test_assign_driver(self, dispatch_service, workflow_env, db):
        """Assigning a driver transitions dispatch to Driver-Assigned state."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        driver_id = ids["driver_ids"][0]

        result = dispatch_service.assign_driver(trip_id, driver_id)
        assert result.success is True, f"assign_driver failed: {result.message}"

        trip = workflow_env.get_trip(trip_id)
        assert trip is not None
        assert trip.get("driver_id") == driver_id

    def test_assign_both(self, dispatch_service, workflow_env, db):
        """Assigning both truck and driver transitions to Fully Dispatched."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )
        truck_id = ids["truck_ids"][0]
        driver_id = ids["driver_ids"][0]

        result = dispatch_service.assign_both(trip_id, truck_id, driver_id)
        assert result.success is True, f"assign_both failed: {result.message}"

        trip = workflow_env.get_trip(trip_id)
        assert trip is not None
        assert trip.get("truck_id") == truck_id, "Truck not assigned"
        assert trip.get("driver_id") == driver_id, "Driver not assigned"

    def test_assign_truck_to_nonexistent_trip_fails(self, dispatch_service, db):
        """assign_truck on a non-existent trip must raise or return failure."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        truck_id = ids["truck_ids"][0]

        with pytest.raises(Exception):
            dispatch_service.assign_truck(999_999, truck_id)

    def test_assign_nonexistent_truck_fails(self, dispatch_service, workflow_env, db):
        """assign_truck with a non-existent truck must raise or return failure."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )

        with pytest.raises(Exception):
            dispatch_service.assign_truck(trip_id, 999_999)


class TestDispatchStatusTransitions:
    """Dispatch service delegates to trip status machinery via transition_status."""

    def test_transition_status_via_dispatch(self, dispatch_service, workflow_env, db):
        """DispatchService.transition_status must forward to ops engine."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )

        result = dispatch_service.transition_status(trip_id, "Loading")
        assert result.success is True, (
            f"dispatch transition_status failed: {result.message}"
        )
        trip = workflow_env.get_trip(trip_id)
        assert trip["status"] == "Loading"

    def test_cancel_trip_alias(self, dispatch_service, workflow_env, db):
        """DispatchService.cancel_trip is an alias for transition to Cancelled."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )

        result = dispatch_service.cancel_trip(trip_id, reason="Test cancellation")
        assert result.success is True
        trip = workflow_env.get_trip(trip_id)
        assert trip["status"] == "Cancelled"

    def test_complete_trip_alias(self, dispatch_service, workflow_env, db):
        """DispatchService.complete_trip is an alias for transition to Delivered."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="In Transit",
        )

        result = dispatch_service.complete_trip(trip_id)
        assert result.success is True
        trip = workflow_env.get_trip(trip_id)
        assert trip["status"] == "Delivered"

    def test_invalid_transition_via_dispatch_raises(self, dispatch_service, workflow_env, db):
        """DispatchService.transition_status raises on illegal transitions."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)
        trip_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0],
            status="Planned",
        )

        with pytest.raises(Exception):
            dispatch_service.transition_status(trip_id, "Paid")


class TestDispatchBoardStates:
    """Dispatch board correctly groups trips by their column/status."""

    def test_dispatch_board_columns(self, dispatch_service, workflow_env, db):
        """get_dispatch_board_data returns trips grouped by column."""
        from tests.workflow_integrity.personas import build_ana_persona

        ids = build_ana_persona(db)

        # Create trips in various statuses
        planned_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0], status="Planned"
        )
        loading_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0], status="Loading"
        )
        transit_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0], status="In Transit"
        )
        delivered_id = workflow_env.create_trip(
            client_id=ids["client_ids"][0], status="Delivered"
        )

        board = dispatch_service.get_dispatch_board_data()
        assert board is not None

        # Each column should contain at least the trip we created
        column_ids = {}
        for col_name, trips in board.column_trips.items():
            column_ids[col_name] = {t["trip_id_num"] for t in trips}

        assert planned_id in column_ids.get("Planned", set()), (
            f"Planned trip {planned_id} not in board's Planned column"
        )
        assert loading_id in column_ids.get("Loading", set()), (
            f"Loading trip {loading_id} not in board's Loading column"
        )
        assert transit_id in column_ids.get("In Transit", set()), (
            f"In Transit trip {transit_id} not in board's In Transit column"
        )
        assert delivered_id in column_ids.get("Delivered", set()), (
            f"Delivered trip {delivered_id} not in board's Delivered column"
        )
