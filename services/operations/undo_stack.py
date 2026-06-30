"""Undo/redo stack for trip status transitions."""
import logging
import threading
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class UndoCommand:
    trip_id: int
    old_status: str
    new_status: str
    previous_odometer: Optional[float] = None
    truck_id: Optional[int] = None


class UndoStack:
    MAX_DEPTH = 20

    def __init__(self):
        self._lock = threading.Lock()
        self._undo: list[UndoCommand] = []
        self._redo: list[UndoCommand] = []

    def push(self, command: UndoCommand) -> None:
        with self._lock:
            self._undo.append(command)
            if len(self._undo) > self.MAX_DEPTH:
                self._undo.pop(0)
            self._redo.clear()
        logger.debug("UndoStack push: trip %d, %s -> %s (stack size %d)",
                     command.trip_id, command.old_status, command.new_status, len(self._undo))

    def undo(self, current_status: Optional[str] = None) -> Optional[UndoCommand]:
        with self._lock:
            if not self._undo:
                return None
            cmd = self._undo[-1]
            if current_status is not None and cmd.new_status != current_status:
                logger.warning(
                    "UndoStack: cannot undo trip %d — expected status '%s', actual '%s'",
                    cmd.trip_id, cmd.new_status, current_status,
                )
                return None
            self._undo.pop()
            self._redo.append(cmd)
        logger.debug("UndoStack undo: trip %d, reverting %s -> %s",
                     cmd.trip_id, cmd.new_status, cmd.old_status)
        return cmd

    def redo(self, current_status: Optional[str] = None) -> Optional[UndoCommand]:
        with self._lock:
            if not self._redo:
                return None
            cmd = self._redo[-1]
            if current_status is not None and cmd.old_status != current_status:
                logger.warning(
                    "UndoStack: cannot redo trip %d — expected status '%s', actual '%s'",
                    cmd.trip_id, cmd.old_status, current_status,
                )
                return None
            self._redo.pop()
            self._undo.append(cmd)
        logger.debug("UndoStack redo: trip %d, restoring %s -> %s",
                     cmd.trip_id, cmd.old_status, cmd.new_status)
        return cmd

    def clear(self) -> None:
        with self._lock:
            self._undo.clear()
            self._redo.clear()
        logger.debug("UndoStack cleared")

    @property
    def can_undo(self) -> bool:
        with self._lock:
            return len(self._undo) > 0

    @property
    def can_redo(self) -> bool:
        with self._lock:
            return len(self._redo) > 0

    def last_undo_command(self) -> Optional[UndoCommand]:
        with self._lock:
            return self._undo[-1] if self._undo else None

    def last_redo_command(self) -> Optional[UndoCommand]:
        with self._lock:
            return self._redo[-1] if self._redo else None
