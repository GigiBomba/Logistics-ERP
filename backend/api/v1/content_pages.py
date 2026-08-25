"""Content page endpoints — all return hardcoded data.

GET /api/v1/changelog       — Changelog entries
GET /api/v1/roadmap         — Roadmap items
GET /api/v1/status          — Service status  
GET /api/v1/announcements   — Announcements
"""
from __future__ import annotations


import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from backend.dependencies_security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["content-pages"])


_HARDCODED_CHANGELOG = [
    {
        "version": "3.2.0",
        "release_date": "2026-07-01",
        "sections": [
            {"type": "added", "items": ["AI Co-Pilot voice commands", "Multi-language OCR support", "New analytics dashboard"]},
            {"type": "changed", "items": ["Improved route optimization algorithm", "Updated invoice templates"]},
            {"type": "fixed", "items": ["Route export with special characters", "Booking calendar timezone issues"]},
        ],
    },
    {
        "version": "3.1.0",
        "release_date": "2026-05-15",
        "sections": [
            {"type": "added", "items": ["Real-time GPS tracking for all vehicles", "Driver mobile app beta"]},
            {"type": "fixed", "items": ["CMR generation encoding issues", "Payment reconciliation rounding"]},
        ],
    },
]

_HARDCODED_ROADMAP = [
    {"id": "rm-1", "title": "AI-Powered Route Optimization", "description": "Machine learning models that learn from your fleet's historical data to suggest optimal routes.", "status": "in_progress", "category": "AI & Automation", "target_date": "2026-Q3"},
    {"id": "rm-2", "title": "Mobile Driver App", "description": "Native mobile app for drivers with navigation, document scanning, and real-time messaging.", "status": "in_progress", "category": "Mobile", "target_date": "2026-Q3"},
    {"id": "rm-3", "title": "Freight Exchange Marketplace", "description": "Connect with carriers and shippers to find and list available loads.", "status": "planned", "category": "Platform", "target_date": "2026-Q4"},
]

_HARDCODED_STATUS = [
    {"name": "API", "services": [{"name": "Core API", "status": "operational", "updated_at": "2026-07-20T00:00:00Z"}, {"name": "Webhook Delivery", "status": "operational", "updated_at": "2026-07-20T00:00:00Z"}]},
    {"name": "AI Services", "services": [{"name": "AI Co-Pilot", "status": "operational", "updated_at": "2026-07-20T00:00:00Z"}, {"name": "OCR Processing", "status": "operational", "updated_at": "2026-07-20T00:00:00Z"}]},
]

_HARDCODED_ANNOUNCEMENTS = [
    {"id": "ann-1", "title": "New AI Co-Pilot Features Released", "content": "Voice commands and multi-language support are now available.", "severity": "info", "is_pinned": True, "published_at": "2026-07-01"},
    {"id": "ann-2", "title": "Scheduled Maintenance", "content": "API will be briefly unavailable on July 25, 02:00-03:00 UTC.", "severity": "warning", "is_pinned": True, "published_at": "2026-07-15"},
]


@router.get("/changelog")
def get_changelog():
    return _HARDCODED_CHANGELOG


@router.get("/roadmap")
def get_roadmap(status: Optional[str] = Query(None)):
    if status:
        return [item for item in _HARDCODED_ROADMAP if item["status"] == status]
    return _HARDCODED_ROADMAP


@router.get("/status")
def get_status():
    return _HARDCODED_STATUS


@router.get("/announcements")
def get_announcements():
    return _HARDCODED_ANNOUNCEMENTS
