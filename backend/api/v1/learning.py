"""Learning & developer resource endpoints.

GET /tutorials                  — List tutorials
GET /tutorials/:slug           — Single tutorial
GET /developers/resources      — Developer resources
GET /developers/toolkit/versions — Toolkit download versions
"""
from __future__ import annotations


from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from backend.dependencies_security import get_current_user

router = APIRouter(tags=["learning"])


_HARDCODED_TUTORIALS = [
    {"id": "tut-1", "title": "Getting Started with Operion", "slug": "getting-started", "excerpt": "Learn the basics of the Operion logistics platform.", "content": "<h2>Welcome to Operion</h2><p>This guide walks you through the initial setup of your Operion account.</p>", "category": "beginner", "reading_time_minutes": 5, "published_at": "2026-01-01"},
    {"id": "tut-2", "title": "Managing Your Fleet", "slug": "managing-fleet", "excerpt": "Add, edit, and manage your vehicles.", "content": "<h2>Fleet Management</h2><p>Learn how to manage your vehicles effectively.</p>", "category": "intermediate", "reading_time_minutes": 8, "published_at": "2026-01-15"},
]

_HARDCODED_DEV_RESOURCES = [
    {"id": "dr-1", "title": "REST API Reference", "description": "Complete API documentation for the Operion platform.", "icon": "FileText", "type": "api", "href": "/docs/api-reference"},
    {"id": "dr-2", "title": "Operion Toolkit", "description": "Desktop tools for advanced fleet management.", "icon": "Wrench", "type": "toolkit", "href": "/developers/toolkit"},
]

_HARDCODED_TOOLKIT_VERSIONS = [
    {"version": "3.2.0", "release_date": "2026-07-01", "windows_url": "#", "macos_url": "#", "linux_url": "#", "size_mb": 245, "changelog": "Bug fixes and performance improvements.", "requirements": {"os": ["Windows 10+", "macOS 13+", "Ubuntu 22.04+"], "ram": "8 GB", "storage": "500 MB", "processor": "x64"}, "checksums": {"windows_sha256": "abc123"}},
]


@router.get("/tutorials")
def list_tutorials(category: Optional[str] = Query(None), search: Optional[str] = Query(None)):
    items = _HARDCODED_TUTORIALS
    if category:
        items = [t for t in items if t["category"] == category]
    if search:
        s = search.lower()
        items = [t for t in items if s in t["title"].lower() or s in t["excerpt"].lower()]
    return items


@router.get("/tutorials/{slug}")
def get_tutorial(slug: str):
    for t in _HARDCODED_TUTORIALS:
        if t["slug"] == slug:
            return t
    raise HTTPException(status_code=404, detail="Tutorial not found")


@router.get("/developers/resources")
def get_dev_resources():
    return _HARDCODED_DEV_RESOURCES


@router.get("/developers/toolkit/versions")
def get_toolkit_versions():
    return _HARDCODED_TOOLKIT_VERSIONS
