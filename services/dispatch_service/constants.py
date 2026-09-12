"""Canonical dispatch-board constants — single source of truth.

``STATUS_TO_COLUMN`` / ``COLUMN_KEYS`` were historically duplicated between
``services/dispatch_service/dispatch_service.py`` and
``backend/api/v1/dispatch.py``; both now import them from here so the
board's column semantics can never drift.
"""

STATUS_TO_COLUMN: dict[str, str] = {
    "Planned": "Planned",
    "Scheduled": "Planned",
    "Pending": "Planned",
    "Loading": "Loading",
    "Preparing": "Loading",
    "Pickup": "Loading",
    "In Transit": "In Transit",
    "InTransit": "In Transit",
    "Active": "In Transit",
    "InProgress": "In Transit",
    "Delivered": "Delivered",
    "Completed": "Delivered",
    "Done": "Delivered",
    "Invoiced": "Delivered",
    "Paid": "Delivered",
    "Cancelled": "Cancelled",
}

COLUMN_KEYS = ["Planned", "Loading", "In Transit", "Delivered", "Cancelled"]