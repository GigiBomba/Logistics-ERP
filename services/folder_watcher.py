"""Watch folder / hot folder — monitors a directory for new files and
feeds them into the automation pipeline.

Designed for WhatsApp Desktop auto-save folders, scanner hot folders,
and any other directory-based import source.  Uses ``watchdog`` when
available (efficient OS-level file notifications), with a polling
fallback for systems without ``watchdog`` installed.

Settings (stored in the ``settings`` table):
    - folder_watcher_enabled     (1/0)
    - folder_watcher_path        Directory to watch
    - folder_watcher_recursive   Watch subdirectories (1/0, default 0)
    - folder_watcher_delete      Delete files after import (1/0, default 0)
    - folder_watcher_interval    Polling interval in seconds (default 10)
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
import time
from typing import Callable

from services.document_automation.image_processor import (
    _IMAGE_EXTENSIONS,
    _PDF_EXTENSIONS,
)

logger = logging.getLogger(__name__)

_SUPPORTED_EXTS = _IMAGE_EXTENSIONS | _PDF_EXTENSIONS
_DEFAULT_INTERVAL = 10


class FolderWatcher:
    """Monitor a directory and invoke a callback for each new file.

    Typical usage::

        def on_files(paths):
            for p in paths:
                process(p)

        watcher = FolderWatcher(on_files, "/path/to/watch")
        watcher.start()
        ...
        watcher.stop()
    """

    def __init__(
        self,
        file_callback: Callable[[list[str]], None],
        watch_path: str = "",
        recursive: bool = False,
        delete_after: bool = False,
        interval_s: int = _DEFAULT_INTERVAL,
    ) -> None:
        self._callback = file_callback
        self._watch_path = watch_path
        self._recursive = recursive
        self._delete = delete_after
        self._interval = interval_s

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._known_files: set[str] = set()

    # ── Public API ────────────────────────────────────────────────────

    def configure(
        self,
        watch_path: str = "",
        recursive: bool = False,
        delete_after: bool = False,
        interval_s: int = _DEFAULT_INTERVAL,
    ) -> None:
        self._watch_path = watch_path
        self._recursive = recursive
        self._delete = delete_after
        self._interval = interval_s

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running():
            return
        if not self._watch_path or not os.path.isdir(self._watch_path):
            logger.warning("FolderWatcher: path %r does not exist, not starting", self._watch_path)
            return

        self._seed_known_files()
        self._stop_event.clear()

        # Try watchdog for efficient OS-level monitoring.
        if self._try_watchdog():
            return

        # Fall back to polling.
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="FolderWatcher",
        )
        self._thread.start()
        logger.info(
            "FolderWatcher (polling) started: %s interval=%ds recursive=%s",
            self._watch_path, self._interval, self._recursive,
        )

    def stop(self) -> None:
        self._stop_event.set()
        # Stop watchdog observer if active.
        if hasattr(self, "_observer"):
            try:
                self._observer.stop()
                self._observer.join(timeout=3.0)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("FolderWatcher stopped")

    # ── Internal ──────────────────────────────────────────────────────

    def _seed_known_files(self) -> None:
        """Pre-populate known files so existing files don't trigger import."""
        for path in self._walk():
            self._known_files.add(os.path.abspath(path))

    def _walk(self) -> list[str]:
        """Return all supported files under the watch path."""
        results: list[str] = []
        try:
            if self._recursive:
                for root, _dirs, files in os.walk(self._watch_path):
                    for fn in files:
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in _SUPPORTED_EXTS:
                            results.append(os.path.join(root, fn))
            else:
                for fn in os.listdir(self._watch_path):
                    full = os.path.join(self._watch_path, fn)
                    if os.path.isfile(full):
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in _SUPPORTED_EXTS:
                            results.append(full)
        except OSError as exc:
            logger.warning("FolderWatcher: walk error: %s", exc)
        return results

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_for_new_files()
            except Exception as exc:
                logger.warning("FolderWatcher poll failed: %s", exc)
            self._stop_event.wait(self._interval)

    def _is_stable(self, file_path: str) -> bool:
        """Return True if *file_path* has a stable mtime older than 2 seconds."""
        try:
            st = os.stat(file_path)
            age = st.st_mtime
            return (time.time() - age) >= 2.0
        except OSError:
            return False

    def _check_for_new_files(self) -> None:
        now = {os.path.abspath(p) for p in self._walk()}
        new = now - self._known_files
        if new:
            # Only process files whose mtime is older than 2 seconds (write-complete guard).
            new_list = sorted(p for p in new if self._is_stable(p))
            if not new_list:
                return
            logger.info("FolderWatcher: %d new file(s)", len(new_list))
            try:
                self._callback(new_list)
            except Exception as exc:
                logger.warning("FolderWatcher: callback failed: %s", exc)

            if self._delete:
                for p in new_list:
                    try:
                        os.remove(p)
                        logger.debug("FolderWatcher: deleted %s", p)
                    except OSError as exc:
                        logger.warning("FolderWatcher: failed to delete %s: %s", p, exc)

            self._known_files |= new

    def _try_watchdog(self) -> bool:
        """Try to use watchdog for event-based monitoring (more efficient).

        Returns True if watchdog was successfully started.
        """
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            return False

        class _Handler(FileSystemEventHandler):
            def __init__(self, callback, known, delete, stop):
                self._callback = callback
                self._known = known
                self._delete = delete
                self._stop = stop

            def _accept(self, event):
                if self._stop.is_set():
                    return False
                if event.is_directory:
                    return False
                ext = os.path.splitext(event.src_path)[1].lower()
                if ext not in _SUPPORTED_EXTS:
                    return False
                abspath = os.path.abspath(event.src_path)
                if abspath in self._known:
                    return False
                return True

            def _process(self, abspath: str) -> None:
                self._callback([abspath])
                self._known.add(abspath)
                if self._delete:
                    with contextlib.suppress(OSError):
                        os.remove(abspath)

            def on_created(self, event):
                if not self._accept(event):
                    return
                self._process(os.path.abspath(event.src_path))

            def on_modified(self, event):
                if not self._accept(event):
                    return
                self._process(os.path.abspath(event.src_path))

            def on_moved(self, event):
                if self._stop.is_set():
                    return
                # Process the destination path after a move/rename.
                dest = getattr(event, "dest_path", None)
                if dest:
                    ext = os.path.splitext(dest)[1].lower()
                    if ext not in _SUPPORTED_EXTS:
                        return
                    abspath = os.path.abspath(dest)
                    if abspath in self._known:
                        return
                    self._process(abspath)

        handler = _Handler(self._callback, self._known_files, self._delete, self._stop_event)
        self._observer = Observer()
        self._observer.schedule(handler, self._watch_path, recursive=self._recursive)
        self._observer.start()
        logger.info("FolderWatcher (watchdog) started: %s", self._watch_path)
        return True
