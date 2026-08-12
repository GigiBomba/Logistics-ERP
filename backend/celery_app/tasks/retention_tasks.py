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
from database.tenant_context import set_company_context
from repositories.company_repository import CompanyRepository
from repositories.copilot_repository import (
    CopilotAuditRepository,
    CopilotReasoningGraphRepository,
    ConversationSummaryRepository,
)

logger = logging.getLogger(__name__)


@celery_app.task
def enforce_copilot_retention() -> dict:
    """Enforce rolling retention on all Copilot tables.
    
    copilot_audit_log: 24 months from created_at
    copilot_reasoning_graphs: 90 days from finalized_at (null graph JSONB, keep row)
    conversation_summary: 24 months from ended_at

    Cleanup runs per active company (tenant-scoped) so one scheduled run
    never deletes another tenant's audit/summary history.
    """
    from backend.db import DatabaseManager
    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        results = {}

        audit_cutoff = (datetime.now() - timedelta(days=730)).isoformat()
        graph_cutoff = (datetime.now() - timedelta(days=90)).isoformat()
        conv_cutoff = (datetime.now() - timedelta(days=730)).isoformat()

        audit_repo = CopilotAuditRepository(db)
        graph_repo = CopilotReasoningGraphRepository(db)
        conv_repo = ConversationSummaryRepository(db)

        audit_total = 0
        graph_total = 0
        conv_total = 0

        for company_id in CompanyRepository(db).get_active_ids():
            if not company_id:
                continue  # skip admin/global scope (id 0)
            set_company_context(company_id)

            # ── copilot_audit_log: delete rows older than 24 months ──────
            try:
                audit_total += audit_repo.delete_older_than(audit_cutoff, company_id=company_id)
            except Exception as e:
                logger.warning(
                    "Retention: audit_log cleanup failed for company %d: %s",
                    company_id, e,
                )
                results["audit_log_error"] = str(e)

            # ── copilot_reasoning_graphs: null graph JSONB after 90 days ─
            try:
                graph_total += graph_repo.delete_older_than(graph_cutoff, company_id=company_id)
            except Exception as e:
                logger.warning(
                    "Retention: reasoning_graphs cleanup failed for company %d: %s",
                    company_id, e,
                )
                results["reasoning_graphs_error"] = str(e)

            # ── conversation_summary: delete rows older than 24 months ───
            try:
                conv_total += conv_repo.delete_older_than(conv_cutoff, company_id=company_id)
            except Exception as e:
                logger.warning(
                    "Retention: conversation_summary cleanup failed for company %d: %s",
                    company_id, e,
                )
                results["conversation_summary_error"] = str(e)

        results["audit_log_deleted"] = audit_total
        logger.info("Retention: deleted %d audit rows older than 24 months", audit_total)
        results["reasoning_graphs_anonymized"] = graph_total
        logger.info("Retention: anonymized %d reasoning graphs older than 90 days", graph_total)
        results["conversation_summary_deleted"] = conv_total
        logger.info("Retention: deleted %d conversation summaries older than 24 months", conv_total)

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
            # Anonymize copilot_audit_log — per active company so the raw SQL
            # is always tenant-scoped (never reads/writes another tenant's rows).
            # TODO: migrate SELECT to repo when CopilotAuditRepository supports JSONB search
            audit_repo = CopilotAuditRepository(db)
            anonymized_count = 0
            for company_id in CompanyRepository(db).get_active_ids():
                if not company_id:
                    continue  # skip admin/global scope (id 0)
                set_company_context(company_id)
                rows = db.conn.execute(
                    "SELECT id, parameters, result FROM copilot_audit_log "
                    "WHERE company_id = ? AND "
                    "(CAST(parameters AS TEXT) LIKE ? OR CAST(result AS TEXT) LIKE ?)",
                    (company_id, f"%{entity_id}%", f"%{entity_id}%"),
                ).fetchall()

                for row in rows:
                    try:
                        params = json.loads(row["parameters"]) if row["parameters"] else {}
                        result_data = json.loads(row["result"]) if row["result"] else {}
                        params_redacted = _redact_jsonb(params)
                        result_redacted = _redact_jsonb(result_data)
                        audit_repo._execute(
                            "UPDATE copilot_audit_log SET parameters = ?, result = ? "
                            "WHERE id = ? AND company_id = ?",
                            (json.dumps(params_redacted), json.dumps(result_redacted),
                             row["id"], company_id),
                            commit=False,
                        )
                        anonymized_count += 1
                    except Exception as e:
                        logger.warning(
                            "Erasure: audit row %s failed for company %d: %s",
                            row["id"], company_id, e,
                        )
                audit_repo.db.conn.commit()
            results["audit_anonymized"] = anonymized_count
            logger.info("Erasure: anonymized %d audit log entries", anonymized_count)
        except Exception as e:
            logger.warning("Erasure: audit log anonymization failed: %s", e)
            results["audit_error"] = str(e)
        
        return results
    finally:
        db.close()
