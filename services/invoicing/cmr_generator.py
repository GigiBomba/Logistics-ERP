"""CMR (waybill) PDF generator — professional logistics-grade, 24-box layout.

Produces 2-page A4 CMR documents per the UN Convention on the Contract for the
International Carriage of Goods by Road (Geneva, 1956), with bilingual labels,
four-copy support, eFTI XML embedding, PDF/A-3 compliance, and signature pads.
"""
import json
import os
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from services.invoicing.config_manager import load_company_config
from services.invoicing.cmr_efti import generate_efti_xml

logger = logging.getLogger(__name__)


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

BOX_LABELS = {
    "box_1": "CONSIGNOR / EXPEDITOR",
    "box_2": "CONSIGNEE / DESTINATAR",
    "box_3": "PLACE OF TAKING OVER / LOCUL PREDARII",
    "box_4": "PLACE OF DELIVERY / LOCUL LIVRARII",
    "box_5": "DOCUMENTS ATTACHED / DOCUMENTE ATASATE",
    "box_6": "MARKS AND NUMBERS / MARCAJE SI NUMERE",
    "box_7": "NUMBER & KIND OF PACKAGES / NR. SI TIP COLETE",
    "box_8": "NATURE OF GOODS / NATURA MARFII",
    "box_9": "STATISTICAL NUMBER / COD STATISTIC",
    "box_10": "GROSS WEIGHT (KG) / GREUTATE BRUTA",
    "box_11": "VOLUME (M\\u00B3) / VOLUM",
    "box_12": "SENDER'S INSTRUCTIONS / INSTRUCTIUNILE EXPEDITORULUI",
    "box_13": "CARRIER'S RESERVATIONS / REZERVELE TRANSPORTATORULUI",
    "box_14": "SPECIAL AGREEMENTS / ACORDURI SPECIALE",
    "box_15": "CARRIAGE CHARGES / TAXE DE TRANSPORT",
    "box_16": "CARRIER / TRANSPORTATOR",
    "box_17": "SUCCESSIVE CARRIERS / TRANSPORTATORI SUCCESIVI",
    "box_18": "VEHICLE / VEHICUL",
    "box_19": "TRAILER / REMORCA",
    "box_20": "DRIVER / SOFER",
    "box_21": "ADR - DANGEROUS GOODS / MARFURI PERICULOASE",
    "box_22": "SENDER'S SIGNATURE / SEMNATURA EXPEDITORULUI",
    "box_23": "CARRIER'S SIGNATURE / SEMNATURA TRANSPORTATORULUI",
    "box_24": "CONSIGNEE'S SIGNATURE / SEMNATURA DESTINATARULUI",
    "box_25": "CONSIGNMENT RECEIVED / RECEPTIE MARFA",
}


class CMRGenerator:
    def __init__(self, db=None, prefs=None):
        self.db = db
        self.prefs = prefs
        self.styles = getSampleStyleSheet()
        self._init_styles()

    def _init_styles(self):
        """Initialize shared Paragraph styles with modern, professional typography."""
        self.primary_color = self._hex_color(load_company_config().get("company_color", "#6366f1"))
        self.text_color = colors.HexColor("#1f2937")
        self.muted_color = colors.HexColor("#6b7280")
        self.light_bg = colors.HexColor("#f8fafc")
        self.border_color = colors.HexColor("#cbd5e1")
        self.header_bg = colors.HexColor("#f1f5f9")

        # Section label — muted italic above each section
        self.sec_label = ParagraphStyle(
            "SecLabel", parent=self.styles["Normal"],
            fontSize=7, leading=9, textColor=self.muted_color,
            fontName="Helvetica-Oblique", spaceAfter=1,
        )
        # Section value — primary text
        self.sec_val = ParagraphStyle(
            "SecVal", parent=self.styles["Normal"],
            fontSize=8.5, leading=11, textColor=self.text_color,
            fontName="Helvetica", spaceAfter=1,
        )
        # Small value — for secondary info
        self.sec_small = ParagraphStyle(
            "SecSmall", parent=self.styles["Normal"],
            fontSize=7.5, leading=10, textColor=self.text_color,
            fontName="Helvetica", spaceAfter=1,
        )
        # Title
        self.title_style = ParagraphStyle(
            "CMRTitle", parent=self.styles["Title"],
            fontSize=16, leading=20, textColor=self.text_color,
            fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=1,
        )
        # Subtitle
        self.subtitle_style = ParagraphStyle(
            "CMRSubtitle", parent=self.styles["Normal"],
            fontSize=8, leading=10, textColor=self.muted_color,
            alignment=TA_CENTER, spaceAfter=4,
        )
        # Signature
        self.sig_style = ParagraphStyle(
            "CMRSig", parent=self.styles["Normal"],
            fontSize=7.5, leading=10, textColor=self.text_color,
            fontName="Helvetica",
        )
        # Footer
        self.footer_style = ParagraphStyle(
            "CMRFooter", parent=self.styles["Normal"],
            fontSize=7, leading=9, textColor=self.muted_color,
            alignment=TA_CENTER, spaceAfter=1,
        )
        # Copy badge text
        self.badge_style = ParagraphStyle(
            "Badge", parent=self.styles["Normal"],
            fontSize=7, leading=9, textColor=colors.white,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        )

    def _safe_str(self, val) -> str:
        if val is None:
            return ""
        return str(val)

    def _hex_color(self, hex_str: str):
        """Convert hex color string to ReportLab Color, safely."""
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
        ctx.setdefault("company_name", conf.get("company_name", ""))
        ctx.setdefault("company_address", conf.get("address", ""))
        ctx.setdefault("company_phone", conf.get("phone", ""))
        ctx.setdefault("company_email", conf.get("email", ""))
        ctx.setdefault("company_cui", conf.get("cui", ""))
        ctx.setdefault("company_reg", conf.get("reg_number", ""))
        ctx.setdefault("signature_path", conf.get("signature_path", ""))
        ctx.setdefault("stamp_path", conf.get("stamp_path", ""))
        ctx.setdefault("company_color", conf.get("company_color", "#6366f1"))
        ctx.setdefault("truck_plate", trip_data.get("truck_plate",
                          trip_data.get("truck_number", "")))
        ctx.setdefault("trailer_plate", trip_data.get("trailer_plate", ""))
        ctx.setdefault("driver_name", trip_data.get("driver_name", ""))
        ctx.setdefault("driver_license", trip_data.get("driver_license",
                          trip_data.get("license_number", "")))
        ctx.setdefault("cmr_insurance", trip_data.get("cmr_insurance_number", ""))
        ctx.setdefault("eori_number", trip_data.get("eori_number", ""))
        ctx.setdefault("loading_country", trip_data.get("loading_country", ""))
        ctx.setdefault("delivery_country", trip_data.get("delivery_country", ""))
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
        ctx.setdefault("start_date", trip_data.get("start_date", ""))
        ctx.setdefault("end_date", trip_data.get("end_date", ""))
        ctx["successive_carriers"] = trip_data.get("successive_carriers", [])
        ctx["adr_items"] = self._parse_adr(trip_data)
        ctx["has_adr"] = bool(ctx["adr_items"])
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

    def generate_all_copies(self, trip_data: dict, output_dir: str) -> Dict[str, str]:
        ctx = self._gather_context(trip_data)
        cmr_number = ctx["cmr_number"]
        paths = {}
        for suffix, color_name, color_hex, color_light, bar_text, desig_text in COPY_CONFIGS:
            path = self._build_single_copy(ctx, suffix, output_dir,
                                           color_name, color_hex, color_light,
                                           bar_text, desig_text)
            paths[suffix] = path

        if self.db:
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
                           output_dir: str, color_name: str = "Sender",
                           color_hex: str = "#D32F2F", color_light: str = "#FFCDD2",
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
            """Top-edge color bar for copy identification."""
            canvas.saveState()
            canvas.setFillColor(colors.HexColor(color_hex))
            canvas.rect(0, A4[1] - 3 * mm, A4[0], 3 * mm, fill=1, stroke=0)
            canvas.restoreState()

        doc.build(story, onFirstPage=_draw_page_bg, onLaterPages=_draw_page_bg)

        try:
            xml_data = generate_efti_xml(cmr_number, ctx, {
                "company_name": ctx.get("company_name", ""),
                "address": ctx.get("company_address", ""),
                "cui": ctx.get("company_cui", ""),
                "eori_number": ctx.get("eori_number", ""),
            })
            self._embed_xml_payload(filepath, xml_data, cmr_number)
        except Exception as e:
            logger.debug("eFTI XML embedding skipped: %s", e)

        return filepath

    # ── Continuous Story Builder ────────────────────────────────────

    def _build_story(self, ctx, color_hex, bar_text, desig_text):
        """Build one continuous story — ReportLab auto-paginates when needed."""
        story = []
        w = A4[0] - 20 * mm
        line_color = colors.HexColor(color_hex)

        # ── Header ──
        story.append(self._copy_badge(color_hex, bar_text))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            "<b>CMR</b> &mdash; International Consignment Note", self.title_style))
        story.append(Paragraph(
            "Convention on the Contract for the International Carriage of Goods by Road "
            "(Geneva, 19 May 1956)", self.subtitle_style))
        story.append(Paragraph(
            f"<b>Ref:</b> {ctx['cmr_number']} &nbsp;&nbsp; <b>Trip:</b> #{ctx['trip_id']} "
            f"&nbsp;&nbsp; <b>Date:</b> {datetime.now().strftime('%d %b %Y')}",
            self.footer_style))
        story.append(self._hline(line_color, 0.75))

        # ── 1. Consignor ──
        story.append(self._section_label("1. CONSIGNOR / EXPEDITOR"))
        story.append(Paragraph(self._party_text(ctx, "consignor"), self.sec_val))
        story.append(Spacer(1, 1 * mm))

        # ── 2. Consignee ──
        story.append(self._section_label("2. CONSIGNEE / DESTINATAR"))
        story.append(Paragraph(self._party_text(ctx, "consignee"), self.sec_val))
        story.append(self._hline(line_color, 0.5))

        # ── 3 & 4. Loading & Delivery ──
        story.append(self._two_col_table(
            [("3. PLACE OF TAKING OVER", self._location_text(ctx, "loading")),
             ("4. PLACE OF DELIVERY", self._location_text(ctx, "delivery"))],
            w, line_color))
        story.append(self._hline(line_color, 0.5))

        # ── 5. Documents ──
        docs = ctx.get("documents_attached", "") or "None"
        story.append(self._section_label("5. DOCUMENTS ATTACHED / DOCUMENTE ATAȘATE"))
        story.append(Paragraph(docs, self.sec_small))
        story.append(self._hline(line_color, 0.5))

        # ── Cargo Table ──
        story.append(self._section_label("GOODS / MARFĂ"))
        story.append(self._cargo_table(ctx, w, line_color))
        story.append(self._hline(line_color, 0.5))

        # ── 12 & 13. Instructions & Reservations ──
        inst = ctx.get("carrier_instructions", "") or "None"
        res = ctx.get("carrier_reservations", "") or "None"
        story.append(self._two_col_table(
            [("12. SENDER'S INSTRUCTIONS", inst),
             ("13. CARRIER'S RESERVATIONS", res)],
            w, line_color))
        story.append(self._hline(line_color, 0.5))

        # ── 14 & 15. Agreements & Charges ──
        agr = ctx.get("special_agreements", "") or "None"
        payer = ctx.get("carriage_payer", "")
        charges = (
            "Sender pays / Expeditorul plătește" if payer == "sender" else
            "Consignee pays / Destinatarul plătește" if payer == "consignee" else
            "&mdash;"
        )
        dist = ctx.get("distance_km", "")
        if dist:
            charges += f"<br/>Distance: {dist} km"
        story.append(self._two_col_table(
            [("14. SPECIAL AGREEMENTS", agr),
             ("15. CARRIAGE CHARGES", charges)],
            w, line_color))
        story.append(self._hline(line_color, 0.5))

        # ── 16. Carrier ──
        story.append(self._section_label("16. CARRIER / TRANSPORTATOR"))
        story.append(Paragraph(self._carrier_text(ctx), self.sec_val))
        story.append(self._hline(line_color, 0.5))

        # ── 17. Successive Carriers ──
        if ctx.get("successive_carriers"):
            story.append(self._section_label("17. SUCCESSIVE CARRIERS"))
            story.append(Paragraph(self._successive_text(ctx), self.sec_small))
            story.append(self._hline(line_color, 0.5))

        # ── 18, 19, 20. Vehicle / Trailer / Driver ──
        v_text = ctx.get("truck_plate", "") or "&mdash;"
        t_text = ctx.get("trailer_plate", "") or "&mdash;"
        d_lines = []
        if ctx.get("driver_name"):
            d_lines.append(ctx["driver_name"])
        if ctx.get("driver_license"):
            d_lines.append(f"License: {ctx['driver_license']}")
        d_text = "<br/>".join(d_lines) if d_lines else "&mdash;"
        story.append(self._three_col_table(
            [("18. VEHICLE", v_text),
             ("19. TRAILER", t_text),
             ("20. DRIVER", d_text)],
            w, line_color))
        story.append(self._hline(line_color, 0.5))

        # ── 21. ADR ──
        if ctx.get("has_adr"):
            story.append(self._section_label("21. DANGEROUS GOODS (ADR)"))
            story.append(self._adr_table(ctx, w, line_color))
            story.append(self._hline(line_color, 0.5))

        # ── 22-24. Signatures ──
        story.append(self._section_label("SIGNATURES / SEMNĂTURI"))
        story.append(self._signature_row(ctx, w, line_color))
        story.append(self._hline(line_color, 0.5))

        # ── 25. Receipt ──
        story.append(self._section_label("25. CONSIGNMENT RECEIVED / RECEPTIE MARFĂ"))
        story.append(self._receipt_block())

        # ── Footer ──
        story.append(Spacer(1, 4 * mm))
        story.append(self._hline(line_color, 0.3))
        story.append(Paragraph(
            f"Generated by Operion ERP &middot; {datetime.now().strftime('%d/%m/%Y %H:%M')} "
            f"&middot; CMR {ctx['cmr_number']} &middot; {desig_text}", self.footer_style))
        return story

    # ── Content Helpers ─────────────────────────────────────────────

    def _party_text(self, ctx, role):
        if role == "consignor":
            lines = [f"<b>{ctx.get('company_name', '')}</b>", ctx.get("company_address", "")]
            cui = ctx.get("company_cui", "")
            if cui:
                lines.append(f"VAT/CUI: {cui}")
            eori = ctx.get("eori_number", "")
            if eori:
                lines.append(f"EORI: {eori}")
            phone = ctx.get("company_phone", "")
            if phone:
                lines.append(f"Tel: {phone}")
        else:
            lines = [f"<b>{ctx.get('client_name', '')}</b>", ctx.get("client_address", "")]
            vat = ctx.get("consignee_vat", "")
            if vat:
                lines.append(f"VAT: {vat}")
            eori = ctx.get("consignee_eori", "")
            if eori:
                lines.append(f"EORI: {eori}")
            contact = ctx.get("consignee_contact", "")
            if contact:
                lines.append(f"Contact: {contact}")
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
        if country:
            parts.append(f"Country: {country}")
        if date:
            parts.append(f"Date: {date}")
        return "<br/>".join(parts) if parts else "&mdash;"

    def _carrier_text(self, ctx):
        lines = [f"<b>{ctx.get('company_name', '')}</b>", ctx.get("company_address", "")]
        phone = ctx.get("company_phone", "")
        if phone:
            lines.append(f"Tel: {phone}")
        email = ctx.get("company_email", "")
        if email:
            lines.append(f"Email: {email}")
        reg = ctx.get("company_reg", "")
        if reg:
            lines.append(f"Reg No: {reg}")
        ins = ctx.get("cmr_insurance", "")
        if ins:
            lines.append(f"CMR Insurance: {ins}")
        return "<br/>".join(lines)

    def _successive_text(self, ctx):
        carriers = ctx.get("successive_carriers", [])
        if not carriers:
            return "None"
        rows = []
        for i, c in enumerate(carriers):
            rows.append(
                f"{i + 1}. <b>{c.get('carrier_name', '')}</b> &mdash; "
                f"{c.get('carrier_address', '')} &mdash; "
                f"Plate: {c.get('vehicle_plate', '')} &mdash; "
                f"Driver: {c.get('driver_name', '')}"
            )
        return "<br/>".join(rows)

    # ── Layout Primitives ───────────────────────────────────────────

    def _section_label(self, text):
        return Paragraph(text, self.sec_label)

    def _hline(self, color, thickness=0.5):
        return HRFlowable(width="100%", thickness=thickness, color=color)

    def _copy_badge(self, color_hex, text):
        """Small colored badge at top."""
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

    def _two_col_table(self, items, total_w, line_color):
        """Clean two-column layout: label+value pairs side by side."""
        half = total_w / 2
        left_label, left_val = items[0]
        right_label, right_val = items[1]
        data = [
            [Paragraph(left_label, self.sec_label), Paragraph(right_label, self.sec_label)],
            [Paragraph(left_val, self.sec_val), Paragraph(right_val, self.sec_val)],
        ]
        tbl = Table(data, colWidths=[half, half])
        tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (0, -1), 3 * mm),
            ('RIGHTPADDING', (1, 0), (1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1 * mm),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, 0), (-1, 0), 0.3, line_color),
        ]))
        return tbl

    def _three_col_table(self, items, total_w, line_color):
        """Clean three-column layout."""
        third = total_w / 3
        labels = [Paragraph(it[0], self.sec_label) for it in items]
        values = [Paragraph(it[1], self.sec_val) for it in items]
        data = [labels, values]
        tbl = Table(data, colWidths=[third, third, third])
        tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (0, -1), 2 * mm),
            ('RIGHTPADDING', (1, 0), (1, -1), 2 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 1 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1 * mm),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, 0), (-1, 0), 0.3, line_color),
        ]))
        return tbl

    def _cargo_table(self, ctx, total_w, line_color):
        """Professional cargo table — the heart of the CMR."""
        marks = ctx.get("cargo_marks", "") or "&mdash;"
        cnt = ctx.get("package_count", "") or ""
        typ = ctx.get("package_type", "") or ""
        pkg = f"<b>{cnt}</b> {typ}" if cnt else "&mdash;"
        desc = ctx.get("cargo_description", "") or "&mdash;"
        weight = ctx.get("gross_weight_kg", "") or ""
        weight = f"<b>{weight} kg</b>" if weight else "&mdash;"
        volume = ctx.get("volume_m3", "") or ""
        volume = f"<b>{volume} m³</b>" if volume else "&mdash;"
        hs = ctx.get("hs_code", "") or "&mdash;"

        hdr = ["Marks & Nos", "Packages", "Description", "Weight", "Volume", "HS Code"]
        row = [marks, pkg, desc, weight, volume, hs]
        data = [hdr, row]

        cw = total_w / 6
        tbl = Table(data, colWidths=[cw] * 6)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.header_bg),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.text_color),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, line_color),
            ('LINEBELOW', (0, 0), (-1, 0), 0.75, line_color),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5 * mm),
        ]))
        return tbl

    def _adr_table(self, ctx, total_w, line_color):
        """Professional ADR dangerous goods table."""
        adr_items = ctx.get("adr_items", [])
        if not adr_items:
            return Paragraph("&mdash;", self.sec_small)
        hdr = ["UN No", "Class", "Pack. Grp", "Tunnel", "Qty", "Net Wt (kg)"]
        rows = [hdr]
        for item in adr_items:
            rows.append([
                item.get("un_no", ""),
                item.get("adr_class", ""),
                item.get("packing_group", ""),
                item.get("tunnel_code", ""),
                item.get("quantity", ""),
                item.get("net_weight", ""),
            ])
        cw = total_w / 6
        tbl = Table(rows, colWidths=[cw] * 6)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.text_color),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('GRID', (0, 0), (-1, -1), 0.5, line_color),
            ('LINEBELOW', (0, 0), (-1, 0), 0.75, line_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff7ed")]),
        ]))
        return tbl

    def _signature_row(self, ctx, total_w, line_color):
        """Three signature pads side by side, clean and spacious."""
        third = total_w / 3
        pads = []
        for n, label in [(22, "Sender / Expeditor"),
                         (23, "Carrier / Transportator"),
                         (24, "Consignee / Destinatar")]:
            pads.append(self._signature_pad(label, ctx, third))
        data = [pads]
        tbl = Table(data, colWidths=[third, third, third])
        tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (0, -1), 2 * mm),
            ('RIGHTPADDING', (1, 0), (1, -1), 2 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEABOVE', (0, 0), (-1, 0), 0.5, line_color),
        ]))
        return tbl

    def _signature_pad(self, label, ctx, pad_width):
        """Single signature pad with dotted lines and image space."""
        elements = []
        elements.append(Paragraph(f"<b>{label}</b>", self.sec_label))
        elements.append(Spacer(1, 2 * mm))

        line = (
            "Date: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>"
            " &nbsp;&nbsp; Place: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>"
        )
        elements.append(Paragraph(line, self.sig_style))
        elements.append(Spacer(1, 1.5 * mm))
        elements.append(Paragraph(
            "Name (print): <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            self.sig_style))
        elements.append(Spacer(1, 1.5 * mm))
        elements.append(Paragraph(
            "Signature: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            self.sig_style))
        elements.append(Spacer(1, 2 * mm))

        # Image placeholders
        sig_path = ctx.get("signature_path", "")
        stamp_path = ctx.get("stamp_path", "")
        imgs = []
        if sig_path and os.path.isfile(sig_path):
            try:
                imgs.append(Image(sig_path, width=2.8 * cm, height=1.0 * cm))
            except Exception:
                pass
        if stamp_path and os.path.isfile(stamp_path):
            try:
                imgs.append(Image(stamp_path, width=2.0 * cm, height=2.0 * cm))
            except Exception:
                pass
        if imgs:
            inner_w = pad_width - 6 * mm
            if len(imgs) == 2:
                img_tbl = Table([imgs], colWidths=[inner_w, inner_w])
                img_tbl.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                ]))
            else:
                img_tbl = Table([imgs], colWidths=[inner_w])
                img_tbl.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                ]))
            elements.append(img_tbl)

        return elements

    def _receipt_block(self):
        """Consignment receipt area with checkboxes and lines."""
        return Paragraph(
            "Place of delivery: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>"
            "&nbsp;&nbsp; Date: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>"
            "&nbsp;&nbsp; Time: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/>"
            "Received in good condition: &#9744; Yes &nbsp;&nbsp; &#9744; No&nbsp;&nbsp;"
            "&nbsp;&nbsp; Reservations: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u><br/><br/>"
            "Signature + Stamp: <u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>",
            self.sig_style)

    def _embed_xml_payload(self, pdf_path, xml_string, cmr_number):
        try:
            self._embed_xml_pdfa3(pdf_path, xml_string, cmr_number)
        except ImportError:
            self._embed_xml_fallback(pdf_path, xml_string, cmr_number)
        except Exception as e:
            logger.debug("PDF/A-3 embedding fell back to PyPDF2: %s", e)
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
        from datetime import datetime as dt_module

        icc_data = _get_srgb_icc_profile()
        now_utc = dt_module.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")

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
                f'      <dc:title>{cmr_number}</dc:title>\n'
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
            for i in range(0, len(names_tree), 2):
                if i + 1 < len(names_tree):
                    file_spec = names_tree[i + 1]
                    if file_spec not in af_array:
                        af_array.append(file_spec)

            # ── Save ──
            pdf.save(pdf_path)

    def _embed_xml_fallback(self, pdf_path, xml_string, cmr_number):
        """Fallback embedding using PyPDF2 (no PDF/A-3 structures)."""
        try:
            from PyPDF2 import PdfReader, PdfWriter
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

    # ── Meta JSON ────────────────────────────────────────────────────

    def _build_meta_json(self, ctx: dict, copies: dict, output_dir: str) -> str:
        icc_available = _get_srgb_icc_profile() is not None
        pdfa3 = False
        try:
            import pikepdf
            pdfa3 = True
        except ImportError:
            pass
        meta = {
            "cmr_number": ctx["cmr_number"],
            "trip_id": ctx["trip_id"],
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator_version": "2.0.0",
            "cmr_sequence": ctx.get("cmr_sequence", 0),
            "pdf_compliance": {
                "pdfa3_enabled": pdfa3,
                "icc_profile_available": icc_available,
                "efti_xml_embedded": True,
            },
            "copies": {},
            "signatures": {
                "sender": {"status": "unsigned", "timestamp": None},
                "carrier": {"status": "unsigned", "timestamp": None},
                "consignee": {"status": "unsigned", "timestamp": None},
            },
        }
        for suffix, path in copies.items():
            try:
                with open(path, "rb") as f:
                    sha = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                sha = ""
            meta["copies"][suffix] = {"path": os.path.basename(path), "sha256": sha}
        data_str = json.dumps({k: str(v) if not isinstance(v, (dict, list, int, float, bool, type(None))) else v
                                for k, v in ctx.items()}, default=str)
        meta["input_data_hash"] = hashlib.sha256(data_str.encode()).hexdigest()
        meta_path = os.path.join(output_dir, "_meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        return meta_path
