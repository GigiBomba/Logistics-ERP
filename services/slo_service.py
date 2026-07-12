"""Stub SLO/SLA service."""

from __future__ import annotations


def get_slo_service():
    from services.app_state import AppState
    return AppState


def get_report():
    return {"status": "ok", "uptime": 0, "services": {}}


def get_status_page():
    return {"status": "operational"}
