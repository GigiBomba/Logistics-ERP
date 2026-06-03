"""Centralized error handler for the application.

Provides categorized error handling with logging and user-facing messages.
UI components should use show_error() / show_warning() for user dialogs.
Services should use the standard exception handling patterns.
"""
import logging
import traceback
from enum import Enum
from typing import Optional


class ErrorCategory(Enum):
    DATABASE = "database"
    NETWORK = "network"
    VALIDATION = "validation"
    FILE_IO = "file_io"
    ROUTE = "route"
    TRANSLATION = "translation"
    UI = "ui"
    UNKNOWN = "unknown"


_logger = logging.getLogger("error_handler")


def handle_exception(
    error: Exception,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    context: str = "",
    show_dialog: bool = False,
    parent_widget=None,
) -> str:
    """Log an exception and optionally show a user dialog.
    
    Returns a user-friendly message string.
    """
    tb = traceback.format_exc()
    msg = str(error) or repr(error)
    log_msg = f"[{category.value}] {context}: {msg}" if context else f"[{category.value}] {msg}"
    _logger.error("%s\n%s", log_msg, tb)

    if show_dialog and parent_widget:
        _show_dialog(parent_widget, msg, category)
    
    return msg


def _show_dialog(parent_widget, message: str, category: ErrorCategory) -> None:
    """Show a tkinter messagebox for user-facing errors."""
    try:
        import tkinter.messagebox as mb
        title = f"Error - {category.value}"
        mb.showerror(title, message)
    except Exception:
        pass


class AppError(Exception):
    """Base exception for application-level errors."""
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN):
        super().__init__(message)
        self.category = category
