"""Prometheus metrics for the Operion backend."""
from __future__ import annotations

import time
import logging
from typing import Callable
from fastapi import Request, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

from backend.services.slo_service import get_slo_service

logger = logging.getLogger(__name__)

# HTTP metrics
http_requests_total = Counter(
    "operion_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "operion_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Business metrics
trips_created_total = Counter(
    "operion_trips_created_total",
    "Total trips created"
)

invoices_generated_total = Counter(
    "operion_invoices_generated_total",
    "Total invoices generated"
)

documents_uploaded_total = Counter(
    "operion_documents_uploaded_total",
    "Total documents uploaded"
)

ocr_processed_total = Counter(
    "operion_ocr_processed_total",
    "Total OCR jobs processed",
    ["status"]  # success, failed
)

routes_calculated_total = Counter(
    "operion_routes_calculated_total",
    "Total routes calculated"
)

# System metrics
active_users_gauge = Gauge(
    "operion_active_users",
    "Number of active users"
)

active_trips_gauge = Gauge(
    "operion_active_trips",
    "Number of active trips"
)

db_connections_gauge = Gauge(
    "operion_db_connections",
    "Number of active database connections"
)

celery_tasks_pending = Gauge(
    "operion_celery_tasks_pending",
    "Number of pending Celery tasks"
)

# External API metrics
external_api_requests_total = Counter(
    "operion_external_api_requests_total",
    "Total external API calls",
    ["service", "status"]  # e.g., graphhopper, nominatim, timocom
)

external_api_duration_seconds = Histogram(
    "operion_external_api_duration_seconds",
    "External API call duration",
    ["service"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware that records HTTP metrics for Prometheus."""
    
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start
        endpoint = self._get_endpoint(request)
        
        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint
        ).observe(duration)

        # Record SLO for enterprise SLA tracking
        try:
            slo = get_slo_service()
            slo.record_request(response.status_code, duration * 1000)
        except Exception as exc:
            logger.warning("SLO recording failed: %s", exc)
        
        return response
    
    @staticmethod
    def _get_endpoint(request: Request) -> str:
        """Get a normalized endpoint path for metric labels."""
        path = request.url.path
        # Normalize IDs to avoid metric explosion
        parts = path.split("/")
        normalized = []
        for part in parts:
            if part.isdigit():
                normalized.append("{id}")
            elif len(part) == 36 and part.count("-") == 4:  # UUID
                normalized.append("{uuid}")
            else:
                normalized.append(part)
        return "/".join(normalized)


def get_metrics_response() -> Response:
    """Generate Prometheus metrics endpoint response."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
