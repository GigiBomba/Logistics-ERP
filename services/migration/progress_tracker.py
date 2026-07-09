"""Qt signal bridge between migration service layer and UI.

Provides a ``QObject``-based progress tracker that emits Qt signals
so the UI can react to stage changes, progress updates, completion,
and errors from any migration service operation.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal

from services.migration.types import ProgressCallback

logger = logging.getLogger(__name__)


class MigrationProgressTracker(QObject):
    """Bridges service-layer progress callbacks to Qt signals.

    Usage from a service call::

        tracker = MigrationProgressTracker()
        svc = ImportService(db)
        stats = svc.commit(rows, EntityType.CLIENT, progress_cb=tracker.callback)

    Connect UI slots::

        tracker.stage_changed.connect(lambda stage, pct, msg: ...)
        tracker.progress.connect(lambda cur, total, msg: ...)
        tracker.completed.connect(lambda result: ...)
        tracker.error_occurred.connect(lambda err: ...)
    """

    stage_changed = Signal(str, int, str)  # (stage_label, percent, message)
    progress = Signal(int, int, str)       # (current, total, message)
    completed = Signal(dict)               # result_summary
    error_occurred = Signal(str)           # error_message

    def callback(self, stage: str, percent: int, message: str = "") -> None:
        """Convenience callback compatible with ``ProgressCallback``.

        Emits ``stage_changed`` with the given arguments.
        """
        self.stage_changed.emit(stage, percent, message)

    def set_progress(self, current: int, total: int, message: str = "") -> None:
        """Emit a fine-grained progress update."""
        self.progress.emit(current, total, message)

    def set_completed(self, result: dict[str, Any]) -> None:
        """Emit the completion signal with a result summary."""
        self.completed.emit(result)

    def set_error(self, error: str) -> None:
        """Emit an error signal."""
        self.error_occurred.emit(error)
