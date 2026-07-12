"""Chaos tests: DispatchService failure scenarios — trip service failures,
availability checker failures, event bus failures, missing optional
dependencies, database/repo failures, and concurrent access.

Simulates infrastructure failures to verify graceful degradation.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest

from services.dispatch_service.dispatch_service import DispatchService
from services.dispatch_service.errors import (
    DispatchError,
    DriverNotFoundError,
    InvalidStatusTransitionError,
    ResourceUnavailableError,
    TripNotFoundError,
    TruckNotFoundError,
)
from services.dispatch_service.models import DispatchBoardFilters, DispatchResult
from services.operations.alert_manager import Alert, AlertType, Severity
from services.operations.event_bus import TRIP_ASSIGNED, TRIP_STATUS_CHANGED

pytestmark = pytest.mark.chaos


# ======================================================================
# Helpers
# ======================================================================


def _make_service(
    trip_service=None,
    fleet_repo=None,
    driver_repo=None,
    conflict_service=None,
    dta_service=None,
    tacho_repo=None,
    event_bus=None,
    alert_manager=None,
    ops_engine=None,
) -> DispatchService:
    """Create a DispatchService backed by MagicMocks for unspecified deps."""
    return DispatchService(
        trip_service=trip_service or MagicMock(),
        fleet_repo=fleet_repo or MagicMock(),
        driver_repo=driver_repo or MagicMock(),
        conflict_service=conflict_service or MagicMock(),
        dta_service=dta_service,
        tacho_repo=tacho_repo,
        event_bus=event_bus,
        alert_manager=alert_manager,
        ops_engine=ops_engine,
    )


def _patch_availability(service, method="check_truck", available=True, status_text="Available"):
    """Patch an AvailabilityChecker method to return a fixed response."""
    return patch.object(
        service._availability,
        method,
        return_value=MagicMock(available=available, status_text=status_text),
    )


# ======================================================================
# 1. Trip service failures
# ======================================================================


class TestTripServiceFailures:
    """Simulate trip_service failures — update, get_all, etc."""

    def setup_method(self):
        self.mock_trip = MagicMock()
        self.mock_fleet = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_conflict = MagicMock()
        self.mock_event = MagicMock()

        self.trip_service = MagicMock()
        self.fleet_repo = MagicMock()
        self.driver_repo = MagicMock()

        self.service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.mock_conflict,
            event_bus=self.mock_event,
            ops_engine=MagicMock(),
        )

        # Default valid data
        self.trip = {"id": 42, "truck_number": None, "truck_id": None, "status": "Planned"}
        self.truck = {"id": 7, "plate": "ABC-123"}
        self.driver = {"id": 5, "name": "John Doe"}

        self.trip_service.get_by_id.return_value = self.trip
        self.fleet_repo.get_by_id.return_value = self.truck
        self.driver_repo.get_by_id.return_value = self.driver

        # Patch availability to pass
        self._avail_patch = _patch_availability(self.service, "check_truck", available=True)
        self._avail_patch.start()
        self._avail_driver_patch = _patch_availability(self.service, "check_driver", available=True)
        self._avail_driver_patch.start()

    def teardown_method(self):
        self._avail_patch.stop()
        self._avail_driver_patch.stop()

    def test_assign_truck_trip_service_update_raises_error_propagates(self):
        """assign_truck: trip_service.update() raises → error propagates."""
        self.trip_service.update.side_effect = RuntimeError("DB write failure")

        with pytest.raises(RuntimeError, match="DB write failure"):
            self.service.assign_truck(42, 7)

        # Validate existence still occurred
        self.trip_service.get_by_id.assert_called_once_with(42)
        self.fleet_repo.get_by_id.assert_called_once_with(7)

    def test_assign_driver_trip_service_update_raises_error_propagates(self):
        """assign_driver: trip_service.update() raises → error propagates."""
        self.trip_service.update.side_effect = RuntimeError("DB write failure")

        with pytest.raises(RuntimeError, match="DB write failure"):
            self.service.assign_driver(42, 5)

        self.trip_service.get_by_id.assert_called_once_with(42)
        self.driver_repo.get_by_id.assert_called_once_with(5)

    def test_transition_status_ops_engine_raises_dispatch_error(self):
        """transition_status: ops_engine.force_trip_status() raises → DispatchError."""
        self.service._ops_engine.force_trip_status.side_effect = RuntimeError("Ops engine crash")

        with pytest.raises(DispatchError, match="Failed to transition trip #42"):
            self.service.transition_status(42, "Loading")

    def test_get_dispatch_board_data_trip_service_fails_graceful_empty_board(self):
        """get_dispatch_board_data: both repo and trip_service fail → empty board."""
        # Make both the repo query and get_all fallback fail
        repo = MagicMock()
        repo.get_by_statuses.side_effect = RuntimeError("Repo unavailable")
        self.trip_service._trip_repo = repo
        self.trip_service.get_all.side_effect = RuntimeError("TripService unavailable")

        response = self.service.get_dispatch_board_data()

        # Graceful degradation: returns empty groups, no crash
        assert response.column_trips is not None
        total = sum(len(v) for v in response.column_trips.values())
        assert total == 0
        assert all(len(v) == 0 for v in response.column_trips.values())

    def test_get_dispatch_board_data_fallback_to_get_all_succeeds(self):
        """get_dispatch_board_data: repo fails, fallback to get_all works."""
        repo = MagicMock()
        repo.get_by_statuses.side_effect = RuntimeError("Repo unavailable")
        self.trip_service._trip_repo = repo
        self.trip_service.get_all.return_value = [
            {"id": 1, "status": "Planned", "start_date": "2026-07-01"},
        ]

        response = self.service.get_dispatch_board_data()

        assert len(response.column_trips["Planned"]) == 1
        # Fallback was used
        self.trip_service.get_all.assert_called_once()


# ======================================================================
# 2. Availability checker failures
# ======================================================================


class TestAvailabilityCheckerFailures:
    """Simulate availability checker failures — unavailable, raise, etc."""

    def setup_method(self):
        self.trip_service = MagicMock()
        self.fleet_repo = MagicMock()
        self.driver_repo = MagicMock()
        self.conflict_service = MagicMock()
        self.event_bus = MagicMock()

        self.service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            event_bus=self.event_bus,
        )

        self.trip = {"id": 42, "truck_number": None, "truck_id": None, "status": "Planned"}
        self.truck = {"id": 7, "plate": "ABC-123"}
        self.driver = {"id": 5, "name": "John Doe"}

        self.trip_service.get_by_id.return_value = self.trip
        self.fleet_repo.get_by_id.return_value = self.truck
        self.driver_repo.get_by_id.return_value = self.driver

    def test_assign_truck_availability_returns_unavailable_raises_error(self):
        """assign_truck: availability checker returns unavailable → ResourceUnavailableError."""
        with _patch_availability(self.service, "check_truck", available=False, status_text="Truck in service"):
            with pytest.raises(ResourceUnavailableError, match="Truck in service"):
                self.service.assign_truck(42, 7)

        # No update was made
        self.trip_service.update.assert_not_called()

    def test_assign_truck_availability_checker_raises_exception_propagates(self):
        """assign_truck: availability checker raises exception → exception propagates."""
        self.service._availability.check_truck = MagicMock(
            side_effect=RuntimeError("Availability service down"),
        )

        with pytest.raises(RuntimeError, match="Availability service down"):
            self.service.assign_truck(42, 7)

        # No update was made
        self.trip_service.update.assert_not_called()

    def test_assign_truck_availability_checker_raises_dispatch_error(self):
        """assign_truck: availability checker raises DispatchError → propagates unchanged."""
        self.service._availability.check_truck = MagicMock(
            side_effect=ResourceUnavailableError("Conflict detected"),
        )

        with pytest.raises(ResourceUnavailableError, match="Conflict detected"):
            self.service.assign_truck(42, 7)

    def test_assign_driver_availability_returns_unavailable_raises_error(self):
        """assign_driver: availability checker returns unavailable → ResourceUnavailableError."""
        with _patch_availability(self.service, "check_driver", available=False, status_text="License expired"):
            with pytest.raises(ResourceUnavailableError, match="License expired"):
                self.service.assign_driver(42, 5)

        self.trip_service.update.assert_not_called()


# ======================================================================
# 3. Event bus failures (fire-and-forget)
# ======================================================================


class TestEventBusFailures:
    """Event bus publish raises — operations still succeed (fire-and-forget pattern)."""

    def setup_method(self):
        self.trip_service = MagicMock()
        self.fleet_repo = MagicMock()
        self.driver_repo = MagicMock()
        self.conflict_service = MagicMock()
        self.event_bus = MagicMock()

        self.service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            event_bus=self.event_bus,
        )

        self.trip = {"id": 42, "truck_number": None, "truck_id": None, "driver_id": None, "driver_name": None, "status": "Planned"}
        self.truck = {"id": 7, "plate": "ABC-123"}
        self.driver = {"id": 5, "name": "John Doe"}

        self.trip_service.get_by_id.return_value = self.trip
        self.fleet_repo.get_by_id.return_value = self.truck
        self.driver_repo.get_by_id.return_value = self.driver

        # Patch availability to pass
        self._patch_truck = _patch_availability(self.service, "check_truck", available=True)
        self._patch_truck.start()
        self._patch_driver = _patch_availability(self.service, "check_driver", available=True)
        self._patch_driver.start()

    def teardown_method(self):
        self._patch_truck.stop()
        self._patch_driver.stop()

    def test_assign_truck_event_bus_raises_still_succeeds(self):
        """assign_truck: event_bus.publish() raises → still succeeds (fire-and-forget)."""
        self.event_bus.publish.side_effect = RuntimeError("Event bus down")

        result = self.service.assign_truck(42, 7)

        assert result.success is True
        # Trip update still happened
        self.trip_service.update.assert_called_once()

    def test_assign_driver_event_bus_raises_still_succeeds(self):
        """assign_driver: event_bus.publish() raises → still succeeds (fire-and-forget)."""
        self.event_bus.publish.side_effect = RuntimeError("Event bus down")

        result = self.service.assign_driver(42, 5)

        assert result.success is True
        self.trip_service.update.assert_called_once()

    def test_transition_status_manual_path_event_bus_raises_still_succeeds(self):
        """transition_status (manual path): event_bus.publish() raises → still succeeds."""
        service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            event_bus=self.event_bus,
            ops_engine=None,  # Force manual path
        )
        service._trip_service.get_by_id.return_value = self.trip
        self.event_bus.publish.side_effect = RuntimeError("Event bus down")

        result = service.transition_status(42, "Loading")

        assert result.success is True
        # Manual update still happened
        self.trip_service.update.assert_called_once_with(42, {"status": "Loading"})


# ======================================================================
# 4. Missing optional dependencies
# ======================================================================


class TestMissingOptionalDependencies:
    """Graceful degradation when optional dependencies are None."""

    def setup_method(self):
        self.trip_service = MagicMock()
        self.fleet_repo = MagicMock()
        self.driver_repo = MagicMock()
        self.conflict_service = MagicMock()

        self.trip = {"id": 42, "truck_number": None, "truck_id": None, "driver_id": None, "driver_name": None, "status": "Planned"}
        self.truck = {"id": 7, "plate": "ABC-123"}
        self.driver = {"id": 5, "name": "John Doe"}

        self.trip_service.get_by_id.return_value = self.trip
        self.fleet_repo.get_by_id.return_value = self.truck
        self.driver_repo.get_by_id.return_value = self.driver

    def test_no_event_bus_assign_truck_still_works(self):
        """No event_bus → assign_truck still works."""
        service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            event_bus=None,
        )
        with _patch_availability(service, "check_truck", available=True):
            result = service.assign_truck(42, 7)

        assert result.success is True
        self.trip_service.update.assert_called_once()

    def test_no_event_bus_assign_driver_still_works(self):
        """No event_bus → assign_driver still works."""
        service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            event_bus=None,
        )
        with _patch_availability(service, "check_driver", available=True):
            result = service.assign_driver(42, 5)

        assert result.success is True
        self.trip_service.update.assert_called_once()

    def test_no_alert_manager_create_delay_alert_returns_none(self):
        """No alert_manager → create_delay_alert returns None."""
        service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            alert_manager=None,
        )

        trip_data = {"trip_id_num": 42, "status": "In Transit", "truck_plate": "ABC-123", "driver_name": "John"}
        alert = service.create_delay_alert(trip_data, 30)

        assert alert is None

    @pytest.mark.parametrize("alert_manager_fixture", [None, MagicMock()])
    def test_no_alert_manager_resolve_delay_alert_returns_false(self, alert_manager_fixture):
        """No alert_manager → resolve_delay_alert returns False."""
        service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            alert_manager=alert_manager_fixture,
        )

        if alert_manager_fixture is not None:
            alert_manager_fixture.get_alerts.return_value = []

        result = service.resolve_delay_alert(42)
        assert result is False

    def test_no_ops_engine_transition_status_falls_back_to_manual(self):
        """No ops_engine → transition_status falls back to manual update."""
        service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            event_bus=MagicMock(),
            ops_engine=None,
        )
        service._trip_service.get_by_id.return_value = self.trip

        result = service.transition_status(42, "Loading")

        assert result.success is True
        self.trip_service.update.assert_called_once_with(42, {"status": "Loading"})

    def test_no_dta_service_assign_both_still_works(self):
        """No dta_service → assign_both still works."""
        service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            dta_service=None,
            event_bus=MagicMock(),
        )
        with _patch_availability(service, "check_truck", available=True), \
             _patch_availability(service, "check_driver", available=True):
            result = service.assign_both(42, 7, 5)

        assert result.success is True
        assert result.operation == "assign_both"


# ======================================================================
# 5. Database/repo failures
# ======================================================================


class TestRepoFailures:
    """Repo get_by_id raises exceptions — error propagates."""

    def setup_method(self):
        self.trip_service = MagicMock()
        self.fleet_repo = MagicMock()
        self.driver_repo = MagicMock()
        self.conflict_service = MagicMock()

        self.service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            event_bus=MagicMock(),
        )

        self.trip = {"id": 42, "status": "Planned"}
        self.truck = {"id": 7, "plate": "ABC-123"}
        self.driver = {"id": 5, "name": "John Doe"}

    def test_fleet_repo_get_by_id_raises_error_propagates(self):
        """fleet_repo.get_by_id() raises → error propagates."""
        self.trip_service.get_by_id.return_value = self.trip
        self.fleet_repo.get_by_id.side_effect = RuntimeError("DB connection lost")

        with pytest.raises(RuntimeError, match="DB connection lost"):
            self.service.assign_truck(42, 7)

    def test_driver_repo_get_by_id_raises_error_propagates(self):
        """driver_repo.get_by_id() raises → error propagates."""
        self.trip_service.get_by_id.return_value = self.trip
        self.driver_repo.get_by_id.side_effect = RuntimeError("DB connection lost")

        with pytest.raises(RuntimeError, match="DB connection lost"):
            self.service.assign_driver(42, 5)

    def test_trip_service_get_by_id_raises_error_propagates(self):
        """trip_service.get_by_id() raises → error propagates."""
        self.trip_service.get_by_id.side_effect = RuntimeError("DB connection lost")

        with pytest.raises(RuntimeError, match="DB connection lost"):
            self.service.assign_truck(42, 7)

    def test_trip_service_get_by_id_raises_on_transition_status_propagates(self):
        """transition_status: trip_service.get_by_id() raises → error propagates."""
        self.trip_service.get_by_id.side_effect = RuntimeError("DB connection lost")

        with pytest.raises(RuntimeError, match="DB connection lost"):
            self.service.transition_status(42, "Loading")

    def test_fleet_repo_get_by_id_raises_on_bulk_assign(self):
        """bulk_assign_truck: fleet_repo.get_by_id() raises → error propagates."""
        self.fleet_repo.get_by_id.side_effect = RuntimeError("DB connection lost")

        with pytest.raises(RuntimeError, match="DB connection lost"):
            self.service.bulk_assign_truck([1, 2, 3], 7)


# ======================================================================
# 6. Concurrent access (thread safety smoke)
# ======================================================================


class TestConcurrentAccess:
    """Thread-safety smoke tests — rapid concurrent operations on same trip."""

    def setup_method(self):
        self.trip_service = MagicMock()
        self.fleet_repo = MagicMock()
        self.driver_repo = MagicMock()
        self.conflict_service = MagicMock()
        self.event_bus = MagicMock()
        self.ops_engine = MagicMock()

        self.service = _make_service(
            trip_service=self.trip_service,
            fleet_repo=self.fleet_repo,
            driver_repo=self.driver_repo,
            conflict_service=self.conflict_service,
            event_bus=self.event_bus,
            ops_engine=self.ops_engine,
        )

        self.trip = {"id": 42, "truck_number": None, "truck_id": None, "driver_id": None, "driver_name": None, "status": "Planned"}
        self.truck = {"id": 7, "plate": "ABC-123"}
        self.driver = {"id": 5, "name": "John Doe"}

        self.trip_service.get_by_id.return_value = self.trip
        self.fleet_repo.get_by_id.return_value = self.truck
        self.driver_repo.get_by_id.return_value = self.driver

        # Patch availability to pass
        self._patch_truck = _patch_availability(self.service, "check_truck", available=True)
        self._patch_truck.start()
        self._patch_driver = _patch_availability(self.service, "check_driver", available=True)
        self._patch_driver.start()

    def teardown_method(self):
        self._patch_truck.stop()
        self._patch_driver.stop()

    def test_rapid_status_transitions_on_same_trip(self):
        """Rapid concurrent status transitions on same trip — no crash."""
        n_threads = 20
        errors = []
        lock = threading.Lock()

        def _transition(status: str):
            try:
                # Each thread re-reads the mock (same MagicMock instance)
                self.service.transition_status(42, "Loading")
            except Exception as e:
                with lock:
                    errors.append((status, str(e)))

        statuses = [f"Loading-{i}" for i in range(n_threads)]
        threads = [threading.Thread(target=_transition, args=(s,)) for s in statuses]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        # Acceptable outcomes: success, DispatchError (race), or InvalidStatusTransitionError
        # The key invariant is no hard crash / unhandled exception type
        for status, err in errors:
            assert isinstance(err, (DispatchError, InvalidStatusTransitionError)), (
                f"Unexpected error type for {status}: {err}"
            )

    def test_simultaneous_truck_assignments_same_trip(self):
        """Simultaneous truck assignments to the same trip — no crash."""
        n_threads = 10
        errors = []
        lock = threading.Lock()

        def _assign(truck_id: int):
            try:
                self.service.assign_truck(42, truck_id)
            except Exception as e:
                with lock:
                    errors.append((truck_id, str(e)))

        truck_ids = list(range(1, n_threads + 1))
        threads = [threading.Thread(target=_assign, args=(tid,)) for tid in truck_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        # Acceptable: some succeed, some fail with resource conflict, no crash
        for tid, err in errors:
            assert isinstance(err, (DispatchError, ResourceUnavailableError, RuntimeError)), (
                f"Unexpected error for truck {tid}: {err}"
            )

    def test_simultaneous_truck_and_driver_assignments(self):
        """Concurrent truck + driver assignments on same trip — no crash."""
        n_pairs = 8
        errors = []
        lock = threading.Lock()

        def _assign_pair(idx: int):
            try:
                self.service.assign_both(42, 7 + idx, 5 + idx)
            except Exception as e:
                with lock:
                    errors.append((idx, str(e)))

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_assign_pair, i) for i in range(n_pairs)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    with lock:
                        errors.append(("future", str(e)))

        # No hard crash; DispatchError-level failures are acceptable
        for idx, err in errors:
            assert isinstance(err, (DispatchError, ResourceUnavailableError, TruckNotFoundError, DriverNotFoundError)), (
                f"Unexpected error for idx {idx}: {err}"
            )

    def test_concurrent_status_transitions_different_trips_no_interference(self):
        """Concurrent status transitions on different trips — no interference."""
        n_trips = 30
        errors = []
        lock = threading.Lock()

        # Set up trip_service.get_by_id to return different trip per id
        def get_by_id_side_effect(trip_id):
            return {"id": trip_id, "truck_number": None, "truck_id": None, "status": "Planned"}

        self.trip_service.get_by_id.side_effect = get_by_id_side_effect

        def _transition(trip_id: int):
            try:
                self.service.transition_status(trip_id, "Loading")
            except Exception as e:
                with lock:
                    errors.append((trip_id, str(e)))

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(_transition, i) for i in range(n_trips)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    with lock:
                        errors.append(("future", str(e)))

        # All should succeed since ops_engine is mocked
        assert len(errors) == 0, f"Concurrent transitions failed: {errors[:5]}"
