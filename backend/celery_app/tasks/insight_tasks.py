"""Proactive insight generation tasks (§18).

Each insight type runs as a scheduled background job. Jobs only INSERT
into copilot_insights — they never call BaseTool.execute() directly.

Blueprint: §18 — Proactive Operations Intelligence.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from backend.celery_app.celery import celery_app
from backend.config import BackendSettings
from database.tenant_context import set_company_context
from repositories.copilot_repository import CopilotInsightRepository
from repositories.company_repository import CompanyRepository

logger = logging.getLogger(__name__)

# ── Insight database helpers ────────────────────────────────────────────────

def _insert_insight(db, company_id: int, insight_type: str, severity: str,
                    payload: dict) -> None:
    """Insert a single insight into the copilot_insights table.

    ``CopilotInsightRepository.create`` uses ``INSERT OR IGNORE`` so retries
    after partial progress never duplicate a row (unique index
    ``idx_copilot_insights_dedup`` on ``(company_id, insight_type, payload)``).
    """
    CopilotInsightRepository(db).create({
        "company_id": company_id,
        "insight_type": insight_type,
        "severity": severity,
        "payload": json.dumps(payload),
    })


def _get_company_ids(db) -> list[int]:
    """Get all active company IDs."""
    return CompanyRepository(db).get_active_ids()


# ── Individual insight tasks ────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=2, default_retry_delay=300,
                 time_limit=900, soft_time_limit=840)
def maintenance_forecast_job(self) -> dict:
    """Identify trucks needing maintenance in the next 7 days."""
    from backend.db import DatabaseManager
    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        from backend.services.fleet_maintenance_service import FleetMaintenanceService
        svc = FleetMaintenanceService(db)
        companies = _get_company_ids(db)
        insights_created = 0
        errors = 0
        for company_id in companies:
            try:
                # TODO: migrate to repo when available (FleetRepository lacks is_active filter)
                trucks = db.conn.execute(
                    "SELECT id FROM trucks WHERE company_id = ? AND is_active = 1",
                    (company_id,),
                ).fetchall()
                for (truck_id,) in trucks:
                    upcoming = svc.predict_all_upcoming(truck_id, days_ahead=7)
                    for pred in upcoming:
                        if pred.get("overdue") or pred.get("remaining_days", 999) <= 7:
                            _insert_insight(db, company_id, "maintenance_forecast",
                                            "high" if pred.get("overdue") else "medium",
                                            {"truck_id": truck_id, "maint_type": pred.get("type"),
                                             "remaining_days": pred.get("remaining_days"),
                                             "overdue": pred.get("overdue")})
                            insights_created += 1
            except Exception as exc:
                errors += 1
                logger.warning("maintenance_forecast_job failed for company %s: %s", company_id, exc)
        logger.info("maintenance_forecast_job: %d insights created", insights_created)
        if errors:
            logger.warning("maintenance_forecast_job: %d company pass(es) failed", errors)
        return {"insights_created": insights_created}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300,
                 time_limit=900, soft_time_limit=840)
def overdue_invoice_job(self) -> dict:
    """Detect invoices past due date.

    Tenant-scoped: iterates active companies and filters ``invoices`` by
    ``company_id`` per pass so one job never reads another tenant's invoices.
    """
    from backend.db import DatabaseManager
    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        companies = _get_company_ids(db)
        insights_created = 0
        errors = 0
        for company_id in companies:
            try:
                set_company_context(company_id)
                # TODO: migrate to repo when available (InvoiceRepository lacks status+due_date filter)
                rows = db.conn.execute(
                    "SELECT id, company_id, client_name FROM invoices "
                    "WHERE status = 'sent' AND due_date < ? AND company_id = ?",
                    (today, company_id),
                ).fetchall()
                for invoice_id, inv_company_id, client_name in rows:
                    _insert_insight(db, inv_company_id, "overdue_invoice", "high",
                                    {"invoice_id": invoice_id, "client_name": client_name})
                    insights_created += 1
            except Exception as exc:
                errors += 1
                logger.warning("overdue_invoice_job failed for company %s: %s", company_id, exc)
        logger.info("overdue_invoice_job: %d insights created", insights_created)
        if errors:
            logger.warning("overdue_invoice_job: %d company pass(es) failed", errors)
        return {"insights_created": insights_created}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300,
                 time_limit=900, soft_time_limit=840)
def fleet_availability_job(self) -> dict:
    """Check fleet availability — vehicles in maintenance, low health scores."""
    from backend.db import DatabaseManager
    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        from backend.services.fleet_maintenance_service import FleetMaintenanceService
        svc = FleetMaintenanceService(db)
        companies = _get_company_ids(db)
        insights_created = 0
        errors = 0
        for company_id in companies:
            try:
                set_company_context(company_id)
                health_list = svc.get_all_health()
                for health in health_list:
                    score = getattr(health, 'score', 100)
                    if score < 50:
                        _insert_insight(db, company_id, "fleet_availability", "critical",
                                        {"truck_id": getattr(health, 'truck_id', 0),
                                         "health_score": score})
                        insights_created += 1
                    elif score < 70:
                        _insert_insight(db, company_id, "fleet_availability", "medium",
                                        {"truck_id": getattr(health, 'truck_id', 0),
                                         "health_score": score})
                        insights_created += 1
            except Exception as exc:
                errors += 1
                logger.warning("fleet_availability_job failed for company %s: %s", company_id, exc)
        logger.info("fleet_availability_job: %d insights created", insights_created)
        if errors:
            logger.warning("fleet_availability_job: %d company pass(es) failed", errors)
        return {"insights_created": insights_created}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300,
                 time_limit=900, soft_time_limit=840)
def fuel_cost_trend_job(self) -> dict:
    """Detect fuel cost trends — sharp increases or decreases."""
    from backend.db import DatabaseManager
    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        from backend.services.fuel_price_service import FuelPriceService
        svc = FuelPriceService()
        companies = _get_company_ids(db)
        insights_created = 0
        errors = 0
        for company_id in companies:
            try:
                price = svc.get_price_for_country("DEFAULT")
                if price and price > 2.0:
                    _insert_insight(db, company_id, "fuel_cost_trend", "medium",
                                    {"current_price": price, "trend": "high"})
                    insights_created += 1
            except Exception as exc:
                errors += 1
                logger.warning("fuel_cost_trend_job failed for company %s: %s", company_id, exc)
        logger.info("fuel_cost_trend_job: %d insights created", insights_created)
        if errors:
            logger.warning("fuel_cost_trend_job: %d company pass(es) failed", errors)
        return {"insights_created": insights_created}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300,
                 time_limit=900, soft_time_limit=840)
def return_load_matcher_job(self) -> dict:
    """Identify return load opportunities (trips with different origin/destination countries).

    Tenant-scoped: iterates active companies and filters ``trips`` by
    ``company_id`` per pass so one job never reads another tenant's trips.
    """
    from backend.db import DatabaseManager
    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        companies = _get_company_ids(db)
        insights_created = 0
        errors = 0
        for company_id in companies:
            try:
                set_company_context(company_id)
                # TODO: migrate to repo when available (TripRepository lacks status+updated_at filter)
                rows = db.conn.execute(
                    """SELECT id, company_id, loading_country, delivery_country 
                       FROM trips WHERE status = 'delivering' AND updated_at >= ?
                       AND company_id = ?""",
                    (f"{today}T00:00:00", company_id),
                ).fetchall()
                for trip_id, trip_company_id, loading_country, delivery_country in rows:
                    if (loading_country and delivery_country 
                        and loading_country.lower() != delivery_country.lower()):
                        _insert_insight(db, trip_company_id, "return_load_opportunity", "low",
                                        {"trip_id": trip_id, 
                                         "origin_country": loading_country,
                                         "destination_country": delivery_country})
                        insights_created += 1
            except Exception as exc:
                errors += 1
                logger.warning("return_load_matcher_job failed for company %s: %s", company_id, exc)
        logger.info("return_load_matcher_job: %d insights created", insights_created)
        if errors:
            logger.warning("return_load_matcher_job: %d company pass(es) failed", errors)
        return {"insights_created": insights_created}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300,
                 time_limit=900, soft_time_limit=840)
def driver_hours_forecast_job(self) -> dict:
    """Forecast drivers approaching HOS limits."""
    from backend.db import DatabaseManager
    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        from backend.services.tacho_service import TachoService
        svc = TachoService(db)
        companies = _get_company_ids(db)
        insights_created = 0
        errors = 0
        for company_id in companies:
            try:
                # Set company context for multi-tenant isolation
                set_company_context(company_id)

                summary = svc.get_fleet_summary(datetime.now().date())
                if hasattr(summary, 'success') and summary.success and summary.data:
                    for entry in summary.data:
                        # FleetTachoSummary has total_driving_hours and vehicle_id
                        hours_used = getattr(entry, 'total_driving_hours', 0) or 0
                        vehicle_id = getattr(entry, 'vehicle_id', None)
                        if hours_used > 8:
                            _insert_insight(db, company_id, "driver_hours_forecast", "high",
                                            {"vehicle_id": vehicle_id,
                                             "hours_used": hours_used})
                            insights_created += 1
            except Exception as exc:
                errors += 1
                logger.warning("driver_hours_forecast_job failed for company %s: %s", company_id, exc)
        logger.info("driver_hours_forecast_job: %d insights created", insights_created)
        if errors:
            logger.warning("driver_hours_forecast_job: %d company pass(es) failed", errors)
        return {"insights_created": insights_created}
    finally:
        db.close()


# ── Workflow struggle job (§18, §34.9) ──────────────────────────────────────
# Data source: the app's struggle signal.  The UI ``StruggleDetector``
# (``ui/copilot/controllers/struggle_detector.py``) emits
# ``struggle_detected(workflow_id, tooltip_key)`` and logs
# "Struggle detected: screen=... workflow=..." client-side.  It is never
# persisted to a dedicated table — the backend-recorded analogue is the §34.9
# abandonment signal already computed by the observability panel from
# ``copilot_audit_log``: a conversation that started a tool execution
# (``status='running'`` / ``action='tool_execution_start'``) but never reached
# a terminal status within the window.  This job aggregates that same signal
# per company and, when a workflow crosses the abandonment threshold, writes a
# ``copilot_insights`` row for the Review/Approve/Dismiss queue.

STRUGGLE_WINDOW_DAYS = 7          # look back window for abandoned workflows
STRUGGLE_THRESHOLD = 3            # min abandoned conversations per workflow
STRUGGLE_HIGH_THRESHOLD = 6       # ≥ this many → severity "high"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300,
                 time_limit=900, soft_time_limit=840)
def workflow_struggle_job(self) -> dict:
    """Detect workflows with high abandonment and surface a proactive nudge.

    Aggregates the §34.9 abandonment signal from ``copilot_audit_log`` per
    active company: conversations that started a tool execution in the recent
    window but never finished it.  A workflow whose abandoned-conversation
    count crosses ``STRUGGLE_THRESHOLD`` gets a ``workflow_struggle`` insight.

    Tenant-scoped: ``set_company_context`` + a per-pass ``company_id`` filter
    keep one job pass from ever reading another tenant's audit rows.
    """
    from backend.db import DatabaseManager
    config = BackendSettings()
    db = DatabaseManager(config.db_path)
    try:
        since = (datetime.now() - timedelta(days=STRUGGLE_WINDOW_DAYS)).isoformat()
        companies = _get_company_ids(db)
        insights_created = 0
        errors = 0
        for company_id in companies:
            try:
                set_company_context(company_id)
                # Abandoned conversations: started (status/action) but with no
                # terminal row in the window.  Handles both the SQLite
                # ``status``-column schema and the ``action``-column schema the
                # observability panel already tolerates.
                rows = db.conn.execute(
                    """SELECT tool_name, COUNT(DISTINCT conversation_id) AS abandoned_count
                       FROM copilot_audit_log t
                       WHERE company_id = ?
                         AND created_at >= ?
                         AND conversation_id IS NOT NULL AND conversation_id != ''
                         AND (status = 'running' OR action = 'tool_execution_start')
                         AND NOT EXISTS (
                             SELECT 1 FROM copilot_audit_log t2
                             WHERE t2.company_id = ?
                               AND t2.conversation_id = t.conversation_id
                               AND t2.created_at >= ?
                               AND (t2.status IN ('succeeded', 'failed', 'skipped')
                                    OR t2.action IN ('tool_execution_succeeded',
                                                     'tool_execution_failed'))
                         )
                         AND tool_name IS NOT NULL AND tool_name != ''
                       GROUP BY tool_name
                       HAVING COUNT(DISTINCT conversation_id) >= ?""",
                    (company_id, since, company_id, since, STRUGGLE_THRESHOLD),
                ).fetchall()
                for tool_name, abandoned_count in rows:
                    workflow_id = tool_name  # tool = the workflow the user attempted
                    _insert_insight(
                        db,
                        company_id,
                        "workflow_struggle",
                        "high" if abandoned_count >= STRUGGLE_HIGH_THRESHOLD else "medium",
                        {
                            "workflow_id": workflow_id,
                            "tool_name": tool_name,
                            "abandoned_count": abandoned_count,
                            "window_days": STRUGGLE_WINDOW_DAYS,
                        },
                    )
                    insights_created += 1
            except Exception as exc:
                errors += 1
                logger.warning("workflow_struggle_job failed for company %s: %s", company_id, exc)
        logger.info("workflow_struggle_job: %d insights created", insights_created)
        if errors:
            logger.warning("workflow_struggle_job: %d company pass(es) failed", errors)
        return {"insights_created": insights_created}
    finally:
        db.close()


# ── Consolidation task ──────────────────────────────────────────────────────

@celery_app.task(time_limit=1800, soft_time_limit=1740)
def generate_all_insights() -> dict:
    """Run all insight generation tasks sequentially."""
    results = {
        "maintenance": maintenance_forecast_job.delay(),
        "overdue_invoices": overdue_invoice_job.delay(),
        "fleet_availability": fleet_availability_job.delay(),
        "fuel_cost_trend": fuel_cost_trend_job.delay(),
        "return_load_matcher": return_load_matcher_job.delay(),
        "driver_hours_forecast": driver_hours_forecast_job.delay(),
    }
    return {k: v.id for k, v in results.items()}
