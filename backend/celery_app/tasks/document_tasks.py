"""Celery tasks for document generation — PDF, email packages."""
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from backend.celery_app.celery import celery_app
from backend.db import DatabaseManager
from backend.dependencies import set_company_context
from backend.desktop_config import Config
from backend.services.document_service import DocumentService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def generate_document_pdf(
    self, document_id: int, company_id: int, template_name: str,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Generate a PDF for a document using its template.

    ``request_id`` is the HTTP correlation id from the originating request,
    used to trace async task failures back to their request.
    """
    logger.info(
        "generate_document_pdf: document_id=%d company_id=%d template=%s request_id=%s",
        document_id, company_id, template_name, request_id,
    )
    set_company_context(company_id)
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
            from backend.repositories.document_repository import DocumentRepository
            doc_record = DocumentRepository(db).get_by_id(document_id)
            trip_id = doc_record.get("entity_id") if doc_record else None
            if trip_id:
                builder.build_combined_pdf(trip_id, output_dir)
            else:
                builder.build_zip(0, output_dir)

        logger.info(
            "generate_document_pdf completed: document_id=%d request_id=%s",
            document_id, request_id,
        )
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
    self, document_ids: List[int], recipient: str, company_id: int,
    prefs: Optional[Dict[str, Any]] = None,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Build and optionally email a ZIP package of documents.

    ``request_id`` is the HTTP correlation id from the originating request,
    used to trace async task failures back to their request.
    """
    logger.info(
        "build_email_package: document_count=%d recipient=%s company_id=%d request_id=%s",
        len(document_ids), recipient, company_id, request_id,
    )
    set_company_context(company_id)
    if prefs is None:
        prefs = {}
    db = DatabaseManager(Config.DB_PATH)
    try:
        service = DocumentService(db)
        fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
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
                from backend.services.document_service import DocumentService as DS
                from repositories.sent_email_repository import SentEmailRepository
                svc = DS(db)
                dedup = SentEmailRepository(db)
                # Dedup (roadmap 12): claim a 'pending' row before sending.
                # If the row already exists (INSERT OR IGNORE inserts 0 rows),
                # a send is already in flight/complete for this
                # (document_id, recipient) pair — skip to avoid double-send.
                if not document_ids or not dedup.claim(document_ids[0], recipient):
                    logger.warning(
                        "build_email_package: email already sent/in-flight for "
                        "document_id=%s recipient=%s — skipping duplicate send",
                        document_ids[0] if document_ids else None, recipient,
                    )
                    result["email_sent"] = False
                    result["email_deduplicated"] = True
                else:
                    try:
                        svc.email_document(document_ids[0], recipient, prefs=prefs)
                        dedup.mark_sent(document_ids[0], recipient)
                        result["email_sent"] = True
                    except Exception as e:
                        # On failure remove the pending row so a Celery retry
                        # can re-attempt the send (same failure path as before).
                        dedup.remove_pending(document_ids[0], recipient)
                        result["email_error"] = str(e)
                        result["email_sent"] = False
            logger.info(
                "build_email_package completed: document_count=%d request_id=%s",
                len(document_ids), request_id,
            )
            return result
        finally:
            if os.path.isfile(zip_path):
                os.unlink(zip_path)
    except Exception as exc:
        logger.exception("Email package build failed")
        self.retry(exc=exc)
    finally:
        db.close()
