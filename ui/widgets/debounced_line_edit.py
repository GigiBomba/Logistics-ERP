"""QLineEdit with configurable debounce delay.

Emits ``debouncedTextChanged`` only after the user stops typing for ``delay_ms``.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QLineEdit


class DebouncedLineEdit(QLineEdit):
    """QLineEdit that debounces the text-changed signal.

    Use this for all search/filter inputs to avoid firing a query
    on every keystroke.

    Signals:
        debouncedTextChanged(str): emitted ``delay_ms`` after the last keystroke.
    """

    debouncedTextChanged = Signal(str)

    def __init__(
        self,
        parent=None,
        placeholder: str = "",
        delay_ms: int = 300,
    ):
        super().__init__(parent)
        self._delay_ms = delay_ms
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._emit_debounced)

        if placeholder:
            self.setPlaceholderText(placeholder)

        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text: str) -> None:
        self._debounce_timer.start(self._delay_ms)

    def _emit_debounced(self) -> None:
        self.debouncedTextChanged.emit(self.text())
