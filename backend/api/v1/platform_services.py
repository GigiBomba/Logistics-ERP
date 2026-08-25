"""Platform service endpoints — mixed DB + hardcoded data.

POST   /newsletter/subscribe       — Subscribe email
POST   /newsletter/unsubscribe     — Unsubscribe email
GET    /search                     — Global search
GET    /integrations               — Integration catalog
GET    /integrations/:id           — Single integration
GET    /security/reports           — Security reports (hardcoded)
POST   /security/reports           — Submit security report
GET    /notifications              — User notifications
POST   /notifications/:id/read    — Mark read
POST   /notifications/read-all    — Mark all read
GET    /notifications/preferences    — Get prefs
PATCH  /notifications/preferences   — Update prefs
GET    /onboarding/checklist       — Onboarding checklist
POST   /onboarding/steps/:stepId/complete — Complete step
"""
from __future__ import annotations


import json
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.dependencies import get_db
from backend.dependencies_security import get_current_user, require_dispatcher
from backend.errors import ErrorCode
from backend.db import DatabaseManager
from backend.services.turnstile import require_turnstile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["platform-services"])

# ── Rate limiting (newsletter: 3 per IP per 10 min) ───────────────
_newsletter_rate_limit: Dict[str, list] = {}
_NEWSLETTER_MAX = 3
_NEWSLETTER_WINDOW = 600  # 10 minutes


def _check_newsletter_rate_limit(ip: str) -> None:
    now = time.time()
    attempts = _newsletter_rate_limit.get(ip, [])
    attempts = [t for t in attempts if now - t < _NEWSLETTER_WINDOW]
    if len(attempts) >= _NEWSLETTER_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many subscription attempts. Please try again in a few minutes.",
            headers={"Retry-After": str(_NEWSLETTER_WINDOW)},
        )
    attempts.append(now)
    _newsletter_rate_limit[ip] = attempts

# ── Hardcoded data ──────────────────────────────────────────────

_HARDCODED_INTEGRATIONS = [
    {"id": "int-1", "name": "TransEu", "description": "European freight exchange platform.", "icon": "Truck", "category": "telematics", "is_connected": False, "docs_url": "/docs/integrations/transeu"},
    {"id": "int-2", "name": "QuickBooks", "description": "Accounting and invoicing integration.", "icon": "BookOpen", "category": "accounting", "is_connected": False, "docs_url": "/docs/integrations/quickbooks"},
]

_HARDCODED_SECURITY_REPORTS_HISTORY = [
    {"id": "sec-1", "title": "Dependency scan: CVE-2026-1234", "description": "Minor vulnerability in logging dependency.", "severity": "low", "status": "resolved", "reported_at": "2026-06-01", "resolved_at": "2026-06-05"},
]

_HARDCODED_ONBOARDING_STEPS = [
    {"id": "profile", "title": "Complete your profile", "description": "Add your name and avatar.", "completed": False, "required": True, "link": "/dashboard/settings"},
    {"id": "company", "title": "Set up your company", "description": "Configure your company details.", "completed": False, "required": True, "link": "/dashboard/company"},
    {"id": "first-trip", "title": "Create your first route", "description": "Plan and dispatch your first trip.", "completed": False, "required": False, "link": "/dashboard"},
    {"id": "invite-team", "title": "Invite team members", "description": "Add dispatchers and drivers.", "completed": False, "required": False, "link": "/dashboard/organizations"},
]


# ═══════════════════════════════════════════════════════════════
# Newsletter
# ═══════════════════════════════════════════════════════════════

@router.post("/newsletter/subscribe")
def subscribe_newsletter(
    data: Dict[str, Any],
    request: Request,
    db: DatabaseManager = Depends(get_db),
):
    email = data.get("email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email is required.")

    # ── Turnstile validation (bot protection) ─────────────────────────────
    # Validated when a token is present; pass-through when absent unless
    # REQUIRE_TURNSTILE=1 is set (see backend.services.turnstile).
    require_turnstile(
        data.get("turnstile_token"),
        request.client.host if request.client else None,
    )

    # ── Rate limit (3 per IP per 10 min) ──────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_newsletter_rate_limit(client_ip)

    # ── Ensure the subscriptions table exists (lazy, self-contained) ──────
    # The shared schema module does not define newsletter_subscriptions, so
    # create it on first subscribe. Idempotent; safe on every call.
    try:
        db.conn.execute(
            "CREATE TABLE IF NOT EXISTS newsletter_subscriptions ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  email TEXT UNIQUE NOT NULL,"
            "  name TEXT,"
            "  preferences TEXT,"
            "  is_active INTEGER NOT NULL DEFAULT 1,"
            "  unsubscribed_at TEXT,"
            "  created_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        db.conn.commit()
    except Exception:
        # Table already exists / unavailable — let the INSERT report real errors.
        pass

    try:
        db.conn.execute(
            "INSERT INTO newsletter_subscriptions (email, name, preferences) VALUES (?, ?, ?)",
            (email, data.get("name"), json.dumps(data.get("preferences", {}))),
        )
        db.conn.commit()
    except Exception:
        # Email already exists — reactivate
        db.conn.execute(
            "UPDATE newsletter_subscriptions SET is_active = 1, unsubscribed_at = NULL WHERE email = ?",
            (email,),
        )
        db.conn.commit()
    return {"status": "ok", "message": "Subscribed successfully."}

@router.post("/newsletter/unsubscribe")
def unsubscribe_newsletter(data: Dict[str, Any], db: DatabaseManager = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    if email:
        db.conn.execute("UPDATE newsletter_subscriptions SET is_active = 0, unsubscribed_at = datetime('now') WHERE email = ?", (email,))
        db.conn.commit()
    return {"status": "ok", "message": "Unsubscribed successfully."}


# ═══════════════════════════════════════════════════════════════
# Global Search
# ═══════════════════════════════════════════════════════════════

@router.get("/search")
def global_search(q: str = Query(""), type: Optional[str] = Query(None), db: DatabaseManager = Depends(get_db)):
    if not q:
        return {"results": [], "total": 0, "query": q}
    
    results = []
    
    # Search blog posts
    if not type or type in ("all", "blog"):
        rows = db.conn.execute(
            "SELECT slug, title, excerpt FROM blog_posts WHERE published = 1 AND (title LIKE ? OR excerpt LIKE ?) LIMIT 10",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
        for r in rows:
            results.append({"id": f"blog-{r['slug']}", "type": "blog", "title": r["title"], "description": r["excerpt"], "url": f"/blog/{r['slug']}", "score": 1})
    
    return {"results": results, "total": len(results), "query": q}


# ═══════════════════════════════════════════════════════════════
# Integrations
# ═══════════════════════════════════════════════════════════════

@router.get("/integrations")
def list_integrations(category: Optional[str] = Query(None)):
    if category:
        return [i for i in _HARDCODED_INTEGRATIONS if i["category"] == category]
    return _HARDCODED_INTEGRATIONS

@router.get("/integrations/{integration_id}")
def get_integration(integration_id: str):
    for i in _HARDCODED_INTEGRATIONS:
        if i["id"] == integration_id:
            return i
    raise HTTPException(404, "Integration not found")


# ═══════════════════════════════════════════════════════════════
# Security Reports
# ═══════════════════════════════════════════════════════════════

@router.get("/security/reports")
def get_security_reports():
    return _HARDCODED_SECURITY_REPORTS_HISTORY

@router.post("/security/reports", status_code=201)
def submit_security_report(data: Dict[str, Any]):
    # Just acknowledge — no persistent storage for Phase 8
    return {"status": "ok", "detail": "Report received. We will review it shortly."}


# ═══════════════════════════════════════════════════════════════
# Portal Notifications
# ═══════════════════════════════════════════════════════════════

@router.get("/notifications")
def get_notifications(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    user_id = current_user.get("id")
    rows = db.conn.execute(
        "SELECT id, type, title, message, is_read, link_url, created_at "
        "FROM portal_notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]

@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    db.conn.execute(
        "UPDATE portal_notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notification_id, current_user.get("id")),
    )
    db.conn.commit()
    return {"status": "ok"}

@router.post("/notifications/read-all")
def mark_all_notifications_read(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    db.conn.execute(
        "UPDATE portal_notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
        (current_user.get("id"),),
    )
    db.conn.commit()
    return {"status": "ok"}

@router.get("/notifications/preferences")
def get_notification_preferences(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    user_id = current_user.get("id")
    row = db.conn.execute("SELECT notification_prefs FROM users WHERE id = ?", (user_id,)).fetchone()
    if row and row["notification_prefs"]:
        try:
            return json.loads(row["notification_prefs"])
        except (json.JSONDecodeError, TypeError):
            pass
    # Default preferences
    return {"email_notifications": True, "product_updates": True, "security_alerts": True, "marketing_emails": False, "blog_digest": False}

@router.patch("/notifications/preferences")
def update_notification_preferences(
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
):
    user_id = current_user.get("id")
    # Ensure the column exists
    try:
        db.conn.execute("ALTER TABLE users ADD COLUMN notification_prefs TEXT DEFAULT '{}'")
    except Exception:
        pass
    db.conn.execute(
        "UPDATE users SET notification_prefs = ? WHERE id = ?",
        (json.dumps(data), user_id),
    )
    db.conn.commit()
    return {"status": "ok"}


# ═══════════════════════════════════════════════════════════════
# Onboarding
# ═══════════════════════════════════════════════════════════════

@router.get("/onboarding/checklist")
def get_onboarding_checklist(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    user_id = current_user.get("id")
    # Get completed steps
    completed_rows = db.conn.execute(
        "SELECT step_id FROM onboarding_progress WHERE user_id = ? AND completed = 1",
        (user_id,),
    ).fetchall()
    completed_set = {r["step_id"] for r in completed_rows}

    steps = []
    for s in _HARDCODED_ONBOARDING_STEPS:
        steps.append({
            **s,
            "completed": s["id"] in completed_set,
        })

    completed_count = sum(1 for s in steps if s["completed"])
    return {"steps": steps, "completed_count": completed_count, "total_count": len(steps)}

@router.post("/onboarding/steps/{step_id}/complete")
def complete_onboarding_step(
    step_id: str,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    user_id = current_user.get("id")
    db.conn.execute(
        "INSERT OR REPLACE INTO onboarding_progress (user_id, step_id, completed, completed_at) "
        "VALUES (?, ?, 1, datetime('now'))",
        (user_id, step_id),
    )
    db.conn.commit()
    return {"status": "ok", "step_id": step_id}
