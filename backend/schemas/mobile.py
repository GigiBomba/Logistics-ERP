"""Mobile API schemas — condensed Pydantic models for mobile clients.

These DTOs are purpose-built for mobile: bandwidth-optimised, flattened
where possible, and containing only the fields a mobile screen needs.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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


# ──────────────────────────────────────────────────────────────────────
#  Dispatcher / Manager
# ──────────────────────────────────────────────────────────────────────

class DispatcherOverviewResponse(BaseModel):
    """Aggregate dispatcher dashboard."""
    active_jobs: int = 0
    active_drivers: int = 0
    open_alerts: int = 0
    vehicles_on_road: int = 0


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
#  Forward-reference resolution
# ──────────────────────────────────────────────────────────────────────

DriverMyDayResponse.model_rebuild()
DriverVehicleResponse.model_rebuild()
