"""PySide6 freehand signature pad — QPainter-based replacement for the tk.Canvas version.

Migrates ``ui/widgets/signature_pad.py`` to PySide6.  Uses a custom ``QWidget``
with a ``paintEvent`` override and ``QPainter`` for stroke rendering.  Produces a
PNG image via Pillow's ``ImageDraw`` on accept (same as the original), or allows
the user to pick an existing signature image via ``QFileDialog``.

Modes:
    "draw"   — Canvas for freehand drawing with mouse
    "upload" — File picker for selecting existing signature image
    "none"   — No signature set
"""

from __future__ import annotations

import io
import logging
import os
import uuid

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.theme import COLORS, S
from ui.widgets import ActionButton, StyledLineEdit

logger = logging.getLogger(__name__)

PAD_WIDTH = 260
PAD_HEIGHT = 80


# ──────────────────────────────────────────────────────────────────────────────
# Canvas widget — handles drawing via QPainter
# ──────────────────────────────────────────────────────────────────────────────


class _CanvasWidget(QWidget):
    """Custom widget that renders freehand strokes with ``QPainter``.

    This is the drop-in replacement for the original ``tk.Canvas``.
    Strokes are stored as ``List[List[Tuple[int, int]]]`` (each stroke is a list
    of (x, y) tuples).  The widget repaints on every stroke change.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(PAD_WIDTH, PAD_HEIGHT)
        self.setMouseTracking(False)
        self.setCursor(Qt.CrossCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._strokes: list[list[tuple[int, int]]] = []
        self._current_stroke: list[tuple[int, int]] = []
        self._active = False  # True while pen is down

    # ── Stroke management ──────────────────────────────────────────────────────

    def clear_strokes(self) -> None:
        """Remove all strokes and reset the current stroke."""
        self._strokes.clear()
        self._current_stroke.clear()
        self._active = False
        self.update()

    def get_strokes(self) -> list[list[tuple[int, int]]]:
        """Return a copy of the finished strokes list."""
        return [list(s) for s in self._strokes]

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return
        self._active = True
        self._current_stroke = [(int(event.position().x()), int(event.position().y()))]
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._active or not self._current_stroke:
            return
        x = int(event.position().x())
        y = int(event.position().y())
        self._current_stroke.append((x, y))
        self.update()  # request repaint on every move for smooth drawing

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return
        self._finalize_stroke()
        self.update()

    def leaveEvent(self, event: QEvent) -> None:
        """Finalize in-progress stroke when mouse leaves the canvas."""
        if self._active:
            self._finalize_stroke()
            self.update()
        super().leaveEvent(event)

    def _finalize_stroke(self) -> None:
        """Save the current stroke if valid and reset."""
        self._active = False
        if len(self._current_stroke) > 1:
            self._strokes.append(list(self._current_stroke))
        self._current_stroke.clear()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        bg_color = QColor(COLORS["bg_input"])
        painter.fillRect(self.rect(), bg_color)

        pen_color = QColor(COLORS["text_primary"])
        pen = QPen(pen_color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        # Finished strokes
        for stroke in self._strokes:
            self._draw_stroke(painter, stroke)

        # Current (in-progress) stroke
        if self._current_stroke and len(self._current_stroke) > 1:
            self._draw_stroke(painter, self._current_stroke)

        painter.end()

    @staticmethod
    def _draw_stroke(painter: QPainter, stroke: list[tuple[int, int]]) -> None:
        """Draw a single stroke as a series of connected line segments."""
        for i in range(len(stroke) - 1):
            x1, y1 = stroke[i]
            x2, y2 = stroke[i + 1]
            painter.drawLine(x1, y1, x2, y2)


# ──────────────────────────────────────────────────────────────────────────────
# Main signature pad widget
# ──────────────────────────────────────────────────────────────────────────────


class QtSignaturePad(QWidget):
    """A signature capture widget with draw / upload / accept controls.

    Modes:
        "draw"   — Canvas for freehand drawing with mouse
        "upload" — File picker for selecting existing signature image
        "none"   — No signature set

    Usage:
        pad = QtSignaturePad(parent, label="Sender Signature")
        # ... user draws or uploads ...
        path = pad.get_path()  # None if no signature set
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        label: str = "",
    ):
        super().__init__(parent)
        self._label_text = label
        self._saved_path: str | None = None
        self._mode: str = "none"

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(S["1"])

        # Optional label
        if self._label_text:
            lbl = QLabel(self._label_text)
            lbl.setProperty("fontRole", "small")
            lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
            layout.addWidget(lbl)

        # ── Toggle row (Draw / Upload / Clear + status) ──────────────────
        toggle_row = QWidget()
        toggle_layout = QHBoxLayout(toggle_row)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(S["1"])

        self._draw_btn = ActionButton(
            toggle_row, "Draw",
            command=self._switch_to_draw,
            variant="primary",
        )
        self._draw_btn.setFixedHeight(22)
        toggle_layout.addWidget(self._draw_btn)

        self._upload_btn = ActionButton(
            toggle_row, "Upload",
            command=self._switch_to_upload,
            variant="ghost",
        )
        self._upload_btn.setFixedHeight(22)
        toggle_layout.addWidget(self._upload_btn)

        self._clear_btn = ActionButton(
            toggle_row, "Clear",
            command=self._clear,
            variant="ghost",
        )
        self._clear_btn.setFixedHeight(22)
        toggle_layout.addWidget(self._clear_btn)

        toggle_layout.addStretch(1)

        self._status_lbl = QLabel(t("signature.no_signature", default="No signature"))
        self._status_lbl.setProperty("fontRole", "small")
        self._status_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        toggle_layout.addWidget(self._status_lbl)

        layout.addWidget(toggle_row)

        # ── Canvas area (draw mode) ─────────────────────────────────────
        # Wrap the _CanvasWidget in a QFrame to produce a border effect.
        self._canvas_frame = QFrame()
        self._canvas_frame.setFrameShape(QFrame.StyledPanel)
        self._canvas_frame.setFixedSize(PAD_WIDTH + 2, PAD_HEIGHT + 2)
        self._canvas_frame.setStyleSheet(
            f"background-color: {COLORS['border']};"
        )

        canvas_layout = QHBoxLayout(self._canvas_frame)
        canvas_layout.setContentsMargins(1, 1, 1, 1)
        canvas_layout.setSpacing(0)

        self._canvas = _CanvasWidget()
        canvas_layout.addWidget(self._canvas)

        layout.addWidget(self._canvas_frame)

        # ── Upload area (hidden initially) ──────────────────────────────
        self._upload_frame = QWidget()
        upload_layout = QHBoxLayout(self._upload_frame)
        upload_layout.setContentsMargins(0, 0, 0, 0)
        upload_layout.setSpacing(S["1"])

        self._browse_btn = ActionButton(
            self._upload_frame, "Browse Image...",
            command=self._browse_image,
            variant="ghost",
        )
        self._browse_btn.setFixedHeight(22)
        upload_layout.addWidget(self._browse_btn)

        self._upload_path_edit = StyledLineEdit(
            self._upload_frame,
            placeholder="No file selected",
            height=22,
        )
        self._upload_path_edit.setReadOnly(True)
        upload_layout.addWidget(self._upload_path_edit, 1)

        self._upload_frame.setVisible(False)
        layout.addWidget(self._upload_frame)

        # ── Accept button ───────────────────────────────────────────────
        self._accept_btn = ActionButton(
            self, "Accept Signature",
            command=self._accept,
            variant="success",
        )
        self._accept_btn.setFixedHeight(26)
        layout.addWidget(self._accept_btn)

        # Start in "none" mode — canvas hidden, upload hidden
        self._canvas_frame.setVisible(False)

    # ── Mode switching ────────────────────────────────────────────────────────

    def _switch_to_draw(self) -> None:
        self._mode = "draw"
        self._canvas_frame.setVisible(True)
        self._upload_frame.setVisible(False)

    def _switch_to_upload(self) -> None:
        self._mode = "upload"
        self._canvas_frame.setVisible(False)
        self._upload_frame.setVisible(True)

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def _clear(self) -> None:
        self._canvas.clear_strokes()
        self._saved_path = None
        self._upload_path_edit.clear()
        self._mode = "none"
        self._canvas_frame.setVisible(False)
        self._upload_frame.setVisible(False)
        self._status_lbl.setText(t("signature.no_signature", default="No signature"))
        self._status_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")

    # ── Render to PNG ─────────────────────────────────────────────────────────

    def _render_to_png(self) -> bytes:
        """Render strokes to a Pillow Image and return PNG bytes.

        Uses the same scaling logic as the original tk.Canvas version:
        render at 2x, then downsample with LANCZOS for anti-aliasing.
        """
        img = Image.new("RGBA", (PAD_WIDTH * 2, PAD_HEIGHT * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        strokes = self._canvas.get_strokes()
        for stroke in strokes:
            if len(stroke) < 2:
                continue
            for i in range(len(stroke) - 1):
                x1, y1 = stroke[i][0] * 2, stroke[i][1] * 2
                x2, y2 = stroke[i + 1][0] * 2, stroke[i + 1][1] * 2
                draw.line([x1, y1, x2, y2], fill=(0, 0, 0, 255), width=4)

        buf = io.BytesIO()
        # Resize back down for anti-aliased look
        img_small = img.resize((PAD_WIDTH, PAD_HEIGHT), Image.LANCZOS)
        img_small.save(buf, format="PNG")
        return buf.getvalue()

    def _save_temp_png(self, png_data: bytes) -> str:
        """Save PNG bytes to temp directory and return absolute path."""
        temp_dir = os.path.join("data", "temp", "signatures")
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"sig_{uuid.uuid4().hex[:12]}.png"
        path = os.path.join(temp_dir, filename)
        with open(path, "wb") as f:
            f.write(png_data)
        return os.path.abspath(path)

    def _accept(self) -> None:
        if self._mode == "draw":
            strokes = self._canvas.get_strokes()
            if strokes:
                png_data = self._render_to_png()
                self._saved_path = self._save_temp_png(png_data)
                self._status_lbl.setText(t("signature.accepted", default="Signature accepted"))
                self._status_lbl.setStyleSheet(f"color: {COLORS['text_success']};")
        elif self._mode == "upload":
            path = self._upload_path_edit.text()
            if path and os.path.isfile(path):
                self._saved_path = path
                self._status_lbl.setText(t("signature.label_selected", default="Selected: {}").format(os.path.basename(path)))
                self._status_lbl.setStyleSheet(f"color: {COLORS['text_success']};")
        self._mode = "signed"

    # ── Upload mode ───────────────────────────────────────────────────────────

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("signature.select_title", default="Select Signature Image"),
            "",
            t("signature.filter_images", default="Image files (*.png *.jpg *.jpeg *.bmp);;All files (*.*)"),
        )
        if path:
            self._upload_path_edit.setText(os.path.basename(path))
            self._saved_path = path
            self._mode = "upload"
            self._status_lbl.setText(t("signature.label_selected", default="Selected: {}").format(os.path.basename(path)))
            self._status_lbl.setStyleSheet(f"color: {COLORS['text_success']};")

    # ── Public API ────────────────────────────────────────────────────────────

    def get_path(self) -> str | None:
        """Return the saved signature image path, or ``None`` if not set."""
        return self._saved_path

    def set_path(self, path: str | None) -> None:
        """Pre-load a signature path.

        If the path exists on disk the status label is updated accordingly.
        """
        if path and os.path.isfile(path):
            self._saved_path = path
            self._upload_path_edit.setText(os.path.basename(path))
            self._status_lbl.setText(t("signature.label_loaded", default="Loaded: {}").format(os.path.basename(path)))
            self._status_lbl.setStyleSheet(f"color: {COLORS['text_success']};")

    def cleanup(self) -> None:
        """Release any Pillow resources held by this widget.

        Currently no long-lived Pillow objects are stored, so
        this is a no-op placeholder for API compatibility.  Call it when the
        widget is being discarded.
        """
        self._canvas.clear_strokes()
        self._saved_path = None
        self._status_lbl.setText(t("signature.cleaned_up", default="Cleaned up"))
        self._status_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        logger.debug("QtSignaturePad resources released")
