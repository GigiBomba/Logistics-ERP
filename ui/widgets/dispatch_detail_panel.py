"""Slide-in detail panel for viewing/editing trip details from the dispatch board."""
import tkinter as tk
import customtkinter as ctk
from datetime import datetime
from services.i18n import t
from ui.theme import COLORS, FONTS
from ui.styles import Theme


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

        self._build()
        self.after(100, lambda: self.focus_set())
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_surface"])
        self._scroll.pack(fill="both", expand=True, padx=12, pady=12)

        self._build_header()
        self._build_fields()
        self._build_alerts()
        self._build_buttons()

    def _build_header(self):
        hdr = ctk.CTkFrame(self._scroll, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))

        trip_id = self._trip_data.get("trip_id", "")
        ctk.CTkLabel(hdr, text=trip_id, fg_color="transparent",
                     text_color=COLORS["text_primary"], font=FONTS["h2"]).pack(anchor="w")

        status = self._trip_data.get("status", "Planned")
        status_colors = {
            "Planned": COLORS["chip_planned"],
            "Loading": COLORS["chip_loading"],
            "In Transit": COLORS["chip_transit"],
            "Delivered": COLORS["chip_delivered"],
        }
        chip = ctk.CTkFrame(hdr, fg_color=status_colors.get(status, COLORS["chip_planned"]))
        ctk.CTkLabel(chip, text=status, fg_color=status_colors.get(status, COLORS["chip_planned"]),
                     text_color=COLORS["text_primary"], font=FONTS["label"]).pack(padx=8, pady=2)
        chip.pack(anchor="w", pady=(4, 0))

    def _build_fields(self):
        fields = [
            ("dispatch_board.detail_truck", "truck_plate", lambda v: v or t("common.na")),
            ("dispatch_board.detail_driver", "driver_name", lambda v: v or t("common.na")),
            ("dispatch_board.detail_client", "client_name", lambda v: v or t("common.na")),
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
            row = ctk.CTkFrame(self._scroll, fg_color="transparent")
            row.pack(fill="x", pady=(0, 6))

            ctk.CTkLabel(row, text=t(label_key), fg_color="transparent",
                        text_color=COLORS["text_muted"], font=FONTS["label"],
                        width=100, anchor="w").pack(side="left")

            value = fmt_fn(self._trip_data) if data_key is None else fmt_fn(self._trip_data.get(data_key, ""))
            ctk.CTkLabel(row, text=str(value), fg_color="transparent",
                        text_color=COLORS["text_primary"], font=FONTS["body"],
                        anchor="w").pack(side="left", fill="x", expand=True)

    def _build_alerts(self):
        sep = ctk.CTkFrame(self._scroll, fg_color=COLORS["border"], height=1)
        sep.pack(fill="x", pady=(8, 4))

        ctk.CTkLabel(self._scroll, text=t("dispatch_board.detail_alerts_for_trip"),
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
                    arow = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_elevated"], corner_radius=4)
                    arow.pack(fill="x", pady=(0, 3))
                    ctk.CTkLabel(arow, text=getattr(alert.severity, "value", "?").upper(),
                                fg_color=sev_color, text_color="#ffffff",
                                font=FONTS["label"], width=60, corner_radius=3).pack(side="left", padx=6, pady=4)
                    ctk.CTkLabel(arow, text=getattr(alert, "message", "")[:80],
                                fg_color="transparent", text_color=COLORS["text_secondary"],
                                font=FONTS["label"], anchor="w").pack(side="left", fill="x", expand=True, padx=6, pady=4)
            else:
                ctk.CTkLabel(self._scroll, text=t("dispatch_board.detail_no_alerts"),
                            fg_color="transparent", text_color=COLORS["text_muted"],
                            font=FONTS["label"]).pack(anchor="w")
        else:
            ctk.CTkLabel(self._scroll, text=t("dispatch_board.detail_no_alerts"),
                        fg_color="transparent", text_color=COLORS["text_muted"],
                        font=FONTS["label"]).pack(anchor="w")

    def _build_buttons(self):
        btn_row = ctk.CTkFrame(self, fg_color=COLORS["bg_elevated"], height=52)
        btn_row.pack(fill="x", side="bottom")
        btn_row.pack_propagate(False)

        close_btn = ctk.CTkButton(
            btn_row, text=t("dispatch_board.detail_close"),
            fg_color=COLORS["bg_elevated"], text_color=COLORS["text_secondary"],
            font=FONTS["body_bold"], cursor="hand2", height=32,
            command=self._close,
        )
        close_btn.pack(side="right", padx=12, pady=10)

    def _close(self):
        if self._on_close_cb:
            self._on_close_cb()
        self.destroy()
