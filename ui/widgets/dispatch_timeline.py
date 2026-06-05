"""Gantt timeline view for trip scheduling on the dispatch board."""
import customtkinter as ctk
from datetime import datetime, timedelta
from services.i18n import t
from ui.theme import COLORS, FONTS
from utils.dates import parse_date


class DispatchTimeline(ctk.CTkFrame):
    """Simplified Gantt chart showing truck scheduling over time."""

    def __init__(self, parent, db, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_base"], **kwargs)
        self._db = db
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_base"],
                                               scrollbar_button_color=COLORS["border"])
        self._scroll.pack(fill="both", expand=True)

    def refresh(self, cards_data: list = None):
        for w in self._scroll.winfo_children():
            w.destroy()

        if not cards_data:
            ctk.CTkLabel(self._scroll, text=t("dispatch_board.timeline_no_data"),
                        fg_color="transparent", text_color=COLORS["text_muted"],
                        font=FONTS["body"]).pack(pady=60)
            return

        active_trips = [cd for cd in cards_data
                       if cd.get("status", "") not in
                       ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced")
                       and cd.get("truck_plate")]

        if not active_trips:
            ctk.CTkLabel(self._scroll, text=t("dispatch_board.timeline_no_data"),
                        fg_color="transparent", text_color=COLORS["text_muted"],
                        font=FONTS["body"]).pack(pady=60)
            return

        trucks = {}
        for trip in active_trips:
            plate = trip.get("truck_plate", "")
            if plate not in trucks:
                trucks[plate] = []
            trucks[plate].append(trip)

        now = datetime.now()
        now_str = now.strftime("%H:%M")
        ctk.CTkLabel(self._scroll, text=f"{t('dispatch_board.timeline_now')}: {now_str}",
                    fg_color="transparent", text_color=COLORS["accent"],
                    font=FONTS["h3"]).pack(anchor="w", padx=12, pady=(8, 4))

        ctk.CTkFrame(self._scroll, fg_color=COLORS["border"], height=1).pack(fill="x", padx=8, pady=2)

        header = ctk.CTkFrame(self._scroll, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(4, 2))
        ctk.CTkLabel(header, text="Truck", fg_color="transparent",
                    text_color=COLORS["text_muted"], font=FONTS["label"],
                    width=120, anchor="w").pack(side="left")
        ctk.CTkLabel(header, text="Schedule", fg_color="transparent",
                    text_color=COLORS["text_muted"], font=FONTS["label"],
                    anchor="w").pack(side="left", fill="x", expand=True)

        status_colors = {
            "Planned": COLORS["chip_planned"],
            "Loading": COLORS["chip_loading"],
            "In Transit": COLORS["chip_transit"],
        }

        for plate, trips in sorted(trucks.items()):
            row = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_surface"], corner_radius=4)
            row.pack(fill="x", padx=8, pady=2)

            ctk.CTkLabel(row, text=plate, fg_color="transparent",
                        text_color=COLORS["text_primary"], font=FONTS["small"],
                        width=120, anchor="w").pack(side="left", padx=6, pady=6)

            bar_frame = ctk.CTkFrame(row, fg_color="transparent")
            bar_frame.pack(side="left", fill="x", expand=True, padx=4, pady=4)

            for trip in trips:
                dep_raw = trip.get("departure_date", "")
                eta_raw = trip.get("eta", "")
                trip_id = trip.get("trip_id", "")
                status = trip.get("status", "Planned")
                color = status_colors.get(status, COLORS["chip_planned"])

                dep_dt = parse_date(dep_raw, "%d/%m/%Y")
                eta_dt = parse_date(eta_raw, "%d/%m/%Y")

                if dep_dt and eta_dt:
                    dep_str = dep_dt.strftime("%d/%m %H:%M") if hasattr(dep_dt, 'strftime') else dep_raw
                    eta_str = eta_dt.strftime("%d/%m %H:%M") if hasattr(eta_dt, 'strftime') else eta_raw
                    label = f"{trip_id} ({dep_str} - {eta_str})"
                else:
                    label = f"{trip_id} ({dep_raw} - {eta_raw})"

                bar = ctk.CTkFrame(bar_frame, fg_color=color, height=22, corner_radius=4)
                bar.pack(fill="x", pady=1)
                ctk.CTkLabel(bar, text=label, fg_color=color,
                            text_color=COLORS["text_primary"], font=FONTS["label"],
                            anchor="w").pack(side="left", padx=6, pady=2)
