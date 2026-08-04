"""MobileAnalyticsAggregator — reshapes desktop analytics into compact fl_chart JSON.

Blueprint §6.4 / §4.4 contract: a *new mobile-facing aggregation layer* that
must NOT simply proxy the desktop Plotly-data-shaped responses.  Each method
returns small, pre-aggregated JSON suited to ``fl_chart`` inputs.

Every method scopes its queries to ``company_id`` by setting the tenant
context (``database.tenant_context.set_company_context``) — the desktop
``AnalyticsService``/``AnalyticsRepository`` derive their company filter from
that contextvar (not from a passed argument), so the HTTP handler must set it
before the repository runs.  We set it defensively here too so the aggregator
is also safe to call from background tasks / REPL.

Data sources (all real, none invented):
  - revenue          → get_financial_analytics / get_revenue_by_client / get_route_profitability
  - fleet_utilization→ trucks.status real strings + get_truck_utilization
  - driver_performance → get_driver_comparison + per-driver OTD (get_driver_otd)
  - invoice_aging    → get_invoice_aging (exact bucket mapping)

NOT available (recorded, REAL WINS): driver ``rating`` — no column exists
anywhere; the mobile Driver Performance rows therefore carry
trips_completed/on_time_pct/profit_per_km/revenue only.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from database.tenant_context import set_company_context

logger = logging.getLogger(__name__)

# Map the real trucks.status strings onto the compact mobile keys.
_STATUS_SPLIT_KEYS = {
    "Active": "active",
    "In Service": "maintenance",
    "Inactive": "decommissioned",
}


class MobileAnalyticsAggregator:
    """Compact fl_chart-friendly analytics shapes for the mobile app."""

    def __init__(self, db):
        self.db = db
        from repositories.analytics_repository import AnalyticsRepository
        from services.analytics_service import AnalyticsService

        self._service = AnalyticsService(db)
        self._repo = AnalyticsRepository(db)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _scope(self, company_id: int) -> None:
        """Pin the tenant context so repository company filters apply."""
        if company_id:
            set_company_context(company_id)

    @staticmethod
    def _num(value: Any, default: float = 0.0) -> float:
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _int(value: Any, default: int = 0) -> int:
        try:
            return int(value or default)
        except (TypeError, ValueError):
            return default

    # ── Revenue (§6.4) ────────────────────────────────────────────────────

    def revenue(
        self,
        company_id: int,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        group_by: str = "period",
    ) -> Dict[str, Any]:
        """Revenue line + bar-chart inputs.

        ``trend``     → monthly revenue (get_financial).
        ``per_client``→ revenue per client (get_revenue_by_client).
        ``per_route`` → avg profit per route (get_route_profitability).

        ``group_by`` is accepted for contract parity; all three sections are
        always returned (the client picks which to render).
        """
        self._scope(company_id)
        financial = self._service.get_financial(
            company_id=company_id, from_date=from_date, to_date=to_date
        ) or []
        trend = [
            {"label": r.get("month") or "", "value": self._num(r.get("revenue"))}
            for r in financial
            if isinstance(r, dict)
        ]

        clients = self._service.get_revenue_by_client(
            company_id=company_id, from_date=from_date, to_date=to_date
        ) or []
        per_client = [
            {
                "label": r.get("client") or "Unknown",
                "value": self._num(r.get("revenue")),
            }
            for r in clients
            if isinstance(r, dict)
        ]

        routes = self._service.get_route_profitability(
            company_id=company_id, from_date=from_date, to_date=to_date
        ) or []
        per_route = [
            {
                "label": r.get("route_label") or "Route",
                # Route "profitability" value = average profit per route (the
                # desktop metric that actually ranks routes).
                "value": self._num(r.get("avg_profit")),
            }
            for r in routes
            if isinstance(r, dict)
        ]

        return {"trend": trend, "per_client": per_client, "per_route": per_route}

    # ── Fleet utilization (§6.4) ──────────────────────────────────────────

    def fleet_utilization(
        self,
        company_id: int,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fleet status split + per-truck utilization.

        ``status_split`` counts real trucks.status strings
        ('Active'/'In Service'/'Inactive' → active/maintenance/decommissioned);
        soft-deleted trucks (deleted_at set) are excluded.
        ``trucks`` is the desktop get_truck_utilization output (no date-range
        support in the source query — documented limitation).
        """
        self._scope(company_id)
        status_split = {"active": 0, "maintenance": 0, "decommissioned": 0}
        try:
            rows = self.db.execute(
                "SELECT status, COUNT(*) AS cnt FROM trucks "
                "WHERE company_id = ? AND (deleted_at IS NULL OR deleted_at = '') "
                "GROUP BY status",
                (company_id,),
            ).fetchall()
            for r in rows:
                key = _STATUS_SPLIT_KEYS.get((r["status"] or "").strip())
                if key is not None:
                    status_split[key] += self._int(r["cnt"])
        except Exception as exc:  # pragma: no cover - defensive (deleted_at may not exist)
            logger.warning("fleet_utilization status split failed: %s", exc)

        trucks = self._service.get_truck_utilization() or []
        truck_list = [
            {
                "truck": r.get("truck") or "",
                "trip_count": self._int(r.get("trip_count")),
                "total_km": self._num(r.get("total_km")),
            }
            for r in trucks
            if isinstance(r, dict)
        ]
        return {"status_split": status_split, "trucks": truck_list}

    # ── Driver performance (§6.4) ─────────────────────────────────────────

    def driver_performance(
        self,
        company_id: int,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Per-driver performance rows for a sortable DataTable.

        Fields: driver, trips_completed, on_time_pct, profit_per_km, revenue.
        NO ``rating`` — the column does not exist anywhere in the schema
        (recorded; REAL WINS).
        """
        self._scope(company_id)
        rows = self._service.get_driver_comparison(
            company_id=company_id, from_date=from_date, to_date=to_date
        ) or []
        otd = self._repo.get_driver_otd(from_date, to_date) or {}
        out: List[Dict[str, Any]] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            driver = r.get("driver") or ""
            out.append(
                {
                    "driver": driver,
                    "trips_completed": self._int(r.get("trip_count")),
                    "on_time_pct": self._num(otd.get(driver), 0.0),
                    "profit_per_km": self._num(r.get("profit_per_km")),
                    "revenue": self._num(r.get("revenue")),
                }
            )
        return {"rows": out}

    # ── Invoice aging (§6.4) ──────────────────────────────────────────────

    def invoice_aging(self, company_id: int) -> Dict[str, Any]:
        """Invoice aging buckets (exact mapping of get_invoice_aging).

        current_bucket → current, bucket_31_60 → bucket_31_60,
        bucket_61_90 → bucket_61_90, overdue_bucket → overdue,
        total_outstanding → total_outstanding.
        """
        self._scope(company_id)
        row = self._service.get_invoice_aging() or {}
        return {
            "current": self._num(row.get("current_bucket")),
            "bucket_31_60": self._num(row.get("bucket_31_60")),
            "bucket_61_90": self._num(row.get("bucket_61_90")),
            "overdue": self._num(row.get("overdue_bucket")),
            "total_outstanding": self._num(row.get("total_outstanding")),
        }

    # ── CSV serialization for GET /mobile/analytics/export ────────────────

    def to_csv(self, report: str, company_id: int,
               from_date: Optional[str] = None, to_date: Optional[str] = None) -> str:
        """Render an analytics report as a small CSV string (sync export)."""
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")

        if report == "revenue":
            data = self.revenue(company_id, from_date, to_date)
            writer.writerow(["month", "revenue"])
            for p in data["trend"]:
                writer.writerow([p["label"], p["value"]])
            writer.writerow([])
            writer.writerow(["client", "revenue"])
            for p in data["per_client"]:
                writer.writerow([p["label"], p["value"]])
        elif report == "fleet":
            data = self.fleet_utilization(company_id, from_date, to_date)
            writer.writerow(["status", "count"])
            for key, value in data["status_split"].items():
                writer.writerow([key, value])
            writer.writerow([])
            writer.writerow(["truck", "trip_count", "total_km"])
            for t in data["trucks"]:
                writer.writerow([t["truck"], t["trip_count"], t["total_km"]])
        elif report == "drivers":
            data = self.driver_performance(company_id, from_date, to_date)
            writer.writerow(["driver", "trips_completed", "on_time_pct", "profit_per_km", "revenue"])
            for r in data["rows"]:
                writer.writerow([
                    r["driver"], r["trips_completed"], r["on_time_pct"],
                    r["profit_per_km"], r["revenue"],
                ])
        elif report == "invoice_aging":
            data = self.invoice_aging(company_id)
            writer.writerow(["bucket", "amount"])
            for key in ("current", "bucket_31_60", "bucket_61_90", "overdue", "total_outstanding"):
                writer.writerow([key, data[key]])
        else:
            raise ValueError(f"Unknown analytics report: {report!r}")

        return buf.getvalue()
