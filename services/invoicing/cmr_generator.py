"""CMR (waybill) PDF generator for auto-generated trip documents."""
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from services.invoicing.config_manager import load_company_config
from utils.helpers import remove_accents


class CMRGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()

    def generate(self, trip_data: dict, output_dir: str) -> str:
        conf = load_company_config()
        trip_id = trip_data.get("trip_id", trip_data.get("id", 0))
        cmr_id = f"CMR-{datetime.now().year}-{trip_id:04d}"
        filename = f"{cmr_id}.pdf"
        full_path = os.path.join(output_dir, filename)

        doc = SimpleDocTemplate(full_path, pagesize=A4,
                                leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)
        story = []

        title_style = ParagraphStyle("CMRTitle", parent=self.styles["Title"],
                                     fontSize=18, textColor=colors.HexColor("#1a73e8"), alignment=1)
        story.append(Paragraph(f"<b>CMR — INTERNATIONAL WAYBILL</b>", title_style))
        story.append(Paragraph(f"{cmr_id} | {datetime.now().strftime('%d/%m/%Y')}", self.styles["Normal"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a73e8"), spaceAfter=15))

        sender_info = (f"<b>SENDER</b><br/>"
                       f"{remove_accents(conf['company_name'])}<br/>"
                       f"{remove_accents(conf.get('address', ''))}<br/>"
                       f"Tel: {conf.get('phone', '')}")
        client_name = trip_data.get("client_name", "N/A")
        client_address = trip_data.get("client_address", "")
        receiver_info = (f"<b>RECEIVER</b><br/>"
                         f"{remove_accents(client_name)}<br/>"
                         f"{remove_accents(client_address)}")

        info_table = Table([[Paragraph(sender_info, self.styles["Normal"]),
                             Paragraph(receiver_info, self.styles["Normal"])]],
                          colWidths=[9*cm, 9*cm])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 1*cm))

        story.append(Paragraph("<b>TRANSPORT DETAILS</b>", self.styles["Normal"]))
        truck = trip_data.get("truck_number", trip_data.get("truck_plate", "N/A"))
        driver = trip_data.get("driver_name", "N/A")
        transport_data = [
            ["Truck", "Driver", "Distance", "Start Date", "End Date"],
            [truck, remove_accents(driver),
             f"{trip_data.get('distance_km', 0)} km",
             trip_data.get("start_date", ""), trip_data.get("end_date", "")]
        ]
        tech_table = Table(transport_data, colWidths=[3.6*cm]*5)
        tech_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f0f4ff")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(tech_table)
        story.append(Spacer(1, 0.8*cm))

        story.append(Paragraph("<b>LOADING / UNLOADING</b>", self.styles["Normal"]))
        origin = trip_data.get("origin", trip_data.get("loading_address", ""))
        destination = trip_data.get("destination", trip_data.get("unloading_address", ""))
        stops = trip_data.get("stops", [])
        if stops and isinstance(stops, list) and len(stops) >= 2:
            origin = origin or stops[0]
            destination = destination or stops[-1]

        place_data = [
            ["Place of Loading", "Place of Unloading"],
            [remove_accents(origin), remove_accents(destination)]
        ]
        place_table = Table(place_data, colWidths=[9*cm, 9*cm])
        place_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f0f4ff")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(place_table)
        story.append(Spacer(1, 1.5*cm))

        sig_data = [
            ["Sender's Signature", "Carrier's Signature", "Receiver's Signature"],
            ["", "", ""],
            ["", "", ""],
            ["", "", ""],
        ]
        sig_table = Table(sig_data, colWidths=[6*cm, 6*cm, 6*cm])
        sig_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f0f4ff")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
        ]))
        story.append(sig_table)

        story.append(Spacer(1, 1*cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        footer_msg = f"Generated by Operion ERP | {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        story.append(Paragraph(footer_msg, self.styles["Italic"]))

        doc.build(story)
        return full_path
