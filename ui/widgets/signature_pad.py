"""Signature drawing pad — canvas-based widget for freehand signature capture.

Produces a PNG image from the drawn strokes using Pillow's ImageDraw.
Integrates into the CMR form's Boxes 22-24 as a drop-in replacement for
the file-upload button.
"""

import io
import logging
import os
import tempfile
import tkinter as tk
import uuid
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw

from ui.theme import COLORS, FONTS, S

logger = logging.getLogger(__name__)

PAD_WIDTH = 260
PAD_HEIGHT = 80


class SignaturePad(ctk.CTkFrame):
    """A signature capture widget with draw/clear/accept controls.

    Modes:
        "draw"   — Canvas for freehand drawing with mouse
        "upload" — File picker for selecting existing signature image
        "none"   — No signature set

    Usage:
        pad = SignaturePad(parent, label="Sender Signature")
        # ... user draws or uploads ...
        path = pad.get_path()  # None if no signature set
    """

    def __init__(self, parent, label="", **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)
        self._label_text = label
        self._strokes = []
        self._current_stroke = []
        self._saved_path = None
        self._mode = "none"

        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)

        if self._label_text:
            ctk.CTkLabel(self, text=self._label_text,
                         font=FONTS["small"], text_color=COLORS["text_muted"],
                         anchor="w").grid(row=0, column=0, sticky="w",
                                          pady=(0, S["1"]))

        # Mode toggle buttons
        toggle_row = ctk.CTkFrame(self, fg_color="transparent")
        toggle_row.grid(row=1, column=0, sticky="ew", pady=(0, S["1"]))

        ctk.CTkButton(toggle_row, text="Draw", font=FONTS["small"],
                      width=50, height=22,
                      fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                      text_color="#fff",
                      command=self._switch_to_draw).pack(side="left", padx=(0, S["1"]))

        ctk.CTkButton(toggle_row, text="Upload", font=FONTS["small"],
                      width=50, height=22,
                      fg_color=COLORS["bg_elevated"], hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_secondary"],
                      command=self._switch_to_upload).pack(side="left", padx=(0, S["1"]))

        ctk.CTkButton(toggle_row, text="Clear", font=FONTS["small"],
                      width=50, height=22,
                      fg_color=COLORS["bg_elevated"], hover_color=COLORS["danger"],
                      text_color=COLORS["text_secondary"],
                      command=self._clear).pack(side="left")

        self._status_lbl = ctk.CTkLabel(toggle_row, text="No signature",
                                        font=FONTS["small"],
                                        text_color=COLORS["text_muted"])
        self._status_lbl.pack(side="right")

        # Canvas container (draw mode)
        self._canvas_frame = ctk.CTkFrame(self, fg_color=COLORS["border"],
                                          corner_radius=4)
        self._canvas_frame.grid(row=2, column=0, sticky="ew", pady=(0, S["1"]))

        self._canvas = tk.Canvas(
            self._canvas_frame,
            width=PAD_WIDTH, height=PAD_HEIGHT,
            bg=COLORS["bg_input"],
            highlightthickness=0,
            cursor="pencil",
        )
        self._canvas.pack(padx=1, pady=1)
        self._canvas.bind("<ButtonPress-1>", self._on_pen_down)
        self._canvas.bind("<B1-Motion>", self._on_pen_move)
        self._canvas.bind("<ButtonRelease-1>", self._on_pen_up)

        # Upload area (hidden initially)
        self._upload_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._upload_frame.grid(row=3, column=0, sticky="ew", pady=(0, S["1"]))
        self._upload_frame.grid_remove()

        ctk.CTkButton(self._upload_frame, text="Browse Image...",
                      font=FONTS["small"], width=100, height=22,
                      fg_color=COLORS["bg_elevated"],
                      hover_color=COLORS["border_hover"],
                      text_color=COLORS["text_primary"],
                      command=self._browse_image).pack(side="left")

        self._upload_path_var = tk.StringVar()
        ctk.CTkEntry(self._upload_frame, textvariable=self._upload_path_var,
                     font=FONTS["small"], height=22, state="readonly",
                     fg_color=COLORS["bg_input"], border_color=COLORS["border"],
                     text_color=COLORS["text_muted"]).pack(
            side="left", fill="x", expand=True, padx=(S["1"], 0))

        # Accept button
        self._accept_btn = ctk.CTkButton(self, text="Accept Signature",
                                         font=FONTS["small"], height=26,
                                         fg_color=COLORS["success"],
                                         hover_color=COLORS["success"],
                                         text_color="#fff",
                                         command=self._accept)
        self._accept_btn.grid(row=4, column=0, sticky="ew")

    # ── Drawing ─────────────────────────────────────────────────

    def _on_pen_down(self, event):
        if self._mode != "draw":
            return
        x = self._canvas.canvasx(event.x)
        y = self._canvas.canvasy(event.y)
        self._current_stroke = [(x, y)]
        self._canvas.create_oval(
            x - 1, y - 1, x + 1, y + 1,
            fill=COLORS["text_primary"], outline=COLORS["text_primary"],
        )

    def _on_pen_move(self, event):
        if self._mode != "draw" or not self._current_stroke:
            return
        x = self._canvas.canvasx(event.x)
        y = self._canvas.canvasy(event.y)
        prev = self._current_stroke[-1]
        self._canvas.create_line(
            prev[0], prev[1], x, y,
            width=2, fill=COLORS["text_primary"], capstyle=tk.ROUND,
            smooth=True,
        )
        self._current_stroke.append((x, y))

    def _on_pen_up(self, event):
        if self._current_stroke and len(self._current_stroke) > 1:
            self._strokes.append(list(self._current_stroke))
        self._current_stroke = []

    def _clear(self):
        self._canvas.delete("all")
        self._strokes.clear()
        self._current_stroke = []
        self._saved_path = None
        self._upload_path_var.set("")
        self._mode = "none"
        self._status_lbl.configure(text="No signature",
                                   text_color=COLORS["text_muted"])

    # ── Render to PNG ────────────────────────────────────────────

    def _render_to_png(self) -> bytes:
        """Render strokes to a Pillow Image and return PNG bytes."""
        img = Image.new("RGBA", (PAD_WIDTH * 2, PAD_HEIGHT * 2),
                        (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        for stroke in self._strokes:
            if len(stroke) < 2:
                continue
            for i in range(len(stroke) - 1):
                x1, y1 = stroke[i][0] * 2, stroke[i][1] * 2
                x2, y2 = stroke[i + 1][0] * 2, stroke[i + 1][1] * 2
                draw.line([x1, y1, x2, y2],
                          fill=(250, 250, 250, 255), width=4)

        buf = io.BytesIO()
        # Resize back down for anti-aliased look
        img_small = img.resize((PAD_WIDTH, PAD_HEIGHT), Image.LANCZOS)
        img_small.save(buf, format="PNG")
        return buf.getvalue()

    def _accept(self):
        if self._mode == "draw" and self._strokes:
            png_data = self._render_to_png()
            self._saved_path = self._save_temp_png(png_data)
            self._status_lbl.configure(text="Signature accepted",
                                       text_color=COLORS["text_success"])
        elif self._mode == "upload":
            path = self._upload_path_var.get()
            if path and os.path.isfile(path):
                self._saved_path = path
                self._status_lbl.configure(text=f"Selected: {os.path.basename(path)}",
                                           text_color=COLORS["text_success"])
        self._mode = "none"

    def _save_temp_png(self, png_data: bytes) -> str:
        """Save PNG bytes to temp directory and return path."""
        temp_dir = os.path.join("data", "temp", "signatures")
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"sig_{uuid.uuid4().hex[:12]}.png"
        path = os.path.join(temp_dir, filename)
        with open(path, "wb") as f:
            f.write(png_data)
        return os.path.abspath(path)

    # ── Upload mode ──────────────────────────────────────────────

    def _switch_to_draw(self):
        self._mode = "draw"
        self._canvas_frame.grid()
        self._upload_frame.grid_remove()

    def _switch_to_upload(self):
        self._mode = "upload"
        self._canvas_frame.grid_remove()
        self._upload_frame.grid()

    def _browse_image(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Signature Image",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"),
                       ("All files", "*.*")])
        if path:
            self._upload_path_var.set(os.path.basename(path))
            self._saved_path = path
            self._mode = "upload"
            self._status_lbl.configure(text=f"Selected: {os.path.basename(path)}",
                                       text_color=COLORS["text_success"])

    # ── Public API ───────────────────────────────────────────────

    def get_path(self):
        """Return the saved signature image path, or None if not set."""
        return self._saved_path

    def set_path(self, path):
        """Pre-load a signature path."""
        if path and os.path.isfile(path):
            self._saved_path = path
            self._upload_path_var.set(os.path.basename(path))
            self._status_lbl.configure(
                text=f"Loaded: {os.path.basename(path)}",
                text_color=COLORS["text_success"])
