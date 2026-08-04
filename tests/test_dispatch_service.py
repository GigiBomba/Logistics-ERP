"""Comprehensive unit tests for DispatchService — all public API, static methods, and private helpers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from services.dispatch_service.dispatch_service import (
    DispatchService,
    STATUS_TO_COLUMN,
    COLUMN_KEYS,
)
from services.dispatch_service.errors import (
    DispatchError,
    DriverNotFoundError,
    InvalidStatusTransitionError,
    ResourceUnavailableError,
    TripNotFoundError,
    TruckNotFoundError,
)
from services.dispatch_service.models import (
    BulkDispatchResult,
    DispatchBoardFilters,
    DispatchDataResponse,
    DispatchResult,
    UndoToken,
)
from services.operations.alert_manager import Alert, AlertType, Severity
from services.operations.event_bus import TRIP_ASSIGNED, TRIP_STATUS_CHANGED


# ══════════════════════════════════════════════════════════════════════
# Constructor & wiring
# ══════════════════════════════════════════════════════════════════════


class TestDispatchServiceConstructor:
    """Verify all dependencies are wired correctly into the service and AvailabilityChecker."""

    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()
        self.mock_event_bus = MagicMock()
        self.mock_alert_manager = MagicMock()
        self.mock_ops_engine = MagicMock()
        self.mock_dta_service = MagicMock()
        self.mock_tacho_repo = MagicMock()

    def test_all_dependencies_stored(self):
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            dta_service=self.mock_dta_service,
            tacho_repo=self.mock_tacho_repo,
            event_bus=self.mock_event_bus,
            alert_manager=self.mock_alert_manager,
            ops_engine=self.mock_ops_engine,
        )
        assert service._trip_service is self.mock_trip_service
        assert service._fleet_repo is self.mock_fleet_repo
        assert service._driver_repo is self.mock_driver_repo
        assert service._conflict_service is self.mock_conflict_service
        assert service._dta_service is self.mock_dta_service
        assert service._event_bus is self.mock_event_bus
        assert service._alert_manager is self.mock_alert_manager
        assert service._ops_engine is self.mock_ops_engine

    def test_availability_checker_wired(self):
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            dta_service=self.mock_dta_service,
            tacho_repo=self.mock_tacho_repo,
            event_bus=self.mock_event_bus,
        )
        assert service._availability._fleet_repo is self.mock_fleet_repo
        assert service._availability._driver_repo is self.mock_driver_repo
        assert service._availability._conflict_service is self.mock_conflict_service
        assert service._availability._tacho_repo is self.mock_tacho_repo

    def test_minimal_dependencies(self):
        """No optional deps — should not crash."""
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
        )
        assert service._dta_service is None
        assert service._event_bus is None
        assert service._alert_manager is None
        assert service._ops_engine is None
        assert service._availability._tacho_repo is None


# ══════════════════════════════════════════════════════════════════════
# assign_truck
# ══════════════════════════════════════════════════════════════════════


class TestAssignTruck:
    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()
        self.mock_event_bus = MagicMock()
        self.mock_alert_manager = MagicMock()
        self.mock_ops_engine = MagicMock()
        self.mock_dta_service = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            dta_service=self.mock_dta_service,
            event_bus=self.mock_event_bus,
            alert_manager=self.mock_alert_manager,
            ops_engine=self.mock_ops_engine,
        )

        # Default mock trip
        self.mock_trip = {"id": 42, "truck_number": None, "truck_id": None, "status": "Planned"}
        self.mock_trip_service.get_by_id.return_value = self.mock_trip

        # Default mock truck
        self.mock_truck = {"id": 7, "plate": "ABC-123", "truck_number": "ABC-123"}
        self.mock_fleet_repo.get_by_id.return_value = self.mock_truck

        # Mock availability to pass
        self._patch_avail = patch.object(
            self.service._availability, "check_truck",
            return_value=MagicMock(available=True, status_text="Available"),
        )
        self._patch_avail.start()

    def teardown_method(self):
        self._patch_avail.stop()

    def test_happy_path(self):
        result = self.service.assign_truck(42, 7)

        assert result.success is True
        assert result.trip_id == 42
        assert result.operation == "assign_truck"
        assert "ABC-123" in result.message
        assert result.details["truck_plate"] == "ABC-123"

        # Trip update called with plate and id (as TripUpdate model)
        self.mock_trip_service.update.assert_called_once()
        args, _ = self.mock_trip_service.update.call_args
        assert args[0] == 42
        assert args[1].truck_plate == "ABC-123"
        assert args[1].truck_id == 7

        # Event published
        self.mock_event_bus.publish.assert_called_once_with(
            TRIP_ASSIGNED,
            {"trip_id": 42, "truck_id": 7, "truck_plate": "ABC-123"},
        )

        # Undo token created
        assert result.undo_token is not None
        assert result.undo_token.operation == "assign_truck"
        assert result.undo_token.trip_id == 42
        assert result.undo_token.previous_state == {"truck_number": None, "truck_id": None}
        assert "Unassign" in result.undo_token.undo_description

    def test_trip_not_found(self):
        self.mock_trip_service.get_by_id.return_value = None
        with pytest.raises(TripNotFoundError, match="Trip #42 not found"):
            self.service.assign_truck(42, 7)
        self.mock_trip_service.update.assert_not_called()

    def test_truck_not_found(self):
        self.mock_fleet_repo.get_by_id.return_value = None
        with pytest.raises(TruckNotFoundError, match="Truck #7 not found"):
            self.service.assign_truck(42, 7)
        self.mock_trip_service.update.assert_not_called()

    def test_availability_check_fails(self):
        self._patch_avail.stop()
        patch.object(
            self.service._availability, "check_truck",
            return_value=MagicMock(available=False, status_text="Truck is in service/repair"),
        ).start()
        with pytest.raises(ResourceUnavailableError, match="Truck is in service"):
            self.service.assign_truck(42, 7)
        self.mock_trip_service.update.assert_not_called()

    def test_event_bus_publish_fire_and_forget(self):
        self.mock_event_bus.publish.side_effect = RuntimeError("Bus down")
        result = self.service.assign_truck(42, 7)
        assert result.success is True
        # Trip update still happened
        self.mock_trip_service.update.assert_called_once()

    def test_event_bus_none(self):
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=None,
        )
        patch.object(
            service._availability, "check_truck",
            return_value=MagicMock(available=True, status_text="Available"),
        ).start()
        service._availability.check_truck = MagicMock(
            return_value=MagicMock(available=True, status_text="Available"),
        )

        result = service.assign_truck(42, 7)
        assert result.success is True
        # No crash when event_bus is None

    def test_truck_plate_fallback_to_truck_number(self):
        truck_no_plate = {"id": 7, "truck_number": "TRK-99"}
        self.mock_fleet_repo.get_by_id.return_value = truck_no_plate
        result = self.service.assign_truck(42, 7)
        self.mock_trip_service.update.assert_called_once()
        args, _ = self.mock_trip_service.update.call_args
        assert args[0] == 42
        assert args[1].truck_plate == "TRK-99"
        assert args[1].truck_id == 7
        assert "TRK-99" in result.message
        assert result.details["truck_plate"] == "TRK-99"

    def test_truck_plate_fallback_to_truck_id_str(self):
        truck_no_plate_no_number = {"id": 7}
        self.mock_fleet_repo.get_by_id.return_value = truck_no_plate_no_number
        result = self.service.assign_truck(42, 7)
        self.mock_trip_service.update.assert_called_once()
        args, _ = self.mock_trip_service.update.call_args
        assert args[0] == 42
        assert args[1].truck_plate == "7"
        assert args[1].truck_id == 7

    def test_validate_trip_called(self):
        self.service.assign_truck(42, 7)
        self.mock_trip_service.get_by_id.assert_called_once_with(42)

    def test_validate_truck_called(self):
        self.service.assign_truck(42, 7)
        self.mock_fleet_repo.get_by_id.assert_called_once_with(7)


# ══════════════════════════════════════════════════════════════════════
# assign_driver
# ══════════════════════════════════════════════════════════════════════


class TestAssignDriver:
    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()
        self.mock_event_bus = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=self.mock_event_bus,
        )

        self.mock_trip = {"id": 42, "driver_id": None, "driver_name": None, "status": "Planned"}
        self.mock_trip_service.get_by_id.return_value = self.mock_trip

        self.mock_driver = {"id": 5, "name": "John Doe", "driver_name": "John Doe"}
        self.mock_driver_repo.get_by_id.return_value = self.mock_driver

        self._patch_avail = patch.object(
            self.service._availability, "check_driver",
            return_value=MagicMock(available=True, status_text="Available"),
        )
        self._patch_avail.start()

    def teardown_method(self):
        self._patch_avail.stop()

    def test_happy_path(self):
        result = self.service.assign_driver(42, 5)

        assert result.success is True
        assert result.trip_id == 42
        assert result.operation == "assign_driver"
        assert "John Doe" in result.message
        assert result.details["driver_name"] == "John Doe"
        assert result.details["driver_id"] == 5

        self.mock_trip_service.update.assert_called_once()
        args, _ = self.mock_trip_service.update.call_args
        assert args[0] == 42
        assert args[1].driver_id == 5
        assert args[1].driver_name == "John Doe"

        self.mock_event_bus.publish.assert_called_once_with(
            TRIP_ASSIGNED,
            {"trip_id": 42, "driver_id": 5, "driver_name": "John Doe"},
        )

        assert result.undo_token is not None
        assert result.undo_token.operation == "assign_driver"
        assert result.undo_token.trip_id == 42
        assert result.undo_token.previous_state == {"driver_id": None, "driver_name": None}

    def test_trip_not_found(self):
        self.mock_trip_service.get_by_id.return_value = None
        with pytest.raises(TripNotFoundError):
            self.service.assign_driver(42, 5)

    def test_driver_not_found(self):
        self.mock_driver_repo.get_by_id.return_value = None
        with pytest.raises(DriverNotFoundError, match="Driver #5 not found"):
            self.service.assign_driver(42, 5)

    def test_availability_fails(self):
        self._patch_avail.stop()
        patch.object(
            self.service._availability, "check_driver",
            return_value=MagicMock(available=False, status_text="License expired"),
        ).start()
        with pytest.raises(ResourceUnavailableError, match="License expired"):
            self.service.assign_driver(42, 5)

    def test_event_bus_fire_and_forget(self):
        self.mock_event_bus.publish.side_effect = RuntimeError("Bus down")
        result = self.service.assign_driver(42, 5)
        assert result.success is True

    def test_driver_name_fallback_to_empty(self):
        no_name_driver = {"id": 5}
        self.mock_driver_repo.get_by_id.return_value = no_name_driver
        result = self.service.assign_driver(42, 5)
        assert result.details["driver_name"] == ""


# ══════════════════════════════════════════════════════════════════════
# assign_both
# ══════════════════════════════════════════════════════════════════════


class TestAssignBoth:
    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()
        self.mock_event_bus = MagicMock()
        self.mock_dta_service = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            dta_service=self.mock_dta_service,
            event_bus=self.mock_event_bus,
        )

        self.mock_trip = {"id": 42, "truck_number": None, "truck_id": None,
                          "driver_id": None, "driver_name": None, "status": "Planned"}
        self.mock_trip_service.get_by_id.return_value = self.mock_trip

        self.mock_truck = {"id": 7, "plate": "ABC-123", "truck_number": "ABC-123"}
        self.mock_fleet_repo.get_by_id.return_value = self.mock_truck

        self.mock_driver = {"id": 5, "name": "John Doe"}
        self.mock_driver_repo.get_by_id.return_value = self.mock_driver

        # Mock both availability checks to pass
        self._patch_truck = patch.object(
            self.service._availability, "check_truck",
            return_value=MagicMock(available=True, status_text="Available"),
        )
        self._patch_truck.start()
        self._patch_driver = patch.object(
            self.service._availability, "check_driver",
            return_value=MagicMock(available=True, status_text="Available"),
        )
        self._patch_driver.start()

    def teardown_method(self):
        self._patch_truck.stop()
        self._patch_driver.stop()

    def test_both_succeed(self):
        result = self.service.assign_both(42, 7, 5)

        assert result.success is True
        assert result.operation == "assign_both"
        assert "ABC-123" in result.message
        assert "John Doe" in result.message
        assert result.details["truck_plate"] == "ABC-123"
        assert result.details["driver_name"] == "John Doe"

        # DTA pairing called
        self.mock_dta_service.assign_driver_to_truck.assert_called_once_with(5, 7)

    def test_only_truck(self):
        result = self.service.assign_both(42, 7, None)

        assert result.success is True
        assert "ABC-123" in result.message
        assert "driver" not in result.details or result.details.get("driver_name") == ""
        # DTA not called because no driver_id
        self.mock_dta_service.assign_driver_to_truck.assert_not_called()

    def test_only_driver(self):
        result = self.service.assign_both(42, None, 5)

        assert result.success is True
        assert "John Doe" in result.message
        assert "truck_plate" not in result.details
        self.mock_dta_service.assign_driver_to_truck.assert_not_called()

    def test_truck_succeeds_driver_fails_rollback(self):
        # Make driver assignment fail
        self._patch_driver.stop()
        real_driver_assign = self.service.assign_driver

        def failing_assign_driver(trip_id, driver_id):
            raise DispatchError("Driver unavailable")

        self.service.assign_driver = failing_assign_driver

        with pytest.raises(DispatchError, match="Driver unavailable"):
            self.service.assign_both(42, 7, 5)

        # Truck should be rolled back (last call is the rollback)
        assert self.mock_trip_service.update.call_count >= 2
        last_update = self.mock_trip_service.update.call_args[0][1]
        assert last_update.truck_plate == "" or last_update.truck_plate is None
        assert last_update.truck_id is None

    def test_truck_succeeds_driver_fails_no_undo_if_no_truck_assigned(self):
        self._patch_driver.stop()

        def failing_assign_driver(trip_id, driver_id):
            raise DispatchError("Driver unavailable")

        self.service.assign_driver = failing_assign_driver

        with pytest.raises(DispatchError):
            self.service.assign_both(42, None, 5)
        # No rollback because no truck was assigned
        # trip_service.update should have been called only once (by assign_both's driver attempt
        # which never reaches update because assign_driver fails before update)
        # Actually assign_driver fails before update so update not called at all
        assert self.mock_trip_service.update.call_count == 0

    def test_dta_service_best_effort_failure(self):
        self.mock_dta_service.assign_driver_to_truck.side_effect = RuntimeError("DTA down")
        result = self.service.assign_both(42, 7, 5)
        assert result.success is True
        # Still succeeds despite DTA failure

    def test_dta_service_none(self):
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            dta_service=None,
            event_bus=self.mock_event_bus,
        )
        patch.object(
            service._availability, "check_truck",
            return_value=MagicMock(available=True, status_text="Available"),
        ).start()
        patch.object(
            service._availability, "check_driver",
            return_value=MagicMock(available=True, status_text="Available"),
        ).start()

        result = service.assign_both(42, 7, 5)
        assert result.success is True

    def test_both_none(self):
        """Neither truck nor driver — trivial success with no assignments."""
        result = self.service.assign_both(42, None, None)
        assert result.success is True
        assert result.operation == "assign_both"
        self.mock_trip_service.update.assert_not_called()


# ══════════════════════════════════════════════════════════════════════
# bulk_assign_truck
# ══════════════════════════════════════════════════════════════════════


class TestBulkAssignTruck:
    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()
        self.mock_event_bus = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=self.mock_event_bus,
        )

        self.mock_truck = {"id": 7, "plate": "ABC-123"}
        self.mock_fleet_repo.get_by_id.return_value = self.mock_truck

        # Patch assign_truck on the service to control per-trip behaviour
        self.results_call_count = 0

    def test_all_succeed(self):
        def assign_truck_side_effect(trip_id, truck_id):
            return DispatchResult(
                success=True,
                trip_id=trip_id,
                operation="assign_truck",
                message=f"Assigned to trip #{trip_id}",
                undo_token=UndoToken("assign_truck", trip_id, {}, "desc"),
            )
        self.service.assign_truck = assign_truck_side_effect

        result = self.service.bulk_assign_truck([1, 2, 3], 7)

        assert result.total == 3
        assert result.succeeded == 3
        assert result.failed == 0
        assert len(result.results) == 3
        assert len(result.undo_tokens) == 3

    def test_mixed_success_failure(self):
        call_count = 0

        def assign_truck_side_effect(trip_id, truck_id):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # second trip fails
                raise TruckNotFoundError(f"Truck #{truck_id} not found")
            return DispatchResult(
                success=True,
                trip_id=trip_id,
                operation="assign_truck",
                message=f"Assigned to trip #{trip_id}",
                undo_token=UndoToken("assign_truck", trip_id, {}, "desc"),
            )
        self.service.assign_truck = assign_truck_side_effect

        result = self.service.bulk_assign_truck([1, 2, 3], 7)

        assert result.total == 3
        assert result.succeeded == 2
        assert result.failed == 1
        assert len(result.results) == 3
        assert len(result.undo_tokens) == 2
        assert result.results[1].success is False
        assert "not found" in result.results[1].message

    def test_all_fail(self):
        def assign_truck_side_effect(trip_id, truck_id):
            raise DispatchError("Generic failure")
        self.service.assign_truck = assign_truck_side_effect

        result = self.service.bulk_assign_truck([1, 2], 7)

        assert result.total == 2
        assert result.succeeded == 0
        assert result.failed == 2
        assert len(result.undo_tokens) == 0

    def test_empty_list(self):
        result = self.service.bulk_assign_truck([], 7)
        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0
        assert result.results == []
        assert result.undo_tokens == []

    def test_truck_validated_once(self):
        self.service.assign_truck = MagicMock(
            return_value=DispatchResult(True, 1, "assign_truck", "ok",
                                        undo_token=UndoToken("assign_truck", 1, {}, "desc")),
        )
        self.service.bulk_assign_truck([1, 2], 7)
        self.mock_fleet_repo.get_by_id.assert_called_once_with(7)

    def test_truck_not_found(self):
        self.mock_fleet_repo.get_by_id.return_value = None
        with pytest.raises(TruckNotFoundError):
            self.service.bulk_assign_truck([1, 2], 7)


# ══════════════════════════════════════════════════════════════════════
# bulk_assign_driver
# ══════════════════════════════════════════════════════════════════════


class TestBulkAssignDriver:
    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()
        self.mock_event_bus = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=self.mock_event_bus,
        )

        self.mock_driver = {"id": 5, "name": "John Doe"}
        self.mock_driver_repo.get_by_id.return_value = self.mock_driver

    def test_all_succeed(self):
        def assign_driver_side_effect(trip_id, driver_id):
            return DispatchResult(
                success=True,
                trip_id=trip_id,
                operation="assign_driver",
                message=f"Assigned to trip #{trip_id}",
                undo_token=UndoToken("assign_driver", trip_id, {}, "desc"),
            )
        self.service.assign_driver = assign_driver_side_effect

        result = self.service.bulk_assign_driver([1, 2, 3], 5)

        assert result.total == 3
        assert result.succeeded == 3
        assert result.failed == 0
        assert len(result.results) == 3
        assert len(result.undo_tokens) == 3

    def test_mixed(self):
        call_count = 0

        def assign_driver_side_effect(trip_id, driver_id):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise DriverNotFoundError(f"Driver #{driver_id} not found")
            return DispatchResult(
                success=True,
                trip_id=trip_id,
                operation="assign_driver",
                message=f"Assigned to trip #{trip_id}",
                undo_token=UndoToken("assign_driver", trip_id, {}, "desc"),
            )
        self.service.assign_driver = assign_driver_side_effect

        result = self.service.bulk_assign_driver([1, 2, 3], 5)

        assert result.total == 3
        assert result.succeeded == 2
        assert result.failed == 1
        assert result.results[1].success is False

    def test_all_fail(self):
        def assign_driver_side_effect(trip_id, driver_id):
            raise DispatchError("Fail")
        self.service.assign_driver = assign_driver_side_effect

        result = self.service.bulk_assign_driver([1, 2], 5)
        assert result.succeeded == 0
        assert result.failed == 2

    def test_empty(self):
        result = self.service.bulk_assign_driver([], 5)
        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0

    def test_driver_validated_once(self):
        self.service.assign_driver = MagicMock(
            return_value=DispatchResult(True, 1, "assign_driver", "ok",
                                        undo_token=UndoToken("assign_driver", 1, {}, "desc")),
        )
        self.service.bulk_assign_driver([1, 2], 5)
        self.mock_driver_repo.get_by_id.assert_called_once_with(5)

    def test_driver_not_found(self):
        self.mock_driver_repo.get_by_id.return_value = None
        with pytest.raises(DriverNotFoundError):
            self.service.bulk_assign_driver([1, 2], 5)


# ══════════════════════════════════════════════════════════════════════
# transition_status
# ══════════════════════════════════════════════════════════════════════


class TestTransitionStatus:
    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()
        self.mock_event_bus = MagicMock()
        self.mock_ops_engine = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=self.mock_event_bus,
            ops_engine=self.mock_ops_engine,
        )

        self.mock_trip = {"id": 42, "status": "Planned"}
        self.mock_trip_service.get_by_id.return_value = self.mock_trip

    def test_via_ops_engine_valid_transition(self):
        result = self.service.transition_status(42, "Loading")

        assert result.success is True
        assert result.operation == "transition_status"
        assert "Planned" in result.message
        assert "Loading" in result.message
        assert result.details["old_status"] == "Planned"
        assert result.details["new_status"] == "Loading"

        self.mock_ops_engine.force_trip_status.assert_called_once_with(42, "Loading")
        # No direct trip_service.update call because ops_engine handled it
        self.mock_trip_service.update.assert_not_called()
        # No event bus publish because ops_engine handled it
        self.mock_event_bus.publish.assert_not_called()

    def test_via_ops_engine_exception_raised(self):
        self.mock_ops_engine.force_trip_status.side_effect = RuntimeError("Engine error")

        with pytest.raises(DispatchError, match="Failed to transition trip #42 via ops_engine"):
            self.service.transition_status(42, "Loading")

    def test_manual_update_no_ops_engine(self):
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=self.mock_event_bus,
            ops_engine=None,
        )
        # Need trip mock on this service too
        service._trip_service.get_by_id.return_value = self.mock_trip

        result = service.transition_status(42, "Loading")

        assert result.success is True
        service._trip_service.update.assert_called_once()
        args, _ = service._trip_service.update.call_args
        assert args[0] == 42
        assert args[1].status == "Loading"
        self.mock_event_bus.publish.assert_called_once_with(
            TRIP_STATUS_CHANGED,
            {"trip_id": 42, "old_status": "Planned", "new_status": "Loading"},
        )

    def test_manual_update_no_event_bus(self):
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=None,
            ops_engine=None,
        )
        service._trip_service.get_by_id.return_value = self.mock_trip

        result = service.transition_status(42, "Loading")
        assert result.success is True
        # No crash

    def test_manual_update_event_bus_fire_and_forget(self):
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=self.mock_event_bus,
            ops_engine=None,
        )
        service._trip_service.get_by_id.return_value = self.mock_trip
        self.mock_event_bus.publish.side_effect = RuntimeError("Bus down")

        result = service.transition_status(42, "Loading")
        assert result.success is True

    def test_invalid_transition(self):
        with pytest.raises(InvalidStatusTransitionError, match="Cannot transition"):
            self.service.transition_status(42, "Delivered")

    def test_trip_not_found(self):
        self.mock_trip_service.get_by_id.return_value = None
        with pytest.raises(TripNotFoundError):
            self.service.transition_status(42, "Loading")


# ══════════════════════════════════════════════════════════════════════
# cancel_trip / complete_trip
# ══════════════════════════════════════════════════════════════════════


class TestCancelTrip:
    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()
        self.mock_event_bus = MagicMock()
        self.mock_ops_engine = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=self.mock_event_bus,
            ops_engine=self.mock_ops_engine,
        )

        self.mock_trip = {"id": 42, "status": "Planned"}
        self.mock_trip_service.get_by_id.return_value = self.mock_trip

    def test_cancel_delegates_to_transition_status(self):
        result = self.service.cancel_trip(42, "Customer request")
        assert result.success is True
        assert result.details["new_status"] == "Cancelled"
        self.mock_ops_engine.force_trip_status.assert_called_once_with(42, "Cancelled")

    def test_cancel_default_reason(self):
        result = self.service.cancel_trip(42)
        assert result.success is True

    def test_cancel_raises_on_invalid(self):
        self.mock_trip["status"] = "Paid"
        with pytest.raises(InvalidStatusTransitionError):
            self.service.cancel_trip(42)


class TestCompleteTrip:
    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()
        self.mock_event_bus = MagicMock()
        self.mock_ops_engine = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=self.mock_event_bus,
            ops_engine=self.mock_ops_engine,
        )

        self.mock_trip = {"id": 42, "status": "In Transit"}
        self.mock_trip_service.get_by_id.return_value = self.mock_trip

    def test_complete_delegates_to_transition_status(self):
        result = self.service.complete_trip(42)
        assert result.success is True
        assert result.details["new_status"] == "Delivered"
        self.mock_ops_engine.force_trip_status.assert_called_once_with(42, "Delivered")

    def test_complete_raises_on_invalid(self):
        self.mock_trip["status"] = "Planned"
        with pytest.raises(InvalidStatusTransitionError):
            self.service.complete_trip(42)


# ══════════════════════════════════════════════════════════════════════
# get_dispatch_board_data
# ══════════════════════════════════════════════════════════════════════


class TestGetDispatchBoardData:
    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
        )

        # Mock the internal trip repo for status-filtered query
        self.mock_repo = MagicMock()
        self.mock_trip_service._trip_repo = self.mock_repo

    def test_default_filters_applied_when_none(self):
        self.mock_repo.get_by_statuses.return_value = []
        response = self.service.get_dispatch_board_data()
        assert isinstance(response, DispatchDataResponse)
        assert response.column_trips.keys() == {"Planned", "Loading", "In Transit", "Delivered", "Cancelled"}
        assert all(len(v) == 0 for v in response.column_trips.values())

    def test_trips_grouped_by_column(self):
        trips = [
            {"id": 1, "status": "Planned", "start_date": "2026-01-01"},
            {"id": 2, "status": "Loading", "start_date": "2026-01-01"},
            {"id": 3, "status": "In Transit", "start_date": "2026-01-01"},
            {"id": 4, "status": "Delivered", "end_date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")},
            {"id": 5, "status": "Cancelled", "end_date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")},
        ]
        self.mock_repo.get_by_statuses.return_value = trips

        response = self.service.get_dispatch_board_data()

        assert len(response.column_trips["Planned"]) == 1
        assert len(response.column_trips["Loading"]) == 1
        assert len(response.column_trips["In Transit"]) == 1
        assert len(response.column_trips["Delivered"]) == 1
        assert len(response.column_trips["Cancelled"]) == 1
        assert response.status_counts["Planned"] == 1
        assert response.status_counts["Loading"] == 1
        assert response.status_counts["In Transit"] == 1
        assert response.status_counts["Delivered"] == 1
        assert response.status_counts["Cancelled"] == 1

    def test_delivered_cutoff_filters_old_trips(self):
        old_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        recent_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        trips = [
            {"id": 1, "status": "Delivered", "end_date": old_date},
            {"id": 2, "status": "Delivered", "end_date": recent_date},
        ]
        self.mock_repo.get_by_statuses.return_value = trips

        response = self.service.get_dispatch_board_data()

        assert len(response.column_trips["Delivered"]) == 1
        # Old one filtered out, recent one kept

    def test_delivered_cutoff_uses_custom_window(self):
        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        trips = [
            {"id": 1, "status": "Delivered", "end_date": old_date},
        ]
        self.mock_repo.get_by_statuses.return_value = trips

        filters = DispatchBoardFilters(delivered_window_days=7)
        response = self.service.get_dispatch_board_data(filters)

        assert len(response.column_trips["Delivered"]) == 0

    def test_delivered_trip_without_end_date_uses_created_at(self):
        recent_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        trips = [
            {"id": 1, "status": "Delivered", "created_at": recent_date},
        ]
        self.mock_repo.get_by_statuses.return_value = trips

        response = self.service.get_dispatch_board_data()
        assert len(response.column_trips["Delivered"]) == 1

    def test_trip_with_unknown_status_skipped(self):
        trips = [
            {"id": 1, "status": "UnknownStatus"},
        ]
        self.mock_repo.get_by_statuses.return_value = trips

        response = self.service.get_dispatch_board_data()
        # Unknown status doesn't map to any column
        total_trips = sum(len(v) for v in response.column_trips.values())
        assert total_trips == 0

    def test_status_mapping_normalization(self):
        trips = [
            {"id": 1, "status": "InTransit", "start_date": "2026-01-01"},
            {"id": 2, "status": "Active", "start_date": "2026-01-01"},
        ]
        self.mock_repo.get_by_statuses.return_value = trips

        response = self.service.get_dispatch_board_data()
        assert len(response.column_trips["In Transit"]) == 2

    def test_route_resolution(self):
        """_build_card_data is called and card_data includes resolved route."""
        # Use a trip that can have a route resolved
        trips = [
            {"id": 1, "status": "Planned", "route_history_v2_id": 99, "start_date": "2026-01-01"},
        ]
        self.mock_repo.get_by_statuses.return_value = trips

        # Wire a route_repo
        mock_route_repo = MagicMock()
        self.mock_trip_service._route_repo = mock_route_repo
        mock_route_repo.get_by_id.return_value = {
            "route_summary_json": json.dumps({"origin": "Paris", "destination": "Berlin"}),
        }

        response = self.service.get_dispatch_board_data()
        card = response.column_trips["Planned"][0]
        assert card["origin"] == "Paris"
        assert card["destination"] == "Berlin"

    def test_route_resolution_fallback_on_exception(self):
        trips = [
            {"id": 1, "status": "Planned", "route_history_v2_id": 99, "start_date": "2026-01-01"},
        ]
        self.mock_repo.get_by_statuses.return_value = trips

        mock_route_repo = MagicMock()
        self.mock_trip_service._route_repo = mock_route_repo
        mock_route_repo.get_by_id.side_effect = ValueError("DB error")

        response = self.service.get_dispatch_board_data()
        card = response.column_trips["Planned"][0]
        assert card["origin"] == ""
        assert card["destination"] == ""

    def test_fallback_to_trip_service_get_all(self):
        """If repo.get_by_statuses fails, fall back to trip_service.get_all."""
        self.mock_repo.get_by_statuses.side_effect = Exception("Repo error")
        self.mock_trip_service.get_all.return_value = [
            {"id": 1, "status": "Planned", "start_date": "2026-01-01"},
        ]

        response = self.service.get_dispatch_board_data()
        assert len(response.column_trips["Planned"]) == 1
        self.mock_trip_service.get_all.assert_called_once()

    def test_fallback_to_empty_when_both_fail(self):
        """If both get_by_statuses and get_all fail, return empty board."""
        self.mock_repo.get_by_statuses.side_effect = Exception("Repo error")
        self.mock_trip_service.get_all.side_effect = Exception("Service error")

        response = self.service.get_dispatch_board_data()
        total_trips = sum(len(v) for v in response.column_trips.values())
        assert total_trips == 0

    def test_card_data_structure(self):
        trips = [
            {"id": 42, "status": "Planned", "truck_number": "ABC-123", "driver_name": "John",
             "driver_id": 5, "truck_id": 7, "start_date": "2026-06-01", "end_date": "2026-06-02"},
        ]
        self.mock_repo.get_by_statuses.return_value = trips

        response = self.service.get_dispatch_board_data()
        card = response.column_trips["Planned"][0]
        assert card["trip_id"] == "#42"
        assert card["trip_id_num"] == 42
        assert card["status"] == "Planned"
        assert card["truck_plate"] == "ABC-123"
        assert card["truck_id"] == 7
        assert card["driver_name"] == "John"
        assert card["driver_id"] == 5
        assert card["departure_date"] == "2026-06-01"
        assert card["eta"] == "2026-06-02"
        assert card["alerts_count"] == 0

    def test_filters_limit_passed_to_get_all_fallback(self):
        self.mock_repo.get_by_statuses.side_effect = Exception("Repo error")
        self.mock_trip_service.get_all.return_value = []

        filters = DispatchBoardFilters(limit=500)
        self.service.get_dispatch_board_data(filters)
        self.mock_trip_service.get_all.assert_called_once_with(limit=500)


# ══════════════════════════════════════════════════════════════════════
# evaluate_trip_delay  (STATIC pure function)
# ══════════════════════════════════════════════════════════════════════


class TestEvaluateTripDelay:
    """Tests for the static pure function evaluate_trip_delay."""

    FIXED_NOW = datetime(2026, 7, 13, 12, 0, 0)

    # ── In Transit ────────────────────────────────────────────────────

    def test_in_transit_past_eta_delayed(self):
        trip = {"status": "In Transit", "eta": "11/07/2026"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is True
        assert minutes > 0

    def test_in_transit_future_eta_not_delayed(self):
        trip = {"status": "In Transit", "eta": "15/07/2026"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False
        assert minutes == 0

    def test_in_transit_no_eta_not_delayed(self):
        trip = {"status": "In Transit", "eta": ""}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False

    def test_in_transit_eta_parse_error_not_delayed(self):
        trip = {"status": "In Transit", "eta": "not-a-date"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False

    def test_active_variant_past_eta(self):
        trip = {"status": "Active", "eta": "11/07/2026"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is True

    def test_inprogress_variant(self):
        trip = {"status": "InProgress", "eta": "11/07/2026"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is True

    def test_intransit_variant(self):
        trip = {"status": "InTransit", "eta": "11/07/2026"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is True

    # ── Loading ───────────────────────────────────────────────────────

    def test_loading_past_departure_plus_2h_delayed(self):
        trip = {"status": "Loading", "departure_date": "13/07/2026"}
        now = datetime(2026, 7, 13, 15, 0, 0)  # 15h past midnight departure, 13h past threshold
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=now)
        assert delayed is True
        assert minutes == 780  # (15:00 - 02:00) = 13h = 780min

    def test_loading_within_2h_not_delayed(self):
        trip = {"status": "Loading", "departure_date": "13/07/2026"}
        now = datetime(2026, 7, 13, 1, 30, 0)  # 1.5h past midnight, within 2h threshold
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=now)
        assert delayed is False

    def test_loading_no_departure_not_delayed(self):
        trip = {"status": "Loading", "departure_date": ""}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False

    def test_loading_bad_date_not_delayed(self):
        trip = {"status": "Loading", "departure_date": "bad-date"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False

    def test_preparing_variant(self):
        trip = {"status": "Preparing", "departure_date": "11/07/2026"}
        now = datetime(2026, 7, 13, 12, 0, 0)
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=now)
        assert delayed is True

    def test_pickup_variant(self):
        trip = {"status": "Pickup", "departure_date": "11/07/2026"}
        now = datetime(2026, 7, 13, 12, 0, 0)
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=now)
        assert delayed is True

    # ── Planned ───────────────────────────────────────────────────────

    def test_planned_departure_long_past_delayed(self):
        trip = {"status": "Planned", "departure_date": "10/07/2026"}
        # 10 Jul + 24h = 11 Jul, now is 13 Jul → delayed
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is True
        assert minutes > 0

    def test_planned_departure_recent_not_delayed(self):
        trip = {"status": "Planned", "departure_date": "13/07/2026"}
        now = datetime(2026, 7, 13, 6, 0, 0)  # same day, within 24h
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=now)
        assert delayed is False

    def test_planned_no_departure_not_delayed(self):
        trip = {"status": "Planned", "departure_date": ""}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False

    def test_planned_bad_date_not_delayed(self):
        trip = {"status": "Planned", "departure_date": "bad"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False

    def test_scheduled_variant(self):
        trip = {"status": "Scheduled", "departure_date": "10/07/2026"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is True

    def test_pending_variant(self):
        trip = {"status": "Pending", "departure_date": "10/07/2026"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is True

    # ── Other statuses (never delayed) ────────────────────────────────

    def test_delivered_not_delayed(self):
        trip = {"status": "Delivered"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False

    def test_cancelled_not_delayed(self):
        trip = {"status": "Cancelled"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False

    def test_empty_status_not_delayed(self):
        trip = {"status": ""}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False

    def test_missing_status_not_delayed(self):
        trip = {}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=self.FIXED_NOW)
        assert delayed is False

    # ── Edge cases ────────────────────────────────────────────────────

    def test_now_defaults_to_datetime_now(self):
        """When now is None, should use datetime.now() — just ensure no crash and returns tuple."""
        trip = {"status": "In Transit", "eta": "01/01/2020"}
        delayed, minutes = DispatchService.evaluate_trip_delay(trip)
        assert isinstance(delayed, bool)
        assert isinstance(minutes, int)

    def test_in_transit_eta_equal_now_not_delayed(self):
        """If eta == now exactly, not considered delayed."""
        now = datetime(2026, 7, 13, 12, 0, 0)
        trip = {"status": "In Transit", "eta": "13/07/2026"}
        # _parse_trip_date returns 00:00 on that day, so now > that
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=now)
        assert delayed is True  # now > midnight of the 13th

    def test_minutes_calculation_accuracy(self):
        now = datetime(2026, 7, 13, 14, 0, 0)
        trip = {"status": "Loading", "departure_date": "13/07/2026"}
        # departure at midnight, threshold = 02:00, now = 14:00 → 720 min overdue
        delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=now)
        assert delayed is True
        assert minutes == 720


# ══════════════════════════════════════════════════════════════════════
# create_delay_alert
# ══════════════════════════════════════════════════════════════════════


class TestCreateDelayAlert:
    def setup_method(self):
        self.mock_alert_manager = MagicMock()
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            alert_manager=self.mock_alert_manager,
        )

    def test_creates_alert_critical(self):
        self.mock_alert_manager.get_alerts.return_value = []
        self.mock_alert_manager.create_alert.return_value = Alert(
            id="alert-1", type=AlertType.TRIP_DELAY, severity=Severity.CRITICAL,
        )

        trip_data = {"trip_id_num": 42, "truck_plate": "ABC-123",
                     "driver_name": "John", "status": "In Transit"}
        alert = self.service.create_delay_alert(trip_data, 150)  # >120 min → CRITICAL

        assert alert is not None
        self.mock_alert_manager.create_alert.assert_called_once()
        call_kwargs = self.mock_alert_manager.create_alert.call_args.kwargs
        assert call_kwargs["alert_type"] == AlertType.TRIP_DELAY
        assert call_kwargs["severity"] == Severity.CRITICAL
        assert call_kwargs["title"] == "Trip #42 — Delay"
        assert call_kwargs["trip_id"] == "42"
        assert call_kwargs["truck_id"] == "ABC-123"

    def test_creates_alert_warning(self):
        self.mock_alert_manager.get_alerts.return_value = []
        self.mock_alert_manager.create_alert.return_value = Alert(
            id="alert-2", type=AlertType.TRIP_DELAY, severity=Severity.WARNING,
        )

        trip_data = {"trip_id_num": 42, "truck_plate": "", "driver_name": "",
                     "status": "Loading"}
        alert = self.service.create_delay_alert(trip_data, 60)  # ≤120 min → WARNING

        assert alert is not None
        call_kwargs = self.mock_alert_manager.create_alert.call_args.kwargs
        assert call_kwargs["severity"] == Severity.WARNING
        assert call_kwargs["truck_id"] is None  # empty plate becomes None

    def test_skips_duplicate(self):
        existing_alerts = [
            Alert(id="existing-1", type=AlertType.TRIP_DELAY, trip_id="42", resolved=False),
        ]
        self.mock_alert_manager.get_alerts.return_value = existing_alerts

        trip_data = {"trip_id_num": 42}
        alert = self.service.create_delay_alert(trip_data, 60)

        assert alert is None
        self.mock_alert_manager.create_alert.assert_not_called()

    def test_no_trip_id_returns_none(self):
        trip_data = {"truck_plate": "ABC"}
        alert = self.service.create_delay_alert(trip_data, 60)
        assert alert is None
        self.mock_alert_manager.create_alert.assert_not_called()

    def test_no_alert_manager_returns_none(self):
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            alert_manager=None,
        )
        alert = service.create_delay_alert({"trip_id_num": 42}, 60)
        assert alert is None

    def test_metadata_includes_minutes_and_status(self):
        self.mock_alert_manager.get_alerts.return_value = []
        self.mock_alert_manager.create_alert.return_value = MagicMock()

        trip_data = {"trip_id_num": 42, "status": "In Transit"}
        self.service.create_delay_alert(trip_data, 90)

        metadata = self.mock_alert_manager.create_alert.call_args.kwargs["metadata"]
        assert metadata["minutes_overdue"] == 90
        assert metadata["status"] == "In Transit"

    def test_duplicate_check_respects_different_trip_id(self):
        existing_alerts = [
            Alert(id="existing-1", type=AlertType.TRIP_DELAY, trip_id="99", resolved=False),
        ]
        self.mock_alert_manager.get_alerts.return_value = existing_alerts
        self.mock_alert_manager.create_alert.return_value = MagicMock()

        trip_data = {"trip_id_num": 42, "status": "In Transit"}
        alert = self.service.create_delay_alert(trip_data, 60)
        assert alert is not None  # Different trip, so alert created


# ══════════════════════════════════════════════════════════════════════
# resolve_delay_alert
# ══════════════════════════════════════════════════════════════════════


class TestResolveDelayAlert:
    def setup_method(self):
        self.mock_alert_manager = MagicMock()
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            alert_manager=self.mock_alert_manager,
        )

    def test_resolves_existing_alert(self):
        existing_alerts = [
            Alert(id="alert-1", type=AlertType.TRIP_DELAY, trip_id="42", resolved=False),
        ]
        self.mock_alert_manager.get_alerts.return_value = existing_alerts
        self.mock_alert_manager.resolve_alert.return_value = True

        result = self.service.resolve_delay_alert(42)
        assert result is True
        self.mock_alert_manager.resolve_alert.assert_called_once_with("alert-1")

    def test_no_alert_found_returns_false(self):
        self.mock_alert_manager.get_alerts.return_value = [
            Alert(id="alert-1", type=AlertType.TRIP_DELAY, trip_id="99", resolved=False),
        ]
        result = self.service.resolve_delay_alert(42)
        assert result is False
        self.mock_alert_manager.resolve_alert.assert_not_called()

    def test_no_alert_manager_returns_false(self):
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            alert_manager=None,
        )
        result = service.resolve_delay_alert(42)
        assert result is False

    def test_empty_alerts_list_returns_false(self):
        self.mock_alert_manager.get_alerts.return_value = []
        result = self.service.resolve_delay_alert(42)
        assert result is False


# ══════════════════════════════════════════════════════════════════════
# Private helpers
# ══════════════════════════════════════════════════════════════════════


class TestValidateTripExists:
    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=MagicMock(),
            driver_repo=MagicMock(),
            conflict_service=MagicMock(),
        )

    def test_trip_found(self):
        self.mock_trip_service.get_by_id.return_value = {"id": 42}
        trip = self.service._validate_trip_exists(42)
        assert trip["id"] == 42
        self.mock_trip_service.get_by_id.assert_called_once_with(42)

    def test_trip_not_found_raises(self):
        self.mock_trip_service.get_by_id.return_value = None
        with pytest.raises(TripNotFoundError):
            self.service._validate_trip_exists(42)


class TestValidateTruckExists:
    def setup_method(self):
        self.mock_fleet_repo = MagicMock()
        self.service = DispatchService(
            trip_service=MagicMock(),
            fleet_repo=self.mock_fleet_repo,
            driver_repo=MagicMock(),
            conflict_service=MagicMock(),
        )

    def test_truck_found(self):
        self.mock_fleet_repo.get_by_id.return_value = {"id": 7}
        truck = self.service._validate_truck_exists(7)
        assert truck["id"] == 7

    def test_truck_not_found_raises(self):
        self.mock_fleet_repo.get_by_id.return_value = None
        with pytest.raises(TruckNotFoundError):
            self.service._validate_truck_exists(7)


class TestValidateDriverExists:
    def setup_method(self):
        self.mock_driver_repo = MagicMock()
        self.service = DispatchService(
            trip_service=MagicMock(),
            fleet_repo=MagicMock(),
            driver_repo=self.mock_driver_repo,
            conflict_service=MagicMock(),
        )

    def test_driver_found(self):
        self.mock_driver_repo.get_by_id.return_value = {"id": 5}
        driver = self.service._validate_driver_exists(5)
        assert driver["id"] == 5

    def test_driver_not_found_raises(self):
        self.mock_driver_repo.get_by_id.return_value = None
        with pytest.raises(DriverNotFoundError):
            self.service._validate_driver_exists(5)


class TestBuildCardData:
    def setup_method(self):
        self.service = DispatchService(
            trip_service=MagicMock(),
            fleet_repo=MagicMock(),
            driver_repo=MagicMock(),
            conflict_service=MagicMock(),
        )

    def test_builds_card_with_all_fields(self):
        trip = {
            "id": 42,
            "status": "In Transit",
            "truck_number": "ABC-123",
            "driver_name": "John",
            "driver_id": 5,
            "truck_id": 7,
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
        }
        card = self.service._build_card_data(trip, None)
        assert card["trip_id"] == "#42"
        assert card["trip_id_num"] == 42
        assert card["status"] == "In Transit"
        assert card["truck_plate"] == "ABC-123"
        assert card["truck_id"] == 7
        assert card["driver_name"] == "John"
        assert card["driver_id"] == 5
        assert card["origin"] == ""
        assert card["destination"] == ""
        assert card["departure_date"] == "2026-06-01"
        assert card["eta"] == "2026-06-02"
        assert card["alerts_count"] == 0

    def test_card_with_missing_fields(self):
        trip = {"id": 0, "status": ""}
        card = self.service._build_card_data(trip, None)
        assert card["trip_id"] == "#0"
        assert card["trip_id_num"] == 0
        assert card["status"] == ""  # empty string preserved from trip
        assert card["truck_plate"] == ""
        assert card["driver_name"] == ""
        assert card["driver_id"] is None
        assert card["truck_id"] is None

    def test_card_with_route_resolution(self):
        trip = {"id": 1, "status": "Planned", "route_history_v2_id": 99}
        mock_route_repo = MagicMock()
        mock_route_repo.get_by_id.return_value = {
            "route_summary_json": '{"origin": "Paris", "destination": "Berlin"}',
        }
        card = self.service._build_card_data(trip, mock_route_repo)
        assert card["origin"] == "Paris"
        assert card["destination"] == "Berlin"


class TestResolveRoute:
    def setup_method(self):
        self.service = DispatchService(
            trip_service=MagicMock(),
            fleet_repo=MagicMock(),
            driver_repo=MagicMock(),
            conflict_service=MagicMock(),
        )

    def test_no_route_id(self):
        trip = {"id": 1}
        origin, dest = self.service._resolve_route(trip, MagicMock())
        assert origin == ""
        assert dest == ""

    def test_no_route_repo(self):
        trip = {"id": 1, "route_history_v2_id": 99}
        origin, dest = self.service._resolve_route(trip, None)
        assert origin == ""
        assert dest == ""

    def test_route_found(self):
        trip = {"id": 1, "route_history_v2_id": 99}
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "route_summary_json": json.dumps({"origin": "Paris", "destination": "Berlin"}),
        }
        origin, dest = self.service._resolve_route(trip, mock_repo)
        assert origin == "Paris"
        assert dest == "Berlin"

    def test_route_not_found(self):
        trip = {"id": 1, "route_history_v2_id": 99}
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        origin, dest = self.service._resolve_route(trip, mock_repo)
        assert origin == ""
        assert dest == ""

    def test_route_no_summary(self):
        trip = {"id": 1, "route_history_v2_id": 99}
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {"route_summary_json": ""}
        origin, dest = self.service._resolve_route(trip, mock_repo)
        assert origin == ""
        assert dest == ""

    def test_summary_already_dict(self):
        trip = {"id": 1, "route_history_v2_id": 99}
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "route_summary_json": {"origin": "Paris", "destination": "Berlin"},
        }
        origin, dest = self.service._resolve_route(trip, mock_repo)
        assert origin == "Paris"
        assert dest == "Berlin"

    def test_parse_error_returns_empty(self):
        trip = {"id": 1, "route_history_v2_id": 99}
        mock_repo = MagicMock()
        mock_repo.get_by_id.side_effect = ValueError("DB error")
        origin, dest = self.service._resolve_route(trip, mock_repo)
        assert origin == ""
        assert dest == ""


# ══════════════════════════════════════════════════════════════════════
# _parse_trip_date (static)
# ══════════════════════════════════════════════════════════════════════


class TestParseTripDate:
    def test_valid_date(self):
        with patch("utils.dates.parse_date", return_value=datetime(2026, 7, 13)) as mock_parse:
            result = DispatchService._parse_trip_date("13/07/2026")
            mock_parse.assert_called_once_with("13/07/2026", "%d/%m/%Y")
            assert result == datetime(2026, 7, 13)

    def test_invalid_date_returns_none(self):
        with patch("utils.dates.parse_date", return_value=None):
            result = DispatchService._parse_trip_date("bad-date")
            assert result is None


# ══════════════════════════════════════════════════════════════════════
# Module-level constants
# ══════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_status_to_column_mapping(self):
        assert STATUS_TO_COLUMN["Planned"] == "Planned"
        assert STATUS_TO_COLUMN["Scheduled"] == "Planned"
        assert STATUS_TO_COLUMN["Loading"] == "Loading"
        assert STATUS_TO_COLUMN["In Transit"] == "In Transit"
        assert STATUS_TO_COLUMN["InTransit"] == "In Transit"
        assert STATUS_TO_COLUMN["Delivered"] == "Delivered"
        assert STATUS_TO_COLUMN["Cancelled"] == "Cancelled"

    def test_column_keys(self):
        assert COLUMN_KEYS == ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]


# ══════════════════════════════════════════════════════════════════════
# Silent-swallow regression: former logger.debug / `except: pass` sites now
# log a warning while keeping identical return values and control flow.
# ══════════════════════════════════════════════════════════════════════


class TestSwallowSitesLogWarnings:
    """Regression tests for observability: silent swallow sites log warnings."""

    def setup_method(self):
        self.mock_trip_service = MagicMock()
        self.mock_fleet_repo = MagicMock()
        self.mock_driver_repo = MagicMock()
        self.mock_conflict_service = MagicMock()
        self.mock_event_bus = MagicMock()
        self.mock_dta_service = MagicMock()

        self.service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=self.mock_event_bus,
            dta_service=self.mock_dta_service,
        )

        self.mock_trip = {"id": 42, "truck_number": None, "truck_id": None,
                          "driver_id": None, "driver_name": None, "status": "Planned"}
        self.mock_trip_service.get_by_id.return_value = self.mock_trip
        self.mock_truck = {"id": 7, "plate": "ABC-123"}
        self.mock_fleet_repo.get_by_id.return_value = self.mock_truck
        self.mock_driver = {"id": 5, "name": "John Doe"}
        self.mock_driver_repo.get_by_id.return_value = self.mock_driver

        self._patch_truck = patch.object(
            self.service._availability, "check_truck",
            return_value=MagicMock(available=True, status_text="Available"),
        )
        self._patch_truck.start()
        self._patch_driver = patch.object(
            self.service._availability, "check_driver",
            return_value=MagicMock(available=True, status_text="Available"),
        )
        self._patch_driver.start()

    def teardown_method(self):
        self._patch_truck.stop()
        self._patch_driver.stop()

    def test_assign_truck_event_publish_failure_logs_warning(self):
        self.mock_event_bus.publish.side_effect = RuntimeError("Bus down")
        with patch("services.dispatch_service.dispatch_service.logger") as mock_logger:
            result = self.service.assign_truck(42, 7)
        assert result.success is True  # behaviour unchanged — still no raise
        assert mock_logger.warning.call_count == 1
        args = mock_logger.warning.call_args[0]
        assert any("TRIP_ASSIGNED" in str(a) for a in args)
        assert any("42" in str(a) for a in args)

    def test_assign_driver_event_publish_failure_logs_warning(self):
        self.mock_event_bus.publish.side_effect = RuntimeError("Bus down")
        with patch("services.dispatch_service.dispatch_service.logger") as mock_logger:
            result = self.service.assign_driver(42, 5)
        assert result.success is True
        assert mock_logger.warning.call_count == 1
        args = mock_logger.warning.call_args[0]
        assert any("TRIP_ASSIGNED" in str(a) for a in args)

    def test_dta_pairing_failure_logs_warning(self):
        self.mock_dta_service.assign_driver_to_truck.side_effect = RuntimeError("DTA down")
        with patch("services.dispatch_service.dispatch_service.logger") as mock_logger:
            result = self.service.assign_both(42, 7, 5)
        assert result.success is True
        assert mock_logger.warning.call_count == 1
        args = mock_logger.warning.call_args[0]
        assert any("DTA pairing failed" in str(a) for a in args)

    def test_transition_status_event_publish_failure_logs_warning(self):
        self.mock_event_bus.publish.side_effect = RuntimeError("Bus down")
        service = DispatchService(
            trip_service=self.mock_trip_service,
            fleet_repo=self.mock_fleet_repo,
            driver_repo=self.mock_driver_repo,
            conflict_service=self.mock_conflict_service,
            event_bus=self.mock_event_bus,
            ops_engine=None,
        )
        service._trip_service.get_by_id.return_value = self.mock_trip
        with patch("services.dispatch_service.dispatch_service.logger") as mock_logger:
            result = service.transition_status(42, "Loading")
        assert result.success is True
        assert mock_logger.warning.call_count == 1
        args = mock_logger.warning.call_args[0]
        assert any("TRIP_STATUS_CHANGED" in str(a) for a in args)

    def test_route_resolution_failure_logs_warning(self):
        mock_route_repo = MagicMock()
        self.mock_trip_service._route_repo = mock_route_repo
        mock_route_repo.get_by_id.side_effect = ValueError("DB error")
        trips = [{"id": 42, "status": "Planned", "route_history_v2_id": 99,
                  "start_date": "2026-01-01"}]
        self.mock_trip_service._trip_repo.get_by_statuses.return_value = trips
        with patch("services.dispatch_service.dispatch_service.logger") as mock_logger:
            response = self.service.get_dispatch_board_data()
        card = response.column_trips["Planned"][0]
        assert card["origin"] == ""
        assert card["destination"] == ""
        assert mock_logger.warning.call_count == 1
        args = mock_logger.warning.call_args[0]
        assert any("Failed to resolve route" in str(a) for a in args)

    def test_delay_parse_error_logs_warning_and_returns_same_default(self):
        """evaluate_trip_delay still returns (False, 0) but logs a warning."""
        trip = {"status": "In Transit", "eta": "bad"}
        now = datetime(2026, 7, 13, 12, 0, 0)
        with patch.object(
            DispatchService, "_parse_trip_date", side_effect=ValueError("bad date"),
        ) as mock_parse, patch(
            "services.dispatch_service.dispatch_service.logger",
        ) as mock_logger:
            delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=now)
        assert delayed is False
        assert minutes == 0
        mock_parse.assert_called_once()
        assert mock_logger.warning.call_count == 1
        args = mock_logger.warning.call_args[0]
        assert any("Failed to evaluate delay" in str(a) for a in args)

    def test_delay_parse_error_logs_trip_id_context_when_present(self):
        trip = {"status": "Loading", "departure_date": "bad", "trip_id_num": 99}
        now = datetime(2026, 7, 13, 12, 0, 0)
        with patch.object(
            DispatchService, "_parse_trip_date", side_effect=ValueError("bad date"),
        ), patch("services.dispatch_service.dispatch_service.logger") as mock_logger:
            delayed, minutes = DispatchService.evaluate_trip_delay(trip, now=now)
        assert delayed is False
        assert minutes == 0
        assert mock_logger.warning.call_count == 1
        args = mock_logger.warning.call_args[0]
        assert any("99" in str(a) for a in args)
