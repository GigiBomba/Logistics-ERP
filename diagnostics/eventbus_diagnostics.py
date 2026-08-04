"""EventBus Diagnostics Probe — monitor EventBus publish/subscribe timing.

Monkey-patches ``services.operations.event_bus.EventBus.publish`` and
``EventBus.subscribe`` at the class level to measure handler execution
time, detect slow handlers, track publish rates, and identify event storms.

**NOTE**: EventBus is a singleton (thread-safe with Lock). Monkey-patching
at the class level affects ALL instances including ``shared_event_bus``.

Detection events
----------------
- ``eventbus.handler_error`` — a subscriber callback raised an exception
- ``eventbus.slow_handler`` — a handler took >50 ms to execute
- ``eventbus.storm`` — >50 publishes of the same event type in 100 ms (debounced 5 s)

Metrics
-------
- ``eventbus.publish_count.<event_type>`` — incremental publish counter
- ``eventbus.handler_count.<event_type>`` — incremental handler-invocation counter
- ``eventbus.subscriber_count.<event_type>`` — incremental subscriber-registration counter
- ``eventbus.subscriber_total`` — current total subscriber count across all event types
- Spans recorded for publishes taking >10 ms
- Spans recorded for handlers taking >50 ms
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable

from diagnostics.models import DiagnosticCategory, Span, Event
from diagnostics.store import DiagnosticStore

logger = logging.getLogger("diagnostics.eventbus_diagnostics")


class EventBusProbe:
    """Monitors EventBus publish/subscribe timing, storms, and errors.

    Usage::

        probe = EventBusProbe(store)
        probe.install()     # patches EventBus.publish and EventBus.subscribe
        probe.sample()      # periodic check (called by engine)
        probe.uninstall()   # restores originals
    """

    sample_interval_s: float = 2.0

    def __init__(self, store: DiagnosticStore):
        self.store = store
        self._installed = False
        self._original_subscribe: Any = None
        self._original_publish: Any = None
        self._enabled = True

        # Lock protects all probe-level mutable state below.
        self._lock = threading.Lock()

        # Per-event-type rolling windows for storm detection
        self._publish_windows: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=100)
        )

        # Storm debounce: event_type -> last storm event time
        self._storm_debounce: dict[str, float] = {}

    # ── Install / Uninstall ──────────────────────────────────────────

    def install(self) -> None:
        """Monkey-patch ``EventBus.subscribe`` and ``EventBus.publish``."""
        if self._installed:
            return

        # Late import so the entire module doesn't fail if EventBus is unavailable
        from services.operations.event_bus import EventBus, shared_event_bus

        self._event_bus_cls = EventBus
        self._shared_event_bus = shared_event_bus
        self._original_subscribe = EventBus.subscribe
        self._original_publish = EventBus.publish
        probe = self
        store = self.store

        # ── Patched subscribe ───────────────────────────────────────
        @functools.wraps(self._original_subscribe)
        def _patched_subscribe(
            self: EventBus, event_type: str, callback: Callable
        ) -> None:
            handler_name = getattr(callback, "__name__", str(callback)[:50])
            store.increment(f"eventbus.subscriber_count.{event_type}")

            def _wrapped_callback(ev: dict[str, Any]) -> Any:
                if not probe._enabled:
                    return callback(ev)

                start = time.perf_counter()
                try:
                    return callback(ev)
                except Exception as exc:
                    store.record_event(Event(
                        name="eventbus.handler_error",
                        category=DiagnosticCategory.EVENT_BUS,
                        metadata={
                            "event_type": event_type,
                            "handler": handler_name,
                            "error": str(exc)[:100],
                        },
                    ))
                    raise
                finally:
                    elapsed = (time.perf_counter() - start) * 1000.0
                    store.increment(f"eventbus.handler_count.{event_type}")
                    if elapsed > 50.0:
                        end_time = time.perf_counter()
                        store.record_span(Span(
                            name=f"eventbus.handler.{event_type}.{handler_name}",
                            category=DiagnosticCategory.EVENT_BUS,
                            start_time=start,
                            end_time=end_time,
                            metadata={"elapsed_ms": round(elapsed, 2)},
                        ))
                        store.record_event(Event(
                            name="eventbus.slow_handler",
                            category=DiagnosticCategory.EVENT_BUS,
                            metadata={
                                "event_type": event_type,
                                "handler": handler_name,
                                "elapsed_ms": round(elapsed, 1),
                            },
                        ))

            return probe._original_subscribe(self, event_type, _wrapped_callback)

        # ── Patched publish ─────────────────────────────────────────
        @functools.wraps(self._original_publish)
        def _patched_publish(
            self: EventBus,
            event_type: str,
            data: dict[str, Any] | None = None,
            timestamp: str | None = None,
        ) -> None:
            if not probe._enabled:
                return probe._original_publish(
                    self, event_type, data, timestamp
                )

            start = time.perf_counter()
            subscriber_count = len(self._subscribers.get(event_type, []))
            store.increment(f"eventbus.publish_count.{event_type}")

            try:
                return probe._original_publish(
                    self, event_type, data, timestamp
                )
            finally:
                elapsed = (time.perf_counter() - start) * 1000.0

                # ── Span for slow publishes (>10 ms) ────────────────
                if elapsed > 10.0:
                    store.record_span(Span(
                        name=f"eventbus.publish.{event_type}",
                        category=DiagnosticCategory.EVENT_BUS,
                        start_time=start,
                        end_time=time.perf_counter(),
                        metadata={
                            "subscriber_count": subscriber_count,
                            "elapsed_ms": round(elapsed, 2),
                        },
                    ))

                # ── Storm detection ─────────────────────────────────
                now = time.perf_counter()
                window = probe._publish_windows[event_type]
                window.append(now)

                recent = sum(1 for t in window if now - t < 0.1)
                if recent > 50:
                    with probe._lock:
                        last_storm = probe._storm_debounce.get(event_type, 0.0)
                        if now - last_storm > 5.0:  # debounce 5 s
                            probe._storm_debounce[event_type] = now
                            store.record_event(Event(
                                name="eventbus.storm",
                                category=DiagnosticCategory.EVENT_BUS,
                                metadata={
                                    "event_type": event_type,
                                    "publishes_per_100ms": recent,
                                },
                            ))

        EventBus.subscribe = _patched_subscribe
        EventBus.publish = _patched_publish
        self._installed = True
        logger.info("[DIAG] EventBusProbe installed")

    def uninstall(self) -> None:
        """Restore original ``EventBus.subscribe`` and ``EventBus.publish``."""
        if self._installed:
            if self._original_subscribe is not None:
                self._event_bus_cls.subscribe = self._original_subscribe
            if self._original_publish is not None:
                self._event_bus_cls.publish = self._original_publish
            self._installed = False
            with self._lock:
                self._publish_windows.clear()
                self._storm_debounce.clear()
            logger.info("[DIAG] EventBusProbe uninstalled")

    # ── Sampling ─────────────────────────────────────────────────────

    def sample(self) -> None:
        """Periodic top-N and gauge reporting.

        Called by ``DiagnosticsEngine._sampler_loop`` every ~2 s.
        """
        try:
            # ── Top-5 most published event types ────────────────────
            counters = self.store.get_all_counters()
            publish_counts: list[tuple[str, int]] = []
            for key, val in counters.items():
                if key.startswith("eventbus.publish_count."):
                    publish_counts.append((key, val))

            publish_counts.sort(key=lambda x: x[1], reverse=True)
            for event_key, count in publish_counts[:5]:
                event_type = event_key.replace("eventbus.publish_count.", "", 1)
                self.store.set_gauge(
                    f"eventbus.publish_top.{event_type}", float(count)
                )

            # ── Top-5 slowest handlers (spans with category EVENT_BUS)
            slow_spans = self.store.get_spans(
                category=DiagnosticCategory.EVENT_BUS, limit=5
            )
            for i, span in enumerate(slow_spans):
                self.store.set_gauge(
                    f"eventbus.slow_handler_{i}_ms",
                    round(span.elapsed_ms, 1),
                )

            # ── Subscriber total (current count from EventBus instance)
            total_subscribers = sum(
                len(cbs) for cbs in self._shared_event_bus._subscribers.values()
            )
            self.store.set_gauge(
                "eventbus.subscriber_total", float(total_subscribers)
            )
        except Exception:
            logger.exception(
                "[DIAG] EventBusProbe.sample failed — suppressed"
            )
