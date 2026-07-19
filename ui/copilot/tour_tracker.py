"""Tour completion tracker — persists tutorial state to a local JS file.

Blueprint: §34.7 — Onboarding Tour (first launch tracking).

A simple JSON file on disk records which walkthroughs the user has completed.
This is deliberately NOT a backend API call — the tutorial should work even
when the user is offline or using the local-only version of the app.

File location: ~/.operion/.tour_completed.json
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ── File location ─────────────────────────────────────────────────────────

APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".operion")
TOUR_COMPLETED_FILE = os.path.join(APP_DATA_DIR, ".tour_completed.json")


def _ensure_app_data_dir() -> None:
    """Create the app data directory if it doesn't exist."""
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
    except OSError as exc:
        logger.warning("Cannot create app data dir %s: %s", APP_DATA_DIR, exc)


def _read_tour_data() -> dict[str, Any]:
    """Read the tour completion file, returning default data on any error."""
    try:
        if not os.path.exists(TOUR_COMPLETED_FILE):
            return {"_version": "1.0", "tours": {}}
        with open(TOUR_COMPLETED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"_version": "1.0", "tours": {}}
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read tour data: %s", exc)
        return {"_version": "1.0", "tours": {}}


def _write_tour_data(data: dict[str, Any]) -> None:
    """Write tour data to the completion file."""
    _ensure_app_data_dir()
    try:
        with open(TOUR_COMPLETED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.error("Failed to write tour data: %s", exc)


# ── Public API ────────────────────────────────────────────────────────────


def mark_tour_completed(workflow_id: str = "app_overview") -> None:
    """Mark a walkthrough workflow as completed.

    Records the completion timestamp so the tour won't auto-start again.

    Args:
        workflow_id: The workflow ID that was completed (default: app_overview).
    """
    data = _read_tour_data()
    tours = data.setdefault("tours", {})
    tours[workflow_id] = {
        "completed": True,
        "completed_at": datetime.utcnow().isoformat() + "Z",
    }
    _write_tour_data(data)
    logger.info("Tour marked completed: %s", workflow_id)


def is_tour_completed(workflow_id: str = "app_overview") -> bool:
    """Check if a walkthrough has been completed.

    Args:
        workflow_id: The workflow ID to check (default: app_overview).

    Returns:
        True if the workflow has been completed at least once.
    """
    data = _read_tour_data()
    tours = data.get("tours", {})
    info = tours.get(workflow_id, {})
    return bool(info.get("completed", False))


def clear_tour_completed(workflow_id: str = "app_overview") -> None:
    """Reset a walkthrough so it can be replayed.

    Args:
        workflow_id: The workflow ID to reset (default: app_overview).
    """
    data = _read_tour_data()
    tours = data.setdefault("tours", {})
    tours.pop(workflow_id, None)
    _write_tour_data(data)
    logger.info("Tour reset: %s", workflow_id)


def clear_all_tours() -> None:
    """Reset ALL walkthrough completions."""
    data = _read_tour_data()
    data["tours"] = {}
    _write_tour_data(data)
    logger.info("All tours reset")


def get_completed_tours() -> list[str]:
    """Return list of all completed workflow IDs."""
    data = _read_tour_data()
    tours = data.get("tours", {})
    return [wid for wid, info in tours.items() if info.get("completed")]


def get_completion_count(workflow_id: str) -> int:
    """Return how many times a workflow has been completed."""
    data = _read_tour_data()
    tours = data.get("tours", {})
    info = tours.get(workflow_id, {})
    return info.get("count", 1 if info.get("completed") else 0)


def increment_completion_count(workflow_id: str) -> None:
    """Increment the completion count for a workflow."""
    data = _read_tour_data()
    tours = data.setdefault("tours", {})
    info = tours.setdefault(workflow_id, {})
    info["completed"] = True
    info["count"] = info.get("count", 0) + 1
    info["completed_at"] = datetime.utcnow().isoformat() + "Z"
    _write_tour_data(data)
