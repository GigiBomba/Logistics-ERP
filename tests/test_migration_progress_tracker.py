"""Unit tests for MigrationProgressTracker — Qt signal bridge.

These tests require pytest-qt and a running QApplication (provided by the
``qapp`` fixture from tests/conftest.py).
"""
from __future__ import annotations

import pytest

from PySide6.QtCore import QObject

pytestmark = pytest.mark.qt


class TestMigrationProgressTrackerIsQObject:
    """Verify the tracker is a proper QObject."""

    def test_is_qobject(self):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        assert isinstance(tracker, QObject)

    def test_has_required_signals(self):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        assert hasattr(tracker, "stage_changed")
        assert hasattr(tracker, "progress")
        assert hasattr(tracker, "completed")
        assert hasattr(tracker, "error_occurred")

    def test_can_be_instantiated_without_arguments(self):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        assert tracker is not None


class TestCallback:
    """callback(stage, percent, msg) -> stage_changed signal."""

    def test_callback_emits_stage_changed(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        with qtbot.waitSignal(tracker.stage_changed, timeout=1000) as blocker:
            tracker.callback("test", 50, "hello")
        assert blocker.args == ["test", 50, "hello"]

    def test_callback_with_empty_message(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        with qtbot.waitSignal(tracker.stage_changed, timeout=1000) as blocker:
            tracker.callback("stage", 100, "")
        assert blocker.args == ["stage", 100, ""]

    def test_callback_zero_percent(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        with qtbot.waitSignal(tracker.stage_changed, timeout=1000) as blocker:
            tracker.callback("start", 0, "beginning")
        assert blocker.args == ["start", 0, "beginning"]

    def test_callback_is_progress_callback_compatible(self, qapp, qtbot):
        """Verify the callback signature matches ProgressCallback type."""
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        # This is the same signature as ProgressCallback = Optional[Callable[[str, int, str], None]]
        cb = tracker.callback
        with qtbot.waitSignal(tracker.stage_changed, timeout=1000) as blocker:
            cb("importing", 75, "in progress")
        assert blocker.args == ["importing", 75, "in progress"]


class TestSetProgress:
    """set_progress(current, total, msg) -> progress signal."""

    def test_set_progress_emits_signal(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        with qtbot.waitSignal(tracker.progress, timeout=1000) as blocker:
            tracker.set_progress(5, 10, "processing")
        assert blocker.args == [5, 10, "processing"]

    def test_set_progress_at_start(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        with qtbot.waitSignal(tracker.progress, timeout=1000) as blocker:
            tracker.set_progress(0, 100, "starting")
        assert blocker.args == [0, 100, "starting"]

    def test_set_progress_at_completion(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        with qtbot.waitSignal(tracker.progress, timeout=1000) as blocker:
            tracker.set_progress(100, 100, "done")
        assert blocker.args == [100, 100, "done"]

    def test_set_progress_zero_total(self, qapp, qtbot):
        """Edge case: total=0 should still emit cleanly."""
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        with qtbot.waitSignal(tracker.progress, timeout=1000) as blocker:
            tracker.set_progress(0, 0, "no work")
        assert blocker.args == [0, 0, "no work"]


class TestSetCompleted:
    """set_completed(result) -> completed signal."""

    def test_set_completed_emits_signal(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        result = {"ok": True, "rows": 42}
        with qtbot.waitSignal(tracker.completed, timeout=1000) as blocker:
            tracker.set_completed(result)
        assert blocker.args == [result]

    def test_set_completed_empty_dict(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        with qtbot.waitSignal(tracker.completed, timeout=1000) as blocker:
            tracker.set_completed({})
        assert blocker.args == [{}]

    def test_set_completed_with_stats(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        result = {"committed": 10, "skipped": 2, "failed": 0}
        with qtbot.waitSignal(tracker.completed, timeout=1000) as blocker:
            tracker.set_completed(result)
        assert blocker.args == [result]
        assert blocker.args[0]["committed"] == 10


class TestSetError:
    """set_error(msg) -> error_occurred signal."""

    def test_set_error_emits_signal(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        with qtbot.waitSignal(tracker.error_occurred, timeout=1000) as blocker:
            tracker.set_error("fail")
        assert blocker.args == ["fail"]

    def test_set_error_with_long_message(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        msg = "A" * 500
        with qtbot.waitSignal(tracker.error_occurred, timeout=1000) as blocker:
            tracker.set_error(msg)
        assert blocker.args == [msg]

    def test_set_error_empty_string(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        with qtbot.waitSignal(tracker.error_occurred, timeout=1000) as blocker:
            tracker.set_error("")
        assert blocker.args == [""]


class TestMultipleEmissions:
    """Verify the tracker can emit multiple signals in sequence."""

    def test_multiple_callbacks(self, qapp, qtbot):
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        received = []

        def collect(*args):
            received.append(args)

        tracker.stage_changed.connect(collect)

        tracker.callback("a", 10, "start")
        tracker.callback("b", 50, "middle")
        tracker.callback("c", 100, "end")

        assert len(received) == 3
        assert received[0] == ("a", 10, "start")
        assert received[1] == ("b", 50, "middle")
        assert received[2] == ("c", 100, "end")

    def test_multiple_signals(self, qapp, qtbot):
        """Emit all four signal types and verify each is received."""
        from services.migration.progress_tracker import MigrationProgressTracker

        tracker = MigrationProgressTracker()
        results = {"stage": None, "progress": None, "completed": None, "error": None}

        def on_stage(*args):
            results["stage"] = args

        def on_progress(*args):
            results["progress"] = args

        def on_completed(*args):
            results["completed"] = args

        def on_error(*args):
            results["error"] = args

        tracker.stage_changed.connect(on_stage)
        tracker.progress.connect(on_progress)
        tracker.completed.connect(on_completed)
        tracker.error_occurred.connect(on_error)

        tracker.callback("stage1", 25, "validating")
        tracker.set_progress(1, 4, "row 1")
        tracker.set_completed({"ok": True})
        tracker.set_error("something went wrong")

        assert results["stage"] == ("stage1", 25, "validating")
        assert results["progress"] == (1, 4, "row 1")
        assert results["completed"] == ({"ok": True},)
        assert results["error"] == ("something went wrong",)
