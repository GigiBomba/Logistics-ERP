"""Driver and truck availability panel for the dispatch board."""
import customtkinter as ctk
from datetime import datetime, timedelta
from services.i18n import t
from ui.theme import COLORS, FONTS
from repositories.driver_repository import DriverRepository
from repositories.fleet_repository import FleetRepository
from services.conflict_service import TripConflictService


class ResourcePanel(ctk.CTkFrame):
    """Split panel showing driver availability (top) and truck availability (bottom)."""

    def __init__(self, parent, db, ops=None, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_base"], **kwargs)
        self._db = db
        self._ops = ops
        self._driver_repo = DriverRepository(db)
        self._fleet_repo = FleetRepository(db)
        self._conflict_service = TripConflictService(db)
        self._driver_rows = []
        self._truck_rows = []

        self._build()

    def _build(self):
        self._drivers_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_surface"],
                                                      scrollbar_button_color=COLORS["border"])
        self._drivers_frame.pack(fill="both", expand=True, padx=4, pady=(4, 2))

        self._build_section_header(self._drivers_frame, "dispatch_board.resource_drivers_title")

        self._trucks_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_surface"],
                                                     scrollbar_button_color=COLORS["border"])
        self._trucks_frame.pack(fill="both", expand=True, padx=4, pady=(2, 4))

        self._build_section_header(self._trucks_frame, "dispatch_board.resource_trucks_title")

    def _build_section_header(self, parent, title_key):
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(hdr, text=t(title_key), fg_color="transparent",
                     text_color=COLORS["text_primary"], font=FONTS["h3"]).pack(side="left", padx=8)

    def refresh(self):
        self._refresh_drivers()
        self._refresh_trucks()

    def _refresh_drivers(self):
        for w in self._drivers_frame.winfo_children():
            w.destroy()
        self._build_section_header(self._drivers_frame, "dispatch_board.resource_drivers_title")

        try:
            drivers = self._driver_repo.get_active_drivers()
        except Exception:
            drivers = []

        if not drivers:
            ctk.CTkLabel(self._drivers_frame, text=t("dispatch_board.resource_no_drivers"),
                        fg_color="transparent", text_color=COLORS["text_muted"],
                        font=FONTS["label"]).pack(pady=20)
            return

        now = datetime.now()
        for d in drivers:
            status, detail, blocked_reason = self._driver_status(d, now)
            self._draw_driver_row(d, status, detail, blocked_reason)

    def _driver_status(self, driver: dict, now: datetime):
        driver_id = driver.get("id")
        license_expiry = driver.get("license_expiry", "")
        medical_expiry = driver.get("medical_expiry", "")

        try:
            if license_expiry:
                exp = datetime.strptime(license_expiry, "%Y-%m-%d")
                if now.date() > exp.date():
                    return "blocked", t("dispatch_board.resource_license_expired"), t("dispatch_board.resource_license_expired")
            if medical_expiry:
                exp = datetime.strptime(medical_expiry, "%Y-%m-%d")
                if now.date() > exp.date():
                    return "blocked", t("dispatch_board.resource_medical_expired"), t("dispatch_board.resource_medical_expired")
        except Exception:
            pass

        try:
            from repositories.trip_repository import TripRepository
            trip_repo = TripRepository(self._db)
            driver_trips = trip_repo.get_by_driver_id(int(driver_id))
            active_trips = [t for t in driver_trips if t.get("status", "") not in
                          ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced")]
            if active_trips:
                current = active_trips[0]
                eta_raw = current.get("end_date", "")
                try:
                    from utils.dates import parse_date
                    eta_dt = parse_date(eta_raw, "%d/%m/%Y")
                    if eta_dt:
                        if now < eta_dt:
                            hours = (eta_dt - now).total_seconds() / 3600
                            if hours <= 4:
                                return "returning", f"TRP-{current['id']} ETA {eta_raw}", None
                            return "on_trip", f"TRP-{current['id']} ETA {eta_raw}", None
                        return "returning", f"TRP-{current['id']} just arrived", None
                except Exception:
                    pass
                return "on_trip", f"TRP-{current['id']}", None
        except Exception:
            pass

        return "free", t("dispatch_board.resource_status_free"), None

    def _draw_driver_row(self, driver: dict, status: str, detail: str, blocked_reason: str):
        colors = {
            "free": (COLORS["success"], COLORS["success_dim"]),
            "returning": (COLORS["warning"], COLORS["warning_dim"]),
            "on_trip": (COLORS["danger"], COLORS["danger_dim"]),
            "blocked": (COLORS["danger"], COLORS["danger_dim"]),
        }
        dot_color, _ = colors.get(status, (COLORS["text_muted"], COLORS["bg_surface"]))

        row = ctk.CTkFrame(self._drivers_frame, fg_color=COLORS["bg_surface"], corner_radius=4)
        row.pack(fill="x", padx=4, pady=1)

        dot = ctk.CTkFrame(row, fg_color=dot_color, width=8, height=8, corner_radius=4)
        dot.pack(side="left", padx=(6, 4), pady=8)
        dot.pack_propagate(False)

        name = driver.get("name", "?")
        license_cat = driver.get("license_category", "")
        ctk.CTkLabel(row, text=name, fg_color="transparent", text_color=COLORS["text_primary"],
                     font=FONTS["small"], anchor="w").pack(side="left", padx=(2, 12))

        ctk.CTkLabel(row, text=license_cat, fg_color="transparent", text_color=COLORS["text_muted"],
                     font=FONTS["label"], anchor="w").pack(side="left", padx=(0, 8))

        detail_color = COLORS["text_secondary"]
        if blocked_reason:
            detail_color = COLORS["danger"]
        ctk.CTkLabel(row, text=detail, fg_color="transparent", text_color=detail_color,
                     font=FONTS["label"], anchor="e").pack(side="right", padx=(4, 8))

    def _refresh_trucks(self):
        for w in self._trucks_frame.winfo_children():
            w.destroy()
        self._build_section_header(self._trucks_frame, "dispatch_board.resource_trucks_title")

        try:
            trucks = self._fleet_repo.get_active_trucks()
        except Exception:
            trucks = []

        if not trucks:
            ctk.CTkLabel(self._trucks_frame, text=t("dispatch_board.resource_no_trucks"),
                        fg_color="transparent", text_color=COLORS["text_muted"],
                        font=FONTS["label"]).pack(pady=20)
            return

        now = datetime.now()
        for t in trucks:
            status, detail, blocked_reason = self._truck_status(t, now)
            self._draw_truck_row(t, status, detail, blocked_reason)

    def _truck_status(self, truck: dict, now: datetime):
        truck_id = truck.get("id")
        plate = truck.get("plate_number", "?")
        truck_status = truck.get("status", "")

        if truck_status == "In Service":
            return "blocked", t("dispatch_board.resource_in_service"), t("dispatch_board.resource_in_service")

        try:
            insurance = truck.get("insurance_expiry", "")
            if insurance:
                exp = datetime.strptime(insurance, "%Y-%m-%d")
                if now.date() > exp.date():
                    return "blocked", t("dispatch_board.resource_insurance_expired"), t("dispatch_board.resource_insurance_expired")

            inspection = truck.get("inspection_expiry", "")
            if inspection:
                exp = datetime.strptime(inspection, "%Y-%m-%d")
                if now.date() > exp.date():
                    return "blocked", t("dispatch_board.resource_inspection_expired"), t("dispatch_board.resource_inspection_expired")

            maint_due = truck.get("maintenance_due")
            mileage = truck.get("mileage")
            if maint_due is not None and mileage is not None:
                if float(mileage) >= float(maint_due):
                    return "blocked", t("dispatch_board.resource_maintenance_due"), t("dispatch_board.resource_maintenance_due")
        except Exception:
            pass

        try:
            from repositories.trip_repository import TripRepository
            trip_repo = TripRepository(self._db)
            truck_trips = trip_repo.get_by_truck_id(int(truck_id))
            active_trips = [t for t in truck_trips if t.get("status", "") not in
                          ("Delivered", "Completed", "Done", "Cancelled", "Paid", "Invoiced")]
            if active_trips:
                current = active_trips[0]
                eta_raw = current.get("end_date", "")
                try:
                    from utils.dates import parse_date
                    eta_dt = parse_date(eta_raw, "%d/%m/%Y")
                    if eta_dt:
                        if now < eta_dt:
                            hours = (eta_dt - now).total_seconds() / 3600
                            if hours <= 4:
                                return "returning", f"TRP-{current['id']} ETA {eta_raw}", None
                            return "on_trip", f"TRP-{current['id']} ETA {eta_raw}", None
                        return "returning", f"TRP-{current['id']} just arrived", None
                except Exception:
                    pass
                return "on_trip", f"TRP-{current['id']}", None
        except Exception:
            pass

        return "free", t("dispatch_board.resource_status_free"), None

    def _draw_truck_row(self, truck: dict, status: str, detail: str, blocked_reason: str):
        colors = {
            "free": (COLORS["success"], COLORS["success_dim"]),
            "returning": (COLORS["warning"], COLORS["warning_dim"]),
            "on_trip": (COLORS["danger"], COLORS["danger_dim"]),
            "blocked": (COLORS["danger"], COLORS["danger_dim"]),
        }
        dot_color, _ = colors.get(status, (COLORS["text_muted"], COLORS["bg_surface"]))

        row = ctk.CTkFrame(self._trucks_frame, fg_color=COLORS["bg_surface"], corner_radius=4)
        row.pack(fill="x", padx=4, pady=1)

        dot = ctk.CTkFrame(row, fg_color=dot_color, width=8, height=8, corner_radius=4)
        dot.pack(side="left", padx=(6, 4), pady=8)
        dot.pack_propagate(False)

        plate = truck.get("plate_number", "?")
        model = truck.get("model", "")
        ctk.CTkLabel(row, text=plate, fg_color="transparent", text_color=COLORS["text_primary"],
                     font=FONTS["small"], anchor="w").pack(side="left", padx=(2, 12))

        ctk.CTkLabel(row, text=model, fg_color="transparent", text_color=COLORS["text_muted"],
                     font=FONTS["label"], anchor="w").pack(side="left", padx=(0, 8))

        detail_color = COLORS["text_secondary"]
        if blocked_reason:
            detail_color = COLORS["danger"]
        ctk.CTkLabel(row, text=detail, fg_color="transparent", text_color=detail_color,
                     font=FONTS["label"], anchor="e").pack(side="right", padx=(4, 8))
