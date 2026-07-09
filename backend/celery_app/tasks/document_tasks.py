"""Celery tasks for document generation — PDF, email packages."""
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from backend.celery_app.celery import celery_app
from config import Config
from database.db_manager import DatabaseManager
from services.document_service import DocumentService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def generate_document_pdf(
    self, document_id: int, template_name: str
) -> Dict[str, Any]:
    """Generate a PDF for a document using its template."""
    db = DatabaseManager(Config.DB_PATH)
    try:
        service = DocumentService(db)
        doc = service.get_by_id(document_id)
        if not doc:
            return {"error": "Document not found", "document_id": document_id}

        file_path = doc.get("file_path", "")
        if not file_path or not os.path.isfile(file_path):
            return {"error": "Source file not found", "document_id": document_id, "path": file_path}

        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(Config.REPORTS_DIR, "generated")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"doc_{document_id}_{template_name}_{ts}.pdf")

        try:
            from services.invoicing.config_manager import load_company_config
            from services.invoicing.generator import InvoiceGenerator
            gen = InvoiceGenerator()
            config = load_company_config()
            gen.generate(doc, config, output_path)
        except ImportError:
            from services.document_automation.package_builder import PackageBuilder
            builder = PackageBuilder(db)
            # Fallback: build a combined PDF from the document's trip
            from repositories.document_repository import DocumentRepository
            doc_record = DocumentRepository(db).get_by_id(document_id)
            trip_id = doc_record.get("entity_id") if doc_record else None
            if trip_id:
                builder.build_combined_pdf(trip_id, output_dir)
            else:
                builder.build_zip(0, output_dir)

        return {
            "status": "ok",
            "document_id": document_id,
            "output_path": output_path,
            "template": template_name,
        }
    except Exception as exc:
        logger.exception("PDF generation failed for doc %d", document_id)
        self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def build_email_package(
    self, document_ids: List[int], recipient: str, prefs: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build and optionally email a ZIP package of documents."""
    if prefs is None:
        prefs = {}
    db = DatabaseManager(Config.DB_PATH)
    try:
        service = DocumentService(db)
        zip_path = tempfile.mktemp(suffix=".zip")
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for doc_id in document_ids:
                    doc = service.get_by_id(doc_id)
                    if doc and doc.get("file_path") and os.path.isfile(doc["file_path"]):
                        arcname = doc.get("file_name", f"doc_{doc_id}")
                        zf.write(doc["file_path"], arcname)
            result = {
                "status": "ok",
                "document_count": len(document_ids),
                "recipient": recipient,
                "zip_size": os.path.getsize(zip_path),
            }
            smtp_configured = (
                prefs.get("smtp_server") or Config.SMTP_SERVER
            ) and (
                prefs.get("smtp_user") or Config.SMTP_USER
            )
            if smtp_configured and recipient:
                try:
                    from services.document_service import DocumentService as DS
                    svc = DS(db)
                    svc.email_document(document_ids[0], recipient, prefs=prefs)
                    result["email_sent"] = True
                except Exception as e:
                    result["email_error"] = str(e)
                    result["email_sent"] = False
            return result
        finally:
            if os.path.isfile(zip_path):
                os.unlink(zip_path)
    except Exception as exc:
        logger.exception("Email package build failed")
        self.retry(exc=exc)
    finally:
        db.close()
