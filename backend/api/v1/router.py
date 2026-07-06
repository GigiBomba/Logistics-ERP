from fastapi import APIRouter

from backend.api.v1 import (
    admin,
    alerts,
    analytics,
    auth,
    clients,
    cmr,
    documents,
    drivers,
    fleet,
    health,
    invoices,
    maintenance,
    ocr,
    receipts,
    routes,
    settings,
    tacho,
    trips,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(ocr.router)
api_v1_router.include_router(trips.router)
api_v1_router.include_router(clients.router)
api_v1_router.include_router(drivers.router)
api_v1_router.include_router(fleet.router)
api_v1_router.include_router(routes.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(maintenance.router)
api_v1_router.include_router(alerts.router)
api_v1_router.include_router(settings.router)
api_v1_router.include_router(tacho.router)
api_v1_router.include_router(invoices.router)
api_v1_router.include_router(cmr.router)
api_v1_router.include_router(receipts.router)
