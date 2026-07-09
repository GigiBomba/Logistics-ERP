"""Tests for the centralized application state management."""
from __future__ import annotations

import logging
import threading

import pytest

from services.app_state import AppState


class TestAppState:
    """Test suite for AppState singleton."""

    def test_singleton_returns_same_instance(self):
        a = AppState()
        b = AppState()
        assert a is b

    def test_get_returns_default_when_missing(self):
        state = AppState()
        assert state.get("nonexistent") is None

    def test_get_returns_custom_default(self):
        state = AppState()
        assert state.get("nonexistent", 42) == 42

    def test_set_and_get_roundtrip(self):
        state = AppState()
        state.set("key1", "value1")
        assert state.get("key1") == "value1"

    def test_set_overwrites_previous(self):
        state = AppState()
        state.set("key", "first")
        state.set("key", "second")
        assert state.get("key") == "second"

    def test_subscribe_receives_notification(self):
        state = AppState()
        received = []
        state.subscribe("key", lambda v: received.append(v))
        state.set("key", "hello")
        assert received == ["hello"]

    def test_subscribe_multiple_callbacks(self):
        state = AppState()
        received1 = []
        received2 = []
        state.subscribe("key", lambda v: received1.append(v))
        state.subscribe("key", lambda v: received2.append(v))
        state.set("key", "val")
        assert received1 == ["val"]
        assert received2 == ["val"]

    def test_unsubscribe_stops_receiving(self):
        state = AppState()
        received = []
        cb = lambda v: received.append(v)
        state.subscribe("key", cb)
        state.unsubscribe("key", cb)
        state.set("key", "val")
        assert received == []

    def test_unsubscribe_unknown_key_no_error(self):
        state = AppState()
        # Should not raise even though key/callback don't exist
        state.unsubscribe("nonexistent", lambda v: None)

    def test_subscriber_exception_is_logged(self, caplog):
        state = AppState()

        def broken_cb(value):
            raise RuntimeError("boom")

        state.subscribe("key", broken_cb)
        with caplog.at_level(logging.WARNING):
            state.set("key", "val")
        assert "AppState listener failed for 'key'" in caplog.text

    @pytest.mark.slow
    def test_thread_safe_concurrent_set_get(self):
        state = AppState()
        n_threads = 10
        n_ops = 100
        errors = []

        def worker():
            for i in range(n_ops):
                try:
                    state.set("shared", i)
                    state.get("shared")
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_subscribe_separate_keys_isolated(self):
        state = AppState()
        received_a = []
        received_b = []
        state.subscribe("a", lambda v: received_a.append(v))
        state.subscribe("b", lambda v: received_b.append(v))
        state.set("a", "A")
        state.set("b", "B")
        assert received_a == ["A"]
        assert received_b == ["B"]
