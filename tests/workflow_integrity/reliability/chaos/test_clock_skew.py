"""Clock skew between devices chaos tests (Stage B P5-U4 / R-CONF-06).

Devices whose clocks are skewed relative to the server must not be able to
inject "future" or "stale" timestamps into conflict resolution.  This module
pins the *real* stamping path used by the fixtures:

* Scenario 1 — a status update whose queued action carries a client
  timestamp that is +5min ahead / -5min behind the server still stores the
  **server-authoritative** time in ``trip_status_history.created_at`` — the
  audit record written by ``TripRepository.record_status_history`` through
  ``datetime.now()``.  The client-supplied value is never honored because
  the real transition path (``MobileClient._apply_status_update`` →
  ``TripStatusEngine.transition``) accepts no timestamp argument.
* Scenario 2 — R-CONF-06 intent: two updates from differently-skewed
  devices converge on *server application order*; the final stored status
  is the last transition the real path applied, regardless of how far
  ahead/behind each device clock was.

All assertions are synchronous — no ``time.sleep``; events are observed
through the ``event_monitor`` fixture and its poll-free helpers.

Documented gap: R-CONF-06 additionally requires a server-side *rejection
window* (client timestamps >30s in the future or >5min in the past are
rejected).  The current sync path does not accept client timestamps at all,
so no such window exists yet — that requirement is pinned as a skip.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tests.workflow_integrity.fixtures.multi_platform_client import (
    DesktopClient,
    MobileClient,
)
from tests.workflow_integrity.personas import build_ionut_persona

pytestmark = pytest.mark.chaos_workflow

# Tolerance for "stored ≈ server now" comparisons — the server stamps with
# microsecond precision inside the test's execution window, so this only
# guards against wall-clock granularity, never against the ±5min skew.
_TOLERANCE = timedelta(seconds=10)


def _status_history(db, trip_id: int) -> list[dict]:
    """All recorded status transitions for a trip, oldest first."""
    rows = db.conn.execute(
        "SELECT * FROM trip_status_history WHERE trip_id = ? ORDER BY id",
        (trip_id,),
    ).fetchall()
    return [dict(r) for r in rows]


class TestServerAuthoritativeTimestamp:
    """Scenario 1 — the stored record/audit timestamp is server time.

    A device's clock skew is metadata on the queued action, never an input
    to the transition engine: ``TripStatusEngine.transition`` takes no
    timestamp argument, so the audit row written by
    ``TripRepository.record_status_history`` always carries the server's
    own ``datetime.now()``.
    """

    def test_plus_and_minus_skew_still_store_server_time(
        self, db, trip_service, event_monitor
    ):
        """A +5min and a -5min client timestamp are both ignored.

        Both updates flow through the real offline queue → sync → transition
        path.  The stored ``trip_status_history.created_at`` lands inside the
        sync's server-side wall-clock window — never on the device-supplied
        values.
        """
        ids = build_ionut_persona(db)
        trip_id = ids["trip_ids"]["planned"]  # starts Planned
        mobile = MobileClient(trip_service, db)
        event_monitor.track("trip.status_changed")

        now = datetime.now()
        skew_ahead = now + timedelta(minutes=5)   # desktop +5min vs server
        skew_behind = now - timedelta(minutes=5)  # mobile -5min vs server

        # Queue both updates through the real offline path.  Each queued
        # action carries the device's (skewed) local timestamp, exactly the
        # metadata a real offline client would attach on the device.
        mobile.update_status(trip_id, "Loading", offline=True,
                             idempotency_key="skew-ahead-loading")
        mobile._offline_queue[-1]["client_timestamp"] = skew_ahead.isoformat()
        mobile.update_status(trip_id, "In Transit", offline=True,
                             idempotency_key="skew-behind-in-transit")
        mobile._offline_queue[-1]["client_timestamp"] = skew_behind.isoformat()

        server_before = datetime.now()
        results = mobile.sync_queue()
        server_after = datetime.now()
        # Both transitions were legal (Planned → Loading → In Transit).
        assert [r["result"] for r in results] == [True, True]

        rows = _status_history(db, trip_id)
        assert len(rows) == 2
        expected_statuses = ["Loading", "In Transit"]

        for row, skew_dt in zip(rows, (skew_ahead, skew_behind)):
            stored = datetime.fromisoformat(row["created_at"])
            # 1. Server-authoritative: the audit record lands inside the
            #    server's own execution window.
            assert server_before - _TOLERANCE <= stored <= server_after + _TOLERANCE
            # 2. The client-supplied skew was NOT honored — ±5min is far
            #    outside any plausible server write window.
            assert abs((stored - skew_dt).total_seconds()) > 4 * 60
            assert row["new_status"] == expected_statuses.pop(0)

        event_monitor.assert_event_count("trip.status_changed", 2)
        assert [e["data"]["new_status"] for e in
                event_monitor.get_events("trip.status_changed")] == [
            "Loading", "In Transit",
        ]


class TestServerOrderConvergence:
    """Scenario 2 — R-CONF-06: skewed clocks converge on server order.

    Two devices with opposite clock skews queue conflicting updates while
    offline.  Neither device's clock is consulted: the final stored status
    is the last transition the server applied (sync/heal order), and every
    platform reads that identical state.
    """

    def test_rconf06_skewed_devices_converge_on_last_server_applied(
        self, db, trip_service, invoice_service, event_bus, event_monitor
    ):
        """The -5min-behind device wins because its update was applied last.

        Desk device (clock +5min) queues Loading; driver device (clock
        -5min) queues In Transit.  On heal the server applies Loading first
        (legal from Planned), then In Transit (legal from Loading).  The
        "behind" clock wins — server application order, not device skew,
        decides the final state.
        """
        ids = build_ionut_persona(db)
        trip_id = ids["trip_ids"]["planned"]  # starts Planned

        desktop = DesktopClient(trip_service, invoice_service, event_bus, db)
        desk_device = MobileClient(trip_service, db)    # clock +5min ahead
        driver_device = MobileClient(trip_service, db)  # clock -5min behind
        event_monitor.track("trip.status_changed")

        now = datetime.now()
        desk_device.update_status(trip_id, "Loading", offline=True,
                                  idempotency_key="rconf06-desk")
        desk_device._offline_queue[-1]["client_timestamp"] = (
            (now + timedelta(minutes=5)).isoformat()
        )
        driver_device.update_status(trip_id, "In Transit", offline=True,
                                    idempotency_key="rconf06-driver")
        driver_device._offline_queue[-1]["client_timestamp"] = (
            (now - timedelta(minutes=5)).isoformat()
        )
        # Neither queued update reached the server while offline.
        assert trip_service.get_by_id(trip_id)["status"] == "Planned"

        # Heal order = server application order.
        assert desk_device.sync_queue()[0]["result"] is True
        assert trip_service.get_by_id(trip_id)["status"] == "Loading"
        assert driver_device.sync_queue()[0]["result"] is True

        final = trip_service.get_by_id(trip_id)["status"]
        assert final == "In Transit"
        # Identical business state on every platform.
        assert desktop.get_trip(trip_id)["status"] == final
        assert desk_device.get_trip(trip_id)["status"] == final
        assert driver_device.get_trip(trip_id)["status"] == final
        event_monitor.assert_event_count("trip.status_changed", 2)

    @pytest.mark.skip(
        reason=(
            "R-CONF-06 rejection-window requirement (reject client timestamps "
            ">30s in the future or >5min in the past) is a documented gap: "
            "the real sync path (TripStatusEngine.transition) accepts no "
            "client timestamp, so there is no window to reject.  Scenario 1 "
            "pins the current authoritative-stamping behavior instead."
        )
    )
    def test_rconf06_rejection_window_for_skewed_client_timestamps(
        self, db, trip_service
    ):
        """GAP (skipped): the server must reject out-of-range client timestamps.

        R-CONF-06 requires the server to reject status updates whose client
        timestamp is >30s in the future or >5min in the past.  The real
        transition path accepts no client timestamp today, so the rejection
        window cannot be exercised yet — see the skip reason above.
        """
        ids = build_ionut_persona(db)
        trip_id = ids["trip_ids"]["planned"]
        mobile = MobileClient(trip_service, db)

        # Intended assertion once a rejection window exists: applying an
        # update carrying a +5min (or -5min) client timestamp must fail and
        # produce no trip_status_history row / no status_changed event.
        mobile.update_status(trip_id, "Loading", offline=True,
                             idempotency_key="rconf06-future")
        mobile._offline_queue[-1]["client_timestamp"] = (
            (datetime.now() + timedelta(minutes=5)).isoformat()
        )
        results = mobile.sync_queue()
        assert results[0]["result"] is False
        assert _status_history(db, trip_id) == []