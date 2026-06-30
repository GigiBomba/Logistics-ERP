"""Template service — document template generation (CMR, contracts, etc.)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from database.db_manager import DatabaseManager
from repositories.document_repository import DocumentRepository

logger = logging.getLogger("document_template_service")

DOCUMENTS_ROOT = os.path.join("data", "documents")


class TemplateService:

    def __init__(self, db: DatabaseManager, repo: DocumentRepository) -> None:
        self.db = db
        self._repo = repo

    def create_template(self, name: str, description: str = "",
                        category: str = "general",
                        template_type: str = "pdf",
                        fields: list[dict] | None = None) -> int:
        now = datetime.now().isoformat()
        fields_json = json.dumps(fields if fields else [])
        return self._repo.create_template(
            name, description, category, template_type, fields_json, now, now,
        )

    def get_templates(self, category: str = "") -> list[dict[str, object]]:
        return self._repo.get_templates(category)

    def generate_from_template(self, template_id: int,
                                context: dict[str, str],
                                output_dir: str = "") -> str | None:
        template_rec = self._repo.get_template_by_id(template_id)
        if not template_rec:
            return None

        json.loads(template_rec.get("fields_json", "[]"))
        cat = template_rec["category"]
        ttype = template_rec["template_type"]

        if cat == "cmr" and ttype == "pdf":
            from services.invoicing.cmr_generator import CMRGenerator
            gen = CMRGenerator(db=self.db)
            if not output_dir:
                output_dir = os.path.join(DOCUMENTS_ROOT, "trips")
            os.makedirs(output_dir, exist_ok=True)
            context.get("trip_id", "unknown")
            filepath = gen.generate(context, output_dir)
            return filepath

        if cat == "contract" and ttype == "pdf":
            return self._generate_contract_pdf(context, output_dir)

        return None

    def _generate_contract_pdf(self, context: dict[str, str],
                                output_dir: str) -> str | None:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        os.makedirs(output_dir, exist_ok=True)
        filename = f"Contract_{context.get('client_name', 'Unknown')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        filepath = os.path.join(output_dir, filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4,
                                leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)
        styles = getSampleStyleSheet()
        story = []
        title_style = ParagraphStyle("CTitle", parent=styles["Title"],
                                     fontSize=18, textColor=colors.HexColor("#1a73e8"))
        story.append(Paragraph("<b>CONTRACT</b>", title_style))
        story.append(Spacer(1, 0.5*cm))

        for k, v in context.items():
            story.append(Paragraph(f"<b>{k}:</b> {v}", styles["Normal"]))
            story.append(Spacer(1, 0.2*cm))

        story.append(Spacer(1, 2*cm))
        story.append(Paragraph("Signed: ________________    Date: ________________",
                               styles["Normal"]))
        doc.build(story)
        return filepath
