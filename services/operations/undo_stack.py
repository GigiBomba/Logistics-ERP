"""Undo/redo stack for trip status transitions."""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
        self._undo: List[UndoCommand] = []
        self._redo: List[UndoCommand] = []

    def push(self, command: UndoCommand) -> None:
        self._undo.append(command)
        if len(self._undo) > self.MAX_DEPTH:
            self._undo.pop(0)
        self._redo.clear()
        logger.debug("UndoStack push: trip %d, %s -> %s (stack size %d)",
                     command.trip_id, command.old_status, command.new_status, len(self._undo))

    def undo(self) -> Optional[UndoCommand]:
        if not self._undo:
            return None
        cmd = self._undo.pop()
        self._redo.append(cmd)
        logger.debug("UndoStack undo: trip %d, reverting %s -> %s",
                     cmd.trip_id, cmd.new_status, cmd.old_status)
        return cmd

    def redo(self) -> Optional[UndoCommand]:
        if not self._redo:
            return None
        cmd = self._redo.pop()
        self._undo.append(cmd)
        logger.debug("UndoStack redo: trip %d, restoring %s -> %s",
                     cmd.trip_id, cmd.old_status, cmd.new_status)
        return cmd

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
        logger.debug("UndoStack cleared")

    @property
    def can_undo(self) -> bool:
        return len(self._undo) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo) > 0

    def last_undo_command(self) -> Optional[UndoCommand]:
        return self._undo[-1] if self._undo else None

    def last_redo_command(self) -> Optional[UndoCommand]:
        return self._redo[-1] if self._redo else None
