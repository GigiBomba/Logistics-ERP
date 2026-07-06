"""Tests for route_compliance.RouteComplianceAnalyzer."""

from __future__ import annotations

from dataclasses import fields
from unittest.mock import patch

import pytest

from services.route_compliance import TOLL_COUNTRIES, RouteComplianceAnalyzer, RouteComplianceSummary


@pytest.fixture
def analyzer() -> RouteComplianceAnalyzer:
    return RouteComplianceAnalyzer()


@pytest.fixture(autouse=True)
def mock_t():
    """Mock t() so that summary/explanation text is predictable."""
    def _mock_t(key: str, *args, **kwargs):
        fmt_map = {
            "compliance.traversed": "Traversed: {}",
            "compliance.toll_countries": "Toll countries: {}",
            "compliance.border_crossings": "Border crossings: {}",
            "compliance.extra_distance": "Extra distance: {} km",
            "compliance.why_chosen": "Chosen: {}, {}",
        }
        fmt = fmt_map.get(key, key)
        if args or kwargs:
            try:
                return fmt.format(*args, **kwargs)
            except (KeyError, IndexError, ValueError):
                return fmt
        return fmt

    with patch("services.route_compliance.t", side_effect=_mock_t):
        yield


class TestRouteComplianceAnalyzer:
    def test_empty_route(self, analyzer: RouteComplianceAnalyzer):
        result = analyzer.analyze({})
        assert result.traversed == []
        assert result.toll_countries == []
        assert result.excluded_avoided == []
        assert result.border_crossings == 0
        assert result.extra_distance_km == 0.0
        assert result.reroute_reason == ""
        assert result.note == ""

    def test_empty_route_with_empty_lists(self, analyzer: RouteComplianceAnalyzer):
        route = {"detected_countries": [], "excluded_countries_requested": []}
        result = analyzer.analyze(route)
        assert result.traversed == []
        assert result.excluded_avoided == []
        assert result.border_crossings == 0

    def test_countries_but_no_exclusions(self, analyzer: RouteComplianceAnalyzer):
        route = {"detected_countries": ["FR", "DE", "NL"]}
        result = analyzer.analyze(route)
        assert result.traversed == ["FR", "DE", "NL"]
        assert result.excluded_avoided == []
        assert result.border_crossings == 2

    def test_toll_countries_detected(self, analyzer: RouteComplianceAnalyzer):
        route = {"detected_countries": ["FR", "IT", "DE"]}
        result = analyzer.analyze(route)
        assert "IT" in result.toll_countries
        assert "FR" in result.toll_countries
        assert "DE" in result.toll_countries  # DE is in TOLL_COUNTRIES
        all_toll = set(result.toll_countries)
        assert all_toll.issubset(TOLL_COUNTRIES)

    def test_no_toll_countries(self, analyzer: RouteComplianceAnalyzer):
        route = {"detected_countries": ["RO", "BG", "HU"]}
        result = analyzer.analyze(route)
        assert result.toll_countries == []

    def test_excluded_countries_avoided(self, analyzer: RouteComplianceAnalyzer):
        route = {
            "detected_countries": ["FR", "DE"],
            "excluded_countries_requested": ["IT", "CH"],
        }
        result = analyzer.analyze(route)
        assert "IT" in result.excluded_avoided
        assert "CH" in result.excluded_avoided
        assert "FR" not in result.excluded_avoided

    def test_excluded_country_still_traversed(self, analyzer: RouteComplianceAnalyzer):
        """If an excluded country is still in the route, it's NOT in excluded_avoided."""
        route = {
            "detected_countries": ["FR", "DE", "IT"],
            "excluded_countries_requested": ["IT"],
        }
        result = analyzer.analyze(route)
        assert result.excluded_avoided == []

    def test_extra_distance(self, analyzer: RouteComplianceAnalyzer):
        route = {"extra_distance_km": "150.5"}
        result = analyzer.analyze(route)
        assert result.extra_distance_km == 150.5

    def test_extra_distance_zero(self, analyzer: RouteComplianceAnalyzer):
        route = {"extra_distance_km": 0}
        result = analyzer.analyze(route)
        assert result.extra_distance_km == 0.0

    def test_reroute_reason(self, analyzer: RouteComplianceAnalyzer):
        route = {"reroute_reason": "toll_avoidance", "note": "Avoided IT tolls"}
        result = analyzer.analyze(route)
        assert result.reroute_reason == "toll_avoidance"
        assert result.note == "Avoided IT tolls"

    def test_cached_route(self, analyzer: RouteComplianceAnalyzer):
        route = {"cached": True, "note": "Cached route used"}
        result = analyzer.analyze(route)
        assert result.explanation_text != ""

    def test_single_country_no_borders(self, analyzer: RouteComplianceAnalyzer):
        route = {"detected_countries": ["FR"]}
        result = analyzer.analyze(route)
        assert result.border_crossings == 0

    def test_summary_text_format(self, analyzer: RouteComplianceAnalyzer):
        route = {"detected_countries": ["FR", "IT"]}
        result = analyzer.analyze(route)
        assert "Traversed:" in result.summary_text
        assert "FR" in result.summary_text
        assert "IT" in result.summary_text
        assert "Border crossings:" in result.summary_text

    def test_extra_distance_in_summary(self, analyzer: RouteComplianceAnalyzer):
        route = {"detected_countries": ["FR"], "extra_distance_km": 50}
        result = analyzer.analyze(route)
        assert "Extra distance" in result.summary_text

    def test_reroute_reason_chosen_no_explanation(self, analyzer: RouteComplianceAnalyzer):
        """reroute_reason 'chosen' should not produce an explanation."""
        route = {"reroute_reason": "chosen", "note": "User picked this route"}
        result = analyzer.analyze(route)
        assert result.explanation_text == ""

    def test_reroute_reason_with_explanation(self, analyzer: RouteComplianceAnalyzer):
        route = {"reroute_reason": "toll_avoidance", "note": "Avoided tolls"}
        result = analyzer.analyze(route)
        assert "Chosen:" in result.explanation_text
        assert "toll_avoidance" in result.explanation_text


class TestRouteComplianceSummaryDataclass:
    def test_all_fields_present(self):
        """Verify the dataclass has all expected fields."""
        field_names = {f.name for f in fields(RouteComplianceSummary)}
        expected = {
            "traversed", "toll_countries", "excluded_avoided",
            "border_crossings", "extra_distance_km", "reroute_reason",
            "note", "summary_text", "explanation_text",
        }
        assert field_names == expected

    def test_default_construction(self):
        summary = RouteComplianceSummary(
            traversed=["FR"],
            toll_countries=["IT"],
            excluded_avoided=[],
            border_crossings=1,
            extra_distance_km=0.0,
            reroute_reason="",
            note="",
            summary_text="test",
            explanation_text="",
        )
        assert summary.traversed == ["FR"]
        assert summary.border_crossings == 1
        assert summary.summary_text == "test"


class TestTollCountries:
    def test_toll_countries_is_frozenset(self):
        assert isinstance(TOLL_COUNTRIES, frozenset)

    def test_toll_countries_contains_expected(self):
        assert "IT" in TOLL_COUNTRIES
        assert "FR" in TOLL_COUNTRIES
        assert "PL" in TOLL_COUNTRIES

    def test_non_toll_countries_not_in_set(self):
        assert "RO" not in TOLL_COUNTRIES
        assert "BG" not in TOLL_COUNTRIES
