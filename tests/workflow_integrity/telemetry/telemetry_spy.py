"""TelemetrySpy — in-process, schema-aware recorder for every EventBus event.

Complementary to ``EventMonitor`` and ``TelemetryCollector``: those collect
only what you explicitly ``track()`` (or a fixed required list).  This spy
subscribes to *every* known event type up front and records timestamped
captures using a monotonic clock, so tests can assert counts, relative
ordering, payload schemas (delegating to ``event_catalog.validate_event``)
and latency (derived from the stored monotonic timestamps).

The EventBus has no wildcard subscription, so "all events" is implemented
as the subscribe-all pattern from ``EventMonitor.track_all``: iterate
``services.operations.event_bus.ALL_EVENTS`` and additionally union in the
catalog's event names when ``event_catalog`` is available (the bus's
``subscribe`` tolerates names outside ``ALL_EVENTS``).  Capture happens
in-process and synchronously — once ``publish`` returns, every subscriber
has already run, so no timeout/polling is needed.

Usage::

    spy = TelemetrySpy(event_bus)              # subscribes to all events
    event_bus.publish("trip.created", {"id": 1})
    event_bus.publish("workflow.started", {"trip_id": 1})

    spy.assert_events("trip.created", "workflow.started")   # count >= 1, order
    spy.assert_events(("trip.created", 1))                  # exact count
    spy.assert_schema("trip.created")                       # event_catalog
    latency_ms = spy.query_latency_ms("trip.created")
"""

from __future__ import annotations

import time
from typing import Any, Iterable

from services.operations.event_bus import ALL_EVENTS, EventBus


def _catalog_event_names() -> list[str]:
    """Event names declared by ``event_catalog``, or ``[]`` if unavailable.

    ``event_catalog.py`` (EVENT_CATALOG + validate_event) is delivered by a
    sibling unit; the spy must not hard-depend on it, so the union is best
    effort.  If ``EVENT_CATALOG`` is a dict, its keys are used; if it is a
    list/set/tuple of names, its items are used.
    """
    try:
        from tests.workflow_integrity.telemetry.event_catalog import EVENT_CATALOG
    except ImportError:
        return []
    if isinstance(EVENT_CATALOG, dict):
        return list(EVENT_CATALOG.keys())
    if isinstance(EVENT_CATALOG, (list, tuple, set)):
        return list(EVENT_CATALOG)
    return []


class TelemetrySpy:
    """Subscribes to every EventBus event and records timestamped captures.

    Each capture is a dict::

        {
            "event":     <the full EventBus event dict>,
            "type":      <event type>,
            "data":      <event payload (dict)>,
            "captured_at": <time.time() wall-clock capture time>,
            "monotonic":   <time.monotonic() capture timestamp>,
        }

    ``monotonic`` is what ``query_latency_ms`` is derived from.
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus if event_bus is not None else EventBus()
        self._captures: list[dict[str, Any]] = []
        self._subscribed = False
        self.start()

    # ── Subscription ──────────────────────────────────────────────

    def start(self) -> None:
        """(Re-)subscribe to every known event type and clear captures.

        Safe to call after ``EventBus.reset()`` — it re-registers the spy
        callback for all event types on the same bus instance.
        """
        event_types: set[str] = set(ALL_EVENTS)
        event_types.update(_catalog_event_names())
        if not self._subscribed:
            for evt in event_types:
                self._bus.subscribe(evt, self._collect)
            self._subscribed = True
        self._captures.clear()

    def _collect(self, event: dict[str, Any]) -> None:
        self._captures.append(
            {
                "event": event,
                "type": event["type"],
                "data": event.get("data", {}),
                "captured_at": time.time(),
                "monotonic": time.monotonic(),
            }
        )

    # ── Getters ───────────────────────────────────────────────────

    def get_captures(self, event_type: str | None = None) -> list[dict[str, Any]]:
        """Return all captures, optionally filtered by event type."""
        if event_type is None:
            return list(self._captures)
        return [c for c in self._captures if c["type"] == event_type]

    def captured_types(self) -> list[str]:
        """Ordered event types as captured."""
        return [c["type"] for c in self._captures]

    def count(self, event_type: str | None = None) -> int:
        """Number of captures, optionally for one event type."""
        return len(self.get_captures(event_type))

    def clear(self) -> None:
        """Reset captures without unsubscribing."""
        self._captures.clear()

    def __len__(self) -> int:
        return len(self._captures)

    # ── Assertions ────────────────────────────────────────────────

    def assert_events(self, *names: str | tuple[str, int], order: bool = True) -> TelemetrySpy:
        """Assert captures for the given events (counts + relative order).

        Each element of ``*names`` is either:

        * an event name (``str``)        → at least one capture required, or
        * a ``(name, count)`` tuple      → exactly ``count`` captures required.

        When ``order`` is True (default), the names must appear in this
        relative order in the captured stream (a subsequence match — other
        events may be interleaved).

        Returns ``self`` for chaining.
        """
        specs: list[tuple[str, int | None]] = []
        for item in names:
            if isinstance(item, str):
                specs.append((item, None))
            elif (
                isinstance(item, (tuple, list))
                and len(item) == 2
                and isinstance(item[0], str)
            ):
                specs.append((item[0], item[1]))
            else:
                raise TypeError(
                    f"assert_events expects event names or (name, count) tuples, "
                    f"got {item!r}"
                )

        # ── Counts ──
        actual_counts = {t: self.count(t) for t, _ in specs}
        failures: list[str] = []
        for name, required in specs:
            actual = actual_counts[name]
            if required is None:
                if actual < 1:
                    failures.append(
                        f"expected at least 1 '{name}' capture, found {actual}"
                    )
            elif actual != required:
                failures.append(
                    f"expected exactly {required} '{name}' captures, found {actual}"
                )

        # ── Order (subsequence over the captured type stream) ──
        if order and not failures and len(specs) > 1:
            captured = self.captured_types()
            si = 0
            for ct in captured:
                if si >= len(specs):
                    break
                if ct == specs[si][0]:
                    si += 1
            if si < len(specs):
                failures.append(
                    f"expected order {[s[0] for s in specs]!r} not observed "
                    f"in captured sequence {captured!r}"
                )

        if failures:
            raise AssertionError("TelemetrySpy.assert_events failed:\n  " + "\n  ".join(failures))
        return self

    def assert_schema(self, event_name: str, data: dict[str, Any] | None = None) -> TelemetrySpy:
        """Validate event payload schemas via ``event_catalog.validate_event``.

        If ``data`` is given, validates the payload shape
        ``{"event_name": event_name, **data}`` directly.  Otherwise it
        validates every captured event of ``event_name``, converting each
        capture to the catalog's flat shape (``{"event_name": <type>,
        **<payload>}``).  Fails early with a clear message if nothing was
        captured.

        Delegates to ``tests.workflow_integrity.telemetry.event_catalog.validate_event``,
        which returns the list of required fields missing from an event; an
        empty list means the event satisfies its catalogued schema.  Events
        not in the mandatory catalog are out of scope (``validate_event``
        returns ``[]``) and therefore pass.

        Returns ``self`` for chaining.
        """
        try:
            from tests.workflow_integrity.telemetry.event_catalog import validate_event
        except ImportError as exc:  # pragma: no cover — depends on sibling unit
            raise AssertionError(
                "assert_schema requires tests/workflow_integrity/telemetry/"
                "event_catalog.py (EVENT_CATALOG + validate_event), which is not "
                f"importable: {exc}"
            ) from exc

        if data is not None:
            targets: list[dict[str, Any]] = [{"event_name": event_name, **data}]
        else:
            captures = self.get_captures(event_name)
            if not captures:
                raise AssertionError(
                    f"assert_schema({event_name!r}): no captured events of that type "
                    f"(captured types: {self.captured_types()!r})"
                )
            targets = [{"event_name": c["type"], **c["data"]} for c in captures]

        for catalog_event in targets:
            missing = validate_event(catalog_event)
            if missing:
                raise AssertionError(
                    f"event {catalog_event['event_name']!r} failed schema validation; "
                    f"missing required fields: {missing}"
                )
        return self

    def assert_not_captured(self, event_type: str) -> TelemetrySpy:
        """Assert no event of *event_type* was captured."""
        n = self.count(event_type)
        if n > 0:
            raise AssertionError(
                f"Expected no '{event_type}' captures, but found {n}: "
                f"{self.get_captures(event_type)!r}"
            )
        return self

    # ── Latency ───────────────────────────────────────────────────

    def query_latency_ms(
        self, event_name: str, start_event: str | None = None
    ) -> float:
        """Elapsed milliseconds between captures, from monotonic timestamps.

        Default: the span from the first to the last capture of
        ``event_name`` (0.0 if fewer than two, or none at all).

        With ``start_event``: the span from the *first* capture of
        ``start_event`` to the *last* capture of ``event_name`` — useful for
        measuring a cross-event operation (e.g. ``workflow.started`` →
        ``workflow.completed``).  Returns 0.0 if either side is absent.
        """
        caps = self.get_captures(event_name)
        if not caps:
            return 0.0
        if start_event is not None:
            starts = self.get_captures(start_event)
            if not starts:
                return 0.0
            start_ts = starts[0]["monotonic"]
        else:
            start_ts = caps[0]["monotonic"]
        return (caps[-1]["monotonic"] - start_ts) * 1000.0