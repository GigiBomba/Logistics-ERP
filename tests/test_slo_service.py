"""Comprehensive unit tests for services/slo_service.py.

Tests cover get_slo_service, get_report, and get_status_page —
validating return types and expected dictionary keys.
"""

from __future__ import annotations

import pytest

from services.slo_service import get_report, get_slo_service, get_status_page


# ──────────────────────────────────────────────────────────────
# get_slo_service
# ──────────────────────────────────────────────────────────────


class TestGetSloService:
    """Return the AppState class (stub)."""

    def test_returns_app_state(self):
        from services.app_state import AppState

        svc = get_slo_service()
        assert svc is AppState
        # AppState is a singleton with _instance attribute
        assert hasattr(svc, "_instance")

    def test_returns_class_not_instance(self):
        svc = get_slo_service()
        # It should be a class, not an instance
        assert isinstance(svc, type)


# ──────────────────────────────────────────────────────────────
# get_report
# ──────────────────────────────────────────────────────────────


class TestGetReport:
    """Return a status report dictionary."""

    def test_returns_dict(self):
        report = get_report()
        assert isinstance(report, dict)

    def test_has_status_key(self):
        report = get_report()
        assert "status" in report
        assert report["status"] == "ok"

    def test_has_uptime_key(self):
        report = get_report()
        assert "uptime" in report
        assert report["uptime"] == 0

    def test_has_services_key(self):
        report = get_report()
        assert "services" in report
        assert isinstance(report["services"], dict)

    def test_exact_structure(self):
        report = get_report()
        assert report == {"status": "ok", "uptime": 0, "services": {}}


# ──────────────────────────────────────────────────────────────
# get_status_page
# ──────────────────────────────────────────────────────────────


class TestGetStatusPage:
    """Return a status page dictionary."""

    def test_returns_dict(self):
        page = get_status_page()
        assert isinstance(page, dict)

    def test_has_status_key(self):
        page = get_status_page()
        assert "status" in page

    def test_status_is_operational(self):
        page = get_status_page()
        assert page["status"] == "operational"

    def test_exact_structure(self):
        page = get_status_page()
        assert page == {"status": "operational"}
