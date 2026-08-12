"""Waitlist request/response schemas."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class WaitlistJoinRequest(BaseModel):
    """Public waitlist signup payload."""

    company_name: str = Field(..., min_length=1, description="Company name")
    contact_name: Optional[str] = Field(None, description="Contact person name")
    email: str = Field(..., description="Email address")
    fleet_size: Optional[str] = Field(None, description="Fleet size category")
    company_size: Optional[str] = Field(None, description="Company size category")
    country: Optional[str] = Field(None, max_length=2, description="ISO 3166-1 alpha-2 country code")
    source: str = Field("landing_page", description="Signup source / campaign")
    hp_field: Optional[str] = Field(None, description="Honeypot — leave empty")
    turnstile_token: Optional[str] = Field(None, description="Cloudflare Turnstile token")
    referred_by: Optional[str] = Field(
        None, max_length=16,
        description="Referrer's waitlist referral code (redeemed on join)",
    )


class WaitlistJoinResponse(BaseModel):
    """Response returned after successful waitlist signup."""

    status: str = Field("joined", description="Status of the signup")
    referral_code: str = Field(..., description="Unique referral code")


# ── Enums (module-level constants) ─────────────────────────────────────

FLEET_SIZE_VALUES = {"1-5", "6-20", "21-50", "51-200", "200+"}
COMPANY_SIZE_VALUES = {"solo", "2-10", "11-50", "51-200", "200+"}
WAITLIST_STATUS_VALUES = {"joined", "invited", "activated", "converted", "churned", "unsubscribed"}

# State machine: joined → invited → activated → converted
# unsubscribed / churned reachable from any state
VALID_TRANSITIONS = {
    "joined": {"invited", "churned", "unsubscribed"},
    "invited": {"activated", "churned", "unsubscribed"},
    "activated": {"converted", "churned", "unsubscribed"},
    "converted": {"churned", "unsubscribed"},
    "churned": set(),
    "unsubscribed": set(),
}


# ── Admin Entry Models ─────────────────────────────────────────────────

class WaitlistEntryResponse(BaseModel):
    id: int
    company_name: str
    contact_name: Optional[str] = None
    email: str
    fleet_size: Optional[str] = None
    company_size: Optional[str] = None
    country: Optional[str] = None
    source: str
    referral_code: str
    referred_by: Optional[str] = None
    status: str
    joined_at: str
    invited_at: Optional[str] = None
    activated_at: Optional[str] = None
    converted_at: Optional[str] = None
    notes: Optional[str] = None
    user_agent: Optional[str] = None
    unsubscribed_at: Optional[str] = None


class WaitlistEntryUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    admin_override: bool = False  # skip state machine validation for backfills


class WaitlistPageResponse(BaseModel):
    entries: list[WaitlistEntryResponse]
    total: int
    page: int
    page_size: int
    by_status: dict[str, int]


class WaitlistStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_country: dict[str, int]
    by_company_size: dict[str, int]
    by_fleet_size: dict[str, int]
    by_source: dict[str, int]
    growth_daily: list[dict[str, Any]]
    conversion_rate: float


class WaitlistCampaignRequest(BaseModel):
    """Admin campaign send payload (simulated send — no email infra yet)."""

    subject: str = Field(..., min_length=1, description="Email subject (required)")
    body: str = Field("", description="Email body")
    segment: Literal["all", "invited", "joined", "converted"] = Field(
        "all", description="Recipient segment (churned/unsubscribed never included)"
    )


class WaitlistCampaignResponse(BaseModel):
    status: str
    count: int
    total_recipients: int
