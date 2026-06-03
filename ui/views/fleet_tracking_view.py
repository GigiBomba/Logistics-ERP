"""Live Fleet Tracking view — map + vehicle list with polling."""
import logging
import threading
import tkinter as tk
from datetime import datetime
from typing import List, Optional

import customtkinter as ctk

from services.fleet_tracking_service import (
    VehiclePosition,
    fleet_tracking_service,
)
from services.i18n import t
from ui.theme import COLORS, FONTS, S, RADIUS_CHIP, btn, divider

logger = logging.getLogger(__name__)


class FleetTrackingView:
    def __init__(self, parent, db, prefs=None, ops=None,
                 embedded=False, on_navigate=None):
        self.db = db
        self.prefs = prefs
        self.ops = ops
        self._on_navigate = on_navigate
        self._embedded = embedded

        self._map = None
        self._markers = {}
        self._vehicle_list = None
        self._detail_panel = None
        self._refresh_btn = None
        self._updated_lbl = None
        self._after_ids = []
        self._selected_position = None

        if embedded:
            self.win = None
            self.frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_base"])
            self.frame.pack(fill="both", expand=True)
            self._tk_root = parent.winfo_toplevel()
        else:
            self.win = ctk.CTkToplevel(parent)
            self.win.title(f"\U0001f4cd {t('tracking.section_title')}")
            self.win.geometry("1200x750")
            self.frame = self.win
            self._tk_root = self.win

        self._build()

    # ── Lifecycle ─────────────────────────────────────────────────────

    def wakeup(self):
        """Called when view becomes active."""
        if fleet_tracking_service.is_configured():
            self._start_polling()

    def shutdown(self):
        """Called when view is hidden."""
        self._stop_polling()

    # ── Build ─────────────────────────────────────────────────────────

    def _build(self):
        self.frame.configure(fg_color=COLORS["bg_base"])

        if not fleet_tracking_service.is_configured():
            self._build_not_configured_state()
            return

        self.frame.columnconfigure(0, weight=72)
        self.frame.columnconfigure(1, weight=28)
        self.frame.rowconfigure(0, weight=1)

        map_frame = ctk.CTkFrame(self.frame, fg_color=COLORS["bg_base"],
                                 corner_radius=0)
        map_frame.grid(row=0, column=0, sticky="nsew")

        panel = ctk.CTkFrame(self.frame,
                             fg_color=COLORS["bg_surface"],
                             corner_radius=0)
        panel.grid(row=0, column=1, sticky="nsew")

        # 1px left border on right panel
        ctk.CTkFrame(panel, fg_color=COLORS["border"],
                     width=1, corner_radius=0).pack(
                         side="left", fill="y")

        self._build_map(map_frame)
        self._build_vehicle_panel(panel)

    def _build_not_configured_state(self):
        """Shown when no tracking platform is configured."""
        f = ctk.CTkFrame(self.frame, fg_color="transparent")
        f.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(f, text="\U0001f5fa",
                     font=("Segoe UI", 64),
                     text_color=COLORS["text_muted"]
                     ).pack()
        ctk.CTkLabel(f, text=t("tracking.not_configured_title"),
                     font=FONTS["h2"],
                     text_color=COLORS["text_primary"]
                     ).pack(pady=(S["4"], S["2"]))
        ctk.CTkLabel(f, text=t("tracking.not_configured_hint"),
                     font=FONTS["body"],
                     text_color=COLORS["text_muted"],
                     wraplength=360
                     ).pack()

        def go_to_settings():
            if self._on_navigate:
                self._on_navigate("settings")

        btn(f, t("tracking.go_to_settings"),
            command=go_to_settings,
            variant="primary"
            ).pack(pady=S["6"])

    def _build_map(self, parent):
        try:
            import tkintermapview
            self._map = tkintermapview.TkinterMapView(
                parent,
                corner_radius=0
            )
            self._map.pack(fill="both", expand=True)
            # Default center: Romania
            self._map.set_position(45.9432, 24.9668)
            self._map.set_zoom(7)
            self._map.set_tile_server(
                "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
            )
            self._markers = {}
        except ImportError:
            ctk.CTkLabel(
                parent,
                text="tkintermapview not installed.\n"
                     "Run: pip install tkintermapview",
                font=FONTS["body"],
                text_color=COLORS["text_muted"]
            ).place(relx=0.5, rely=0.5, anchor="center")
            self._map = None

    def _build_vehicle_panel(self, parent):
        # Header
        header = ctk.CTkFrame(parent, fg_color="transparent",
                              height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text=t("tracking.panel_title"),
                     font=FONTS["h3"],
                     text_color=COLORS["text_primary"]
                     ).pack(side="left", padx=S["5"], anchor="center")

        # Refresh button + last updated time
        self._refresh_btn = btn(
            header,
            "\u21bb",
            command=self._force_refresh,
            variant="ghost"
        )
        self._refresh_btn.pack(side="right", padx=S["3"])

        self._updated_lbl = ctk.CTkLabel(
            header, text="",
            font=FONTS["label"],
            text_color=COLORS["text_muted"]
        )
        self._updated_lbl.pack(side="right")

        divider(parent)

        # Vehicle list (scrollable)
        self._vehicle_list = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"]
        )
        self._vehicle_list.pack(fill="both", expand=True)

        # Selected vehicle detail (bottom, fixed height)
        divider(parent)
        self._detail_panel = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            height=200
        )
        self._detail_panel.pack(fill="x")
        self._detail_panel.pack_propagate(False)

    # ── Vehicle rows ──────────────────────────────────────────────────

    def _build_vehicle_row(self, position: VehiclePosition,
                           matched_truck_id: Optional[int]) -> None:
        row = ctk.CTkFrame(
            self._vehicle_list,
            fg_color="transparent",
            corner_radius=RADIUS_CHIP,
            height=52,
            cursor="hand2"
        )
        row.pack(fill="x", padx=S["2"], pady=1)
        row.pack_propagate(False)

        # Status indicator dot
        status_color = {
            "moving":  COLORS["success"],
            "stopped": COLORS["text_muted"],
            "idle":    COLORS["warning"],
            "offline": COLORS["danger"],
        }.get(position.status, COLORS["text_muted"])

        dot = ctk.CTkLabel(row, text="\u25cf",
                           font=FONTS["small"],
                           text_color=status_color,
                           width=20)
        dot.pack(side="left", padx=(S["3"], 0))

        # Vehicle name
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=S["2"])

        ctk.CTkLabel(info, text=position.name,
                     font=FONTS["body_bold"],
                     text_color=COLORS["text_primary"],
                     anchor="w").pack(anchor="w")

        detail_str = (
            f"{position.speed_kmh:.0f} km/h" if position.speed_kmh > 3
            else (position.address[:30] + "\u2026"
                  if position.address and len(position.address) > 30
                  else position.address or "Stopped")
        )
        ctk.CTkLabel(info, text=detail_str,
                     font=FONTS["small"],
                     text_color=COLORS["text_secondary"],
                     anchor="w").pack(anchor="w")

        # Hover effects
        def on_enter(e):
            row.configure(fg_color=COLORS["bg_elevated"])

        def on_leave(e):
            row.configure(fg_color="transparent")

        def on_click(e, p=position, tid=matched_truck_id):
            self._select_vehicle(p, tid)

        for w in (row, dot, info):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)

    def _select_vehicle(self, position: VehiclePosition,
                        truck_id: Optional[int]) -> None:
        """Pan map to vehicle + show detail panel."""
        if self._map and position.latitude and position.longitude:
            self._map.set_position(position.latitude, position.longitude)
            self._map.set_zoom(14)

        # Build detail panel
        for w in self._detail_panel.winfo_children():
            w.destroy()

        f = ctk.CTkFrame(self._detail_panel,
                         fg_color="transparent")
        f.pack(fill="both", expand=True, padx=S["5"], pady=S["4"])

        ctk.CTkLabel(f, text=position.name,
                     font=FONTS["h3"],
                     text_color=COLORS["text_primary"],
                     anchor="w").pack(anchor="w")

        details = [
            (t("tracking.d_status"),  position.status.title()),
            (t("tracking.d_speed"),   f"{position.speed_kmh:.0f} km/h"),
            (t("tracking.d_updated"), position.timestamp.strftime("%H:%M:%S")),
        ]
        if position.odometer_km:
            details.append((t("tracking.d_odometer"),
                            f"{position.odometer_km:,.0f} km"))
        if position.address:
            addr = (position.address[:40] + "\u2026"
                    if len(position.address) > 40
                    else position.address)
            details.append((t("tracking.d_address"), addr))

        for label, value in details:
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=label,
                         font=FONTS["label"],
                         text_color=COLORS["text_muted"],
                         width=90, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value,
                         font=FONTS["small"],
                         text_color=COLORS["text_primary"],
                         anchor="w").pack(side="left")

        if truck_id:
            def view_fleet():
                if self._on_navigate:
                    self._on_navigate("fleet")

            btn(f, t("tracking.btn_fleet_detail"),
                command=view_fleet,
                variant="ghost"
                ).pack(anchor="w", pady=(S["3"], 0))

    # ── Map markers ───────────────────────────────────────────────────

    def _update_map_markers(self,
                            positions: List[VehiclePosition]) -> None:
        if not self._map:
            return

        current_ids = {p.device_id for p in positions}

        # Remove markers for vehicles no longer in data
        for device_id in list(self._markers.keys()):
            if device_id not in current_ids:
                try:
                    self._markers[device_id].delete()
                except Exception:
                    pass
                del self._markers[device_id]

        # Add or update markers
        for pos in positions:
            if not pos.latitude or not pos.longitude:
                continue

            # Marker color based on status
            color = {
                "moving":  "#22c55e",
                "stopped": "#94a3b8",
                "idle":    "#f59e0b",
                "offline": "#ef4444",
            }.get(pos.status, "#94a3b8")

            marker_text = f"\U0001f69b {pos.name}"
            if pos.speed_kmh > 3:
                marker_text += f" {pos.speed_kmh:.0f}km/h"

            if pos.device_id in self._markers:
                # Update position
                self._markers[pos.device_id].set_position(
                    pos.latitude, pos.longitude
                )
                self._markers[pos.device_id].set_text(marker_text)
            else:
                # Create new marker
                try:
                    marker = self._map.set_marker(
                        pos.latitude, pos.longitude,
                        text=marker_text,
                        marker_color_circle=color,
                        marker_color_outside=color,
                    )
                    self._markers[pos.device_id] = marker
                except Exception as e:
                    logger.warning("Could not add marker: %s", e)

    # ── Vehicle list refresh ──────────────────────────────────────────

    def _refresh_vehicle_list(self,
                              positions: List[VehiclePosition]) -> None:
        for w in self._vehicle_list.winfo_children():
            w.destroy()

        if not positions:
            ctk.CTkLabel(self._vehicle_list,
                         text=t("tracking.no_vehicles"),
                         font=FONTS["body"],
                         text_color=COLORS["text_muted"]
                         ).pack(pady=S["8"])
            return

        for pos in sorted(positions,
                           key=lambda p: p.name.lower()):
            truck_id = fleet_tracking_service.match_to_truck(pos)
            self._build_vehicle_row(pos, truck_id)

        self._updated_lbl.configure(
            text=datetime.now().strftime("%H:%M:%S")
        )

    # ── Polling ───────────────────────────────────────────────────────

    def _poll_and_update(self) -> None:
        """Runs in background thread — fetches positions."""
        try:
            positions = fleet_tracking_service.get_positions(
                force_refresh=True
            )
            # Update UI on main thread
            self.frame.after(0, lambda p=positions: self._apply_update(p))
        except Exception as e:
            logger.error("Tracking poll error: %s", e)

    def _apply_update(self, positions: List[VehiclePosition]) -> None:
        self._update_map_markers(positions)
        self._refresh_vehicle_list(positions)
        # Schedule next poll
        self._schedule_next_poll()

    def _schedule_next_poll(self):
        try:
            aid = self._tk_root.after(30_000, self._poll_and_update)
            self._after_ids.append(aid)
        except tk.TclError:
            pass

    def _start_polling(self) -> None:
        # Initial load immediately
        self._poll_and_update()

    def _stop_polling(self) -> None:
        for aid in self._after_ids:
            try:
                self._tk_root.after_cancel(aid)
            except tk.TclError:
                pass
        self._after_ids.clear()

    # ── Refresh button ────────────────────────────────────────────────

    def _force_refresh(self) -> None:
        self._refresh_btn.configure(state="disabled")

        def do():
            try:
                positions = fleet_tracking_service.get_positions(
                    force_refresh=True
                )
                self.frame.after(0, lambda p=positions: (
                    self._apply_update(p),
                    self._refresh_btn.configure(state="normal")
                ))
            except Exception as e:
                logger.error("Force refresh failed: %s", e)
                self.frame.after(0, lambda: (
                    self._refresh_btn.configure(state="normal")
                ))

        threading.Thread(target=do, daemon=True).start()
