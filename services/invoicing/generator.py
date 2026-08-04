from __future__ import annotations

import logging
import os
from datetime import datetime

from reportlab.lib import colors

logger = logging.getLogger(__name__)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.i18n import _get_translations, t
from utils.helpers import remove_accents
from utils.resource_path import data_path

from .config_manager import load_company_config

class InvoiceGenerator:
    def __init__(self):
        self.reports_dir = data_path("invoices")
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
        self.styles = getSampleStyleSheet()

    def _tr(self, key: str, mode: str) -> str:
        """Translate key: client mode always uses English, internal uses current app language."""
        if mode == "client":
            result = _get_translations("en").get(key, key)
            return str(result) if result is not None else key
        return t(key)

    def generate(self, trip_data, mode="client"):
        conf = load_company_config()
        trip_id = trip_data.get("id", 0)
        try:
            trip_id_int = int(trip_id)
        except (TypeError, ValueError):
            trip_id_int = 1
        trip_year = str(trip_data.get("created_at", ""))[:4]
        inv_year = trip_year if trip_year and trip_year.isdigit() else datetime.now().year
        invoice_id = f"INV-{inv_year}-{trip_id_int:04d}"
        filename = f"{invoice_id}_{mode}.pdf"
        full_path = os.path.join(self.reports_dir, filename)

        client_name = trip_data.get("client_name", "")
        total_price = trip_data.get("total_price_eur", 0)
        logger.info("Generating invoice PDF: invoice_id=%s, client=%s, total=%s, mode=%s",
                    invoice_id, client_name, total_price, mode)

        doc = SimpleDocTemplate(full_path, pagesize=A4,
                                leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)
        story = []

        title_text = self._tr("invoice_pdf.title_client", mode) if mode == "client" else self._tr("invoice_pdf.title_internal", mode)
        title_style = ParagraphStyle("InvTitle", parent=self.styles["Title"], fontSize=18, textColor=colors.HexColor("#1a73e8"), alignment=0)

        story.append(Paragraph(f"<b>{title_text}</b>", title_style))
        story.append(Paragraph(self._tr("invoice_pdf.serial", mode).format(invoice_id, datetime.now().strftime('%d/%m/%Y')), self.styles["Normal"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a73e8"), spaceAfter=15))

        company_info = (f"<b>{self._tr('invoice_pdf.sender_header', mode)}</b><br/>"
                        f"{remove_accents(conf.get('company_name', ''))}<br/>"
                        f"CUI: {conf.get('cui', '')}<br/>"
                        f"Reg. Com: {conf.get('reg_number', '')}<br/>"
                        f"Adresa: {remove_accents(conf.get('address', ''))}<br/>"
                        f"Judet: {conf.get('county', '')} Oras: {conf.get('city', '')}<br/>"
                        f"Tel: {conf.get('phone', '')}")
        iban = conf.get("iban", "")
        bank = conf.get("bank_name", "")
        if iban:
            company_info += f"<br/>IBAN: {iban}"
        if bank:
            company_info += f"<br/>Banca: {remove_accents(bank)}"

        client_info = (f"<b>{self._tr('invoice_pdf.bill_to_header', mode)}</b><br/>"
                       f"{remove_accents(trip_data.get('client_name', ''))}")
        client_vat = trip_data.get("client_vat")
        client_address = trip_data.get("client_address")
        client_phone = trip_data.get("client_phone")
        client_email = trip_data.get("client_email")
        if client_vat:
            client_info += f"<br/>VAT: {client_vat}"
        if client_address:
            client_info += f"<br/>{remove_accents(client_address)}"
        if client_phone:
            client_info += f"<br/>Tel: {client_phone}"
        if client_email:
            client_info += f"<br/>Email: {client_email}"

        info_table = Table([[Paragraph(company_info, self.styles["Normal"]),
                             Paragraph(client_info, self.styles["Normal"])]], colWidths=[9.5*cm, 8.5*cm])
        story.append(info_table)
        story.append(Spacer(1, 1*cm))

        story.append(Paragraph(f"<b>{self._tr('invoice_pdf.trip_info', mode)}</b>", self.styles["Normal"]))
        tech_data = [
            [self._tr("invoice_pdf.truck", mode), self._tr("invoice_pdf.driver", mode), self._tr("invoice_pdf.distance", mode), self._tr("invoice_pdf.start_date", mode), self._tr("invoice_pdf.end_date", mode)],
            [trip_data.get("truck_number", ""), remove_accents(trip_data.get("driver_name", "")),
             f"{trip_data.get('distance_km', 0)} km", trip_data.get("start_date", ""), trip_data.get("end_date", "")]
        ]
        tech_table = Table(tech_data, colWidths=[3.6*cm]*5)
        tech_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f0f4ff")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
        ]))
        story.append(tech_table)
        story.append(Spacer(1, 1*cm))

        story.append(Paragraph(f"<b>{self._tr('invoice_pdf.financials', mode)}</b>", self.styles["Normal"]))

        if mode == "internal":
            fin_data = [
                [self._tr("invoice_pdf.desc_header", mode), self._tr("invoice_pdf.amount_header", mode)],
                [self._tr("invoice_pdf.line_gross", mode), f"{trip_data.get('total_price_eur', 0):.2f}"],
                [self._tr("invoice_pdf.line_fuel", mode), f"- {trip_data.get('fuel_cost', 0):.2f}"],
                [self._tr("invoice_pdf.line_tolls", mode), f"- {trip_data.get('toll_cost', 0):.2f}"],
                [self._tr("invoice_pdf.line_salary", mode), f"- {trip_data.get('salary_cost', 0):.2f}"],
                [self._tr("invoice_pdf.line_other", mode), f"- {trip_data.get('extra_costs', 0):.2f}"],
                [Paragraph(f"<b>{self._tr('invoice_pdf.net_profit', mode)}</b>", self.styles["Normal"]),
                 Paragraph(f"<b>{trip_data.get('net_profit', 0):.2f} {trip_data.get('currency', 'EUR')}</b>", self.styles["Normal"])]
            ]
        else:
            fin_data = [
                [self._tr("invoice_pdf.desc_header", mode), self._tr("invoice_pdf.qty_header", mode), self._tr("invoice_pdf.total_header", mode)],
                [self._tr("invoice_pdf.service_desc", mode).format(trip_data.get('distance_km', 0)),
                 "1",
                 Paragraph(f"<b>{trip_data.get('total_price_eur', 0):.2f} {trip_data.get('currency', 'EUR')}</b>", self.styles["Normal"])]
            ]

        fin_col_widths = [13*cm, 5*cm] if mode == "internal" else [10*cm, 2*cm, 6*cm]
        fin_table = Table(fin_data, colWidths=fin_col_widths)
        fin_table.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,0), 1, colors.black),
            ('ALIGN', (-1,1), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        if mode == "internal":
            fin_table.setStyle(TableStyle([('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#e8f0fe"))]))

        story.append(fin_table)

        story.append(Spacer(1, 1*cm))

            # Payment instructions
        iban = conf.get("iban", "")
        bank = conf.get("bank_name", "")
        if iban:
            pay_info = f"<b>Plata:</b> IBAN {iban}"
            if bank:
                pay_info += f" — {remove_accents(bank)}"
            pay_style = ParagraphStyle("PayInfo", parent=self.styles["Normal"],
                                       fontSize=9, textColor=colors.HexColor("#333333"))
            story.append(Paragraph(pay_info, pay_style))
            story.append(Spacer(1, 0.3*cm))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        footer_msg = f"Email: {conf.get('email', '')} | Tel: {conf.get('phone', '')}"
        story.append(Paragraph(remove_accents(footer_msg), self.styles["Italic"]))
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(self._tr("invoice_pdf.footer", mode), self.styles["Italic"]))

        doc.build(story)
        logger.info("Invoice PDF generated successfully: path=%s, invoice_id=%s", full_path, invoice_id)
        return full_path

    def _draw_watermark(self, canvas, doc, text="PROFORMA"):
        """Draw a light diagonal watermark across each page."""
        from reportlab.lib import colors as rl_colors
        canvas.saveState()
        canvas.setFont("Helvetica", 80)
        canvas.setFillColor(rl_colors.Color(0.85, 0.85, 0.85, alpha=0.35))
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, text)
        canvas.restoreState()

    def generate_rich(self, invoice_data, document_type="invoice"):
        """Generate a rich invoice PDF with line items, tax, discount, notes, and branding.

        invoice_data dict with keys: invoice_number, issue_date, due_date, payment_terms,
        currency, company, client, line_items, tax_rate, discount_type, discount_value,
        subtotal, total_tax, discount, grand_total, notes, logo_path, signature_path,
        stamp_path, company_color, mode.

        document_type: "invoice" (default) or "proforma".
        """
        conf = invoice_data.get("company", load_company_config())
        client = invoice_data.get("client", {})
        addon_items = invoice_data.get("addon_items", [])
        if not addon_items:
            addon_items = invoice_data.get("line_items", [])
        currency = invoice_data.get("currency", "EUR")
        company_color_hex = invoice_data.get("company_color", "#1a73e8")
        mode = invoice_data.get("mode", "client")

        # Internal mode: use _tr for translated titles; client mode: English
        if mode == "internal":
            mode_title = self._tr("invoice_pdf.title_internal", mode)
        else:
            mode_title = self._tr("invoice_pdf.title_client", mode)

        try:
            company_color = colors.HexColor(company_color_hex)
        except Exception:
            company_color = colors.HexColor("#1a73e8")

        invoice_id = invoice_data.get("invoice_number", f"INV-{datetime.now().year}-0001")
        if invoice_id.startswith(("INV-", "PROF-")):
            invoice_id = f"{invoice_id}_{datetime.now().strftime('%H%M%S%f')}"
        filename = f"{invoice_id}_{mode}.pdf"
        full_path = os.path.join(self.reports_dir, filename)

        client_name = client.get("name", "")
        grand_total = invoice_data.get("grand_total", 0)
        logger.info("Generating rich invoice PDF: invoice_id=%s, client=%s, grand_total=%s, mode=%s, document_type=%s",
                    invoice_id, client_name, grand_total, mode, document_type)

        try:
            doc = SimpleDocTemplate(full_path, pagesize=A4,
                                    leftMargin=1.5*cm, rightMargin=1.5*cm,
                                    topMargin=1.5*cm, bottomMargin=1.5*cm)
            story = []

            is_proforma = document_type == "proforma"

            # ── HEADER ──────────────────────────────────────────────────
            if is_proforma:
                title_text = "PROFORMA INVOICE"
            else:
                title_text = mode_title
            title_style = ParagraphStyle("InvTitle", parent=self.styles["Title"],
                                         fontSize=22, textColor=company_color, alignment=2)
            story.append(Paragraph(f"<b>{title_text}</b>", title_style))
            story.append(Spacer(1, 0.3*cm))

            # Proforma number and dates
            if is_proforma:
                valid_until = invoice_data.get("valid_until", invoice_data.get("due_date", ""))
                header_info = (
                    f"<b>Proforma #:</b> {invoice_id}<br/>"
                    f"<b>Date:</b> {invoice_data.get('issue_date', '')}<br/>"
                    f"<b>Valid Until:</b> {valid_until}<br/>"
                    f"<b>Payment Terms:</b> {invoice_data.get('payment_terms', 'Net 30')}"
                )
            else:
                header_info = (
                    f"<b>Invoice #:</b> {invoice_id}<br/>"
                    f"<b>Date:</b> {invoice_data.get('issue_date', '')}<br/>"
                    f"<b>Due Date:</b> {invoice_data.get('due_date', '')}<br/>"
                    f"<b>Payment Terms:</b> {invoice_data.get('payment_terms', 'Net 30')}"
                )
            header_style = ParagraphStyle("InvHeader", parent=self.styles["Normal"],
                                          fontSize=9, alignment=2)
            story.append(Paragraph(header_info, header_style))
            story.append(HRFlowable(width="100%", thickness=1.5,
                                    color=company_color, spaceAfter=12))

            # ── FROM / BILL TO ──────────────────────────────────────────
            iban = conf.get("iban", "")
            bank = conf.get("bank_name", "")
            company_info = (
                f"<b>FROM:</b><br/>"
                f"{remove_accents(conf.get('company_name', ''))}<br/>"
                f"CUI: {conf.get('cui', '')}<br/>"
                f"Reg. Com: {conf.get('reg_number', '')}<br/>"
                f"{remove_accents(conf.get('address', ''))}<br/>"
                f"Judet: {conf.get('county', '')}, Oras: {conf.get('city', '')}<br/>"
                f"Tel: {conf.get('phone', '')}<br/>"
                f"Email: {conf.get('email', '')}"
            )
            if iban:
                company_info += f"<br/>IBAN: {iban}"
            if bank:
                company_info += f"<br/>Banca: {remove_accents(bank)}"

            client_info = (
                f"<b>BILL TO:</b><br/>"
                f"{remove_accents(client.get('name', ''))}"
            )
            if client.get("vat_number"):
                client_info += f"<br/>VAT: {client.get('vat_number')}"
            if client.get("address"):
                client_info += f"<br/>{remove_accents(client.get('address', ''))}"
            if client.get("phone"):
                client_info += f"<br/>Tel: {client.get('phone')}"
            if client.get("email"):
                client_info += f"<br/>Email: {client.get('email')}"

            # Logo handling
            logo_path = invoice_data.get("logo_path", "")
            if logo_path and os.path.isfile(logo_path):
                try:
                    from reportlab.platypus import Image
                    logo_img = Image(logo_path, width=2.5*cm, height=2.5*cm)
                    logo_img.hAlign = 'LEFT'
                    story.append(logo_img)
                    story.append(Spacer(1, 0.3*cm))
                except Exception:
                    pass

            info_table_data = [
                [Paragraph(company_info, self.styles["Normal"]),
                 Paragraph(client_info, self.styles["Normal"])]
            ]
            info_table = Table(info_table_data, colWidths=[9*cm, 9*cm])
            info_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(info_table)
            story.append(Spacer(1, 0.6*cm))

            # ── TRIP DETAILS ─────────────────────────────────────────────
            loading_stops = invoice_data.get("loading_stops", [])
            unloading_stops = invoice_data.get("unloading_stops", [])
            distance = invoice_data.get("distance", "")
            truck = invoice_data.get("truck_plate", "")
            driver = invoice_data.get("driver_name", "")

            has_stops = loading_stops or unloading_stops
            if has_stops or any([distance, truck, driver]):
                story.append(Paragraph("<b>TRIP DETAILS</b>", self.styles["Normal"]))
                trip_rows = []
                if loading_stops:
                    for i, stop in enumerate(loading_stops):
                        trip_rows.append(
                            [Paragraph(f"<b>Loading {i+1}:</b>", self.styles["Normal"]),
                             Paragraph(remove_accents(stop), self.styles["Normal"])])
                if unloading_stops:
                    for i, stop in enumerate(unloading_stops):
                        trip_rows.append(
                            [Paragraph(f"<b>Unloading {i+1}:</b>", self.styles["Normal"]),
                             Paragraph(remove_accents(stop), self.styles["Normal"])])
                if distance:
                    trip_rows.append(
                        [Paragraph("<b>Distance:</b>", self.styles["Normal"]),
                         Paragraph(str(distance), self.styles["Normal"])])
                if truck:
                    trip_rows.append(
                        [Paragraph("<b>Truck:</b>", self.styles["Normal"]),
                         Paragraph(str(truck), self.styles["Normal"])])
                if driver:
                    trip_rows.append(
                        [Paragraph("<b>Driver:</b>", self.styles["Normal"]),
                         Paragraph(remove_accents(str(driver)), self.styles["Normal"])])
                if trip_rows:
                    trip_table = Table(trip_rows, colWidths=[3*cm, 15*cm])
                    trip_table.setStyle(TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('TOPPADDING', (0, 0), (-1, -1), 2),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ]))
                    story.append(trip_table)
                story.append(Spacer(1, 0.6*cm))

            # ── DESCRIPTION ──────────────────────────────────────────────
            description = invoice_data.get("description", "")
            if description and description.strip():
                story.append(Paragraph("<b>Description:</b>", self.styles["Normal"]))
                story.append(Paragraph(remove_accents(description), self.styles["Normal"]))
                story.append(Spacer(1, 0.6*cm))

            # ── ADDON ITEMS TABLE ────────────────────────────────────────
            trip_price = invoice_data.get("trip_price", 0)
            price_pre_vat = invoice_data.get("price_pre_vat")
            vat_percent = invoice_data.get("vat_percent")

            # Trip price line
            price_data = [
                [Paragraph("<b>Item</b>", self.styles["Normal"]),
                 Paragraph("<b>Amount</b>", self.styles["Normal"])],
            ]

            if price_pre_vat is not None and vat_percent is not None:
                price_pre_val = float(price_pre_vat)
                trip_price_val = float(trip_price)
                if price_pre_val > trip_price_val:
                    raise ValueError(
                        f"price_pre_vat ({price_pre_val:.2f}) exceeds trip_price ({trip_price_val:.2f})"
                    )
                vat_rate = float(vat_percent) / 100.0
                expected_vat = round(price_pre_val * vat_rate, 2)
                actual_vat = round(trip_price_val - price_pre_val, 2)
                if abs(expected_vat - actual_vat) > 0.05:
                    logger.warning(
                        "VAT rounding discrepancy: expected %.2f at %s%% "
                        "but got %.2f (trip=%.2f, base=%.2f) — proceeding",
                        expected_vat, vat_percent, actual_vat, trip_price_val, price_pre_val,
                    )
                price_data.append([
                    Paragraph(f"Transport fee (excl. VAT {vat_percent}%)", self.styles["Normal"]),
                    Paragraph(f"{price_pre_val:,.2f} {currency}", self.styles["Normal"])])
                price_data.append([
                    Paragraph(f"VAT {vat_percent}%", self.styles["Normal"]),
                    Paragraph(f"{trip_price_val - price_pre_val:,.2f} {currency}", self.styles["Normal"])])
                price_data.append([
                    Paragraph("<b>Transport fee (incl. VAT)</b>", self.styles["Normal"]),
                    Paragraph(f"<b>{trip_price_val:,.2f} {currency}</b>", self.styles["Normal"])])
            else:
                price_data.append([
                    Paragraph("Transport fee", self.styles["Normal"]),
                    Paragraph(f"{float(trip_price):,.2f} {currency}", self.styles["Normal"])])

            # Addon items
            for ai in addon_items:
                desc = ai.get("description", "Additional")
                amt = ai.get("amount", 0) or ai.get("total", 0)
                price_data.append([
                    Paragraph(remove_accents(str(desc)), self.styles["Normal"]),
                    Paragraph(f"{float(amt):,.2f} {currency}", self.styles["Normal"])])

            price_table = Table(price_data, colWidths=[13*cm, 5*cm])
            price_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f0f4ff")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(price_table)
            story.append(Spacer(1, 0.6*cm))

            # ── INTERNAL MODE: COST BREAKDOWN ─────────────────────────────
            if mode == "internal":
                trip_data = invoice_data.get("trip_data") or {}
                gross = float(trip_data.get("total_price_eur", 0) or 0)
                fuel = float(trip_data.get("fuel_cost", 0) or 0)
                tolls = float(trip_data.get("toll_cost", 0) or 0)
                salary = float(trip_data.get("salary_cost", 0) or 0)
                extra = float(trip_data.get("extra_costs", 0) or 0)
                net = float(trip_data.get("net_profit", 0) or 0)
                total_costs = fuel + tolls + salary + extra

                story.append(Paragraph("<b>COST BREAKDOWN (internal)</b>", self.styles["Normal"]))
                cost_data = [
                    [Paragraph("<b>Item</b>", self.styles["Normal"]),
                     Paragraph("<b>Amount</b>", self.styles["Normal"])],
                    [Paragraph("Gross Revenue", self.styles["Normal"]),
                     Paragraph(f"{gross:,.2f} EUR", self.styles["Normal"])],
                    [Paragraph("Fuel Cost", self.styles["Normal"]),
                     Paragraph(f"-{fuel:,.2f} EUR", self.styles["Normal"])],
                    [Paragraph("Toll Cost", self.styles["Normal"]),
                     Paragraph(f"-{tolls:,.2f} EUR", self.styles["Normal"])],
                    [Paragraph("Driver Salary", self.styles["Normal"]),
                     Paragraph(f"-{salary:,.2f} EUR", self.styles["Normal"])],
                    [Paragraph("Extra Costs", self.styles["Normal"]),
                     Paragraph(f"-{extra:,.2f} EUR", self.styles["Normal"])],
                    [Paragraph("<b>Total Costs</b>", self.styles["Normal"]),
                     Paragraph(f"<b>-{total_costs:,.2f} EUR</b>", self.styles["Normal"])],
                    [Paragraph("<b>Net Profit</b>", self.styles["Normal"]),
                     Paragraph(f"<b>{net:,.2f} EUR</b>", self.styles["Normal"])],
                ]
                cost_table = Table(cost_data, colWidths=[13*cm, 5*cm])
                cost_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e8f0fe")),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor("#f0f4ff")),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#e8f0fe")),
                ]))
                story.append(cost_table)
                story.append(Spacer(1, 0.6*cm))

            # ── TOTALS ──────────────────────────────────────────────────
            subtotal = invoice_data.get("subtotal", 0)
            total_tax = invoice_data.get("total_tax", 0)
            discount = invoice_data.get("discount", 0)
            grand_total = invoice_data.get("grand_total", 0)

            totals_data = [
                [Paragraph("<b>Subtotal:</b>", self.styles["Normal"]),
                 Paragraph(f"{subtotal:,.2f} {currency}", self.styles["Normal"])],
                [Paragraph("<b>Tax:</b>", self.styles["Normal"]),
                 Paragraph(f"{total_tax:,.2f} {currency}", self.styles["Normal"])],
            ]
            if discount != 0:
                label = "Discount" if discount > 0 else "Adjustment"
                disc_label = f"{label} ({invoice_data.get('discount_type', '')}):"
                sign = "-" if discount > 0 else "+"
                totals_data.append([
                    Paragraph(f"<b>{disc_label}</b>", self.styles["Normal"]),
                    Paragraph(f"{sign}{abs(discount):,.2f} {currency}", self.styles["Normal"]),
                ])

            totals_table = Table(totals_data, colWidths=[12*cm, 6*cm])
            totals_table.setStyle(TableStyle([
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
            ]))
            story.append(totals_table)
            story.append(Spacer(1, 0.3*cm))

            grand_style = ParagraphStyle("GrandTotal", parent=self.styles["Normal"],
                                         fontSize=12, textColor=company_color)
            story.append(Paragraph(
                f"<b>GRAND TOTAL: {grand_total:,.2f} {currency}</b>", grand_style))
            story.append(Spacer(1, 0.4*cm))

            # ── AMOUNT IN WORDS ─────────────────────────────────────────
            if grand_total > 0:
                try:
                    from utils.number_to_words import number_to_words as _ntw
                    lang = "en" if mode == "client" else "en"
                    words = _ntw(grand_total, currency, lang)
                    word_style = ParagraphStyle("AmountWords", parent=self.styles["Normal"],
                                                fontSize=9, fontName="Helvetica-Oblique",
                                                textColor=colors.HexColor("#555555"))
                    story.append(Paragraph(f"<b>Amount in words:</b> {words}", word_style))
                    story.append(Spacer(1, 0.6*cm))
                except ValueError:
                    story.append(Paragraph(
                        f"<b>Amount in words:</b> [amount too large to convert to words]",
                        self.styles["Normal"]))
                except Exception:
                    pass

            # ── NOTES ───────────────────────────────────────────────────
            notes = invoice_data.get("notes", "")
            if notes and notes.strip():
                story.append(Paragraph("<b>Notes:</b>", self.styles["Normal"]))
                story.append(Paragraph(remove_accents(notes), self.styles["Normal"]))
                story.append(Spacer(1, 1*cm))

            # ── SIGNATURE / STAMP ───────────────────────────────────────
            sig_path = invoice_data.get("signature_path", "")
            stamp_path = invoice_data.get("stamp_path", "")

            if sig_path or stamp_path:
                sig_data = []
                if sig_path and os.path.isfile(sig_path):
                    try:
                        from reportlab.platypus import Image
                        sig_img = Image(sig_path, width=4*cm, height=1.5*cm)
                        sig_data.append(sig_img)
                    except Exception:
                        sig_data.append(Paragraph("Authorized Signature", self.styles["Normal"]))
                else:
                    sig_data.append(Paragraph("", self.styles["Normal"]))

                if stamp_path and os.path.isfile(stamp_path):
                    try:
                        from reportlab.platypus import Image
                        stamp_img = Image(stamp_path, width=3*cm, height=3*cm)
                        sig_data.append(stamp_img)
                    except Exception:
                        sig_data.append(Paragraph("", self.styles["Normal"]))
                elif len(sig_data) == 1 and sig_path:
                    sig_data.append(Paragraph("", self.styles["Normal"]))

                if len(sig_data) > 0:
                    sig_table = Table([sig_data], colWidths=[9*cm, 9*cm])
                    sig_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                    ]))
                    story.append(sig_table)
                    story.append(Spacer(1, 0.5*cm))

            # ── PAYMENT INSTRUCTIONS ───────────────────────────────────
            iban = conf.get("iban", "")
            bank = conf.get("bank_name", "")
            if iban:
                pay_info = f"<b>Payment:</b> IBAN {iban}"
                if bank:
                    pay_info += f" — {remove_accents(bank)}"
                pay_style = ParagraphStyle("PayInfo", parent=self.styles["Normal"],
                                           fontSize=9, textColor=colors.HexColor("#333333"))
                story.append(Paragraph(pay_info, pay_style))
                story.append(Spacer(1, 0.3*cm))

            # ── FOOTER ──────────────────────────────────────────────────
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
            footer_text = (f"{conf.get('company_name', '')} | "
                           f"CUI: {conf.get('cui', '')} | "
                           f"Tel: {conf.get('phone', '')} | "
                           f"Email: {conf.get('email', '')}")
            story.append(Paragraph(remove_accents(footer_text), self.styles["Italic"]))
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph(
                "Thank you for your trust! — Generated by Operion ERP",
                self.styles["Italic"]))

            if is_proforma:
                story.append(Spacer(1, 0.3*cm))
                story.append(Paragraph(
                    "<i>This is a proforma invoice and does not constitute a tax invoice.</i>",
                    self.styles["Italic"]))

            # Build with optional watermark for proforma
            if is_proforma:
                doc.build(story, onFirstPage=self._draw_watermark,
                          onLaterPages=self._draw_watermark)
            else:
                doc.build(story)
            logger.info("Rich invoice PDF generated successfully: path=%s, invoice_id=%s, grand_total=%s",
                        full_path, invoice_id, grand_total)
            return full_path
        except Exception as e:
            logger.error("Failed to generate rich invoice PDF: invoice_id=%s, client=%s, grand_total=%s, document_type=%s — %s",
                         invoice_id, client_name, grand_total, document_type, e, exc_info=True)
            raise
