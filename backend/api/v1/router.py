from __future__ import annotations

from fastapi import APIRouter

from backend.api.v1 import (
    admin,
    alerts,
    analytics,
    api_keys,
    auth,
    clients,
    cmr,
    copilot_router,
    dispatch,
    documents,
    drivers,
    feature_flags,
    fleet,
    freight_exchange,
    gdpr,
    health,
    invoices,
    maintenance,
    metrics,
    migration,
    mobile,
    oauth2,
    ocr,
    organizations,
    payments,
    receipts,
    registration,
    route_demo,
    routes,
    settings,
    slo,
    support,
    sync,
    tacho,
    trips,
    users,
    waitlist,
    webhooks,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(api_keys.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(ocr.router)
api_v1_router.include_router(organizations.router)
api_v1_router.include_router(trips.router)
api_v1_router.include_router(dispatch.router)
api_v1_router.include_router(clients.router)
api_v1_router.include_router(drivers.router)
api_v1_router.include_router(fleet.router)
api_v1_router.include_router(freight_exchange.router)
api_v1_router.include_router(routes.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(maintenance.router)
api_v1_router.include_router(metrics.router)
api_v1_router.include_router(migration.router)
api_v1_router.include_router(alerts.router)
api_v1_router.include_router(settings.router)
api_v1_router.include_router(tacho.router)
api_v1_router.include_router(invoices.router)
api_v1_router.include_router(cmr.router)
api_v1_router.include_router(copilot_router.router)
api_v1_router.include_router(receipts.router)
api_v1_router.include_router(registration.router)
api_v1_router.include_router(route_demo.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(oauth2.router)
api_v1_router.include_router(payments.router)
api_v1_router.include_router(feature_flags.router)
api_v1_router.include_router(gdpr.router)
api_v1_router.include_router(slo.router)
api_v1_router.include_router(support.router)
api_v1_router.include_router(sync.router)
api_v1_router.include_router(webhooks.router)
api_v1_router.include_router(waitlist.router)
api_v1_router.include_router(mobile.router)
# New mobile entity routers (blueprint §6) — mounted alongside the legacy
# mobile.py router; subpaths (/fleet, /drivers, …) do not collide with it.
api_v1_router.include_router(mobile.mobile_router)

