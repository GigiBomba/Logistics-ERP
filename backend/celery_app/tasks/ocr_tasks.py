from __future__ import annotations

import logging
from typing import Any, Dict

from backend.celery_app.celery import celery_app
from backend.db import DatabaseManager
from backend.dependencies import set_company_context
from backend.desktop_config import Config
from backend.services.document_service import DocumentService
from repositories.document_repository import DocumentRepository
from repositories.gps_telemetry_repository import GpsTelemetryRepository

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_ocr(
    self, document_id: int, company_id: int, engine: str = "auto",
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Run OCR on a document (entry task — accepts a tracing ``request_id``).

    ``request_id`` is the HTTP correlation id from the originating request,
    used to trace async task failures back to their request.
    """
    logger.info(
        "process_document_ocr: document_id=%d company_id=%d request_id=%s",
        document_id, company_id, request_id,
    )
    set_company_context(company_id)
    db = DatabaseManager(Config.DB_PATH)
    try:
        service = DocumentService(db)
        doc = service.get_by_id(document_id)
        if not doc:
            return {"error": "Document not found", "document_id": document_id}

        file_path = doc.get("file_path", "")
        if not file_path:
            return {"error": "No file path", "document_id": document_id}

        try:
            import os
            if not os.path.isfile(file_path):
                return {"error": "File not on disk", "document_id": document_id, "path": file_path}
        except Exception:
            pass

        result_text = ""
        result_fields: Dict[str, Any] = {}

        try:
            from services.document_automation.ocr_extractor import OcrExtractor
            extractor = OcrExtractor(db=db)
            extraction = extractor.extract(file_path)
            if extraction:
                result_text = extraction.full_text or ""
                result_fields = extraction.extracted or {}
        except Exception as e:
            return {"error": str(e), "document_id": document_id}

        update_fields = {
            "ocr_text": result_text,
            "ocr_engine": engine,
            "ocr_run_at": __import__("datetime").datetime.now().isoformat(),
            "extracted_data_json": __import__("json").dumps(result_fields),
        }
        try:
            DocumentRepository(db).update(
                document_id,
                commit=True,
                ocr_text=result_text,
                ocr_engine=engine,
                ocr_run_at=update_fields["ocr_run_at"],
                extracted_data_json=__import__("json").dumps(result_fields),
            )
        except Exception as e:
            return {"error": f"DB update failed: {e}", "document_id": document_id}

        logger.info(
            "process_document_ocr completed: document_id=%d request_id=%s",
            document_id, request_id,
        )
        return {
            "status": "ok",
            "document_id": document_id,
            "engine": engine,
            "text_length": len(result_text),
            "field_count": len(result_fields),
        }
    except Exception as exc:
        self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2)
def batch_ocr_documents(
    self, document_ids: list, company_id: int, engine: str = "auto"
) -> Dict[str, Any]:
    logger.info(
        "batch_ocr_documents: count=%d company_id=%d engine=%s",
        len(document_ids), company_id, engine,
    )
    results = []
    for doc_id in document_ids:
        result = process_document_ocr.delay(doc_id, company_id, engine)
        results.append({"document_id": doc_id, "task_id": result.id})
    return {"status": "batch_enqueued", "tasks": results}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def flush_gps_batch_to_postgres(self) -> Dict[str, Any]:
    """Drain every tenant's ``gps:batch:{company_id}`` queue into gps_telemetry.

    Scheduled globally from ``backend.celery_app.celery`` beat (every 30 s).
    The queue is tenant-scoped at push time (``backend.api.v1.fleet`` writes
    ``gps:batch:{company_id}``), so this task iterates the active companies and
    drains each company's queue with ``set_company_context(company_id)`` — every
    row lands with the correct ``company_id``.

    Rows are only removed from the Redis list (``ltrim``) AFTER the DB commit
    succeeds, so a mid-drain failure retries without losing pings; the
    ``idx_gps_telemetry_unique(truck_id, recorded_at)`` unique index makes
    replayed inserts idempotent (no double-inserts).
    """
    logger.info("flush_gps_batch_to_postgres: per-company drain starting")
    from backend.cache import get_cache
    from backend.db import DatabaseManager
    from backend.desktop_config import Config
    from database.tenant_context import set_company_context as set_tenant_context

    cache = get_cache()
    if not cache._enabled:
        return {"status": "redis_unavailable"}

    db = DatabaseManager(Config.DB_PATH, engine=Config.DB_ENGINE)
    total = 0
    try:
        import json
        from repositories.company_repository import CompanyRepository

        repo = GpsTelemetryRepository(db)
        companies = CompanyRepository(db).get_active_ids()
        for company_id in companies:
            set_tenant_context(company_id)
            key = f"gps:batch:{company_id}"
            items = cache.lrange(key, 0, -1) or []
            if not items:
                continue
            records = []
            for raw in items:
                ping = json.loads(raw)
                records.append({
                    "truck_id": ping.get("truck_id"),
                    "latitude": ping.get("latitude"),
                    "longitude": ping.get("longitude"),
                    "speed_kmh": ping.get("speed_kmh", 0),
                    "heading": ping.get("heading", 0),
                    "driver_id": ping.get("driver_id"),
                    "recorded_at": ping.get("timestamp", ""),
                })
            repo.create_many(records)  # commits internally (INSERT OR IGNORE)
            cache.ltrim(key, len(records), -1)
            total += len(records)
            logger.info(
                "flush_gps_batch_to_postgres: flushed %d pings for company_id=%d",
                len(records), company_id,
            )
        return {"status": "ok", "flushed": total}
    except Exception as exc:
        self.retry(exc=exc)
    finally:
        db.close()
