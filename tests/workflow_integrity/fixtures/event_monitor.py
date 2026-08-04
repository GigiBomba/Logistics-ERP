"""EventMonitor — optics on the EventBus for test assertions.

Wraps the singleton EventBus, subscribes to specified event types,
and collects published events in an ordered list.  Provides
assertion helpers so tests can verify correct event emission
without mocking.

Usage::

    def test_trip_archiving_emits_event(workflow_env, event_monitor):
        event_monitor.track("trip.archived")

        workflow_env.trip_service.archive(42)

        event_monitor.assert_event_published(
            "trip.archived",
            data={"id": 42},
            timeout=2.0,
        )
"""

from __future__ import annotations

import time
from typing import Any, Callable

from services.operations.event_bus import EventBus


class EventMonitor:
    """Collects and asserts on EventBus publications during a test.

    Call ``track(*event_types)`` to subscribe before exercising the
    system under test.  After the action, call assertion methods to
    verify which events were published, in what order, and with what
    data payloads.
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus if event_bus is not None else EventBus()
        self._collected: list[dict[str, Any]] = []
        self._subscribed: set[str] = set()

    # ── Subscriptions ───────────────────────────────────────────

    def track(self, *event_types: str) -> None:
        """Subscribe to one or more event types for collection.

        Safe to call multiple times — each event type is
        subscribed only once.
        """
        for evt in event_types:
            if evt not in self._subscribed:
                self._event_bus.subscribe(evt, self._collect)
                self._subscribed.add(evt)

    def track_all(self) -> None:
        """Subscribe to every known event type (expensive — prefer
        ``track`` with explicit types when possible)."""
        from services.operations.event_bus import ALL_EVENTS
        self.track(*ALL_EVENTS)

    def _collect(self, event: dict[str, Any]) -> None:
        self._collected.append(event)

    # ── Getters ─────────────────────────────────────────────────

    def get_events(self, event_type: str | None = None) -> list[dict]:
        """Return collected events, optionally filtered by type."""
        if event_type is None:
            return list(self._collected)
        return [e for e in self._collected if e["type"] == event_type]

    def clear(self) -> None:
        """Reset collected events without unsubscribing."""
        self._collected.clear()

    # ── Assertions ──────────────────────────────────────────────

    def assert_event_published(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        timeout: float = 0.0,
    ) -> None:
        """Assert an event of *event_type* was published.

        If *data* is given, also assert that the event payload
        contains every key-value pair in *data* (partial match).

        If *timeout* > 0, poll for up to *timeout* seconds for
        the event to arrive (useful when the event is published
        asynchronously).
        """
        deadline = time.time() + timeout if timeout > 0 else None
        while True:
            matches = self.get_events(event_type)
            if data is not None:
                matches = [e for e in matches if _dict_contains(e.get("data", {}), data)]
            if matches:
                return
            if deadline is not None and time.time() < deadline:
                time.sleep(0.05)
                continue
            break

        all_events_of_type = self.get_events(event_type)
        msg = (
            f"Expected event '{event_type}' was not published."
        )
        if data:
            msg += f"  Expected event payload containing: {data}"
        if all_events_of_type:
            msg += f"  Found {len(all_events_of_type)} events of this type but none matched the data filter."
        else:
            msg += f"  No events of type '{event_type}' were published at all."
            if self._collected:
                types_found = set(e["type"] for e in self._collected)
                msg += f"  Types that were published: {types_found}"
        raise AssertionError(msg)

    def assert_event_not_published(
        self, event_type: str
    ) -> None:
        """Assert no event of *event_type* was published."""
        count = len(self.get_events(event_type))
        if count > 0:
            raise AssertionError(
                f"Expected no '{event_type}' events, "
                f"but found {count}: {self.get_events(event_type)}"
            )

    def assert_event_count(
        self, event_type: str, count: int
    ) -> None:
        """Assert exactly *count* events of *event_type* were published."""
        actual = len(self.get_events(event_type))
        if actual != count:
            raise AssertionError(
                f"Expected {count} '{event_type}' events, "
                f"but found {actual}"
            )

    def assert_event_sequence(
        self, *event_types: str
    ) -> None:
        """Assert events were published in the given order.

        The collected list may contain other events interleaved
        between the expected ones — this is a subsequence check,
        not an exact contiguous match.
        """
        expected = list(event_types)
        collected_types = [e["type"] for e in self._collected]
        ei = 0
        for ct in collected_types:
            if ei >= len(expected):
                break
            if ct == expected[ei]:
                ei += 1
        if ei < len(expected):
            raise AssertionError(
                f"Expected event subsequence {expected} not found.  "
                f"Actual sequence: {collected_types}"
            )

    def __enter__(self) -> EventMonitor:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def _dict_contains(actual: dict, expected: dict) -> bool:
    """Return True if *actual* contains all key-value pairs in *expected*."""
    for k, v in expected.items():
        if k not in actual:
            return False
        if actual[k] != v:
            return False
    return True
