from fastapi import APIRouter, Depends

from backend.api.v1 import (
    admin,
    alerts,
    analytics,
    api_keys,
    auth,
    automail,
    avatars,
    blog,
    clients,
    cmr,
    company,
    contact,
    content_pages,
    documents,
    drivers,
    emails,
    feature_flags,
    fleet,
    gdpr,
    health,
    invoices,
    licenses,
    maintenance,
    mfa,
    mobile,
    oauth2,
    ocr,
    organizations,
    packages,
    platform_services,
    proformas,
    receipts,
    registration,
    route_demo,
    routes,
    settings,
    slo,
    subscriptions,
    support,
    tacho,
    trips,
    users,
    waitlist,
    webhooks,
    webhooks_stripe,
)
from backend.dependencies_security import require_active_subscription

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(mfa.mfa_router)
api_v1_router.include_router(mfa.mfa_me_router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(api_keys.router)
api_v1_router.include_router(content_pages.router)
# ── ERP operational surface — trial-gated (audit F1 enforcement) ─────────
# Expired-trial companies get 402 on these routers; billing/support/
# license/org/company endpoints stay open so locked users can pay/upgrade.
api_v1_router.include_router(
    documents.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    ocr.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    trips.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    clients.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    drivers.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    fleet.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    routes.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    analytics.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    maintenance.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    alerts.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    tacho.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    invoices.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    cmr.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    receipts.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    automail.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    emails.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    packages.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    mobile.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(
    proformas.router, dependencies=[Depends(require_active_subscription)]
)
api_v1_router.include_router(settings.router)
api_v1_router.include_router(registration.router)
api_v1_router.include_router(route_demo.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(oauth2.router)
api_v1_router.include_router(feature_flags.router)
api_v1_router.include_router(gdpr.router)
api_v1_router.include_router(slo.router)
api_v1_router.include_router(webhooks_stripe.router)
api_v1_router.include_router(webhooks.router)
api_v1_router.include_router(waitlist.router)
api_v1_router.include_router(avatars.router)
api_v1_router.include_router(contact.router)
api_v1_router.include_router(platform_services.router)
# ── Website-facing routers (billing/org/license/support/company/blog) ───
# Left ungated so locked companies can still manage billing, team,
# licenses, support tickets and read public content.
api_v1_router.include_router(subscriptions.router)
api_v1_router.include_router(organizations.router)
api_v1_router.include_router(licenses.router)
api_v1_router.include_router(support.router)
api_v1_router.include_router(company.router)
api_v1_router.include_router(blog.router)
