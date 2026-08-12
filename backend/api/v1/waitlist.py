"""Waitlist API — public join + admin management.

POST  /waitlist/join                      — Public signup (Phase 1)
GET   /waitlist/count                     — Public live signup counter
GET   /waitlist/unsubscribe/{token}       — Public one-click unsubscribe
GET   /waitlist/admin/entries             — Admin: list / filter / paginate
PATCH /waitlist/admin/entries/{id}        — Admin: status / notes update (state machine)
DELETE /waitlist/admin/entries/{id}       — Admin: delete an entry
GET   /waitlist/admin/export.csv          — Admin: CSV export (filter-aware)
GET   /waitlist/admin/stats               — Admin: funnel / source / growth stats
POST  /waitlist/admin/campaign            — Admin: simulated segment campaign send
"""

import csv
import hashlib
import io
import logging
import os
import secrets
import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from backend.dependencies import get_db
from backend.dependencies_security import require_admin
from backend.errors import ErrorCode
from backend.schemas.waitlist import (
    VALID_TRANSITIONS,
    WaitlistCampaignRequest,
    WaitlistCampaignResponse,
    WaitlistEntryResponse,
    WaitlistEntryUpdate,
    WaitlistJoinRequest,
    WaitlistJoinResponse,
    WaitlistPageResponse,
    WaitlistStatsResponse,
)
from backend.services.turnstile import require_turnstile
from backend.utils.rate_limit import check_rate_limit
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

# ── Rate limiting (waitlist-specific: 5 per IP per 10 min) ────────────
# Redis-backed across workers (backend/utils/rate_limit.py); in-memory
# fallback when Redis is unavailable.
_WAITLIST_MAX = 5
_WAITLIST_WINDOW = 600  # 10 minutes

# ── Live counter cache (TTL) ───────────────────────────────────────────
# The public counter is intentionally cheap: recomputed at most once per
# _COUNT_TTL seconds, otherwise served from a module-level dict.
_count_cache: Dict[str, Any] = {"count": 0, "cached_at": None}
_COUNT_TTL = 60  # seconds
# Statuses that represent real, current signups. 'churned'/'unsubscribed'
# are excluded because those entries are no longer active on the list.
_COUNT_STATUSES = ("joined", "invited", "activated", "converted")

# ── Referral redemption abuse control ─────────────────────────────────
_REFERRAL_MAX_PER_DAY = 10
_referral_redemptions: Dict[str, int] = {}  # "CODE:YYYY-MM-DD" -> count

# Salt for IP hashing (generated once at module load)
_IP_SALT = os.environ.get("OPERION_IP_HASH_SALT", secrets.token_hex(16))


def _generate_referral_code(length: int = 8) -> str:
    """Generate a short unique referral code (alphanumeric, uppercase)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no confusing chars
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _check_rate_limit(ip: str) -> None:
    if not check_rate_limit("waitlist", _hash_ip(ip), _WAITLIST_MAX, _WAITLIST_WINDOW):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts. Please try again in a few minutes.",
            headers={"Retry-After": str(_WAITLIST_WINDOW)},
        )


def _hash_ip(ip: str) -> str:
    """SHA-256 hash of IP with salt — never store raw IP."""
    return hashlib.sha256(f"{ip}:{_IP_SALT}".encode()).hexdigest()


# ── Public live counter (blueprint §11.4) ─────────────────────────────

def _get_count(db: DatabaseManager) -> Dict[str, Any]:
    """Return cached waitlist count, recomputing at most once per TTL."""
    now = time.time()
    cached_at = _count_cache.get("cached_at")
    if cached_at is not None and now - cached_at < _COUNT_TTL:
        return _count_cache

    try:
        row = db.conn.execute(
            "SELECT COUNT(*) AS c FROM waitlist_entries "
            "WHERE status IN (?, ?, ?, ?)",
            _COUNT_STATUSES,
        ).fetchone()
        count = int(row["c"]) if row else 0
    except Exception:
        # DB hiccup — serve the last known value rather than failing.
        logger.warning("Waitlist count query failed, serving stale value", exc_info=True)
        count = int(_count_cache.get("count", 0))

    _count_cache["count"] = count
    _count_cache["cached_at"] = now
    return _count_cache


def _invalidate_count_cache() -> None:
    """Force the next /count request to recompute."""
    _count_cache["cached_at"] = None


@router.get("/count")
def get_waitlist_count(
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Public live signup counter — cheap, TTL-cached, no auth."""
    cached = _get_count(db)
    cached_at = cached.get("cached_at")
    return {
        "count": cached["count"],
        "cached_at": datetime.fromtimestamp(cached_at).isoformat() if cached_at else None,
    }


# ── Referral abuse controls (blueprint §18b.2) ────────────────────────

def _normalize_email(email: Optional[str]) -> str:
    """Lower-case and strip dots from the local part (Gmail-style)."""
    email = (email or "").strip().lower()
    if "@" in email:
        local, _, domain = email.partition("@")
        local = local.replace(".", "")
        return f"{local}@{domain}"
    return email


def _referral_day_key(referral_code: str) -> str:
    return f"{referral_code}:{time.strftime('%Y-%m-%d')}"


def _check_referral_rate_limit(referral_code: str) -> None:
    """Reject redemptions of the same code beyond _REFERRAL_MAX_PER_DAY/day."""
    key = _referral_day_key(referral_code)
    if _referral_redemptions.get(key, 0) >= _REFERRAL_MAX_PER_DAY:
        logger.warning(
            "Referral redemption rate-limit hit: code=%s", referral_code,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": ErrorCode.RATE_LIMITED.value,
                "detail": "This referral code has been used too many times today.",
            },
            headers={"Retry-After": "3600"},
        )


def _redeem_referral(
    referral_code: str,
    referee_email: str,
    db: DatabaseManager,
) -> None:
    """Validate + record one referral redemption (self-referral, rate-limit).

    Raises:
        HTTPException: 400 REFERRAL_SELF_REFERRAL if the referee is the
            referrer; 400 REFERRAL_INVALID if the code is unknown; 429 if
            the daily redemption cap for the code is exceeded.
    """
    code = (referral_code or "").strip().upper()
    if not code:
        return

    referrer = db.conn.execute(
        "SELECT id, email FROM waitlist_entries WHERE referral_code = ?",
        (code,),
    ).fetchone()
    if referrer is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.REFERRAL_INVALID.value,
                "detail": "That referral code is not valid.",
            },
        )

    # Self-referral: reject when the referrer and referee are the same
    # person (compare normalized emails).
    if _normalize_email(referrer["email"]) == _normalize_email(referee_email):
        logger.warning(
            "Self-referral attempt blocked: code=%s email=%s",
            code, referee_email,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.REFERRAL_SELF_REFERRAL.value,
                "detail": "You can't use your own referral code.",
            },
        )

    _check_referral_rate_limit(code)
    key = _referral_day_key(code)
    _referral_redemptions[key] = _referral_redemptions.get(key, 0) + 1

    # Audit trail: operation_events (reuse existing AuditRepository).
    try:
        from repositories.audit_repository import AuditRepository
        AuditRepository(db).log_event(
            event_type="waitlist.referral_redeemed",
            entity_type="waitlist_entry",
            entity_id=str(referrer["id"]),
            data={
                "referral_code": code,
                "referee_email": referee_email,
                "referrer_email": referrer["email"],
            },
        )
    except Exception:
        logger.warning("Referral redemption audit write failed", exc_info=True)

    logger.info(
        "Referral redeemed: code=%s referrer_id=%s referee=%s",
        code, referrer["id"], referee_email,
    )


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

    # ── Turnstile validation (bot protection) ─────────────────────────────
    # Validated when a token is present; pass-through when absent unless
    # REQUIRE_TURNSTILE=1 is set (see backend.services.turnstile).
    require_turnstile(
        data.turnstile_token,
        request.client.host if request.client else None,
    )

    # ── Rate limit check ───────────────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # ── Normalize email ────────────────────────────────────────────────
    email = data.email.strip().lower()

    # ── Check for duplicate email (case-insensitive) ───────────────────
    existing = db.conn.execute(
        "SELECT id FROM waitlist_entries WHERE lower(email) = lower(?)",
        (email,),
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You're already on the list — check your inbox for updates.",
        )

    # ── Referral redemption: self-referral + per-code daily cap ────────
    referred_by = (data.referred_by or "").strip().upper() or None
    if referred_by:
        _redeem_referral(referred_by, email, db)

    # ── Generate unique referral code ──────────────────────────────────
    # Try up to 10 times to avoid collision (extremely unlikely with 8-char code)
    max_attempts = 10
    referral_code = ""
    for _ in range(max_attempts):
        candidate = _generate_referral_code()
        exists = db.conn.execute(
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
        db.conn.execute(
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
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signup failed. Please try again.",
        )

    # ── Refresh the public live counter (keep /count fresh) ────────────
    _invalidate_count_cache()

    logger.info(
        "Waitlist join: company='%s' email=%s source=%s code=%s",
        data.company_name, email, data.source, referral_code,
    )

    # ── TODO Phase 3: Enqueue Welcome email (async, not blocking) ──────
    # Email 1 trigger goes here once EmailProvider is built.

    return {"status": "joined", "referral_code": referral_code}


# ── Phase 2: Admin management ─────────────────────────────────────────

# Columns surfaced in admin list/CSV responses (subset of the table).
_ENTRY_COLUMNS = (
    "id", "company_name", "contact_name", "email", "fleet_size",
    "company_size", "country", "source", "referral_code", "referred_by",
    "status", "joined_at", "invited_at", "activated_at", "converted_at",
    "notes", "user_agent", "unsubscribed_at",
)

# Status timestamp column set on forward transitions.
_STATUS_TIMESTAMP_COLUMN = {
    "invited": "invited_at",
    "activated": "activated_at",
    "converted": "converted_at",
    "unsubscribed": "unsubscribed_at",
}

# Campaign segments → which statuses are eligible recipients.
# 'churned'/'unsubscribed' are never contacted, even by the 'all' segment.
_CAMPAIGN_SEGMENTS = {
    "all": ["joined", "invited", "activated", "converted"],
    "joined": ["joined"],
    "invited": ["invited"],
    "converted": ["converted"],
}


def _row_to_entry(row) -> Dict[str, Any]:
    """Convert a waitlist_entries sqlite row into a serialisable dict."""
    keys = row.keys()
    return {k: row[k] for k in _ENTRY_COLUMNS if k in keys}


def _build_search_clause(search: Optional[str]):
    """Return (where_sql_fragment, params) for the shared search filter.

    Searches email / company_name / contact_name with case-insensitive LIKE.
    """
    if not search:
        return "", []
    like = f"%{search}%"
    return (
        "(email LIKE ? COLLATE NOCASE OR company_name LIKE ? COLLATE NOCASE "
        "OR contact_name LIKE ? COLLATE NOCASE)",
        [like, like, like],
    )


@router.get("/admin/entries", response_model=WaitlistPageResponse)
def list_waitlist_entries(
    search: Optional[str] = Query(None, description="Email / company / contact LIKE search"),
    status_filter: Optional[str] = Query(None, alias="status", description="Exact status filter"),
    date_from: Optional[str] = Query(None, description="Only entries joined on/after this date"),
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(50, ge=1, le=500, description="Entries per page"),
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Admin: list waitlist entries with search / status / date filters + pagination."""
    where = []
    params: list = []

    clause, clause_params = _build_search_clause(search)
    if clause:
        where.append(clause)
        params.extend(clause_params)
    if status_filter:
        where.append("status = ?")
        params.append(status_filter)
    if date_from:
        where.append("joined_at >= ?")
        params.append(date_from)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total = db.conn.execute(
        f"SELECT COUNT(*) AS c FROM waitlist_entries{where_sql}", params
    ).fetchone()["c"]

    rows = db.conn.execute(
        f"SELECT * FROM waitlist_entries{where_sql} "
        "ORDER BY joined_at DESC, id DESC LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()

    # Per-status breakdown over the *filtered* set (before pagination).
    by_status: Dict[str, int] = {}
    for status_val, cnt in db.conn.execute(
        f"SELECT status, COUNT(*) AS c FROM waitlist_entries{where_sql} GROUP BY status",
        params,
    ).fetchall():
        by_status[status_val] = int(cnt)

    return {
        "entries": [_row_to_entry(r) for r in rows],
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "by_status": by_status,
    }


@router.patch("/admin/entries/{entry_id}", response_model=WaitlistEntryResponse)
def update_waitlist_entry(
    entry_id: int,
    data: WaitlistEntryUpdate,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Admin: update an entry's status (enforcing the state machine) and/or notes.

    ``admin_override=True`` bypasses the state machine for backfills. Timestamps
    are set on forward transitions (invited_at / activated_at / converted_at /
    unsubscribed_at), preserving an existing value if already present.
    """
    row = db.conn.execute(
        "SELECT * FROM waitlist_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Waitlist entry not found")

    current_status = row["status"]
    sets: list[str] = []
    params: list = []

    if data.status is not None:
        new_status = data.status
        if not data.admin_override:
            allowed = VALID_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error_code": ErrorCode.VALIDATION_ERROR.value,
                        "detail": (
                            f"Invalid status transition: {current_status} -> {new_status}"
                        ),
                    },
                )
        sets.append("status = ?")
        params.append(new_status)
        ts_col = _STATUS_TIMESTAMP_COLUMN.get(new_status)
        if ts_col and (current_status != new_status or not row[ts_col]):
            sets.append(f"{ts_col} = COALESCE({ts_col}, datetime('now'))")

    if data.notes is not None:
        sets.append("notes = ?")
        params.append(data.notes)

    if sets:
        params.append(entry_id)
        db.conn.execute(
            f"UPDATE waitlist_entries SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        db.conn.commit()

    _invalidate_count_cache()
    updated = db.conn.execute(
        "SELECT * FROM waitlist_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    return _row_to_entry(updated)


@router.delete("/admin/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_waitlist_entry(
    entry_id: int,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
) -> None:
    """Admin: delete a waitlist entry (204 no content; 404 if missing)."""
    row = db.conn.execute(
        "SELECT id FROM waitlist_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Waitlist entry not found")
    db.conn.execute("DELETE FROM waitlist_entries WHERE id = ?", (entry_id,))
    db.conn.commit()
    _invalidate_count_cache()


@router.get("/admin/export.csv")
def export_waitlist_csv(
    search: Optional[str] = Query(None, description="Optional search filter"),
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
) -> Response:
    """Admin: export all (or filtered) entries as CSV, newest first."""
    clause, params = _build_search_clause(search)
    where_sql = (" WHERE " + clause) if clause else ""
    rows = db.conn.execute(
        f"SELECT * FROM waitlist_entries{where_sql} ORDER BY joined_at DESC, id DESC",
        params,
    ).fetchall()

    headers = list(_ENTRY_COLUMNS)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow([r[h] if r[h] is not None else "" for h in headers])
    return Response(content=buf.getvalue(), media_type="text/csv")


@router.get("/admin/stats", response_model=WaitlistStatsResponse)
def waitlist_stats(
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Admin: funnel + demographic stats over all entries."""
    total = db.conn.execute(
        "SELECT COUNT(*) AS c FROM waitlist_entries"
    ).fetchone()["c"]

    def _group(column: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for val, cnt in db.conn.execute(
            f"SELECT {column}, COUNT(*) AS c FROM waitlist_entries GROUP BY {column}"
        ).fetchall():
            if val is not None:
                counts[str(val)] = int(cnt)
        return counts

    converted = db.conn.execute(
        "SELECT COUNT(*) AS c FROM waitlist_entries WHERE status = 'converted'"
    ).fetchone()["c"]
    conversion_rate = round(int(converted) / int(total), 6) if total else 0.0

    return {
        "total": int(total),
        "by_status": _group("status"),
        "by_country": _group("country"),
        "by_company_size": _group("company_size"),
        "by_fleet_size": _group("fleet_size"),
        "by_source": _group("source"),
        "growth_daily": [
            {"date": row["day"], "count": int(row["c"])}
            for row in db.conn.execute(
                "SELECT date(joined_at) AS day, COUNT(*) AS c FROM waitlist_entries "
                "GROUP BY day ORDER BY day"
            ).fetchall()
        ],
        "conversion_rate": conversion_rate,
    }


@router.post("/admin/campaign", response_model=WaitlistCampaignResponse)
def send_waitlist_campaign(
    data: WaitlistCampaignRequest,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Admin: simulate a segmented campaign send.

    Recipients are selected by status (churned/unsubscribed are always
    excluded); no email infra exists yet, so the "send" is a logged intent.
    """
    statuses = _CAMPAIGN_SEGMENTS[data.segment]
    placeholders = ", ".join("?" for _ in statuses)
    recipients = db.conn.execute(
        f"SELECT id, email FROM waitlist_entries WHERE status IN ({placeholders})",
        statuses,
    ).fetchall()
    total_recipients = len(recipients)

    if total_recipients == 0:
        return {"status": "no_recipients", "count": 0, "total_recipients": 0}

    logger.info(
        "Campaign send (simulated): segment=%s recipients=%d subject=%r",
        data.segment, total_recipients, data.subject,
    )
    return {"status": "sent", "count": total_recipients, "total_recipients": total_recipients}


# ── Phase 2: Public unsubscribe ────────────────────────────────────────

@router.get("/unsubscribe/{token}")
def unsubscribe_waitlist(
    token: str,
    db: DatabaseManager = Depends(get_db),
) -> Dict[str, Any]:
    """Public one-click unsubscribe, keyed by referral code (or numeric id).

    Unknown tokens still return success — we never reveal whether an email
    is on the list (anti-enumeration / privacy).
    """
    row = db.conn.execute(
        "SELECT id FROM waitlist_entries WHERE referral_code = ? OR CAST(id AS TEXT) = ?",
        (token, token),
    ).fetchone()
    if row is not None:
        db.conn.execute(
            "UPDATE waitlist_entries SET status = 'unsubscribed', "
            "unsubscribed_at = COALESCE(unsubscribed_at, datetime('now')) "
            "WHERE id = ?",
            (row["id"],),
        )
        db.conn.commit()
        _invalidate_count_cache()
        logger.info("Waitlist unsubscribe: entry_id=%s", row["id"])
    return {"status": "unsubscribed"}
