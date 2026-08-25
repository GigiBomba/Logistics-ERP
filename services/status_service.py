"""Trip status normalization and canonical column mapping.

Extracted from UI views to avoid duplicating status normalization logic
across dispatch_board_view, route_planner_view, and history_view.
"""

from __future__ import annotations

from typing import Any

# ── Canonical status → column mapping ─────────────────────────────
# Normalizes all raw status strings stored in the DB into one of 5
# column groups used by the dispatch board kanban and other views.
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

# ── Valid status transitions (imported from event_bus for convenience) ──
VALID_TRANSITIONS: dict[str, list[str]] = {
    "Planned": ["Loading", "Cancelled"],
    "Loading": ["Planned", "In Transit", "Cancelled"],
    "In Transit": ["Loading", "Delivered", "Cancelled"],
    "Delivered": ["In Transit", "Invoiced", "Cancelled"],
    "Invoiced": ["Delivered", "Paid", "Cancelled"],
    "Paid": ["Invoiced"],
    "Cancelled": ["Planned"],
}

# ── Column display definitions ────────────────────────────────────
# NOTE: the `color` field was removed — it was dead data carrying the OLD
# (pre-audit) dispatch-board palette (Planned=dark gray, In Transit=blue).
# Nothing consumed it; the live dispatch board renders from
# board_state.COLUMN_DEFS (tokenized). Only `key` is used here (ordering).
COLUMN_DEFS: list[dict[str, Any]] = [
    {"key": "Planned",    "i18n_key": "dispatch_board.col_planned"},
    {"key": "Loading",    "i18n_key": "dispatch_board.col_loading"},
    {"key": "In Transit", "i18n_key": "dispatch_board.col_in_transit"},
    {"key": "Delivered",  "i18n_key": "dispatch_board.col_delivered"},
    {"key": "Cancelled",  "i18n_key": "dispatch_board.col_cancelled"},
]


def canonical_status(raw: str) -> str:
    """Normalize a raw status string to its canonical column name.

    Args:
        raw: Any raw status string from the DB (e.g. "InTransit", "Active", "Done").

    Returns:
        The canonical column name ("Planned", "Loading", "In Transit",
        "Delivered", or "Cancelled"). Returns the raw string unchanged
        if no mapping exists.
    """
    return STATUS_TO_COLUMN.get(raw, raw)


def allowed_transitions(current: str) -> list[str]:
    """Return list of statuses the trip can transition to.

    Args:
        current: The current status.

    Returns:
        List of valid next statuses. Empty list if current is unknown.
    """
    return VALID_TRANSITIONS.get(current, [])


def is_terminal(status: str) -> bool:
    """Return True if the status is a terminal (end) state."""
    terminal = {"Delivered", "Invoiced", "Paid", "Cancelled"}
    return canonical_status(status) in terminal


def column_for_status(status: str) -> str:
    """Return the kanban column key for a given status."""
    return canonical_status(status)


def status_display_order() -> list[str]:
    """Return the canonical order of status columns."""
    return [c["key"] for c in COLUMN_DEFS]
