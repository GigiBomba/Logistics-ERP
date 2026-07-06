from typing import Any, Dict

from backend.celery_app.celery import celery_app
from config import Config
from database.db_manager import DatabaseManager
from services.document_service import DocumentService

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_ocr(self, document_id: int, engine: str = "auto") -> Dict[str, Any]:
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
            from services.document_automation.ocr_extractor import extract_ocr_data
            result = extract_ocr_data(file_path, engine=engine)
            if result:
                result_text = result.get("text", "")
                result_fields = result.get("fields", {})
        except Exception as e:
            return {"error": str(e), "document_id": document_id}

        update_fields = {
            "ocr_text": result_text,
            "ocr_engine": engine,
            "ocr_run_at": __import__("datetime").datetime.now().isoformat(),
            "extracted_data_json": __import__("json").dumps(result_fields),
        }
        try:
            db.conn.execute(
                "UPDATE documents SET ocr_text = ?, ocr_engine = ?, "
                "ocr_run_at = ?, extracted_data_json = ? WHERE id = ?",
                (result_text, engine, update_fields["ocr_run_at"],
                 __import__("json").dumps(result_fields), document_id),
            )
            db.conn.commit()
        except Exception as e:
            return {"error": f"DB update failed: {e}", "document_id": document_id}

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
def batch_ocr_documents(self, document_ids: list, engine: str = "auto") -> Dict[str, Any]:
    results = []
    for doc_id in document_ids:
        result = process_document_ocr.delay(doc_id, engine)
        results.append({"document_id": doc_id, "task_id": result.id})
    return {"status": "batch_enqueued", "tasks": results}


@celery_app.task
def flush_gps_batch_to_postgres() -> Dict[str, Any]:
    from backend.cache import get_cache
    from config import Config
    from database.db_manager import DatabaseManager

    cache = get_cache()
    if not cache._enabled:
        return {"status": "redis_unavailable"}

    db = DatabaseManager(Config.DB_PATH, engine=Config.DB_ENGINE)
    count = 0
    try:
        import json
        while True:
            raw = cache.lpop("gps:batch_queue")
            if raw is None:
                break
            ping = json.loads(raw)
            db.conn.execute(
                "INSERT INTO gps_telemetry "
                "(truck_id, latitude, longitude, speed_kmh, heading, driver_id, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    ping.get("truck_id"),
                    ping.get("latitude"),
                    ping.get("longitude"),
                    ping.get("speed_kmh", 0),
                    ping.get("heading", 0),
                    ping.get("driver_id"),
                    ping.get("timestamp", ""),
                ),
            )
            count += 1
        if count:
            db.conn.commit()
    finally:
        db.close()
    return {"status": "ok", "flushed": count}
