"""Waitlist API — public join + admin management.

POST  /api/waitlist/join                 — Public signup (Phase 1)
GET   /api/waitlist/count                — Live counter (blueprint §11.4)
GET   /api/waitlist/unsubscribe/{token}  — Unsubscribe stub (Phase 3)

Admin (Phase 2):
GET    /api/waitlist/admin/entries        — list / filter / paginate
PATCH  /api/waitlist/admin/entries/{id}   — status updates (state machine)
DELETE /api/waitlist/admin/entries/{id}
GET    /api/waitlist/admin/export.csv
GET    /api/waitlist/admin/stats
POST   /api/waitlist/admin/campaign
"""
from __future__ import annotations


import csv
import hashlib
import io
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from backend.dependencies import get_db
from backend.dependencies_security import require_admin
from backend.db import DatabaseManager
from backend.schemas.waitlist import (
    VALID_TRANSITIONS,
    WAITLIST_STATUS_VALUES,
    WaitlistCampaignRequest,
    WaitlistEntryUpdate,
    WaitlistJoinRequest,
    WaitlistJoinResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

# ── Rate limiting (waitlist-specific: 5 per IP per 10 min) ────────────
# Backed by the shared Redis/in-memory helper so tests can reset it
# between cases via ``backend.utils.rate_limit._fallback``.
_WAITLIST_MAX = 5
_WAITLIST_WINDOW = 600  # 10 minutes

# Salt for IP hashing (generated once at module load)
_IP_SALT = os.environ.get("OPERION_IP_HASH_SALT", secrets.token_hex(16))

# ── Live counter cache (blueprint §11.4) ──────────────────────────────
# Module-level state: ``{"count": int, "cached_at": float|None}``.
# A new signup invalidates the cache; reads serve it for _COUNT_CACHE_TTL.
_count_cache: Dict[str, Any] = {"count": 0, "cached_at": None}
_COUNT_CACHE_TTL = 60  # seconds

# ── Referral redemption rate limiting (blueprint §18b.2) ───────────────
# Maps a referral code → list of redemption timestamps.  A code may be
# redeemed at most _REDEMPTION_MAX times per _REDEMPTION_WINDOW.
_referral_redemptions: Dict[str, List[float]] = {}
_REDEMPTION_MAX = 10        # redemptions per code per day
_REDEMPTION_WINDOW = 86400  # 1 day


def _generate_referral_code(length: int = 8) -> str:
    """Generate a short unique referral code (alphanumeric, uppercase)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no confusing chars
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _check_rate_limit(ip: str) -> None:
    """Enforce the per-IP signup limit via the shared rate-limit helper."""
    from backend.utils.rate_limit import check_rate_limit

    if not check_rate_limit("waitlist:join", ip, _WAITLIST_MAX, _WAITLIST_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts. Please try again in a few minutes.",
            headers={"Retry-After": str(_WAITLIST_WINDOW)},
        )


def _hash_ip(ip: str) -> str:
    """SHA-256 hash of IP with salt — never store raw IP."""
    return hashlib.sha256(f"{ip}:{_IP_SALT}".encode()).hexdigest()


def _normalize_referral_email(email: str) -> str:
    """Gmail-style normalization: lowercase + ignore dots in the local part."""
    local, _, domain = email.partition("@")
    return f"{local.replace('.', '')}@{domain}".lower()


def _invalidate_count_cache() -> None:
    """A new signup changes the count — drop the cached value."""
    _count_cache["cached_at"] = None


# ── Phase 1: Public Join ──────────────────────────────────────────────

@router.post("/join", response_model=WaitlistJoinResponse, status_code=201)
def join_waitlist(
    data: WaitlistJoinRequest,
    request: Request,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Public waitlist signup — no authentication required."""

    # ── Honeypot check ─────────────────────────────────────────────────
    if data.hp_field:
        # Bot detected — fake success response, don't reveal it was caught
        logger.info("Waitlist honeypot triggered from IP: %s",
                     request.client.host if request.client else "unknown")
        return {"status": "joined", "referral_code": "WLCM-" + secrets.token_hex(4).upper()}

    # ── Rate limit check ───────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # ── Normalize email ────────────────────────────────────────────────
    email = data.email.strip().lower()

    # ── Check for duplicate email (case-insensitive) ───────────────────
    existing = db.execute(
        "SELECT id FROM waitlist_entries WHERE lower(email) = lower(?)",
        (email,),
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You're already on the list — check your inbox for updates.",
        )

    # ── Referral handling (blueprint §18b) ─────────────────────────────
    referred_by: Optional[str] = None
    if data.referred_by:
        code = data.referred_by.strip().upper()
        referrer = db.execute(
            "SELECT id, email FROM waitlist_entries WHERE referral_code = ?",
            (code,),
        ).fetchone()
        if referrer is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "referral/invalid-code",
                    "detail": "That referral code isn't valid.",
                },
            )
        if _normalize_referral_email(referrer["email"]) == _normalize_referral_email(email):
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "referral/self-referral",
                    "detail": "You can't use your own referral code.",
                },
            )
        now = time.time()
        redemptions = [
            t for t in _referral_redemptions.get(code, [])
            if now - t < _REDEMPTION_WINDOW
        ]
        if len(redemptions) >= _REDEMPTION_MAX:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_code": "rate-limited",
                    "detail": "This referral code has reached its daily redemption limit.",
                },
            )
        referred_by = code

    # ── Generate unique referral code ──────────────────────────────────
    # Try up to 10 times to avoid collision (extremely unlikely with 8-char code)
    max_attempts = 10
    referral_code = ""
    for _ in range(max_attempts):
        candidate = _generate_referral_code()
        exists = db.execute(
            "SELECT id FROM waitlist_entries WHERE referral_code = ?",
            (candidate,),
        ).fetchone()
        if not exists:
            referral_code = candidate
            break
    if not referral_code:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate referral code. Please try again.",
        )

    # ── Gather abuse-detection metadata ────────────────────────────────
    forwarded = request.headers.get("X-Forwarded-For", "")
    real_ip = forwarded.split(",")[0].strip() or client_ip
    ip_hash = _hash_ip(real_ip)
    user_agent = request.headers.get("User-Agent", "")[:300] or None

    # ── Insert row ─────────────────────────────────────────────────────
    try:
        db.execute(
            """INSERT INTO waitlist_entries 
               (company_name, contact_name, email, fleet_size, company_size,
                country, source, referral_code, referred_by, ip_hash, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.company_name,
                data.contact_name,
                email,
                data.fleet_size,
                data.company_size,
                data.country.upper() if data.country else None,
                data.source,
                referral_code,
                referred_by,
                ip_hash,
                user_agent,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signup failed. Please try again.",
        )

    # Record a successful redemption (only after a real insert).
    if referred_by:
        _referral_redemptions.setdefault(referred_by, []).append(time.time())

    _invalidate_count_cache()

    logger.info(
        "Waitlist join: company='%s' email=%s source=%s code=%s referred_by=%s",
        data.company_name, email, data.source, referral_code, referred_by,
    )

    # ── TODO Phase 3: Enqueue Welcome email (async, not blocking) ──────
    # Email 1 trigger goes here once EmailProvider is built.

    return {"status": "joined", "referral_code": referral_code}


# ── Public: Live counter (blueprint §11.4) ────────────────────────────

@router.get("/count")
def waitlist_count(db: DatabaseManager = Depends(get_db)) -> Dict[str, Any]:
    """Live count of waitlist signups (cached within a short TTL).

    Excludes churned and unsubscribed entries.
    """
    now = time.time()
    cached_at = _count_cache.get("cached_at")
    if cached_at is not None and now - cached_at < _COUNT_CACHE_TTL:
        return {"count": _count_cache["count"], "cached_at": _count_cache["cached_at"]}

    row = db.execute(
        "SELECT COUNT(*) AS c FROM waitlist_entries "
        "WHERE status NOT IN ('churned', 'unsubscribed')"
    ).fetchone()
    count = row["c"] if row else 0
    _count_cache["count"] = count
    _count_cache["cached_at"] = now
    return {"count": count, "cached_at": now}


# ── Public: Unsubscribe (Phase 3 stub) ────────────────────────────────

@router.get("/unsubscribe/{token}")
def unsubscribe(token: str) -> Dict[str, Any]:
    """Unsubscribe stub — real token lookup lands with the email provider."""
    return {"status": "unsubscribed"}


# ── Phase 2: Admin — shared query helpers ─────────────────────────────

def _build_filters(search: str, entry_status: Optional[str], date_from: Optional[str]):
    """Build a WHERE clause + params shared by list/export endpoints."""
    where: List[str] = []
    params: List[Any] = []
    if search:
        where.append("(company_name LIKE ? OR email LIKE ? OR referral_code LIKE ?)")
        params.extend([f"%{search}%"] * 3)
    if entry_status:
        where.append("status = ?")
        params.append(entry_status)
    if date_from:
        where.append("joined_at >= ?")
        params.append(date_from)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    return where_sql, params


# ── Admin: List entries ───────────────────────────────────────────────

@router.get("/admin/entries")
def list_waitlist_entries(
    search: str = "",
    status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[str] = Query(None, description="Only entries joined on/after this date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """List waitlist entries with filtering and pagination."""
    where_sql, params = _build_filters(search, status, date_from)

    total_row = db.execute(
        f"SELECT COUNT(*) AS c FROM waitlist_entries {where_sql}",
        tuple(params),
    ).fetchone()
    total = total_row["c"] if total_row else 0

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM waitlist_entries {where_sql} "
        "ORDER BY joined_at DESC, id DESC LIMIT ? OFFSET ?",
        tuple(params) + (page_size, offset),
    ).fetchall()
    entries = [dict(r) for r in rows]

    status_rows = db.execute(
        f"SELECT status, COUNT(*) AS c FROM waitlist_entries {where_sql} GROUP BY status",
        tuple(params),
    ).fetchall()
    by_status = {r["status"]: r["c"] for r in status_rows}

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "page_size": page_size,
        "by_status": by_status,
    }


# ── Admin: Update entry ───────────────────────────────────────────────

@router.patch("/admin/entries/{entry_id}")
def update_waitlist_entry(
    entry_id: int,
    update: WaitlistEntryUpdate,
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Update a waitlist entry — status follows a validated state machine."""
    row = db.execute(
        "SELECT * FROM waitlist_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Waitlist entry not found.")
    current = dict(row)

    sets: List[str] = []
    params: List[Any] = []

    if update.status is not None:
        if update.status not in WAITLIST_STATUS_VALUES:
            raise HTTPException(status_code=422, detail=f"Invalid status: {update.status}")
        if not update.admin_override and update.status not in VALID_TRANSITIONS.get(
            current["status"], set()
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Cannot transition from '{current['status']}' to '{update.status}'."
                ),
            )
        sets.append("status = ?")
        params.append(update.status)
        timestamp_col = {
            "invited": "invited_at",
            "activated": "activated_at",
            "converted": "converted_at",
            "unsubscribed": "unsubscribed_at",
        }.get(update.status)
        if timestamp_col:
            sets.append(f"{timestamp_col} = datetime('now')")

    if update.notes is not None:
        sets.append("notes = ?")
        params.append(update.notes)

    if sets:
        params.append(entry_id)
        db.execute(
            f"UPDATE waitlist_entries SET {', '.join(sets)} WHERE id = ?",
            tuple(params),
        )
        db.commit()

    updated = db.execute(
        "SELECT * FROM waitlist_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    return dict(updated)


# ── Admin: Delete entry ───────────────────────────────────────────────

@router.delete("/admin/entries/{entry_id}", status_code=204)
def delete_waitlist_entry(
    entry_id: int,
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_admin),
) -> None:
    """Delete a waitlist entry."""
    row = db.execute(
        "SELECT id FROM waitlist_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Waitlist entry not found.")
    db.execute("DELETE FROM waitlist_entries WHERE id = ?", (entry_id,))
    db.commit()
    return None


# ── Admin: Export CSV ─────────────────────────────────────────────────

_CSV_COLUMNS = [
    "id", "company_name", "contact_name", "email", "fleet_size",
    "company_size", "country", "source", "referral_code", "referred_by",
    "status", "joined_at", "invited_at", "activated_at", "converted_at",
    "notes", "unsubscribed_at",
]


@router.get("/admin/export.csv")
def export_waitlist_csv(
    search: str = "",
    status: Optional[str] = Query(None, description="Filter by status"),
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_admin),
) -> Response:
    """Export waitlist entries as CSV (newest first)."""
    where_sql, params = _build_filters(search, status, None)
    rows = db.execute(
        f"SELECT * FROM waitlist_entries {where_sql} "
        "ORDER BY joined_at DESC, id DESC",
        tuple(params),
    ).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CSV_COLUMNS)
    for r in rows:
        data = dict(r)
        writer.writerow(["" if data.get(c) is None else data.get(c) for c in _CSV_COLUMNS])

    return Response(content=buf.getvalue(), media_type="text/csv")


# ── Admin: Stats ──────────────────────────────────────────────────────

@router.get("/admin/stats")
def waitlist_stats(
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Aggregate waitlist statistics."""
    def _counts_by(column: str) -> Dict[str, int]:
        rows = db.execute(
            f"SELECT {column} AS k, COUNT(*) AS c FROM waitlist_entries GROUP BY {column}"
        ).fetchall()
        return {r["k"]: r["c"] for r in rows if r["k"] is not None}

    total_row = db.execute("SELECT COUNT(*) AS c FROM waitlist_entries").fetchone()
    total = total_row["c"] if total_row else 0

    by_status = _counts_by("status")
    growth_rows = db.execute(
        "SELECT substr(joined_at, 1, 10) AS day, COUNT(*) AS c "
        "FROM waitlist_entries GROUP BY day ORDER BY day"
    ).fetchall()
    growth_daily = [{"date": r["day"], "count": r["c"]} for r in growth_rows]

    converted = by_status.get("converted", 0)
    conversion_rate = converted / total if total else 0.0

    return {
        "total": total,
        "by_status": by_status,
        "by_country": _counts_by("country"),
        "by_company_size": _counts_by("company_size"),
        "by_fleet_size": _counts_by("fleet_size"),
        "by_source": _counts_by("source"),
        "growth_daily": growth_daily,
        "conversion_rate": conversion_rate,
    }


# ── Admin: Campaign ───────────────────────────────────────────────────

_CAMPAIGN_SEGMENTS = {"all", "joined", "invited", "activated", "converted"}


@router.post("/admin/campaign")
def send_waitlist_campaign(
    data: WaitlistCampaignRequest,
    db: DatabaseManager = Depends(get_db),
    _: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Send a campaign email to a waitlist segment.

    Phase 3 will hand off to the EmailProvider; today we just report the
    recipient count for the segment.
    """
    if data.segment not in _CAMPAIGN_SEGMENTS:
        raise HTTPException(status_code=422, detail=f"Invalid segment: {data.segment}")

    if data.segment == "all":
        where_sql, params = "WHERE status NOT IN ('unsubscribed', 'churned')", []
    else:
        where_sql, params = "WHERE status = ?", [data.segment]

    rows = db.execute(
        f"SELECT id, email FROM waitlist_entries {where_sql}", tuple(params)
    ).fetchall()
    count = len(rows)

    if count == 0:
        return {"status": "no_recipients", "count": 0, "total_recipients": 0}

    # ── TODO Phase 3: enqueue emails via EmailProvider (async, non-blocking)
    logger.info(
        "Waitlist campaign '%s' → %d recipient(s), segment=%s",
        data.subject, count, data.segment,
    )
    return {"status": "sent", "count": count, "total_recipients": count}
