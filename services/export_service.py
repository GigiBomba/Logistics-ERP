import contextlib
import os
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Table, TableStyle

from config import Config
from utils.helpers import remove_accents

_ALLOWED_EXTENSIONS = {".pdf", ".xlsx"}

class ExportService:
    def __init__(self, prefs=None):
        self.styles = getSampleStyleSheet()
        self.reports_dir = Config.REPORTS_DIR
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
        self.prefs = prefs

    @staticmethod
    def _safe_filename(filename: str, allowed_ext: str = ".pdf") -> str:
        """Validate filename is a plain name with allowed extension (prevents path traversal)."""
        name = os.path.basename(filename)
        ext = os.path.splitext(name)[1].lower()
        if ext not in _ALLOWED_EXTENSIONS and ext != allowed_ext:
            raise ValueError(f"Filename extension '{ext}' not allowed")
        if ".." in name or "/" in name or "\\" in name:
            raise ValueError(f"Invalid filename: {filename!r}")
        return name

    def generate_pdf(self, trips, filename=None):
        """Generează PDF-ul de istoric fără diacritice."""
        if not filename:
            filename = f"raport_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        else:
            filename = self._safe_filename(filename, allowed_ext=".pdf")

        full_path = os.path.join(self.reports_dir, filename)

        doc = SimpleDocTemplate(full_path, pagesize=A4,
                                leftMargin=1*cm, rightMargin=1*cm,
                                topMargin=1*cm, bottomMargin=1*cm)
        story = []

        # Stil Titlu
        title_style = ParagraphStyle("T", parent=self.styles["Title"], fontSize=18, textColor=colors.HexColor("#1a73e8"))

        # Curățăm titlul și header-ul de orice diacritică
        story.append(Paragraph(remove_accents("Cashflow Manager - Raport Activitate"), title_style))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#1a73e8"), spaceAfter=20))

        # Header Tabel (ASCII)
        data = [[
            "Data",
            "Camion",
            "Sofer",
            "Client",
            "KM",
            "Brut/km",
            "Profit",
            "Status"
        ]]

        for t in trips:
            # Aplicăm _remove_accents pe toate câmpurile care pot conține text românesc
            data.append([
                str(t["created_at"])[:10],
                remove_accents(t["truck_number"]),
                remove_accents(t["driver_name"]),
                remove_accents(t["client_name"]),
                f"{t['distance_km']:.0f}",
                f"{t['gross_per_km']:.2f}",
                f"{t['net_profit']:.2f}",
                remove_accents(t["status"])
            ])

        # Ajustăm lățimile coloanelor (total ~19cm)
        table = Table(data, colWidths=[2.2*cm, 2.5*cm, 3.2*cm, 4*cm, 1.5*cm, 1.8*cm, 2.3*cm, 2.3*cm])

        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1a73e8")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))

        story.append(table)
        try:
            doc.build(story)
        except Exception:
            # Clean up partial file on build failure
            if os.path.exists(full_path):
                with contextlib.suppress(OSError):
                    os.remove(full_path)
            raise
        return full_path

    def generate_excel(self, trips, filename=None):
        """Generează Excel detaliat (aici putem păstra diacriticele deoarece Excel le suportă nativ)."""
        if not filename:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        else:
            filename = self._safe_filename(filename, allowed_ext=".xlsx")

        full_path = os.path.join(self.reports_dir, filename)

        wb = Workbook()
        ws = wb.active
        ws.title = "Istoric Curse"

        headers = [
            "ID", "Data", "Camion", "Sofer", "Client", "KM",
            "Pret Total", "Profit Net", "Brut/km", "Net/km",
            "Status", "Combustibil", "Taxe", "Salariu"
        ]
        ws.append(headers)

        for t in trips:
            ws.append([
                t["id"], t["created_at"], t["truck_number"], t["driver_name"],
                t["client_name"], t["distance_km"], t["total_price_eur"],
                t["net_profit"], t["gross_per_km"], t["rate_per_km"],
                t["status"], t["fuel_cost"], t["toll_cost"], t["salary_cost"]
            ])

        # Formatare Header Excel
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="1A73E8", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")

        # Ajustare automată lățime
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                with contextlib.suppress(Exception): max_length = max(max_length, len(str(cell.value)))
            ws.column_dimensions[column].width = max_length + 2

        wb.save(full_path)
        return full_path
