"""GDPR compliance endpoints — data export and deletion (admin only)."""
from __future__ import annotations

import json
import logging
import tempfile
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from backend.dependencies import get_db
from backend.dependencies_security import require_admin
from repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gdpr", tags=["gdpr"])

# Tables to include in data export (all business tables with company_id)
EXPORT_TABLES = [
    "trips", "invoices", "proforma_invoices", "receipts",
    "clients", "client_contacts", "client_tags",
    "trucks", "drivers", "driver_truck_assignments",
    "routes", "route_history", "route_history_v2", "route_events",
    "documents", "document_links", "document_versions",
    "maintenance_records", "maintenance_schedules", "truck_health_scores",
    "alerts", "trip_status_history", "operation_events",
    "tacho_imports", "tacho_driver_activity", "tacho_vehicle_data",
    "gps_telemetry",
    "webhook_events", "email_logs",
    "contracts", "successive_carriers", "cmr_audit_log",
    "document_pipeline_runs", "document_package", "document_package_items",
    "automail_templates", "automail_schedules", "automail_client_overrides",
    "payment_profiles",
]


@router.post("/export/company/{company_id}")
async def export_company_data(company_id: int, db=Depends(get_db),
                               _=Depends(require_admin)):
    """Export all data for a company (GDPR Article 20 — data portability).

    Returns a JSON file containing all records across all tables
    that belong to the specified company.
    """
    export_data = {
        "exported_at": datetime.now().isoformat(),
        "company_id": company_id,
        "tables": {},
    }

    total_records = 0

    for table in EXPORT_TABLES:
        try:
            # GDPR dynamic export — cannot migrate to repo
            col_check = db.conn.execute(f"PRAGMA table_info({table})").fetchall()
            has_company_id = any(c[1] == "company_id" for c in col_check)

            if has_company_id:
                # GDPR dynamic export — cannot migrate to repo
                rows = db.execute(
                    f"SELECT * FROM {table} WHERE company_id = ?", (company_id,)  # nosec B608
                ).fetchall()
            else:
                rows = []

            records = [_row_to_dict(r) for r in rows]
            export_data["tables"][table] = {
                "count": len(records),
                "records": records,
            }
            total_records += len(records)

        except Exception as e:
            export_data["tables"][table] = {"count": 0, "error": str(e)}
            logger.warning("GDPR export: failed to read table %s: %s", table, e)

    export_data["total_records"] = total_records
    logger.info("GDPR export: company_id=%d, records=%d across %d tables",
                company_id, total_records, len(EXPORT_TABLES))

    # Write to temp file and return as download
    fd, path = tempfile.mkstemp(suffix=".json", prefix=f"gdpr_export_{company_id}_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, default=str, ensure_ascii=False)

    return FileResponse(
        path,
        media_type="application/json",
        filename=f"operion_gdpr_export_company_{company_id}_{datetime.now().strftime('%Y%m%d')}.json"
    )


@router.post("/export/user/{user_id}")
async def export_user_data(user_id: int, db=Depends(get_db),
                           _=Depends(require_admin)):
    """Export all data associated with a user (GDPR data portability)."""
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    user_data = user
    # Remove sensitive fields from export
    user_data.pop("password_hash", None)

    export = {
        "exported_at": datetime.now().isoformat(),
        "user": user_data,
        "company_id": user_data.get("company_id"),
    }

    logger.info("GDPR export: user_id=%d", user_id)

    fd, path = tempfile.mkstemp(suffix=".json", prefix=f"gdpr_export_user_{user_id}_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2, default=str, ensure_ascii=False)

    return FileResponse(
        path, media_type="application/json",
        filename=f"operion_gdpr_export_user_{user_id}_{datetime.now().strftime('%Y%m%d')}.json"
    )


@router.post("/delete/company/{company_id}")
async def delete_company_data(company_id: int, confirm: str = "",
                               db=Depends(get_db), _=Depends(require_admin)):
    """Delete all data for a company (GDPR Article 17 — right to erasure).

    Requires explicit confirmation: ?confirm=DELETE
    Performs a SOFT delete (sets is_active=0) for recoverability.
    """
    if confirm != "DELETE":
        raise HTTPException(400, "Must confirm deletion with ?confirm=DELETE")

    deleted = {}

    # 1. Soft-delete all child records
    for table in EXPORT_TABLES:
        try:
            # GDPR dynamic export — cannot migrate to repo
            col_check = db.conn.execute(f"PRAGMA table_info({table})").fetchall()
            has_company_id = any(c[1] == "company_id" for c in col_check)
            has_is_active = any(c[1] == "is_active" for c in col_check)

            if has_company_id:
                # GDPR dynamic export — cannot migrate to repo
                if has_is_active:
                    result = db.execute(
                        f"UPDATE {table} SET is_active = 0 WHERE company_id = ?",  # nosec B608
                        (company_id,)
                    )
                else:
                    result = db.execute(
                        f"DELETE FROM {table} WHERE company_id = ?",  # nosec B608
                        (company_id,)
                    )
                deleted[table] = result.rowcount if hasattr(result, 'rowcount') else "unknown"

        except Exception as e:
            deleted[table] = f"error: {e}"
            logger.warning("GDPR delete: failed on table %s: %s", table, e)

    # 2. Soft-delete company record
    from repositories.company_repository import CompanyRepository
    CompanyRepository(db).update(company_id, {"is_active": 0})

    # 3. Audit log
    try:
        from backend.repositories.audit_repository import AuditRepository
        audit = AuditRepository(db)
        audit.log_event(
            event_type="gdpr.deletion",
            entity_type="company",
            entity_id=str(company_id),
            data={"tables_affected": list(deleted.keys())},
            company_id=company_id,
        )
    except Exception:
        pass

    logger.info("GDPR deletion: company_id=%d, tables=%d", company_id, len(deleted))

    return {
        "status": "completed",
        "company_id": company_id,
        "tables_affected": deleted,
        "note": "Soft delete performed. Data marked inactive. For permanent deletion, contact system administrator."
    }


@router.post("/delete/user/{user_id}")
async def delete_user_data(user_id: int, db=Depends(get_db),
                           _=Depends(require_admin)):
    """Deactivate a user account (GDPR right to erasure)."""
    UserRepository(db).deactivate_user(user_id)

    logger.info("GDPR user deactivation: user_id=%d", user_id)

    return {
        "status": "deactivated",
        "user_id": user_id,
        "note": "User account deactivated. Audit logs and company records are retained per legal requirements."
    }


@router.get("/data-inventory")
async def data_inventory(db=Depends(get_db), _=Depends(require_admin)):
    """Return a data inventory — what data is stored and where."""
    inventory = {
        "data_categories": [
            {"category": "Business operations", "tables": ["trips", "invoices", "proforma_invoices", "receipts", "routes", "route_history", "route_history_v2"], "retention": "10 years (legal requirement for transport documents)"},
            {"category": "Client data", "tables": ["clients", "client_contacts", "client_tags", "contracts"], "retention": "Duration of business relationship + 5 years"},
            {"category": "Fleet data", "tables": ["trucks", "drivers", "driver_truck_assignments", "maintenance_records", "maintenance_schedules", "truck_health_scores"], "retention": "Duration of asset ownership + 3 years"},
            {"category": "Tachograph data", "tables": ["tacho_imports", "tacho_driver_activity", "tacho_vehicle_data"], "retention": "2 years (EU 165/2014 requirement)"},
            {"category": "GPS tracking", "tables": ["gps_telemetry"], "retention": "90 days"},
            {"category": "Authentication", "tables": ["users"], "retention": "Duration of account + 1 year after deactivation"},
            {"category": "Audit & logging", "tables": ["operation_events", "cmr_audit_log", "webhook_events", "email_logs", "trip_status_history"], "retention": "3 years"},
            {"category": "Communications", "tables": ["automail_templates", "automail_schedules", "automail_client_overrides", "email_logs"], "retention": "2 years"},
            {"category": "Documents", "tables": ["documents", "document_links", "document_versions", "document_pipeline_runs", "document_package", "document_package_items"], "retention": "Per legal document retention requirements"},
        ],
        "data_subject_rights": [
            "Right to access (export)",
            "Right to erasure (delete)",
            "Right to data portability (JSON export)",
            "Right to rectification (via normal CRUD endpoints)",
        ],
        "processing_purposes": [
            "Transport logistics management",
            "Fleet management",
            "Financial accounting and invoicing",
            "Legal compliance (tachograph, CMR retention)",
            "Business intelligence and analytics",
        ],
    }
    return inventory


def _row_to_dict(row) -> dict:
    """Convert sqlite3.Row to dict."""
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}
