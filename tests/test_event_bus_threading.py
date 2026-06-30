"""Thread-safety tests for EventBus under concurrent access."""
import threading
import time
import unittest
from unittest.mock import Mock

from services.operations.event_bus import EventBus, TRIP_CREATED, TRIP_UPDATED


class TestEventBusConcurrentPublish(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self._original = dict(self.bus._subscribers)

    def tearDown(self):
        self.bus._subscribers = self._original

    def test_concurrent_publish_from_multiple_threads(self):
        received = []
        lock = threading.Lock()
        start_event = threading.Event()

        def handler(ev):
            with lock:
                received.append(ev["type"])

        self.bus.subscribe(TRIP_CREATED, handler)

        def publisher():
            start_event.wait()
            for _ in range(20):
                self.bus.publish(TRIP_CREATED, {"trip_id": 1})

        threads = [threading.Thread(target=publisher) for _ in range(5)]
        for t in threads:
            t.start()
        start_event.set()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(received), 100)

    def test_concurrent_subscribe_and_publish_no_crash(self):
        errors = []
        barrier = threading.Barrier(20)

        def publisher():
            barrier.wait()
            for _ in range(20):
                self.bus.publish(TRIP_UPDATED, {"trip_id": 1})

        def subscriber():
            barrier.wait()
            for _ in range(20):
                try:
                    self.bus.subscribe(TRIP_UPDATED, lambda ev: None)
                except Exception as e:
                    errors.append(e)

        threads = []
        for _ in range(10):
            threads.append(threading.Thread(target=publisher))
            threads.append(threading.Thread(target=subscriber))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Errors during concurrent access: {errors}")

    def test_concurrent_unsubscribe_during_publish(self):
        errors = []
        barrier = threading.Barrier(10)

        def make_handler(i):
            def handler(ev):
                time.sleep(0.001)
            return handler

        handlers = [make_handler(i) for i in range(10)]
        for h in handlers:
            self.bus.subscribe(TRIP_CREATED, h)

        def remover():
            barrier.wait()
            try:
                self.bus.unsubscribe(TRIP_CREATED, handlers[0])
            except Exception as e:
                errors.append(e)

        def publisher():
            barrier.wait()
            for _ in range(50):
                self.bus.publish(TRIP_CREATED, {"trip_id": 1})

        threads = [threading.Thread(target=remover) for _ in range(2)]
        threads.append(threading.Thread(target=publisher))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Errors during concurrent unsubscribe: {errors}")

    def test_publish_with_no_subscribers_does_not_raise(self):
        try:
            self.bus.publish(TRIP_CREATED, {"trip_id": 1})
        except Exception as e:
            self.fail(f"Publish with no subscribers raised: {e}")

    def test_publish_to_subscriber_that_raises_does_not_crash_bus(self):
        def failing_handler(ev):
            raise RuntimeError("expected test error")

        self.bus.subscribe(TRIP_CREATED, failing_handler)

        try:
            self.bus.publish(TRIP_CREATED, {"trip_id": 1})
        except Exception as e:
            self.fail(f"Subscriber exception propagated: {e}")

    def test_subscribe_same_callback_twice_called_twice(self):
        count = [0]

        def handler(ev):
            count[0] += 1

        self.bus.subscribe(TRIP_CREATED, handler)
        self.bus.subscribe(TRIP_CREATED, handler)

        self.bus.publish(TRIP_CREATED, {"trip_id": 1})
        self.assertEqual(count[0], 2)

    def test_history_trimming_maintains_recent(self):
        for i in range(200):
            self.bus.publish(TRIP_CREATED, {"trip_id": i})

        history = self.bus.get_history()
        self.assertLessEqual(len(history), 100)
        self.assertEqual(history[-1]["data"]["trip_id"], 199)


if __name__ == "__main__":
    unittest.main()
