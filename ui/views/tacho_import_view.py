"""Tachograph Import UI — two-panel import + history view."""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from ui.theme import COLORS, FONTS, S, card, card_header, btn, page_heading
from services.i18n import t
from services.tacho_service import TachoService

logger = __import__("logging").getLogger(__name__)


class TachoImportView(ctk.CTkFrame):
    """Tachograph import view with import panel (left) and history (right)."""

    def __init__(self, parent, db, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_base"])
        super().__init__(parent, **kwargs)
        self.db = db
        self.tacho_service = TachoService(db)
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=45)
        self.columnconfigure(1, weight=55)
        self.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, S["4"]))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        self._build_import_panel(left)
        self._build_history_panel(right)

    # ── Left: Import panel ────────────────────────────────────────────

    def _build_import_panel(self, parent):
        page_heading(parent, t("tacho.title"), t("tacho.subtitle"))

        # Import card
        c = card(parent)
        c._outer.pack(fill="x", pady=(0, S["3"]))
        card_header(c, t("tacho.import_card_title"))
        content = ctk.CTkFrame(c, fg_color="transparent")
        content.pack(fill="x", padx=S["5"], pady=S["5"])

        # How it works info box
        info = ctk.CTkFrame(content, fg_color=COLORS["bg_elevated"],
                            corner_radius=6)
        info.pack(fill="x", pady=(0, S["3"]))
        ctk.CTkLabel(info, text=t("tacho.how_it_works"),
                     font=FONTS["body_bold"],
                     text_color=COLORS["text_primary"],
                     anchor="w").pack(anchor="w", padx=S["3"], pady=(S["2"], 0))
        steps = (
            "1. Driver inserts card into USB reader\n"
            "2. Export .DDD file using card reader software\n"
            "3. Import the .DDD file here"
        )
        ctk.CTkLabel(info, text=steps,
                     font=FONTS["small"],
                     text_color=COLORS["text_secondary"],
                     justify="left").pack(anchor="w", padx=S["3"],
                                          pady=(S["1"], S["2"]))

        # Buttons
        btn(content, t("tacho.import_driver_card"),
            command=self._import_driver_card,
            variant="primary").pack(fill="x", pady=(0, S["2"]))
        btn(content, t("tacho.import_vehicle_unit"),
            command=self._import_vehicle_unit,
            variant="secondary").pack(fill="x", pady=(0, S["2"]))

        # Progress label (hidden initially)
        self._progress_lbl = ctk.CTkLabel(
            content, text="",
            font=FONTS["body"],
            text_color=COLORS["accent_text"]
        )
        self._progress_lbl.pack(anchor="w", pady=(S["2"], 0))

        # Result card (hidden initially)
        self._result_card = card(parent)
        self._result_card._outer.pack(fill="x", pady=(S["4"], 0))
        self._result_card._outer.pack_forget()
        self._build_result_content(self._result_card)

    def _build_result_content(self, parent):
        self._result_content = ctk.CTkFrame(parent, fg_color="transparent")
        self._result_content.pack(fill="x", padx=S["5"], pady=S["5"])

        self._result_icon = ctk.CTkLabel(
            self._result_content, text="",
            font=("Segoe UI", 24)
        )
        self._result_icon.pack(anchor="w")

        self._result_msg = ctk.CTkLabel(
            self._result_content, text="",
            font=FONTS["body"],
            text_color=COLORS["text_primary"],
            anchor="w", wraplength=350
        )
        self._result_msg.pack(anchor="w", pady=(S["2"], 0))

        self._result_detail = ctk.CTkLabel(
            self._result_content, text="",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"],
            anchor="w", wraplength=350
        )
        self._result_detail.pack(anchor="w", pady=(S["1"], 0))

        self._result_violations = ctk.CTkLabel(
            self._result_content, text="",
            font=FONTS["label"],
            fg_color=COLORS["warning_dim"],
            text_color=COLORS["text_warning"],
            corner_radius=4, padx=S["2"], height=22
        )
        self._result_violations.pack(anchor="w", pady=(S["2"], 0))

    # ── Right: History panel ──────────────────────────────────────────

    def _build_history_panel(self, parent):
        c = card(parent)
        c._outer.pack(fill="both", expand=True)
        card_header(c, t("tacho.import_history"))

        self._history_scroll = ctk.CTkScrollableFrame(
            c, fg_color="transparent",
            scrollbar_button_color=COLORS["border"]
        )
        self._history_scroll.pack(fill="both", expand=True,
                                  padx=S["3"], pady=S["3"])

        self._refresh_history()

    def _refresh_history(self):
        for w in self._history_scroll.winfo_children():
            w.destroy()

        try:
            imports = self.tacho_service.get_import_history(limit=50)
        except Exception:
            imports = []

        if not imports:
            ctk.CTkLabel(self._history_scroll,
                         text=t("tacho.no_history"),
                         font=FONTS["small"],
                         text_color=COLORS["text_muted"]
                         ).pack(pady=S["8"])
            return

        for imp in imports:
            self._build_history_row(imp)

    def _build_history_row(self, imp):
        row = ctk.CTkFrame(self._history_scroll,
                           fg_color=COLORS["bg_elevated"],
                           corner_radius=6, height=44)
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        # File icon
        ctk.CTkLabel(row, text="🗄",
                     font=("Segoe UI", 14),
                     text_color=COLORS["text_muted"],
                     width=28).pack(side="left", padx=(S["3"], 0))

        # File name (truncated)
        fname = imp.get("file_name", "—")
        if len(fname) > 24:
            fname = fname[:21] + "…"
        ctk.CTkLabel(row, text=fname,
                     font=FONTS["body_bold"],
                     text_color=COLORS["text_primary"],
                     width=130, anchor="w"
                     ).pack(side="left", padx=(S["2"], 0))

        # Date
        imp_at = imp.get("imported_at", "")
        if isinstance(imp_at, str) and len(imp_at) >= 10:
            date_str = imp_at[:10]
        else:
            date_str = str(imp_at)[:10]
        ctk.CTkLabel(row, text=date_str,
                     font=FONTS["small"],
                     text_color=COLORS["text_muted"],
                     width=80).pack(side="left")

        # Type chip
        ftype = imp.get("file_type", "")
        type_label = (t("tacho.type_driver") if ftype == "driver_card"
                      else t("tacho.type_vehicle"))
        type_color = (COLORS["accent_dim"] if ftype == "driver_card"
                      else COLORS["info_dim"])
        ctk.CTkLabel(row, text=type_label,
                     font=FONTS["label"],
                     fg_color=type_color,
                     text_color=COLORS["text_primary"],
                     corner_radius=4, padx=S["2"], height=18
                     ).pack(side="left", padx=(S["2"], 0))

        # Status chip
        status = imp.get("parse_status", "ok")
        status_color = COLORS["success_dim"]
        status_text = "OK"
        if status == "error":
            status_color = COLORS["danger_dim"]
            status_text = "Error"
        elif status == "partial":
            status_color = COLORS["warning_dim"]
            status_text = "Partial"
        ctk.CTkLabel(row, text=status_text,
                     font=FONTS["label"],
                     fg_color=status_color,
                     text_color=COLORS["text_primary"],
                     corner_radius=4, padx=S["2"], height=18
                     ).pack(side="right", padx=(0, S["3"]))

    # ── Import actions ────────────────────────────────────────────────

    def _import_driver_card(self):
        file_path = filedialog.askopenfilename(
            title=t("tacho.select_driver_card"),
            filetypes=[
                ("DDD files", "*.ddd *.DDD"),
                ("All tachograph files", "*.ddd *.DDD *.tgd *.TGD"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self._run_import(file_path)

    def _import_vehicle_unit(self):
        file_path = filedialog.askopenfilename(
            title=t("tacho.select_vehicle_unit"),
            filetypes=[
                ("DDD files", "*.ddd *.DDD"),
                ("All tachograph files", "*.ddd *.DDD *.tgd *.TGD"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self._run_import(file_path)

    def _run_import(self, file_path: str):
        self._show_progress(t("tacho.importing"))
        self._result_card._outer.pack_forget()

        def do_import():
            result = self.tacho_service.import_ddd_file(file_path)
            self.after(0, lambda r=result: self._on_import_complete(r))

        threading.Thread(target=do_import, daemon=True).start()

    def _show_progress(self, text: str):
        self._progress_lbl.configure(text=text)
        self.update_idletasks()

    def _hide_progress(self):
        self._progress_lbl.configure(text="")

    def _on_import_complete(self, result: dict):
        self._hide_progress()
        if result.get("success"):
            self._show_result_success(result)
        else:
            self._show_result_error(result.get("error", "Unknown error"))
        self._refresh_history()

    def _show_result_success(self, result: dict):
        self._result_card._outer.pack(fill="x", pady=(S["4"], 0))
        self._result_icon.configure(text="✓",
                                     text_color=COLORS["text_success"])
        self._result_msg.configure(
            text=result.get("summary", "Import successful")
        )

        detail_parts = []
        if result.get("driver_name") and result.get("driver_name") != "Unknown Driver":
            detail_parts.append(f"Driver: {result['driver_name']}")
        if result.get("plate"):
            detail_parts.append(f"Plate: {result['plate']}")
        if result.get("calibration_expiry"):
            detail_parts.append(f"Calibration: {result['calibration_expiry']}")
        if result.get("days_imported"):
            detail_parts.append(f"Days: {result['days_imported']}")
        if result.get("odometer_km"):
            detail_parts.append(f"Odometer: {result['odometer_km']:.0f} km")

        self._result_detail.configure(
            text="  |  ".join(detail_parts) if detail_parts else ""
        )

        violations = result.get("violations_found", 0)
        if violations > 0:
            self._result_violations.configure(
                text=f"⚠ {violations} violation(s) flagged"
            )
            self._result_violations.pack(anchor="w", pady=(S["2"], 0))
        else:
            self._result_violations.pack_forget()

    def _show_result_error(self, error: str):
        self._result_card._outer.pack(fill="x", pady=(S["4"], 0))
        self._result_icon.configure(text="✗",
                                     text_color=COLORS["text_danger"])
        self._result_msg.configure(text=error)
        self._result_detail.configure(text="")
        self._result_violations.pack_forget()
