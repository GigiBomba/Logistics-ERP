"""Dispatch alerts and operations panel: alerts list, unassigned trips, assignment summary."""
import customtkinter as ctk
from datetime import datetime
from services.i18n import t
from ui.theme import COLORS, FONTS


class DispatchAlertsPanel(ctk.CTkFrame):
    """Combined panel showing: active alerts, unassigned trips, assignment summary."""

    def __init__(self, parent, db, ops=None, on_assign_truck=None, on_assign_driver=None, on_resolve_alert=None, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_base"], **kwargs)
        self._db = db
        self._ops = ops
        self._on_assign_truck = on_assign_truck
        self._on_assign_driver = on_assign_driver
        self._on_resolve_alert = on_resolve_alert
        self._build()

    def _build(self):
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_base"],
                                               scrollbar_button_color=COLORS["border"])
        self._scroll.pack(fill="both", expand=True)

        self._brief_section = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_surface"], corner_radius=8)
        self._brief_section.pack(fill="x", padx=4, pady=(2, 4))
        self._build_section_header(self._brief_section, "dispatch_board.brief_title", False)

        self._alerts_section = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_surface"], corner_radius=8)
        self._alerts_section.pack(fill="x", padx=4, pady=4)
        self._build_section_header(self._alerts_section, "dispatch_board.alerts_panel_title", True)

        self._unassigned_section = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_surface"], corner_radius=8)
        self._unassigned_section.pack(fill="x", padx=4, pady=4)
        self._build_section_header(self._unassigned_section, "dispatch_board.alerts_panel_unassigned_title", True)

        self._summary_section = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_surface"], corner_radius=8)
        self._summary_section.pack(fill="x", padx=4, pady=4)
        self._build_section_header(self._summary_section, "dispatch_board.alerts_panel_summary_title", False)

    def _build_section_header(self, parent, title_key, with_resolve_btn):
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(hdr, text=t(title_key), fg_color="transparent",
                     text_color=COLORS["text_primary"], font=FONTS["h3"]).pack(side="left")
        if with_resolve_btn:
            btn = ctk.CTkButton(hdr, text=t("dispatch_board.alerts_panel_resolve_all"),
                               fg_color=COLORS["bg_elevated"], text_color=COLORS["text_muted"],
                               font=FONTS["label"], cursor="hand2", height=24, width=80,
                               command=self._resolve_all_alerts)
            btn.pack(side="right")

    def _refresh_brief(self, cards_data: list):
        children = list(self._brief_section.winfo_children())
        for w in children[1:]:
            w.destroy()

        today_str = datetime.now().strftime("%d/%m/%Y")
        departing = 0
        arriving = 0
        needs_attention = 0

        for cd in cards_data:
            status = cd.get("status", "")
            if status in ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced"):
                continue
            dep = cd.get("departure_date", "")
            eta = cd.get("eta", "")
            if dep and dep[:10] == today_str:
                departing += 1
            if eta and eta[:10] == today_str:
                arriving += 1
            has_truck = bool(cd.get("truck_plate"))
            has_driver = bool(cd.get("driver_name"))
            if not has_truck or not has_driver:
                needs_attention += 1

        critical_count = 0
        if self._ops:
            try:
                from services.operations.alert_manager import Severity
                alerts = self._ops.get_alerts(severity=Severity.CRITICAL, resolved=False, limit=50)
                critical_count = len(alerts)
            except Exception:
                pass

        kpis = [
            ("dispatch_board.brief_departing_today", departing, COLORS["accent"]),
            ("dispatch_board.brief_arriving_today", arriving, COLORS["success"]),
            ("dispatch_board.brief_critical", critical_count, COLORS["danger"] if critical_count else COLORS["text_muted"]),
            ("dispatch_board.brief_needs_attention", needs_attention, COLORS["warning"] if needs_attention else COLORS["text_muted"]),
        ]

        grid = ctk.CTkFrame(self._brief_section, fg_color="transparent")
        grid.pack(fill="x", padx=4, pady=8)

        for i, (key, val, color) in enumerate(kpis):
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(cell, text=t(key), fg_color="transparent",
                        text_color=COLORS["text_muted"], font=FONTS["label"]).pack()
            ctk.CTkLabel(cell, text=str(val), fg_color="transparent",
                        text_color=color, font=FONTS["mono_lg"]).pack()

    def refresh(self, cards_data: list = None):
        self._refresh_brief(cards_data or [])
        self._refresh_alerts()
        self._refresh_unassigned(cards_data or [])
        self._refresh_summary(cards_data or [])

    def _refresh_alerts(self):
        children = list(self._alerts_section.winfo_children())
        for w in children[1:]:
            w.destroy()

        if not self._ops:
            ctk.CTkLabel(self._alerts_section, text="Ops not available",
                        fg_color="transparent", text_color=COLORS["text_muted"],
                        font=FONTS["label"]).pack(pady=12)
            return

        alerts = self._ops.get_active_alerts(limit=20)
        if not alerts:
            ctk.CTkLabel(self._alerts_section, text=t("dispatch_board.alerts_panel_no_alerts"),
                        fg_color="transparent", text_color=COLORS["text_muted"],
                        font=FONTS["label"]).pack(pady=12)
            return

        for alert in alerts:
            self._draw_alert_row(alert)

    def _draw_alert_row(self, alert):
        sev_colors = {"critical": COLORS["danger"], "warning": COLORS["warning"], "info": COLORS["info"]}
        sev = str(getattr(alert.severity, "value", alert.severity)).lower()
        chip_color = sev_colors.get(sev, COLORS["info"])

        row = ctk.CTkFrame(self._alerts_section, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=1)

        ctk.CTkLabel(row, text=sev.upper()[:3], fg_color=chip_color, text_color="#ffffff",
                     font=FONTS["label"], width=36, corner_radius=3).pack(side="left", padx=(0, 6))

        text = getattr(alert, "title", "") or getattr(alert, "message", "")
        ctk.CTkLabel(row, text=text[:60], fg_color="transparent", text_color=COLORS["text_secondary"],
                     font=FONTS["label"], anchor="w").pack(side="left", fill="x", expand=True)

        resolve_btn = ctk.CTkButton(row, text="\u2713", fg_color="transparent",
                                    text_color=COLORS["text_muted"], font=FONTS["label"],
                                    cursor="hand2", width=22, height=22,
                                    command=lambda a=alert: self._resolve_alert_row(a))
        resolve_btn.pack(side="right")

    def _resolve_alert_row(self, alert):
        if self._ops:
            self._ops.resolve_alert(alert.id)
        if self._on_resolve_alert:
            self._on_resolve_alert()

    def _resolve_all_alerts(self):
        if not self._ops:
            return
        alerts = self._ops.get_active_alerts(limit=100)
        for alert in alerts:
            self._ops.resolve_alert(alert.id)
        if self._on_resolve_alert:
            self._on_resolve_alert()

    def _refresh_unassigned(self, cards_data: list):
        children = list(self._unassigned_section.winfo_children())
        for w in children[1:]:
            w.destroy()

        no_truck = []
        no_driver = []
        no_both = []

        for cd in cards_data:
            has_truck = bool(cd.get("truck_plate"))
            has_driver = bool(cd.get("driver_name"))
            status = cd.get("status", "")
            if status in ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced"):
                continue
            if not has_truck and not has_driver:
                no_both.append(cd)
            elif not has_truck:
                no_truck.append(cd)
            elif not has_driver:
                no_driver.append(cd)

        all_unassigned = no_truck + no_driver + no_both
        if not all_unassigned:
            ctk.CTkLabel(self._unassigned_section, text=t("dispatch_board.alerts_panel_no_unassigned"),
                        fg_color="transparent", text_color=COLORS["success"],
                        font=FONTS["label"]).pack(pady=12)
            return

        if no_truck:
            self._draw_unassigned_group("dispatch_board.alerts_panel_no_truck", no_truck)
        if no_driver:
            self._draw_unassigned_group("dispatch_board.alerts_panel_no_driver", no_driver)
        if no_both:
            self._draw_unassigned_group("dispatch_board.alerts_panel_neither", no_both)

    def _draw_unassigned_group(self, title_key: str, items: list):
        grp = ctk.CTkFrame(self._unassigned_section, fg_color="transparent")
        grp.pack(fill="x", padx=4, pady=(2, 4))

        ctk.CTkLabel(grp, text=t(title_key), fg_color="transparent", text_color=COLORS["warning"],
                     font=FONTS["label"]).pack(anchor="w", padx=4)

        for item in items[:5]:
            row = ctk.CTkFrame(grp, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)

            trip_id = item.get("trip_id", "")
            origin = item.get("origin", "?")
            dest = item.get("destination", "?")
            route = f"{trip_id}: {origin}\u2192{dest}"

            ctk.CTkLabel(row, text=route[:50], fg_color="transparent",
                        text_color=COLORS["text_secondary"], font=FONTS["label"],
                        anchor="w").pack(side="left", fill="x", expand=True)

            assign_btn = ctk.CTkButton(row, text=t("dispatch_board.alerts_panel_quick_assign"),
                                      fg_color=COLORS["accent"], text_color="#ffffff",
                                      font=FONTS["label"], cursor="hand2", height=20, width=70,
                                      command=lambda i=item: self._quick_assign(i))
            assign_btn.pack(side="right")

        if len(items) > 5:
            ctk.CTkLabel(grp, text=f"... +{len(items) - 5} more",
                        fg_color="transparent", text_color=COLORS["text_muted"],
                        font=FONTS["label"]).pack(anchor="w", padx=4)

    def _quick_assign(self, item):
        if self._on_assign_truck and not item.get("truck_plate"):
            self._on_assign_truck(item)
        if self._on_assign_driver and not item.get("driver_name"):
            self._on_assign_driver(item)

    def _refresh_summary(self, cards_data: list):
        children = list(self._summary_section.winfo_children())
        for w in children[1:]:
            w.destroy()

        total_active = 0
        fully_assigned = 0
        partial = 0
        unassigned = 0

        for cd in cards_data:
            status = cd.get("status", "")
            if status in ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced"):
                continue
            total_active += 1
            has_truck = bool(cd.get("truck_plate"))
            has_driver = bool(cd.get("driver_name"))
            if has_truck and has_driver:
                fully_assigned += 1
            elif has_truck or has_driver:
                partial += 1
            else:
                unassigned += 1

        kpis = [
            ("dispatch_board.alerts_panel_total_trips", total_active, COLORS["text_primary"]),
            ("dispatch_board.alerts_panel_fully_assigned", fully_assigned, COLORS["success"]),
            ("dispatch_board.alerts_panel_partial", partial, COLORS["warning"]),
            ("dispatch_board.alerts_panel_unassigned", unassigned, COLORS["danger"] if unassigned else COLORS["text_muted"]),
        ]

        grid = ctk.CTkFrame(self._summary_section, fg_color="transparent")
        grid.pack(fill="x", padx=4, pady=8)

        for i, (key, val, color) in enumerate(kpis):
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(cell, text=t(key), fg_color="transparent",
                        text_color=COLORS["text_muted"], font=FONTS["label"]).pack()
            ctk.CTkLabel(cell, text=str(val), fg_color="transparent",
                        text_color=color, font=FONTS["mono_lg"]).pack()
