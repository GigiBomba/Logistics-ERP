"""Tests for ui.base_view — the foundational BaseView lifecycle class."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, call, patch

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from ui.base_view import BaseView


# ── Test host that overrides lifecycle hooks for verification ──────────────


class _TestView(BaseView):
    """Concrete BaseView that records lifecycle hook calls."""

    def __init__(self, parent=None):
        self._build_called = False
        self._load_called = False
        self._shutdown_called = False
        super().__init__(parent)

    def _build_ui(self):
        self._build_called = True

    def _load_data(self):
        self._load_called = True

    def _on_shutdown(self):
        self._shutdown_called = True


class _CrashingView(BaseView):
    """View whose _on_shutdown raises to test exception swallowing."""

    def _on_shutdown(self):
        raise RuntimeError("forced shutdown failure")


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def view(qtbot):
    v = _TestView()
    qtbot.addWidget(v)
    return v


# ── Initialisation ───────────────────────────────────────────────────────────


class TestInit:
    def test_default_state(self, view):
        assert view._shutdown_flag is False
        assert view._subs == []
        assert view._timers == []
        assert view._i18n_id is None

    def test_event_bus_shared(self, view):
        from services.operations.event_bus import shared_event_bus
        assert view._event_bus is shared_event_bus

    def test_is_qscrollarea(self, view):
        assert isinstance(view, BaseView)

    def test_parent_assignment(self, qtbot):
        parent = QWidget()
        v = _TestView(parent)
        qtbot.addWidget(v)
        assert v.parent() is parent
        # Keep parent alive until after test teardown
        self._saved_parent = parent

    def test_no_auto_build_ui(self, qtbot):
        """_build_ui must be called by subclass, not by BaseView.__init__."""
        with patch.object(BaseView, "_build_ui") as mock:
            v = _TestView()
            qtbot.addWidget(v)
            mock.assert_not_called()

    def test_no_auto_load_data(self, qtbot):
        with patch.object(BaseView, "_load_data") as mock:
            v = _TestView()
            qtbot.addWidget(v)
            mock.assert_not_called()


# ── wakeup ───────────────────────────────────────────────────────────────────


class TestWakeup:
    def test_calls_load_data(self, view, qtbot):
        view.wakeup()
        # _load_data_async -> _load_data runs via queued timers; wait until it
        # fires instead of a fixed 50 ms sleep (races loaded CI runners).
        qtbot.waitUntil(lambda: view._load_called, timeout=10000)

    def test_noop_after_shutdown(self, view, qtbot):
        view.shutdown()
        view._load_called = False
        view.wakeup()
        qtbot.wait(100)
        assert not view._load_called


# ── shutdown ─────────────────────────────────────────────────────────────────


class TestShutdown:
    def test_sets_flag(self, view):
        view.shutdown()
        assert view._shutdown_flag is True

    def test_idempotent(self, view):
        view.shutdown()
        view._shutdown_called = False
        view.shutdown()
        assert not view._shutdown_called

    def test_calls_on_shutdown(self, view):
        view.shutdown()
        assert view._shutdown_called

    def test_stops_timers(self, view, qtbot):
        cb = MagicMock()
        timer = view._add_timer(100, cb)
        view.shutdown()
        assert not timer.isActive()

    def test_unsubscribes_event_bus(self, view):
        cb = MagicMock()
        bus = view._event_bus
        view._subscribe("test_event", cb)
        bus.publish("test_event", {"k": "v"})
        assert cb.call_count == 1

        view.shutdown()
        cb.reset_mock()
        bus.publish("test_event", {"k": "v2"})
        assert cb.call_count == 0

    def test_unregisters_i18n(self, view):
        cb = MagicMock()
        view._register_i18n(cb)
        from services.i18n import _listeners
        assert cb in _listeners

        view.shutdown()
        assert cb not in _listeners

    def test_clears_subs_list(self, view):
        cb = MagicMock()
        view._subscribe("e", cb)
        view.shutdown()
        assert view._subs == []

    def test_clears_timers_list(self, view):
        view._add_timer(1000, MagicMock())
        view.shutdown()
        assert view._timers == []

    def test_clears_i18n_id(self, view):
        cb = MagicMock()
        view._register_i18n(cb)
        view.shutdown()
        assert view._i18n_id is None

    def test_on_shutdown_exception_swallowed(self, caplog):
        v = _CrashingView()
        caplog.set_level(logging.ERROR)
        v.shutdown()
        assert v._shutdown_flag is True
        assert "forced shutdown failure" in caplog.text

    def test_timer_stop_exception_swallowed(self, view):
        bad_timer = MagicMock(spec=QTimer)
        bad_timer.stop.side_effect = RuntimeError("timer dead")
        view._timers.append(bad_timer)
        view.shutdown()
        assert view._shutdown_flag is True

    def test_unsubscribe_exception_swallowed(self, view):
        bus = view._event_bus
        cb = MagicMock()
        view._subscribe("e", cb)
        bus.unsubscribe = MagicMock(side_effect=RuntimeError("bus dead"))
        view.shutdown()
        assert view._shutdown_flag is True

    def test_i18n_unregister_exception_swallowed(self, view):
        cb = MagicMock()
        view._register_i18n(cb)
        with patch("ui.base_view.unregister_listener", side_effect=RuntimeError("i18n dead")):
            view.shutdown()
        assert view._shutdown_flag is True
        assert view._i18n_id is None


# ── _add_timer ───────────────────────────────────────────────────────────────


class TestAddTimer:
    def test_creates_timer(self, view):
        cb = MagicMock()
        t = view._add_timer(500, cb)
        assert isinstance(t, QTimer)
        assert t.isActive()

    def test_tracks_in_timers_list(self, view):
        t = view._add_timer(500, MagicMock())
        assert t in view._timers

    def test_callback_connected(self, view, qtbot):
        cb = MagicMock()
        view._add_timer(50, cb)
        qtbot.wait(100)
        assert cb.call_count >= 1

    def test_multiple_timers_tracked(self, view):
        t1 = view._add_timer(100, MagicMock())
        t2 = view._add_timer(200, MagicMock())
        assert view._timers == [t1, t2]


# ── _add_shot ────────────────────────────────────────────────────────────────


class TestAddShot:
    def test_creates_singleshot(self, view):
        cb = MagicMock()
        t = view._add_shot(10, cb)
        assert isinstance(t, QTimer)
        assert t.isSingleShot()

    def test_callback_invoked(self, view, qtbot):
        cb = MagicMock()
        view._add_shot(10, cb)
        qtbot.wait(50)
        assert cb.call_count == 1

    def test_noop_after_shutdown(self, view, qtbot):
        cb = MagicMock()
        view._add_shot(10, cb)
        view.shutdown()
        qtbot.wait(50)
        assert cb.call_count == 0


# ── _subscribe ───────────────────────────────────────────────────────────────


class TestSubscribe:
    def test_records_subscription(self, view):
        cb = MagicMock()
        view._subscribe("my_event", cb)
        assert len(view._subs) == 1
        bus, event, stored_cb = view._subs[0]
        assert bus is view._event_bus
        assert event == "my_event"
        assert stored_cb is cb

    def test_callback_receives_events(self, view):
        cb = MagicMock()
        view._subscribe("e", cb)
        view._event_bus.publish("e", {"x": 1})
        assert cb.called

    def test_multiple_subscriptions(self, view):
        cb1, cb2 = MagicMock(), MagicMock()
        view._subscribe("a", cb1)
        view._subscribe("b", cb2)
        assert len(view._subs) == 2

    def test_callback_not_called_for_unrelated_event(self, view):
        cb = MagicMock()
        view._subscribe("e", cb)
        view._event_bus.publish("other", {})
        assert not cb.called


# ── _publish ─────────────────────────────────────────────────────────────────


class TestPublish:
    def test_publishes_to_event_bus(self, view):
        cb = MagicMock()
        view._subscribe("e", cb)
        view._publish("e", {"key": "val"})
        assert cb.called

    def test_publish_without_data(self, view):
        cb = MagicMock()
        view._subscribe("e", cb)
        view._publish("e")
        assert cb.called


# ── _register_i18n ───────────────────────────────────────────────────────────


class TestRegisterI18n:
    def test_stores_callback(self, view):
        cb = MagicMock()
        view._register_i18n(cb)
        assert view._i18n_id is cb

    def test_callback_registered_with_service(self, view):
        cb = MagicMock()
        view._register_i18n(cb)
        from services.i18n import _listeners
        assert cb in _listeners

    def test_re_registration_replaces_old(self, view):
        cb1, cb2 = MagicMock(), MagicMock()
        view._register_i18n(cb1)
        view._register_i18n(cb2)
        from services.i18n import _listeners
        assert cb1 not in _listeners
        assert cb2 in _listeners
        assert view._i18n_id is cb2

    def test_unregister_failure_during_re_registration(self, view):
        cb1, cb2 = MagicMock(), MagicMock()
        view._register_i18n(cb1)
        with patch("ui.base_view.unregister_listener", side_effect=RuntimeError("dead")):
            view._register_i18n(cb2)
        assert view._i18n_id is cb2


# ── _safe_call ───────────────────────────────────────────────────────────────


class TestSafeCall:
    def test_invokes_callback(self, view):
        cb = MagicMock()
        view._safe_call(cb, 1, 2, kw=3)
        cb.assert_called_once_with(1, 2, kw=3)

    def test_noop_after_shutdown(self, view):
        view.shutdown()
        cb = MagicMock()
        view._safe_call(cb)
        assert not cb.called

    def test_exception_swallowed(self, caplog):
        v = _TestView()
        caplog.set_level(logging.ERROR)

        def boom():
            raise ValueError("bang")

        v._safe_call(boom)
        assert "bang" in caplog.text
        assert v._shutdown_flag is False


# ── Integration: full lifecycle ──────────────────────────────────────────────


class TestFullLifecycle:
    def test_wakeup_shutdown_cycle(self, view, qtbot):
        view.wakeup()
        qtbot.wait(50)  # Let async timers fire
        assert view._load_called

        view.shutdown()
        assert view._shutdown_called
        assert view._shutdown_flag

        view._load_called = False
        view.wakeup()
        qtbot.wait(50)
        assert not view._load_called

    def test_multiple_shutdown_idempotent(self, view):
        view.shutdown()
        view.shutdown()
        view.shutdown()
        assert view._shutdown_flag

    def test_timer_cleanup_on_shutdown(self, view, qtbot):
        cb = MagicMock()
        t = view._add_timer(20, cb)
        qtbot.wait(60)
        call_count_before = cb.call_count
        assert call_count_before > 0

        view.shutdown()
        assert not t.isActive()
        cb.reset_mock()
        qtbot.wait(60)
        assert cb.call_count == 0

    def test_event_bus_cleanup_on_shutdown(self, view):
        cb = MagicMock()
        view._subscribe("e", cb)
        assert len(view._subs) == 1

        view.shutdown()
        assert view._subs == []

    def test_i18n_cleanup_on_shutdown(self, view):
        cb = MagicMock()
        view._register_i18n(cb)
        view.shutdown()

        from services.i18n import _listeners
        assert cb not in _listeners

    def test_subclass_build_ui_integration(self, qtbot):
        called = False

        class MyView(BaseView):
            def __init__(self):
                super().__init__()
                self._build_ui()

            def _build_ui(self):
                nonlocal called
                called = True

        v = MyView()
        qtbot.addWidget(v)
        assert called
