"""SLO/SLA tracking service for enterprise readiness."""
from __future__ import annotations

import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class SloMetric:
    """A single SLO metric."""
    name: str
    target: float  # e.g., 99.9 for 99.9%
    window_hours: int  # measurement window
    total: int = 0
    good: int = 0
    current_slo: float = 100.0
    last_reset: Optional[datetime] = None


class SloService:
    """Tracks Service Level Objectives (SLOs) and reports SLA metrics."""

    def __init__(self):
        self._metrics: dict[str, SloMetric] = {
            "api_availability": SloMetric(
                name="api_availability",
                target=99.9,  # 99.9% uptime
                window_hours=720,  # 30 days
            ),
            "api_latency_p99": SloMetric(
                name="api_latency_p99",
                target=99.0,  # 99% of requests under 2s
                window_hours=168,  # 7 days
            ),
            "webhook_delivery": SloMetric(
                name="webhook_delivery",
                target=99.5,  # 99.5% successful webhook processing
                window_hours=168,
            ),
            "route_calculation": SloMetric(
                name="route_calculation",
                target=95.0,  # 95% within 5s
                window_hours=168,
            ),
        }
        self._uptime_start = datetime.now()

    def record_request(self, status_code: int, duration_ms: float):
        """Record an API request for availability and latency SLOs."""
        # Availability: any non-5xx is "good"
        avail = self._metrics["api_availability"]
        avail.total += 1
        if status_code < 500:
            avail.good += 1
        avail.current_slo = self._compute_slo(avail)

        # Latency: p99 under 2000ms
        latency = self._metrics["api_latency_p99"]
        latency.total += 1
        if duration_ms < 2000:
            latency.good += 1
        latency.current_slo = self._compute_slo(latency)

    def record_webhook(self, success: bool):
        """Record a webhook processing result."""
        metric = self._metrics["webhook_delivery"]
        metric.total += 1
        if success:
            metric.good += 1
        metric.current_slo = self._compute_slo(metric)

    def record_route_calculation(self, duration_ms: float):
        """Record a route calculation result."""
        metric = self._metrics["route_calculation"]
        metric.total += 1
        if duration_ms < 5000:
            metric.good += 1
        metric.current_slo = self._compute_slo(metric)

    def _compute_slo(self, metric: SloMetric) -> float:
        """Compute current SLO percentage."""
        if metric.total == 0:
            return 100.0
        return round((metric.good / metric.total) * 100, 2)

    def get_report(self) -> dict:
        """Generate SLO/SLA report."""
        now = datetime.now()
        uptime_hours = (now - self._uptime_start).total_seconds() / 3600

        metrics_report = {}
        for key, metric in self._metrics.items():
            metrics_report[key] = {
                "name": metric.name,
                "target_pct": metric.target,
                "current_pct": metric.current_slo,
                "within_target": metric.current_slo >= metric.target,
                "total_events": metric.total,
                "good_events": metric.good,
                "window_hours": metric.window_hours,
            }

        return {
            "uptime_hours": round(uptime_hours, 1),
            "uptime_since": self._uptime_start.isoformat(),
            "slo_metrics": metrics_report,
            "overall_status": "healthy" if all(
                m["within_target"] for m in metrics_report.values()
            ) else "degraded",
        }

    def get_status_page(self) -> dict:
        """Generate a public-facing status page response."""
        report = self.get_report()

        return {
            "status": report["overall_status"],
            "uptime_percentage": f"{report['slo_metrics']['api_availability']['current_pct']}%",
            "services": {
                "api": {
                    "status": "operational" if report["slo_metrics"]["api_availability"]["within_target"] else "degraded",
                    "slo": f"{report['slo_metrics']['api_availability']['current_pct']}% (target: {report['slo_metrics']['api_availability']['target_pct']}%)",
                },
                "webhooks": {
                    "status": "operational" if report["slo_metrics"]["webhook_delivery"]["within_target"] else "degraded",
                    "slo": f"{report['slo_metrics']['webhook_delivery']['current_pct']}%",
                },
                "routing": {
                    "status": "operational" if report["slo_metrics"]["route_calculation"]["within_target"] else "degraded",
                    "slo": f"{report['slo_metrics']['route_calculation']['current_pct']}%",
                },
            },
            "updated_at": datetime.now().isoformat(),
        }


# Global singleton for the SLO service
_slo_service = SloService()


def get_slo_service() -> SloService:
    return _slo_service
