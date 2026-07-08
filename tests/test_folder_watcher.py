"""Tests for FolderWatcher service.

Covers:
  - Initialization and configuration
  - Start/stop lifecycle
  - Poll loop — detecting new files, ignoring known files
  - Callback invocation on new files
  - Delete-after-import behavior
  - Recursive directory walking
  - Watchdog fallback (mock observer)
"""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from services.folder_watcher import FolderWatcher


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def watch_dir(tmp_path):
    """Create a temporary directory to watch."""
    d = tmp_path / "watch"
    d.mkdir()
    return str(d)


@pytest.fixture
def callback():
    return MagicMock()


@pytest.fixture
def watcher(watch_dir, callback):
    return FolderWatcher(
        file_callback=callback,
        watch_path=watch_dir,
        recursive=False,
        delete_after=False,
        interval_s=0.05,  # short interval for fast tests
    )


@pytest.fixture
def known_watcher(watch_dir, callback):
    """A watcher that already knows about some files."""
    w = FolderWatcher(
        file_callback=callback,
        watch_path=watch_dir,
        recursive=False,
        delete_after=False,
        interval_s=0.05,
    )
    w._known_files.add(os.path.abspath(os.path.join(watch_dir, "existing.pdf")))
    return w


# ── Initialization and configuration ───────────────────────────────

class TestInit:
    def test_default_state(self, callback):
        w = FolderWatcher(file_callback=callback)
        assert w._watch_path == ""
        assert w._recursive is False
        assert w._delete is False
        assert w._interval == 10
        assert w._thread is None
        assert w.is_running() is False

    def test_configure_updates_settings(self, watcher, watch_dir):
        watcher.configure(
            watch_path="/new/path", recursive=True,
            delete_after=True, interval_s=30,
        )
        assert watcher._watch_path == "/new/path"
        assert watcher._recursive is True
        assert watcher._delete is True
        assert watcher._interval == 30


# ── Start / Stop ───────────────────────────────────────────────────

class TestStartStop:
    def test_start_does_nothing_when_path_missing(self, callback):
        w = FolderWatcher(file_callback=callback, watch_path="/nonexistent")
        w.start()
        assert w.is_running() is False

    def test_start_starts_polling(self, watcher):
        watcher.start()
        assert watcher.is_running() is True
        watcher.stop()
        assert watcher.is_running() is False

    def test_start_idempotent(self, watcher):
        watcher.start()
        thread_id = id(watcher._thread)
        watcher.start()  # second call should no-op
        assert id(watcher._thread) == thread_id
        watcher.stop()

    def test_stop_clears_thread(self, watcher):
        watcher.start()
        watcher.stop()
        assert watcher._thread is None


# ── Poll loop — new file detection ─────────────────────────────────

class TestPollLoop:
    def test_detects_new_file(self, watcher, watch_dir, callback):
        watcher._seed_known_files()

        # Create a new file
        new_file = os.path.join(watch_dir, "new_doc.pdf")
        Path(new_file).write_text("dummy content")

        watcher._check_for_new_files()
        callback.assert_called_once()
        args = callback.call_args[0][0]
        assert any(new_file in p for p in args)

    def test_ignores_known_files(self, known_watcher, watch_dir, callback):
        known_watcher._check_for_new_files()
        callback.assert_not_called()

    def test_ignores_unsupported_extensions(self, watcher, watch_dir, callback):
        watcher._seed_known_files()
        new_file = os.path.join(watch_dir, "notes.txt")
        Path(new_file).write_text("text")
        watcher._check_for_new_files()
        callback.assert_not_called()

    def test_detects_multiple_new_files(self, watcher, watch_dir, callback):
        watcher._seed_known_files()
        for name in ["a.pdf", "b.jpg", "c.png"]:
            Path(os.path.join(watch_dir, name)).write_text("data")
        watcher._check_for_new_files()
        callback.assert_called_once()
        args = callback.call_args[0][0]
        assert len(args) == 3

    def test_callback_exception_does_not_crash(self, watcher, watch_dir):
        watcher._seed_known_files()
        watcher._callback = MagicMock(side_effect=RuntimeError("boom"))
        Path(os.path.join(watch_dir, "crash.pdf")).write_text("data")
        # Should not raise
        watcher._check_for_new_files()

    def test_walk_non_recursive(self, watcher, watch_dir):
        subdir = os.path.join(watch_dir, "sub")
        os.mkdir(subdir)
        Path(os.path.join(subdir, "nested.pdf")).write_text("data")
        results = watcher._walk()
        assert len(results) == 0  # subdir not walked in non-recursive mode

    def test_walk_recursive(self, watch_dir, callback):
        w = FolderWatcher(
            file_callback=callback, watch_path=watch_dir, recursive=True,
        )
        subdir = os.path.join(watch_dir, "sub")
        os.mkdir(subdir)
        Path(os.path.join(subdir, "nested.pdf")).write_text("data")
        results = w._walk()
        assert len(results) == 1
        assert "nested.pdf" in results[0]


# ── Delete after import ────────────────────────────────────────────

class TestDeleteAfter:
    def test_delete_removes_file(self, watch_dir, callback):
        w = FolderWatcher(
            file_callback=callback, watch_path=watch_dir,
            delete_after=True, interval_s=0.05,
        )
        w._seed_known_files()
        new_file = os.path.join(watch_dir, "delete_me.pdf")
        Path(new_file).write_text("data")
        assert os.path.isfile(new_file)

        w._check_for_new_files()
        assert not os.path.isfile(new_file)

    def test_delete_failure_does_not_raise(self, watch_dir, callback):
        w = FolderWatcher(
            file_callback=callback, watch_path=watch_dir,
            delete_after=True, interval_s=0.05,
        )
        w._seed_known_files()
        # Create a file that cannot be deleted (e.g., by making it read-only)
        new_file = os.path.join(watch_dir, "protected.pdf")
        Path(new_file).write_text("data")
        os.chmod(new_file, 0o444)  # read-only on Unix — may not work on Windows
        # Should not raise
        w._check_for_new_files()


# ── Watchdog fallback ──────────────────────────────────────────────

class TestWatchdog:
    def test_try_watchdog_returns_false_when_not_installed(self, watcher):
        with patch.dict("sys.modules", {"watchdog": None}):
            # When watchdog is not importable, returns False
            result = watcher._try_watchdog()
            assert result is False

    def test_try_watchdog_starts_observer(self, watcher, watch_dir):
        mock_observer = MagicMock()
        with patch("watchdog.observers.Observer", return_value=mock_observer), \
             patch("watchdog.events.FileSystemEventHandler"):
            result = watcher._try_watchdog()
        assert result is True
        mock_observer.schedule.assert_called_once()
        mock_observer.start.assert_called_once()

    def test_watchdog_handler_ignores_directory_events(self, watcher, watch_dir):
        """The watchdog handler should skip directory creation events."""
        from watchdog.events import FileSystemEventHandler

        with patch("watchdog.observers.Observer"), \
             patch("watchdog.events.FileSystemEventHandler"):
            watcher._try_watchdog()

            class FakeEvent:
                is_directory = True
                src_path = os.path.join(watch_dir, "subdir")

            handler = watcher._observer._handler  # our inner handler
            # Should not call the callback for a directory event
            watcher._callback = MagicMock()
            handler.on_created(FakeEvent())
            watcher._callback.assert_not_called()


# ── Edge cases ─────────────────────────────────────────────────────

class TestEdgeCases:
    def test_seed_known_files_with_existing_content(self, watch_dir, callback):
        """Existing files should be in _known_files after seed."""
        Path(os.path.join(watch_dir, "pre_existing.pdf")).write_text("data")
        w = FolderWatcher(
            file_callback=callback, watch_path=watch_dir,
        )
        w._seed_known_files()
        assert len(w._known_files) >= 1

    def test_walk_handles_oserror(self, watcher):
        """_walk should handle OSError gracefully."""
        watcher._watch_path = "/nonexistent/path"
        result = watcher._walk()
        assert result == []

    def test_poll_loop_stops_on_stop_event(self, watcher):
        """The poll loop should exit when stop_event is set."""
        watcher._stop_event.set()
        # Should exit immediately without calling _check_for_new_files
        watcher._check_for_new_files = MagicMock()
        watcher._poll_loop()
        watcher._check_for_new_files.assert_not_called()
