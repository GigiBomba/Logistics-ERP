from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from services.dispatch_service.dispatch_service import DispatchService

pytestmark = pytest.mark.mutation


class TestKillMutationDelayStatus:
    """Kill: 'In Transit' string comparison mutation → delay logic changes."""

    def test_in_transit_past_eta_is_delayed(self):
        """In Transit with past ETA MUST be delayed.
        If status comparison is mutated (e.g. 'In Transit' → not in tuple),
        this trip would incorrectly not be flagged."""
        trip = {"status": "In Transit", "eta": "01/01/2026"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True
        assert minutes > 0

    def test_in_transit_future_eta_not_delayed(self):
        """In Transit with future ETA MUST NOT be delayed.
        If status comparison is inverted, future ETA would be flagged."""
        trip = {"status": "In Transit", "eta": "01/01/2027"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0


class TestKillMutationDelayThresholdLoading:
    """Kill: 2h Loading threshold mutated from 120→0 or 120→999."""

    def test_loading_119min_not_delayed(self):
        """Loading at departure+119min → NOT delayed.
        If threshold is mutated from 120→0, this would incorrectly be delayed."""
        trip = {"status": "Loading", "departure_date": "01/06/2026"}
        # dep_dt = 2026-06-01 00:00, threshold = 2026-06-01 02:00
        now = datetime(2026, 6, 1, 1, 59)  # 1h59m after departure midnight
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_loading_121min_is_delayed(self):
        """Loading at departure+121min → delayed.
        If threshold is mutated from 120→999, this would incorrectly not be delayed."""
        trip = {"status": "Loading", "departure_date": "01/06/2026"}
        now = datetime(2026, 6, 1, 2, 1)  # 2h1m after departure midnight
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True
        assert minutes == 1

    def test_loading_over_threshold_exact_minutes(self):
        """Kill: minutes calculation for Loading uses exact arithmetic (not truncated hours)."""
        trip = {"status": "Loading", "departure_date": "01/06/2026"}
        # threshold = 2026-06-01 02:00, now = 2026-06-01 05:30
        # diff = 3h30m = 210 minutes
        now = datetime(2026, 6, 1, 5, 30)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True
        assert minutes == 210


class TestKillMutationDelayThresholdPlanned:
    """Kill: 24h Planned threshold mutated to 0 or infinite."""

    def test_planned_23h59m_not_delayed(self):
        """Planned departure 23h59min ago → NOT delayed.
        If threshold is mutated to 0, this would incorrectly be delayed."""
        trip = {"status": "Planned", "departure_date": "01/06/2026"}
        now = datetime(2026, 6, 1, 23, 59)  # 23h59m after departure midnight
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_planned_24h1min_is_delayed(self):
        """Planned departure 24h1min ago → delayed.
        If threshold is mutated to infinite, this would incorrectly not be delayed."""
        trip = {"status": "Planned", "departure_date": "01/06/2026"}
        now = datetime(2026, 6, 2, 0, 1)  # 24h1m after departure midnight
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True
        assert minutes == 1

    def test_planned_over_24h_exact_minutes(self):
        """Kill: minutes calculation for Planned uses exact arithmetic."""
        trip = {"status": "Planned", "departure_date": "01/06/2026"}
        # dep = Jun 1 00:00, now = Jun 3 12:00
        # threshold = now - 24h = Jun 2 12:00
        # minutes = (Jun 2 12:00 - Jun 1 00:00) = 36h = 2160 min
        now = datetime(2026, 6, 3, 12, 0)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True
        assert minutes == 2160


class TestKillMutationDelayNullHandling:
    """Kill: null/empty ETA/departure handling mutated → raises instead of graceful return."""

    def test_in_transit_no_eta_not_delayed(self):
        """In Transit without ETA → NOT delayed (not raises)."""
        trip = {"status": "In Transit", "eta": ""}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_in_transit_missing_eta_key_not_delayed(self):
        """In Transit without eta key → NOT delayed."""
        trip = {"status": "In Transit"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_loading_no_departure_not_delayed(self):
        """Loading without departure → NOT delayed (not raises)."""
        trip = {"status": "Loading", "departure_date": ""}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_loading_missing_departure_key_not_delayed(self):
        """Loading without departure key → NOT delayed."""
        trip = {"status": "Loading"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_planned_no_departure_not_delayed(self):
        """Planned without departure → NOT delayed."""
        trip = {"status": "Planned"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0


class TestKillMutationDelayAliases:
    """Kill: status alias handling — all aliases treated like canonical status."""

    def test_intransit_alias_delayed(self):
        """'InTransit' treated like 'In Transit' with past ETA → delayed."""
        trip = {"status": "InTransit", "eta": "01/01/2026"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True
        assert minutes > 0

    def test_active_alias_delayed(self):
        """'Active' treated like 'In Transit' with past ETA → delayed."""
        trip = {"status": "Active", "eta": "01/01/2026"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True
        assert minutes > 0

    def test_inprogress_alias_delayed(self):
        """'InProgress' treated like 'In Transit' with past ETA → delayed."""
        trip = {"status": "InProgress", "eta": "01/01/2026"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True
        assert minutes > 0

    def test_intransit_alias_no_eta_not_delayed(self):
        """'InTransit' without ETA → NOT delayed (same as canonical)."""
        trip = {"status": "InTransit"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_loading_alias_preparing_delayed(self):
        """'Preparing' treated like 'Loading' over threshold → delayed."""
        trip = {"status": "Preparing", "departure_date": "01/06/2026"}
        now = datetime(2026, 6, 1, 2, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True

    def test_loading_alias_pickup_delayed(self):
        """'Pickup' treated like 'Loading' over threshold → delayed."""
        trip = {"status": "Pickup", "departure_date": "01/06/2026"}
        now = datetime(2026, 6, 1, 2, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True

    def test_planned_alias_scheduled_delayed(self):
        """'Scheduled' treated like 'Planned' over 24h → delayed."""
        trip = {"status": "Scheduled", "departure_date": "01/06/2026"}
        now = datetime(2026, 6, 2, 0, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True

    def test_planned_alias_pending_delayed(self):
        """'Pending' treated like 'Planned' over 24h → delayed."""
        trip = {"status": "Pending", "departure_date": "01/06/2026"}
        now = datetime(2026, 6, 2, 0, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True


class TestKillMutationDelayReturnShape:
    """Kill: return tuple shape — always returns (bool, int), never None."""

    def test_delayed_returns_bool_int_tuple(self):
        """Delayed result is (True, positive_int)."""
        trip = {"status": "In Transit", "eta": "01/01/2026"}
        now = datetime(2026, 6, 1)
        result = DispatchService.evaluate_trip_delay(trip, now)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], int)

    def test_not_delayed_returns_false_zero_tuple(self):
        """Non-delayed result is (False, 0)."""
        trip = {"status": "Planned"}
        now = datetime(2026, 6, 1)
        result = DispatchService.evaluate_trip_delay(trip, now)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (False, 0)

    def test_neutral_status_returns_false_zero_tuple(self):
        """Status that is never delayed (e.g. Delivered) returns (False, 0)."""
        trip = {"status": "Delivered"}
        now = datetime(2026, 6, 1)
        result = DispatchService.evaluate_trip_delay(trip, now)
        assert isinstance(result, tuple)
        assert result == (False, 0)


class TestKillMutationDelayArithmetic:
    """Kill: exact minutes calculation arithmetic."""

    def test_in_transit_minutes_arithmetic(self):
        """In Transit: minutes = exact diff in minutes, not hours or truncated days."""
        trip = {"status": "In Transit", "eta": "01/01/2026"}
        # 2h30m after eta midnight = 150 minutes
        now = datetime(2026, 1, 1, 2, 30)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is True
        assert minutes == 150


class TestKillMutationDelayNeverDelayed:
    """Kill: statuses that should never be delayed."""

    def test_delivered_never_delayed(self):
        """Delivered status with past ETA → NOT delayed."""
        trip = {"status": "Delivered", "eta": "01/01/2020"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_cancelled_never_delayed(self):
        """Cancelled status with past ETA → NOT delayed."""
        trip = {"status": "Cancelled", "eta": "01/01/2020"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_empty_status_never_delayed(self):
        """Empty status string with past ETA → NOT delayed."""
        trip = {"status": "", "eta": "01/01/2020"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_missing_status_key_never_delayed(self):
        """Missing status key with past ETA → NOT delayed."""
        trip = {"eta": "01/01/2020"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_unknown_status_never_delayed(self):
        """Unknown status value → NOT delayed (falls through to return False, 0)."""
        trip = {"status": "UnknownStatus", "eta": "01/01/2020"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0

    def test_completed_never_delayed(self):
        """'Completed' (Delivered alias) → NOT delayed."""
        trip = {"status": "Completed", "eta": "01/01/2020"}
        now = datetime(2026, 6, 1)
        is_delayed, minutes = DispatchService.evaluate_trip_delay(trip, now)
        assert is_delayed is False
        assert minutes == 0
