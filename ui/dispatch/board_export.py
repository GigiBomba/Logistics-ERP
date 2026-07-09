"""CSV and PDF export for the dispatch board.

Extracted from ``dispatch_board_view.py`` to reduce its 2330-line footprint.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from typing import Any, Callable

from PySide6.QtWidgets import QFileDialog, QWidget

from services.i18n import t

logger = logging.getLogger(__name__)


def export_csv(
    parent: QWidget,
    card_data: list[dict[str, Any]],
    show_toast: Callable[[str, str], None],
) -> None:
    """Export dispatch board data to a CSV file."""
    if not card_data:
        show_toast(t("dispatch_board.export_error").format(error="No data"), "error")
        return
    path, _ = QFileDialog.getSaveFileName(
        parent,
        t("dispatch_board.export_csv"),
        f"dispatch_board_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        "CSV files (*.csv)",
    )
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Trip ID", "Status", "Truck", "Driver", "Origin", "Destination",
                "Departure", "ETA", "Alerts",
            ])
            for cd in card_data:
                writer.writerow([
                    cd.get("trip_id", ""),
                    cd.get("status", ""),
                    cd.get("truck_plate", ""),
                    cd.get("driver_name", ""),
                    cd.get("origin", ""),
                    cd.get("destination", ""),
                    cd.get("departure_date", ""),
                    cd.get("eta", ""),
                    cd.get("alerts_count", 0),
                ])
        show_toast(t("dispatch_board.export_success").format(path=path), "success")
    except Exception as e:
        show_toast(t("dispatch_board.export_error").format(error=str(e)), "error")


def export_pdf(
    parent: QWidget,
    card_data: list[dict[str, Any]],
    show_toast: Callable[[str, str], None],
) -> None:
    """Export dispatch board data to a PDF file."""
    if not card_data:
        show_toast(t("dispatch_board.export_error").format(error="No data"), "error")
        return
    path, _ = QFileDialog.getSaveFileName(
        parent,
        t("dispatch_board.export_pdf"),
        f"dispatch_board_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        "PDF files (*.pdf)",
    )
    if not path:
        return
    try:
        from reportlab.lib import colors as rl_colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        doc = SimpleDocTemplate(path, pagesize=landscape(A4), topMargin=10 * mm, bottomMargin=10 * mm)
        styles = getSampleStyleSheet()
        elements: list = []

        title_style = ParagraphStyle(
            "Title", parent=styles["Title"], fontSize=14,
            textColor=rl_colors.HexColor("#fafafa"),
        )
        elements.append(
            Paragraph(f"Dispatch Board \u2014 {datetime.now().strftime('%d/%m/%Y %H:%M')}", title_style)
        )
        elements.append(Spacer(1, 6 * mm))

        status_colors = {
            "Planned": rl_colors.HexColor("#1c1917"),
            "Loading": rl_colors.HexColor("#341a00"),
            "In Transit": rl_colors.HexColor("#0f1f4a"),
            "Delivered": rl_colors.HexColor("#052e16"),
            "Cancelled": rl_colors.HexColor("#1A1A20"),
        }
        header_style = ParagraphStyle(
            "Header", textColor=rl_colors.HexColor("#fafafa"),
            fontSize=9, fontName="Helvetica-Bold",
        )
        cell_style = ParagraphStyle(
            "Cell", textColor=rl_colors.HexColor("#a1a1aa"), fontSize=8,
        )

        from ui.views.dispatch_board.board_state import STATUS_TO_COLUMN

        for col_key in ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]:
            col_trips = [
                cd for cd in card_data
                if STATUS_TO_COLUMN.get(cd.get("status", "")) == col_key
            ]
            bg = status_colors.get(col_key, rl_colors.grey)

            elements.append(Paragraph(f"{col_key} ({len(col_trips)})", header_style))
            elements.append(Spacer(1, 2 * mm))

            if col_trips:
                table_data = [["Trip ID", "Truck", "Driver", "Route", "Departure", "ETA"]]
                for cd in col_trips[:50]:
                    table_data.append([
                        cd.get("trip_id", ""),
                        cd.get("truck_plate", ""),
                        cd.get("driver_name", ""),
                        f"{cd.get('origin','?')} \u2192 {cd.get('destination','?')}",
                        cd.get("departure_date", ""),
                        cd.get("eta", ""),
                    ])
                tbl = Table(table_data, colWidths=[45 * mm, 40 * mm, 45 * mm, 60 * mm, 40 * mm, 40 * mm])
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), bg),
                    ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.HexColor("#fafafa")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#27272a")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [rl_colors.HexColor("#111113"), rl_colors.HexColor("#18181b")]),
                ]))
                elements.append(tbl)
            else:
                elements.append(Paragraph("No trips", cell_style))
            elements.append(Spacer(1, 4 * mm))

        doc.build(elements)
        show_toast(t("dispatch_board.export_success").format(path=path), "success")
    except Exception as e:
        show_toast(t("dispatch_board.export_error").format(error=str(e)), "error")
