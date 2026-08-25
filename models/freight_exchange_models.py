from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date, datetime
from models.common import Money


class ProviderCredentials(BaseModel):
    company_id: int
    provider_id: str  # "timocom", "trans_eu", "teleroute", "wtransnet"
    client_id: str
    client_secret_encrypted: str
    scope: list[str] = []
    grant_type: Literal["client_credentials", "authorization_code"] = "client_credentials"
    authorization_code: Optional[str] = None
    redirect_uri: Optional[str] = None
    api_key: Optional[str] = None


class ProviderSession(BaseModel):
    company_id: int
    provider_id: str
    access_token_encrypted: str
    expires_at: datetime
    refresh_token_encrypted: Optional[str] = None
    last_health_check_at: Optional[datetime] = None
    last_health_check_status: Optional[Literal["healthy", "degraded", "down"]] = None
    user_id: Optional[int] = None


class ProviderHealthCheck(BaseModel):
    provider_id: str
    status: Literal["healthy", "degraded", "down"]
    latency_ms: int
    checked_at: datetime
    error: Optional[str] = None


class ProviderCapabilities(BaseModel):
    provider_id: str
    supported_filters: list[str]
    supports_saved_search: bool
    supports_offer_publishing: bool
    rate_limit_per_minute: int
    adr_search: bool = False
    trailer_type_search: bool = False
    supports_loading_type: bool = False
    supports_country_filter: bool = False
    supports_sort: bool = False
    supports_freight_publication: bool = False
    supports_negotiation: bool = False
    supports_transport_orders: bool = False
    supports_monitoring: bool = False
    supports_webhooks: bool = False
    supports_oauth_user: bool = False
    requires_api_key_header: bool = False


class GeoFilter(BaseModel):
    location: str
    radius_km: float


class LoadSearchFilters(BaseModel):
    origin: Optional[GeoFilter] = None
    destination: Optional[GeoFilter] = None
    pickup_date_from: date
    pickup_date_to: date
    delivery_date_from: Optional[date] = None
    delivery_date_to: Optional[date] = None
    trailer_type: Optional[list[str]] = None
    adr_required: Optional[bool] = None
    weight_kg_min: Optional[float] = None
    weight_kg_max: Optional[float] = None
    price_min: Optional[float] = None
    distance_km_max: Optional[float] = None
    extra_filters: dict = {}
    loading_type: Optional[str] = None  # "ftl", "ltl", or None (any)
    loading_country: Optional[str] = None  # ISO country code for loading
    delivery_country: Optional[str] = None  # ISO country code for delivery
    sort_by: Optional[str] = None  # "price", "distance", "date", or None
    sort_order: Optional[str] = "asc"  # "asc" or "desc"
    min_trucks: Optional[int] = None  # Minimum number of trucks/vehicles needed
    loading_type_list: Optional[list[str]] = None  # Multiple loading types e.g. ["ftl", "ltl"]


class LoadSearchResult(BaseModel):
    result_id: str
    provider_id: str
    provider_load_id: str
    origin: str
    destination: str
    pickup_window: tuple[datetime, datetime]
    delivery_window: tuple[datetime, datetime]
    price: Money
    distance_km: float
    trailer_type: str
    adr: bool
    raw_payload: dict = {}
    loading_type: str = ""  # "ftl", "ltl", or empty string
    loading_country: str = ""  # ISO country code
    delivery_country: str = ""  # ISO country code
    weight_kg: float = 0.0  # actual weight of the load
    loading_date: Optional[str] = None  # ISO date string for loading date display
    unloading_date: Optional[str] = None  # ISO date string for delivery date display


class SavedSearch(BaseModel):
    saved_search_id: str
    company_id: int
    user_id: int
    label: str
    filters: LoadSearchFilters
    provider_ids: Optional[list[str]] = None
    created_at: datetime
    last_refreshed_at: Optional[datetime] = None


class ImportResult(BaseModel):
    trip_id: int
    source: Literal["manual", "freight_exchange"]
    source_provider_id: Optional[str] = None
    source_reference_id: Optional[str] = None
    imported_at: datetime
    imported_by_user_id: int


class VehicleCompatibility(BaseModel):
    vehicle_id: int
    compatible: bool
    reasons: list[str]  # i18n keys e.g. "freight.compat.trailer_mismatch"


class DriverCompatibility(BaseModel):
    driver_id: int
    compatible: bool
    hours_remaining: float
    reasons: list[str]


class LoadEvaluation(BaseModel):
    provider_id: str
    provider_load_id: str
    estimated_revenue: Money
    fuel_cost: Money
    toll_cost: Money
    driver_salary: Money
    deadhead_distance_km: float
    expected_profit: Money
    profit_margin_pct: float
    estimated_duration_hours: float
    risk_score: float  # 0.0-1.0, higher = riskier
    vehicle_compatibility: list[VehicleCompatibility] = []
    driver_compatibility: list[DriverCompatibility] = []
    evaluated_at: datetime


class TruckMatchScore(BaseModel):
    vehicle_id: int
    driver_id: Optional[int] = None
    score: float  # 0-100
    rank: int
    reasons: list[str]  # i18n keys, ordered by contribution
    distance_to_pickup_km: float
    expected_deadhead_km: float
    expected_profit: Money
    driver_hours_remaining: Optional[float] = None
    maintenance_status: str
    trailer_compatible: bool


class TransEuUserToken(BaseModel):
    """Per-user OAuth token for Trans.eu. Stored encrypted at rest."""
    id: str = ""
    company_id: int
    user_id: int
    trans_eu_account_id: Optional[str] = None
    access_token_encrypted: str
    refresh_token_encrypted: str
    scope: str = ""
    expires_at: datetime
    api_key_encrypted: str
    client_id: str = ""
    client_secret_encrypted: str = ""
    status: Literal["active", "expired", "revoked", "needs_reauth"] = "active"
    connected_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    last_refreshed_at: Optional[datetime] = None


class FreightOffer(BaseModel):
    """Trans.eu freight tracked in Operion beyond LoadSearchResult."""
    id: str = ""
    company_id: int
    user_id: int
    trans_eu_freight_id: int
    trans_eu_reference_number: str = ""
    status: str = "draft"
    publication_status: Optional[str] = None
    publication_type: Optional[str] = None
    origin: str
    destination: str
    pickup_from: Optional[datetime] = None
    pickup_to: Optional[datetime] = None
    delivery_from: Optional[datetime] = None
    delivery_to: Optional[datetime] = None
    price_amount: float = 0.0
    price_currency: str = "EUR"
    distance_km: float = 0.0
    trailer_type: str = ""
    adr: bool = False
    weight_kg: float = 0.0
    raw_payload: dict = Field(default_factory=dict)
    externally_modified_at: Optional[datetime] = None
    operion_trip_id: Optional[int] = None
    trans_eu_order_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TransEuWebhookEvent(BaseModel):
    """Received webhook event from Trans.eu."""
    id: Optional[str] = None
    company_id: int
    trans_eu_event_id: str
    event_name: str
    occurred_at: datetime
    payload: dict = Field(default_factory=dict)
    status: Literal["received", "processed", "failed", "skipped"] = "received"
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
