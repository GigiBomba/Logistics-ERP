import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from typing import Any, Dict, Optional

from services.i18n import t
from ui.icons import iconed
from services.fleet_maintenance_service import FleetMaintenanceService, MaintType, MAINT_DISPLAY, MAINT_ICONS
from ui.styles import Theme
from ui.widgets import ActionButton, StyledEntry
from ui.widgets.service_timeline_widget import ServiceTimelineWidget
from ui.theme import FONTS


class MaintenanceHealthTab(ctk.CTkFrame):
    def __init__(self, parent, service: FleetMaintenanceService, truck_id: int,
                 truck_plate: str, win: tk.Toplevel):
        super().__init__(parent, fg_color=Theme.BG)
        self.service = service
        self.truck_id = truck_id
        self.truck_plate = truck_plate
        self.win = win
        self._i18n_widgets = []

        self._build()

    def _i18n_tag(self, widget, key, prefix=""):
        self._i18n_widgets.append((widget, key, prefix))

    def _build(self):
        toolbar = ctk.CTkFrame(self, fg_color=Theme.BG)
        toolbar.pack(fill="x")
        self._refresh_btn = ActionButton(toolbar, iconed("maint.refresh_score"), self.refresh,
                                         color=Theme.ACCENT)
        self._refresh_btn.pack(side="left", padx=4)
        self._i18n_tag(self._refresh_btn, "maint.refresh_score")
        self._predict_btn = ActionButton(toolbar, iconed("maint.predictions"), self._show_predictions,
                                         color=Theme.PURPLE_SOFT)
        self._predict_btn.pack(side="left", padx=4)
        self._i18n_tag(self._predict_btn, "maint.predictions")

        paned = tk.PanedWindow(self, orient="vertical", bg=Theme.BG, sashwidth=3,
                               sashrelief="ridge", sashpad=0)
        paned.pack(fill="both", expand=True)

        self._health_frame = ctk.CTkFrame(paned, fg_color=Theme.BG)
        paned.add(self._health_frame, height=260)

        timeline_container = ctk.CTkFrame(paned, fg_color=Theme.BG)
        paned.add(timeline_container)

        self._timeline = ServiceTimelineWidget(
            timeline_container, self.service, self.truck_id,
            self.truck_plate, self.win,
            on_edit_record=self._edit_record_from_timeline,
        )
        self._timeline.pack(fill="both", expand=True)

        self.refresh()

    def refresh(self):
        for w in self._health_frame.winfo_children():
            w.destroy()
        health = self.service.compute_health(self.truck_id)
        self._render_health(health)
        self._timeline.refresh()

    def refresh_translations(self):
        for widget, key, prefix in self._i18n_widgets:
            try:
                widget.configure(text=f"{prefix}{iconed(key) if key.startswith('maint.') else t(key)}")
            except Exception:
                pass
        self.refresh()

    def _render_health(self, health):
        score = health.score
        if score >= 80:
            color = Theme.SUCCESS
            label = iconed("maint.excellent")
        elif score >= 50:
            color = Theme.WARNING
            label = iconed("maint.fair")
        else:
            color = Theme.DANGER
            label = iconed("maint.critical_health")

        gauge_f = ctk.CTkFrame(self._health_frame, fg_color=Theme.BG)
        gauge_f.pack(pady=20)
        self._draw_gauge(gauge_f, score, color, label)

        metrics_f = ctk.CTkFrame(self._health_frame, fg_color=Theme.BG)
        metrics_f.pack(pady=10)
        cards = [
            (iconed("maint.metric_score"), f"{score}/100", color),
            (iconed("maint.metric_compliance"), f"{health.compliance_pct:.0f}%", Theme.SUCCESS if health.compliance_pct >= 80 else Theme.WARNING),
            (iconed("maint.metric_overdue"), str(health.overdue_count), Theme.DANGER if health.overdue_count > 0 else Theme.MUTED),
            (iconed("maint.metric_recurring"), str(health.recurring_issues), Theme.WARNING if health.recurring_issues > 0 else Theme.MUTED),
            (iconed("maint.metric_downtime"), f"{health.downtime_days}d", Theme.ORANGE if health.downtime_days > 30 else Theme.MUTED),
        ]
        for title, val, c in cards:
            card = ctk.CTkFrame(metrics_f, fg_color=Theme.SURFACE2)
            card.pack(side="left", padx=6, fill="y")
            ctk.CTkLabel(card, text=title, fg_color=Theme.SURFACE2, text_color=Theme.MUTED,
                     font=FONTS["label"]).pack()
            ctk.CTkLabel(card, text=val, fg_color=Theme.SURFACE2, text_color=c,
                     font=FONTS["h2"]).pack()
            ctk.CTkLabel(card, text=iconed("maint.updated", health.last_updated[:10]), fg_color=Theme.SURFACE2,
                     text_color=Theme.MUTED, font=FONTS["label"]).pack()

    def _draw_gauge(self, parent, score, color, label):
        frame = ctk.CTkFrame(parent, fg_color=Theme.BG)
        frame.pack(pady=8)

        ctk.CTkLabel(frame, text=f"{score}", fg_color=Theme.BG, text_color=color,
                     font=FONTS["display"]).pack()
        ctk.CTkLabel(frame, text=label, fg_color=Theme.BG, text_color=color,
                     font=FONTS["label"]).pack()

        bar = ctk.CTkProgressBar(frame, width=140, height=12,
                                 progress_color=color, fg_color=Theme.SURFACE2)
        bar.pack(pady=(4, 0))
        bar.set(score / 100.0)

    def _edit_record_from_timeline(self, rec: Dict[str, Any]):
        self._record_form(title=iconed("maint.form_title_edit"), record=rec)

    def _record_form(self, title="", record=None):
        win = ctk.CTkToplevel(self.win)
        win.title(title)
        win.geometry("550x500")
        win.configure(fg_color=Theme.BG)
        Theme.apply(win)

        f = ctk.CTkFrame(win, fg_color=Theme.BG)
        f.pack(fill="both", expand=True)

        fields = {}

        def add_row(label):
            r = ctk.CTkFrame(f, fg_color=Theme.BG)
            r.pack(fill="x", pady=4)
            ctk.CTkLabel(r, text=label, fg_color=Theme.BG, text_color=Theme.MUTED,
                     font=FONTS["label"], width=18, anchor="w").pack(side="left")
            e = StyledEntry(r)
            e.pack(side="left", fill="x", expand=True)
            return e

        type_opts = [mt.value for mt in MaintType]
        r = ctk.CTkFrame(f, fg_color=Theme.BG)
        r.pack(fill="x", pady=4)
        ctk.CTkLabel(r, text=iconed("maint.form_type"), fg_color=Theme.BG, text_color=Theme.MUTED,
                 font=FONTS["label"], width=18, anchor="w").pack(side="left")
        self._form_type_combo = ctk.CTkComboBox(r, values=type_opts, state="readonly")
        self._form_type_combo.set(record["maintenance_type"] if record else MaintType.OIL_CHANGE.value)
        self._form_type_combo.pack(side="left")

        fields["date"] = add_row(iconed("maint.form_date"))
        fields["date"].insert(0, record["date"][:10] if record and record.get("date") else datetime.now().strftime("%Y-%m-%d"))

        fields["km"] = add_row(iconed("maint.form_km"))
        if record and record.get("km"):
            fields["km"].insert(0, str(record["km"]))

        fields["cost"] = add_row(iconed("maint.form_cost"))
        if record and record.get("cost"):
            fields["cost"].insert(0, str(record["cost"]))

        fields["provider"] = add_row(iconed("maint.form_provider"))
        if record and record.get("service_provider"):
            fields["provider"].insert(0, record["service_provider"])

        fields["notes"] = add_row(iconed("maint.form_notes"))
        if record and record.get("notes"):
            fields["notes"].insert(0, record["notes"])

        def save():
            try:
                mt = self._form_type_combo.get()
                date = fields["date"].get().strip()
                km = float(fields["km"].get().strip()) if fields["km"].get().strip() else None
                cost = float(fields["cost"].get().strip()) if fields["cost"].get().strip() else None
                provider = fields["provider"].get().strip()
                notes = fields["notes"].get().strip()

                if record:
                    self.service.update_record(
                        record["id"], mt, date, km, cost, provider, notes,
                    )
                win.destroy()
                self.refresh()
            except Exception as e:
                messagebox.showerror(iconed("maint.error_generic"), str(e))

        ActionButton(f, iconed("maint.save"), save, color=Theme.ACCENT_SUCCESS).pack(fill="x", pady=8)
        ActionButton(f, iconed("maint.cancel"), win.destroy, color=Theme.SURFACE2).pack(fill="x")

    def _show_predictions(self):
        win = ctk.CTkToplevel(self.win)
        win.title(iconed("maint.predictions_title", self.truck_plate))
        win.geometry("600x500")
        win.configure(fg_color=Theme.BG)
        Theme.apply(win)

        ctk.CTkLabel(win, text=iconed("maint.predictions_header", self.truck_plate),
                 fg_color=Theme.BG, text_color=Theme.TEXT, font=FONTS["h3"]).pack(pady=10)

        scroll_frame = ctk.CTkScrollableFrame(win, fg_color=Theme.BG)
        scroll_frame.pack(fill="both", expand=True, padx=16, pady=6)

        for mt in MaintType:
            pred = self.service.predict_next_service(self.truck_id, mt.value)
            card = ctk.CTkFrame(scroll_frame, fg_color=Theme.SURFACE2)
            card.pack(fill="x", pady=3)

            try:
                icon = MAINT_ICONS.get(mt, "\u2699\uFE0F")
                disp = MAINT_DISPLAY.get(mt, mt.value)
            except ValueError:
                icon = "\u2699\uFE0F"
                disp = mt.value

            row1 = ctk.CTkFrame(card, fg_color=Theme.SURFACE2)
            row1.pack(fill="x")
            ctk.CTkLabel(row1, text=f"{icon} {disp}", fg_color=Theme.SURFACE2, text_color=Theme.TEXT,
                     font=FONTS["small"]).pack(side="left")

            if not pred:
                ctk.CTkLabel(card, text=iconed("maint.no_schedule"), fg_color=Theme.SURFACE2,
                         text_color=Theme.MUTED, font=FONTS["label"]).pack(anchor="w")
                continue

            if pred.get("overdue"):
                ctk.CTkLabel(row1, text=iconed("maint.status_overdue"), fg_color=Theme.SURFACE2, text_color=Theme.DANGER,
                         font=FONTS["label"]).pack(side="right")

            lines = []
            if pred.get("due_by_km") is not None:
                lines.append(iconed("maint.km_remaining", pred["due_by_km"]))
            if pred.get("due_by_date"):
                lines.append(iconed("maint.due_by_date", pred["due_by_date"]))
            if pred.get("remaining_days") is not None:
                lines.append(iconed("maint.days_left", pred["remaining_days"]))
            if pred.get("due_km"):
                lines.append(iconed("maint.target_km", pred["due_km"]))
            for line in lines:
                ctk.CTkLabel(card, text=line, fg_color=Theme.SURFACE2, text_color=Theme.MUTED,
                         font=FONTS["label"]).pack(anchor="w", pady=(1, 0))
