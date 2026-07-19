"""Data retention and GDPR erasure tasks for Copilot tables (§24).

Enforces rolling retention periods on copilot_audit_log, copilot_reasoning_graphs,
and conversation_summary. Also handles right-to-erasure anonymization.

Blueprint: §24 — Data Retention & Right to Erasure.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from backend.celery_app.celery import celery_app
from backend.config import BackendSettings

logger = logging.getLogger(__name__)


@celery_app.task
def enforce_copilot_retention() -> dict:
    """Enforce rolling retention on all Copilot tables.
    
    copilot_audit_log: 24 months from created_at
    copilot_reasoning_graphs: 90 days from finalized_at (null graph JSONB, keep row)
    conversation_summary: 24 months from ended_at
    """
    from backend.db import DatabaseManager
    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        results = {}
        
        try:
            # ── copilot_audit_log: delete rows older than 24 months ──────
            audit_cutoff = (datetime.now() - timedelta(days=730)).isoformat()
            deleted = db.conn.execute(
                "DELETE FROM copilot_audit_log WHERE created_at < ?",
                (audit_cutoff,),
            ).rowcount
            db.conn.commit()
            results["audit_log_deleted"] = deleted
            logger.info("Retention: deleted %d audit rows older than 24 months", deleted)
        except Exception as e:
            logger.warning("Retention: audit_log cleanup failed: %s", e)
            results["audit_log_error"] = str(e)
        
        try:
            # ── copilot_reasoning_graphs: null graph JSONB after 90 days ─
            graph_cutoff = (datetime.now() - timedelta(days=90)).isoformat()
            nulled = db.conn.execute(
                "UPDATE copilot_reasoning_graphs SET graph = NULL, finalized_at = NULL "
                "WHERE finalized_at < ? AND graph IS NOT NULL",
                (graph_cutoff,),
            ).rowcount
            db.conn.commit()
            results["reasoning_graphs_anonymized"] = nulled
            logger.info("Retention: anonymized %d reasoning graphs older than 90 days", nulled)
        except Exception as e:
            logger.warning("Retention: reasoning_graphs cleanup failed: %s", e)
            results["reasoning_graphs_error"] = str(e)
        
        try:
            # ── conversation_summary: delete rows older than 24 months ───
            conv_cutoff = (datetime.now() - timedelta(days=730)).isoformat()
            deleted_conv = db.conn.execute(
                "DELETE FROM conversation_summary WHERE ended_at < ?",
                (conv_cutoff,),
            ).rowcount
            db.conn.commit()
            results["conversation_summary_deleted"] = deleted_conv
            logger.info("Retention: deleted %d conversation summaries older than 24 months", deleted_conv)
        except Exception as e:
            logger.warning("Retention: conversation_summary cleanup failed: %s", e)
            results["conversation_summary_error"] = str(e)
        
        return results
    finally:
        db.close()


@celery_app.task
def anonymize_copilot_data(entity_type: str, entity_id: int) -> dict:
    """Anonymize personal data in copilot tables for GDPR erasure requests.
    
    Replaces personal identifiers in parameters and result JSONB blobs
    with '[REDACTED]' while leaving structural fields intact.
    
    Args:
        entity_type: 'user', 'client', 'driver'
        entity_id: The ID of the entity to anonymize
    
    Blueprint: §24 — Right to Erasure.
    """
    from backend.db import DatabaseManager
    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        redacted = "[REDACTED]"
        results = {}
        
        # Fields to redact in JSONB parameters and result blobs
        personal_keys = {"name", "email", "phone", "address", "contact", "notes",
                         "driver_name", "client_name", "company_name", "recipient",
                         "sender", "to_address", "from_address", "body", "subject"}
        
        def _redact_jsonb(obj):
            """Recursively redact personal keys in JSON."""
            if isinstance(obj, dict):
                return {k: _redact_jsonb(v) if k not in personal_keys else redacted for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_redact_jsonb(item) for item in obj]
            return obj
        
        try:
            # Anonymize copilot_audit_log
            rows = db.conn.execute(
                "SELECT id, parameters, result FROM copilot_audit_log "
                "WHERE CAST(parameters AS TEXT) LIKE ? OR CAST(result AS TEXT) LIKE ?",
                (f"%{entity_id}%", f"%{entity_id}%"),
            ).fetchall()
            
            anonymized_count = 0
            for row in rows:
                try:
                    params = json.loads(row["parameters"]) if row["parameters"] else {}
                    result_data = json.loads(row["result"]) if row["result"] else {}
                    params_redacted = _redact_jsonb(params)
                    result_redacted = _redact_jsonb(result_data)
                    db.conn.execute(
                        "UPDATE copilot_audit_log SET parameters = ?, result = ? WHERE id = ?",
                        (json.dumps(params_redacted), json.dumps(result_redacted), row["id"]),
                    )
                    anonymized_count += 1
                except Exception:
                    continue
            db.conn.commit()
            results["audit_anonymized"] = anonymized_count
            logger.info("Erasure: anonymized %d audit log entries", anonymized_count)
        except Exception as e:
            logger.warning("Erasure: audit log anonymization failed: %s", e)
            results["audit_error"] = str(e)
        
        return results
    finally:
        db.close()
