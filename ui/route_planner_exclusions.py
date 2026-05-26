"""Country exclusions sidebar panel (UI only)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from services.country_avoidance import CountryAvoidanceManager
from services.i18n import t
from ui.styles import Theme


class CountryExclusionsPanel:
    """Collapsible excluded-countries UI with scrollable chip/tag layout."""

    _CHIP_BG = Theme.ACCENT
    _CHIP_FG = "#ffffff"
    _CHIP_ACTIVE_BG = "#6d3fd8"
    _CHIP_FONT = ("Segoe UI", 9)
    _CHIP_REMOVE_FONT = ("Segoe UI", 8)
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
        self._country_search_var = tk.StringVar()
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
        section = tk.Frame(parent, bg=Theme.SURFACE2, highlightthickness=1, highlightbackground=Theme.BORDER)
        section.pack(fill="x", padx=20, pady=(10, 8))

        header = tk.Frame(section, bg=Theme.SURFACE2)
        header.pack(fill="x", padx=10, pady=(8, 6))

        self._exclusions_toggle = tk.Button(
            header,
            text="▾",
            width=2,
            bg=Theme.SURFACE2,
            fg=Theme.TEXT,
            activebackground=Theme.BORDER,
            activeforeground=Theme.TEXT,
            bd=0,
            cursor="hand2",
            command=self._toggle_section,
        )
        self._exclusions_toggle.pack(side="left")

        self._header_label = tk.Label(
            header,
            text=t("route.exclusions_label"),
            bg=Theme.SURFACE2,
            fg=Theme.TEXT,
            font=Theme.FONT_BOLD,
        )
        self._header_label.pack(side="left", padx=(4, 8))

        tk.Label(
            header,
            textvariable=self._exclusions_count_var,
            bg=Theme.SURFACE2,
            fg=Theme.MUTED,
        ).pack(side="left")

        self._clear_btn = tk.Button(
            header,
            text=t("route.exclusions_clear"),
            bg=Theme.SURFACE2,
            fg=Theme.MUTED,
            activebackground=Theme.BORDER,
            activeforeground=Theme.TEXT,
            bd=0,
            cursor="hand2",
            command=self._clear_all,
        )
        self._clear_btn.pack(side="right")

        self._body = tk.Frame(section, bg=Theme.SURFACE2)
        self._body.pack(fill="x", padx=10, pady=(0, 10))

        self._configure_combobox_style()
        self._country_combo = ttk.Combobox(
            self._body,
            textvariable=self._country_search_var,
            values=[],
            state="normal",
            height=8,
            style="RoutePlanner.TCombobox",
        )
        self._country_combo.pack(fill="x", pady=(0, 8))
        self._country_combo.bind("<KeyRelease>", self._on_search_key)
        self._country_combo.bind("<<ComboboxSelected>>", self._add_country)
        self._country_combo.bind("<Return>", self._add_country)

        tags_shell = tk.Frame(self._body, bg=Theme.SURFACE2)
        tags_shell.pack(fill="x")

        self._tags_canvas = tk.Canvas(tags_shell, bg=Theme.SURFACE2, highlightthickness=0)
        self._tags_scroll = tk.Scrollbar(tags_shell, orient="vertical", command=self._tags_canvas.yview)
        self._tags_frame = tk.Frame(self._tags_canvas, bg=Theme.SURFACE2)
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
        self._country_combo.configure(values=self._available_options(self._country_search_var.get()))

    def _add_country(self, event=None) -> None:
        code = self._code_from_input(self._country_search_var.get())
        if not code:
            options = self._available_options(self._country_search_var.get())
            code = self._code_from_input(options[0]) if options else None
        if not code:
            return
        selected = self.avoidance.get_selected()
        if code not in selected:
            selected.append(code)
            self.avoidance.set_selected(selected)
        self._country_search_var.set("")
        self.refresh()
        self._notify()

    def _remove_country(self, code: str) -> None:
        selected = [c for c in self.avoidance.get_selected() if c != code]
        self.avoidance.set_selected(selected)
        self.refresh()
        self._notify()

    def _clear_all(self) -> None:
        self.avoidance.clear()
        self._country_search_var.set("")
        self.refresh()
        self._notify()

    def refresh(self) -> None:
        self._country_combo.configure(values=self._available_options(""))
        self._render_tags()
        count = len(self.avoidance.get_selected())
        self._exclusions_count_var.set(
            t("route.exclusions_selected").format(count) if count else t("route.exclusions_none")
        )
        self._clear_btn.configure(text=t("route.exclusions_clear"), state="normal" if count else "disabled")
        self._header_label.config(text=t("route.exclusions_label"))

    def _render_tags(self) -> None:
        for w in self._tags_frame.winfo_children():
            w.destroy()

        selected = self.avoidance.get_selected()
        countries = self.avoidance.get_all_countries()

        if not selected:
            tk.Label(
                self._tags_frame,
                text=t("route.exclusions_empty"),
                bg=Theme.SURFACE2,
                fg=Theme.MUTED,
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
            row = tk.Frame(self._tags_frame, bg=Theme.SURFACE2)
            row.pack(fill="x", anchor="w")

            for code, name, label in row_data:
                chip = tk.Frame(row, bg=self._CHIP_BG, bd=0)

                tk.Label(
                    chip,
                    text=label,
                    bg=self._CHIP_BG,
                    fg=self._CHIP_FG,
                    font=self._CHIP_FONT,
                ).pack(side="left", padx=(self._CHIP_PAD_X, 2), pady=self._CHIP_PAD_Y)

                tk.Button(
                    chip,
                    text="✕",
                    bg=self._CHIP_BG,
                    fg=self._CHIP_FG,
                    activebackground=self._CHIP_ACTIVE_BG,
                    activeforeground=self._CHIP_FG,
                    bd=0,
                    cursor="hand2",
                    font=self._CHIP_REMOVE_FONT,
                    command=lambda c=code: self._remove_country(c),
                ).pack(side="left", padx=(0, self._CHIP_PAD_X), pady=self._CHIP_PAD_Y)

                chip.pack(side="left", padx=(0, self._CHIP_GAP), pady=self._CHIP_GAP)
