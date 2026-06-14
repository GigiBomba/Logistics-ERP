"""CMR (waybill) PDF generator — professional logistics-grade, 24-box layout.

Produces 2-page A4 CMR documents per the UN Convention on the Contract for the
International Carriage of Goods by Road (Geneva, 1956), with bilingual labels,
four-copy support, eFTI XML embedding, PDF/A-3 compliance, and signature pads.
"""
import json
import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from services.invoicing.config_manager import load_company_config
from services.invoicing.cmr_efti import generate_efti_xml

logger = logging.getLogger(__name__)


import functools


@functools.lru_cache(maxsize=1)
def _get_srgb_icc_profile() -> Optional[bytes]:
    """Load sRGB ICC profile for PDF/A-3 OutputIntent.

    Returns the ICC profile bytes, or None if unavailable.
    Tries local file first, then Pillow extraction.
    """
    icc_path = os.path.join("data", "srgb.icc")
    if os.path.isfile(icc_path):
        with open(icc_path, "rb") as f:
            data = f.read()
        if len(data) > 500 and data[36:40] == b"acsp":
            return data
    try:
        from PIL import Image, ImageCms
        import io
        img = Image.new("RGB", (1, 1), (255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=100)
        buf.seek(0)
        img2 = Image.open(buf)
        info = img2.info or {}
        if "icc_profile" in info and len(info["icc_profile"]) > 500:
            return info["icc_profile"]
    except Exception:
        pass
    return None



COPY_CONFIGS = [
    ("Sender", "RED", "#D32F2F", "#FFCDD2",
     "COPY FOR CONSIGNOR / COPIE PENTRU EXPEDITOR",
     "This copy is retained by: THE CONSIGNOR (SENDER)"),
    ("Consignee", "BLUE", "#1565C0", "#BBDEFB",
     "COPY FOR CONSIGNEE / COPIE PENTRU DESTINATAR",
     "This copy accompanies goods to: THE CONSIGNEE"),
    ("Carrier", "GREEN", "#2E7D32", "#C8E6C9",
     "COPY FOR CARRIER / COPIE PENTRU TRANSPORTATOR",
     "This copy is retained by: THE CARRIER"),
    ("Administrative", "BLACK", "#212121", "#BDBDBD",
     "ADMINISTRATIVE COPY / COPIE ADMINISTRATIVA",
     "This copy is for: ADMINISTRATIVE RECORDS"),
]


class CMRGenerator:
    def __init__(self, db=None, prefs=None):
        self.db = db
        self.prefs = prefs
        self.styles = getSampleStyleSheet()
        self._init_styles()

    def _init_styles(self):
        """Initialize shared Paragraph styles with modern, professional typography."""
        self.text_color = colors.HexColor("#1f2937")
        self.muted_color = colors.HexColor("#6b7280")

        self.sec_val = ParagraphStyle(
            "SecVal", parent=self.styles["Normal"],
            fontSize=8.5, leading=11, textColor=self.text_color,
            fontName="Helvetica", spaceAfter=1,
        )
        self.sig_style = ParagraphStyle(
            "CMRSig", parent=self.styles["Normal"],
            fontSize=7.5, leading=10, textColor=self.text_color,
            fontName="Helvetica",
        )
        self.footer_style = ParagraphStyle(
            "CMRFooter", parent=self.styles["Normal"],
            fontSize=7, leading=9, textColor=self.muted_color,
            alignment=TA_CENTER, spaceAfter=1,
        )
        self.badge_style = ParagraphStyle(
            "Badge", parent=self.styles["Normal"],
            fontSize=7, leading=9, textColor=colors.white,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        )
        # Header block styles (created once, reused)
        self._hdr_style = ParagraphStyle(
            "DocHeader", parent=self.styles["Normal"],
            fontSize=22, leading=26, textColor=colors.HexColor("#D32F2F"),
            fontName="Helvetica-Bold", alignment=0, spaceAfter=0,
        )
        self._hdr_sub_style = ParagraphStyle(
            "DocSub", parent=self.styles["Normal"],
            fontSize=7.5, leading=10, textColor=self.text_color,
            alignment=0, spaceAfter=2,
        )
        self._hdr_right_style = ParagraphStyle(
            "DocRight", parent=self.styles["Normal"],
            fontSize=8, leading=10, textColor=self.muted_color,
            alignment=TA_RIGHT, spaceBefore=4,
        )
        # Cargo table styles (created once, reused)
        self._cargo_hdr_style = ParagraphStyle(
            "cargo_hdr", parent=self.styles["Normal"], fontName="Helvetica-Bold",
            fontSize=5.5, leading=6.5, textColor=self.text_color,
            alignment=TA_LEFT, wordWrap="CJK",
        )
        self._cargo_val_style = ParagraphStyle(
            "cargo_val", parent=self.styles["Normal"], fontName="Helvetica",
            fontSize=7.5, leading=9, textColor=self.text_color,
            alignment=TA_LEFT, wordWrap="CJK",
        )
        self._adr_label_style = ParagraphStyle(
            "adr_label", parent=self.styles["Normal"], fontName="Helvetica-Bold",
            fontSize=6.5, leading=8, textColor=colors.HexColor("#991b1b"),
            alignment=TA_LEFT, wordWrap="CJK",
        )
        self._adr_hdr_style = ParagraphStyle(
            "adr_hdr", parent=self.styles["Normal"], fontName="Helvetica-Bold",
            fontSize=5.5, leading=6.5, textColor=self.text_color,
            alignment=TA_CENTER, wordWrap="CJK",
        )
        self._adr_val_style = ParagraphStyle(
            "adr_val", parent=self.styles["Normal"], fontName="Helvetica",
            fontSize=7, leading=8.5, textColor=self.text_color,
            alignment=TA_CENTER, wordWrap="CJK",
        )

    def _hex_color(self, hex_str: str):
        try:
            return colors.HexColor(hex_str)
        except Exception:
            return colors.HexColor("#6366f1")

    def _next_cmr_number(self) -> Tuple[str, int]:
        year = datetime.now().year
        if self.db:
            try:
                row = self.db.conn.execute(
                    "SELECT sequence_number FROM cmr_counter WHERE year = ?", (year,)
                ).fetchone()
                if row:
                    seq = int(row["sequence_number"]) + 1
                    self.db.conn.execute(
                        "UPDATE cmr_counter SET sequence_number = ? WHERE year = ?",
                        (seq, year),
                    )
                else:
                    seq = 1
                    self.db.conn.execute(
                        "INSERT INTO cmr_counter (year, sequence_number) VALUES (?, ?)",
                        (year, seq),
                    )
                self.db.conn.commit()
            except Exception as e:
                logger.debug("cmr_counter fallback: %s", e)
                seq = int(datetime.now().timestamp()) % 100000
        else:
            seq = int(datetime.now().timestamp()) % 100000
        cmr_number = f"CMR-{year}-{seq:06d}"
        return cmr_number, seq

    def _gather_context(self, trip_data: Dict[str, Any]) -> Dict[str, Any]:
        trip_id = trip_data.get("trip_id", trip_data.get("id", 0))
        conf = load_company_config()
        ctx = dict(trip_data)
        ctx.setdefault("trip_id", trip_id)
        ctx.setdefault("cmr_number", trip_data.get("cmr_number", ""))
        ctx.setdefault("cmr_sequence", trip_data.get("cmr_sequence", 0))
        if not ctx["cmr_number"]:
            cmr_number, seq = self._next_cmr_number()
            ctx["cmr_number"] = cmr_number
            ctx["cmr_sequence"] = seq
        # Consignor — override company config from form data
        ctx.setdefault("consignor_name",
            trip_data.get("consignor_name") or trip_data.get("company_name") or conf.get("company_name", ""))
        ctx.setdefault("consignor_address",
            trip_data.get("consignor_address") or trip_data.get("company_address") or conf.get("address", ""))
        ctx.setdefault("consignor_phone",
            trip_data.get("consignor_phone") or trip_data.get("company_phone") or conf.get("phone", ""))
        ctx.setdefault("consignor_vat",
            trip_data.get("consignor_vat") or trip_data.get("company_cui") or conf.get("cui", ""))
        ctx.setdefault("consignor_eori",
            trip_data.get("consignor_eori") or trip_data.get("eori_number") or conf.get("eori_number", ""))
        # Consignee — resolved from trip data or client lookup, no company fallback
        ctx.setdefault("client_name", trip_data.get("client_name", ""))
        ctx.setdefault("client_address", trip_data.get("client_address", ""))
        ctx.setdefault("consignee_vat", trip_data.get("consignee_vat", ""))
        ctx.setdefault("consignee_eori", trip_data.get("consignee_eori", ""))
        ctx.setdefault("consignee_contact", trip_data.get("consignee_contact", ""))
        # Carrier — override company config from form data
        ctx.setdefault("carrier_name",
            trip_data.get("carrier_name") or trip_data.get("company_name") or conf.get("company_name", ""))
        ctx.setdefault("carrier_address",
            trip_data.get("carrier_address") or trip_data.get("company_address") or conf.get("address", ""))
        ctx.setdefault("carrier_phone",
            trip_data.get("carrier_phone") or trip_data.get("company_phone") or conf.get("phone", ""))
        ctx.setdefault("carrier_email",
            trip_data.get("carrier_email") or trip_data.get("company_email") or conf.get("email", ""))
        ctx.setdefault("carrier_reg",
            trip_data.get("carrier_reg") or trip_data.get("company_reg") or conf.get("reg_number", ""))
        ctx.setdefault("carrier_insurance",
            trip_data.get("cmr_insurance_number") or conf.get("cmr_insurance", ""))
        # Signature/stamp — use "__NONE__" sentinel to force empty (allow clearing)
        sig_raw = trip_data.get("signature_path", conf.get("signature_path", ""))
        stamp_raw = trip_data.get("stamp_path", conf.get("stamp_path", ""))
        ctx["signature_path"] = "" if sig_raw == "__NONE__" else sig_raw
        ctx["stamp_path"] = "" if stamp_raw == "__NONE__" else stamp_raw
        ctx.setdefault("company_color", conf.get("company_color", "#6366f1"))
        ctx.setdefault("truck_plate", trip_data.get("truck_plate", trip_data.get("truck_number", "")))
        ctx.setdefault("trailer_plate", trip_data.get("trailer_plate", ""))
        ctx.setdefault("driver_name", trip_data.get("driver_name", ""))
        ctx.setdefault("driver_license", trip_data.get("driver_license", trip_data.get("license_number", "")))
        ctx.setdefault("loading_country", trip_data.get("loading_country", ""))
        ctx.setdefault("delivery_country", trip_data.get("delivery_country", ""))
        ctx.setdefault("loading_city", trip_data.get("loading_city", ""))
        ctx.setdefault("delivery_city", trip_data.get("delivery_city", ""))
        ctx.setdefault("place_of_loading", trip_data.get("place_of_loading",
                          trip_data.get("origin", trip_data.get("loading_address", ""))))
        ctx.setdefault("place_of_delivery", trip_data.get("destination",
                          trip_data.get("unloading_address", "")))
        ctx.setdefault("place_of_loading_date", trip_data.get("place_of_loading_date",
                          trip_data.get("start_date", "")))
        ctx.setdefault("documents_attached", trip_data.get("documents_attached", ""))
        ctx.setdefault("cargo_description", trip_data.get("cargo_description", ""))
        ctx.setdefault("cargo_marks", trip_data.get("cargo_marks", ""))
        ctx.setdefault("package_count", trip_data.get("package_count", ""))
        ctx.setdefault("package_type", trip_data.get("package_type", ""))
        ctx.setdefault("gross_weight_kg", trip_data.get("gross_weight_kg", ""))
        ctx.setdefault("volume_m3", trip_data.get("volume_m3", ""))
        ctx.setdefault("hs_code", trip_data.get("hs_code", ""))
        ctx.setdefault("carrier_instructions", trip_data.get("carrier_instructions", ""))
        ctx.setdefault("carrier_reservations", trip_data.get("carrier_reservations", ""))
        ctx.setdefault("special_agreements", trip_data.get("special_agreements", ""))
        ctx.setdefault("carriage_payer", trip_data.get("carriage_payer", ""))
        ctx.setdefault("distance_km", trip_data.get("distance_km", ""))
        ctx["successive_carriers"] = trip_data.get("successive_carriers", [])
        ctx["adr_items"] = self._parse_adr(trip_data)
        ctx["has_adr"] = bool(ctx["adr_items"])
        # New boxes from WYSIWYG form
        ctx.setdefault("cod_amount", trip_data.get("cod_amount", ""))
        ctx.setdefault("issue_place", trip_data.get("issue_place", ""))
        ctx.setdefault("issue_date", trip_data.get("issue_date", ""))
        ctx["financial_grid"] = trip_data.get("financial_grid", {})
        for party in ["sender", "carrier", "consignee"]:
            sig_key = f"sig_{party}_path"
            ctx.setdefault(sig_key, trip_data.get(sig_key, ""))
        # Generating role — determines whether company acts as consignor or consignee
        ctx["generating_role"] = trip_data.get("generating_role", "consignor")
        return ctx

    def _parse_adr(self, trip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw = trip_data.get("adr_info_json", "")
        if not raw:
            return []
        try:
            if isinstance(raw, str):
                items = json.loads(raw)
            else:
                items = raw
            return items if isinstance(items, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def generate(self, trip_data: dict, output_dir: str) -> str:
        ctx = self._gather_context(trip_data)
        filepath = self._build_single_copy(ctx, "Sender", output_dir)
        return filepath

    def generate_all_copies(self, trip_data: dict, output_dir: str,
                            skip_db_update: bool = False) -> Dict[str, str]:
        ctx = self._gather_context(trip_data)
        cmr_number = ctx["cmr_number"]
        paths = {}
        for suffix, color_name, color_hex, color_light, bar_text, desig_text in COPY_CONFIGS:
            path = self._build_single_copy(ctx, suffix, output_dir,
                                           color_hex, bar_text, desig_text)
            paths[suffix] = path

        if self.db and not skip_db_update:
            try:
                self.db.conn.execute(
                    "UPDATE trips SET cmr_number = ?, cmr_sequence = ?, cmr_status = 'generated' WHERE id = ?",
                    (cmr_number, ctx.get("cmr_sequence", 0), ctx["trip_id"]),
                )
                self.db.conn.commit()
            except Exception:
                pass

        return paths

    def _build_single_copy(self, ctx: Dict[str, Any], suffix: str,
                           output_dir: str, color_hex: str = "#D32F2F",
                           bar_text: str = "", desig_text: str = "") -> str:
        cmr_number = ctx["cmr_number"]
        filename = f"CMR_{suffix}_Copy.pdf"
        filepath = os.path.join(output_dir, filename)

        doc = SimpleDocTemplate(
            filepath, pagesize=A4,
            leftMargin=10 * mm, rightMargin=10 * mm,
            topMargin=10 * mm, bottomMargin=10 * mm,
            title=f"{cmr_number} - {suffix} Copy",
            author="Operion ERP",
            subject=f"eCMR {cmr_number}",
        )

        story = self._build_story(ctx, color_hex, bar_text, desig_text)

        def _draw_page_bg(canvas, doc):
            """Left-margin color stripe + top bar for copy identification."""
            canvas.saveState()
            canvas.setFillColor(colors.HexColor(color_hex))
            # Full-height left margin stripe (8mm wide)
            canvas.rect(0, 0, 8 * mm, A4[1], fill=1, stroke=0)
            # Top bar (3mm)
            canvas.rect(0, A4[1] - 3 * mm, A4[0], 3 * mm, fill=1, stroke=0)
            canvas.restoreState()

        doc.build(story, onFirstPage=_draw_page_bg, onLaterPages=_draw_page_bg)

        try:
            xml_data = generate_efti_xml(cmr_number, ctx, {
                "company_name": ctx.get("consignor_name", ""),
                "address": ctx.get("consignor_address", ""),
                "cui": ctx.get("consignor_vat", ""),
                "eori_number": ctx.get("consignor_eori", ""),
            }, client_data={
                "name": ctx.get("client_name", ""),
                "address": ctx.get("client_address", ""),
                "vat_number": ctx.get("consignee_vat", ""),
                "eori_number": ctx.get("consignee_eori", ""),
                "contact": ctx.get("consignee_contact", ""),
            }, truck_data={
                "plate_number": ctx.get("truck_plate", ""),
                "trailer_plate": ctx.get("trailer_plate", ""),
            }, driver_data={
                "name": ctx.get("driver_name", ""),
                "license_number": ctx.get("driver_license", ""),
            }, successive_carriers=ctx.get("successive_carriers", []),
            role=ctx.get("generating_role", "consignor"))
            self._embed_xml_payload(filepath, xml_data, cmr_number)
        except Exception as e:
            logger.debug("eFTI XML embedding skipped: %s", e)

        return filepath

    # ── Story Builder (grid-based, real CMR form layout) ───────────

    def _build_story(self, ctx, color_hex, bar_text, desig_text):
        """Build CMR form as a professional grid — 2-col body with unified cargo table."""
        story = []
        L = 78 * mm          # Left column width
        R = 112 * mm         # Right column width (cargo area)
        FW = L + R           # Full width = 190mm
        lc = colors.HexColor(color_hex)

        # ── Header ──
        story.append(self._copy_badge(color_hex, bar_text))
        story.append(Spacer(1, 2 * mm))
        story.append(self._header_block(ctx, color_hex, FW))
        story.append(self._hline(lc, 0.75))

        # ── Parties + Cargo Grid ──
        left_block = Paragraph(
            "<b>1. CONSIGNOR / EXPEDITOR</b><br/>" + self._party_text(ctx, "consignor") +
            "<br/><br/><b>2. CONSIGNEE / DESTINATAR</b><br/>" + self._party_text(ctx, "consignee"),
            self.sec_val)
        cargo_block = self._cargo_grid(ctx, R, lc)
        story.append(self._grid_2col(left_block, cargo_block, L, R, lc, min_height=70 * mm))

        # ── Loading & Delivery ──
        story.append(self._grid_2col(
            self._labeled_box("3. PLACE OF TAKING OVER / LOCUL PREDARII",
                              self._location_text(ctx, "loading")),
            self._labeled_box("4. PLACE OF DELIVERY / LOCUL LIVRARII",
                              self._location_text(ctx, "delivery")),
            L, R, lc))

        # ── Documents & Instructions ──
        story.append(self._grid_2col(
            self._labeled_box("5. DOCUMENTS ATTACHED / DOCUMENTE ATASATE",
                              ctx.get("documents_attached", "") or "—"),
            self._labeled_box("13. SENDER'S INSTRUCTIONS / INSTRUCTIUNI",
                              ctx.get("carrier_instructions", "") or "—"),
            L, R, lc))

        # ── Carrier & Reservations ──
        story.append(self._grid_2col(
            self._labeled_box("18. CARRIER / TRANSPORTATOR",
                              self._carrier_text(ctx)),
            self._labeled_box("14. CARRIER'S RESERVATIONS / REZERVE TRANSPORTATOR",
                              ctx.get("carrier_reservations", "") or "—"),
            L, R, lc))

        # ── Successive Carriers & Special Agreements ──
        succ = self._successive_text(ctx)
        story.append(self._grid_2col(
            self._labeled_box("19. SUCCESSIVE CARRIERS / TRANSPORTATORI SUCCESIVI", succ),
            self._labeled_box("17. SPECIAL AGREEMENTS / ACORDURI SPECIALE",
                              ctx.get("special_agreements", "") or "—"),
            L, R, lc))

        # ── Carriage Payment, COD, Distance & Vehicle ──
        payer = str(ctx.get("carriage_payer") or "")
        pay_label = ("Sender pays / Expeditorul plateste" if payer.lower() == "sender" else
                     "Consignee pays / Destinatarul plateste" if payer.lower() == "consignee" else "—")
        left_parts = [f"<b>15. PAYMENT OF CARRIAGE / PLATA TRANSPORT:</b> {pay_label}"]

        cod_amount = ctx.get("cod_amount", "")
        if cod_amount:
            left_parts.append(f"<b>16. CASH ON DELIVERY (COD) / RAMBURS:</b> EUR {cod_amount}")

        dist = ctx.get("distance_km", "")
        if dist:
            try:
                dist = round(float(dist), 1)
            except (ValueError, TypeError):
                pass
            left_parts.append(f"<b>Distance / Distanta:</b> {dist} km")

        vd = (f"Vehicle: {ctx.get('truck_plate') or '—'}   "
              f"Trailer: {ctx.get('trailer_plate') or '—'}\n"
              f"Driver: {ctx.get('driver_name') or '—'}")
        if ctx.get("driver_license"):
            vd += f"   Lic: {ctx['driver_license']}"
        story.append(self._grid_2col(
            self._labeled_box("15-16. CARRIAGE PAYMENT & COD / PLATA SI RAMBURS",
                              "<br/><br/>".join(left_parts)),
            self._labeled_box("VEHICLE & DRIVER / VEHICUL SI SOFER", vd),
            L, R, lc))

        # ── Box 20: Financial Grid (spanning full width, always shown) ──
        story.append(self._financial_grid(ctx, FW, lc))

        # ── Boxes 21-24: Issue info and Signatures ──
        issue_place = ctx.get("issue_place", "")
        issue_date = ctx.get("issue_date", "")
        issue_text = ""
        if issue_place or issue_date:
            issue_text = f"<b>Established in:</b> {issue_place}  <b>on:</b> {issue_date}"
        else:
            issue_text = "Established in: _______________  on: ___/___/______"
        story.append(self._full_width_box("21. ESTABLISHED IN / ON / EMIS IN / LA",
                                          issue_text, FW, lc))

        # ── Signatures (Boxes 22-24) ──
        story.append(self._signature_grid_enhanced(ctx, FW, lc))

        # ── Receipt ──
        story.append(self._full_width_box("RECEPTION CONFIRMATION / CONFIRMARE RECEPTIE",
                                          self._receipt_text(), FW, lc))

        # ── Footer ──
        story.append(Spacer(1, 4 * mm))
        story.append(self._hline(lc, 0.3))
        story.append(Paragraph(
            f"Generated by Operion ERP · {datetime.now().strftime('%d/%m/%Y %H:%M')} "
            f"· CMR {ctx['cmr_number']} · {desig_text}", self.footer_style))
        return story

    # ── Content Helpers ─────────────────────────────────────────────

    def _party_text(self, ctx, role):
        if role == "consignor":
            lines = [f"<b>{ctx.get('consignor_name', '')}</b>", ctx.get("consignor_address", "")]
            cui = ctx.get("consignor_vat", "")
            if cui: lines.append(f"VAT/CUI: {cui}")
            eori = ctx.get("consignor_eori", "")
            if eori: lines.append(f"EORI: {eori}")
            phone = ctx.get("consignor_phone", "")
            if phone: lines.append(f"Tel: {phone}")
        else:
            lines = [f"<b>{ctx.get('client_name', '')}</b>", ctx.get("client_address", "")]
            vat = ctx.get("consignee_vat", "")
            if vat: lines.append(f"VAT: {vat}")
            eori = ctx.get("consignee_eori", "")
            if eori: lines.append(f"EORI: {eori}")
            contact = ctx.get("consignee_contact", "")
            if contact: lines.append(f"Contact: {contact}")
        return "<br/>".join(lines)

    def _location_text(self, ctx, role):
        if role == "loading":
            addr = ctx.get("place_of_loading", "")
            country = ctx.get("loading_country", "")
            date = ctx.get("place_of_loading_date", "")
        else:
            addr = ctx.get("place_of_delivery", "")
            country = ctx.get("delivery_country", "")
            date = ""
        parts = [addr]
        if country: parts.append(f"Country: {country}")
        if date: parts.append(f"Date: {date}")
        return "<br/>".join(parts) if parts else "—"

    def _carrier_text(self, ctx):
        lines = [f"<b>{ctx.get('carrier_name', '')}</b>", ctx.get("carrier_address", "")]
        phone = ctx.get("carrier_phone", "")
        if phone: lines.append(f"Tel: {phone}")
        email = ctx.get("carrier_email", "")
        if email: lines.append(f"Email: {email}")
        reg = ctx.get("carrier_reg", "")
        if reg: lines.append(f"Reg No: {reg}")
        ins = ctx.get("carrier_insurance", "")
        if ins: lines.append(f"CMR Insurance: {ins}")
        return "<br/>".join(lines)

    def _successive_text(self, ctx):
        carriers = ctx.get("successive_carriers", [])
        if not carriers:
            return "—"
        rows = []
        for i, c in enumerate(carriers):
            parts = [f"<b>{c.get('carrier_name', '')}</b>"]
            addr = c.get('carrier_address', '')
            if addr:
                parts.append(addr)
            country = c.get('carrier_country', '')
            if country:
                parts.append(country)
            plate = c.get('vehicle_plate', '')
            if plate:
                parts.append(f"Plate: {plate}")
            trailer = c.get('trailer_plate', '')
            if trailer:
                parts.append(f"Trailer: {trailer}")
            driver = c.get('driver_name', '')
            if driver:
                parts.append(f"Driver: {driver}")
            from_loc = c.get('from_location', '')
            to_loc = c.get('to_location', '')
            if from_loc or to_loc:
                parts.append(f"Route: {from_loc} → {to_loc}")
            rows.append(f"{i + 1}. " + " — ".join(parts))
        return "<br/>".join(rows)

    def _receipt_text(self):
        return (
            "Place: __________________________  Date: ___/___/______  Time: ___:___<br/>"
            "Good condition: &#9744; Yes  &#9744; No<br/>"
            "Reservations: ________________________________________________<br/><br/>"
            "Signature + Stamp: ________________________________________________")

    # ── Grid Layout Primitives ─────────────────────────────────────

    def _hline(self, color, thickness=0.5):
        return HRFlowable(width="100%", thickness=thickness, color=color)

    def _copy_badge(self, color_hex, text):
        badge = Table([[Paragraph(text, self.badge_style)]],
                      colWidths=[A4[0] - 20 * mm], rowHeights=[5 * mm])
        badge.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(color_hex)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return badge

    def _header_block(self, ctx, color_hex, w):
        """Full-width header — uses cached styles from _init_styles."""
        self._hdr_style.textColor = colors.HexColor(color_hex)
        data = [[
            Paragraph("<b>CMR</b><br/>INTERNATIONAL<br/>CONSIGNMENT NOTE", self._hdr_style),
            Paragraph(
                f"<font size=11 color='{color_hex}'><b>No: {ctx['cmr_number']}</b></font><br/>"
                f"Trip #{ctx['trip_id']}<br/>"
                f"{datetime.now().strftime('%d %b %Y')}",
                self._hdr_right_style),
        ]]
        tbl = Table(data, colWidths=[w * 0.65, w * 0.35])
        tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return tbl

    def _grid_2col(self, left, right, left_w, right_w, lc, min_height=None):
        """Two-column grid row with copy-colored borders on all sides."""
        data = [[left, right]]
        row_heights = None
        if min_height:
            row_heights = [min_height]
        tbl = Table(data, colWidths=[left_w, right_w], rowHeights=row_heights)
        tbl.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, lc),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (0, 0), 3 * mm),
            ('RIGHTPADDING', (0, 0), (0, 0), 1.5 * mm),
            ('LEFTPADDING', (1, 0), (1, 0), 1.5 * mm),
            ('RIGHTPADDING', (1, 0), (1, 0), 3 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ]))
        return tbl

    def _labeled_box(self, label, value):
        """A box with a bold label and value text."""
        return Paragraph(
            f"<b>{label}</b><br/>{value}", self.sec_val)

    def _full_width_box(self, label, value, w, lc):
        """A single full-width bordered box."""
        content = Paragraph(f"<b>{label}</b><br/>{value}", self.sec_val)
        tbl = Table([[content]], colWidths=[w - 0 * mm])
        tbl.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, lc),
            ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5 * mm),
        ]))
        return tbl

    def _cargo_grid(self, ctx, right_w, lc):
        """Unified cargo table with 6 fixed-width columns — all vertical lines align.
        Includes conditional ADR rows."""
        c6 = [22 * mm, 13 * mm, 12 * mm, 27 * mm, 18 * mm, 20 * mm]  # = 112mm

        marks_val = ctx.get("cargo_marks", "") or "—"
        pkg_val = ctx.get("package_count", "") or "—"
        kind_val = ctx.get("package_type", "") or "—"
        nature_val = ctx.get("cargo_description", "") or "—"
        hs_val = ctx.get("hs_code", "") or "—"
        wt_val = (f"{ctx['gross_weight_kg']} kg" if ctx.get("gross_weight_kg") else "—")
        vol_val = (f"{ctx['volume_m3']} m³" if ctx.get("volume_m3") else "—")

        def H(s):
            return Paragraph(s, self._cargo_hdr_style)

        def V(s):
            return Paragraph(str(s), self._cargo_val_style)

        rows = [
            [H("6. MARKS &amp; NUMBERS"), H("7. NO. PKGS"), H("8. METHOD"),
             H("9. NATURE OF GOODS"), H("10. HS CODE"), H("11. WT / 12. VOL")],
            [V(marks_val), "", "", "", "", ""],
            [V(pkg_val), V(kind_val), V(nature_val), V(hs_val), V(wt_val), V(vol_val)],
        ]

        if ctx.get("has_adr"):
            adr_items = ctx["adr_items"]
            rows.append([Paragraph("ADR — DANGEROUS GOODS", self._adr_label_style),
                         "", "", "", "", ""])
            rows.append([
                Paragraph("UN No", self._adr_hdr_style),
                Paragraph("Class", self._adr_hdr_style),
                Paragraph("Pack Grp", self._adr_hdr_style),
                Paragraph("Tunnel", self._adr_hdr_style),
                Paragraph("Qty", self._adr_hdr_style),
                Paragraph("Net Wt", self._adr_hdr_style),
            ])
            for item in adr_items:
                rows.append([
                    Paragraph(str(item.get("un_no", "")), self._adr_val_style),
                    Paragraph(str(item.get("adr_class", "")), self._adr_val_style),
                    Paragraph(str(item.get("packing_group", "")), self._adr_val_style),
                    Paragraph(str(item.get("tunnel_code", "")), self._adr_val_style),
                    Paragraph(str(item.get("quantity", "")), self._adr_val_style),
                    Paragraph(str(item.get("net_weight", "")), self._adr_val_style),
                ])

        tbl = Table(rows, colWidths=c6)
        styles = [
            ('GRID', (0, 0), (-1, -1), 0.5, lc),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('LINEBELOW', (0, 0), (-1, 0), 0.75, lc),
            ('SPAN', (0, 1), (5, 1)),
            ('BACKGROUND', (0, 1), (-1, 1), colors.white),
        ]

        # ADR-specific styling
        if ctx.get("has_adr"):
            adr_idx = 3
            styles.extend([
                ('SPAN', (0, adr_idx), (5, adr_idx)),
                ('BACKGROUND', (0, adr_idx), (-1, adr_idx), colors.HexColor("#fef2f2")),
                ('BACKGROUND', (0, adr_idx + 1), (-1, adr_idx + 1), colors.HexColor("#fef2f2")),
                ('ALIGN', (0, adr_idx + 1), (-1, -1), 'CENTER'),
                ('VALIGN', (0, adr_idx + 1), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, adr_idx + 2), (-1, -1),
                 [colors.white, colors.HexColor("#fff5f5")]),
            ])

        tbl.setStyle(TableStyle(styles))
        return tbl

    def _financial_grid(self, ctx, w, lc):
        """Box 20: To be Paid by — financial split sub-grid."""
        fin = ctx.get("financial_grid", {})
        if not isinstance(fin, dict):
            fin = {}
        cost_rows = [
            ("Carriage charges / Taxe transport",
             fin.get("carriage_sender", ""),
             fin.get("carriage_consignee", "")),
            ("Supplementary charges / Taxe suplimentare",
             fin.get("supplementary_sender", ""),
             fin.get("supplementary_consignee", "")),
            ("Customs duties / Taxe vamale",
             fin.get("customs_sender", ""),
             fin.get("customs_consignee", "")),
            ("Other costs / Alte costuri",
             fin.get("other_sender", ""),
             fin.get("other_consignee", "")),
        ]
        hdr_style = self._cargo_hdr_style
        val_style = self._cargo_val_style

        header = [
            Paragraph("20. TO BE PAID BY", hdr_style),
            Paragraph("Sender", hdr_style),
            Paragraph("Consignee", hdr_style),
        ]
        cw = [w * 0.45, w * 0.275, w * 0.275]
        data = [header]
        for label, sender_val, consignee_val in cost_rows:
            data.append([
                Paragraph(label, val_style),
                Paragraph(f"EUR {sender_val}" if sender_val else "—", val_style),
                Paragraph(f"EUR {consignee_val}" if consignee_val else "—", val_style),
            ])
        tbl = Table(data, colWidths=cw)
        tbl.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, lc),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('LINEBELOW', (0, 0), (-1, 0), 0.75, lc),
        ]))
        return tbl

    def _signature_grid_enhanced(self, ctx, w, lc):
        """Boxes 22-24: Signature pads for Sender, Carrier, Consignee."""
        q = w / 3
        pads = []
        for box_num, label, party_key in [
            (22, "Sender / Expeditor", "sender"),
            (23, "Carrier / Transportator", "carrier"),
            (24, "Consignee / Destinatar", "consignee"),
        ]:
            pads.append(self._sig_pad_enhanced(box_num, label, party_key, ctx, q))
        data = [pads]
        tbl = Table(data, colWidths=[q, q, q])
        tbl.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, lc),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ]))
        return tbl

    def _sig_pad_enhanced(self, box_num, label, party_key, ctx, pad_w):
        """Enhanced signature pad with box number, supporting per-party signature images."""
        guts = (
            f"<b>Box {box_num}. {label}</b><br/><br/>"
            "Date: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/>"
            "Place: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/>"
            "Name: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/>"
            "Signature: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>"
        )
        elements = [Paragraph(guts, self.sig_style)]
        sig_key = f"sig_{party_key}_path"
        sig_path = ctx.get(sig_key, ctx.get("signature_path", ""))
        if sig_path and os.path.isfile(sig_path):
            elements.append(Spacer(1, 1 * mm))
            try:
                elements.append(Image(sig_path, width=2.2 * cm, height=0.9 * cm))
            except Exception:
                pass
        return elements

    def _embed_xml_payload(self, pdf_path, xml_string, cmr_number):
        try:
            self._embed_xml_pdfa3(pdf_path, xml_string, cmr_number)
        except ImportError:
            self._embed_xml_fallback(pdf_path, xml_string, cmr_number)
        except Exception as e:
            logger.debug("PDF/A-3 pikepdf wrapper failed, using pypdf fallback: %s", e)
            self._embed_xml_fallback(pdf_path, xml_string, cmr_number)

    def _embed_xml_pdfa3(self, pdf_path, xml_string, cmr_number):
        """Apply full PDF/A-3 compliance structures using pikepdf.

        Adds:
        - eFTI XML as embedded file with /AFRelationship=/Data
        - XMP metadata stream with pdfaid:part=3, pdfaid:conformance=B
        - /OutputIntents with sRGB ICC profile
        - /MarkInfo with /Marked=true for tagged PDF
        - Document-level metadata (Title, Author, Subject, Keywords)
        """
        import pikepdf

        icc_data = _get_srgb_icc_profile()
        now_utc = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")

        with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
            # ── XMP Metadata Stream (PDF/A-3 conformance declarations) ──
            xmp = (
                '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
                '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
                '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
                '    <rdf:Description rdf:about=""\n'
                '        xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">\n'
                '      <pdfaid:part>3</pdfaid:part>\n'
                '      <pdfaid:conformance>B</pdfaid:conformance>\n'
                '    </rdf:Description>\n'
                '    <rdf:Description rdf:about=""\n'
                '        xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
                f'      <dc:title>{cmr_number.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}</dc:title>\n'
                '      <dc:creator>Operion ERP</dc:creator>\n'
                f'      <dc:subject>eCMR {cmr_number}</dc:subject>\n'
                '    </rdf:Description>\n'
                '    <rdf:Description rdf:about=""\n'
                '        xmlns:xmp="http://ns.adobe.com/xap/1.0/">\n'
                f'      <xmp:CreateDate>{now_utc}</xmp:CreateDate>\n'
                f'      <xmp:ModifyDate>{now_utc}</xmp:ModifyDate>\n'
                '      <xmp:CreatorTool>Operion CMR Generator v2.0</xmp:CreatorTool>\n'
                '    </rdf:Description>\n'
                '  </rdf:RDF>\n'
                '</x:xmpmeta>\n'
                '<?xpacket end="w"?>'
            )
            metadata_stream = pikepdf.Stream(
                pdf, xmp.encode("utf-8"),
                Subtype="/XML", Type="/Metadata",
            )
            pdf.Root["/Metadata"] = metadata_stream

            # ── Document Info (complementary to XMP) ──
            info = pdf.docinfo or pikepdf.Dictionary()
            info["/Title"] = cmr_number
            info["/Author"] = "Operion ERP"
            info["/Subject"] = f"eCMR {cmr_number}"
            info["/Keywords"] = "cmr,efti,consignment"
            info["/Creator"] = "Operion CMR Generator v2.0"
            info["/CreationDate"] = now_utc
            info["/ModDate"] = now_utc
            pdf.docinfo = info

            # ── /OutputIntents with sRGB ICC Profile ──
            if icc_data:
                icc_stream = pikepdf.Stream(pdf, icc_data,
                    N=3,  # number of color components (RGB)
                )
                intent = pikepdf.Dictionary({
                    "/Type": "/OutputIntent",
                    "/S": "/GTS_PDFA1",
                    "/OutputConditionIdentifier": "sRGB IEC61966-2.1",
                    "/Info": "sRGB IEC61966-2.1",
                    "/DestOutputProfile": icc_stream,
                })
                pdf.Root["/OutputIntents"] = pikepdf.Array([intent])

            # ── /MarkInfo ──
            pdf.Root["/MarkInfo"] = pikepdf.Dictionary({"/Marked": True})

            # ── Embed eFTI XML with AFRelationship ──
            xml_bytes = xml_string.encode("utf-8")
            spec = pikepdf.AttachedFileSpec(
                pdf, xml_bytes,
                description=f"eFTI eCMR structured data for {cmr_number}",
                filename="cmr_efti_data.xml",
                mime_type="text/xml",
                creation_date=now_utc,
                mod_date=now_utc,
                relationship=pikepdf.Name("/Data"),
            )
            pdf.attachments._add_replace_filespec("cmr_efti_data.xml", spec)

            # ── /AF array in document catalog (PDF/A-3 requirement) ──
            # Ensure the file spec is referenced from Root.AF
            af_array = pdf.Root.get("/AF")
            if af_array is None:
                af_array = pikepdf.Array()
                pdf.Root["/AF"] = af_array
            # Find the Filespec object in the Names tree and add to AF
            names = pdf.Root.get("/Names", pikepdf.Dictionary())
            embedded_files = names.get("/EmbeddedFiles", pikepdf.Dictionary())
            names_tree = embedded_files.get("/Names", pikepdf.Array())
            if names_tree and hasattr(names_tree, '__len__'):
                for i in range(0, len(names_tree), 2):
                    if i + 1 < len(names_tree):
                        file_spec = names_tree[i + 1]
                        if file_spec not in af_array:
                            af_array.append(file_spec)

            # ── Save ──
            pdf.save(pdf_path)

    def _embed_xml_fallback(self, pdf_path, xml_string, cmr_number):
        """Fallback embedding using pypdf (no PDF/A-3 structures)."""
        try:
            from pypdf import PdfReader, PdfWriter
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.add_attachment(
                "cmr_efti_data.xml",
                xml_string.encode("utf-8"),
            )
            writer.add_metadata({
                "/Title": cmr_number,
                "/Author": "Operion ERP",
                "/Subject": f"eCMR {cmr_number}",
                "/Keywords": "cmr,efti,consignment",
            })
            with open(pdf_path, "wb") as f:
                writer.write(f)
        except ImportError:
            pass
        except Exception as e:
            logger.debug("XML embedding skipped: %s", e)
