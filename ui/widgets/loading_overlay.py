"""Full-window loading overlay with spinner and progress.

Stretches over the entire parent window.  Auto-hides after all tasks
finish or a safety timeout (20s).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.theme import COLORS

_log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS = 20_000


class LoadingOverlay(QFrame):
    """Full-window dark translucent overlay with spinner + progress."""

    def __init__(
        self,
        parent: QWidget | None = None,
        text: str = "Loading\u2026",
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("loadingOverlay")
        self.setStyleSheet("""
            #loadingOverlay {
                background-color: rgba(9, 9, 11, 200);
            }
        """)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        # Spinner
        self._spinner = QLabel("\u25E0", self)  # unicode half-circle
        sp_font = QFont("Segoe UI", 48)
        self._spinner.setFont(sp_font)
        self._spinner.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        self._spinner.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._spinner)

        # Main text
        self._text_label = QLabel(text, self)
        tf = QFont("IBM Plex Sans", 18)
        self._text_label.setFont(tf)
        self._text_label.setStyleSheet(f"color: {COLORS['text_primary']}; background: transparent;")
        self._text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._text_label)

        # Progress sub-text
        self._progress_label = QLabel("", self)
        pf = QFont("IBM Plex Sans", 13)
        self._progress_label.setFont(pf)
        self._progress_label.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        self._progress_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._progress_label)

        # Rotate the spinner via a repeating timer
        self._spin_angle = 0
        self._spin_chars = ["\u25E0", "\u25E1", "\u25E2", "\u25E3"]
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._tick_spinner)
        self._spin_timer.start(200)

        # Safety timeout
        self._safety = QTimer(self)
        self._safety.setSingleShot(True)
        self._safety.timeout.connect(self._on_timeout)
        self._safety.start(timeout_ms)

        self._finished = False

    def _tick_spinner(self) -> None:
        self._spin_angle = (self._spin_angle + 1) % 4
        self._spinner.setText(self._spin_chars[self._spin_angle])

    def set_text(self, text: str) -> None:
        self._text_label.setText(text)

    def set_progress(self, current: int, total: int) -> None:
        self._progress_label.setText(f"{current} / {total} ready")

    def stop(self) -> None:
        """Stop timers and hide the overlay without deleting."""
        self._spin_timer.stop()
        self._safety.stop()
        self.hide()

    def mark_done(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.stop()
        self.deleteLater()

    def _on_timeout(self) -> None:
        _log.info("LoadingOverlay safety timeout reached — hiding")
        self.mark_done()

    def show(self) -> None:
        super().show()
        self.raise_()

    def resizeEvent(self, event) -> None:
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        super().resizeEvent(event)
