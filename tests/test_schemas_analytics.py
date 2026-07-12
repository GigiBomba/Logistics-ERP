"""Tests for backend/schemas/analytics.py — AnalyticsResponse."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.analytics import AnalyticsResponse


class TestAnalyticsResponse:
    """data (required dict), cached (default False), extra="forbid"."""

    def test_required_only(self):
        inst = AnalyticsResponse(data={"total_trips": 150, "total_km": 12000.5})
        assert inst.data == {"total_trips": 150, "total_km": 12000.5}
        assert inst.cached is False

    def test_cached_true(self):
        inst = AnalyticsResponse(data={}, cached=True)
        assert inst.cached is True

    def test_empty_data(self):
        inst = AnalyticsResponse(data={})
        assert inst.data == {}

    def test_nested_data(self):
        inst = AnalyticsResponse(data={"aggregates": {"count": 10, "sum": 5000.0}})
        assert inst.data["aggregates"]["count"] == 10

    def test_missing_data_raises(self):
        with pytest.raises(ValidationError):
            AnalyticsResponse()  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            AnalyticsResponse(data={}, extra_field="x")  # type: ignore[call-arg]

    def test_serialization_round_trip(self):
        original = AnalyticsResponse(data={"metric": 42}, cached=True)
        dumped = original.model_dump()
        restored = AnalyticsResponse.model_validate(dumped)
        assert restored == original
