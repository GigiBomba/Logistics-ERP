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

@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
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


# ── Consolidation task ──────────────────────────────────────────────────────

@celery_app.task
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
