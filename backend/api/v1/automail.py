"""AutoMail API router — remote CRUD for templates, schedules, settings,
reminder timeline, and manual email actions.

Mirrors the operations performed locally by ``AutoMailRepository``,
``ReminderService``, and ``HistoryService`` so the remote-mode client
(``client.remote_automail.RemoteAutoMailService``) can drive the AutoMail
panels against the backend.
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.schemas.automail import (
    AutomailManualSend,
    AutomailScheduleCreate,
    AutomailScheduleUpdate,
    AutomailSchedulesReorder,
    AutomailSendNow,
    AutomailSendTest,
    AutomailSettingUpdate,
    AutomailTemplateCreate,
    AutomailTemplateUpdate,
    AutomailTripRef,
)
from database.db_manager import DatabaseManager
from repositories.automail_repository import AutoMailRepository

logger = logging.getLogger("api.automail")

router = APIRouter(prefix="/automail", tags=["automail"])


def _repo(db: DatabaseManager) -> AutoMailRepository:
    return AutoMailRepository(db)


# ── Templates ──────────────────────────────────────────────────────────


@router.get("/templates")
def list_templates(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    items = _repo(db).get_all_templates()
    return {"items": items, "total": len(items)}


@router.get("/templates/{template_id}")
def get_template(
    template_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    template = _repo(db).get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.post("/templates", response_model=Dict[str, int])
def create_template(
    data: AutomailTemplateCreate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    template_id = _repo(db).create_template(data.model_dump(exclude_unset=True))
    return {"id": template_id}


@router.put("/templates/{template_id}")
def update_template(
    template_id: int,
    data: AutomailTemplateUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    _repo(db).update_template(template_id, fields)
    return {"status": "updated"}


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    _repo(db).delete_template(template_id)
    return {"status": "deleted"}


# ── Schedules ──────────────────────────────────────────────────────────


@router.get("/schedules")
def list_schedules(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    active_only: bool = False,
    db: DatabaseManager = Depends(get_db),
):
    repo = _repo(db)
    items = repo.get_active_schedules() if active_only else repo.get_all_schedules()
    return {"items": items, "total": len(items)}


@router.get("/schedules/{schedule_id}")
def get_schedule(
    schedule_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    schedule = _repo(db).get_schedule_by_id(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.post("/schedules", response_model=Dict[str, int])
def create_schedule(
    data: AutomailScheduleCreate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    schedule_id = _repo(db).create_schedule(data.model_dump(exclude_unset=True))
    return {"id": schedule_id}


@router.put("/schedules/{schedule_id}")
def update_schedule(
    schedule_id: int,
    data: AutomailScheduleUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    _repo(db).update_schedule(schedule_id, fields)
    return {"status": "updated"}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    _repo(db).delete_schedule(schedule_id)
    return {"status": "deleted"}


@router.post("/schedules/reorder")
def reorder_schedules(
    data: AutomailSchedulesReorder,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    _repo(db).reorder_schedules(data.ids)
    return {"status": "reordered"}


# ── Settings ───────────────────────────────────────────────────────────


@router.get("/settings")
def get_all_settings(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    return _repo(db).get_all_settings()


@router.put("/settings/{key}")
def set_setting(
    key: str,
    data: AutomailSettingUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    _repo(db).set_setting(key, data.value)
    return {"status": "saved", "key": key, "value": data.value}


# ── Reminder timeline / manual controls ────────────────────────────────


@router.get("/reminders/status")
def reminder_status(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    page: int = 0,
    search: str = "",
    status_filter: str = "",
    limit: int = 20,
    db: DatabaseManager = Depends(get_db),
):
    from services.automail.reminder_service import ReminderService

    try:
        entries, total = ReminderService(db).get_reminder_status_for_all_active(
            page=page, search=search, status_filter=status_filter, limit=limit,
        )
    except Exception as exc:
        logger.exception("reminder_status failed: %s", exc)
        entries, total = [], 0
    return {"items": entries, "total": total}


@router.post("/reminders/{invoice_id}/skip")
def skip_reminder(
    invoice_id: int,
    data: AutomailTripRef,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.automail.reminder_service import ReminderService

    ok = ReminderService(db).skip_next_reminder(invoice_id, data.trip_id or 0)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to skip reminder")
    return {"status": "skipped"}


@router.post("/reminders/{invoice_id}/cancel-all")
def cancel_reminders(
    invoice_id: int,
    data: AutomailTripRef,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.automail.reminder_service import ReminderService

    ok = ReminderService(db).cancel_all_reminders(invoice_id, data.trip_id or 0)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to cancel reminders")
    return {"status": "cancelled"}


@router.post("/reminders/{invoice_id}/manual-send")
def log_manual_send(
    invoice_id: int,
    data: AutomailManualSend,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    _repo(db).log_manual_send(invoice_id, data.trip_id or 0, data.recipient)
    return {"status": "logged"}


@router.post("/reminders/{invoice_id}/send-now")
def send_reminder_now(
    invoice_id: int,
    data: AutomailSendNow,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    """Send the next unscheduled reminder for an invoice immediately.

    Mirrors the local ``_InvoiceTimelineCard._on_send_now`` flow: pick the
    next scheduled entry, render the template, attach the trip documents,
    and dispatch through the server-side NotificationCenter.
    """
    from services.automail.reminder_service import ReminderService
    from services.automail.template_service import TemplateService
    from services.document_automation.package_builder import PackageBuilder
    from services.operations.notification_center import NotificationCenter
    from services.preferences import PreferencesManager

    repo = _repo(db)
    schedules = repo.get_active_schedules()
    if not schedules:
        raise HTTPException(status_code=400, detail="No active reminder schedules")

    invoices = repo.get_unpaid_invoices_for_reminders()
    inv = next((i for i in invoices if i.get("invoice_id") == invoice_id), None)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    trip_id = int(data.trip_id) if data.trip_id else (int(inv["trip_id"]) if inv.get("trip_id") else 0)
    recipient = (data.recipient or "").strip() or (inv.get("client_email") or "").strip()
    if not recipient:
        raise HTTPException(status_code=400, detail="No recipient email address")

    # Pick the next unscheduled schedule for this invoice (same as the card).
    sched = schedules[0]
    try:
        timeline = ReminderService(db).get_reminder_status_for_invoice(
            invoice_id=invoice_id,
            invoice_due_date=inv.get("due_date", ""),
            trip_id=trip_id,
            client_id=inv.get("client_id"),
        )
        for entry in timeline:
            if entry.get("status") == "scheduled":
                sid = entry.get("schedule_id")
                for s in schedules:
                    if s["id"] == sid:
                        sched = s
                        break
                break
    except Exception:
        logger.exception("Failed to compute reminder timeline for send-now")

    template = repo.get_template_by_id(sched["template_id"])
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    from services.invoicing.config_manager import load_company_config

    total_amount_val = inv.get("total_amount") or 0
    ctx = {
        "invoice_number": inv.get("invoice_number", ""),
        "total_amount": f"{total_amount_val:,.2f}",
        "currency": inv.get("currency", "EUR"),
        "due_date": inv.get("due_date", ""),
        "days_overdue": "0",
        "company_name": load_company_config().get("company_name", "Operion ERP"),
        "client_name": inv.get("client_name", ""),
        "client_contact": "",
        "trip_id": str(trip_id or ""),
        "truck_plate": "",
        "driver_name": "",
    }
    subject, body_text, body_html = TemplateService(db).render_email(template, ctx)
    has_html = bool(body_html and body_html.strip())

    builder = PackageBuilder(db)
    docs = builder.list_trip_documents(trip_id) if trip_id else []
    paths = [
        d["file_path"] for d in docs
        if d.get("file_path") and os.path.isfile(d["file_path"])
    ]

    cfg = PreferencesManager(db).get_smtp_config()
    if not cfg.get("smtp_server") or not cfg.get("smtp_user"):
        raise HTTPException(status_code=400, detail="SMTP not configured")

    nc = NotificationCenter(db)
    nc.configure_smtp(
        cfg.get("smtp_server", ""),
        int(cfg.get("smtp_port", "587")),
        cfg.get("smtp_user", ""),
        cfg.get("smtp_password", ""),
    )

    ok = nc.send_email(
        to_address=recipient,
        subject=subject,
        body=body_html if has_html else body_text,
        attachments=paths,
        html=has_html,
        trip_id=trip_id,
    )
    if ok:
        repo.log_manual_send(invoice_id, trip_id, recipient)
        return {"status": "sent", "recipient": recipient}
    return {"status": "failed", "detail": "Email sending failed"}


# ── Stats ──────────────────────────────────────────────────────────────


@router.get("/stats")
def automail_stats(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.automail.history_service import HistoryService

    try:
        return HistoryService(db).get_stats()
    except Exception as exc:
        logger.exception("automail_stats failed: %s", exc)
        return {"emails_sent": 0, "emails_failed": 0, "total_outstanding_amount": 0}


# ── Test email ─────────────────────────────────────────────────────────


@router.post("/send-test")
def send_test_email(
    data: AutomailSendTest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    from services.operations.notification_center import NotificationCenter
    from services.preferences import PreferencesManager

    if not data.recipient:
        raise HTTPException(status_code=400, detail="Recipient email is required")

    cfg = PreferencesManager(db).get_smtp_config()
    if not cfg.get("smtp_server") or not cfg.get("smtp_user"):
        raise HTTPException(status_code=400, detail="SMTP not configured")

    nc = NotificationCenter(db)
    nc.configure_smtp(
        cfg.get("smtp_server", ""),
        int(cfg.get("smtp_port", "587")),
        cfg.get("smtp_user", ""),
        cfg.get("smtp_password", ""),
    )
    ok = nc.send_email(
        to_address=data.recipient,
        subject=data.subject or "Test Email",
        body=data.body or "This is a test email from the AutoMail editor.",
        html=data.html,
    )
    if ok:
        return {"status": "sent"}
    return {"status": "failed", "detail": "Email sending failed"}
