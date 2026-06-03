"""Country exclusions sidebar panel (UI only)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import Callable, List, Optional

from services.country_avoidance import CountryAvoidanceManager
from services.i18n import t
from ui.styles import Theme
from ui.theme import COLORS, FONTS


class CountryExclusionsPanel:
    """Collapsible excluded-countries UI with scrollable chip/tag layout."""

    _CHIP_BG = Theme.ACCENT
    _CHIP_FG = COLORS["text_primary"]
    _CHIP_ACTIVE_BG = COLORS["accent"]
    _CHIP_FONT = FONTS["label"]
    _CHIP_REMOVE_FONT = FONTS["label"]
    _CHIP_PAD_X = 6
    _CHIP_PAD_Y = 4
    _CHIP_GAP = 6

    def __init__(
        self,
        parent: tk.Widget,
        avoidance: CountryAvoidanceManager,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        self.avoidance = avoidance
        self.on_change = on_change
        self._exclusions_count_var = tk.StringVar()
        self._exclusions_expanded = tk.BooleanVar(value=True)
        self._build(parent)

    def _notify(self) -> None:
        if self.on_change:
            self.on_change()

    def get_selected(self) -> List[str]:
        return self.avoidance.get_selected()

    def set_selected(self, codes: List[str]) -> None:
        self.avoidance.set_selected(codes)
        self.refresh()

    def _build(self, parent: tk.Widget) -> None:
        section = ctk.CTkFrame(parent, fg_color=Theme.SURFACE2, border_width=1, border_color=Theme.BORDER)
        section.pack(fill="x", padx=20, pady=(10, 8))

        header = ctk.CTkFrame(section, fg_color=Theme.SURFACE2)
        header.pack(fill="x", padx=10, pady=(8, 6))

        self._exclusions_toggle = ctk.CTkButton(
            header,
            text="▾",
            width=28,
            fg_color=Theme.SURFACE2,
            text_color=Theme.TEXT,
            hover_color=Theme.BORDER,
            command=self._toggle_section,
        )
        self._exclusions_toggle.pack(side="left")

        self._header_label = ctk.CTkLabel(
            header,
            text=t("route.exclusions_label"),
            fg_color=Theme.SURFACE2,
            text_color=Theme.TEXT,
            font=Theme.FONT_BOLD,
        )
        self._header_label.pack(side="left", padx=(4, 8))

        ctk.CTkLabel(
            header,
            textvariable=self._exclusions_count_var,
            fg_color=Theme.SURFACE2,
            text_color=Theme.MUTED,
        ).pack(side="left")

        self._clear_btn = ctk.CTkButton(
            header,
            text=t("route.exclusions_clear"),
            fg_color=Theme.SURFACE2,
            text_color=Theme.MUTED,
            hover_color=Theme.BORDER,
            command=self._clear_all,
        )
        self._clear_btn.pack(side="right")

        self._body = ctk.CTkFrame(section, fg_color=Theme.SURFACE2)
        self._body.pack(fill="x", padx=10, pady=(0, 10))

        self._configure_combobox_style()
        self._search_combo = ctk.CTkComboBox(
            self._body,
            values=[],
            state="readonly",
            command=self._add_country,
        )
        self._search_combo.pack(fill="x", pady=(0, 8))
        self._search_combo.bind("<KeyRelease>", self._on_search_key)
        self._search_combo.bind("<Return>", self._add_country)

        tags_shell = ctk.CTkFrame(self._body, fg_color=Theme.SURFACE2)
        tags_shell.pack(fill="x")

        self._tags_canvas = tk.Canvas(tags_shell, bg=Theme.SURFACE2, highlightthickness=0)
        self._tags_scroll = ttk.Scrollbar(tags_shell, orient="vertical", command=self._tags_canvas.yview)
        self._tags_frame = ctk.CTkFrame(self._tags_canvas, fg_color=Theme.SURFACE2)
        self._tags_window = self._tags_canvas.create_window((0, 0), window=self._tags_frame, anchor="nw")

        def _on_frame_configure(event=None):
            self._tags_canvas.configure(scrollregion=self._tags_canvas.bbox("all"))
            bbox = self._tags_canvas.bbox("all")
            if bbox:
                self._tags_canvas.configure(height=bbox[3] + 4)

        self._tags_frame.bind("<Configure>", _on_frame_configure)
        self._tags_canvas.bind(
            "<Configure>",
            lambda e: self._tags_canvas.itemconfigure(self._tags_window, width=e.width),
        )
        self._tags_canvas.configure(yscrollcommand=self._tags_scroll.set)
        self._tags_canvas.pack(side="left", fill="x", expand=True)
        self._tags_scroll.pack(side="right", fill="y")

        self.refresh()

    def _configure_combobox_style(self) -> None:
        try:
            style = ttk.Style()
            style.configure(
                "RoutePlanner.TCombobox",
                fieldbackground=Theme.SURFACE,
                background=Theme.SURFACE,
                foreground=Theme.TEXT,
                arrowcolor=Theme.TEXT,
                bordercolor=Theme.BORDER,
                lightcolor=Theme.BORDER,
                darkcolor=Theme.BORDER,
                padding=5,
            )
        except Exception:
            pass

    def _toggle_section(self) -> None:
        expanded = not self._exclusions_expanded.get()
        self._exclusions_expanded.set(expanded)
        self._exclusions_toggle.configure(text="▾" if expanded else "▸")
        if expanded:
            self._body.pack(fill="x", padx=10, pady=(0, 10))
        else:
            self._body.pack_forget()

    def _country_label(self, code: str, name: str) -> str:
        return f"{name} ({code})"

    def _available_options(self, query: str = "") -> List[str]:
        selected = set(self.avoidance.get_selected())
        countries = self.avoidance.get_all_countries()
        query = query.strip().lower()
        options = []
        for code, name in sorted(countries.items(), key=lambda kv: kv[1]):
            if code in selected:
                continue
            if not query or query in f"{name} {code}".lower():
                options.append(self._country_label(code, name))
        return options

    def _code_from_input(self, value: str) -> Optional[str]:
        value = value.strip()
        if not value:
            return None
        countries = self.avoidance.get_all_countries()
        if "(" in value and value.endswith(")"):
            code = value.rsplit("(", 1)[-1].rstrip(")").upper()
            if code in countries:
                return code
        normalized = value.lower()
        for code, name in countries.items():
            if normalized in (code.lower(), name.lower(), self._country_label(code, name).lower()):
                return code
        matches = [c for c, n in countries.items() if normalized in n.lower() or normalized == c.lower()]
        return matches[0] if len(matches) == 1 else None

    def _on_search_key(self, event=None) -> None:
        if event and event.keysym in ("Return", "Escape", "Up", "Down", "Left", "Right", "Tab"):
            return
        self._search_combo.configure(values=self._available_options(self._search_combo.get()))

    def _add_country(self, event=None) -> None:
        code = self._code_from_input(self._search_combo.get())
        if not code:
            options = self._available_options(self._search_combo.get())
            code = self._code_from_input(options[0]) if options else None
        if not code:
            return
        selected = self.avoidance.get_selected()
        if code not in selected:
            selected.append(code)
            self.avoidance.set_selected(selected)
        self._search_combo.set("")
        self.refresh()
        self._notify()

    def _remove_country(self, code: str) -> None:
        selected = [c for c in self.avoidance.get_selected() if c != code]
        self.avoidance.set_selected(selected)
        self.refresh()
        self._notify()

    def _clear_all(self) -> None:
        self.avoidance.clear()
        self._search_combo.set("")
        self.refresh()
        self._notify()

    def refresh(self) -> None:
        self._search_combo.configure(values=self._available_options(""))
        self._render_tags()
        count = len(self.avoidance.get_selected())
        self._exclusions_count_var.set(
            t("route.exclusions_selected").format(count) if count else t("route.exclusions_none")
        )
        self._clear_btn.configure(text=t("route.exclusions_clear"), state="normal" if count else "disabled")
        self._header_label.configure(text=t("route.exclusions_label"))

    def _render_tags(self) -> None:
        for w in self._tags_frame.winfo_children():
            w.destroy()

        selected = self.avoidance.get_selected()
        countries = self.avoidance.get_all_countries()

        if not selected:
            ctk.CTkLabel(
                self._tags_frame,
                text=t("route.exclusions_empty"),
                fg_color=Theme.SURFACE2,
                text_color=Theme.MUTED,
            ).pack(anchor="w", padx=2, pady=6)
            return

        canvas_width = self._tags_canvas.winfo_width()
        max_width = max(canvas_width - 14, 200)

        codes = sorted(selected, key=lambda c: countries.get(c, c).lower())

        rows = []
        current_row = []
        row_width = 0

        for code in codes:
            name = countries.get(code, code)
            label = f" {name} ({code}) "
            est = len(label) * 7 + 24
            if current_row and row_width + est > max_width:
                rows.append(current_row)
                current_row = [(code, name, label)]
                row_width = est
            else:
                current_row.append((code, name, label))
                row_width += est

        if current_row:
            rows.append(current_row)

        for row_data in rows:
            row = ctk.CTkFrame(self._tags_frame, fg_color=Theme.SURFACE2)
            row.pack(fill="x", anchor="w")

            for code, name, label in row_data:
                chip = ctk.CTkFrame(row, fg_color=self._CHIP_BG)

                ctk.CTkLabel(
                    chip,
                    text=label,
                    fg_color=self._CHIP_BG,
                    text_color=self._CHIP_FG,
                    font=self._CHIP_FONT,
                ).pack(side="left", padx=(self._CHIP_PAD_X, 2), pady=self._CHIP_PAD_Y)

                ctk.CTkButton(
                    chip,
                    text="✕",
                    fg_color=self._CHIP_BG,
                    text_color=self._CHIP_FG,
                    hover_color=self._CHIP_ACTIVE_BG,
                    width=18,
                    height=18,
                    font=self._CHIP_REMOVE_FONT,
                    command=lambda c=code: self._remove_country(c),
                ).pack(side="left", padx=(0, self._CHIP_PAD_X), pady=self._CHIP_PAD_Y)

                chip.pack(side="left", padx=(0, self._CHIP_GAP), pady=self._CHIP_GAP)
