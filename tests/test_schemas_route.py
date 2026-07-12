"""Tests for backend/schemas/route.py — RouteBase, RouteResponse."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.route import RouteBase, RouteResponse


# ── RouteBase ─────────────────────────────────────────────────────────────────


class TestRouteBase:
    """fingerprint="", total_km=0.0, extra="forbid"."""

    def test_defaults(self):
        inst = RouteBase()
        assert inst.fingerprint == ""
        assert inst.total_km == 0.0

    def test_custom_values(self):
        inst = RouteBase(fingerprint="abc123", total_km=150.5)
        assert inst.fingerprint == "abc123"
        assert inst.total_km == 150.5

    def test_total_km_float_coercion(self):
        inst = RouteBase(total_km=100)  # int → float
        assert inst.total_km == 100.0

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            RouteBase(fingerprint="x", unknown="y")  # type: ignore[call-arg]


# ── RouteResponse ─────────────────────────────────────────────────────────────


class TestRouteResponse:
    """Extends RouteBase, adds id (required), profile (default ""), created_at (default "")."""

    def test_valid(self):
        inst = RouteResponse(id=1)
        assert inst.id == 1
        assert inst.profile == ""
        assert inst.created_at == ""
        assert inst.fingerprint == ""

    def test_all_fields(self):
        inst = RouteResponse(
            id=1,
            fingerprint="fp-001",
            total_km=250.0,
            profile="fastest",
            created_at="2025-01-01T00:00:00Z",
        )
        assert inst.profile == "fastest"
        assert inst.total_km == 250.0

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            RouteResponse()  # type: ignore[call-arg]

    def test_extra_field_ignored(self):
        """extra="ignore"."""
        inst = RouteResponse(id=1, unknown="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "unknown")
