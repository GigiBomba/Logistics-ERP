"""Telemetry fixtures — TelemetrySpy wired to the suite ``event_bus`` + fake store.

Two function-scoped pytest fixtures:

* ``telemetry_spy`` — a :class:`TelemetrySpy` subscribing to every EventBus
  event on the suite's ``event_bus`` fixture (see
  ``tests/workflow_integrity/conftest.py``), ready for TEL-16-style count /
  order / schema / latency assertions.
* ``fake_telemetry_store`` — a dict-backed :class:`FakeTelemetryStore`
  simulating the queryable telemetry store used by TEL-16 ("telemetry must
  be available for query within 30 seconds of event emission") assertions.

Tests request them by name::

    def test_telemetry_queryable(telemetry_spy, fake_telemetry_store, event_bus):
        event_bus.publish("workflow.started", {...})
        telemetry_spy.assert_events("workflow.started")
        fake_telemetry_store.record(telemetry_spy.get_captures("workflow.started")[0])
        assert fake_telemetry_store.count("workflow.started") == 1

Because pytest only auto-registers fixtures from conftest/plugin modules, a
test file that needs these fixtures by name must expose this module as a
plugin, e.g. at the top of the test module::

    pytest_plugins = ["tests.workflow_integrity.telemetry.fixtures"]

The underlying pieces (``TelemetrySpy``, ``FakeTelemetryStore``) are also
directly importable for helper-style use without pytest fixture resolution.
"""

from __future__ import annotations

from typing import Any, Iterable

import pytest

from tests.workflow_integrity.telemetry.telemetry_spy import TelemetrySpy

__all__ = [
    "telemetry_spy",
    "fake_telemetry_store",
    "FakeTelemetryStore",
]


class FakeTelemetryStore:
    """Dict-backed, queryable telemetry store for TEL-16-style assertions.

    Simulates the queryable telemetry store (TEL-16: "telemetry must be
    available for query within 30 seconds of event emission").  Records
    events keyed by event type in a plain dict and exposes the query/count
    surface a real store would offer, so tests can assert on stored
    telemetry without any persistence layer.

    Usage::

        store = FakeTelemetryStore()
        store.record({"type": "workflow.started", "data": {...}})
        assert store.count("workflow.started") == 1
        assert store.query("workflow.started")[0]["type"] == "workflow.started"
    """

    def __init__(self) -> None:
        self._events: dict[str, list[dict[str, Any]]] = {}

    def record(self, event: dict[str, Any]) -> None:
        """Store one event (a captured EventBus event dict)."""
        event_type = event.get("type")
        if event_type is None:
            raise ValueError(
                f"FakeTelemetryStore.record expects an event dict with a 'type' "
                f"key, got: {event!r}"
            )
        self._events.setdefault(event_type, []).append(dict(event))

    def record_many(self, events: Iterable[dict[str, Any]]) -> None:
        """Store several events in one call."""
        for event in events:
            self.record(event)

    def query(self, event_type: str | None = None) -> list[dict[str, Any]]:
        """Return stored events, optionally filtered by event type."""
        if event_type is None:
            return [e for bucket in self._events.values() for e in bucket]
        return list(self._events.get(event_type, []))

    def count(self, event_type: str | None = None) -> int:
        """Number of stored events, optionally for one event type."""
        return len(self.query(event_type))

    def types(self) -> list[str]:
        """Event types present in the store, in first-seen order."""
        return list(self._events.keys())

    def reset(self) -> None:
        """Drop all stored events."""
        self._events.clear()

    def __len__(self) -> int:
        return sum(len(bucket) for bucket in self._events.values())


@pytest.fixture
def telemetry_spy(event_bus):
    """Function-scoped TelemetrySpy wired to the suite ``event_bus``.

    Subscribes to every EventBus event on the conftest's fresh bus, so any
    publish made by the system under test is captured and assertable via
    ``assert_events`` / ``assert_schema`` / ``query_latency_ms``.
    """
    spy = TelemetrySpy(event_bus)
    yield spy
    spy.clear()


@pytest.fixture
def fake_telemetry_store():
    """Function-scoped dict-backed queryable store for TEL-16 assertions."""
    store = FakeTelemetryStore()
    yield store
    store.reset()