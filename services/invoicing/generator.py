import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from .config_manager import load_company_config
from services.i18n import t, _get_translations
from utils.helpers import remove_accents

class InvoiceGenerator:
    def __init__(self):
        self.reports_dir = os.path.abspath("invoices")
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
        self.styles = getSampleStyleSheet()

    def _tr(self, key, mode):
        """Translate key: client mode always uses English, internal uses current app language."""
        if mode == "client":
            return _get_translations("en").get(key, key)
        return t(key)

    def generate(self, trip_data, mode="client"):
        conf = load_company_config()
        trip_id = trip_data.get("id", 0)
        invoice_id = f"INV-{datetime.now().year}-{trip_id:04d}"
        filename = f"{invoice_id}_{mode}.pdf"
        full_path = os.path.join(self.reports_dir, filename)

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
                        f"{remove_accents(conf['company_name'])}<br/>"
                        f"CUI: {conf['cui']}<br/>"
                        f"Reg. Com: {conf['reg_number']}<br/>"
                        f"Adresa: {remove_accents(conf['address'])}<br/>"
                        f"Tel: {conf['phone']}")
        
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

        story.append(Spacer(1, 2*cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        footer_msg = f"Email: {conf['email']} | Tel: {conf['phone']}"
        story.append(Paragraph(remove_accents(footer_msg), self.styles["Italic"]))
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(self._tr("invoice_pdf.footer", mode), self.styles["Italic"]))

        doc.build(story)
        return full_path
