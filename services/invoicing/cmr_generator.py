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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
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
        self.box_hdr_style = ParagraphStyle(
            "CMRBoxHdr", parent=self.styles["Normal"],
            fontSize=7, leading=8, textColor=colors.HexColor("#333333"),
            fontName="Helvetica-Bold",
        )
        self.box_val_style = ParagraphStyle(
            "CMRBoxVal", parent=self.styles["Normal"],
            fontSize=8, leading=9, textColor=colors.HexColor("#000000"),
        )
        self.box_val_small = ParagraphStyle(
            "CMRBoxValSmall", parent=self.styles["Normal"],
            fontSize=7, leading=8, textColor=colors.HexColor("#000000"),
        )
        self.title_style = ParagraphStyle(
            "CMRTitle", parent=self.styles["Title"],
            fontSize=11, leading=13, textColor=colors.HexColor("#1a73e8"),
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        )
        self.subtitle_style = ParagraphStyle(
            "CMRSubtitle", parent=self.styles["Normal"],
            fontSize=7, leading=8, textColor=colors.HexColor("#666666"),
            alignment=TA_CENTER,
        )
        self.sig_label = ParagraphStyle(
            "CMRSig", parent=self.styles["Normal"],
            fontSize=7, leading=8, textColor=colors.HexColor("#444444"),
            fontName="Helvetica-Bold",
        )
        self.sig_val = ParagraphStyle(
            "CMRSigVal", parent=self.styles["Normal"],
            fontSize=7, leading=10, textColor=colors.HexColor("#000000"),
        )

    def _safe_str(self, val) -> str:
        if val is None:
            return ""
        return str(val)

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
            topMargin=8 * mm, bottomMargin=8 * mm,
            title=f"{cmr_number} - {suffix} Copy",
            author="Operion ERP",
            subject=f"eCMR {cmr_number}",
        )

        story = []
        story.extend(self._build_page1(ctx, color_hex, color_light, bar_text, desig_text))
        story.append(PageBreak())
        story.extend(self._build_page2(ctx, color_hex, color_light, bar_text, desig_text))

        doc.build(story)

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

    def _build_page1(self, ctx, color_hex, color_light, bar_text, desig_text):
        story = []

        # Top color bar
        story.append(self._color_bar(color_hex, bar_text))
        story.append(Spacer(1, 2 * mm))

        # Title
        story.append(Paragraph(
            "<b>CMR &mdash; INTERNATIONAL CONSIGNMENT NOTE</b>", self.title_style))
        story.append(Paragraph(
            "Convention on the Contract for the International Carriage of Goods by Road"
            " (Geneva, 19 May 1956) &mdash; UN/ADR", self.subtitle_style))
        story.append(Paragraph(
            f"<b>CMR No:</b> {ctx['cmr_number']} &nbsp;|&nbsp;"
            f"Trip: #{ctx['trip_id']} &nbsp;|&nbsp;"
            f"Date: {datetime.now().strftime('%d/%m/%Y')}",
            self.box_val_small))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(color_hex)))
        story.append(Spacer(1, 2 * mm))

        # Row 1: Box 1 (Consignor) | Box 2 (Consignee)
        story.append(self._build_two_box_row(1, "box_1", 2, "box_2",
            self._consignor_content(ctx), self._consignee_content(ctx),
            color_hex, same_height=True))

        story.append(Spacer(1, 1 * mm))

        # Row 2: Box 3 (Place of taking over) | Box 4 (Place of delivery)
        story.append(self._build_two_box_row(3, "box_3", 4, "box_4",
            self._loading_content(ctx), self._delivery_content(ctx),
            color_hex, same_height=True))

        story.append(Spacer(1, 1 * mm))

        # Row 3: Box 5 (Documents) | Box 6 (Marks) | Box 7 (Packages) | Box 8 (Goods)
        story.append(self._build_four_box_row(
            (5, "box_5", self._doc_attached_content(ctx)),
            (6, "box_6", self._marks_content(ctx)),
            (7, "box_7", self._packages_content(ctx)),
            (8, "box_8", self._cargo_content(ctx)),
            color_hex, same_height=True))

        story.append(Spacer(1, 1 * mm))

        # Row 4: Box 9 (HS Code) | Box 10 (Weight) | Box 11 (Volume)
        story.append(self._build_three_box_row(
            (9, "box_9", self._hs_code_content(ctx)),
            (10, "box_10", self._weight_content(ctx)),
            (11, "box_11", self._volume_content(ctx)),
            color_hex, same_height=True))

        # Bottom color bar + designation
        story.append(Spacer(1, 2 * mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(color_hex)))
        story.append(self._designation_footer(color_hex, desig_text, ctx["cmr_number"]))

        return story

    def _build_page2(self, ctx, color_hex, color_light, bar_text, desig_text):
        story = []

        # Top color bar
        story.append(self._color_bar(color_hex, bar_text))
        story.append(Spacer(1, 2 * mm))

        # Row 5: Box 12 (Instructions) | Box 13 (Reservations)
        story.append(self._build_two_box_row(12, "box_12", 13, "box_13",
            self._instructions_content(ctx), self._reservations_content(ctx),
            color_hex, same_height=True))

        story.append(Spacer(1, 1 * mm))

        # Row 6: Box 14 (Special agreements) | Box 15 (Carriage charges)
        story.append(self._build_two_box_row(14, "box_14", 15, "box_15",
            self._agreements_content(ctx), self._charges_content(ctx),
            color_hex, same_height=True))

        story.append(Spacer(1, 1 * mm))

        # Row 7: Box 16 (Carrier full details)
        story.append(self._build_single_box(16, "box_16",
            self._carrier_content(ctx), color_hex))

        story.append(Spacer(1, 1 * mm))

        # Row 8: Box 17 (Successive carriers)
        if ctx.get("successive_carriers"):
            story.append(self._build_single_box(17, "box_17",
                self._successive_carriers_content(ctx), color_hex))
            story.append(Spacer(1, 1 * mm))

        # Row 9: Boxes 18 (Vehicle) | 19 (Trailer) | 20 (Driver)
        story.append(self._build_three_box_row(
            (18, "box_18", self._vehicle_content(ctx)),
            (19, "box_19", self._trailer_content(ctx)),
            (20, "box_20", self._driver_content(ctx)),
            color_hex, same_height=True))

        story.append(Spacer(1, 1 * mm))

        # Row 10: Box 21 (ADR) - conditional
        if ctx.get("has_adr"):
            story.append(self._build_adr_box(ctx, color_hex))
            story.append(Spacer(1, 1 * mm))

        # Row 11: Boxes 22-24 (Signatures)
        story.append(self._build_signature_row(ctx, color_hex))
        story.append(Spacer(1, 1 * mm))

        # Row 12: Box 25 (Consignment received)
        story.append(self._build_single_box(25, "box_25",
            self._received_content(ctx), color_hex))

        # Footer
        story.append(Spacer(1, 3 * mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(color_hex)))
        story.append(Paragraph(
            f"Generated by Operion ERP | {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
            f"CMR {ctx['cmr_number']} | {desig_text}",
            self.subtitle_style))
        story.append(self._color_bar(color_hex, bar_text))

        return story

    # ── Box Content Helpers ──────────────────────────────────────────

    def _consignor_content(self, ctx):
        lines = [
            f"<b>{ctx.get('company_name', '')}</b>",
            ctx.get("company_address", ""),
        ]
        cui = ctx.get("company_cui", "")
        if cui:
            lines.append(f"VAT/CUI: {cui}")
        eori = ctx.get("eori_number", "")
        if eori:
            lines.append(f"EORI: {eori}")
        phone = ctx.get("company_phone", "")
        if phone:
            lines.append(f"Tel: {phone}")
        return Paragraph("<br/>".join(lines), self.box_val_small)

    def _consignee_content(self, ctx):
        lines = [
            f"<b>{ctx.get('client_name', '')}</b>",
            ctx.get("client_address", ""),
        ]
        vat = ctx.get("consignee_vat", "")
        if vat:
            lines.append(f"VAT: {vat}")
        eori = ctx.get("consignee_eori", "")
        if eori:
            lines.append(f"EORI: {eori}")
        contact = ctx.get("consignee_contact", "")
        if contact:
            lines.append(f"Contact: {contact}")
        return Paragraph("<br/>".join(lines), self.box_val_small)

    def _loading_content(self, ctx):
        addr = ctx.get("place_of_loading", "")
        country = ctx.get("loading_country", "")
        date = ctx.get("place_of_loading_date", "")
        lines = [addr]
        if country:
            lines.append(f"Country: {country}")
        if date:
            lines.append(f"Date: {date}")
        return Paragraph("<br/>".join(lines), self.box_val_small)

    def _delivery_content(self, ctx):
        addr = ctx.get("place_of_delivery", "")
        country = ctx.get("delivery_country", "")
        lines = [addr]
        if country:
            lines.append(f"Country: {country}")
        return Paragraph("<br/>".join(lines), self.box_val_small)

    def _doc_attached_content(self, ctx):
        val = ctx.get("documents_attached", "")
        return Paragraph(val or "&mdash;", self.box_val_small)

    def _marks_content(self, ctx):
        val = ctx.get("cargo_marks", "")
        return Paragraph(val or "&mdash;", self.box_val_small)

    def _packages_content(self, ctx):
        cnt = ctx.get("package_count", "")
        typ = ctx.get("package_type", "")
        lines = []
        if cnt:
            lines.append(f"<b>{cnt}</b>")
        if typ:
            lines.append(typ)
        if not lines:
            lines.append("&mdash;")
        return Paragraph("<br/>".join(lines), self.box_val_small)

    def _cargo_content(self, ctx):
        val = ctx.get("cargo_description", "")
        return Paragraph(val or "&mdash;", self.box_val_small)

    def _hs_code_content(self, ctx):
        val = ctx.get("hs_code", "")
        return Paragraph(val or "&mdash;", self.box_val_small)

    def _weight_content(self, ctx):
        val = ctx.get("gross_weight_kg", "")
        return Paragraph(f"<b>{val} kg</b>" if val else "&mdash;", self.box_val_small)

    def _volume_content(self, ctx):
        val = ctx.get("volume_m3", "")
        return Paragraph(f"<b>{val} m\\u00B3</b>" if val else "&mdash;", self.box_val_small)

    def _instructions_content(self, ctx):
        val = ctx.get("carrier_instructions", "")
        return Paragraph(val or "None", self.box_val_small)

    def _reservations_content(self, ctx):
        val = ctx.get("carrier_reservations", "")
        return Paragraph(val or "None", self.box_val_small)

    def _agreements_content(self, ctx):
        val = ctx.get("special_agreements", "")
        return Paragraph(val or "None", self.box_val_small)

    def _charges_content(self, ctx):
        payer = ctx.get("carriage_payer", "")
        if payer == "sender":
            text = "Sender pays / Expeditorul plateste"
        elif payer == "consignee":
            text = "Consignee pays / Destinatarul plateste"
        else:
            text = "&mdash;"
        dist = ctx.get("distance_km", "")
        if dist:
            text += f"<br/>Distance: {dist} km"
        return Paragraph(text, self.box_val_small)

    def _carrier_content(self, ctx):
        lines = [
            f"<b>{ctx.get('company_name', '')}</b>",
            ctx.get("company_address", ""),
        ]
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
        return Paragraph("<br/>".join(lines), self.box_val_small)

    def _successive_carriers_content(self, ctx):
        carriers = ctx.get("successive_carriers", [])
        if not carriers:
            return Paragraph("None", self.box_val_small)
        rows = []
        for i, c in enumerate(carriers):
            rows.append(
                f"{i + 1}. <b>{c.get('carrier_name', '')}</b><br/>"
                f"&nbsp;&nbsp;&nbsp;{c.get('carrier_address', '')}<br/>"
                f"&nbsp;&nbsp;&nbsp;Plate: {c.get('vehicle_plate', '')} | "
                f"Driver: {c.get('driver_name', '')}<br/>"
                f"&nbsp;&nbsp;&nbsp;From: {c.get('from_location', '')} → "
                f"To: {c.get('to_location', '')}"
            )
        return Paragraph("<br/>".join(rows), self.box_val_small)

    def _vehicle_content(self, ctx):
        plate = ctx.get("truck_plate", "")
        return Paragraph(f"<b>{plate}</b>" if plate else "&mdash;", self.box_val_small)

    def _trailer_content(self, ctx):
        plate = ctx.get("trailer_plate", "")
        return Paragraph(f"<b>{plate}</b>" if plate else "&mdash;", self.box_val_small)

    def _driver_content(self, ctx):
        lines = []
        name = ctx.get("driver_name", "")
        lic = ctx.get("driver_license", "")
        if name:
            lines.append(f"<b>{name}</b>")
        if lic:
            lines.append(f"License: {lic}")
        if not lines:
            lines.append("&mdash;")
        return Paragraph("<br/>".join(lines), self.box_val_small)

    def _received_content(self, ctx):
        return Paragraph(
            "Place of delivery: _________________________<br/>"
            "Date: ___/___/______ &nbsp; Time: ___:___<br/>"
            "Received in good condition: &#9744; Yes &nbsp; &#9744; No<br/>"
            "Reservations: ____________________________________________<br/><br/>"
            "Signature + Stamp: [&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;]",
            self.box_val_small)

    # ── Layout Helpers ──────────────────────────────────────────────

    def _color_bar(self, color_hex, text):
        color = colors.HexColor(color_hex)
        bar = Table(
            [[Paragraph(f"<b>{text}</b>",
             ParagraphStyle("BarText", fontSize=8, leading=9,
                            textColor=colors.white, fontName="Helvetica-Bold",
                            alignment=TA_CENTER))]],
            colWidths=[A4[0] - 20 * mm],
            rowHeights=[6 * mm],
        )
        bar.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return bar

    def _designation_footer(self, color_hex, desig_text, cmr_number):
        color = colors.HexColor(color_hex)
        data = [[Paragraph(
            f"<b>{desig_text}</b><br/>"
            f"<font size=7>CMR Ref: {cmr_number} | Operion ERP</font>",
            ParagraphStyle("Desig", fontSize=7, leading=9,
                           textColor=colors.HexColor("#444444"),
                           alignment=TA_CENTER))]]
        tbl = Table(data, colWidths=[A4[0] - 20 * mm], rowHeights=[10 * mm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f5f5f5")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 0.5, color),
            ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
        ]))
        return tbl

    def _box_header(self, number, label_key, color_hex):
        label = BOX_LABELS.get(label_key, label_key)
        return Paragraph(
            f"<font size=7 color='{color_hex}'><b>{number}.</b></font> "
            f"<font size=7><b>{label}</b></font>",
            self.box_hdr_style)

    def _box_frame(self, content, color_hex):
        data = [[content]]
        tbl = Table(data, colWidths=[A4[0] - 20 * mm - 2 * mm])
        tbl.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor(color_hex)),
            ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 1 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1 * mm),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return tbl

    def _build_single_box(self, number, label_key, content, color_hex):
        header = self._box_header(number, label_key, color_hex)
        body = self._box_frame(content, color_hex)
        data = [[header], [body]]
        tbl = Table(data, colWidths=[A4[0] - 20 * mm])
        tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return tbl

    def _build_two_box_row(self, n1, l1, n2, l2, c1, c2, color_hex, same_height=False):
        h1 = self._box_header(n1, l1, color_hex)
        b1 = self._box_frame(c1, color_hex)
        h2 = self._box_header(n2, l2, color_hex)
        b2 = self._box_frame(c2, color_hex)
        half = (A4[0] - 20 * mm) / 2
        data = [[[h1, b1], [h2, b2]]]
        inner_tbl = Table(data, colWidths=[half, half])
        inner_tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (1, 0), (1, 0), 1 * mm),
        ]))
        return inner_tbl

    def _build_three_box_row(self, b1, b2, b3, color_hex, same_height=False):
        third = (A4[0] - 20 * mm) / 3
        boxes = []
        for n, label_key, content in (b1, b2, b3):
            h = self._box_header(n, label_key, color_hex)
            b = self._box_frame(content, color_hex)
            boxes.append([h, b])
        data = [boxes]
        inner_tbl = Table(data, colWidths=[third, third, third])
        inner_tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (1, 0), (1, 0), 0.5 * mm),
            ('LEFTPADDING', (2, 0), (2, 0), 0.5 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return inner_tbl

    def _build_four_box_row(self, b1, b2, b3, b4, color_hex, same_height=False):
        quarter = (A4[0] - 20 * mm) / 4
        boxes = []
        for n, label_key, content in (b1, b2, b3, b4):
            h = self._box_header(n, label_key, color_hex)
            b = self._box_frame(content, color_hex)
            boxes.append([h, b])
        data = [boxes]
        inner_tbl = Table(data, colWidths=[quarter, quarter, quarter, quarter])
        inner_tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return inner_tbl

    def _build_signature_row(self, ctx, color_hex):
        third = (A4[0] - 20 * mm) / 3
        sig_boxes = []
        for n, label_key in [(22, "box_22"), (23, "box_23"), (24, "box_24")]:
            content = self._signature_block(ctx, n, label_key)
            h = self._box_header(n, label_key, color_hex)
            b = self._box_frame(content, color_hex)
            sig_boxes.append([h, b])

        data = [sig_boxes]
        inner = Table(data, colWidths=[third, third, third])
        inner.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        return inner

    def _signature_block(self, ctx, number, label_key):
        parts = [
            "<b>Date:</b> ___/___/______",
            "<b>Place:</b> ______________________",
            "<b>Name (print):</b> ______________________",
            "<b>Signature:</b> _______________________",
        ]
        body_text = "<br/>".join(parts)

        sig_path = ctx.get("signature_path", "")
        stamp_path = ctx.get("stamp_path", "")
        img_elements = []
        if sig_path and os.path.isfile(sig_path):
            try:
                img_elements.append(Image(sig_path, width=3.5 * cm, height=1.3 * cm))
            except Exception:
                img_elements.append(Paragraph("[Signature]", self.box_val_small))
        if stamp_path and os.path.isfile(stamp_path):
            try:
                img_elements.append(Image(stamp_path, width=2.5 * cm, height=2.5 * cm))
            except Exception:
                pass

        elements = [Paragraph(body_text, self.box_val_small)]
        if img_elements:
            elements.append(Spacer(1, 1 * mm))
            img_col_widths = []
            if len(img_elements) == 2:
                img_col_widths = [(A4[0] - 20 * mm) / 3 - 8 * mm] * 2
                img_tbl = Table([img_elements], colWidths=img_col_widths)
                img_tbl.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                ]))
            else:
                img_col_widths = [(A4[0] - 20 * mm) / 3 - 4 * mm]
                img_tbl = Table([img_elements], colWidths=img_col_widths)
                img_tbl.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                ]))
            elements.append(img_tbl)

        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(
            "<i>Digital: [ Click to Sign | Timestamp: ____________ ]</i>",
            self.box_val_small))

        return elements if len(elements) > 1 else elements[0]

    def _build_adr_box(self, ctx, color_hex):
        header = self._box_header(21, "box_21", color_hex)
        adr_items = ctx.get("adr_items", [])
        if not adr_items:
            body = self._box_frame(Paragraph("&mdash;", self.box_val_small), color_hex)
            return self._wrap_box(header, body)

        adr_header = ["UN No", "Class", "Packing Grp", "Tunnel Code", "Qty", "Net Wt(kg)"]
        adr_rows = [adr_header]
        for item in adr_items:
            adr_rows.append([
                item.get("un_no", ""),
                item.get("adr_class", ""),
                item.get("packing_group", ""),
                item.get("tunnel_code", ""),
                item.get("quantity", ""),
                item.get("net_weight", ""),
            ])
        col_w = (A4[0] - 20 * mm - 4 * mm) / 6
        tbl = Table(adr_rows, colWidths=[col_w] * 6)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(color_hex)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor(color_hex)),
            ('FONTSIZE', (0, 0), (-1, -1), 6),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff3e0")]),
        ]))
        body = self._box_frame(tbl, color_hex)
        return self._wrap_box(header, body)

    def _wrap_box(self, header, body):
        data = [[header], [body]]
        tbl = Table(data, colWidths=[A4[0] - 20 * mm])
        tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return tbl

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
