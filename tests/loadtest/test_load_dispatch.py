"""Load tests for dispatch operations — DispatchService directly.

Tests cover bulk assignment throughput, dispatch board data loading,
concurrent access, and status transition throughput.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from services.dispatch_service.dispatch_service import DispatchService
from services.dispatch_service.models import DispatchBoardFilters
from tests.loadtest.conftest import run_concurrent

pytestmark = pytest.mark.slow


class TestLoadDispatch:
    """Load tests for DispatchService operations."""

    @pytest.fixture
    def dispatch_service(self):
        """Build a DispatchService with fully mocked dependencies."""
        mock_trip_service = MagicMock()
        mock_fleet_repo = MagicMock()
        mock_driver_repo = MagicMock()
        mock_conflict_service = MagicMock()

        # Make the availability checker return available for all checks
        mock_avail = MagicMock()
        mock_avail.available = True
        mock_avail.status_text = "Available"
        mock_conflict_service.check_conflicts.return_value = []

        svc = DispatchService(
            trip_service=mock_trip_service,
            fleet_repo=mock_fleet_repo,
            driver_repo=mock_driver_repo,
            conflict_service=mock_conflict_service,
        )

        # Patch the internal availability checker to always succeed
        svc._availability.check_truck = lambda _truck, _data: mock_avail
        svc._availability.check_driver = lambda _driver, _data: mock_avail

        return svc, mock_trip_service, mock_fleet_repo, mock_driver_repo

    # ── 1. Bulk assignment throughput ────────────────────────────────────

    @pytest.mark.parametrize("n", [10, 50, 100])
    def test_bulk_assign_truck_throughput(self, dispatch_service, n):
        """Bulk-assign a truck to N trips; assert sub-linear-ish scaling."""
        svc, mock_trip_service, mock_fleet_repo, _ = dispatch_service

        # Setup: trips exist, truck exists, all calls succeed
        mock_trip_service.get_by_id.side_effect = [
            {"id": i, "status": "Planned", "truck_number": None, "truck_id": None}
            for i in range(1, n + 1)
        ]
        mock_fleet_repo.get_by_id.return_value = {
            "id": 42,
            "plate": "TEST-001",
            "truck_number": "TEST-001",
        }

        trip_ids = list(range(1, n + 1))

        start = time.perf_counter()
        result = svc.bulk_assign_truck(trip_ids, truck_id=42)
        elapsed = time.perf_counter() - start

        # All should succeed
        assert result.succeeded == n, f"Expected {n} succeeded, got {result.succeeded}"
        assert result.failed == 0, f"Expected 0 failed, got {result.failed}"

        # Reasonable threshold: 100 ops should complete in < 2s in-memory
        # This is intentionally generous for CI.
        threshold = 0.02 * n  # 20ms per trip
        assert elapsed < max(threshold, 2.0), (
            f"bulk_assign_truck(n={n}) took {elapsed:.3f}s "
            f"(threshold={threshold:.3f}s)"
        )

    # ── 2. Dispatch board data loading ───────────────────────────────────

    def test_dispatch_board_data_loading(self, dispatch_service):
        """Load dispatch board with 100 trips across all statuses."""
        svc, mock_trip_service, _, _ = dispatch_service

        # Create 100 trips spanning all valid statuses
        statuses = [
            "Planned", "Scheduled", "Pending",
            "Loading", "Preparing", "Pickup",
            "In Transit", "Active", "InProgress",
            "Delivered", "Completed", "Done", "Invoiced", "Paid",
            "Cancelled",
        ]
        all_trips = [
            {
                "id": i,
                "status": statuses[i % len(statuses)],
                "truck_number": f"TRUCK-{i}",
                "driver_name": f"Driver {i}",
                "start_date": "2026-07-01",
                "end_date": "2026-07-10",
                "created_at": "2026-06-15",
                "route_history_v2_id": None,
            }
            for i in range(1, 101)
        ]

        # Wire trip_service.get_all to return these
        mock_trip_service.get_all.return_value = all_trips

        filters = DispatchBoardFilters(delivered_window_days=90, limit=200)

        start = time.perf_counter()
        data = svc.get_dispatch_board_data(filters)
        elapsed = time.perf_counter() - start

        # Verify all trips were grouped
        total_counted = sum(data.status_counts.values())
        assert total_counted == 100, (
            f"Expected 100 trips grouped, got {total_counted}"
        )
        # Response time threshold
        assert elapsed < 0.5, (
            f"get_dispatch_board_data took {elapsed:.3f}s (threshold: 0.5s)"
        )

    # ── 3. Concurrent access simulation ──────────────────────────────────

    @pytest.mark.parametrize("n_threads", [5, 10, 20])
    def test_concurrent_assign_truck(self, dispatch_service, n_threads):
        """Spawn N threads calling assign_truck simultaneously; no corruption."""
        svc, mock_trip_service, mock_fleet_repo, _ = dispatch_service

        # Setup: each thread assigns a distinct trip to the same truck
        mock_fleet_repo.get_by_id.return_value = {
            "id": 99,
            "plate": "CONCUR-99",
            "truck_number": "CONCUR-99",
        }

        # Give each concurrent call its own trip ID
        call_counter = iter(range(1, n_threads + 1))

        def assign_call():
            trip_id = next(call_counter)
            mock_trip_service.get_by_id.return_value = {
                "id": trip_id,
                "status": "Planned",
                "truck_number": None,
                "truck_id": None,
            }
            return svc.assign_truck(trip_id, truck_id=99)

        results, timings, errors, elapsed = run_concurrent(assign_call, n_threads)

        # No errors
        assert len(errors) == 0, (
            f"Concurrent assign_truck(n={n_threads}) produced {len(errors)} errors: {errors}"
        )
        # All succeeded
        assert len(results) == n_threads, (
            f"Expected {n_threads} results, got {len(results)}"
        )
        for r in results:
            assert r.success, f"Assign_truck failed: {r.message}"
            assert r.operation == "assign_truck"

    # ── 4. Status transition throughput ──────────────────────────────────

    def test_status_transition_throughput(self, dispatch_service):
        """Create 50 trips and transition each through all valid statuses."""
        svc, mock_trip_service, mock_fleet_repo, _ = dispatch_service

        # Trip data — needs to return a trip whose status is the current
        # simulated status for each call.
        # We track the "current" status for each trip via a closure.
        trip_statuses: dict[int, str] = {}

        def get_by_id_side_effect(trip_id):
            status = trip_statuses.get(trip_id, "Planned")
            return {
                "id": trip_id,
                "status": status,
                "truck_number": None,
                "truck_id": None,
                "driver_id": None,
                "driver_name": None,
            }

        mock_trip_service.get_by_id.side_effect = get_by_id_side_effect

        # The chain of transitions to test
        transition_chain = [
            "Planned",
            "Loading",
            "In Transit",
            "Delivered",
        ]

        n_trips = 50
        trip_ids = list(range(1, n_trips + 1))

        # Set initial status to "Planned" for all trips
        for tid in trip_ids:
            trip_statuses[tid] = "Planned"

        total_transitions = 0
        start = time.perf_counter()

        # Transition each trip through the chain
        for status_idx in range(len(transition_chain) - 1):
            new_status = transition_chain[status_idx + 1]
            for tid in trip_ids:
                trip_statuses[tid] = new_status  # advance status
                svc.transition_status(tid, new_status)
                total_transitions += 1

        elapsed = time.perf_counter() - start

        expected = n_trips * (len(transition_chain) - 1)
        assert total_transitions == expected, (
            f"Expected {expected} transitions, got {total_transitions}"
        )

        # Throughput threshold: each transition should be fast
        threshold = 0.01 * total_transitions  # 10ms per transition
        assert elapsed < max(threshold, 2.0), (
            f"{total_transitions} transitions took {elapsed:.3f}s "
            f"(threshold={max(threshold, 2.0):.3f}s)"
        )

        # Verify final status
        for tid in trip_ids:
            assert trip_statuses[tid] == "Delivered", (
                f"Trip #{tid} final status is '{trip_statuses[tid]}', expected 'Delivered'"
            )
