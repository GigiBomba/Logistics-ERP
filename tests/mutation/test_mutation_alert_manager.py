from __future__ import annotations

import threading

import pytest

from services.operations.alert_manager import AlertManager, AlertType, Severity

pytestmark = pytest.mark.mutation


@pytest.fixture
def am():
    """Fresh AlertManager singleton for each test."""
    AlertManager._instance = None
    AlertManager._lock = threading.Lock()
    mgr = AlertManager(db=None)
    mgr._alerts.clear()
    return mgr


def _make_alert(alert_id="a1", alert_type=AlertType.TRIP_DELAY,
                truck_id="T1", trip_id="101", message="Test delay",
                resolved=False):
    from services.operations.alert_manager import Alert
    return Alert(
        id=alert_id,
        type=alert_type,
        severity=Severity.WARNING,
        title="Test",
        message=message,
        truck_id=truck_id,
        trip_id=trip_id,
        resolved=resolved,
    )


class TestKillMutationFindDuplicate:
    """Mutation-killing tests for AlertManager._find_duplicate()."""

    def test_resolved_alerts_not_considered_duplicates(self):
        """Kill: 'a.resolved: continue' deletion (resolved alerts are skipped)."""
        resolved_alert = _make_alert(resolved=True)
        am = _build_am_with_alerts([resolved_alert])
        dup = am._find_duplicate(AlertType.TRIP_DELAY, "T1", "101")
        # resolved is skipped -> no duplicate found
        assert dup is None

    def test_different_type_not_duplicate(self):
        """Kill: 'a.type != alert_type: continue' inverted (different type -> no match)."""
        alert = _make_alert(alert_type=AlertType.MAINTENANCE)
        am = _build_am_with_alerts([alert])
        dup = am._find_duplicate(AlertType.TRIP_DELAY, "T1", "101")
        # MAINTENANCE != TRIP_DELAY -> continue -> no match
        # If '!=' is mutated to '==', MAINTENANCE == TRIP_DELAY is False
        # -> continue for wrong reason; but actually with '==', it would
        # continue only when types are EQUAL, so MAINTENANCE != TRIP_DELAY
        # would NOT continue -> match found (WRONG)
        assert dup is None

    def test_different_truck_not_duplicate(self):
        """Kill: 'a.truck_id != truck_id' -> '==' (different truck -> no match)."""
        alert = _make_alert(truck_id="T2")
        am = _build_am_with_alerts([alert])
        dup = am._find_duplicate(AlertType.TRIP_DELAY, "T1", "101")
        # "T2" != "T1" -> continue -> no match
        # If '!=' -> '==': "T2" == "T1" is False -> does NOT continue
        # -> match found (WRONG)
        assert dup is None

    def test_none_truck_id_matches_none(self):
        """Both truck_id are None -> should match."""
        alert = _make_alert(truck_id=None)
        am = _build_am_with_alerts([alert])
        dup = am._find_duplicate(AlertType.TRIP_DELAY, None, "101")
        # None != None is False -> does NOT continue -> type matches too -> found
        assert dup is not None
        assert dup.id == "a1"

    def test_different_trip_not_duplicate(self):
        """Kill: 'a.trip_id != trip_id' inverted (different trip -> no match)."""
        alert = _make_alert(trip_id="202")
        am = _build_am_with_alerts([alert])
        dup = am._find_duplicate(AlertType.TRIP_DELAY, "T1", "101")
        # "202" != "101" -> continue -> no match
        # If inverted: "202" == "101" is False -> does NOT continue -> match (WRONG)
        assert dup is None

    def test_first_match_returned_when_multiple(self):
        """Kill: returns the FIRST matching alert (early return), not the last."""
        alert1 = _make_alert(alert_id="a1", message="First")
        alert2 = _make_alert(alert_id="a2", message="Second")
        am = _build_am_with_alerts([alert1, alert2])
        dup = am._find_duplicate(AlertType.TRIP_DELAY, "T1", "101")
        # Both match (type, truck_id, trip_id are the same), should return a1 (first)
        assert dup is not None
        assert dup.id == "a1"
        assert dup.message == "First"

    def test_exact_match_finds_duplicate(self):
        """All fields match -> duplicate alert returned."""
        alert = _make_alert()
        am = _build_am_with_alerts([alert])
        dup = am._find_duplicate(AlertType.TRIP_DELAY, "T1", "101")
        assert dup is not None
        assert dup.id == "a1"

    def test_create_resolve_create_same_alert_resolved_not_blocking(self):
        """Create + resolve + create same alert: resolved alert is not blocking.

        After resolving an alert, creating the same alert again should
        succeed (resolved alerts are not considered duplicates).
        """
        AlertManager._instance = None
        AlertManager._lock = threading.Lock()

        mgr = AlertManager(db=None)

        # Create an alert
        alert1 = mgr.create_alert(
            AlertType.TRIP_DELAY, Severity.WARNING,
            "Test", "Same message", truck_id="T1", trip_id="101",
        )
        assert alert1 is not None
        assert alert1.resolved is False

        # Resolve it
        mgr.resolve_alert(alert1.id)
        assert alert1.resolved is True

        # Create the same alert again — should succeed, not return the old one
        alert2 = mgr.create_alert(
            AlertType.TRIP_DELAY, Severity.WARNING,
            "Test", "Same message", truck_id="T1", trip_id="101",
        )
        assert alert2 is not None
        assert alert2.id != alert1.id  # different alert, not duplicate


def _build_am_with_alerts(alerts):
    """Helper: create a fresh AlertManager and populate _alerts."""
    AlertManager._instance = None
    AlertManager._lock = threading.Lock()
    mgr = AlertManager(db=None)
    mgr._alerts.clear()
    for a in alerts:
        mgr._alerts[a.id] = a
    return mgr
