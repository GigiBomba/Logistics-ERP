"""Mobile API schemas — condensed Pydantic models for mobile clients.

These DTOs are purpose-built for mobile: bandwidth-optimised, flattened
where possible, and containing only the fields a mobile screen needs.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from models.invoice_models import InvoiceLineItem


# ──────────────────────────────────────────────────────────────────────
#  Shared / common
# ──────────────────────────────────────────────────────────────────────

class SyncCursorRequest(BaseModel):
    """Request body for storing a sync cursor."""
    entity_type: str
    cursor: str


# ──────────────────────────────────────────────────────────────────────
#  Driver
# ──────────────────────────────────────────────────────────────────────

class DriverTransportResponse(BaseModel):
    """Condensed transport card for driver list screens."""
    model_config = ConfigDict(extra="ignore")

    id: int
    load_info: str = ""
    origin: str = ""
    destination: str = ""
    status: str = ""
    vehicle_plate: str = ""
    scheduled_date: Optional[str] = None
    last_updated: Optional[str] = None


class DriverTransportDetailResponse(BaseModel):
    """Full transport detail for the driver transport screen."""
    model_config = ConfigDict(extra="ignore")

    id: int
    load_info: str = ""
    origin: str = ""
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    destination: str = ""
    dest_lat: Optional[float] = None
    dest_lng: Optional[float] = None
    waypoints: List[str] = []
    status: str = ""
    assigned_driver_name: str = ""
    vehicle_plate: str = ""
    scheduled_date: Optional[str] = None
    delivered_date: Optional[str] = None
    last_updated: Optional[str] = None


class DriverMyDayResponse(BaseModel):
    """Aggregate dashboard for the driver home screen."""
    active_transports: int = 0
    next_stop: Optional[str] = None
    next_stop_time: Optional[str] = None
    unread_messages: int = 0
    recent_transports: List[DriverTransportResponse] = []
    recent_messages: List["MobileMessageResponse"] = []


class StatusUpdateRequest(BaseModel):
    """Request to update a transport's status."""
    status: str


class DriverVehicleResponse(BaseModel):
    """Assigned vehicle info for the driver."""
    model_config = ConfigDict(extra="ignore")

    id: int
    plate: str = ""
    type: str = ""
    brand: str = ""
    model: str = ""
    status: str = ""
    documents: List["VehicleDocumentResponse"] = []


class VehicleDocumentResponse(BaseModel):
    """A vehicle-associated document with expiry tracking."""
    model_config = ConfigDict(extra="ignore")

    id: int
    document_type: str = ""   # ITP, RCA, etc.
    expiry_date: Optional[str] = None
    is_expiring_soon: bool = False


# ──────────────────────────────────────────────────────────────────────
#  Expenses
# ──────────────────────────────────────────────────────────────────────


class MobileExpenseResponse(BaseModel):
    """Expense item for the driver expenses list."""
    model_config = ConfigDict(extra="ignore")

    id: int
    expense_type: str = ""
    amount: float = 0.0
    currency: str = "EUR"
    date: Optional[str] = None
    description: str = ""
    receipt_url: Optional[str] = None
    status: str = "pending"


class MobileExpenseCreateRequest(BaseModel):
    """Create a new expense from mobile."""
    expense_type: str = "other"  # fuel, tolls, per_diem, other
    amount: float
    currency: str = "EUR"
    date: Optional[str] = None
    description: str = ""


# ──────────────────────────────────────────────────────────────────────
#  Messaging (new)
# ──────────────────────────────────────────────────────────────────────

class MobileMessageResponse(BaseModel):
    """A driver-dispatcher message."""
    model_config = ConfigDict(extra="ignore")

    id: int
    sender_id: int
    sender_name: str = ""
    receiver_id: int
    text: str = ""
    timestamp: Optional[str] = None
    is_read: bool = False
    transport_id: Optional[int] = None


class MobileMessageSendRequest(BaseModel):
    """Create a new message."""
    receiver_id: int
    text: str
    transport_id: Optional[int] = None


# ──────────────────────────────────────────────────────────────────────
#  Push notifications
# ──────────────────────────────────────────────────────────────────────

class DeviceRegisterRequest(BaseModel):
    """Register a device for push notifications."""
    token: str
    platform: str  # "ios" or "android"
    device_id: str
    device_name: Optional[str] = ""


# ──────────────────────────────────────────────────────────────────────
#  Dispatcher / Manager
# ──────────────────────────────────────────────────────────────────────

class DispatcherOverviewResponse(BaseModel):
    """Aggregate dispatcher dashboard."""
    active_jobs: int = 0
    active_drivers: int = 0
    open_alerts: int = 0
    vehicles_on_road: int = 0
    revenue_to_date: float = 0.0


class FleetPositionResponse(BaseModel):
    """A single vehicle position for the fleet map."""
    vehicle_id: int
    plate: str = ""
    driver_name: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    status: str = ""
    last_update: Optional[str] = None


class DispatcherJobResponse(BaseModel):
    """Condensed job card for dispatcher list."""
    model_config = ConfigDict(extra="ignore")

    id: int
    load_info: str = ""
    driver_name: str = ""
    vehicle_plate: str = ""
    status: str = ""
    origin: str = ""
    destination: str = ""
    last_updated: Optional[str] = None


class DispatcherDriverResponse(BaseModel):
    """Condensed driver card for dispatcher."""
    id: int
    name: str = ""
    status: str = ""  # available, driving, off
    current_transport: Optional[str] = None
    current_vehicle: Optional[str] = None


class DriverTripOverviewResponse(BaseModel):
    """Overview of the driver's currently assigned trip (mobile trip screen).

    Contract with the mobile app (``DriverTripOverview``): every field is
    nullable — when the driver has no current trip the endpoint returns
    HTTP 200 with all fields null and the app renders its empty state.
    ``transport_id`` is a string (never an int). ``status`` uses the mobile
    enum values; ``eta_confidence`` is ``live``/``stale`` or null (the app
    falls back to its ``unavailable`` value on null).
    """
    model_config = ConfigDict(extra="ignore")

    transport_id: Optional[str] = None
    load_info: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    status: Optional[Literal["planned", "loading", "in_transit", "delivered", "cancelled"]] = None
    status_since: Optional[str] = None  # ISO-8601
    eta: Optional[str] = None  # ISO-8601
    eta_confidence: Optional[Literal["live", "stale"]] = None


class DispatcherAlertResponse(BaseModel):
    """An alert for the dispatcher inbox."""
    id: int
    type: str = ""
    title: str = ""
    description: str = ""
    severity: str = ""
    is_read: bool = False
    created_at: Optional[str] = None
    related_entity_id: Optional[int] = None
    related_entity_type: str = ""


class ApprovalActionRequest(BaseModel):
    """Approve or reject an approval item."""
    reason: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────
#  Sync
# ──────────────────────────────────────────────────────────────────────

class SyncResponse(BaseModel):
    """Response from the delta-sync endpoint."""
    records: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    has_more: bool = False


# ──────────────────────────────────────────────────────────────────────
#  Route share
# ──────────────────────────────────────────────────────────────────────


class RoutePoint(BaseModel):
    """A single point in a route geometry."""
    lat: float
    lng: float


class RouteInstruction(BaseModel):
    """Turn-by-turn instruction for a route."""
    text_key: str = ""
    distance_meters: float = 0.0
    point_index: int = 0


class RouteShareResponse(BaseModel):
    """Route geometry and turn-by-turn instructions for sharing."""
    transport_id: str
    points: list[RoutePoint] = []
    instructions: list[RouteInstruction] = []
    total_distance_meters: float = 0.0
    total_duration_seconds: int = 0
    generated_at: str = ""
    ttl_seconds: int = 300


# ──────────────────────────────────────────────────────────────────────
#  Local Download manifest (blueprint §5.3)
# ──────────────────────────────────────────────────────────────────────


class DownloadCategory(str, Enum):
    """Blueprint §5.3 download categories — mirrors the mobile
    ``DownloadCategory`` enum in ``download_manifest.dart`` exactly
    (documents, invoices, receipts, ocrResults, tripHistory)."""

    documents = "documents"
    invoices = "invoices"
    receipts = "receipts"
    ocr_results = "ocr_results"
    trip_history = "trip_history"


class DownloadRequest(BaseModel):
    """Request for the company-scoped local-download file manifest.

    ``date_from`` / ``date_to`` are ISO-8601 dates (YYYY-MM-DD), optional,
    filtering on the record's upload/creation date.
    """

    model_config = ConfigDict(extra="ignore")

    category: DownloadCategory
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class DownloadManifestEntry(BaseModel):
    """A single downloadable record from the manifest.

    ``download_url`` is a short-lived signed URL to the companion fetch
    endpoint (``GET /api/v1/mobile/company/export/download/{token}``) —
    never a permanent public link.  ``url_expires_at`` is ISO-8601; the
    client must re-request the manifest if it has expired.
    """

    record_id: str
    filename: str
    size_bytes: int = 0
    download_url: str = ""
    url_expires_at: str = ""  # ISO-8601


# ──────────────────────────────────────────────────────────────────────
#  Records core — Fleet (blueprint §6.1)
# ──────────────────────────────────────────────────────────────────────


class MobileTruckOut(BaseModel):
    """Condensed truck record for the mobile fleet screens."""

    model_config = ConfigDict(extra="ignore")

    id: int
    company_id: int = 0
    plate: str = ""
    brand: str = ""
    model: str = ""
    vin: str = ""
    year: Optional[int] = None
    status: str = ""                      # real truck status string ('Active'/'In Service'/'Inactive')
    health_score: Optional[int] = None    # from truck_health_scores (nullable)
    current_driver_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MobileTruckCreate(BaseModel):
    """Create a truck from mobile (fields map 1:1 to truck columns)."""

    model_config = ConfigDict(extra="forbid")

    plate_number: str = Field(..., min_length=1, max_length=50)
    model: str = ""
    manufacturer: str = ""
    year: Optional[int] = None
    vin: str = ""
    status: str = "Active"
    insurance_expiry: Optional[str] = None
    inspection_expiry: Optional[str] = None
    tachograph_expiry: Optional[str] = None
    tracking_device_id: Optional[str] = None
    trailer_plate: str = ""
    max_payload_kg: Optional[float] = None
    cmr_insurance_number: str = ""
    cmr_insurance_expiry: Optional[str] = None


class MobileTruckUpdate(BaseModel):
    """Partial truck update from mobile."""

    model_config = ConfigDict(extra="forbid")

    plate_number: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    year: Optional[int] = None
    vin: Optional[str] = None
    status: Optional[str] = None
    insurance_expiry: Optional[str] = None
    inspection_expiry: Optional[str] = None
    tachograph_expiry: Optional[str] = None
    tracking_device_id: Optional[str] = None
    trailer_plate: Optional[str] = None
    max_payload_kg: Optional[float] = None
    cmr_insurance_number: Optional[str] = None
    cmr_insurance_expiry: Optional[str] = None


class MaintenanceRecordOut(BaseModel):
    """Maintenance record for a truck (category ← maintenance_type, vendor ← service_provider)."""

    model_config = ConfigDict(extra="ignore")

    id: int
    truck_id: int
    date: str = ""
    category: str = ""
    cost: Optional[float] = None
    vendor: str = ""
    notes: str = ""


class MaintenanceCreateRequest(BaseModel):
    """Create a maintenance record from mobile."""

    model_config = ConfigDict(extra="forbid")

    date: str = Field(..., min_length=1)          # ISO date YYYY-MM-DD
    category: str = Field(..., min_length=1)      # e.g. 'Oil Change', 'Tires', 'Repair'
    cost: Optional[float] = None
    vendor: str = ""
    notes: str = ""


# ──────────────────────────────────────────────────────────────────────
#  Records core — Drivers (blueprint §6.2)
# ──────────────────────────────────────────────────────────────────────


class DriverOut(BaseModel):
    """Condensed driver record for the mobile driver screens.

    ``status`` reuses the legacy derivation from ``/mobile/dispatcher/drivers``:
    'driving' → has an active (non-delivered/cancelled) trip; 'available' → has
    an active truck assignment but no active trip; else 'off'.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    company_id: int = 0
    name: str = ""
    phone: str = ""
    email: str = ""
    status: str = "off"  # driving | available | off
    license_number: str = ""
    license_category: str = ""
    license_expiry: Optional[str] = None
    medical_expiry: Optional[str] = None
    adr_certificate_expiry: Optional[str] = None
    current_truck_id: Optional[int] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DriverCreateRequest(BaseModel):
    """Create a driver from mobile."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    phone: str = ""
    email: str = ""
    license_number: str = ""
    license_category: str = ""
    license_expiry: Optional[str] = None
    medical_expiry: Optional[str] = None
    adr_certificate_expiry: Optional[str] = None
    hire_date: Optional[str] = None
    monthly_salary: Optional[float] = None
    notes: str = ""
    is_active: bool = True


class DriverUpdateRequest(BaseModel):
    """Partial driver update from mobile."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    license_number: Optional[str] = None
    license_category: Optional[str] = None
    license_expiry: Optional[str] = None
    medical_expiry: Optional[str] = None
    adr_certificate_expiry: Optional[str] = None
    hire_date: Optional[str] = None
    monthly_salary: Optional[float] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class TachoDayBucket(BaseModel):
    """Per-day tachograph activity bucket for a driver."""

    model_config = ConfigDict(extra="ignore")

    date: str = ""
    driving_minutes: int = 0
    working_minutes: int = 0
    rest_minutes: int = 0
    availability_minutes: int = 0


class TachoTimelineOut(BaseModel):
    """Tachograph timeline for a driver over a date range."""

    model_config = ConfigDict(extra="ignore")

    days: List[TachoDayBucket] = []
    weekly_driving_minutes: int = 0
    weekly_limit_minutes: int = 3360  # EU 56h/2wk weekly driving cap, in minutes


# ──────────────────────────────────────────────────────────────────────
#  Records core — Clients (blueprint §6.3)
# ──────────────────────────────────────────────────────────────────────


class ClientOut(BaseModel):
    """Condensed client record for the mobile client screens."""

    model_config = ConfigDict(extra="ignore")

    id: int
    company_id: int = 0
    name: str = ""
    vat_number: str = ""
    address: str = ""
    payment_terms_days: int = 30
    rating: Optional[int] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ClientContactOut(BaseModel):
    """Condensed client contact (name ← full_name, role ← title)."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = ""
    role: str = ""
    phone: str = ""
    email: str = ""


class ClientDetailOut(ClientOut):
    """Client detail with contacts and recent activity counts."""

    model_config = ConfigDict(extra="ignore")

    contacts: List[ClientContactOut] = []
    recent_trip_count: int = 0
    recent_invoice_count: int = 0


class ClientCreateRequest(BaseModel):
    """Create a client from mobile."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    vat_number: str = ""
    address: str = ""
    payment_terms_days: int = 30
    rating: Optional[int] = Field(None, ge=1, le=5)
    notes: str = ""


class ClientUpdateRequest(BaseModel):
    """Partial client update from mobile."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    vat_number: Optional[str] = None
    address: Optional[str] = None
    payment_terms_days: Optional[int] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None


class ClientContactCreateRequest(BaseModel):
    """Add a contact to a client from mobile."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=1, max_length=255)
    contact_type: str = "operations"
    title: str = ""
    phone: str = ""
    email: str = ""


class ClientMergeRequest(BaseModel):
    """Multi-source client merge (mobile, blueprint §6.3)."""

    model_config = ConfigDict(extra="forbid")

    target_id: int = Field(..., gt=0)
    source_ids: List[int] = Field(..., min_length=1)


class ClientMergeResult(BaseModel):
    """Result of a multi-source client merge."""

    model_config = ConfigDict(extra="ignore")

    merged_trip_count: int = 0
    merged_invoice_count: int = 0
    merged_contact_count: int = 0


# ──────────────────────────────────────────────────────────────────────
#  Analytics (blueprint §6.4) — compact fl_chart-friendly shapes
# ──────────────────────────────────────────────────────────────────────


class AnalyticsPoint(BaseModel):
    """A single {label, value} datapoint for line/bar chart inputs."""

    model_config = ConfigDict(extra="ignore")

    label: str = ""
    value: float = 0.0


class AnalyticsRevenueResponse(BaseModel):
    """Revenue: monthly trend + per-client + per-route chart inputs."""

    model_config = ConfigDict(extra="ignore")

    trend: List[AnalyticsPoint] = []
    per_client: List[AnalyticsPoint] = []
    per_route: List[AnalyticsPoint] = []


class FleetUtilizationTruck(BaseModel):
    """Per-truck utilization row."""

    model_config = ConfigDict(extra="ignore")

    truck: str = ""
    trip_count: int = 0
    total_km: float = 0.0


class FleetUtilizationResponse(BaseModel):
    """Fleet status split + per-truck utilization."""

    model_config = ConfigDict(extra="ignore")

    status_split: Dict[str, int] = {"active": 0, "maintenance": 0, "decommissioned": 0}
    trucks: List[FleetUtilizationTruck] = []


class DriverPerformanceRow(BaseModel):
    """Per-driver performance row (NO rating — column does not exist)."""

    model_config = ConfigDict(extra="ignore")

    driver: str = ""
    trips_completed: int = 0
    on_time_pct: float = 0.0
    profit_per_km: float = 0.0
    revenue: float = 0.0


class DriverPerformanceResponse(BaseModel):
    """Driver performance rows for a sortable table."""

    model_config = ConfigDict(extra="ignore")

    rows: List[DriverPerformanceRow] = []


class InvoiceAgingResponse(BaseModel):
    """Invoice aging buckets (exact mapping of get_invoice_aging)."""

    model_config = ConfigDict(extra="ignore")

    current: float = 0.0
    bucket_31_60: float = 0.0
    bucket_61_90: float = 0.0
    overdue: float = 0.0
    total_outstanding: float = 0.0


class AnalyticsExportResponse(BaseModel):
    """Synchronous analytics CSV export → signed short-lived download URL."""

    model_config = ConfigDict(extra="ignore")

    download_url: str = ""
    expires_at: str = ""  # ISO-8601


# ──────────────────────────────────────────────────────────────────────
#  History (blueprint §6.8)
# ──────────────────────────────────────────────────────────────────────


class TripHistoryOut(BaseModel):
    """A trip-history row for the mobile trip list."""

    model_config = ConfigDict(extra="ignore")

    id: int
    client_name: str = ""
    truck_number: str = ""
    driver_name: str = ""
    origin: str = ""            # place_of_loading
    destination: str = ""       # delivery_country
    status: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    distance_km: Optional[float] = None
    total_price_eur: Optional[float] = None
    net_profit: Optional[float] = None


class RouteHistoryOut(BaseModel):
    """A route-history row from route_history_v2."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = ""               # route_fingerprint
    origin: Optional[str] = None
    destination: Optional[str] = None
    total_distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    created_at: Optional[str] = None


class TripHistoryExportFilters(BaseModel):
    """Optional filters for a trips history export."""

    model_config = ConfigDict(extra="ignore")

    status: Optional[str] = None
    client_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class TripHistoryExportRequest(BaseModel):
    """Request body for POST /mobile/history/trips/export."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["csv", "xlsx", "pdf"] = "csv"
    filters: TripHistoryExportFilters = TripHistoryExportFilters()


class TripHistoryExportJobResponse(BaseModel):
    """202 response for an accepted async export job."""

    model_config = ConfigDict(extra="ignore")

    job_id: int


class ExportJobStatusResponse(BaseModel):
    """Status of an async export job."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["processing", "success", "error"] = "processing"
    download_url: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────
#  Global search (blueprint §6.11)
# ──────────────────────────────────────────────────────────────────────


class SearchSection(BaseModel):
    """One result type: capped items + the true total count."""

    model_config = ConfigDict(extra="ignore")

    items: List[Dict[str, Any]] = []
    total_count: int = 0


class GlobalSearchResponse(BaseModel):
    """Global search across trips/clients/drivers/trucks/documents."""

    model_config = ConfigDict(extra="ignore")

    trips: SearchSection = SearchSection()
    clients: SearchSection = SearchSection()
    drivers: SearchSection = SearchSection()
    trucks: SearchSection = SearchSection()
    documents: SearchSection = SearchSection()


# ──────────────────────────────────────────────────────────────────────
#  Finance — Invoicing (blueprint §6.6)
# ──────────────────────────────────────────────────────────────────────


class InvoiceLineItemOut(BaseModel):
    """One computed invoice line (identical shape to the desktop model)."""

    model_config = ConfigDict(extra="ignore")

    description: str = ""
    quantity: float = 1.0
    unit_of_measure: str = "buc"
    unit_price: float = 0.0
    discount_percent: float = 0.0
    discount_amount: float = 0.0
    taxable_amount: Optional[float] = None
    vat_rate: float = 19.0
    total_net: Optional[float] = None
    vat_amount: Optional[float] = None
    line_total: Optional[float] = None


class InvoiceOut(BaseModel):
    """Invoice row for the mobile list/detail screens.

    ``status`` carries the REAL desktop status strings (draft, finalized,
    xml_generated, submitted_externally, queued, submitting, accepted,
    rejected, manual_review, cancelled, paid).  Totals are the server-computed
    values persisted via the desktop ``_calculate_line_items`` path.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    invoice_number: str = ""
    client_id: int = 0
    client_name: str = ""
    trip_id: Optional[int] = None
    status: str = "draft"
    issue_date: date
    due_date: date
    currency: str = "EUR"
    subtotal_net: float = 0.0
    total_vat: float = 0.0
    total_gross: float = 0.0
    total_amount: float = 0.0
    notes: str = ""
    line_items: List[InvoiceLineItemOut] = []
    efactura_status: str = ""
    efactura_xml_path: Optional[str] = None
    efactura_submission_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class InvoiceDetailOut(InvoiceOut):
    """Invoice detail: invoice fields + client/trip context for the detail screen."""

    model_config = ConfigDict(extra="ignore")

    trip_reference: str = ""
    trip_origin: str = ""
    trip_destination: str = ""
    truck_number: str = ""
    driver_name: str = ""
    client_vat: str = ""
    client_address: str = ""


class InvoiceCreateRequest(BaseModel):
    """Create an invoice from mobile.

    ``issue_date`` / ``due_date`` default to today / today+30d when omitted.
    Line items are passed through to the REAL desktop calculator
    (``InvoiceService._calculate_line_items``); totals are NEVER client-supplied.
    """

    model_config = ConfigDict(extra="forbid")

    trip_id: Optional[int] = None
    client_id: int = Field(..., gt=0)
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: str = "EUR"
    exchange_rate: float = 1.0
    invoice_type: str = "invoice"
    line_items: List[InvoiceLineItem] = []
    notes: str = ""


class InvoiceUpdateRequest(BaseModel):
    """Partial invoice update from mobile (draft only)."""

    model_config = ConfigDict(extra="forbid")

    client_id: Optional[int] = None
    trip_id: Optional[int] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    invoice_type: Optional[str] = None
    line_items: Optional[List[InvoiceLineItem]] = None
    notes: Optional[str] = None


class InvoiceTransitionRequest(BaseModel):
    """State-machine action for POST /mobile/invoices/{id}/transition.

    The machine is validated server-side against the REAL
    ``INVOICE_STATUS_TRANSITIONS`` table (desktop ``_validate_status_transition``).
    """

    model_config = ConfigDict(extra="forbid")

    action: Literal["finalize", "generate_xml", "submit", "mark_paid", "cancel"]


class CmrRequest(BaseModel):
    """CMR generation for an invoice's trip (blueprint §6.6).

    ``trip_id`` is optional — it falls back to the invoice's own trip.
    ``signature_png_base64`` is a raw base64 PNG captured by the mobile
    signature pad; it is persisted to the documents table
    (``entity_type='cmr'``, ``entity_id=<trip_id>``).
    """

    model_config = ConfigDict(extra="forbid")

    trip_id: Optional[int] = None
    language: str = "ro"
    copies: int = Field(3, ge=1, le=6)
    include_stamps: bool = True
    sender_name: str = ""
    sender_address: str = ""
    carrier_name: str = ""
    carrier_license: str = ""
    remarks: str = ""
    signature_png_base64: str = ""


class CmrOut(BaseModel):
    """Result of a mobile CMR generation.

    ``pdf_url`` is a short-lived signed download URL (KIND_DOCUMENT token —
    the same signed-URL pattern Phase 2 uses for export files).
    """

    model_config = ConfigDict(extra="ignore")

    cmr_number: str = ""
    pdf_url: str = ""


# ──────────────────────────────────────────────────────────────────────
#  Finance — Maintenance (blueprint §6.5)
# ──────────────────────────────────────────────────────────────────────


class MaintenanceScheduleOut(BaseModel):
    """An active maintenance schedule with computed overdue/next_due.

    ``overdue`` uses the REAL repository overdue thresholds
    (``schedule_is_overdue``: km / months / fixed expiry — the same source
    as the desktop health-score count).  ``next_due`` is the ISO date derived
    from fixed_expiry_date or last_done_date + interval_months (``None`` when
    the schedule has no date-based cadence).
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    truck_id: int
    truck_plate: str = ""
    maintenance_type: str = ""
    interval_km: Optional[float] = None
    interval_months: Optional[int] = None
    fixed_expiry_date: Optional[str] = None
    last_done_km: Optional[float] = None
    last_done_date: Optional[str] = None
    overdue: bool = False
    next_due: Optional[str] = None


class MaintenanceScheduleCreateRequest(BaseModel):
    """Create a maintenance schedule from mobile (gate: can_schedule_maintenance)."""

    model_config = ConfigDict(extra="forbid")

    truck_id: int = Field(..., gt=0)
    maintenance_type: str = Field(..., min_length=1, max_length=120)
    interval_km: Optional[float] = Field(None, gt=0)
    interval_months: Optional[int] = Field(None, ge=1, le=120)
    fixed_expiry_date: Optional[str] = None


class MaintenanceCostPoint(BaseModel):
    """One aggregated cost point (month or maintenance type)."""

    model_config = ConfigDict(extra="ignore")

    label: str = ""
    total: float = 0.0


class MaintenanceCostTrendOut(BaseModel):
    """Maintenance cost trend: monthly totals + per-type totals."""

    model_config = ConfigDict(extra="ignore")

    monthly: List[MaintenanceCostPoint] = []
    by_type: List[MaintenanceCostPoint] = []


# ──────────────────────────────────────────────────────────────────────
#  Team Management (blueprint §6.9, Phase 4A)
# ──────────────────────────────────────────────────────────────────────

# Roles a manager may invite or promote a team member to.  Admin is
# deliberately excluded server-side — admin users can only be created by
# the environment-admin gateway (id=0), never by another manager.
MANAGEABLE_TEAM_ROLES = ("dispatcher", "manager")


class TeamMemberOut(BaseModel):
    """A company-scoped team member row (mobile team management)."""

    model_config = ConfigDict(extra="ignore")

    id: int
    email: str
    display_name: str = ""
    role: str = ""
    is_active: bool = True
    created_at: Optional[str] = None
    driver_name: Optional[str] = None


class TeamMemberInviteRequest(BaseModel):
    """POST /mobile/team/invite body — create a new team member.

    Server-side role constraint: ``role`` must be one of ``dispatcher`` or
    ``manager`` (an ``admin`` invite is rejected with a machine-readable
    ``role_not_allowed`` error).
    """

    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=3, max_length=255)
    role: str = Field(..., min_length=1, max_length=32)


class TeamMemberPatchRequest(BaseModel):
    """PATCH /mobile/team/{user_id} body — optional role / is_active.

    ``role`` must be in ``{dispatcher, manager}`` (never ``admin``).
    ``is_active=False`` triggers the deactivation cascade (see the endpoint).
    """

    model_config = ConfigDict(extra="forbid")

    role: Optional[str] = Field(None, min_length=1, max_length=32)
    is_active: Optional[bool] = None


# ──────────────────────────────────────────────────────────────────────
#  Company Settings (blueprint §6.10, Phase 4A)
# ──────────────────────────────────────────────────────────────────────

# Real settings-table keys (desktop source of truth — services/preferences.py
# ``_SMTP_KEYS``, ``_SENSITIVE_KEYS`` and ui/views/settings_view):
#   identity block        → legal_name / vat_number / address / invoice_footer
#                           (additive mobile keys — the desktop keeps legal
#                           identity in company_config.json; the settings
#                           table keeps this endpoint tenant-scoped)
#   smtp_*                → PreferencesManager SMTP keys (sensitive: smtp_password)
#   tracking_provider     → ``tracking.platform`` (plain)
#   tracking_api_key      → ``tracking.token`` (sensitive)
#   maintenance thresholds→ ``alert_days_ahead`` / ``tacho_warning`` /
#                           ``tacho_critical`` (plain)
SMTP_SETTING_KEYS = ("smtp_server", "smtp_port", "smtp_user", "smtp_password")
TRACKING_PROVIDER_KEY = "tracking.platform"
TRACKING_API_KEY_KEY = "tracking.token"
MAINTENANCE_THRESHOLD_KEYS = {
    "maintenance_alert_days_ahead": "alert_days_ahead",
    "tacho_warning_days": "tacho_warning",
    "tacho_critical_days": "tacho_critical",
}
IDENTITY_SETTING_KEYS = ("legal_name", "vat_number", "address", "invoice_footer")


class CompanySettingsOut(BaseModel):
    """Company settings for mobile (never contains secret values).

    Secrets (``smtp_password`` / ``tracking_api_key``) are exposed ONLY as
    ``*_is_set`` booleans — the plaintext is never serialized.
    """

    model_config = ConfigDict(extra="ignore")

    legal_name: str = ""
    vat_number: str = ""
    address: str = ""
    invoice_footer: str = ""
    smtp_server: str = ""
    smtp_port: str = ""
    smtp_user: str = ""
    smtp_password_is_set: bool = False
    tracking_provider: str = ""
    tracking_api_key_is_set: bool = False
    maintenance_alert_days_ahead: int = 30
    tacho_warning_days: int = 45
    tacho_critical_days: int = 15


class CompanySettingsUpdateRequest(BaseModel):
    """PATCH /mobile/settings/company body — write-only semantics.

    Any field omitted is left unchanged.  Sensitive fields
    (``smtp_password`` / ``tracking_api_key``):
      - omitted            → unchanged
      - explicit ""        → cleared (``*_is_set`` becomes false)
      - non-empty value    → stored encrypted (is_set true)
    """

    model_config = ConfigDict(extra="forbid")

    legal_name: Optional[str] = Field(None, max_length=255)
    vat_number: Optional[str] = Field(None, max_length=64)
    address: Optional[str] = Field(None, max_length=512)
    invoice_footer: Optional[str] = Field(None, max_length=1024)
    smtp_server: Optional[str] = Field(None, max_length=255)
    smtp_port: Optional[str] = Field(None, max_length=16)
    smtp_user: Optional[str] = Field(None, max_length=255)
    smtp_password: Optional[str] = Field(None, max_length=512)
    tracking_provider: Optional[str] = Field(None, max_length=64)
    tracking_api_key: Optional[str] = Field(None, max_length=512)
    maintenance_alert_days_ahead: Optional[int] = Field(None, ge=1, le=365)
    tacho_warning_days: Optional[int] = Field(None, ge=1, le=365)
    tacho_critical_days: Optional[int] = Field(None, ge=1, le=365)


class TestEmailRequest(BaseModel):
    """POST /mobile/settings/test-email body.

    ``recipient`` defaults to the configured SMTP user when omitted.
    """

    model_config = ConfigDict(extra="forbid")

    recipient: Optional[str] = Field(None, max_length=255)


# ──────────────────────────────────────────────────────────────────────
#  Tachograph (blueprint §6.7, Phase 4A)
# ──────────────────────────────────────────────────────────────────────

TACHO_ALLOWED_EXTENSIONS = (".ddd", ".esm")


class TachoImportJobResponse(BaseModel):
    """202 response for POST /mobile/tacho/import."""

    model_config = ConfigDict(extra="ignore")

    job_id: int


class TachoComplianceDay(BaseModel):
    """One day of driver activity from a tacho import."""

    model_config = ConfigDict(extra="ignore")

    date: str
    driving_minutes: int = 0
    working_minutes: int = 0
    rest_minutes: int = 0
    availability_minutes: int = 0


class TachoComplianceResult(BaseModel):
    """Aggregated compliance result of an import (real EU thresholds)."""

    model_config = ConfigDict(extra="ignore")

    days: List[TachoComplianceDay] = []
    weekly_driving_minutes: int = 0
    weekly_limit_minutes: int = 3360  # EU_MAX_WEEKLY_DRIVING_MINUTES (tacho_service)
    violations: List[str] = []


class TachoImportJobStatusResponse(BaseModel):
    """Status poll for a tacho import job.

    ``status`` is one of ``processing`` / ``success`` / ``error``.  ``result``
    is present only on success; ``error`` carries the honest human-readable
    message (e.g. parser binary missing) on failure.
    """

    model_config = ConfigDict(extra="ignore")

    status: str
    result: Optional[TachoComplianceResult] = None
    error: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────
#  Forward-reference resolution
# ──────────────────────────────────────────────────────────────────────

DriverMyDayResponse.model_rebuild()
DriverVehicleResponse.model_rebuild()
