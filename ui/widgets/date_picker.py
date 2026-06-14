"""Custom dark-themed date picker for the PySide6 branch.

Replaces ``tkcalendar.DateEntry`` with a composite widget composed of a read-only
line edit and a calendar button. Clicking the button opens a popup ``QDialog``
containing a fully dark-styled ``QCalendarWidget``.
"""

from __future__ import annotations

from typing import Optional, Union
from datetime import date, datetime

from PySide6.QtCore import Qt, QDate, QPoint, Signal
from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QCalendarWidget,
    QDialog,
    QDialogButtonBox,
    QSizePolicy,
    QApplication,
)


class QtDatePicker(QWidget):
    """Composite date picker with a dark calendar popup.

    Signals:
        date_changed(QDate): emitted when the selected date changes.
    """

    date_changed = Signal(QDate)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        date_pattern: str = "yyyy-MM-dd",
        placeholder: str = "YYYY-MM-DD",
        height: int = 38,
        initial_date: Optional[Union[QDate, date, str]] = None,
    ):
        super().__init__(parent)
        self._date_pattern = date_pattern
        self._placeholder = placeholder

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.line_edit = QLineEdit(self)
        self.line_edit.setReadOnly(True)
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.setFixedHeight(height)
        self.line_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.line_edit)

        self.calendar_button = QPushButton("\u25BC", self)  # ▼
        self.calendar_button.setFixedSize(height, height)
        self.calendar_button.setProperty("variant", "ghost")
        self.calendar_button.setToolTip("Open calendar")
        layout.addWidget(self.calendar_button)

        self.calendar_button.clicked.connect(self._open_calendar)

        self._current_date: Optional[QDate] = None
        if initial_date is not None:
            self.set_date(initial_date)
        else:
            self.clear()

    # ── Public API ─────────────────────────────────────────────────────────────

    def date(self) -> Optional[QDate]:
        """Return the currently selected ``QDate`` or ``None``."""
        return self._current_date

    def date_py(self) -> Optional[date]:
        """Return the currently selected ``datetime.date`` or ``None``."""
        if self._current_date is None or not self._current_date.isValid():
            return None
        return date(self._current_date.year(), self._current_date.month(), self._current_date.day())

    def text(self) -> str:
        """Return the formatted date string shown in the field."""
        return self.line_edit.text()

    def set_date(self, value: Union[QDate, date, str, datetime, None]) -> None:
        """Set the picker date from a QDate, datetime.date, string, or datetime."""
        qdate = self._to_qdate(value)
        if qdate is None or not qdate.isValid():
            self.clear()
            return

        self._current_date = qdate
        self.line_edit.setText(qdate.toString(self._date_pattern))
        self.date_changed.emit(qdate)

    def set_date_str(self, value: str) -> None:
        """Compatibility alias for ``set_date`` with a string."""
        self.set_date(value)

    def get_date(self) -> Optional[date]:
        """Compatibility alias returning ``datetime.date``."""
        return self.date_py()

    def clear(self) -> None:
        """Clear the current selection."""
        self._current_date = None
        self.line_edit.clear()
        self.line_edit.setPlaceholderText(self._placeholder)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _to_qdate(self, value: Union[QDate, date, str, datetime, None]) -> Optional[QDate]:
        if value is None:
            return None
        if isinstance(value, QDate):
            return value
        if isinstance(value, date):
            return QDate(value.year, value.month, value.day)
        if isinstance(value, datetime):
            return QDate(value.year, value.month, value.day)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            # Try common formats.
            for fmt in ("yyyy-MM-dd", "dd/MM/yyyy", "MM/dd/yyyy", "yyyy/MM/dd"):
                qdate = QDate.fromString(text, fmt)
                if qdate.isValid():
                    return qdate
            # Fallback to ISO parsing.
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                return QDate(parsed.year, parsed.month, parsed.day)
            except Exception:
                return None
        return None

    def _open_calendar(self) -> None:
        dialog = _CalendarDialog(self, self._current_date)
        dialog.position_below(self)
        if dialog.exec() == QDialog.Accepted:
            selected = dialog.selected_date()
            if selected is not None and selected.isValid():
                self.set_date(selected)


class _CalendarDialog(QDialog):
    """Modal popup dialog containing a dark-styled QCalendarWidget."""

    def __init__(self, parent: Optional[QWidget], initial_date: Optional[QDate] = None):
        super().__init__(parent)
        self.setWindowTitle("Select date")
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedSize(280, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.calendar = QCalendarWidget(self)
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        if initial_date is not None and initial_date.isValid():
            self.calendar.setSelectedDate(initial_date)
        layout.addWidget(self.calendar)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def position_below(self, anchor: QWidget) -> None:
        """Move the popup so it appears directly below ``anchor``."""
        global_pos = anchor.mapToGlobal(QPoint(0, anchor.height()))

        # Ensure the popup stays within the available screen geometry.
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        if screen is None:
            self.move(global_pos)
            return

        geo = screen.availableGeometry()
        dialog_size = self.sizeHint() if not self.isFixedSize() else self.size()
        x = global_pos.x()
        y = global_pos.y()

        if x + dialog_size.width() > geo.right():
            x = geo.right() - dialog_size.width()
        if y + dialog_size.height() > geo.bottom():
            y = anchor.mapToGlobal(QPoint(0, 0)).y() - dialog_size.height()

        self.move(max(geo.left(), x), max(geo.top(), y))

    def selected_date(self) -> QDate:
        return self.calendar.selectedDate()


# ──────────────────────────────────────────────────────────────────────────────
# Factory matching the old ``ui.widgets.date_picker.make_date_entry`` signature.
# ──────────────────────────────────────────────────────────────────────────────


def make_date_entry(
    parent: QWidget,
    date_pattern: str = "yyyy-MM-dd",
    placeholder: str = "YYYY-MM-DD",
    height: int = 38,
):
    """Create and return a dark-themed ``QtDatePicker``."""
    return QtDatePicker(parent, date_pattern=date_pattern, placeholder=placeholder, height=height)
