"""Input/output models for DispatchService."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UndoToken:
    """Opaque token the UI can push onto the undo stack."""
    operation: str                     # "assign_truck", "assign_driver", "assign_both", "transition"
    trip_id: int
    previous_state: dict[str, Any]     # snapshot of relevant trip fields before mutation
    undo_description: str              # "Unassign truck AA-12-BBB from trip #42"


@dataclass(frozen=True)
class DispatchResult:
    """Result of a single dispatch operation."""
    success: bool
    trip_id: int
    operation: str                     # "assign_truck", "assign_driver", "complete", "cancel", etc.
    message: str                       # human-readable success/error message
    undo_token: UndoToken | None = None
    details: dict[str, Any] = field(default_factory=dict)  # {"truck_plate": "...", "driver_name": "..."}


@dataclass(frozen=True)
class BulkDispatchResult:
    """Result of a bulk dispatch operation."""
    total: int
    succeeded: int
    failed: int
    results: list[DispatchResult] = field(default_factory=list)
    undo_tokens: list[UndoToken] = field(default_factory=list)


@dataclass
class DispatchBoardFilters:
    """Filters for get_dispatch_board_data."""
    include_statuses: list[str] | None = None  # None = all non-terminal
    delivered_window_days: int = 30
    exclude_archived: bool = True
    limit: int = 2000


@dataclass
class DispatchDataResponse:
    """Response from get_dispatch_board_data."""
    column_trips: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    alert_counts: dict[int, int] = field(default_factory=dict)
    status_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class TruckAvailability:
    """Result of a truck availability check."""
    available: bool
    blocks: list[str] = field(default_factory=list)      # ["Insurance expired", "Maintenance due"]
    conflicts: list[dict] = field(default_factory=list)  # from conflict_service
    status_text: str = ""


@dataclass
class DriverAvailability:
    """Result of a driver availability check."""
    available: bool
    blocks: list[str] = field(default_factory=list)      # ["License expired", "Hours exceeded"]
    conflicts: list[dict] = field(default_factory=list)
    weekly_hours: float = 0.0
    violations: int = 0
    status_text: str = ""
