"""Tests for core framework signals — TopBar, DebouncedLineEdit, QtKanbanColumn, QtDatePicker, AsyncTask, WorkerPool, RenderManager.

These tests use ``qt_widget`` and ``qtbot`` from ``tests.test_conftest``.
No database is needed for any of the tested widgets.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import plotly.graph_objects as go
import pytest
from PySide6.QtCore import QByteArray, QDate, QMimeData, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QSignalSpy, QTest


# =============================================================================
# 1. TopBar signals
# =============================================================================


class TestTopBarSignals:
    """TopBar ``back_clicked`` and ``recent_clicked`` signals."""

    def test_back_clicked_emits_signal(self, qt_widget, qtbot):
        """Create TopBar, programmatically click _back_btn, verify back_clicked emitted."""
        from ui.widgets.topbar import TopBar

        topbar = TopBar(parent=qt_widget)
        qt_widget.show()
        topbar.show()
        qtbot.addWidget(topbar)

        topbar.set_back_enabled(True)
        assert topbar._back_btn.isVisible()

        with qtbot.waitSignal(topbar.back_clicked, timeout=500):
            topbar._back_btn.click()

    def test_recent_clicked_emits_view_key(self, qt_widget, qtbot):
        """Populate recent menu, trigger action, verify recent_clicked(str) emitted."""
        from ui.widgets.topbar import TopBar

        topbar = TopBar(parent=qt_widget)
        qt_widget.show()
        topbar.show()
        qtbot.addWidget(topbar)

        recent_items = [("fleet_map", "Fleet Map"), ("analytics", "Analytics")]
        topbar._update_recent_menu(recent_items)

        menu = topbar._recent_btn.menu()
        assert menu is not None
        action = menu.actions()[0]

        with qtbot.waitSignal(topbar.recent_clicked, timeout=500) as blocker:
            action.trigger()

        assert blocker.args[0] == "fleet_map"


# =============================================================================
# 2. DebouncedLineEdit signals
# =============================================================================


class TestDebouncedLineEditSignals:
    """DebouncedLineEdit ``debouncedTextChanged`` signal."""

    def test_emits_debounced_text_after_delay(self, qt_widget, qtbot):
        """Type text, wait for debouncedTextChanged with timeout."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        edit = DebouncedLineEdit(parent=qt_widget, delay_ms=100)
        edit.show()
        qtbot.addWidget(edit)

        with qtbot.waitSignal(edit.debouncedTextChanged, timeout=1000) as blocker:
            qtbot.keyClicks(edit, "hello")

        assert blocker.args[0] == "hello"

    def test_does_not_emit_if_typing_continues(self, qt_widget, qtbot):
        """Type rapidly, verify signal not emitted (debounce timer resets)."""
        from ui.widgets.debounced_line_edit import DebouncedLineEdit

        edit = DebouncedLineEdit(parent=qt_widget, delay_ms=500)
        edit.show()
        qtbot.addWidget(edit)
        spy = QSignalSpy(edit.debouncedTextChanged)

        # Type characters one by one with delays shorter than the debounce period.
        # Each keystroke restarts the timer, so the signal should NOT fire yet.
        for ch in "hello":
            QTest.keyClick(edit, ch)
            qtbot.wait(50)  # 50 ms < 500 ms debounce

        assert spy.count() == 0, "Signal should not fire during active typing"

        # Wait for the final debounce timer to complete after the last character.
        assert spy.wait(1000), "Debounced signal should fire after typing stops"
        assert spy.count() == 1
        assert spy.at(0)[0] == "hello"


# =============================================================================
# 3. QtKanbanColumn tripDropped  (invalid-drop edge case only)
# =============================================================================


class TestKanbanColumnTripDropped:
    """tripDropped signal — NOT emitted on invalid drops.

    The valid-drop path is already tested in ``tests/test_kanban_column.py``
    (``TestDragDrop::test_drop_emits_tripDropped``).
    """

    def test_tripDropped_not_emitted_on_invalid_drop(self, qt_widget, qtbot):
        """Drop with non-numeric or empty MIME data does NOT emit tripDropped."""
        from ui.widgets.kanban_column import QtKanbanColumn

        column = QtKanbanColumn(
            parent=qt_widget,
            status_key="Planned",
            title_key="dispatch_board.col_planned",
            on_card_click=MagicMock(),
            on_drag_start=MagicMock(),
        )
        qt_widget.show()
        column.show()
        qtbot.addWidget(column)

        spy = QSignalSpy(column.tripDropped)

        # -- Non-numeric text (fails int() parsing) --
        mime = QMimeData()
        mime.setText("not-a-number")
        event = QDropEvent(
            column.pos(), Qt.CopyAction, mime,
            Qt.LeftButton, Qt.NoModifier,
        )
        column.dropEvent(event)
        assert spy.count() == 0, "tripDropped should NOT emit for non-numeric text"

        # -- No text at all --
        mime2 = QMimeData()
        event2 = QDropEvent(
            column.pos(), Qt.CopyAction, mime2,
            Qt.LeftButton, Qt.NoModifier,
        )
        column.dropEvent(event2)
        assert spy.count() == 0, "tripDropped should NOT emit for empty MIME data"

        # Cleanup to avoid callback references persisting across tests.
        column._destroy()


# =============================================================================
# 4. QtDatePicker signals
# =============================================================================


class TestDatePickerSignals:
    """QtDatePicker ``date_changed`` signal."""

    def test_emits_date_changed_on_set_date(self, qt_widget, qtbot):
        """Create date picker, set_date(), wait for date_changed signal."""
        from ui.widgets.date_picker import QtDatePicker

        picker = QtDatePicker(parent=qt_widget)
        picker.show()
        qtbot.addWidget(picker)

        with qtbot.waitSignal(picker.date_changed, timeout=500) as blocker:
            picker.set_date(QDate(2025, 6, 15))

        assert blocker.args[0] == QDate(2025, 6, 15)

    def test_emits_qdate_with_correct_values(self, qt_widget, qtbot):
        """Set date, verify emitted QDate has correct year/month/day."""
        from ui.widgets.date_picker import QtDatePicker

        picker = QtDatePicker(parent=qt_widget)
        picker.show()
        qtbot.addWidget(picker)
        spy = QSignalSpy(picker.date_changed)

        picker.set_date(QDate(2025, 12, 25))

        assert spy.count() == 1
        qdate = spy.at(0)[0]
        assert isinstance(qdate, QDate)
        assert qdate.year() == 2025
        assert qdate.month() == 12
        assert qdate.day() == 25

    def test_does_not_emit_on_clear(self, qt_widget, qtbot):
        """Clear date, verify date_changed NOT emitted."""
        from ui.widgets.date_picker import QtDatePicker

        picker = QtDatePicker(parent=qt_widget)
        picker.show()
        qtbot.addWidget(picker)

        spy = QSignalSpy(picker.date_changed)
        picker.set_date(QDate(2025, 1, 1))
        assert spy.count() == 1

        # ``clear()`` must NOT emit ``date_changed`` — it only resets
        # the internal state and the line-edit text.
        picker.clear()
        assert spy.count() == 1, "clear() should not emit date_changed"


# =============================================================================
# 5. AsyncTask signals
# =============================================================================


class TestAsyncTaskSignals:
    """AsyncTask ``finished`` and ``error`` signals."""

    def test_finished_emits_result(self, qtbot):
        """Run a task returning a value; wait for finished signal."""
        from ui.widgets.async_task import AsyncTask

        task = AsyncTask()
        latch = threading.Event()

        # The worker blocks on the latch so ``waitSignal`` has time to connect.
        task.run(fn=lambda: (latch.wait(10), 42)[1])

        with qtbot.waitSignal(task._worker.finished, timeout=5000) as blocker:
            latch.set()

        assert blocker.args[0] == 42

    def test_error_emits_message(self, qtbot):
        """Run a task that raises an exception; wait for error signal."""
        from ui.widgets.async_task import AsyncTask

        task = AsyncTask()
        latch = threading.Event()

        def failing_fn() -> None:
            latch.wait(10)
            msg = "intentional failure"
            raise ValueError(msg)

        task.run(fn=failing_fn)

        with qtbot.waitSignal(task._worker.error, timeout=5000) as blocker:
            latch.set()

        assert "intentional failure" in blocker.args[0]


# =============================================================================
# 6. WorkerPool signals
# =============================================================================


class TestWorkerPoolSignals:
    """WorkerPool ``_WorkerSignals`` (the carrier signal) via ``_Runnable``.

    Note: ``WorkerPool.run()`` has a pre-existing GC issue where its local
    ``_WorkerSignals`` variable is garbage-collected before the worker thread
    emits the signal.  We test the identical carrier mechanism directly with
    ``_Runnable`` — the same class ``WorkerPool.run()`` uses internally.
    """

    def test_result_delivers_on_success(self, qtbot):
        """Create ``_WorkerSignals``, connect to ``result``, run task, verify signal."""
        from PySide6.QtCore import QThreadPool
        from ui.worker_pool import _WorkerSignals, _Runnable

        signals = _WorkerSignals()
        spy = QSignalSpy(signals.result)

        runnable = _Runnable(fn=lambda: 42, signals=signals)
        QThreadPool.globalInstance().start(runnable)
        QThreadPool.globalInstance().waitForDone(5000)
        qtbot.wait(200)  # process events for queued cross-thread delivery

        assert spy.count() == 1
        assert spy.at(0)[0] == 42

    def test_error_delivers_on_failure(self, qtbot):
        """Create ``_WorkerSignals``, connect to ``error``, run failing task,
        verify signal."""
        from PySide6.QtCore import QThreadPool
        from ui.worker_pool import _WorkerSignals, _Runnable

        signals = _WorkerSignals()
        spy = QSignalSpy(signals.error)

        def failing_fn() -> None:
            msg = "intentional failure"
            raise ValueError(msg)

        runnable = _Runnable(fn=failing_fn, signals=signals)
        QThreadPool.globalInstance().start(runnable)
        QThreadPool.globalInstance().waitForDone(5000)
        qtbot.wait(200)

        assert spy.count() == 1
        assert "intentional failure" in spy.at(0)[0]


# =============================================================================
# 7. Render signals
# =============================================================================


class TestRenderSignals:
    """_RenderSignals ``delivered`` signal and active-tag tracking."""

    def test_delivered_emits_on_completion(self, qtbot):
        """Submit a render request; wait for ``delivered`` signal."""
        from ui.plotly_renderer import RenderManager

        manager = RenderManager()
        fig = go.Figure()
        fig.add_scatter(x=[1, 2, 3], y=[4, 5, 6])

        with qtbot.waitSignal(manager.signals.delivered, timeout=15000) as blocker:
            tag = manager.submit(fig, 200, 150)

        received_tag, payload = blocker.args
        assert received_tag == tag
        assert isinstance(payload, QByteArray)
        assert not payload.isEmpty()

    def test_active_tags_updated(self, qtbot):
        """Verify tags are tracked as active during render and removed on completion."""
        from ui.plotly_renderer import RenderManager

        manager = RenderManager()
        fig = go.Figure()
        fig.add_scatter(x=[1, 2, 3], y=[4, 5, 6])

        # After submit the tag should be in the active set.
        tag = manager.submit(fig, 200, 150)
        assert tag in manager._active_tags, "Tag should be active after submit"

        # Wait for the pool to finish, then process events so the queued
        # ``delivered`` signal arrives and ``_on_delivered`` removes the tag.
        manager.wait_for_done(15000)
        qtbot.wait(500)

        assert tag not in manager._active_tags, (
            "Tag should be removed from active set after delivery"
        )
