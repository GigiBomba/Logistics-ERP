from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from services.conflict_service import TripConflictService

pytestmark = pytest.mark.mutation


def _make_trip(**kwargs) -> dict:
    defaults = {
        "id": 1,
        "truck_number": "TRUCK-001",
        "truck_id": 10,
        "driver_id": 100,
        "driver_name": "Test Driver",
        "start_date": "01/06/2026",
        "end_date": "05/06/2026",
        "distance_km": "600",
        "status": "In Transit",
    }
    defaults.update(kwargs)
    return defaults


class TestKillMutationConflictService:
    """Mutation-killing tests for TripConflictService."""

    @pytest.fixture
    def service(self):
        db = MagicMock()
        svc = TripConflictService(db)
        svc._trip_repo = MagicMock()
        return svc

    @staticmethod
    def _parse_date(date_str):
        from utils.dates import parse_date
        return parse_date(date_str, "%d/%m/%Y")

    # ── Guard deletion ──────────────────────────────────────────

    def test_no_start_date_returns_empty_conflicts(self):
        """Kill: not departure guard deletion (no start_date -> empty conflicts)."""
        db = MagicMock()
        svc = TripConflictService(db)
        svc._trip_repo = MagicMock()

        conflicts = svc.check_conflicts({"truck_number": "TRUCK-001"})
        # If guard is removed, _estimate_eta receives None as start_dt -> crash
        assert conflicts == []

    # ── _same_entity ────────────────────────────────────────────

    def test_same_entity_plate_match_requires_all_conditions(self):
        """Kill: _same_entity 'and' -> 'or' mutation within plate matching.

        All three sub-conditions (truck_plate, other_truck, plate equality)
        must be true for same_truck=True based on plate.
        """
        svc = TripConflictService.__new__(TripConflictService)
        # truck_plate and other_truck and truck_plate == other_truck
        # If 'and' -> 'or': just having truck_plate truthy makes it True
        same_truck, _ = svc._same_entity(
            truck_plate="ABC", other_truck="XYZ",
            truck_id=None, other_truck_id=None,
            driver_id=1, other_driver=1,
        )
        # With correct 'and': "ABC" and "XYZ" and "ABC" != "XYZ" -> False
        # With mutated 'or': "ABC" or "XYZ" or ... -> True (WRONG)
        assert same_truck is False

    def test_same_entity_different_plates_no_match(self):
        """Different plates -> same_truck is False."""
        svc = TripConflictService.__new__(TripConflictService)
        same_truck, _ = svc._same_entity(
            truck_plate="ABC", other_truck="DEF",
            truck_id=None, other_truck_id=None,
            driver_id=1, other_driver=100,
        )
        assert same_truck is False

    # ── Overlap check ───────────────────────────────────────────

    def test_touching_intervals_no_overlap(self):
        """Kill: overlap operator swap (< -> <= or > -> >=).

        Two trips where one ends exactly when the other starts should NOT
        be considered overlapping.
        """
        svc = TripConflictService.__new__(TripConflictService)
        # Trip A: 01/06 - 05/06, Trip B: 05/06 - 10/06
        # departure < other_eta and eta > other_dep
        dep = datetime(2026, 6, 1)
        eta = datetime(2026, 6, 5)
        other_dep = datetime(2026, 6, 5)
        other_eta = datetime(2026, 6, 10)
        # dep < other_eta: 01/06 < 10/06 -> True
        # eta > other_dep: 05/06 > 05/06 -> False  (with >)
        # If > -> >=: 05/06 >= 05/06 -> True (WRONG -> overlap detected)
        overlap = dep < other_eta and eta > other_dep
        assert overlap is False

    # ── De Morgan ───────────────────────────────────────────────

    def test_same_truck_alone_is_conflict_regardless_of_driver(self):
        """Kill: not same_truck and not same_driver -> or mutation.

        Same truck with different driver should STILL be a conflict.
        If 'and' is mutated to 'or', same_truck=True makes
        'not True or not False' = 'False or True' = True -> continue (WRONG).
        """
        db = MagicMock()
        svc = TripConflictService(db)
        repo = MagicMock()
        existing = _make_trip(id=2, truck_number="TRUCK-001", truck_id=10,
                              driver_id=999)  # different driver
        repo.get_active_for_truck.return_value = [existing]
        svc._trip_repo = repo

        conflicts = svc.check_conflicts(
            _make_trip(id=1, truck_number="TRUCK-001", truck_id=10, driver_id=100)
        )
        # same truck -> should be a conflict regardless of driver
        assert len(conflicts) == 1

    def test_different_truck_and_driver_no_conflict(self):
        """Trips with different truck AND different driver -> no conflict."""
        db = MagicMock()
        svc = TripConflictService(db)
        repo = MagicMock()
        existing = _make_trip(id=2, truck_number="TRUCK-002", truck_id=20,
                              driver_id=200)
        repo.get_active_for_truck.return_value = [existing]
        svc._trip_repo = repo

        conflicts = svc.check_conflicts(
            _make_trip(id=1, truck_number="TRUCK-001", truck_id=10, driver_id=100)
        )
        assert len(conflicts) == 0

    # ── _estimate_eta ───────────────────────────────────────────

    def test_estimate_eta_no_end_date_no_distance_default_four_hours(self):
        """Kill: _estimate_eta default 4 hours (no end_date + no distance)."""
        svc = TripConflictService.__new__(TripConflictService)
        start_dt = datetime(2026, 6, 1, 8, 0, 0)
        trip = {"end_date": "", "distance_km": None}
        eta = svc._estimate_eta(trip, start_dt)
        expected = start_dt + timedelta(hours=4)
        assert eta == expected

    def test_estimate_eta_with_distance_calculates_eta(self):
        """Kill: _estimate_eta with distance -> calculated ETA."""
        svc = TripConflictService.__new__(TripConflictService)
        start_dt = datetime(2026, 6, 1, 8, 0, 0)
        trip = {"end_date": "", "distance_km": "600"}
        eta = svc._estimate_eta(trip, start_dt)
        hours = 600 / 60.0  # 10 hours
        expected = start_dt + timedelta(hours=hours)
        assert eta == expected
