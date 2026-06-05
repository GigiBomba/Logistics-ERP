"""Slide-in detail panel for viewing/editing trip details from the dispatch board."""
import tkinter as tk
import customtkinter as ctk
from services.i18n import t
from ui.theme import COLORS, FONTS
from ui.styles import Theme
from services.operations.event_bus import VALID_TRANSITIONS, EventBus, TRIP_UPDATED


STATUS_TO_COLUMN_UI = {
    "Planned": COLORS["chip_planned"],
    "Loading": COLORS["chip_loading"],
    "In Transit": COLORS["chip_transit"],
    "Delivered": COLORS["chip_delivered"],
    "Cancelled": COLORS["chip_cancelled"],
}


class DispatchDetailPanel(ctk.CTkToplevel):
    """Popup showing full trip detail with edit capability."""

    def __init__(self, parent, trip_data: dict, db, on_save=None, on_close=None, ops=None):
        super().__init__(parent)
        self.title(t("dispatch_board.detail_title"))
        self.geometry("480x620")
        self.configure(fg_color=COLORS["bg_surface"])
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self._trip_data = dict(trip_data)
        self._db = db
        self._on_save = on_save
        self._on_close_cb = on_close
        self._ops = ops
        self._editing = False
        self._edit_widgets = {}
        self._btn_row = None
        self._fields_frame = None
        self._alerts_frame = None

        from services.trip_service import TripService
        self._trip_service = TripService(db)

        self._build()
        self.after(100, lambda: self.focus_set())
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_surface"])
        self._scroll.pack(fill="both", expand=True, padx=12, pady=12)

        self._build_header()
        self._fields_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._fields_frame.pack(fill="x")
        self._build_fields_view()
        self._alerts_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._alerts_frame.pack(fill="x")
        self._build_alerts()
        self._build_buttons()

    def _build_header(self):
        hdr = ctk.CTkFrame(self._scroll, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))

        trip_id = self._trip_data.get("trip_id", "")
        ctk.CTkLabel(hdr, text=trip_id, fg_color="transparent",
                     text_color=COLORS["text_primary"], font=FONTS["h2"]).pack(anchor="w")

        status = self._trip_data.get("status", "Planned")
        chip_color = STATUS_TO_COLUMN_UI.get(status, COLORS["chip_planned"])
        chip = ctk.CTkFrame(hdr, fg_color=chip_color)
        ctk.CTkLabel(chip, text=status, fg_color=chip_color,
                     text_color=COLORS["text_primary"], font=FONTS["label"]).pack(padx=8, pady=2)
        chip.pack(anchor="w", pady=(4, 0))

    def _build_fields_view(self):
        for w in self._fields_frame.winfo_children():
            w.destroy()

        fields = [
            ("dispatch_board.detail_truck", "truck_plate", lambda v: v or t("common.na")),
            ("dispatch_board.detail_driver", "driver_name", lambda v: v or t("common.na")),
            ("dispatch_board.detail_route",
             None,
             lambda v: f"{self._trip_data.get('origin','?')} \u2192 {self._trip_data.get('destination','?')}"),
            ("dispatch_board.detail_departure", "departure_date", lambda v: v or t("common.na")),
            ("dispatch_board.detail_eta", "eta", lambda v: v or t("common.na")),
            ("dispatch_board.detail_distance", "distance_km", lambda v: f"{v} km" if v else ""),
            ("dispatch_board.detail_price", "total_price_eur", lambda v: f"{v:,.2f}" if v else ""),
            ("dispatch_board.detail_net_profit", "net_profit", lambda v: f"{v:,.2f}" if v else ""),
        ]

        for label_key, data_key, fmt_fn in fields:
            row = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            row.pack(fill="x", pady=(0, 6))

            ctk.CTkLabel(row, text=t(label_key), fg_color="transparent",
                        text_color=COLORS["text_muted"], font=FONTS["label"],
                        width=100, anchor="w").pack(side="left")

            value = fmt_fn(self._trip_data) if data_key is None else fmt_fn(self._trip_data.get(data_key, ""))
            ctk.CTkLabel(row, text=str(value), fg_color="transparent",
                        text_color=COLORS["text_primary"], font=FONTS["body"],
                        anchor="w").pack(side="left", fill="x", expand=True)

    def _build_fields_edit(self):
        for w in self._fields_frame.winfo_children():
            w.destroy()
        self._edit_widgets = {}

        status = self._trip_data.get("status", "Planned")
        valid_targets = VALID_TRANSITIONS.get(status, [])

        row1 = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(row1, text=t("dispatch_board.detail_status"), fg_color="transparent",
                    text_color=COLORS["text_muted"], font=FONTS["label"],
                    width=100, anchor="w").pack(side="left")
        status_cb = ctk.CTkComboBox(
            row1, values=valid_targets, state="readonly",
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            border_width=1, text_color=COLORS["text_primary"],
            font=FONTS["body"], height=30, corner_radius=6,
            button_color=COLORS["bg_elevated"],
            button_hover_color=COLORS["border_hover"],
            dropdown_fg_color=COLORS["bg_surface"],
            dropdown_text_color=COLORS["text_primary"],
            dropdown_hover_color=COLORS["bg_elevated"],
        )
        if valid_targets:
            status_cb.set(valid_targets[0])
        status_cb.pack(side="left", fill="x", expand=True)
        self._edit_widgets["status"] = status_cb

        row2 = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(row2, text=t("dispatch_board.detail_departure"), fg_color="transparent",
                    text_color=COLORS["text_muted"], font=FONTS["label"],
                    width=100, anchor="w").pack(side="left")
        dep_entry = ctk.CTkEntry(
            row2, fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            border_width=1, text_color=COLORS["text_primary"],
            font=FONTS["body"], height=30, corner_radius=6,
        )
        dep_entry.insert(0, self._trip_data.get("departure_date", ""))
        dep_entry.pack(side="left", fill="x", expand=True)
        self._edit_widgets["departure_date"] = dep_entry

        row3 = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(row3, text=t("dispatch_board.detail_eta"), fg_color="transparent",
                    text_color=COLORS["text_muted"], font=FONTS["label"],
                    width=100, anchor="w").pack(side="left")
        eta_entry = ctk.CTkEntry(
            row3, fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            border_width=1, text_color=COLORS["text_primary"],
            font=FONTS["body"], height=30, corner_radius=6,
        )
        eta_entry.insert(0, self._trip_data.get("eta", ""))
        eta_entry.pack(side="left", fill="x", expand=True)
        self._edit_widgets["eta"] = eta_entry

        row4 = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        row4.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(row4, text=t("dispatch_board.detail_distance"), fg_color="transparent",
                    text_color=COLORS["text_muted"], font=FONTS["label"],
                    width=100, anchor="w").pack(side="left")
        dist_entry = ctk.CTkEntry(
            row4, fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            border_width=1, text_color=COLORS["text_primary"],
            font=FONTS["body"], height=30, corner_radius=6,
        )
        dist_val = self._trip_data.get("distance_km", "")
        if dist_val:
            dist_entry.insert(0, str(dist_val))
        dist_entry.pack(side="left", fill="x", expand=True)
        self._edit_widgets["distance_km"] = dist_entry

    def _build_alerts(self):
        for w in self._alerts_frame.winfo_children():
            w.destroy()

        sep = ctk.CTkFrame(self._alerts_frame, fg_color=COLORS["border"], height=1)
        sep.pack(fill="x", pady=(8, 4))

        if not self._editing:
            ctk.CTkLabel(self._alerts_frame, text=t("dispatch_board.detail_alerts_for_trip"),
                        fg_color="transparent", text_color=COLORS["text_primary"],
                        font=FONTS["h3"]).pack(anchor="w", pady=(4, 6))

            trip_id_num = self._trip_data.get("trip_id_num")
            if self._ops and trip_id_num:
                all_alerts = self._ops.get_alerts(resolved=False, limit=200)
                tid_str = str(trip_id_num)
                alerts = [a for a in all_alerts if str(getattr(a, "trip_id", "")) == tid_str][:20]
                if alerts:
                    for alert in alerts:
                        sev_color = {"critical": COLORS["danger"], "warning": COLORS["warning"]}.get(
                            getattr(alert.severity, "value", ""), COLORS["info"])
                        arow = ctk.CTkFrame(self._alerts_frame, fg_color=COLORS["bg_elevated"], corner_radius=4)
                        arow.pack(fill="x", pady=(0, 3))
                        ctk.CTkLabel(arow, text=getattr(alert.severity, "value", "?").upper(),
                                    fg_color=sev_color, text_color="#ffffff",
                                    font=FONTS["label"], width=60, corner_radius=3).pack(side="left", padx=6, pady=4)
                        ctk.CTkLabel(arow, text=getattr(alert, "message", "")[:80],
                                    fg_color="transparent", text_color=COLORS["text_secondary"],
                                    font=FONTS["label"], anchor="w").pack(side="left", fill="x", expand=True, padx=6, pady=4)
                else:
                    ctk.CTkLabel(self._alerts_frame, text=t("dispatch_board.detail_no_alerts"),
                                fg_color="transparent", text_color=COLORS["text_muted"],
                                font=FONTS["label"]).pack(anchor="w")
            else:
                ctk.CTkLabel(self._alerts_frame, text=t("dispatch_board.detail_no_alerts"),
                            fg_color="transparent", text_color=COLORS["text_muted"],
                            font=FONTS["label"]).pack(anchor="w")

    def _build_buttons(self):
        if self._btn_row:
            for w in self._btn_row.winfo_children():
                w.destroy()
        else:
            self._btn_row = ctk.CTkFrame(self, fg_color=COLORS["bg_elevated"], height=52)
            self._btn_row.pack(fill="x", side="bottom")
            self._btn_row.pack_propagate(False)

        if self._editing:
            save_btn = ctk.CTkButton(
                self._btn_row, text=t("dispatch_board.detail_save"),
                fg_color=COLORS["accent"], text_color="#ffffff",
                font=FONTS["body_bold"], cursor="hand2", height=32,
                command=self._save_changes,
            )
            save_btn.pack(side="right", padx=(6, 12), pady=10)

            cancel_btn = ctk.CTkButton(
                self._btn_row, text=t("dispatch_board.detail_cancel"),
                fg_color=COLORS["bg_elevated"], text_color=COLORS["text_secondary"],
                font=FONTS["body_bold"], cursor="hand2", height=32,
                command=self._cancel_edit,
            )
            cancel_btn.pack(side="right", padx=6, pady=10)
        else:
            edit_btn = ctk.CTkButton(
                self._btn_row, text=t("dispatch_board.detail_edit_button"),
                fg_color=COLORS["accent"], text_color="#ffffff",
                font=FONTS["body_bold"], cursor="hand2", height=32,
                command=self._enter_edit_mode,
            )
            edit_btn.pack(side="right", padx=(6, 12), pady=10)

            close_btn = ctk.CTkButton(
                self._btn_row, text=t("dispatch_board.detail_close"),
                fg_color=COLORS["bg_elevated"], text_color=COLORS["text_secondary"],
                font=FONTS["body_bold"], cursor="hand2", height=32,
                command=self._close,
            )
            close_btn.pack(side="right", padx=6, pady=10)

    def _enter_edit_mode(self):
        self._editing = True
        self._edit_widgets = {}
        self._build_fields_edit()
        self._build_alerts()
        self._build_buttons()

    def _cancel_edit(self):
        self._editing = False
        self._edit_widgets = {}
        self._build_fields_view()
        self._build_alerts()
        self._build_buttons()

    def _save_changes(self):
        trip_id = self._trip_data.get("trip_id_num") or self._trip_data.get("id")
        if not trip_id:
            self._show_inline_error("Cannot identify trip.")
            return

        changes = {}
        status_w = self._edit_widgets.get("status")
        if status_w:
            new_status = status_w.get()
            if new_status:
                changes["status"] = new_status
                self._trip_data["status"] = new_status

        for field in ("departure_date", "eta"):
            w = self._edit_widgets.get(field)
            if w:
                val = w.get().strip()
                if val:
                    changes[field] = val
                    self._trip_data[field] = val

        dist_w = self._edit_widgets.get("distance_km")
        if dist_w:
            val = dist_w.get().strip()
            if val:
                try:
                    changes["distance_km"] = float(val)
                except ValueError:
                    pass

        if not changes:
            self._cancel_edit()
            return

        try:
            self._trip_service.update(int(trip_id), changes)
            EventBus().publish(TRIP_UPDATED, {"trip_id": int(trip_id), "changes": changes})
            if self._on_save:
                self._on_save(self._trip_data)
        except Exception as e:
            self._show_inline_error(str(e))
            return

        self._editing = False
        self._edit_widgets = {}
        self._build_header()
        self._build_fields_view()
        self._build_alerts()
        self._build_buttons()

    def _show_inline_error(self, msg: str):
        for w in self._fields_frame.winfo_children():
            w.destroy()
        err = ctk.CTkLabel(
            self._fields_frame, text=msg,
            fg_color=COLORS["danger"], text_color="#ffffff",
            font=FONTS["body"], corner_radius=6,
        )
        err.pack(fill="x", pady=6)
        self._alerts_frame.after(3000, lambda e=err: e.destroy() if e.winfo_exists() else None)
        self._alerts_frame.after(3000, self._cancel_edit)

    def _close(self):
        if self._on_close_cb:
            self._on_close_cb()
        self.destroy()
