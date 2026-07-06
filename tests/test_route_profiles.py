"""Tests for route_profiles module.

The module reads `Config.GRAPHHOPPER_PROFILES` at import time, so these
tests use the real Config class (no mocking needed since it's pure data).
"""

from __future__ import annotations

import pytest

from services.route_profiles import (
    GRAPHHOPPER_PROFILES,
    gh_profile_for_ui_label,
    ui_label_for_profile,
)

# Known mapping from Config.GRAPHHOPPER_PROFILES
KNOWN_MAPPING = {
    "Recommended": "truck",
    "Fastest": "truck_fast",
    "Cheapest": "truck_cheap",
    "Safest": "truck_safe",
    "Shortest": "truck_short",
}


class TestUiLabelForProfile:
    def test_known_profiles_map_to_labels(self):
        for label, gh_profile in KNOWN_MAPPING.items():
            assert ui_label_for_profile(gh_profile) == label

    def test_unknown_profile_returns_itself(self):
        assert ui_label_for_profile("bike") == "bike"

    def test_none_returns_recommended(self):
        assert ui_label_for_profile(None) == "Recommended"

    def test_empty_string_returns_recommended(self):
        assert ui_label_for_profile("") == "Recommended"

    def test_whitespace_only_profile(self):
        """A whitespace string is truthy, so it's returned as-is if not found."""
        result = ui_label_for_profile("   ")
        assert result == "   "

    def test_case_sensitive(self):
        """The reverse mapping is case-sensitive."""
        result = ui_label_for_profile("Truck")
        assert result == "Truck"  # not "Recommended" since key is lowercase in GH profiles

    def test_all_profiles_from_config_are_mapped(self):
        """Every value in GRAPHHOPPER_PROFILES should map back to a label."""
        for _, gh_profile in GRAPHHOPPER_PROFILES.items():
            label = ui_label_for_profile(gh_profile)
            assert label is not None
            assert isinstance(label, str)


class TestGhProfileForUiLabel:
    def test_known_labels_map_to_profiles(self):
        for label, gh_profile in KNOWN_MAPPING.items():
            assert gh_profile_for_ui_label(label) == gh_profile

    def test_unknown_label_returns_truck(self):
        assert gh_profile_for_ui_label("Unknown") == "truck"

    def test_empty_string_returns_truck(self):
        assert gh_profile_for_ui_label("") == "truck"

    def test_none_returns_truck(self):
        assert gh_profile_for_ui_label(None) == "truck"  # type: ignore[arg-type]

    def test_case_sensitive(self):
        """The mapping is case-sensitive, so lowercase label returns 'truck'."""
        assert gh_profile_for_ui_label("recommended") == "truck"

    def test_all_labels_from_config_are_mapped(self):
        """Every key in GRAPHHOPPER_PROFILES should map to a profile."""
        for label in GRAPHHOPPER_PROFILES:
            profile = gh_profile_for_ui_label(label)
            assert profile is not None
            assert isinstance(profile, str)


class TestGraphhopperProfilesConstant:
    def test_is_dict(self):
        assert isinstance(GRAPHHOPPER_PROFILES, dict)

    def test_contains_expected_labels(self):
        for label in KNOWN_MAPPING:
            assert label in GRAPHHOPPER_PROFILES

    def test_contains_expected_profiles(self):
        for profile in KNOWN_MAPPING.values():
            assert profile in GRAPHHOPPER_PROFILES.values()

    def test_recommended_is_truck(self):
        assert GRAPHHOPPER_PROFILES["Recommended"] == "truck"
