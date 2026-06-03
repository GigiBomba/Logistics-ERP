"""Collapsible fuel price chart panel — extracted from dashboard.py."""
import tkinter as tk
import customtkinter as ctk
from typing import Optional

from services.fuel_price_service import FuelPriceService
from services.i18n import t
from ui.styles import Theme
from ui.theme import FONTS


class FuelPricePanel(ctk.CTkFrame):
    """Collapsible bar chart of diesel prices by country."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=Theme.SURFACE2, **kwargs)
        self._expanded = False
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color=Theme.SURFACE2)
        header.pack(fill="x")

        ctk.CTkLabel(header, text=t("fuel.section_title"), fg_color=Theme.SURFACE2, text_color=Theme.ACCENT,
                     font=FONTS["small"]).pack(side="left")

        self._status_lbl = ctk.CTkLabel(header, text="", fg_color=Theme.SURFACE2,
                                        text_color=Theme.MUTED, font=FONTS["label"], anchor="e")
        self._status_lbl.pack(side="right", padx=(10, 0))

        toggle_btn = ctk.CTkLabel(header, text="\u25BC", fg_color=Theme.SURFACE2, text_color=Theme.MUTED,
                                  cursor="hand2", font=FONTS["label"])
        toggle_btn.pack(side="right")
        toggle_btn.bind("<Button-1>", lambda e: self._toggle())

        self._body = ctk.CTkFrame(self, fg_color=Theme.SURFACE2, height=0)
        self._canvas = tk.Canvas(self._body, bg=Theme.SURFACE2, highlightthickness=0, bd=0, height=120)

        self._update_status()

    def _toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._body.pack(fill="x", pady=(6, 0))
            self._canvas.pack(fill="x", padx=10)
            self._draw_chart()
        else:
            self._canvas.pack_forget()
            self._body.pack_forget()

    def refresh(self):
        self._update_status()
        if self._expanded:
            self._draw_chart()

    def _update_status(self):
        svc = FuelPriceService()
        ts = svc.last_updated_str()
        age = svc.age_seconds()
        if age is not None:
            if age < 60:
                age_s = t("fuel.age_seconds").format(n=f"{age:.0f}")
            elif age < 3600:
                age_s = t("fuel.age_minutes").format(n=f"{age/60:.0f}")
            else:
                age_s = t("fuel.age_hours").format(n=f"{age/3600:.1f}")
            self._status_lbl.config(text=t("fuel.updated_status").format(ts=ts, age=age_s))
        else:
            self._status_lbl.config(text=t("fuel.not_fetched"))

    def _draw_chart(self):
        self._canvas.delete("all")
        svc = FuelPriceService()
        prices = svc.get_prices_all()
        if not prices:
            self._canvas.create_text(200, 30, text=t("fuel.no_data"),
                                     fill=Theme.MUTED, anchor="nw")
            return
        sorted_prices = sorted([(c, p) for c, p in prices.items() if c != "DEFAULT"],
                               key=lambda x: x[1], reverse=True)[:15]
        if not sorted_prices:
            return
        max_p = max(p for _, p in sorted_prices)
        bar_h, gap, top, label_w = 16, 4, 6, 30
        bar_area_w = max(self._canvas.winfo_width() - label_w - 60, 300)

        for i, (code, price) in enumerate(sorted_prices):
            y = top + i * (bar_h + gap)
            self._canvas.create_text(4, y + bar_h // 2, text=code, fill=Theme.TEXT,
                                     font=FONTS["label"], anchor="w")
            bw = int((price / max_p) * bar_area_w)
            color = Theme.DANGER if price > 1.8 else (Theme.WARNING if price > 1.4 else Theme.SUCCESS)
            self._canvas.create_rectangle(label_w, y, label_w + bw, y + bar_h,
                                          fill=color, outline="")
            self._canvas.create_text(label_w + bw + 4, y + bar_h // 2,
                                     text=f"{price:.3f}\u20AC", fill=Theme.MUTED,
                                      font=FONTS["label"], anchor="w")
        self._canvas.configure(height=top + len(sorted_prices) * (bar_h + gap))
