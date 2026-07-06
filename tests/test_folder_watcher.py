"""Tests for FolderWatcher service."""
import os
from unittest.mock import MagicMock, call, patch

import pytest

from services.folder_watcher import FolderWatcher


@pytest.fixture
def mock_callback():
    return MagicMock()


@pytest.fixture
def watcher(mock_callback):
    return FolderWatcher(
        file_callback=mock_callback,
        watch_path="/fake/watch/path",
        recursive=False,
        delete_after=False,
        interval_s=1,
    )


class TestInitAndConfig:
    def test_configure_updates_settings(self, watcher):
        watcher.configure(
            watch_path="/new/path", recursive=True,
            delete_after=True, interval_s=60,
        )
        assert watcher._watch_path == "/new/path"
        assert watcher._recursive is True
        assert watcher._delete is True
        assert watcher._interval == 60

    def test_is_running_returns_false_initially(self, watcher):
        assert watcher.is_running() is False

    def test_start_does_nothing_with_invalid_path(self, mock_callback):
        w = FolderWatcher(mock_callback, watch_path="")
        with patch("os.path.isdir", return_value=False):
            w.start()
        assert w.is_running() is False

    def test_start_polling_fallback(self, watcher):
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        with patch("os.path.isdir", return_value=True), \
             patch.object(watcher, "_try_watchdog", return_value=False), \
             patch.object(watcher, "_seed_known_files"), \
             patch("threading.Thread", return_value=mock_thread):
            watcher.start()
            assert watcher.is_running() is True
            assert watcher._thread is not None

    def test_start_and_stop(self, watcher):
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        with patch("os.path.isdir", return_value=True), \
             patch.object(watcher, "_try_watchdog", return_value=False), \
             patch.object(watcher, "_seed_known_files"), \
             patch("threading.Thread", return_value=mock_thread):
            watcher.start()
            watcher.stop()
            assert watcher.is_running() is False


class TestFileDetection:
    def test_seed_known_files_populates_set(self, watcher):
        with patch.object(watcher, "_walk", return_value=["/a.pdf", "/b.jpg"]), \
             patch("os.path.abspath", side_effect=lambda x: x):
            watcher._seed_known_files()
            assert watcher._known_files == {"/a.pdf", "/b.jpg"}

    def test_walk_filters_supported_extensions(self, watcher):
        with patch("os.listdir", return_value=["doc.pdf", "img.jpg", "notes.txt", "script.exe"]), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.splitext", side_effect=lambda x: (
                 x.rsplit(".", 1)[0] if "." in x else x,
                 "." + x.rsplit(".", 1)[1].lower() if "." in x else "",
             )):
            files = watcher._walk()
            # Should only include .pdf and .jpg
            assert any("doc.pdf" in f for f in files)
            assert any("img.jpg" in f for f in files)
            assert not any("notes.txt" in f for f in files)
            assert not any("script.exe" in f for f in files)

    def test_check_for_new_files_invokes_callback(self, watcher, mock_callback):
        watcher._known_files = {"/a.pdf"}
        with patch.object(watcher, "_walk", return_value=["/a.pdf", "/b.pdf"]), \
             patch("os.path.abspath", side_effect=lambda x: x):
            watcher._check_for_new_files()
            mock_callback.assert_called_once_with(["/b.pdf"])
            assert "/b.pdf" in watcher._known_files

    def test_check_for_new_files_no_new(self, watcher, mock_callback):
        watcher._known_files = {"/a.pdf"}
        with patch.object(watcher, "_walk", return_value=["/a.pdf"]), \
             patch("os.path.abspath", side_effect=lambda x: x):
            watcher._check_for_new_files()
            mock_callback.assert_not_called()

    def test_check_for_new_files_deletes_after(self, mock_callback):
        w = FolderWatcher(mock_callback, watch_path="/p", delete_after=True)
        w._known_files = set()
        with patch.object(w, "_walk", return_value=["/p/new.pdf"]), \
             patch("os.remove") as mock_rm, \
             patch("os.path.abspath", side_effect=lambda x: x):
            w._check_for_new_files()
            mock_callback.assert_called_once()
            mock_rm.assert_called_once_with("/p/new.pdf")

    def test_callback_exception_handled(self, watcher, mock_callback):
        mock_callback.side_effect = RuntimeError("fail")
        watcher._known_files = set()
        with patch.object(watcher, "_walk", return_value=["/a.pdf"]), \
             patch("os.path.abspath", side_effect=lambda x: x):
            watcher._check_for_new_files()  # should not raise


class TestWatchdog:
    def test_try_watchdog_import_error_fallback(self, watcher):
        with patch("builtins.__import__", side_effect=ImportError("no watchdog")):
            result = watcher._try_watchdog()
            assert result is False

    def test_try_watchdog_success(self, watcher):
        mock_handler_cls = MagicMock()
        mock_observer = MagicMock()
        mock_observer_cls = MagicMock(return_value=mock_observer)
        mock_event = MagicMock()

        import types
        watchdog_module = types.ModuleType("watchdog")
        watchdog_module.events = types.ModuleType("watchdog.events")
        watchdog_module.events.FileSystemEventHandler = mock_handler_cls
        watchdog_module.observers = types.ModuleType("watchdog.observers")
        watchdog_module.observers.Observer = mock_observer_cls

        modules = {
            "watchdog": watchdog_module,
            "watchdog.events": watchdog_module.events,
            "watchdog.observers": watchdog_module.observers,
        }

        with patch.dict("sys.modules", modules):
            result = watcher._try_watchdog()
            assert result is True
            assert hasattr(watcher, "_observer")
