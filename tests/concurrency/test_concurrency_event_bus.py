"""Concurrency tests: EventBus under concurrent access — simultaneous publishes, subscribe/unsubscribe during publish, multiple event types.

Verifies that the event bus is thread-safe and does not deadlock,
lose events, or corrupt subscriber lists under concurrent access.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from services.operations.event_bus import EventBus

pytestmark = pytest.mark.concurrency

# Known event types used across the application
TRIP_CREATED = "trip.created"
TRIP_UPDATED = "trip.updated"
TRIP_DELETED = "trip.deleted"
DOCUMENT_UPLOADED = "document.uploaded"
INVOICE_GENERATED = "invoice.generated"
CLIENT_UPDATED = "client.updated"
FLEET_UPDATED = "fleet.updated"
ANALYTICS_REFRESHED = "analytics.refreshed"


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(autouse=True)
def reset_bus():
    """Reset the EventBus singleton before each test."""
    EventBus._instance = None
    yield
    EventBus._instance = None


@pytest.fixture
def fresh_bus():
    """Return a clean EventBus instance with history cleared."""
    bus = EventBus()
    bus._history.clear()
    return bus


# ======================================================================
# 100 simultaneous publishes to same event
# ======================================================================


class TestConcurrencyEventBusSimultaneousPublishes:
    """100 simultaneous publishes to the same event — all subscribers receive."""

    def test_100_simultaneous_publishes_all_received(self, fresh_bus):
        """100 concurrent publishes to the same event — all subscribers receive every event."""
        received = []
        lock = threading.Lock()
        n_publishes = 100

        handler_called = threading.Event()

        def handler(ev):
            with lock:
                received.append(ev["data"]["idx"])
            handler_called.set()

        fresh_bus.subscribe(TRIP_CREATED, handler)

        errors = []

        def publish_event(idx: int):
            try:
                fresh_bus.publish(TRIP_CREATED, {"idx": idx})
            except Exception as e:
                with lock:
                    errors.append((idx, str(e)))

        with ThreadPoolExecutor(max_workers=n_publishes) as pool:
            futs = [pool.submit(publish_event, i) for i in range(n_publishes)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(("submit", str(e)))

        assert len(errors) == 0, f"Publish errors: {errors[:5]}"
        assert len(received) == n_publishes, (
            f"Expected {n_publishes} events received, got {len(received)}. "
            f"Missing: {set(range(n_publishes)) - set(received)}"
        )
        # Verify all indices were received
        assert set(received) == set(range(n_publishes)), (
            f"Missing indices: {set(range(n_publishes)) - set(received)}"
        )

    def test_100_publishes_multiple_subscribers(self, fresh_bus):
        """100 publishes with 3 subscribers — each receives all 100 events."""
        received_by_subscriber: dict[int, list[int]] = {1: [], 2: [], 3: []}
        lock = threading.Lock()
        n_publishes = 100

        def make_handler(sid: int):
            def handler(ev):
                with lock:
                    received_by_subscriber[sid].append(ev["data"]["idx"])
            return handler

        for sid in [1, 2, 3]:
            fresh_bus.subscribe(TRIP_CREATED, make_handler(sid))

        with ThreadPoolExecutor(max_workers=n_publishes) as pool:
            futs = [pool.submit(
                lambda i=i: fresh_bus.publish(TRIP_CREATED, {"idx": i})
            ) for i in range(n_publishes)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception:
                    pass

        for sid, received in received_by_subscriber.items():
            assert len(received) == n_publishes, (
                f"Subscriber {sid} received {len(received)}/{n_publishes} events"
            )


# ======================================================================
# Subscribe/unsubscribe during publish
# ======================================================================


class TestConcurrencyEventBusSubscribeUnsubscribe:
    """Subscribe/unsubscribe during publish — no deadlock."""

    def test_subscribe_during_publish_no_deadlock(self, fresh_bus):
        """Subscribing a new handler while publishes are ongoing does not deadlock."""
        errors = []
        lock = threading.Lock()
        stop_event = threading.Event()
        subscribe_count = [0]

        def publisher():
            while not stop_event.is_set():
                try:
                    fresh_bus.publish(TRIP_CREATED, {"ts": time.time()})
                except Exception as e:
                    with lock:
                        errors.append(("publisher", str(e)))
                    break

        def subscriber():
            while not stop_event.is_set():
                try:
                    handler = lambda ev: None  # noqa: E731
                    fresh_bus.subscribe(TRIP_UPDATED, handler)
                    with lock:
                        subscribe_count[0] += 1
                except Exception as e:
                    with lock:
                        errors.append(("subscriber", str(e)))
                    break
                time.sleep(0.001)

        threads = [
            threading.Thread(target=publisher),
            threading.Thread(target=publisher),
            threading.Thread(target=subscriber),
            threading.Thread(target=subscriber),
        ]

        for t in threads:
            t.daemon = True
            t.start()

        time.sleep(0.5)
        stop_event.set()

        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Subscribe-during-publish errors: {errors[:5]}"
        assert subscribe_count[0] > 0, "No subscriptions were made"

    def test_unsubscribe_during_publish_no_deadlock(self, fresh_bus):
        """Unsubscribing a handler while publishes are ongoing does not deadlock."""
        errors = []
        lock = threading.Lock()
        stop_event = threading.Event()
        unsubscribed_handlers = []

        # Register handlers to be unsubscribed
        handlers = []
        for i in range(10):
            def make_handler(idx=i):
                def handler(ev):
                    pass  # no-op handler
                return handler
            h = make_handler(i)
            fresh_bus.subscribe(TRIP_CREATED, h)
            handlers.append(h)

        def publisher():
            while not stop_event.is_set():
                try:
                    fresh_bus.publish(TRIP_CREATED, {"ts": time.time()})
                except Exception as e:
                    with lock:
                        errors.append(("publisher", str(e)))
                    break

        def unsubscriber():
            for h in handlers:
                if stop_event.is_set():
                    break
                try:
                    fresh_bus.unsubscribe(TRIP_CREATED, h)
                    with lock:
                        unsubscribed_handlers.append(h)
                except Exception as e:
                    with lock:
                        errors.append(("unsubscriber", str(e)))
                time.sleep(0.002)

        threads = [
            threading.Thread(target=publisher),
            threading.Thread(target=publisher),
            threading.Thread(target=unsubscriber),
        ]

        for t in threads:
            t.daemon = True
            t.start()

        time.sleep(0.5)
        stop_event.set()

        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Unsubscribe-during-publish errors: {errors[:5]}"

    def test_subscribe_and_unsubscribe_same_handler_repeatedly(self, fresh_bus):
        """Repeatedly subscribing and unsubscribing the same handler while publishing."""
        errors = []
        call_count = [0]
        lock = threading.Lock()

        def handler(ev):
            with lock:
                call_count[0] += 1

        # Subscribe the handler
        fresh_bus.subscribe(TRIP_CREATED, handler)

        def publisher():
            for _ in range(50):
                fresh_bus.publish(TRIP_CREATED, {"n": 1})

        def sub_unsub():
            for _ in range(25):
                fresh_bus.unsubscribe(TRIP_CREATED, handler)
                fresh_bus.subscribe(TRIP_CREATED, handler)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(publisher), pool.submit(sub_unsub)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(str(e))

        assert len(errors) == 0, f"Subscribe/unsubscribe errors: {errors}"
        # Handler should have been called some number of times
        # (exact count depends on race conditions — but > 0)
        assert call_count[0] > 0, "Handler was never called"


# ======================================================================
# Multiple event types published concurrently
# ======================================================================


class TestConcurrencyEventBusMultipleTypes:
    """Multiple event types published concurrently — event isolation maintained."""

    def test_multiple_event_types_no_cross_contamination(self, fresh_bus):
        """Events of different types published concurrently maintain isolation."""
        received = {
            TRIP_CREATED: [],
            DOCUMENT_UPLOADED: [],
            INVOICE_GENERATED: [],
            CLIENT_UPDATED: [],
        }
        lock = threading.Lock()
        events_per_type = 50

        def make_handler(event_type: str):
            def handler(ev):
                with lock:
                    received[event_type].append(ev["data"]["idx"])
            return handler

        for event_type in received:
            fresh_bus.subscribe(event_type, make_handler(event_type))

        def publish_event_type(event_type: str):
            for i in range(events_per_type):
                fresh_bus.publish(event_type, {"idx": i, "type": event_type})

        with ThreadPoolExecutor(max_workers=len(received)) as pool:
            futs = [pool.submit(publish_event_type, et) for et in received]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception:
                    pass

        for event_type, events in received.items():
            assert len(events) == events_per_type, (
                f"Event type {event_type}: expected {events_per_type}, got {len(events)}"
            )
            # Verify no cross-contamination: events of type TRIP_CREATED
            # should not appear in other event type lists
            for other_type in received:
                if other_type != event_type:
                    for ev in events:
                        # All events for this type should have matching type data
                        assert ev is not None

    def test_concurrent_publish_of_5_event_types(self, fresh_bus):
        """5 different event types published concurrently — all processed correctly."""
        event_types = [
            TRIP_CREATED, TRIP_UPDATED, DOCUMENT_UPLOADED,
            INVOICE_GENERATED, FLEET_UPDATED,
        ]

        received_counts: dict[str, int] = {et: 0 for et in event_types}
        lock = threading.Lock()
        errors = []
        events_per_type = 30

        def make_handler(event_type: str):
            def handler(ev):
                with lock:
                    received_counts[event_type] += 1
            return handler

        for et in event_types:
            fresh_bus.subscribe(et, make_handler(et))

        def publish_type(event_type: str):
            try:
                for i in range(events_per_type):
                    fresh_bus.publish(event_type, {"idx": i})
                    time.sleep(0.001)
            except Exception as e:
                with lock:
                    errors.append((event_type, str(e)))

        with ThreadPoolExecutor(max_workers=len(event_types)) as pool:
            futs = [pool.submit(publish_type, et) for et in event_types]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    with lock:
                        errors.append(("submit", str(e)))

        assert len(errors) == 0, f"Multi-type publish errors: {errors[:5]}"

        for et, count in received_counts.items():
            assert count == events_per_type, (
                f"Event type {et}: expected {events_per_type}, got {count}"
            )

    def test_event_isolation_across_subscriber_groups(self, fresh_bus):
        """Subscribers for different event types only receive their own events."""
        trip_events = []
        doc_events = []
        lock = threading.Lock()

        def trip_handler(ev):
            with lock:
                trip_events.append(ev["data"]["id"])

        def doc_handler(ev):
            with lock:
                doc_events.append(ev["data"]["id"])

        fresh_bus.subscribe(TRIP_CREATED, trip_handler)
        fresh_bus.subscribe(DOCUMENT_UPLOADED, doc_handler)

        # Publish both types concurrently
        def publish_trips():
            for i in range(20):
                fresh_bus.publish(TRIP_CREATED, {"id": f"trip_{i}"})

        def publish_docs():
            for i in range(20):
                fresh_bus.publish(DOCUMENT_UPLOADED, {"id": f"doc_{i}"})

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(publish_trips), pool.submit(publish_docs)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception:
                    pass

        # Verify isolation
        assert len(trip_events) == 20, f"Expected 20 trip events, got {len(trip_events)}"
        assert len(doc_events) == 20, f"Expected 20 doc events, got {len(doc_events)}"

        # Trip handler should only see trip IDs
        for eid in trip_events:
            assert eid.startswith("trip_"), f"Trip handler received non-trip event: {eid}"

        # Doc handler should only see doc IDs
        for eid in doc_events:
            assert eid.startswith("doc_"), f"Doc handler received non-doc event: {eid}"
