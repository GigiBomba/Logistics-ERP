"""Client activity timeline — chronological event feed."""
import customtkinter as ctk
from datetime import datetime
from ui.theme import COLORS, FONTS


class ClientActivityTimeline(ctk.CTkFrame):
    def __init__(self, parent, service, client_id, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_base"])
        super().__init__(parent, **kwargs)
        self.service = service
        self.client_id = client_id
        self._build()

    def _build(self):
        for w in self.winfo_children():
            w.destroy()

        events = self._collect_events()
        if not events:
            ctk.CTkLabel(self, text="No activity recorded", fg_color=COLORS["bg_base"],
                         text_color=COLORS["text_muted"], font=FONTS["small"]).pack(pady=10, anchor="w")
            return

        events.sort(key=lambda e: e["ts"], reverse=True)
        for i, ev in enumerate(events[:30]):
            row = ctk.CTkFrame(self, fg_color=COLORS["bg_base"])
            row.pack(fill="x", pady=1)

            dot_color = COLORS.get(ev.get("color", "accent"), COLORS["accent"])
            ctk.CTkLabel(row, text="\u25cf", fg_color=COLORS["bg_base"],
                         text_color=dot_color, font=FONTS["small"], width=16).pack(side="left")

            ctk.CTkLabel(row, text=ev["label"], fg_color=COLORS["bg_base"],
                         text_color=COLORS["text_primary"], font=FONTS["small"],
                         anchor="w").pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(row, text=ev["ts"][:10], fg_color=COLORS["bg_base"],
                         text_color=COLORS["text_muted"], font=FONTS["label"],
                         width=70).pack(side="right")

    def _collect_events(self):
        events = []

        trips = self.service.get_client_trips(self.client_id, limit=50)
        for t in trips:
            status = t.get("status", "")
            color = {
                "delivered": "success", "completed": "success", "done": "success",
                "in transit": "info", "loading": "warning",
                "planned": "accent", "cancelled": "danger",
            }.get(status.lower() if status else "", "accent")
            events.append({
                "ts": t.get("start_date") or t.get("created_at", ""),
                "label": "Trip: {} — {} / {} — {} km".format(
                    t.get("truck_number", "?"),
                    status,
                    t.get("client_name", "?"),
                    int(t.get("distance_km", 0) or 0),
                ),
                "color": color,
            })

        invs = self.service.get_client_invoices(self.client_id, limit=50)
        for inv in invs:
            status = inv.get("status", "")
            color = "success" if status == "Paid" else "warning"
            events.append({
                "ts": inv.get("issue_date", ""),
                "label": "Invoice: {} — {} — {} EUR ({})".format(
                    inv.get("invoice_number", "?"),
                    status,
                    int(inv.get("total_amount", 0) or 0),
                    inv.get("trip_status", "?"),
                ),
                "color": color,
            })

        return events

    def refresh(self, client_id=None):
        if client_id:
            self.client_id = client_id
        self._build()
