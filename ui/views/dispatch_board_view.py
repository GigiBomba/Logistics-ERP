"""Backward-compat shim — re-exports from the dispatch_board sub-package."""
from __future__ import annotations

from ui.views.dispatch_board.board_state import STATUS_TO_COLUMN  # noqa: F401
from ui.views.dispatch_board.dispatch_board import QtDispatchBoardView

__all__ = ["QtDispatchBoardView", "STATUS_TO_COLUMN"]
