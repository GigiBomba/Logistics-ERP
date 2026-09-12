"""World Model — structured operational snapshot service.

Read-optimized, typed view over Postgres. Rebuilt on demand or on short TTL.
Never written to directly. Aggregates and top-N only — never a substitute for a real query.

NOT built in Phase 0–3. The BaseTool/Reasoning Graph architecture must work correctly
without it first. This file is a contract stub — implementation in Phase 4.

Blueprint: §6
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class OpenProblem(BaseModel):
    """A problem the system has detected — overdue invoice, maintenance needed, HOS violation."""
    model_config = ConfigDict(extra="forbid")

    problem_type: str             # matches an insight_type from copilot_insights (§18)
    severity: Literal["low", "medium", "high", "critical"]
    summary_key: str              # i18n key
    summary_params: Dict[str, Any] = {}
    related_entity_ids: List[str] = []


class FleetSummary(BaseModel):
    """Aggregate fleet snapshot — counts only, never full vehicle list."""
    model_config = ConfigDict(extra="forbid")

    total_vehicles: int = 0
    available_count: int = 0
    in_maintenance_count: int = 0
    dispatched_count: int = 0


class DriverSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_drivers: int = 0
    available_count: int = 0
    on_trip_count: int = 0


class TripSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active_trips: int = 0
    completed_today: int = 0
    planned_tomorrow: int = 0


class DocumentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pending_ocr: int = 0
    expiring_soon: int = 0


class DispatchSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pending_dispatches: int = 0
    in_transit: int = 0


class MaintenanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overdue_count: int = 0
    due_soon_count: int = 0


class FinancialSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overdue_invoices: int = 0
    total_outstanding: float = 0.0
    currency: str = "EUR"


class NotificationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unread_count: int = 0
    critical_count: int = 0


class Objective(BaseModel):
    """A scheduled or approved proactive insight."""
    model_config = ConfigDict(extra="forbid")

    objective_id: str
    description_key: str
    description_params: Dict[str, Any] = {}
    status: str = "scheduled"


class WorldModelSnapshot(BaseModel):
    """Typed snapshot of the current operational state, rebuilt from real services."""
    model_config = ConfigDict(extra="forbid")

    company_id: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    ttl_seconds: int = 60          # short TTL — snapshot, not a cache the planner should trust for long
    fleet: FleetSummary = Field(default_factory=FleetSummary)
    drivers: DriverSummary = Field(default_factory=DriverSummary)
    trips: TripSummary = Field(default_factory=TripSummary)
    documents: DocumentSummary = Field(default_factory=DocumentSummary)
    dispatches: DispatchSummary = Field(default_factory=DispatchSummary)
    maintenance: MaintenanceSummary = Field(default_factory=MaintenanceSummary)
    financial: FinancialSummary = Field(default_factory=FinancialSummary)
    notifications: NotificationSummary = Field(default_factory=NotificationSummary)
    open_problems: List[OpenProblem] = []
    todays_objectives: List[Objective] = []


class WorldModelService:
    """Builds typed operational snapshots from existing services.

    The planner requests slices, not the whole snapshot —
    world_model_service.get_slice(company_id, sections=["fleet", "open_problems"]).
    """

    def __init__(self, db: Any) -> None:
        self._db = db

    def get_slice(
        self,
        company_id: int,
        sections: Optional[List[str]] = None,
    ) -> WorldModelSnapshot:
        """Build a WorldModelSnapshot with only the requested sections.

        Args:
            company_id: Tenant ID for multi-tenant isolation.
            sections: List of section keys to include. If None, returns all.
        """
        sections = sections or [
            "fleet", "drivers", "trips", "documents", "dispatches",
            "maintenance", "financial", "notifications", "open_problems",
        ]

        # The section builders delegate to repositories/services that read the
        # tenant scope from ``database.tenant_context`` contextvars — NOT from
        # mutable attributes on the shared DatabaseManager.  Scope the ambient
        # context around the builds (restoring the caller's prior company in a
        # ``finally``) so ``get_slice(company_id=N)`` queries company N's data
        # regardless of the caller's context, without leaking a different
        # tenant scope back to the caller.
        from database.tenant_context import get_company_id, set_company_context

        prev_company_id = get_company_id()
        # Keep the legacy attribute populated too — a few service paths (e.g.
        # FleetService.get_expenses) still read ``db.user_company_id``.
        if hasattr(self._db, "user_company_id"):
            self._db.user_company_id = company_id

        snapshot_kwargs: Dict[str, Any] = {
            "company_id": company_id,
            "generated_at": datetime.utcnow(),
            "ttl_seconds": 60,
        }

        section_builders = {
            "fleet": self._build_fleet_summary,
            "drivers": self._build_driver_summary,
            "trips": self._build_trip_summary,
            "documents": self._build_document_summary,
            "dispatches": self._build_dispatch_summary,
            "maintenance": self._build_maintenance_summary,
            "financial": self._build_financial_summary,
            "notifications": self._build_notification_summary,
            "open_problems": self._build_open_problems,
            "todays_objectives": self._build_todays_objectives,
        }

        try:
            set_company_context(company_id)
            for section in sections:
                builder = section_builders.get(section)
                if builder:
                    try:
                        snapshot_kwargs[section] = builder(company_id)
                    except Exception as e:
                        logger.warning("World Model section '%s' failed: %s", section, e)
        finally:
            set_company_context(prev_company_id)

        return WorldModelSnapshot(**snapshot_kwargs)

    def _build_fleet_summary(self, company_id: int = 0) -> FleetSummary:
        """Query FleetService for aggregate fleet stats."""
        try:
            from backend.services.fleet_service import FleetService
            svc = FleetService(self._db)
            result = svc.list_all()
            vehicles = result.data if hasattr(result, "success") and result.success else []
            total = len(vehicles) if isinstance(vehicles, list) else 0
            available = 0
            for v in (vehicles or []):
                if isinstance(v, dict):
                    status = v.get("status", "")
                else:
                    status = getattr(v, "status", "")
                if status == "active":
                    available += 1
            return FleetSummary(total_vehicles=total, available_count=available)
        except Exception:
            logger.warning("World Model fleet summary failed", exc_info=True)
        return FleetSummary()

    def _build_driver_summary(self, company_id: int = 0) -> DriverSummary:
        """Query the real ``drivers`` table for aggregate counts.

        The ``drivers`` table has no ``hours_worked`` / ``max_hours_per_day``
        columns — those exist only on the ``DriverResult`` DTO, which
        ``DriverTruckService.list_drivers()`` cannot build against the real
        schema.  The summary is therefore computed from the repository rows
        directly: total count, plus the real ``is_active`` column for the
        availability count.
        """
        try:
            from repositories.driver_repository import DriverRepository
            rows = DriverRepository(self._db).get_all()
            total = len(rows) if isinstance(rows, list) else 0
            available = sum(1 for r in (rows or []) if r.get("is_active"))
            return DriverSummary(total_drivers=total, available_count=available)
        except Exception:
            logger.warning("World Model driver summary failed", exc_info=True)
        return DriverSummary()

    def _build_trip_summary(self, company_id: int = 0) -> TripSummary:
        try:
            from backend.services.trip_service import TripService
            svc = TripService(self._db)
            result = svc.list_all(limit=500)
            trips = result.data if hasattr(result, "success") and result.success else []
            if isinstance(trips, list):
                now_str = datetime.now().strftime("%Y-%m-%d")
                active = 0
                completed_today = 0
                for t in trips:
                    if isinstance(t, dict):
                        status = t.get("status", "")
                        updated = t.get("updated_at", "")
                    else:
                        status = getattr(t, "status", "")
                        updated = getattr(t, "updated_at", None)
                    if status.lower() in ("loading", "in_transit", "delivering"):
                        active += 1
                    if status.lower() == "delivered" and updated is not None:
                        updated_str = str(updated)[:10] if not isinstance(updated, str) else updated[:10]
                        if updated_str == now_str:
                            completed_today += 1
                return TripSummary(active_trips=active, completed_today=completed_today)
        except Exception:
            logger.warning("World Model trip summary failed", exc_info=True)
        return TripSummary()

    def _build_document_summary(self, company_id: int = 0) -> DocumentSummary:
        """Documents awaiting OCR and those expiring within 14 days (§9.1)."""
        try:
            from datetime import datetime, timedelta

            from repositories.document_repository import DocumentRepository

            rows = DocumentRepository(self._db).search(query="", limit=500) or []
            pending = sum(1 for d in rows if not (d.get("ocr_run_at") or ""))
            today = datetime.now().date()
            soon = today + timedelta(days=14)
            expiring = 0
            for d in rows:
                exp = d.get("expiry_date") or ""
                if not exp:
                    continue
                try:
                    exp_dt = datetime.fromisoformat(str(exp)[:10]).date()
                except (TypeError, ValueError):
                    continue
                if today <= exp_dt <= soon:
                    expiring += 1
            return DocumentSummary(pending_ocr=pending, expiring_soon=expiring)
        except Exception:
            logger.warning("World Model document summary failed", exc_info=True)
        return DocumentSummary()

    def _build_dispatch_summary(self, company_id: int = 0) -> DispatchSummary:
        """Open dispatches and in-transit trips from the trips table."""
        try:
            from repositories.trip_repository import TripRepository

            rows = TripRepository(self._db).get_all(limit=500) or []
            pending = 0
            in_transit = 0
            for t in rows:
                status = str(t.get("status", "")).lower()
                if status in ("loading", "dispatched", "planned", "pending"):
                    pending += 1
                elif status in ("in_transit", "in transit", "delivering"):
                    in_transit += 1
            return DispatchSummary(pending_dispatches=pending, in_transit=in_transit)
        except Exception:
            logger.warning("World Model dispatch summary failed", exc_info=True)
        return DispatchSummary()

    def _build_maintenance_summary(self, company_id: int = 0) -> MaintenanceSummary:
        try:
            from backend.services.fleet_maintenance_service import FleetMaintenanceService
            svc = FleetMaintenanceService(self._db)
            summary = svc.get_summary()
            overdue = summary.get("overdue_count", 0) if isinstance(summary, dict) else 0
            due_soon = summary.get("due_soon_count", 0) if isinstance(summary, dict) else 0
            return MaintenanceSummary(overdue_count=overdue, due_soon_count=due_soon)
        except Exception:
            logger.warning("World Model maintenance summary failed", exc_info=True)
        return MaintenanceSummary()

    def _build_financial_summary(self, company_id: int = 0) -> FinancialSummary:
        try:
            from backend.services.analytics_service import AnalyticsService
            svc = AnalyticsService(self._db)
            data = svc.get_overdue_data()
            if isinstance(data, tuple) and len(data) >= 2:
                overdue_list, total = data[0], data[1]
                count = len(overdue_list) if isinstance(overdue_list, list) else 0
                return FinancialSummary(overdue_invoices=count, total_outstanding=float(total or 0))
        except Exception:
            logger.warning("World Model financial summary failed", exc_info=True)
        return FinancialSummary()

    def _build_notification_summary(self, company_id: int = 0) -> NotificationSummary:
        """Unresolved company alerts — unread count + critical/high subset.

        Reads the ``alerts`` table (company-scoped, ``resolved`` flag) — the
        same source the alert/notification surfaces use.
        """
        try:
            row = self._db.conn.execute(
                "SELECT COUNT(*) AS unread, "
                "COALESCE(SUM(CASE WHEN severity IN ('critical','high') THEN 1 ELSE 0 END), 0) AS critical "
                "FROM alerts WHERE company_id = ? AND resolved = 0",
                (company_id,),
            ).fetchone()
            if row:
                return NotificationSummary(
                    unread_count=int(row["unread"] or 0),
                    critical_count=int(row["critical"] or 0),
                )
        except Exception:
            logger.warning("World Model notification summary failed", exc_info=True)
        return NotificationSummary()

    def _build_open_problems(self, company_id: int = 0) -> List[OpenProblem]:
        problems: List[OpenProblem] = []
        try:
            financial = self._build_financial_summary(company_id)
            if financial.overdue_invoices > 0:
                problems.append(OpenProblem(
                    problem_type="overdue_invoices",
                    severity="high" if financial.overdue_invoices > 5 else "medium",
                    summary_key="copilot.world_model.overdue_invoices",
                    summary_params={"count": financial.overdue_invoices},
                ))
        except Exception:
            logger.warning("World Model open-problem financial build failed", exc_info=True)
        try:
            maint = self._build_maintenance_summary(company_id)
            if maint.overdue_count > 0:
                problems.append(OpenProblem(
                    problem_type="overdue_maintenance",
                    severity="high" if maint.overdue_count > 3 else "medium",
                    summary_key="copilot.world_model.overdue_maintenance",
                    summary_params={"count": maint.overdue_count},
                ))
        except Exception:
            logger.warning("World Model open-problem maintenance build failed", exc_info=True)
        return problems

    def _build_todays_objectives(self, company_id: int = 0) -> List[Objective]:
        return []
