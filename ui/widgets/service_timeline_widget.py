import tkinter as tk
import customtkinter as ctk
from tkinter import ttk
from typing import Any, Dict, List, Optional, Callable

from services.i18n import t
from ui.icons import iconed
from services.fleet_maintenance_service import (
    FleetMaintenanceService, MaintType, MAINT_DISPLAY, MAINT_ICONS,
)
from ui.styles import Theme
from ui.widgets import ActionButton, StyledEntry
from ui.theme import COLORS, FONTS

NODE_COLORS = {
    MaintType.TIRE_REPLACEMENT: COLORS["text_muted"],
    MaintType.OIL_CHANGE: COLORS["warning"],
    MaintType.BRAKES: COLORS["danger"],
}
DEFAULT_NODE_COLOR = COLORS["text_muted"]
LINE_COLOR = Theme.SURFACE2
NODE_RADIUS = 7


class ServiceTimelineWidget(ctk.CTkFrame):
    def __init__(self, parent, service: FleetMaintenanceService, truck_id: int,
                 truck_plate: str, win: tk.Toplevel,
                 on_edit_record: Optional[Callable[[Dict[str, Any]], None]] = None):
        super().__init__(parent, fg_color=Theme.BG)
        self.service = service
        self.truck_id = truck_id
        self.truck_plate = truck_plate
        self.win = win
        self.on_edit_record = on_edit_record

        self._build()

    def _node_color(self, maint_type: str) -> str:
        try:
            return NODE_COLORS.get(MaintType(maint_type), DEFAULT_NODE_COLOR)
        except ValueError:
            return DEFAULT_NODE_COLOR

    def _build(self):
        header = ctk.CTkFrame(self, fg_color=Theme.BG)
        header.pack(fill="x", pady=(0, 6))
        self._header_title_label = ctk.CTkLabel(
            header, text=iconed("maint_timeline.title"),
            fg_color=Theme.BG, text_color=Theme.TEXT, font=FONTS["small"],
        )
        self._header_title_label.pack(side="left")
        ActionButton(header, iconed("maint.refresh"), self.refresh,
                     color=Theme.SURFACE2).pack(side="right", padx=2)

        container = ctk.CTkFrame(self, fg_color=Theme.BG)
        container.pack(fill="both", expand=True)

        self._scroll_frame = ctk.CTkScrollableFrame(container, fg_color=Theme.BG)
        self._scroll_frame.pack(fill="both", expand=True)

        self.refresh()

    def refresh(self):
        for w in self._scroll_frame.winfo_children():
            w.destroy()

        records = self.service.get_records(truck_id=self.truck_id, limit=1000)
        records.sort(key=lambda r: r.get("date", ""), reverse=True)

        if not records:
            ctk.CTkLabel(self._scroll_frame, text=iconed("maint.no_records"),
                     fg_color=Theme.BG, text_color=Theme.MUTED, font=FONTS["label"]).pack(pady=30)
            return

        for idx, rec in enumerate(records):
            self._draw_node(rec, is_last=(idx == len(records) - 1))

    def refresh_translations(self):
        self._header_title_label.configure(text=iconed("maint_timeline.title"))

    def _draw_node(self, rec: Dict[str, Any], is_last: bool = False):
        node_frame = ctk.CTkFrame(self._scroll_frame, fg_color=Theme.BG)
        node_frame.pack(fill="x", padx=(8, 4), pady=(0, 0))

        row = ctk.CTkFrame(node_frame, fg_color=Theme.BG)
        row.pack(fill="x")

        left = ctk.CTkFrame(row, width=40, fg_color=Theme.BG)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        dot_canvas = tk.Canvas(left, width=40, height=30, bg=Theme.BG, highlightthickness=0)
        dot_canvas.pack()

        color = self._node_color(rec["maintenance_type"])
        cx, cy = 20, 15
        dot_canvas.create_oval(cx - NODE_RADIUS, cy - NODE_RADIUS,
                               cx + NODE_RADIUS, cy + NODE_RADIUS,
                               fill=color, outline="", width=0)
        dot_canvas.create_oval(cx - NODE_RADIUS + 1, cy - NODE_RADIUS + 1,
                               cx + NODE_RADIUS - 1, cy + NODE_RADIUS - 1,
                               fill=color, outline=Theme.SURFACE2, width=1)

        content = ctk.CTkFrame(row, fg_color=Theme.BG)
        content.pack(side="left", fill="x", expand=True, padx=(4, 8), pady=4)
        content.bind("<Button-1>", lambda e, r=rec: self._on_node_click(r))

        date_str = rec.get("date", "")[:10] if rec.get("date") else ""
        try:
            icon = MAINT_ICONS.get(MaintType(rec["maintenance_type"]), "\u2699\uFE0F")
            disp = MAINT_DISPLAY.get(MaintType(rec["maintenance_type"]), rec["maintenance_type"].replace("_", " ").title())
        except ValueError:
            icon = "\u2699\uFE0F"
            disp = rec["maintenance_type"].replace("_", " ").title()

        ctk.CTkLabel(content, text=date_str, fg_color=Theme.BG, text_color=Theme.TEXT,
                 font=FONTS["small"]).pack(anchor="w")
        ctk.CTkLabel(content, text=f"{icon} {disp}", fg_color=Theme.BG, text_color=Theme.MUTED,
                 font=FONTS["label"]).pack(anchor="w")

        parts = []
        cost = rec.get("cost")
        if cost is not None:
            parts.append(f"\u20AC{float(cost):.2f}")
        provider = rec.get("service_provider", "") or ""
        if provider:
            parts.append(provider)
        notes = rec.get("notes", "") or ""
        if notes and not provider:
            parts.append(notes[:50])
        if parts:
            ctk.CTkLabel(content, text="  |  ".join(parts), fg_color=Theme.BG, text_color=Theme.MUTED,
                     font=FONTS["label"]).pack(anchor="w", pady=(1, 0))

        if notes and provider:
            ctk.CTkLabel(content, text=notes[:60], fg_color=Theme.BG, text_color=Theme.MUTED,
                     font=FONTS["label"]).pack(anchor="w")

        if not is_last:
            line = ctk.CTkFrame(self._scroll_frame, fg_color=Theme.BG)
            line.pack(fill="x", padx=(8, 4))
            line_canvas = tk.Canvas(line, width=40, height=14, bg=Theme.BG, highlightthickness=0)
            line_canvas.pack()
            line_canvas.create_line(20, 0, 20, 14, fill=LINE_COLOR, width=2)

    def _on_node_click(self, rec: Dict[str, Any]):
        if self.on_edit_record:
            self.on_edit_record(rec)
        else:
            self._show_detail_popup(rec)

    def _show_detail_popup(self, rec: Dict[str, Any]):
        win = ctk.CTkToplevel(self.win)
        win.title(iconed("maint_timeline.detail_title"))
        win.geometry("420x300")
        win.configure(fg_color=Theme.BG)
        Theme.apply(win)

        f = ctk.CTkFrame(win, fg_color=Theme.BG)
        f.pack(fill="both", expand=True, padx=20, pady=16)

        date_str = rec.get("date", "")[:10] if rec.get("date") else t("common.na")
        try:
            disp = MAINT_DISPLAY.get(MaintType(rec["maintenance_type"]), rec["maintenance_type"])
        except ValueError:
            disp = rec["maintenance_type"]

        rows = [
            (iconed("maint_timeline.field_date"), date_str),
            (iconed("maint_timeline.field_type"), disp),
            (iconed("maint_timeline.field_cost"), f"\u20AC{float(rec['cost']):.2f}" if rec.get("cost") is not None else t("common.na")),
            (iconed("maint_timeline.field_km"), f"{float(rec['km']):,.0f}" if rec.get("km") else t("common.na")),
            (iconed("maint_timeline.field_provider"), rec.get("service_provider", "") or t("common.na")),
            (iconed("maint_timeline.field_notes"), rec.get("notes", "") or t("common.na")),
        ]
        for label, val in rows:
            r = ctk.CTkFrame(f, fg_color=Theme.BG)
            r.pack(fill="x", pady=2)
            ctk.CTkLabel(r, text=label, fg_color=Theme.BG, text_color=Theme.MUTED,
                     font=FONTS["label"], width=10, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=val, fg_color=Theme.BG, text_color=Theme.TEXT,
                     font=FONTS["label"]).pack(side="left", padx=(4, 0))

        ActionButton(f, iconed("maint.cancel"), win.destroy, color=Theme.SURFACE2).pack(pady=(12, 0))
